from pathlib import Path
import ctypes, json, os, subprocess, time, urllib.request
import psutil
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / '.cache' / ('native-qa-' + str(int(time.time())))
HOME.mkdir(parents=True)
FIX = HOME / 'games'
FIX.mkdir()
(FIX / 'invalid.nes').write_bytes(b'not a game')
(FIX / 'missing.cue').write_text('FILE "missing.bin" BINARY\n TRACK 01 MODE2/2352\n', encoding='utf-8')
program = bytearray([0x78,0xd8,0xa2,0xff,0x9a,0xa9,0x00,0x8d,0x00,0x20,0x8d,0x01,0x20,0x2c,0x02,0x20,0xa9,0x3f,0x8d,0x06,0x20,0xa9,0x00,0x8d,0x06,0x20,0xa9,0x21,0x8d,0x07,0x20,0xa9,0x0a,0x8d,0x01,0x20])
loop = 0x8000 + len(program)
program += bytes([0x4c,loop & 255,loop >> 8])
prg = bytearray([0xea])*16384
prg[:len(program)] = program
prg[-6:] = bytes([0,128,0,128,0,128])
rom = FIX / 'Thử nghiệm GameTranslate.nes'
rom.write_bytes(b'NES\x1a'+bytes([1,1])+bytes(10)+prg+bytes(8192))
rom=Path(os.environ.get('MEDNAFEN_PLAY_TEST_ROM',str(rom)))
env = dict(os.environ, MEDNAFEN_PLAY_TEST_HOME=str(HOME), WEBVIEW2_USER_DATA_FOLDER=str(HOME/'webview'), MEDNAFEN_PLAY_BACKGROUND_QA='1', WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9347')
exe = Path(os.environ.get('MEDNAFEN_PLAY_TEST_EXE', str(ROOT / 'src-tauri/target/debug/mednafen-play.exe')))
proc = subprocess.Popen([str(exe)],env=env,creationflags=subprocess.CREATE_NO_WINDOW)
print('Started native app',proc.pid,flush=True)
try:
    for _ in range(100):
        try:
            urllib.request.urlopen('http://127.0.0.1:9347/json/version',timeout=.5).read()
            break
        except Exception:
            time.sleep(.2)
    with sync_playwright() as p:
        browser=p.chromium.connect_over_cdp('http://127.0.0.1:9347')
        page=browser.contexts[0].pages[0]
        page.wait_for_function('!!window.__TAURI_INTERNALS__',timeout=15000)
        def invoke(cmd,args=None):
            return page.evaluate('([cmd,args])=>window.__TAURI_INTERNALS__.invoke(cmd,args||{})',[cmd,args])
        s=invoke('load_snapshot')
        assert s['engineExists'],s
        if os.environ.get('MEDNAFEN_PLAY_TEST_EXE'):
            assert Path(s['enginePath']).resolve()==(exe.parent/'resources/engine/mednafen.exe').resolve(),s['enginePath']
        assert len(s['store']['games'])==0
        values={'sound.volume':'72','video.fs':'0','sound':'0'}
        invoke('save_settings',{'scope':None,'values':values,'preferences':{'theme':'light','enginePath':''}})
        s=invoke('load_snapshot')
        assert s['store']['settings']['sound.volume']=='72'
        assert (HOME/'library.json').exists()
        invoke('save_settings',{'scope':None,'values':values,'preferences':None})
        assert (HOME/'library.json.bak').exists()
        try:
            invoke('save_settings',{'scope':None,'values':{'sound.volume':'151'},'preferences':None})
            raise AssertionError('Invalid value accepted')
        except Exception as e:
            assert 'sound.volume' in str(e)
        s=invoke('add_games',{'paths':[str(rom),str(rom),str(FIX/'missing.cue'),str(FIX/'invalid.nes')]})
        assert len(s['games'])==3
        game=next(g for g in s['games'] if g['path'].endswith(rom.name))
        missing=next(g for g in s['games'] if g['path'].endswith('missing.cue'))
        bad=next(g for g in s['games'] if g['path'].endswith('invalid.nes'))
        invoke('save_settings',{'scope':game['id'],'values':{'sound.volume':'63'},'preferences':None})
        try:
            invoke('launch_game',{'id':missing['id']})
            raise AssertionError('Missing track accepted')
        except Exception as e:
            assert 'missing.bin' in str(e)
        try:
            invoke('launch_game',{'id':bad['id']})
            raise AssertionError('Invalid ROM returned success')
        except Exception as e:
            assert 'stopped before' in str(e),str(e)
        invoke('player_fullscreen',{'value':True})
        for _ in range(60):
            status=invoke('load_snapshot')
            if status['running'] is None:
                break
            time.sleep(.2)
        assert status['running'] is None,'Failure path remained locked'
        page.wait_for_timeout(600)
        assert not invoke('player_status')['fullscreen'],'Failed launch left fullscreen enabled'
        error_log=invoke('get_log')
        assert error_log.strip(),'Missing invalid-ROM diagnostic'
        print('Invalid ROM failure recovered',flush=True)
        cfg_file=HOME/'mednafen/mednafen.cfg'
        cfg_file.write_text('sound.volume 12\ncommand.save_state keyboard 0x0 61\n',encoding='utf-8')
        invoke('launch_game',{'id':game['id']})
        time.sleep(2)
        status=invoke('load_snapshot')
        assert status['running']==game['id'],status
        profile=(HOME/'mednafen/play-profile.cfg').read_text(encoding='utf-8')
        assert 'sound.volume 63' in profile,profile
        base=(HOME/'mednafen/mednafen.cfg').read_text(encoding='utf-8')
        assert 'sound.volume 63' in base
        assert 'video.fs 0' in base
        definitions=json.loads((ROOT/'src/data/settings.json').read_text(encoding='utf-8'))
        default_save=next(d['default'] for d in definitions if d['key']=='command.save_state')
        assert 'command.save_state '+default_save+'\n' in base,'Stale base mapping defeated reset'
        children=[c for c in psutil.Process(proc.pid).children(recursive=True) if c.name().lower()=='mednafen.exe']
        assert len(children)==1
        try:
            invoke('save_settings',{'scope':None,'values':{'sound.volume':'50'},'preferences':None})
            raise AssertionError('Settings changed while game running')
        except Exception as e:
            assert 'Stop the game' in str(e)
        user32=ctypes.windll.user32
        callback=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
        assert invoke('player_status')['embedded']
        invoke('stop_game')
        for _ in range(100):
            status=invoke('load_snapshot')
            if status['running'] is None:break
            time.sleep(.1)
        assert status['running'] is None
        assert status['store']['gameSettings'][game['id']]['sound.volume']=='63'
        bios=invoke('check_bios',{'values':{}})
        assert any(b['key']=='psx.bios_jp' and not b['exists'] for b in bios)
        out=HOME/'export.cfg'
        invoke('export_config',{'path':str(out),'values':values})
        imported=invoke('import_config',{'path':str(out)})
        assert imported['values']==values
        invoke('save_appearance',{'language':'vi'})
        page.wait_for_timeout(800)
        page.get_by_role('button',name='Cài đặt',exact=True).click()
        page.get_by_role('button',name='Hình ảnh',exact=True).click()
        expect(page.locator('.info-strip.warning')).to_have_count(0,timeout=5000)
        page.screenshot(path=str(ROOT/'.cache/native-settings.png'),full_page=True)
        page.get_by_role('button',name='Âm thanh',exact=True).click()
        page.locator('[data-setting="sound.volume"] input').fill('71')
        app_handles=[]
        def enum_app(hwnd,lparam):
            pid=ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
            if pid.value==proc.pid and user32.GetWindowTextLengthW(hwnd)>0:app_handles.append(hwnd)
            return True
        user32.EnumWindows(callback(enum_app),0)
        assert app_handles
        user32.PostMessageW(app_handles[0],0x0010,0,0)
        expect(page.get_by_role('dialog',name='Cài đặt chưa được lưu')).to_be_visible()
        page.get_by_role('button',name='Quay lại',exact=True).click()
        page.get_by_role('button',name='Hủy thay đổi',exact=True).click()
        print('Native unsaved-close protection passed',flush=True)
        print(json.dumps({'native':'PASS','engine':s['games'][0]['system'],'launch':'Test ROM, embedded child opened and closed in hidden app','settings':'Global/game overrides, disk persistence, validation, config import/export','missingTracks':'rejected','badRom':'recovered','bios':'missing BIOS reported','testHome':str(HOME)},ensure_ascii=False),flush=True)
        browser.close()
finally:
    try:
        for child in psutil.Process(proc.pid).children(recursive=True):
            try:child.terminate()
            except psutil.Error:pass
    except psutil.Error:pass
    proc.terminate()
    proc.wait(timeout=10)
