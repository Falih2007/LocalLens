"""Real, opt-in CPU + phone RPC experiment, separate from single-device results."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import threading
import time
import urllib.request

import autotest
import connectnet

HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PROMPT = 'Explain in three short sentences why testing a computer is useful.'


def process_memory(proc):
    if os.name != 'nt':
        try:
            entries = dict(line.split(':', 1) for line in Path(f'/proc/{proc.pid}/status').read_text().splitlines() if ':' in line)
            return int(entries['VmRSS'].split()[0])*1024
        except (OSError, KeyError): return None
    class Counters(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong)] + [(n, ctypes.c_size_t) for n in ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
    result = Counters(); result.cb = ctypes.sizeof(result)
    if ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(int(proc._handle)), ctypes.byref(result), result.cb): return result.WorkingSetSize
    return None


def participation(log, before, after, traffic):
    match = re.search(r'offloaded (\d+)/(\d+) layers', log)
    remote_graphs = None
    if isinstance(before.get('rpc_graph_events'), int) and isinstance(after.get('rpc_graph_events'), int):
        remote_graphs = after['rpc_graph_events']-before['rpc_graph_events']
    split = bool(match and 0 < int(match[1]) < int(match[2]))
    host_buffer = bool(re.search(r'CPU.*model buffer size\s*=\s*[1-9]', log))
    transferred = traffic.get('bytes_to_phone', 0) > 0 and traffic.get('bytes_from_phone', 0) > 0
    return {'status': 'evidence_collected_review_required' if split and host_buffer and transferred and remote_graphs is not None and remote_graphs > 0 else 'not_verified', 'offloaded_layers': int(match[1]) if match else None, 'total_layers': int(match[2]) if match else None, 'partial_layer_offload': split, 'local_cpu_model_buffer': host_buffer, 'remote_graph_event_delta': remote_graphs, 'bidirectional_rpc_payload': transferred, 'note': 'Review both engine logs and samples. A connection, memory allocation or two standalone instances is not a model-parallel success. No automatic success badge is issued.'}


def run(manager, config, folder, hardware, update, attach, cancelled):
    folder = Path(folder)
    exe = Path(config.get('executable', '')).expanduser().resolve()
    model = Path(config.get('model', '')).expanduser().resolve()
    if not exe.is_file() or (os.name == 'nt' and exe.suffix.lower() != '.exe'): raise ValueError('Select a trusted local RPC-enabled llama-server executable.')
    if not model.is_file() or model.suffix.lower() != '.gguf': raise ValueError('Select a local small GGUF model.')
    if model.stat().st_size > 2*1024**3: raise ValueError('Start with a model under 2 GiB for this first distributed experiment.')
    layers = int(config.get('remote_layers', 8))
    if not 1 <= layers <= 16: raise ValueError('Choose between 1 and 16 remote layers for the partial split.')
    identity = config.get('device_id')
    peer = manager.peer(identity)
    token = manager.credentials[identity]
    reserve = max(4, (hardware.get('ram_gib') or 0)*.2)
    report = {'schema_version': '1.0', 'kind': 'distributed_experiment', 'status': 'running', 'evidence': 'experimental', 'started_at': time.time(), 'hardware': hardware, 'phone': peer.get('hardware'), 'model': {'name': model.name, 'bytes': model.stat().st_size}, 'prompt': PROMPT, 'context_tokens': 1024, 'runs': [], 'capacity_expansion': {'status': 'not_tested', 'reason': 'No enforced equal-resource-limit capacity experiment has been executed.'}, 'limitations': ['Phone-only means all model layers on phone RPC with laptop coordinating tokenization and sampling; it is not a standalone Android baseline.', 'First experiment uses laptop CPU and phone CPU. Intel Arc and NPU are not used.', 'Memory is sampled process RSS and system available RAM, not GPU allocation or exact simultaneous peak.', 'No model quality or throughput improvement is assumed.']}
    def save(): (folder/'distributed.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    update('Validating RPC engine and model fingerprint…')
    digest = hashlib.sha256()
    with model.open('rb') as stream:
        while chunk := stream.read(4*1024**2):
            if cancelled(): raise autotest.Cancelled()
            digest.update(chunk)
    report['model']['sha256'] = digest.hexdigest()
    version = subprocess.run([str(exe), '--version'], capture_output=True, text=True, timeout=15, creationflags=0x08000000 if os.name == 'nt' else 0)
    report['engine_version'] = (version.stdout + version.stderr)[-4000:]
    if '39febd2' not in report['engine_version']:
        raise ValueError('The selected engine does not report the required 39febd2 source revision. Build the matching RPC engine using Phone setup.')
    save()
    tunnel = manager.open_tunnel(identity)
    try:
        for mode, ngl in [('laptop_cpu', 0), ('phone_rpc_only', 999), ('laptop_cpu_and_phone', layers)]:
            if cancelled(): raise autotest.Cancelled()
            update(f'Running real experiment: {mode.replace("_", " ")}')
            with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            key = secrets.token_hex(24)
            base = f'http://127.0.0.1:{port}'
            args = [str(exe), '-m', str(model), '--host', '127.0.0.1', '--port', str(port), '--api-key', key, '-c', '1024', '-np', '1', '-t', str(min(8, hardware.get('threads') or 4)), '-ngl', str(ngl), '--no-webui', '--no-warmup', '-lv', '5']
            if ngl: args += ['--rpc', tunnel.endpoint, '--device', 'RPC0']
            else: args += ['--device', 'none', '--no-kv-offload']
            row = {'mode': mode, 'status': 'failed', 'samples': [], 'command': [('[ephemeral key]' if a == key else a) for a in args], 'load_seconds': None, 'peak_sampled_local_rss_bytes': None, 'minimum_local_available_gib': None, 'minimum_phone_available_gib': None}
            report['runs'].append(row)
            before = connectnet.request(peer, '/status', token=token)
            initial_traffic = tunnel.stats()
            logpath = folder/(mode+'.log')
            stop = threading.Event(); pressure = threading.Event(); readings = []; phone_readings = []; rss = []
            def request(path, body=None, timeout=5):
                req = urllib.request.Request(base+path, data=json.dumps(body).encode() if body is not None else None, headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'})
                with HTTP.open(req, timeout=timeout) as response: return json.load(response)
            proc = None
            try:
                started = time.monotonic()
                with logpath.open('w', encoding='utf-8') as log:
                    proc = subprocess.Popen(args, stdout=log, stderr=log, env={**os.environ, 'GGML_RPC_DEBUG': '3'}, creationflags=0x08000000 if os.name == 'nt' else 0)
                    attach(proc)
                    def monitor():
                        while not stop.is_set():
                            n = autotest.available_gib()
                            if n is not None:
                                readings.append(n)
                                if n < reserve: pressure.set()
                            value = process_memory(proc)
                            if value is not None: rss.append(value)
                            try:
                                status = connectnet.request(peer, '/status', token=token, timeout=3)
                                phone_readings.append(status)
                                n = status.get('available_gib')
                                if ngl and isinstance(n, (int, float)) and n < 2: pressure.set()
                            except (OSError, ValueError):
                                if ngl: pressure.set()
                            if pressure.is_set() and proc.poll() is None: proc.kill()
                            stop.wait(.5)
                    monitor_thread = threading.Thread(target=monitor, daemon=True); monitor_thread.start()
                    while True:
                        if cancelled(): raise autotest.Cancelled()
                        if proc.poll() is not None: raise RuntimeError('Engine stopped. Inspect '+logpath.name)
                        if time.monotonic()-started > 240: raise TimeoutError('Loading exceeded four minutes.')
                        try:
                            if request('/health', timeout=1).get('status') == 'ok': break
                        except (OSError, ValueError): pass
                        time.sleep(.3)
                    row['load_seconds'] = round(time.monotonic()-started, 3)
                    row['load_protocol'] = 'Process start to healthy server, without warmup; includes initialization and polling interval.'
                    body = {'prompt': PROMPT, 'n_predict': 16, 'temperature': 0, 'seed': 42, 'cache_prompt': False, 'ignore_eos': True, 'stream': False}
                    request('/completion', body, 300)
                    for _ in range(2):
                        if cancelled(): raise autotest.Cancelled()
                        body['n_predict'] = 64
                        response = request('/completion', body, 300)
                        timing = response.get('timings', {})
                        for metric, count in [('prompt_per_second', 'prompt_n'), ('predicted_per_second', 'predicted_n')]:
                            value = timing.get(metric)
                            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 < value < float('inf') or not timing.get(count): raise ValueError('Missing real engine timing/count: '+metric)
                        if timing['predicted_n'] != 64: raise ValueError('Incomplete generation sample.')
                        row['samples'].append({'timings': timing, 'content': response.get('content', '')})
                    if pressure.is_set(): raise RuntimeError('Stopped to preserve local or phone memory reserve / connection lost.')
                    row['status'] = 'completed'
            except autotest.Cancelled: raise
            except Exception as exc: row['error'] = str(exc)
            finally:
                stop.set()
                if proc:
                    if proc.poll() is None: proc.kill()
                    proc.wait(timeout=10)
                attach(None)
                if 'monitor_thread' in locals(): monitor_thread.join(timeout=4)
                if logpath.exists(): logpath.write_text(logpath.read_text(encoding='utf-8', errors='replace').replace(key, '[ephemeral key]'), encoding='utf-8')
                row['peak_sampled_local_rss_bytes'] = max(rss) if rss else None
                row['minimum_local_available_gib'] = min(readings) if readings else None
                free = [p['available_gib'] for p in phone_readings if isinstance(p.get('available_gib'), (int, float))]
                row['minimum_phone_available_gib'] = min(free) if free else None
                remote_rss = [p['worker_memory']['rss_bytes'] for p in phone_readings if p.get('worker_memory') and p['worker_memory'].get('rss_bytes') is not None]
                row['peak_sampled_phone_rss_bytes'] = max(remote_rss) if remote_rss else None
                row['phone_observations'] = phone_readings
                current = tunnel.stats(); row['network'] = {k: current[k]-initial_traffic[k] for k in current}
                row['transport_error'] = tunnel.last_error
                row['engine_exit_code'] = proc.returncode if proc else None
                row['safety_stop'] = pressure.is_set()
                if mode == 'laptop_cpu_and_phone':
                    after = phone_readings[-1] if phone_readings else {}
                    row['participation'] = participation(logpath.read_text(encoding='utf-8', errors='replace') if logpath.exists() else '', before, after, row['network'])
                save()
        report['status'] = 'completed' if all(r['status'] == 'completed' for r in report['runs']) else 'incomplete'
        return report
    finally:
        report['finished_at'] = time.time()
        if cancelled(): report['status'] = 'cancelled'
        elif report['status'] == 'running': report['status'] = 'failed'
        report['model_parallel_verified'] = False
        save()
        with manager.lock: manager.tunnels.pop(identity, None)
        tunnel.close()
