"""Real Mednafen keyboard/slot/fast-forward and Settings-view regressions.

CDP input targets only this app on an unselected private desktop. No global input.
The WonderSwan RTC saved by the engine measures emulated time independently of
adapter event counters and skipped video frames.
"""
import ctypes,gzip,hashlib,json,os,struct,time
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from private_desktop import PrivateDesktop,ROOT,u
ROM=Path(os.environ.get('MEDNAFEN_PLAY_TEST_ROM','D:/Workspace/WSC/Namco Super Wars (Japan)/Namco Super Wars (Japan).wsc'))
EXE=Path(os.environ.get('MEDNAFEN_PLAY_TEST_EXE',str(ROOT/'src-tauri/target/debug/mednafen-play.exe')))
digest=hashlib.sha256(ROM.read_bytes()).hexdigest()

with sync_playwright() as pw:
    host=PrivateDesktop(EXE,9354)
    try:
        page=host.connect(pw);invoke=host.invoke
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        def wait(check,label,seconds=20):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                if check():return
                time.sleep(.05)
            raise AssertionError(label+'\n'+invoke('get_log')[-1800:])
        def click(name):
            button=page.get_by_role('button',name=name,exact=True).last
            expect(button).to_be_enabled();button.evaluate('(b)=>b.click()')
        def press(key):page.keyboard.press(key,delay=110);time.sleep(.12)
        def statefile(slot):return next((host.home/'mednafen/mcs').glob('*.mc'+str(slot)),None)
        def save(slot):
            file=statefile(slot);old=file.stat().st_mtime_ns if file else 0
            press('F1')
            wait(lambda:statefile(slot) and statefile(slot).stat().st_mtime_ns>old,'F1 did not save slot '+str(slot))
            file=statefile(slot);raw=file.read_bytes()
            if raw.startswith(b'\x1f\x8b'):raw=gzip.decompress(raw)
            assert raw.startswith(b'MDFNSVST'),raw[:16]
            return raw
        def rtc(raw):
            # State variable layout: byte name length, name, uint32 size, data.
            def value(name):
                name=name.encode();marker=bytes([len(name)])+name
                offset=raw.index(marker)+len(marker);size=struct.unpack_from('<I',raw,offset)[0]
                assert size in (1,2,4,8),(name,size)
                return int.from_bytes(raw[offset+4:offset+4+size],'little')
            bcd=lambda n:(n>>4)*10+(n&15)
            return bcd(value('RTC.hour'))*3600+bcd(value('RTC.min'))*60+bcd(value('RTC.sec'))+value('ClockCycleCounter')/3072000
        invoke('save_settings',{'scope':None,'values':{'sound':'0','filesys.state_comp_level':'0'},'preferences':None})
        game=invoke('add_games',{'paths':[str(ROM)]})['games'][0]
        expect(page.locator('.play-button')).to_be_enabled();page.locator('.play-button').evaluate('(b)=>b.click()')
        wait(lambda:invoke('player_status')['ready'],'No first frame')
        expect(page.locator('[data-testid="player-viewport"] [role="status"]')).to_have_count(0)
        cfg=(host.home/'mednafen/mednafen.cfg').read_text(encoding='utf-8')
        for line in ['command.fast_forward keyboard 0x0 43','command.save_state keyboard 0x0 58','command.load_state keyboard 0x0 59','command.state_slot_inc keyboard 0x0 60','wswan.input.builtin.gamepad.a keyboard 0x0 27']:
            assert line in cfg,line
        # Deliberately leave focus on a UI button, reproducing the reported Tab bug.
        page.locator('.header-log').evaluate('(b)=>b.focus()')
        focused=page.evaluate('document.activeElement.className')
        first=save(0);t0=time.monotonic();r0=rtc(first)
        time.sleep(1.3);normal=save(0);normal_rate=((rtc(normal)-r0)%86400)/(time.monotonic()-t0)
        page.keyboard.down('Tab');wait(lambda:u.GetPropW(host.hwnd,'MPQATab')==1,'Tab not forwarded')
        fast_start=save(0);start=time.monotonic();r1=rtc(fast_start)
        time.sleep(1.5);fast=save(0);fast_rate=((rtc(fast)-r1)%86400)/(time.monotonic()-start)
        assert page.evaluate('document.activeElement.className')==focused,'Tab moved focus to another button'
        assert page.get_by_role('dialog').count()==0
        page.keyboard.up('Tab');wait(lambda:not u.GetPropW(host.hwnd,'MPQATab'),'Tab stuck after keyup')
        time.sleep(.3);release_start=save(0);start=time.monotonic();r2=rtc(release_start)
        time.sleep(1.3);released=save(0);released_rate=((rtc(released)-r2)%86400)/(time.monotonic()-start)
        assert .6<normal_rate<1.5,(normal_rate,fast_rate,released_rate)
        assert fast_rate>normal_rate*2,(normal_rate,fast_rate,released_rate)
        assert .6<released_rate<1.5,(normal_rate,fast_rate,released_rate)
        print('PASS Tab retains UI focus, real RTC rates:',normal_rate,fast_rate,released_rate,flush=True)
        press('F3');assert not statefile(1),'Changing slot saved a state'
        slot1=save(1);saved_rtc=rtc(slot1)
        page.keyboard.down('Tab');time.sleep(1.2);page.keyboard.up('Tab')
        press('F2');after_load=save(1)
        assert (rtc(after_load)-saved_rtc)%86400<1.5,'F2 did not load the saved state'
        press('F3');save(2)
        press('Shift+F3');save(1)
        assert statefile(0) and statefile(1) and statefile(2)
        print('PASS F1 saves, F2 loads, F3 next slot, Shift+F3 previous slot',flush=True)
        # Other game keys must reach the engine; holding X must not click UI.
        press('x');assert page.get_by_role('dialog').count()==0
        page.keyboard.down('Tab');click('Log')
        expect(page.get_by_role('dialog')).to_be_visible()
        wait(lambda:not u.GetPropW(host.hwnd,'MPQAKeys'),'Modal left keys pressed')
        page.keyboard.up('Tab')
        page.get_by_role('dialog').get_by_role('button',name='Close',exact=True).last.evaluate('(b)=>b.click()')
        time.sleep(.5);page.keyboard.down('Tab')
        page.evaluate('window.dispatchEvent(new Event("blur"))')
        wait(lambda:not u.GetPropW(host.hwnd,'MPQAKeys'),'Blur left keys pressed');page.keyboard.up('Tab')
        # Escape returns to menus, and keyboard navigation/typing work in Settings.
        press('Escape');expect(page.locator('.library-view')).to_be_visible()
        assert invoke('load_snapshot')['running']==game['id']
        click('Settings');click('Video')
        picker=page.locator('.system-picker select')
        picker.select_option('wswan')
        expect(page.locator('.settings-system-help')).to_contain_text('remembered automatically')
        expect(page.get_by_role('button',name='Save settings',exact=True)).to_be_disabled()
        click('Audio');click('Video');expect(picker).to_have_value('wswan')
        click('About');click('Settings');expect(picker).to_have_value('wswan')
        page.reload();page.wait_for_function('!!window.__TAURI_INTERNALS__');click('Settings');expect(picker).to_have_value('wswan')
        search=page.get_by_label('Search settings',exact=True);search.fill('');search.focus();page.keyboard.type('volume')
        expect(search).to_have_value('volume');search.fill('')
        assert invoke('load_snapshot')['running']==game['id']
        # Modifying an actual setting enables Save after stopping; selection is not engine config.
        invoke('stop_game');wait(lambda:invoke('load_snapshot')['running'] is None,'Stop failed')
        page.locator('[data-setting="wswan.scanlines"] input').fill('25')
        expect(page.get_by_role('button',name='Save settings',exact=True)).to_be_enabled();click('Save settings')
        wait(lambda:invoke('load_snapshot')['store']['settings'].get('wswan.scanlines')=='25','Video setting not saved')
        assert invoke('load_snapshot')['store']['games'][0]['system']=='wswan'
        print('PASS modal/blur release, Esc/menu, Settings system/category persistence, typing, real video save',flush=True)
        # Preserve an explicit user mapping while applying new defaults elsewhere.
        settings=invoke('load_snapshot')['store']['settings'];settings['wswan.input.builtin.gamepad.a']='keyboard 0x0 6'
        invoke('save_settings',{'scope':None,'values':settings,'preferences':None})
        page.locator('.sidebar nav button').first.evaluate('(b)=>b.click()');page.locator('.play-button').evaluate('(b)=>b.click()')
        wait(lambda:invoke('player_status')['ready'],'Replay failed')
        assert 'wswan.input.builtin.gamepad.a keyboard 0x0 6' in (host.home/'mednafen/mednafen.cfg').read_text(encoding='utf-8')
        child=u.GetPropW(host.hwnd,'MPChild')
        invoke('player_fullscreen',{'value':True});wait(lambda:invoke('player_status')['fullscreen'],'Fullscreen failed')
        u.PostMessageW(child,0x0100,27,0x00010001);wait(lambda:not invoke('player_status')['fullscreen'],'Native Esc failed')
        u.PostMessageW(child,0x0100,27,0x00010001);expect(page.locator('.library-view')).to_be_visible()
        click('Now playing');time.sleep(.5)
        # Native Alt+F4 closes the app, not just the engine. Only this private child.
        emu=next(p for p in host.proc.children() if p.name().lower()=='mednafen.exe')
        u.PostMessageW(child,0x0104,0x73,0x203e0001)
        host.proc.wait(timeout=12);emu.wait(timeout=5)
        assert not errors,errors
        assert hashlib.sha256(ROM.read_bytes()).hexdigest()==digest
        (host.home/'result.json').write_text(json.dumps({'status':'PASS','privateDesktop':True,'romSha256':digest,'normalRtcRate':normal_rate,'fastForwardRtcRate':fast_rate,'releasedRtcRate':released_rate,'checks':['tab-no-ui-navigation','real-fast-forward','keyup-release','F1-save','F2-load','F3-next','shift-F3-previous','modal-blur-release','settings-system-category-persistence','settings-typing','video-save','custom-mapping-preserved','native-fullscreen-esc','native-menu-esc','native-alt-f4']},indent=2))
        print('PASS custom mapping preserved, native Esc and native Alt+F4',flush=True)
    finally:host.close()
