"""只读取证：读取指定进程环境块中的 DATABASE_URL（Windows x64，ctypes + NtQueryInformationProcess）。"""
import ctypes
from ctypes import wintypes

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
ProcessBasicInformation = 0


class PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p),
        ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2", ctypes.c_void_p * 2),
        ("UniqueProcessId", ctypes.c_void_p),
        ("Reserved3", ctypes.c_void_p),
    ]


class UNICODE_STRING(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", wintypes.LPWSTR),
    ]


class PEB(ctypes.Structure):
    _fields_ = [("Reserved", ctypes.c_byte * 2), ("BeingDebugged", ctypes.c_byte),
                ("Reserved2", ctypes.c_byte), ("Reserved3", ctypes.c_void_p * 2),
                ("Ldr", ctypes.c_void_p), ("ProcessParameters", ctypes.c_void_p)]


class RTL_USER_PROCESS_PARAMETERS(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_byte * 16),
        ("Reserved2", ctypes.c_void_p * 10),
        ("ImagePathName", UNICODE_STRING),
        ("CommandLine", UNICODE_STRING),
        ("Environment", ctypes.c_void_p),
    ]


def read_env(pid: int) -> dict:
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise OSError(ctypes.get_last_error())
    try:
        pbi = PROCESS_BASIC_INFORMATION()
        if ntdll.NtQueryInformationProcess(h, ProcessBasicInformation, ctypes.byref(pbi), ctypes.sizeof(pbi), None) != 0:
            raise OSError("NtQueryInformationProcess failed")
        # 读 PEB
        class PEBLite(ctypes.Structure):
            _fields_ = [("_pad", ctypes.c_byte * 0x20), ("ProcessParameters", ctypes.c_void_p)]
        peb_buf = ctypes.create_string_buffer(ctypes.sizeof(PEBLite))
        if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(pbi.PebBaseAddress), peb_buf, ctypes.sizeof(peb_buf), None):
            raise OSError(ctypes.get_last_error(), "ReadProcessMemory PEB")
        pp_ptr = ctypes.cast(peb_buf.raw, ctypes.POINTER(PEBLite)).contents.ProcessParameters
        # 读 RTL_USER_PROCESS_PARAMETERS
        params = RTL_USER_PROCESS_PARAMETERS()
        if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(pp_ptr), ctypes.byref(params), ctypes.sizeof(params), None):
            raise OSError(ctypes.get_last_error(), "ReadProcessMemory RTL")
        env_ptr = params.Environment
        # 读环境块：UTF-16LE，空串结束
        chunks = []
        while True:
            buf = ctypes.create_string_buffer(4096)
            read = ctypes.c_size_t()
            if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(env_ptr), buf, 4096, ctypes.byref(read)):
                raise OSError(ctypes.get_last_error(), "ReadProcessMemory env")
            chunks.append(buf.raw[: read.value])
            double = b"".join(chunks)
            if b"\x00\x00" in double[len(double) - 8:]:
                break
            env_ptr += read.value
        raw = b"".join(chunks)
        end = raw.find(b"\x00\x00")
        if end >= 0:
            raw = raw[:end]
        text = raw.decode("utf-16-le", errors="replace")
        env = {}
        for line in text.split("\x00"):
            if "=" in line:
                k, _, v = line.partition("=")
                env[k] = v
        return env
    finally:
        kernel32.CloseHandle(h)


if __name__ == "__main__":
    import sys
    env = read_env(int(sys.argv[1]))
    keys = [k for k in env if "DATABASE" in k.upper() or "DB_" in k.upper()]
    if keys:
        for k in keys:
            print(f"{k}={env[k]}")
    else:
        print("NO DATABASE_URL/DB_ env var in process env")
    print("cwd-related keys:", {k: env[k] for k in ("PWD", "OLDPWD") if k in env})