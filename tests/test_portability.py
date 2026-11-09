import unittest,tempfile,json,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import device,app,autotest
class PortabilityTests(unittest.TestCase):
 def test_identity_is_opaque_and_not_based_on_cpu_model(self):
  a=device.fingerprint('machine-A');b=device.fingerprint('machine-B')
  self.assertEqual(len(a),64);self.assertNotEqual(a,b);self.assertNotIn('machine',a);self.assertIsNone(device.fingerprint(None))
 def test_same_hardware_different_devices_do_not_share_recommendations(self):
  a={'cpu':'Identical CPU','device_id':device.fingerprint('A')};b={**a,'device_id':device.fingerprint('B')}
  self.assertEqual(device.record_scope({'hardware':a},a),'current')
  self.assertEqual(device.record_scope({'hardware':a},b),'other')
  self.assertEqual(device.record_scope({'hardware':{'cpu':'Identical CPU'}},b),'unverified')
 def test_new_empty_data_directory_has_no_seed_scores(self):
  with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)),patch.object(app,'HARDWARE',{'device_id':'new-laptop'},create=True):
   self.assertEqual(app.history(),[]);self.assertEqual(app.scan_history(),[])
 def test_foreign_records_are_preserved_but_labeled_without_mutating_disk(self):
  with tempfile.TemporaryDirectory() as d,patch.object(app,'DATA',Path(d)),patch.object(app,'HARDWARE',{'device_id':'laptop-B'},create=True):
   folder=Path(d)/'saved';folder.mkdir();record={'id':'saved','finished_at':'2026-01-01','hardware':{'device_id':'laptop-A'},'recommendation':{'model':{'name':'fixture'}}}
   (folder/'scan.json').write_text(json.dumps(record));r=app.scan_history()[0]
   self.assertEqual(r['device_scope'],'other');self.assertEqual(r['recommendation'],record['recommendation']);self.assertNotIn('device_scope',json.loads((folder/'scan.json').read_text()))
 def test_model_selection_responds_to_memory_not_a_fixed_laptop(self):
  small=autotest.plan({'ram_gib':8,'available_gib':5},'thorough');large=autotest.plan({'ram_gib':32,'available_gib':20},'thorough')
  self.assertEqual(small['candidates'],[]);self.assertEqual(large['candidates'][0]['parameters_b'],8)
 def test_default_archive_excludes_runtime_data_but_keeps_source_and_build(self):
  import package_project,zipfile
  with tempfile.TemporaryDirectory() as d:
   destination=package_project.package(Path(d)/'clean.zip')
   with zipfile.ZipFile(destination) as archive:
    names=archive.namelist()
    self.assertIn('LocalLens/app.py',names)
    self.assertIn('LocalLens/frontend/dist/index.html',names)
    self.assertTrue(any(n.startswith('LocalLens/tests/fixtures/') for n in names))
    self.assertFalse(any(n.startswith('LocalLens/data/') or '/node_modules/' in n for n in names))
if __name__=='__main__':unittest.main()
