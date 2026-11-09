import unittest,tempfile,json,io,hashlib
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import autotest
class AutomaticTests(unittest.TestCase):
 def test_plan_reserves_memory_and_descends(self):
  p=autotest.plan({'ram_gib':32,'available_gib':16},'thorough')
  self.assertEqual(p['candidates'][0]['parameters_b'],8)
  self.assertEqual(p['reserve_gib'],6.4)
  self.assertGreater(p['max_download_bytes'],p['first_download_bytes'])
  self.assertEqual(autotest.plan({'ram_gib':32,'available_gib':3})['candidates'],[])
  self.assertEqual(autotest.plan({})['candidates'],[])
 def test_comfort_requires_slowest_and_memory(self):
  r={'samples':[{'predicted_per_second':20},{'predicted_per_second':14}],'minimum_free_ram_gib':8}
  self.assertFalse(autotest.comfortable(r,6.4));r['samples'][1]['predicted_per_second']=17
  self.assertTrue(autotest.comfortable(r,6.4));r['minimum_free_ram_gib']=None
  self.assertFalse(autotest.comfortable(r,6.4))
 def test_timings_require_real_counts_and_finite_speed(self):
  good={'timings':{'predicted_n':128,'predicted_ms':6400,'predicted_per_second':20,'cache_n':0}}
  self.assertEqual(autotest.validate_timings(good)['predicted_n'],128)
  for key,val in [('predicted_n',12),('predicted_per_second',float('nan')),('predicted_per_second',100),('cache_n',10)]:
   bad=json.loads(json.dumps(good));bad['timings'][key]=val
   with self.assertRaises(ValueError):autotest.validate_timings(bad)
 def test_owned_cleanup_refuses_user_files(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/('scan-'+'a'*32);p.mkdir();(p/'keep.txt').write_text('test')
   with self.assertRaises(ValueError):autotest.owned_cleanup(p,Path(d),'mine')
   self.assertTrue((p/'keep.txt').exists());(p/'.locallens-owner').write_text('mine')
   autotest.owned_cleanup(p,Path(d),'mine');self.assertFalse(p.exists())
 def test_cancel_and_hash_mismatch_leave_no_recommendation(self):
  with tempfile.TemporaryDirectory() as d:
   scan=autotest.Scan(Path(d),{'ram_gib':32,'available_gib':16},lambda **x:None,lambda:True,lambda p:None)
   r=scan.run();self.assertEqual(r['status'],'cancelled');self.assertIsNone(r['recommendation'])
  with tempfile.TemporaryDirectory() as d:
   scan=autotest.Scan(Path(d),{},lambda **x:None,lambda:False,lambda p:None)
   with patch.object(autotest.HTTP,'open',return_value=io.BytesIO(b'test')):
    with self.assertRaises(ValueError):scan.download('https://example.invalid',Path(d)/'test',4,'0'*64,'fixture')
 def test_recovery_only_cleans_dead_process_owned_scratch(self):
  import os
  if os.name!='nt':self.skipTest('Windows process recovery')
  with tempfile.TemporaryDirectory() as d:
   parent=Path(d)/'temporary';parent.mkdir()
   for suffix,pid in [('a',os.getpid()),('b',999999999)]:
    p=parent/('scan-'+suffix*32);p.mkdir();(p/'.locallens-owner').write_text(suffix*32)
    (p/'.locallens-meta.json').write_text(json.dumps({'pid':pid,'owner':suffix*32}))
   messages=autotest.recover_temporary(Path(d))
   self.assertTrue((parent/('scan-'+'a'*32)).exists());self.assertFalse((parent/('scan-'+'b'*32)).exists());self.assertEqual(len(messages),1)
 def test_zip_traversal_is_rejected(self):
  import zipfile
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);z=d/'bad.zip'
   with zipfile.ZipFile(z,'w') as f:f.writestr('../outside','bad')
   scan=autotest.Scan(d,{},lambda **x:None,lambda:False,lambda p:None)
   with self.assertRaises(ValueError):scan.extract(z,d/'engine')
   self.assertFalse((d/'outside').exists())
if __name__=='__main__':unittest.main()
