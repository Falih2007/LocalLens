from pathlib import Path
import autotest
import device
import cluster
import io, zipfile
from urllib.parse import unquote, urlsplit
import re
import os, sys, json, platform, subprocess, threading, time, uuid, secrets, webbrowser, shutil, math
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('LOCALLENS_DATA', str(ROOT / 'data')))
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()
JOB = {'status': 'idle'}
PROC = None
BUSY = False
CLUSTER = cluster.Manager(DATA)


def now(): return datetime.now(timezone.utc).isoformat()
def run(args, timeout=30):
    return subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, creationflags=0x08000000 if os.name == 'nt' else 0)

def hardware():
    h = {'os': platform.platform(), 'cpu': platform.processor() or 'Unknown', 'threads': os.cpu_count(), 'ram_gib': None, 'available_gib': None, 'gpus': [], 'npus': [], 'warnings': [], 'detected_at': now(), 'device_id':device.current_device_id()}
    if os.name == 'nt':
        script = "$ErrorActionPreference='Stop'; $o=Get-CimInstance Win32_OperatingSystem; $c=Get-CimInstance Win32_Processor; @{os=$o.Caption;cpu=($c.Name -join ', ');ram_gib=[math]::Round($o.TotalVisibleMemorySize/1MB,2);available_gib=[math]::Round($o.FreePhysicalMemory/1MB,2);gpus=@(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion);npus=@(Get-PnpDevice -PresentOnly | Where-Object {$_.FriendlyName -match '(^|[^a-z])NPU([^a-z]|$)|AI Boost|Neural'} | Select-Object FriendlyName,Status)} | ConvertTo-Json -Depth 4 -Compress"
        try:
            p = run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script])
            if p.returncode: raise RuntimeError(p.stderr.strip())
            h.update(json.loads(p.stdout))
        except Exception as e: h['warnings'].append('Windows hardware query unavailable: '+str(e))
    else: h['warnings'].append('Full hardware detection is Windows-only.')
    h['warnings'].append('GPU memory is intentionally not inferred from WMI AdapterRAM; integrated graphics share system memory.')
    return h

def advisor(h):
    available = h.get('available_gib')
    catalog = [('TinyLlama 1.1B',1.1),('Qwen3 4B',4),('Qwen3 8B',8),('Gemma 3 12B',12),('Qwen3 32B',32),('Llama 3.3 70B',70)]
    out=[]
    for name,b in catalog:
        weights=round(b*1e9*0.60/(1024**3),1)
        needed=round(weights*1.15+2,1)
        status='Unknown memory' if available is None else ('Likely fits' if needed<available*.8 else 'Tight fit' if needed<available else 'Insufficient free RAM')
        out.append({'name':name,'parameters_b':b,'weights_gib':weights,'required_gib':needed,'status':status,'evidence':'estimated','assumption':'Q4-class weights (~0.60 bytes/parameter), 15% runtime overhead + 2 GiB context/workspace. CPU RAM fit only; architecture, context, quantization and GPU limits vary. No speed prediction.'})
    return out

def openvino_command(*args):
    if getattr(sys, 'frozen', False):
        return [sys.executable, '--openvino-worker', *args]
    return [sys.executable, str(ROOT/'openvino_adapter.py'), *args]


def probe_openvino():
    if getattr(sys, 'frozen', False):
        from importlib.util import find_spec
        if find_spec('openvino') is None:
            return {'status':'unavailable','message':'The optional Intel OpenVINO runtime is not bundled.','devices':[]}
    try:
        p=subprocess.run(openvino_command(), capture_output=True, text=True, encoding='utf-8',
                         errors='replace', timeout=45, stdin=subprocess.DEVNULL,
                         creationflags=0x08000000 if os.name=='nt' else 0,
                         env={**os.environ, 'PYINSTALLER_RESET_ENVIRONMENT':'1'})
        if p.returncode:
            raise RuntimeError(p.stderr.strip()[-1000:] or 'OpenVINO runtime exited unexpectedly.')
        return json.loads(p.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError) as error:
        return {'status':'unavailable','message':str(error),'devices':[]}

def parse_bench(stdout, target):
    rows=json.loads(stdout)
    if not isinstance(rows,list) or not rows: raise ValueError('Expected a nonempty llama-bench JSON array.')
    metrics=[]
    for row in rows:
        speed=row.get('avg_ts')
        if isinstance(speed,bool) or not isinstance(speed,(float,int)) or not math.isfinite(speed) or speed<=0: raise ValueError('Invalid measured throughput.')
        ngl=row.get('n_gpu_layers',0)
        if target=='gpu' and (not row.get('gpu_info') or not isinstance(ngl,int) or ngl==0):
            raise ValueError('GPU execution could not be verified from benchmark metadata. Raw logs are retained; no GPU score saved.')
        metrics.append({'test':'prompt' if row.get('n_prompt',0)>0 else 'generation','tokens_per_second':speed,'stddev':row.get('stddev_ts'),'backend':row.get('backends'),'gpu_info':row.get('gpu_info'),'gpu_layers_requested':ngl})
    if not any(m['test']=='prompt' for m in metrics) or not any(m['test']=='generation' for m in metrics):
        raise ValueError('Both prompt processing and generation measurements are required.')
    return metrics,rows

def history(filename='result.json'):
    result=[]
    for f in sorted(DATA.glob('*/'+filename),reverse=True):
        try: result.append(device.annotate(json.loads(f.read_text(encoding='utf-8')),globals().get('HARDWARE',{})))
        except (ValueError,OSError): pass
    return result

def run_benchmark_process(args, folder, env=None):
    global PROC
    with (folder/'stdout.json').open('w',encoding='utf-8') as out, (folder/'stderr.log').open('w',encoding='utf-8') as err:
        with LOCK:
            if JOB['status']=='cancelled':
                return None
            PROC=subprocess.Popen(args,stdout=out,stderr=err,stdin=subprocess.DEVNULL,env=env,
                                  creationflags=0x08000000 if os.name=='nt' else 0)
        try:
            return PROC.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            PROC.kill()
            PROC.wait()
            raise RuntimeError('Benchmark exceeded the 30 minute limit.')


def worker(config, folder, h=None, npu=False):
    global PROC, BUSY
    try:
        if h is None:
            h=hardware()
        if npu:
            from openvino_adapter import model_folder
            model=model_folder(config['model'])
            args=openvino_command('--model',str(model))
            started=now()
            JOB.update(message='Compiling the model on Intel NPU, then running one warmup and three measured prompts.')
            code=run_benchmark_process(args,folder,{**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})
            if JOB['status']=='cancelled':
                return
            if code:
                detail=(folder/'stderr.log').read_text(encoding='utf-8')[-2500:].strip()
                raise RuntimeError('OpenVINO NPU test failed. '+detail)
            result=json.loads((folder/'stdout.json').read_text(encoding='utf-8'))
            result.update(schema_version='1.0',id=folder.name,started_at=started,
                          finished_at=now(),hardware=h)
            save_measurement(result,folder,'npu_result.json')
            return
        executable=Path(config['executable']).expanduser().resolve()
        model=Path(config['model']).expanduser().resolve()
        if not executable.is_file() or executable.suffix.lower()!='.exe': raise ValueError('Choose a local llama-bench.exe file.')
        if not model.is_file() or model.suffix.lower()!='.gguf': raise ValueError('Choose an existing GGUF model file.')
        threads=int(config.get('threads',4))
        if not 1<=threads<=256: raise ValueError('Threads must be between 1 and 256.')
        target=config.get('target','cpu')
        if target not in ('cpu','gpu'): raise ValueError('Invalid target.')
        args=[str(executable),'-m',str(model),'-p','128','-n','32','-r','3','-t',str(threads),'-ngl','0' if target=='cpu' else '99','-o','json','-v','-nkvo','1' if target=='cpu' else '0']
        JOB.update(message='Loading model and running 3 repetitions. First load may take several minutes.',command=args)
        started=now()
        code=run_benchmark_process(args,folder)
        if JOB['status']=='cancelled': return
        if code: raise RuntimeError('llama-bench exited with code '+str(code)+'. '+(folder/'stderr.log').read_text(encoding='utf-8')[-3000:])
        metrics,raw=parse_bench((folder/'stdout.json').read_text(encoding='utf-8'),target)
        if target=='gpu' and not re.search(r'offloaded [1-9][0-9]*/[0-9]+ layers to GPU', (folder/'stderr.log').read_text(encoding='utf-8')):
            raise ValueError('GPU offload was not confirmed in the verbose engine log. No GPU score saved.')
        result={'schema_version':'1.0','id':folder.name,'evidence':'measured','engine':'llama-bench','started_at':started,'finished_at':now(),'target_requested':target,'model':{'path':str(model),'bytes':model.stat().st_size,'mtime_ns':model.stat().st_mtime_ns},'hardware':h,'command':args,'metrics':metrics,'raw':raw,'artifacts':{'stdout':'stdout.json','stderr':'stderr.log'},'limitations':['llama-bench excludes tokenization and sampling time.','GPU offload requested is not proof that every layer ran on the GPU; inspect stderr.log.']}
        save_measurement(result,folder,'result.json')
    except Exception as e:
        if JOB['status']!='cancelled': JOB.update(status='failed',message=str(e))
    finally:
        with LOCK:
            PROC=None
            (folder/'job.json').write_text(json.dumps(JOB,indent=2),encoding='utf-8')
            BUSY=False

def save_measurement(result, folder, filename):
    with LOCK:
        if JOB['status']=='cancelled':
            return
        temp=folder/'result.tmp'
        temp.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
        temp.replace(folder/filename)
        JOB.update(status='completed',message='Measured result saved locally.',result_id=folder.name)


def onboarding_completed(hardware_snapshot):
    try:
        saved=json.loads((DATA/'onboarding.json').read_text(encoding='utf-8'))
        return saved == {'version':1,'device_id':hardware_snapshot.get('device_id')}
    except (OSError, ValueError):
        return False


def complete_onboarding(hardware_snapshot):
    if hardware_snapshot.get('available_gib') is None:
        raise ValueError('Available memory is required to complete setup.')
    with LOCK:
        DATA.mkdir(parents=True,exist_ok=True)
        temp=DATA/'onboarding.tmp'
        temp.write_text(json.dumps({'version':1,'device_id':hardware_snapshot.get('device_id')}),encoding='utf-8')
        temp.replace(DATA/'onboarding.json')


def scan_history():
    records=[]
    for f in sorted(DATA.glob('*/scan.json'),reverse=True):
        try:
            r=json.loads(f.read_text(encoding='utf-8'))
            if r.get('finished_at'): records.append(device.annotate(r,globals().get('HARDWARE',{})))
        except (ValueError,OSError): pass
    return records

def auto_worker(folder,mode="quick"):
    global PROC,BUSY,HARDWARE
    def update(**values):
        with LOCK: JOB.update(values)
    def attach(proc):
        global PROC
        with LOCK:
            PROC=proc
            if proc and JOB.get('status')=='cancelled': proc.kill()
    try:
        HARDWARE=hardware()
        scan=autotest.Scan(folder,HARDWARE,update,lambda: JOB.get('status')=='cancelled',attach,mode)
        result=scan.run()
        with LOCK:
            JOB.update(status=result['status'],stage='finished',download_percent=None,scan_id=folder.name,
                       message=result.get('outcome') or ('Recommended '+result['recommendation']['model']['name']+'.'+(' Test files removed.' if result['cleanup']['status']=='deleted' else '') if result.get('recommendation') else 'Scan finished.'))
            if result['cleanup']['status']=='failed': JOB['message']+=' Temporary cleanup needs attention; see scan report.'
    except Exception as e:
        JOB.update(status='failed',message=str(e))
    finally:
        with LOCK:
            PROC=None
            (folder/'job.json').write_text(json.dumps(JOB,indent=2),encoding='utf-8')
            BUSY=False

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,status,obj,kind='application/json'):
        content=json.dumps(obj,allow_nan=False).encode() if kind=='application/json' else obj
        self.send_response(status); self.send_header('Content-Type',kind); self.send_header('Content-Length',str(len(content))); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"); self.end_headers(); self.wfile.write(content)
    def authorized(self):
        return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}' and self.headers.get('X-LocalLens-Token')==TOKEN
    def do_GET(self):
        if self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}':
            self.reply(403,{'error':'Invalid host'}); return
        built=ROOT/'frontend/dist'
        use_built=(built/'index.html').is_file() and os.environ.get('LOCALLENS_LEGACY_UI')!='1'
        if self.path=='/':
            entry=built/'index.html' if use_built else ROOT/'ui/index.html'
            self.reply(200,entry.read_bytes().replace(b'__TOKEN__',TOKEN.encode()),'text/html; charset=utf-8'); return
        if self.path.startswith('/assets/') and use_built:
            asset=(built/unquote(urlsplit(self.path).path).lstrip('/')).resolve()
            kinds={'.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.svg':'image/svg+xml'}
            if asset.is_relative_to((built/'assets').resolve()) and asset.is_file() and asset.suffix in kinds:
                self.reply(200,asset.read_bytes(),kinds[asset.suffix]); return
            self.reply(404,{'error':'Asset not found'}); return
        if self.path in ('/style.css','/app.js'):
            self.reply(200,(ROOT/'ui'/self.path[1:]).read_bytes(),'text/css' if self.path.endswith('css') else 'text/javascript'); return
        if not self.authorized(): self.reply(403,{'error':'Local session required'}); return
        if self.path=='/api/state': self.reply(200,{'hardware':HARDWARE,'advisor':advisor(HARDWARE),'onboarding_complete':onboarding_completed(HARDWARE),'job':dict(JOB),'busy':BUSY,'history':history(),'npu_results':history('npu_result.json'),'auto_plan':autotest.plan(HARDWARE),'thorough_plan':autotest.plan(HARDWARE,'thorough'),'scans':scan_history()})
        elif self.path=='/api/openvino': self.reply(200,probe_openvino())
        elif self.path=='/api/connect/state': self.reply(200,CLUSTER.snapshot(HARDWARE))
        elif self.path=='/api/connect/guide': self.reply(200,{'text':(ROOT/'CONNECT-DEVICES.md').read_text(encoding='utf-8')})
        elif self.path=='/api/connect/apk':
            apk=ROOT/'android'/'LocalLens-Companion-debug.apk'
            if apk.is_file(): self.reply(200,apk.read_bytes(),'application/vnd.android.package-archive')
            else: self.reply(404,{'error':'APK not built. See android/companion/README.md.'})
        elif self.path=='/api/connect/companion':
            archive=io.BytesIO()
            with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
                for name in ('companion.py','connectnet.py','CONNECT-DEVICES.md'):
                    bundle.write(ROOT/name,name)
            self.reply(200,archive.getvalue(),'application/zip')
        else: self.reply(404,{'error':'Not found'})
    def do_POST(self):
        global BUSY,HARDWARE
        if not self.authorized(): self.reply(403,{'error':'Local session required'}); return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size>16384: raise ValueError('Request too large')
            config=json.loads(self.rfile.read(size))
            if self.path.startswith('/api/connect/'):
                action=self.path.removeprefix('/api/connect/')
                if action=='scan': result=CLUSTER.scan()
                elif action=='pair': result=CLUSTER.pair(config.get('device_id'),config.get('code',''),config.get('fingerprint_confirmed'))
                elif action=='refresh': result=CLUSTER.refresh()
                elif action=='benchmark': result=CLUSTER.benchmark(config.get('device_id'))
                elif action=='disconnect': result=CLUSTER.disconnect(config.get('device_id'))
                elif action=='confirm': result=CLUSTER.confirm(config.get('device_id'))
                elif action=='forget': result=CLUSTER.forget(config.get('device_id'))
                elif action=='resume': result=CLUSTER.resume(config.get('device_id'))
                elif action=='sharing': result=CLUSTER.sharing(config.get('device_id'),config.get('enabled'))
                elif action=='manual': result=CLUSTER.manual(config.get('host'),config.get('port',45460))
                elif action=='experiment':
                    self.reply(403,{'error':'Phone compute is unavailable in this preview.'}); return
                else: raise ValueError('Unknown connection action.')
                self.reply(200,result)
            elif self.path=='/api/auto':
                mode=config.get('mode','quick')
                if mode not in ('quick','thorough'):raise ValueError('Invalid scan mode')
                with LOCK:
                    if BUSY: self.reply(409,{'error':'A test is already running'}); return
                    folder=DATA/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-scan-'+uuid.uuid4().hex[:8]); folder.mkdir(parents=True)
                    BUSY=True
                    JOB.clear(); JOB.update(status='running',kind='automatic',stage='preparing',message='Detecting your hardware and checking the memory reserve…',id=folder.name)
                    accepted=dict(JOB)
                threading.Thread(target=auto_worker,args=(folder,mode),daemon=True).start()
                self.reply(202,accepted)
            elif self.path in ('/api/run','/api/run-npu'):
                npu=self.path=='/api/run-npu'
                if npu and not isinstance(config.get('model'),str):
                    raise ValueError('Choose an OpenVINO model folder.')
                with LOCK:
                    if BUSY: self.reply(409,{'error':'A benchmark is already running'}); return
                    folder=DATA/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]); folder.mkdir(parents=True)
                    BUSY=True
                    JOB.clear(); JOB.update(status='running',message='Validating local files.',id=folder.name)
                    if npu: JOB['kind']='npu'
                    accepted=dict(JOB)
                threading.Thread(target=worker,args=(config,folder,None,npu),daemon=True).start()
                self.reply(202,accepted)
            elif self.path=='/api/cancel':
                with LOCK:
                    if 'id' in config and config['id'] != JOB.get('id'):
                        self.reply(409,{'error':'This test is no longer active.'}); return
                    if JOB['status']=='running':
                        JOB.update(status='cancelled',message='Cancelled. No benchmark score was saved.')
                        if PROC: PROC.kill()
                self.reply(200,dict(JOB))
            elif self.path=='/api/refresh':
                HARDWARE=hardware(); self.reply(200,HARDWARE)
            elif self.path=='/api/onboarding/complete':
                complete_onboarding(HARDWARE)
                self.reply(200,{'onboarding_complete':True})
            else: self.reply(404,{'error':'Not found'})
        except Exception as e: self.reply(400,{'error':str(e)})

def serve(desktop=False):
    global HARDWARE
    recovery=autotest.recover_temporary(DATA)
    HARDWARE=hardware()
    HARDWARE['warnings'].extend(recovery)
    # Benchmarking needs only loopback. The desktop Devices page starts LAN discovery when opened.
    if not desktop:
        CLUSTER.start()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    url=f'http://127.0.0.1:{server.server_port}'
    if desktop:
        def stop_with_parent():
            sys.stdin.buffer.read(1)
            server.shutdown()
        threading.Thread(target=stop_with_parent,daemon=True).start()
        print(f'LOCALLENS_READY {server.server_port}',flush=True)
    else:
        print('LocalLens is running at '+url,flush=True)
    if not desktop and '--no-window' not in sys.argv:
        edge=next((p for p in [Path(os.environ.get('ProgramFiles(x86)',''))/'Microsoft/Edge/Application/msedge.exe',Path(os.environ.get('ProgramFiles',''))/'Microsoft/Edge/Application/msedge.exe'] if p.is_file()),None)
        if edge: subprocess.Popen([str(edge),'--app='+url,'--window-size=1280,900'])
        else: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt:
        if PROC: PROC.kill()
    finally:
        if desktop:
            with LOCK:
                if JOB['status']=='running':
                    JOB.update(status='cancelled',message='The desktop app was closed.')
                    if PROC: PROC.kill()
            deadline=time.monotonic()+4
            while BUSY and time.monotonic()<deadline:
                time.sleep(.05)
        CLUSTER.close()
        server.server_close()

def main():
    if len(sys.argv)>1 and sys.argv[1]=='--openvino-worker':
        from openvino_adapter import main as openvino_main
        openvino_main(sys.argv[2:])
        return
    if '--desktop-sidecar' not in sys.argv:
        serve()
        return
    import msvcrt

    if sys.stdin.buffer.read(1) != b'\x01':
        raise RuntimeError('The desktop supervisor did not authorize startup.')
    if not (ROOT/'frontend/dist/index.html').is_file():
        raise RuntimeError('The installed frontend is missing. Reinstall LocalLens.')
    DATA.mkdir(parents=True,exist_ok=True)
    with (DATA/'.desktop.lock').open('a+b') as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            raise RuntimeError('LocalLens is already using this desktop data folder.') from None
        serve(desktop=True)

if __name__=='__main__': main()
