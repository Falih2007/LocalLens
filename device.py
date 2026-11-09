"""Local-only device provenance. Never expose the raw Windows machine identifier."""
import hashlib,os

def fingerprint(value):
    if not isinstance(value,str) or not value.strip():return None
    return hashlib.sha256(('LocalLens/device/v1/'+value.strip().lower()).encode('utf-8')).hexdigest()

def current_device_id():
    if os.name!='nt':return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
            value,_=winreg.QueryValueEx(key,'MachineGuid')
        return fingerprint(value)
    except OSError:return None

def record_scope(record,hardware):
    saved=record.get('hardware',{}).get('device_id');current=hardware.get('device_id')
    if not saved or not current:return 'unverified'
    return 'current' if saved==current else 'other'

def annotate(record,hardware):
    return {**record,'device_scope':record_scope(record,hardware)}
