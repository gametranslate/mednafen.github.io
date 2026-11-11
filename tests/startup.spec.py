"""Startup timeout and close while hung, without touching the selected desktop."""
import hashlib,json,os,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from private_desktop import PrivateDesktop,ROOT,u
ROM=Path(os.environ.get('MEDNAFEN_PLAY_TEST_ROM','D:/Workspace/WSC/Namco Super Wars (Japan)/Namco Super Wars (Japan).wsc'))
EXE=Path(os.environ.get('MEDNAFEN_PLAY_TEST_EXE',str(ROOT/'src-tauri/target/debug/mednafen-play.exe')))
digest=hashlib.sha256(ROM.read_bytes()).hexdigest()
with sync_playwright() as pw:
    host=PrivateDesktop(EXE,9352)
    try:
        page=host.connect(pw);invoke=host.invoke
        invoke('save_settings',{'scope':None,'values':{'sound':'0'},'preferences':None})
        game=invoke('add_games',{'paths':[str(ROM)]})['games'][0]
        expect(page.locator('.play-button')).to_be_enabled()
        page.locator('.play-button').evaluate('(b)=>b.click()')
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            children=[p for p in host.proc.children() if p.name().lower()=='mednafen.exe']
            if children:break
            time.sleep(.01)
        assert children,'Emulator did not spawn'
        emu=children[0];emu.suspend()
        assert not invoke('player_status')['ready'],'Suspension missed startup'
        start=time.monotonic()
        expect(page.get_by_role('alert')).to_contain_text('15 seconds',timeout=25000)
        assert time.monotonic()-start<24
        assert invoke('load_snapshot')['running'] is None
        emu.wait(timeout=5)
        assert 'Startup timed out' in invoke('get_log')
        page.get_by_role('dialog').get_by_role('button',name='Close',exact=True).last.evaluate('(b)=>b.click()')
        expect(page.locator('.play-button')).to_be_enabled()
        page.locator('.play-button').evaluate('(b)=>b.click()')
        for _ in range(100):
            if invoke('player_status')['ready']:break
            time.sleep(.1)
        assert invoke('player_status')['ready']
        # Close remains cancellable when settings have edits, without losing the game.
        page.get_by_role('button',name='Settings',exact=True).evaluate('(b)=>b.click()')
        page.get_by_role('button',name='Audio',exact=True).evaluate('(b)=>b.click()')
        page.locator('[data-setting="sound.volume"] input').fill('71')
        u.PostMessageW(host.hwnd,0x0010,0,0)
        expect(page.get_by_role('dialog',name='Settings not saved')).to_be_visible()
        page.get_by_role('dialog').get_by_role('button',name='Return',exact=True).evaluate('(b)=>b.click()')
        assert invoke('load_snapshot')['running']==game['id']
        emu=next(p for p in host.proc.children() if p.name().lower()=='mednafen.exe');emu.suspend()
        u.PostMessageW(host.hwnd,0x0010,0,0)
        page.get_by_role('dialog').get_by_role('button',name='Discard changes and close',exact=True).evaluate('(b)=>b.click()')
        host.proc.wait(timeout=12);emu.wait(timeout=5)
        assert digest==hashlib.sha256(ROM.read_bytes()).hexdigest()
        (host.home/'result.json').write_text(json.dumps({'status':'PASS','startupTimeoutSeconds':15,'forcedCleanup':True,'replayAfterTimeout':True,'dirtyCloseGuard':True,'closeHungGame':True,'romUnchanged':True},indent=2))
        print('PASS bounded startup, replay after timeout, dirty close guard, close with hung game',flush=True)
    finally:host.close()
