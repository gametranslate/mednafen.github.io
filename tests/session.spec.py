"""Startup/drop/stop/close regressions; normal presentation on a private desktop."""
import ctypes, hashlib, json, os, shutil, time
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright, expect
from private_desktop import PrivateDesktop,ROOT,u,k,W
ROM=Path(os.environ.get('MEDNAFEN_PLAY_TEST_ROM','D:/Workspace/WSC/Namco Super Wars (Japan)/Namco Super Wars (Japan).wsc'))
EXE=Path(os.environ.get('MEDNAFEN_PLAY_TEST_EXE',str(ROOT/'src-tauri/target/debug/mednafen-play.exe')))
digest=hashlib.sha256(ROM.read_bytes()).hexdigest()

with sync_playwright() as pw:
    host=PrivateDesktop(EXE)
    try:
        page=host.connect(pw);invoke=host.invoke
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        def click(name):
            target=page.locator('.sidebar nav button').first if name=='All games' else page.get_by_role('button',name=name,exact=True)
            # Native first-frame readiness can precede completion of the UI launch
            # promise. Programmatic click() silently ignores a disabled button.
            expect(target.last).to_be_enabled()
            target.last.evaluate('(b)=>b.click()')
        def wait(test,timeout=20):
            end=time.monotonic()+timeout
            while time.monotonic()<end:
                if test():return
                time.sleep(.1)
            raise AssertionError('Timed out: '+invoke('get_log')[-1500:])
        def drop(paths,event='tauri://drag-drop'):
            invoke('plugin:event|emit',{'event':event,'payload':{'paths':list(map(str,paths)),'position':{'x':300,'y':300}} if event.startswith('tauri:') else list(map(str,paths))})
        def capture(name):
            time.sleep(3)
            frame=host.home/'frame.ppm';frame.unlink(missing_ok=True);u.SetPropW(host.hwnd,'MPQACapture',1)
            wait(lambda:frame.exists() and frame.stat().st_size>1000)
            for _ in range(30):
                try:im=Image.open(frame);im.load();break
                except Exception:time.sleep(.1)
            assert len(im.getcolors(im.width*im.height))>10,'Blank native frame'
            im.save(host.home/(name+'.png'))
        invoke('save_settings',{'scope':None,'values':{'sound':'0'},'preferences':None})
        expect(page.locator('.empty-library')).to_be_visible()
        page.wait_for_timeout(700)
        # A suppressed rAF must not block startup. The old UI waited for two rAFs.
        page.evaluate('window.realRAF=window.requestAnimationFrame;window.requestAnimationFrame=()=>0')
        drop([ROM])
        wait(lambda:invoke('player_status')['ready'])
        first=invoke('load_snapshot')['running'];assert first
        expect(page.locator('[data-testid="player-viewport"]')).to_be_visible()
        wait(lambda:page.locator('[data-testid="player-viewport"] [role="status"]').count()==0)
        assert u.GetParent(u.GetPropW(host.hwnd,'MPChild'))==host.hwnd
        assert u.IsWindowVisible(u.GetPropW(host.hwnd,'MPChild'))
        assert u.GetWindowLongW(u.GetPropW(host.hwnd,'MPChild'),-20)&0x10,'Native child must accept Explorer file drops'
        capture('normal-embedded')
        page.evaluate('()=>{window.requestAnimationFrame=window.realRAF;}')
        print('PASS drop-to-play, normal native frame, suppressed animation frames',flush=True)
        # Same ROM must reuse the running game, and invalid drops must not stop it.
        child=u.GetPropW(host.hwnd,'MPChild');drop([ROM]);time.sleep(.8)
        assert len(invoke('load_snapshot')['store']['games'])==1
        assert u.GetPropW(host.hwnd,'MPChild')==child
        invalid=host.home/'unsupported.txt';invalid.write_text('not a ROM')
        drop([invalid]);expect(page.get_by_role('alert')).to_contain_text('not supported')
        assert invoke('load_snapshot')['running']==first
        drop([ROM,ROM]);expect(page.get_by_role('alert')).to_contain_text('one game')
        assert invoke('load_snapshot')['running']==first
        # Native WM_DROPFILES is handled on the SDL child and forwarded to the app.
        second=host.home/'second.wsc';shutil.copyfile(ROM,second)
        class DROPFILES(ctypes.Structure):
            _fields_=[('pFiles',W.DWORD),('pt',W.POINT),('fNC',W.BOOL),('fWide',W.BOOL)]
        raw=(str(second)+chr(0)+chr(0)).encode('utf-16-le')
        header=DROPFILES();header.pFiles=ctypes.sizeof(header);header.fWide=1
        k.GlobalAlloc.argtypes=[W.UINT,ctypes.c_size_t];k.GlobalAlloc.restype=W.HANDLE
        k.GlobalLock.argtypes=[W.HANDLE];k.GlobalLock.restype=ctypes.c_void_p
        k.GlobalUnlock.argtypes=[W.HANDLE]
        mem=k.GlobalAlloc(0x42,ctypes.sizeof(header)+len(raw));ptr=k.GlobalLock(mem)
        ctypes.memmove(ptr,ctypes.byref(header),ctypes.sizeof(header));ctypes.memmove(ptr+ctypes.sizeof(header),raw,len(raw));k.GlobalUnlock(mem)
        u.PostMessageW(child,0x0233,mem,0)
        wait(lambda:invoke('load_snapshot')['running'] not in [None,first])
        wait(lambda:invoke('player_status')['ready'])
        assert len(invoke('load_snapshot')['store']['games'])==2
        capture('native-drop-switch')
        print('PASS duplicate/invalid/multiple drops and native game-surface drop switch',flush=True)
        # Fullscreen/Esc leaves the emulator alive.
        invoke('player_fullscreen',{'value':True});wait(lambda:invoke('player_status')['fullscreen'])
        child=u.GetPropW(host.hwnd,'MPChild');u.PostMessageW(child,0x0100,27,0x00010001)
        wait(lambda:not invoke('player_status')['fullscreen'])
        assert invoke('load_snapshot')['running']
        # A hidden game remains stoppable directly from the library, then can replay.
        click('All games');wait(lambda:page.locator('.library-view').is_visible())
        click('Stop game');wait(lambda:invoke('load_snapshot')['running'] is None)
        expect(page.locator('.play-button')).to_be_enabled()
        page.locator('.play-button').evaluate('(b)=>b.click()')
        wait(lambda:invoke('player_status')['ready'])
        click('Stop game');wait(lambda:invoke('load_snapshot')['running'] is None)
        print('PASS fullscreen/Esc, Stop from library, replay',flush=True)
        # Dirty settings are preserved until the user chooses to discard.
        invoke('save_settings',{'scope':first,'values':{'sound.volume':'61'},'preferences':None})
        click('Settings');click('Audio')
        page.locator('[data-setting="sound.volume"] input').fill('71')
        drop([ROM]);expect(page.get_by_role('dialog')).to_contain_text('unsaved settings')
        assert invoke('load_snapshot')['running'] is None
        click('Continue editing');expect(page.locator('[data-setting="sound.volume"] input')).to_have_value('71')
        drop([ROM]);click('Discard and play');wait(lambda:invoke('player_status')['ready'])
        # Clear confirms and preserves actual ROM/BIOS/save files, stopping the game.
        saved=host.home/'mednafen/sav/keep.sav';saved.parent.mkdir(exist_ok=True);saved.write_bytes(b'preserve-save')
        bios=host.home/'mednafen/firmware/keep.bin';bios.parent.mkdir(exist_ok=True);bios.write_bytes(b'preserve-bios')
        click('All games');click('Clear library');expect(page.get_by_role('dialog')).to_contain_text('ROM files')
        click('Cancel');assert len(invoke('load_snapshot')['store']['games'])==2
        click('Clear library');page.get_by_role('dialog').get_by_role('button',name='Clear library',exact=True).evaluate('(b)=>b.click()')
        wait(lambda:len(invoke('load_snapshot')['store']['games'])==0)
        assert invoke('load_snapshot')['running'] is None
        assert saved.read_bytes()==b'preserve-save' and bios.read_bytes()==b'preserve-bios' and second.is_file()
        assert not invoke('load_snapshot')['store']['gameSettings']
        print('PASS dirty settings and confirmed clear; ROM/BIOS/saves preserved',flush=True)
        # A hung owned process is cleaned up by Stop, allowing another launch.
        drop([ROM]);wait(lambda:invoke('player_status')['ready'])
        emu=next(p for p in host.proc.children() if p.name().lower()=='mednafen.exe');emu.suspend()
        assert invoke('stop_game') is True
        assert invoke('load_snapshot')['running'] is None
        # Dismiss the failure log then relaunch. Window close must save and exit itself.
        if page.get_by_role('dialog').count():click('Close')
        drop([ROM]);wait(lambda:invoke('player_status')['ready'])
        emu=next(p for p in host.proc.children() if p.name().lower()=='mednafen.exe')
        u.PostMessageW(host.hwnd,0x0010,0,0)
        host.proc.wait(timeout=12);emu.wait(timeout=5)
        assert not errors,errors
        assert digest==hashlib.sha256(ROM.read_bytes()).hexdigest()
        (host.home/'result.json').write_text(json.dumps({'status':'PASS','normalPresentation':True,'privateDesktop':True,'romSha256':digest,'checks':['drop','frame-ready','suppressed-raf','native-drop','switch','duplicate','invalid','fullscreen-esc','stop-replay','dirty-settings','clear-preserves-files','hung-stop','window-close']},indent=2))
        print('PASS hung-process recovery and close-with-game; ROM unchanged',flush=True)
    finally:host.close()
