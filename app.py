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

def probe_openvino():
    p=run([sys.executable,str(ROOT/'openvino_adapter.py'),'--probe'],45)
    try: return json.loads(p.stdout)
    except Exception: return {'status':'unavailable','message':p.stderr[-2000:] or 'Adapter did not return a response.'}

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

def history():
    result=[]
    for f in sorted(DATA.glob('*/result.json'),reverse=True):
        try: result.append(device.annotate(json.loads(f.read_text(encoding='utf-8')),globals().get('HARDWARE',{})))
        except (ValueError,OSError): pass
    return result

def worker(config, folder, h):
    global PROC, BUSY
    try:
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
        with (folder/'stdout.json').open('w',encoding='utf-8') as out, (folder/'stderr.log').open('w',encoding='utf-8') as err:
            with LOCK:
                if JOB['status']=='cancelled': return
                PROC=subprocess.Popen(args,stdout=out,stderr=err,creationflags=0x08000000 if os.name=='nt' else 0)
            try: code=PROC.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                PROC.kill(); PROC.wait(); raise RuntimeError('Benchmark exceeded the 30 minute limit.')
        if JOB['status']=='cancelled': return
        if code: raise RuntimeError('llama-bench exited with code '+str(code)+'. '+(folder/'stderr.log').read_text(encoding='utf-8')[-3000:])
        metrics,raw=parse_bench((folder/'stdout.json').read_text(encoding='utf-8'),target)
        if target=='gpu' and not re.search(r'offloaded [1-9][0-9]*/[0-9]+ layers to GPU', (folder/'stderr.log').read_text(encoding='utf-8')):
            raise ValueError('GPU offload was not confirmed in the verbose engine log. No GPU score saved.')
        result={'schema_version':'1.0','id':folder.name,'evidence':'measured','engine':'llama-bench','started_at':started,'finished_at':now(),'target_requested':target,'model':{'path':str(model),'bytes':model.stat().st_size,'mtime_ns':model.stat().st_mtime_ns},'hardware':h,'command':args,'metrics':metrics,'raw':raw,'artifacts':{'stdout':'stdout.json','stderr':'stderr.log'},'limitations':['llama-bench excludes tokenization and sampling time.','GPU offload requested is not proof that every layer ran on the GPU; inspect stderr.log.']}
        with LOCK:
            if JOB['status']=='cancelled': return
            tmp=folder/'result.tmp'; tmp.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8'); tmp.replace(folder/'result.json')
            JOB.update(status='completed',message='Measured result saved locally.',result_id=folder.name)
    except Exception as e:
        if JOB['status']!='cancelled': JOB.update(status='failed',message=str(e))
    finally:
        with LOCK:
            PROC=None
            (folder/'job.json').write_text(json.dumps(JOB,indent=2),encoding='utf-8')
            BUSY=False

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
        if self.path=='/api/state': self.reply(200,{'hardware':HARDWARE,'advisor':advisor(HARDWARE),'job':dict(JOB),'busy':BUSY,'history':history(),'auto_plan':autotest.plan(HARDWARE),'thorough_plan':autotest.plan(HARDWARE,'thorough'),'scans':scan_history()})
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
        global BUSY
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
                    JOB.clear(); JOB.update(status='running',kind='automatic',stage='preparing',message='Checking memory and preparing your automatic test…',id=folder.name)
                threading.Thread(target=auto_worker,args=(folder,mode),daemon=True).start()
                self.reply(202,dict(JOB))
            elif self.path=='/api/run':
                with LOCK:
                    if BUSY: self.reply(409,{'error':'A benchmark is already running'}); return
                    folder=DATA/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]); folder.mkdir(parents=True)
                    BUSY=True
                    JOB.clear(); JOB.update(status='running',message='Validating local files.',id=folder.name)
                threading.Thread(target=worker,args=(config,folder,hardware()),daemon=True).start()
                self.reply(202,dict(JOB))
            elif self.path=='/api/cancel':
                with LOCK:
                    if JOB['status']=='running':
                        JOB.update(status='cancelled',message='Cancelled. No benchmark score was saved.')
                        if PROC: PROC.kill()
                self.reply(200,dict(JOB))
            elif self.path=='/api/refresh':
                global HARDWARE
                HARDWARE=hardware(); self.reply(200,HARDWARE)
            else: self.reply(404,{'error':'Not found'})
        except Exception as e: self.reply(400,{'error':str(e)})

def main():
    global HARDWARE
    recovery=autotest.recover_temporary(DATA)
    HARDWARE=hardware()
    HARDWARE['warnings'].extend(recovery)
    CLUSTER.start()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    url=f'http://127.0.0.1:{server.server_port}'
    print('LocalLens is running at '+url,flush=True)
    if '--no-window' not in sys.argv:
        edge=next((p for p in [Path(os.environ.get('ProgramFiles(x86)',''))/'Microsoft/Edge/Application/msedge.exe',Path(os.environ.get('ProgramFiles',''))/'Microsoft/Edge/Application/msedge.exe'] if p.is_file()),None)
        if edge: subprocess.Popen([str(edge),'--app='+url,'--window-size=1280,900'])
        else: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt:
        if PROC: PROC.kill()
    finally: CLUSTER.close(); server.server_close()

if __name__=='__main__': main()
