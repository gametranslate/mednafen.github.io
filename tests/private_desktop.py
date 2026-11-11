"""Native test host on an unselected Windows desktop. Never calls SwitchDesktop."""
from pathlib import Path
import ctypes, os, subprocess, time, urllib.request
from ctypes import wintypes as W
import psutil

ROOT=Path(__file__).resolve().parents[1]
u=ctypes.WinDLL('user32',use_last_error=True)
k=ctypes.WinDLL('kernel32',use_last_error=True)
u.CreateDesktopW.argtypes=[W.LPCWSTR,ctypes.c_void_p,ctypes.c_void_p,W.DWORD,W.DWORD,ctypes.c_void_p]
u.CreateDesktopW.restype=W.HANDLE
u.CloseDesktop.argtypes=[W.HANDLE]
u.EnumDesktopWindows.argtypes=[W.HANDLE,ctypes.c_void_p,ctypes.c_void_p]
u.GetPropW.argtypes=[W.HWND,W.LPCWSTR];u.GetPropW.restype=W.HANDLE
u.SetPropW.argtypes=[W.HWND,W.LPCWSTR,W.HANDLE]
u.GetWindowThreadProcessId.argtypes=[W.HWND,ctypes.POINTER(W.DWORD)]
u.GetWindowTextLengthW.argtypes=[W.HWND]
u.GetWindowLongW.argtypes=[W.HWND,ctypes.c_int]
u.IsWindowVisible.argtypes=[W.HWND]
u.GetParent.argtypes=[W.HWND];u.GetParent.restype=W.HWND
u.PostMessageW.argtypes=[W.HWND,W.UINT,ctypes.c_size_t,ctypes.c_ssize_t]
u.SendMessageW.argtypes=[W.HWND,W.UINT,ctypes.c_size_t,ctypes.c_ssize_t]
class SI(ctypes.Structure):
    _fields_=[('cb',W.DWORD),('lpReserved',W.LPWSTR),('lpDesktop',W.LPWSTR),('lpTitle',W.LPWSTR),('dwX',W.DWORD),('dwY',W.DWORD),('dwXSize',W.DWORD),('dwYSize',W.DWORD),('dwXCountChars',W.DWORD),('dwYCountChars',W.DWORD),('dwFillAttribute',W.DWORD),('dwFlags',W.DWORD),('wShowWindow',W.WORD),('cbReserved2',W.WORD),('lpReserved2',ctypes.c_void_p),('hStdInput',W.HANDLE),('hStdOutput',W.HANDLE),('hStdError',W.HANDLE)]
class PI(ctypes.Structure):
    _fields_=[('hProcess',W.HANDLE),('hThread',W.HANDLE),('dwProcessId',W.DWORD),('dwThreadId',W.DWORD)]
k.CreateProcessW.argtypes=[W.LPCWSTR,W.LPWSTR,ctypes.c_void_p,ctypes.c_void_p,W.BOOL,W.DWORD,ctypes.c_void_p,W.LPCWSTR,ctypes.POINTER(SI),ctypes.POINTER(PI)]
k.CloseHandle.argtypes=[W.HANDLE]

class PrivateDesktop:
    def __init__(self,exe,port=9351):
        self.home=ROOT/'.cache'/('session-qa-'+str(time.time_ns()));self.home.mkdir()
        self.port=port
        self.name='MednafenQA'+str(time.time_ns())
        self.desktop=u.CreateDesktopW(self.name,None,None,0,0x1ff,None)
        assert self.desktop,ctypes.get_last_error()
        env=dict(os.environ,MEDNAFEN_PLAY_TEST_HOME=str(self.home),WEBVIEW2_USER_DATA_FOLDER=str(self.home/'webview'),MEDNAFEN_PLAY_QA_CAPTURE=str(self.home/'frame.ppm'),WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=f'--remote-debugging-port={port}')
        env.pop('MEDNAFEN_PLAY_BACKGROUND_QA',None)
        si=SI();si.cb=ctypes.sizeof(si);si.lpDesktop='WinSta0\\'+self.name
        self.pi=PI()
        block=ctypes.create_unicode_buffer('\0'.join(key+'='+value for key,value in sorted(env.items()))+'\0\0')
        cmd=ctypes.create_unicode_buffer(subprocess.list2cmdline([str(exe)]))
        assert k.CreateProcessW(None,cmd,None,None,False,0x08000400,block,str(ROOT),ctypes.byref(si),ctypes.byref(self.pi)),ctypes.get_last_error()
        self.proc=psutil.Process(self.pi.dwProcessId)
        print('Private desktop test:',self.home,flush=True)
    def connect(self,playwright):
        for _ in range(150):
            try:urllib.request.urlopen(f'http://127.0.0.1:{self.port}/json/version',timeout=.3).read();break
            except Exception:time.sleep(.2)
        self.browser=playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{self.port}')
        self.page=self.browser.contexts[0].pages[0]
        self.page.wait_for_function('!!window.__TAURI_INTERNALS__')
        assert Path(self.invoke('load_snapshot')['dataDir']).resolve()==self.home.resolve(),'Connected to the wrong test instance'
        handles=[]
        @ctypes.WINFUNCTYPE(W.BOOL,W.HWND,ctypes.c_void_p)
        def enum(h,l):
            pid=W.DWORD();u.GetWindowThreadProcessId(h,ctypes.byref(pid))
            if pid.value==self.proc.pid and u.GetWindowTextLengthW(h)>0:handles.append(h)
            return True
        u.EnumDesktopWindows(self.desktop,enum,None)
        self.hwnd=next(h for h in handles if u.IsWindowVisible(h))
        return self.page
    def invoke(self,c,a=None):
        return self.page.evaluate('([c,a])=>window.__TAURI_INTERNALS__.invoke(c,a||{})',[c,a])
    def close(self):
        try:
            children=self.proc.children(recursive=True)
        except psutil.Error:children=[]
        for child in children+[self.proc]:
            try:child.terminate()
            except psutil.Error:pass
        psutil.wait_procs(children+[self.proc],timeout=5)
        k.CloseHandle(self.pi.hProcess);k.CloseHandle(self.pi.hThread);u.CloseDesktop(self.desktop)
