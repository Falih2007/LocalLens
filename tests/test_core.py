import json,sys,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app

class CoreTests(unittest.TestCase):
 def test_advisor_no_speed_and_unknown(self):
  for r in app.advisor({'available_gib':None}):
   self.assertEqual(r['evidence'],'estimated'); self.assertEqual(r['status'],'Unknown memory'); self.assertNotIn('tokens_per_second',r)
 def test_memory_boundaries(self):
  self.assertEqual(app.advisor({'available_gib':64})[0]['status'],'Likely fits')
  self.assertEqual(app.advisor({'available_gib':1})[-1]['status'],'Insufficient free RAM')
 def test_parser_rejects_bad_measurements(self):
  for data in ['[]','{}','not json',json.dumps([{'avg_ts':-1}]),json.dumps([{'avg_ts':float('nan')}])]:
   with self.assertRaises(ValueError):app.parse_bench(data,'cpu')
 def test_parser_requires_both_tests(self):
  with self.assertRaises(ValueError):app.parse_bench('[{"avg_ts":1,"n_prompt":128}]','cpu')
 def test_gpu_rejects_missing_device_evidence(self):
  with self.assertRaises(ValueError):app.parse_bench('[{"avg_ts":1,"n_gpu_layers":99}]','gpu')
 def test_failed_job_never_creates_score(self):
  with tempfile.TemporaryDirectory() as d:
   app.JOB.update(status='running'); app.worker({'executable':'missing.exe','model':'missing.gguf'},Path(d),{})
   self.assertEqual(app.JOB['status'],'failed'); self.assertFalse((Path(d)/'result.json').exists()); self.assertTrue((Path(d)/'job.json').exists())
 def test_production_assets_are_local_and_traversal_is_rejected(self):
  if not (app.ROOT/'frontend/dist/index.html').is_file():self.skipTest('Frontend not built')
  server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
  base=f'http://127.0.0.1:{server.server_port}'
  try:
   with urllib.request.urlopen(base) as r:html=r.read().decode('utf-8-sig')
   self.assertIn(app.TOKEN,html);self.assertNotIn('__TOKEN__',html)
   import re
   asset=re.search(r'src="(/assets/[^"]+\.js)"',html).group(1)
   with urllib.request.urlopen(base+asset) as r:self.assertEqual(r.status,200);self.assertIn('javascript',r.headers['Content-Type'])
   for route in ['/assets/%2e%2e/app.py','/assets/%2e%2e/%2e%2e/app.py']:
    with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+route)
    self.assertEqual(e.exception.code,404)
  finally:server.shutdown();server.server_close()
 def test_local_http_security_and_static_assets(self):
  app.HARDWARE={'available_gib':4};server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  base=f'http://127.0.0.1:{server.server_port}'
  try:
   for route in ['/','/app.js','/style.css']:
    with urllib.request.urlopen(base+route) as r:self.assertEqual(r.status,200)
   for headers in [{},{'X-LocalLens-Token':'wrong'},{'X-LocalLens-Token':app.TOKEN,'Host':'evil.example'}]:
    with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(urllib.request.Request(base+'/api/state',headers=headers))
    self.assertEqual(e.exception.code,403)
   with urllib.request.urlopen(urllib.request.Request(base+'/api/state',headers={'X-LocalLens-Token':app.TOKEN})) as r:self.assertIn('advisor',json.load(r))
  finally:server.shutdown();server.server_close()
if __name__=='__main__':unittest.main(verbosity=2)
