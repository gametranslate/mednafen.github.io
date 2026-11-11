from pathlib import Path
import ctypes,hashlib,json,os,subprocess,sys,time,urllib.request
import psutil
from PIL import Image
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
HOME=ROOT/'.cache'/('background-qa-'+str(time.time_ns()))
HOME.mkdir(parents=True)
ROM=Path(os.environ.get('MEDNAFEN_PLAY_TEST_ROM',sys.argv[1] if len(sys.argv)>1 else ''))
assert ROM.is_file(), 'Set MEDNAFEN_PLAY_TEST_ROM to your Namco Super Wars WSC ROM for this gameplay fixture.'
original_hash=hashlib.sha256(ROM.read_bytes()).hexdigest()
exe=Path(os.environ.get('MEDNAFEN_PLAY_TEST_EXE',str(ROOT/'src-tauri/target/debug/mednafen-play.exe')))
u=ctypes.windll.user32
u.GetPropW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p];u.GetPropW.restype=ctypes.c_void_p
u.SetPropW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_void_p]
u.GetParent.argtypes=[ctypes.c_void_p];u.GetParent.restype=ctypes.c_void_p
u.PostMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
callback=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
frames=HOME/'frame.ppm'
env=dict(os.environ,MEDNAFEN_PLAY_TEST_HOME=str(HOME), WEBVIEW2_USER_DATA_FOLDER=str(HOME/'webview'),MEDNAFEN_PLAY_BACKGROUND_QA='1',MEDNAFEN_PLAY_QA_CAPTURE=str(frames),WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9348 --disable-background-timer-throttling --disable-renderer-backgrounding')
proc=subprocess.Popen([str(exe)],env=env,creationflags=subprocess.CREATE_NO_WINDOW)
print('Background QA',HOME,flush=True)
try:
 for _ in range(150):
  try:urllib.request.urlopen('http://127.0.0.1:9348/json/version',timeout=.3).read();break
  except Exception:time.sleep(.2)
 with sync_playwright() as p:
  browser=p.chromium.connect_over_cdp('http://127.0.0.1:9348');page=browser.contexts[0].pages[0]
  page.wait_for_function('!!window.__TAURI_INTERNALS__',timeout=20000)
  def invoke(cmd,args=None):return page.evaluate('([cmd,args])=>window.__TAURI_INTERNALS__.invoke(cmd,args||{})',[cmd,args])
  handles=[]
  def enum(h,l):
   pid=ctypes.c_ulong();u.GetWindowThreadProcessId(h,ctypes.byref(pid))
   if pid.value==proc.pid:handles.append(h)
   return True
  u.EnumWindows(callback(enum),0)
  parent=next(h for h in handles if u.GetWindowTextLengthW(h)>0)
  assert not u.IsWindowVisible(parent),'QA app must stay hidden'
  store=invoke('add_games',{'paths':[str(ROM)]});game=store['games'][0]
  assert store['preferences']['language']=='en'
  if os.environ.get('MEDNAFEN_PLAY_TEST_EXE'):
   assert Path(invoke('load_snapshot')['enginePath']).resolve()==(exe.parent/'resources/engine/mednafen.exe').resolve()
  for driver in ['opengl','softfb']:
   invoke('save_settings',{'scope':None,'values':{'sound':'0','video.fs':'0','video.driver':driver},'preferences':None})
   page.wait_for_timeout(700)
   page.locator('.play-button').click()
   for _ in range(100):
    if invoke('player_status')['embedded']:break
    time.sleep(.1)
   status=invoke('player_status');assert status['embedded'],(status,invoke('get_log'))
   child=u.GetPropW(parent,'MPChild');assert u.GetParent(child)==parent
   emu=next(ch for ch in psutil.Process(proc.pid).children() if ch.name().lower()=='mednafen.exe')
   external=[]
   def enum_external(h,l):
    pid=ctypes.c_ulong();u.GetWindowThreadProcessId(h,ctypes.byref(pid))
    if pid.value==emu.pid and u.IsWindowVisible(h):external.append(h)
    return True
   u.EnumWindows(callback(enum_external),0);assert not external,'Separate visible game window'
   time.sleep(4)
   for lang in ['en','de','vi','fr','es','it','ko','zh-TW','zh-CN','ja']:
    saved=invoke('save_appearance',{'language':lang,'theme':'dark'})
    assert saved['preferences']['language']==lang
    assert invoke('load_snapshot')['running']==game['id']
   invoke('save_appearance',{'language':'en','theme':'light'});page.wait_for_timeout(600)
   def capture(name):
    frames.unlink(missing_ok=True);u.SetPropW(parent,'MPQACapture',1)
    for _ in range(150):
     try:
      im=Image.open(frames);im.load();break
     except Exception:time.sleep(.1)
    else:raise AssertionError('No framebuffer readback: '+invoke('get_log'))
    im.save(HOME/(name+'.png'))
    colors=im.convert('RGB').getcolors(im.width*im.height)
    assert len(colors)>10,(name,'blank framebuffer',len(colors))
    bbox=im.convert('RGB').getbbox();ratio=(bbox[2]-bbox[0])/(bbox[3]-bbox[1])
    assert abs(ratio-224/144)<.02,(name,'incorrect WonderSwan aspect ratio',ratio)
    assert not u.IsWindowVisible(parent),'QA made the app visible'
    print(driver,name,im.size,len(colors),'colors',flush=True)
    return im
   before=capture(driver+'-embedded')
   u.PostMessageW(child,0x8000+72,91,0)
   page.wait_for_timeout(200);u.PostMessageW(child,0x8000+72,91,1)
   page.wait_for_timeout(1200)
   after=capture(driver+'-input')
   assert before.tobytes()!=after.tobytes(),'SDL button A input did not change the game'
   invoke('player_fullscreen',{'value':True});page.wait_for_timeout(1000)
   assert invoke('player_status')['fullscreen'];assert not page.locator('.app-header').is_visible()
   capture(driver+'-fullscreen')
   u.PostMessageW(child,0x0100,27,0x00010001);u.PostMessageW(child,0x0101,27,0xc0010001)
   page.wait_for_timeout(1000)
   assert not invoke('player_status')['fullscreen'];assert page.locator('.app-header').is_visible()
   assert invoke('load_snapshot')['running']==game['id']
   capture(driver+'-after-esc')
   # Native Alt+Enter message, no system key injection or global focus.
   u.PostMessageW(child,0x0104,13,0x201c0001);page.wait_for_timeout(800)
   assert invoke('player_status')['fullscreen']
   u.PostMessageW(child,0x0100,27,0x00010001);page.wait_for_timeout(800)
   assert not invoke('player_status')['fullscreen']
   page.get_by_role('button',name='Settings',exact=True).click();page.wait_for_timeout(400)
   assert not (u.GetWindowLongW(child,-16)&0x10000000),'Game covers Settings'
   page.get_by_role('button',name='Now playing',exact=True).click();page.wait_for_timeout(400)
   capture(driver+'-returned')
   invoke('player_bounds',{'bounds':{'x':206,'y':130,'width':800,'height':540},'visible':True});page.wait_for_timeout(500)
   resized=capture(driver+'-resized');assert resized.size==(800,540)
   invoke('player_bounds',{'bounds':{'x':206,'y':130,'width':500,'height':700},'visible':True});page.wait_for_timeout(500)
   portrait=capture(driver+'-portrait');assert portrait.size==(500,700)
   invoke('stop_game')
   for _ in range(100):
    if invoke('load_snapshot')['running'] is None:break
    time.sleep(.1)
   assert invoke('load_snapshot')['running'] is None
   page.wait_for_timeout(700)
  assert original_hash==hashlib.sha256(ROM.read_bytes()).hexdigest()
  (HOME/'result.json').write_text(json.dumps({'status':'PASS','romSha256':original_hash,'drivers':['opengl','softfb'],'fullscreenEscPreservesGame':True,'hidden':True},indent=2))
  print('PASS background rendering / fullscreen / Esc / Alt+Enter / navigation / graceful stop; ROM unchanged',flush=True)
  browser.close()
finally:
 try:
  for ch in psutil.Process(proc.pid).children(recursive=True):
   try:ch.terminate()
   except psutil.Error:pass
 except psutil.Error:pass
 proc.terminate();proc.wait(timeout=10)

