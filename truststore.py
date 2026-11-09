"""Windows user-bound DPAPI storage. Never fall back to plaintext credentials."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def protect(value, decrypt=False):
    if os.name != 'nt':
        raise OSError('Remembered pairing requires Windows DPAPI on this desktop. Session pairing is still available.')
    source = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
    incoming, outgoing = Blob(len(value), source), Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    operation = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    operation.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    operation.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    if not operation(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(outgoing.data, outgoing.size)
    finally:
        kernel.LocalFree(outgoing.data)


class TrustStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists(): return {}
        result = json.loads(protect(self.path.read_bytes(), decrypt=True))
        if not isinstance(result, dict): raise ValueError('Invalid remembered-device file.')
        return result

    def save(self, records):
        content = protect(json.dumps(records, allow_nan=False).encode())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_bytes(content)
        temporary.replace(self.path)
