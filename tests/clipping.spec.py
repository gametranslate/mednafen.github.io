"""Check native presentation geometry, not just the emulator's framebuffer.

All windows and process-local messages belong to an unselected private desktop.
No desktop switching, global input, screenshots of the user's desktop or audio.
"""
import ctypes, hashlib, json, os, time
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright, expect
from private_desktop import PrivateDesktop, ROOT, u, W

ROM = Path(os.environ['MEDNAFEN_PLAY_TEST_ROM'])
EXE = Path(os.environ.get('MEDNAFEN_PLAY_TEST_EXE', str(ROOT/'src-tauri/target/debug/mednafen-play.exe')))
digest = hashlib.sha256(ROM.read_bytes()).hexdigest()
g = ctypes.WinDLL('gdi32', use_last_error=True)
g.CreateRectRgn.argtypes = [ctypes.c_int]*4; g.CreateRectRgn.restype = W.HANDLE
g.DeleteObject.argtypes = [W.HANDLE]
g.PtInRegion.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_int]
u.GetWindowRgn.argtypes = [W.HWND, W.HANDLE]
u.FindWindowExW.argtypes = [W.HWND, W.HWND, W.LPCWSTR, W.LPCWSTR]; u.FindWindowExW.restype = W.HWND
u.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
u.GetClientRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
u.SetWindowPos.argtypes = [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.UINT]
# Match the DPI-aware application's physical coordinates; this changes only this tester.
u.SetThreadDpiAwarenessContext.argtypes = [W.HANDLE]; u.SetThreadDpiAwarenessContext.restype = W.HANDLE
u.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))

with sync_playwright() as pw:
    host = PrivateDesktop(EXE, 9353)
    try:
        page = host.connect(pw); invoke = host.invoke
        errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
        webview = u.FindWindowExW(host.hwnd, None, 'WRY_WEBVIEW', None)
        assert webview, 'WRY native child missing'
        records = []

        def wait(test, label, timeout=20):
            end = time.monotonic()+timeout
            while time.monotonic() < end:
                if test(): return
                time.sleep(.1)
            raise AssertionError(label+'\n'+invoke('get_log')[-1800:])

        def click(name):
            page.get_by_role('button', name=name, exact=True).last.evaluate('(b)=>b.click()')

        def rect(hwnd):
            r = W.RECT(); assert u.GetWindowRect(hwnd, ctypes.byref(r))
            return (r.left, r.top, r.right, r.bottom)

        def clipping(full=False):
            child = u.GetPropW(host.hwnd, 'MPChild')
            if not child or not u.IsWindowVisible(child): return False
            if not u.GetWindowLongW(host.hwnd, -16) & 0x02000000: return False
            if not u.GetWindowLongW(webview, -16) & 0x04000000: return False
            r = g.CreateRectRgn(0,0,0,0)
            try:
                kind = u.GetWindowRgn(webview, r)
                if full: return kind == 1  # NULLREGION: the entire webview is excluded.
                if kind not in (2,3): return False
                w = rect(webview); c = rect(child)
                # Check every native-game edge plus its center in WebView coordinates.
                xs = (c[0]-w[0]+1, (c[0]+c[2])//2-w[0], c[2]-w[0]-2)
                ys = (c[1]-w[1]+1, (c[1]+c[3])//2-w[1], c[3]-w[1]-2)
                if any(g.PtInRegion(r,x,y) for x in xs for y in ys): return False
                # Header, sidebar and game toolbar must remain drawable and clickable.
                return all(g.PtInRegion(r,x,y) for x,y in [(10,10),(10,ys[1]),(xs[1],max(1,c[1]-w[1]-10))])
            finally: g.DeleteObject(r)

        def restored():
            r = g.CreateRectRgn(0,0,0,0)
            try:
                child = u.GetPropW(host.hwnd,'MPChild')
                return u.GetWindowRgn(webview,r)==0 and (not child or not u.IsWindowVisible(child))
            finally: g.DeleteObject(r)

        def capture(name):
            frame = host.home/'frame.ppm'; frame.unlink(missing_ok=True)
            u.SetPropW(host.hwnd,'MPQACapture',1)
            wait(lambda:frame.exists() and frame.stat().st_size>1000, 'No captured frame')
            for _ in range(30):
                try: im=Image.open(frame); im.load(); break
                except Exception: time.sleep(.1)
            colors=len(im.getcolors(im.width*im.height))
            assert colors>10, (name,colors)
            im.save(host.home/(name+'.png'))
            return colors

        def resize(width,height):
            # Only our private desktop's main window, with SWP_NOACTIVATE|NOZORDER|NOMOVE.
            before = rect(host.hwnd)
            assert u.SetWindowPos(host.hwnd,None,0,0,width,height,0x0016)
            wait(lambda:rect(host.hwnd)!=before,'Resize not applied')
            time.sleep(.6)

        for driver in ['opengl','softfb']:
            # Keep the real audio path active but silent; never use the user's profile.
            invoke('save_settings', {'scope':None,'values':{'sound':'1','sound.volume':'0','sound.driver':'wasapish','video.driver':driver},'preferences':None})
            invoke('add_games', {'paths':[str(ROM)]})
            expect(page.locator('.play-button')).to_be_enabled()
            page.locator('.play-button').evaluate('(b)=>b.click()')
            wait(lambda:invoke('player_status')['ready'],'No first frame')
            wait(clipping, 'WebView overlaps the native game viewport')
            running = invoke('load_snapshot')['running']
            time.sleep(3)
            colors = capture(driver+'-embedded')
            frames = invoke('player_status')['frames']
            time.sleep(.5)
            assert invoke('player_status')['frames']>frames
            log = invoke('get_log'); assert 'WASAPI' in log,log[-1500:]
            resize(1100,760); wait(clipping, 'Clipping incorrect after resizing')
            click('Log'); expect(page.get_by_role('dialog')).to_be_visible()
            wait(restored,'Log is obscured by native game')
            resize(1180,820); wait(restored,'Resizing restored a game on top of Log')
            page.get_by_role('dialog').get_by_role('button',name='Close',exact=True).last.evaluate('(b)=>b.click()')
            wait(clipping,'Clipping not reapplied after closing Log')
            click('Settings'); wait(restored,'Settings still clipped')
            click('About'); wait(restored,'About still clipped')
            click('Now playing'); wait(clipping,'Game viewport not restored')
            invoke('player_fullscreen',{'value':True})
            wait(lambda:clipping(True),'Fullscreen WebView still covers game')
            expect(page.locator('.app-header')).not_to_be_visible()
            child = u.GetPropW(host.hwnd,'MPChild')
            u.PostMessageW(child,0x0100,27,0x00010001)
            wait(lambda:not invoke('player_status')['fullscreen'],'Esc did not leave fullscreen')
            wait(clipping,'Clipping incorrect after Esc')
            expect(page.locator('.app-header')).to_be_visible()
            assert invoke('load_snapshot')['running']==running
            click('Stop game'); wait(lambda:invoke('load_snapshot')['running'] is None,'Stop failed')
            wait(restored,'Stop left the WebView clipped')
            expect(page.locator('.play-button')).to_be_enabled()
            records.append({'driver':driver,'frameColors':colors,'clipGame':True,'keepMenus':True,'resize':True,'logResize':True,'settingsAbout':True,'fullscreenEsc':True,'stopRestores':True,'audioEnabledSilent':True})
            print('PASS',driver,'native clipping, menus, resize, Log, Settings, About, fullscreen/Esc, Stop; nonblank frame and silent WASAPI',flush=True)
        assert not errors,errors
        assert hashlib.sha256(ROM.read_bytes()).hexdigest()==digest
        (host.home/'result.json').write_text(json.dumps({'status':'PASS','privateDesktop':True,'userVisibleDesktopTested':False,'romSha256':digest,'checks':records},indent=2))
    finally: host.close()
