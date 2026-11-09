"""One-click real-model prompt tests. Downloads are pinned; only owned scratch is deleted."""
from pathlib import Path
import ctypes, hashlib, json, math, os, re, secrets, shutil, socket, statistics, subprocess
import threading, time, urllib.request, urllib.error, uuid, zipfile
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
MODELS=json.loads((ROOT/'models.json').read_text(encoding='utf-8'))
ENGINE={'url':'https://github.com/ggml-org/llama.cpp/releases/download/b11900/llama-b11900-bin-win-vulkan-x64.zip','bytes':37051563,'sha256':'baf0183b1906d7cc0cfe9a0bd3fae34ceb4048acecc371ff3b7a91456783d051','build':'b11900 Vulkan x64'}
PROMPT='Explain how a laptop can run an AI model locally. Give three practical benefits and two limitations, in clear language for a beginner.'
FORMATTED_PROMPT='<|im_start|>system\nYou are a helpful assistant. Be clear and concise.<|im_end|>\n<|im_start|>user\n'+PROMPT+' /no_think<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
THRESHOLD=15.0
GIB=1024**3
HTTP=urllib.request.build_opener(urllib.request.ProxyHandler({}))

class Cancelled(Exception): pass

def utc():return datetime.now(timezone.utc).isoformat()
def available_gib():
    if os.name!='nt':return None
    class Memory(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong),('total',ctypes.c_ulonglong),('available',ctypes.c_ulonglong),('page',ctypes.c_ulonglong),('free_page',ctypes.c_ulonglong),('virtual',ctypes.c_ulonglong),('free_virtual',ctypes.c_ulonglong),('extended',ctypes.c_ulonglong)]
    m=Memory();m.length=ctypes.sizeof(m)
    return m.available/GIB if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)) else None

def plan(h,mode="quick"):
    free=h.get('available_gib');total=h.get('ram_gib')
    reserve=max(4.0,(total or 0)*.20)
    eligible=[]
    for m in reversed(MODELS):
        if mode!='thorough' and m['parameters_b']>4:continue
        budget=m['bytes']/GIB*1.15+2
        if free is not None and budget<=free-reserve:eligible.append({**m,'estimated_budget_gib':round(budget,2)})
    return {'mode':mode,'candidates':eligible,'reserve_gib':round(reserve,2),'minimum_tokens_per_second':THRESHOLD,'max_download_bytes':ENGINE['bytes']+sum(m['bytes'] for m in eligible),'first_download_bytes':ENGINE['bytes']+(eligible[0]['bytes'] if eligible else 0),'scratch_needed_bytes':int((max([m['bytes'] for m in eligible],default=0)+600*1024**2)*1.1),'prompt':PROMPT,'context_tokens':4096,'output_tokens':128,'repetitions':2,'policy':'Largest comfortable candidate in the selected scan, not a universal model-quality ranking. Test GPU then CPU; stop at the first candidate with a passing backend. All test downloads are removed.'}

def validate_timings(response):
    t=response.get('timings',{})
    n=t.get('predicted_n');ms=t.get('predicted_ms');speed=t.get('predicted_per_second')
    if n!=128 or isinstance(speed,bool) or not isinstance(speed,(int,float)) or not math.isfinite(speed) or speed<=0 or not isinstance(ms,(int,float)) or ms<=0:
        raise ValueError('Engine did not return a valid measured 128-token generation.')
    if abs(speed-n*1000/ms)>max(.1,speed*.02):raise ValueError('Engine token count and throughput disagree.')
    if t.get('cache_n',0)!=0:raise ValueError('Unexpected prompt-cache reuse; this run cannot be compared fairly.')
    return t

def comfortable(r,reserve):
    return len(r.get('samples',[]))==2 and min(x['predicted_per_second'] for x in r['samples'])>=THRESHOLD and r.get('minimum_free_ram_gib') is not None and r['minimum_free_ram_gib']>=reserve

def owned_cleanup(path,parent,owner):
    path=Path(path).resolve();parent=Path(parent).resolve()
    if path.parent!=parent or not re.fullmatch(r'scan-[0-9a-f]{32}',path.name):raise ValueError('Refusing cleanup outside owned scan directory.')
    marker=path/'.locallens-owner'
    if not marker.is_file() or marker.read_text()!=owner:raise ValueError('Refusing cleanup without the scan ownership marker.')
    for attempt in range(5):
        try:shutil.rmtree(path);return
        except OSError:
            if attempt==4:raise
            time.sleep(.3)

class Scan:
    def __init__(self,folder,h,update,cancelled,attach,mode="quick"):
        self.folder=Path(folder);self.h=h;self.update=update;self.cancelled=cancelled;self.attach=attach
        self.proc=None;self.scratch=None;self.owner=uuid.uuid4().hex
        self.record={'schema_version':'1.0','id':self.folder.name,'kind':'automatic-model-scan','started_at':utc(),'hardware':h,'engine':ENGINE,'plan':plan(h,mode),'prompt':PROMPT,'formatted_prompt':FORMATTED_PROMPT,'attempts':[],'recommendation':None,'cleanup':{'status':'pending'},'limitations':['Short prompt, 4096-token context, single user; longer contexts and background workloads can be slower.','This tests speed and system-memory headroom, not answer quality or NPU execution.','GPU memory capacity is not measured separately. GPU allocation failures are recorded and CPU is tried.','Token throughput is the engine decode timing, not whole-request latency.']}
    def check(self):
        if self.cancelled():raise Cancelled('Stopped by user.')
    def save(self):
        tmp=self.folder/'scan.tmp';tmp.write_text(json.dumps(self.record,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(self.folder/'scan.json')
    def progress(self,stage,message,**kw):
        self.check();self.update(stage=stage,message=message,**kw)
    def download(self,url,path,expected,digest,label):
        self.check()
        if shutil.disk_usage(path.parent).free<expected+GIB:raise RuntimeError('Not enough free disk space for the temporary download plus a 1 GiB reserve.')
        sha=hashlib.sha256();done=0;last=0
        request=urllib.request.Request(url,headers={'User-Agent':'LocalLens/0.2'})
        with HTTP.open(request,timeout=20) as response,path.open('wb') as out:
            while True:
                self.check();chunk=response.read(1024*1024)
                if not chunk:break
                done+=len(chunk)
                if done>expected:raise ValueError('Download exceeded its pinned size.')
                sha.update(chunk);out.write(chunk)
                if time.monotonic()-last>.3:
                    self.progress('downloading',f'Downloading {label} · {done/1e9:.2f} / {expected/1e9:.2f} GB',downloaded_bytes=done,total_bytes=expected,download_percent=round(done/expected*100,1));last=time.monotonic()
        if done!=expected or sha.hexdigest()!=digest:raise ValueError(f'{label} failed its size / SHA-256 verification. It will not be used.')
        self.progress('verifying',label+' · SHA-256 verified',download_percent=100)
    def copy_existing_model(self,m,destination):
        # An exact pinned, already-installed Ollama artifact can avoid a large download.
        # Only a scratch copy is ever deleted. The original is read-only to this code.
        if m['parameters_b']!=4:return None
        digest='3e4cb14174460404e7a233e531675303b2fbf7749c02f91864fe311ab6344e4f'
        source=Path.home()/'.ollama/models/blobs'/('sha256-'+digest)
        if not source.is_file() or source.stat().st_size!=2497280480:return None
        self.progress('verifying','Found an existing Qwen3 4B model. Verifying it before making a temporary test copy…',download_percent=None)
        sha=hashlib.sha256()
        with source.open('rb') as f:
            while True:
                self.check();chunk=f.read(4*1024**2)
                if not chunk:break
                sha.update(chunk)
        if sha.hexdigest()!=digest:return None
        self.progress('preparing','Using a verified temporary copy of your installed Qwen3 4B model. Your original will be kept.')
        copied=hashlib.sha256()
        with source.open('rb') as src,destination.open('wb') as dst:
            while True:
                self.check();chunk=src.read(4*1024**2)
                if not chunk:break
                copied.update(chunk);dst.write(chunk)
        if copied.hexdigest()!=digest:
            destination.unlink();return None
        return {**m,'repo':'Ollama library/qwen3:4b','revision':digest,'sha256':digest,'bytes':2497280480,'source':'verified existing Ollama cache; original preserved'}
    def extract(self,archive,destination):
        destination.mkdir()
        with zipfile.ZipFile(archive) as z:
            if sum(f.file_size for f in z.infolist())>600*1024**2:raise ValueError('Engine archive is unexpectedly large.')
            for f in z.infolist():
                self.check();target=(destination/f.filename).resolve()
                if not target.is_relative_to(destination.resolve()) or f.filename.startswith(('/','\\')):raise ValueError('Unsafe archive path.')
                if f.is_dir():target.mkdir(parents=True,exist_ok=True)
                else:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(f) as src,target.open('wb') as dst:shutil.copyfileobj(src,dst)
    def stop(self):
        if self.proc:
            if self.proc.poll() is None:self.proc.kill()
            self.proc.wait(timeout=15);self.proc=None
        self.attach(None)
    def request(self,url,key,body=None,timeout=300):
        req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        with HTTP.open(req,timeout=timeout) as r:return json.load(r)
    def measure(self,exe,model,m,target):
        self.check();key=secrets.token_urlsafe(24)
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        args=[str(exe),'-m',str(model),'--host','127.0.0.1','--port',str(port),'--api-key',key,'-c','4096','-np','1','-t',str(min(8,max(1,(self.h.get('threads') or 4)//2))),'-ngl','99' if target=='gpu' else '0','--no-webui','--no-warmup','-v']
        if target=='cpu':args+=['--no-kv-offload']
        prefix=f'{m["parameters_b"]}B-{target}';logpath=self.folder/(prefix+'-engine.log')
        result={'model':m,'target':target,'evidence':'measured','status':'failed','command':[('[ephemeral session key]' if a==key else a) for a in args],'context_tokens':4096,'samples':[],'protocol':'One 16-token warmup, two uncached 128-token completions, temperature 0, seed 42, ignore_eos true.','log':logpath.name}
        readings=[];monitor_stop=threading.Event();memory_pressure=threading.Event()
        def monitor():
            while not monitor_stop.is_set():
                n=available_gib()
                if n is not None:
                    readings.append(n)
                    if n<self.record['plan']['reserve_gib']:
                        memory_pressure.set()
                        proc=self.proc
                        if proc and proc.poll() is None:
                            try:proc.kill()
                            except OSError:pass
                monitor_stop.wait(.25)
        monitor_thread=threading.Thread(target=monitor,daemon=True);monitor_thread.start()
        try:
            self.progress('loading',f'Loading {m["name"]} on {target.upper()} · this may take a few minutes',download_percent=None)
            with logpath.open('w',encoding='utf-8') as log:
                self.proc=subprocess.Popen(args,stdout=log,stderr=log,creationflags=0x08000000 if os.name=='nt' else 0)
                self.attach(self.proc)
                deadline=time.monotonic()+240
                while True:
                    self.check()
                    if self.proc.poll() is not None:raise RuntimeError(('Stopped to preserve free-memory headroom. ' if memory_pressure.is_set() else 'Engine could not load this model / backend. ')+ 'See '+logpath.name)
                    try:
                        if self.request(base+'/health',key,timeout=2).get('status')=='ok':break
                    except (OSError,ValueError):pass
                    if time.monotonic()>deadline:raise TimeoutError('Model loading exceeded four minutes.')
                    time.sleep(.4)
                if target=='gpu':
                    match=re.search(r'offloaded ([1-9][0-9]*)/([0-9]+) layers to GPU',logpath.read_text(encoding='utf-8',errors='replace'))
                    if not match:raise RuntimeError('GPU offload was not confirmed. CPU will be tested explicitly.')
                    result['gpu_layers_offloaded']=int(match[1]);result['model_layers']=int(match[2])
                body={'prompt':FORMATTED_PROMPT,'n_predict':16,'temperature':0,'seed':42,'cache_prompt':False,'ignore_eos':True,'stream':False}
                self.progress('warming',f'Warming up {m["name"]} · {target.upper()}')
                self.request(base+'/completion',key,body)
                for i in range(2):
                    self.progress('measuring',f'{m["name"]} · {target.upper()} · real prompt test {i+1}/2 · generating 128 tokens')
                    self.check();body['n_predict']=128;start=time.monotonic();response=self.request(base+'/completion',key,body);self.check()
                    result['samples'].append(validate_timings(response));result.setdefault('request_seconds',[]).append(round(time.monotonic()-start,3))
                    result.setdefault('generated_samples',[]).append(response.get('content',''))
                result['status']='completed'
        except Cancelled:raise
        except Exception as e:
            result['error']='Stopped to preserve free-memory headroom.' if memory_pressure.is_set() else str(e)
        finally:
            self.stop();monitor_stop.set();monitor_thread.join(timeout=2)
            if logpath.exists():
                logpath.write_text(logpath.read_text(encoding='utf-8',errors='replace').replace(key,'[ephemeral session key]'),encoding='utf-8')
            result['minimum_free_ram_gib']=round(min(readings),2) if readings else None
        if memory_pressure.is_set():
            result['status']='failed';result['error']='Stopped to preserve free-memory headroom.'
        if result['status']=='completed':
            result['generation_tokens_per_second']=round(statistics.mean(x['predicted_per_second'] for x in result['samples']),2)
            result['slowest_tokens_per_second']=round(min(x['predicted_per_second'] for x in result['samples']),2)
            result['comfortable']=comfortable(result,self.record['plan']['reserve_gib'])
            result['status_label']='Comfortable' if result['comfortable'] else 'Below comfort target'
        return result
    def run(self):
        error=None
        try:
            if os.name!='nt' or platform_machine() not in ('amd64','x86_64'):raise RuntimeError('Automatic setup currently supports Windows x64 only.')
            p=self.record['plan']
            if not p['candidates']:raise RuntimeError('Not enough free memory to test a model with a comfortable reserve. Close other apps and try again.')
            if shutil.disk_usage(self.folder).free<p['scratch_needed_bytes']+GIB:raise RuntimeError('Not enough free disk space for this scan. Free up space and try again.')
            parent=self.folder.parent/'temporary';parent.mkdir(exist_ok=True)
            self.scratch=parent/('scan-'+uuid.uuid4().hex);self.scratch.mkdir();(self.scratch/'.locallens-owner').write_text(self.owner);(self.scratch/'.locallens-meta.json').write_text(json.dumps({'pid':os.getpid(),'owner':self.owner}))
            self.save()
            archive=self.scratch/'engine.zip'
            self.download(ENGINE['url'],archive,ENGINE['bytes'],ENGINE['sha256'],'benchmark engine')
            self.extract(archive,self.scratch/'engine');archive.unlink()
            exe=next((self.scratch/'engine').rglob('llama-server.exe'))
            for m in p['candidates']:
                self.check();self.record['current_model']=m['name'];self.save()
                file=self.scratch/m['filename'];url=f'https://huggingface.co/{m["repo"]}/resolve/{m["revision"]}/{m["filename"]}'
                cached=self.copy_existing_model(m,file)
                if cached:m=cached
                else:self.download(url,file,m['bytes'],m['sha256'],m['name']+' '+m['quantization'])
                passing=[]
                for target in (['gpu','cpu'] if self.h.get('gpus') else ['cpu']):
                    result=self.measure(exe,file,m,target)
                    self.record['attempts'].append(result);self.save()
                    if result.get('comfortable'):passing.append(result)
                self.progress('cleaning',f'Removing the temporary {m["name"]} model…')
                file.unlink()
                if passing:
                    best=max(passing,key=lambda r:r['slowest_tokens_per_second'])
                    self.record['recommendation']={'model':m,'target':best['target'],'evidence':'measured','generation_tokens_per_second':best['generation_tokens_per_second'],'slowest_tokens_per_second':best['slowest_tokens_per_second'],'minimum_free_ram_gib':best['minimum_free_ram_gib'],'reason':f'Largest candidate in this {p["mode"]} scan that passed both measured runs at ≥{THRESHOLD:g} tok/s while leaving at least {p["reserve_gib"]:.1f} GiB free. Faster passing backend selected.','scope':'Best comfortable fit among the selected scan candidates. Quick mode excludes 8B; larger and other model families are not ranked.'}
                    break
            self.record['status']='completed'
            if not self.record['recommendation']:self.record['outcome']='No tested candidate met both speed and memory targets. No comfortable model is recommended.'
        except Cancelled:
            self.record['status']='cancelled';self.record['outcome']='Cancelled. No recommendation made.';self.record['recommendation']=None
        except Exception as e:
            if self.cancelled():
                self.record['status']='cancelled';self.record['outcome']='Cancelled. No recommendation made.';self.record['recommendation']=None
            else:
                self.record['status']='failed';self.record['outcome']=str(e);error=e
        finally:
            try:self.stop()
            except Exception as e:self.record['process_stop_error']=str(e)
            if self.scratch:
                try:
                    owned_cleanup(self.scratch,self.folder.parent/'temporary',self.owner)
                    self.record['cleanup']={'status':'deleted','message':'Temporary model and engine downloads removed.'}
                except Exception as e:self.record['cleanup']={'status':'failed','path':str(self.scratch),'message':str(e)}
            else:self.record['cleanup']={'status':'not_needed'}
            self.record['finished_at']=utc();self.save()
        return self.record

def platform_machine():
    import platform
    return platform.machine().lower()

def recover_temporary(data):
    """Remove only marked scratch from dead processes; never touch active instances."""
    parent=Path(data)/'temporary'
    if not parent.exists():return []
    messages=[]
    for path in parent.iterdir():
        if not path.is_dir() or path.is_symlink() or not re.fullmatch(r'scan-[0-9a-f]{32}',path.name):continue
        try:
            meta=json.loads((path/'.locallens-meta.json').read_text());pid=int(meta['pid']);owner=meta['owner']
            if not re.fullmatch(r'[0-9a-f]{32}',owner):continue
            if os.name=='nt':
                kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                kernel.OpenProcess.restype=ctypes.c_void_p
                handle=kernel.OpenProcess(0x1000,False,pid)
                if handle:
                    kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(handle);continue
                if ctypes.get_last_error()!=87:continue
            else:
                try:os.kill(pid,0);continue
                except ProcessLookupError:pass
                except PermissionError:continue
            owned_cleanup(path,parent,owner);messages.append('Removed temporary downloads from an interrupted scan.')
        except (OSError,ValueError,KeyError):continue
    return messages
