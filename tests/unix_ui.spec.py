"""Run the real packaged WebView/engine on a CI desktop or Linux Xvfb.
Only programmatic events inside this test WebView are used. No global input.
The externally supplied ROM is never included in public test artifacts.
"""
from pathlib import Path
import gzip, hashlib, json, os, platform, struct, subprocess, tempfile, time

ROOT=Path(__file__).resolve().parents[1]
EXE=Path(os.environ['MEDNAFEN_PLAY_TEST_EXE']).resolve()
ROM=Path(os.environ['MEDNAFEN_PLAY_TEST_ROM']).resolve()
ROM_SHA='20462e3ad8728b4a12b83bcfc22777c7dc0de1f585e11a9c7cbec04170635e49'
assert hashlib.sha256(ROM.read_bytes()).hexdigest()==ROM_SHA
REPORT=ROOT/'.cache/unix-qa'
REPORT.mkdir(parents=True,exist_ok=True)

def rtc(file):
    raw=file.read_bytes()
    if raw.startswith(b'\x1f\x8b'):raw=gzip.decompress(raw)
    assert raw.startswith(b'MDFNSVST')
    def value(name):
        name=name.encode();marker=bytes([len(name)])+name
        at=raw.index(marker)+len(marker);size=struct.unpack_from('<I',raw,at)[0]
        assert size in [1,2,4,8]
        return int.from_bytes(raw[at+4:at+4+size],'little')
    bcd=lambda n:(n>>4)*10+(n&15)
    return bcd(value('RTC.hour'))*3600+bcd(value('RTC.min'))*60+bcd(value('RTC.sec'))+value('ClockCycleCounter')/3072000

results=[]
for driver in ['softfb','opengl']:
    home=Path(tempfile.mkdtemp(prefix='mp-ui-',dir=ROOT/'.cache'))
    env=dict(os.environ,MEDNAFEN_PLAY_TEST_HOME=str(home),MEDNAFEN_PLAY_QA_SCRIPT=str(ROOT/'tests/unix_ui.js'),MEDNAFEN_PLAY_QA_DRIVER=driver,SDL_AUDIODRIVER='dummy',WEBKIT_DISABLE_DMABUF_RENDERER='1')
    env.pop('MEDNAFEN_PLAY_BACKGROUND_QA',None)
    with (REPORT/f'{driver}-app.log').open('w') as log:
        proc=subprocess.Popen([str(EXE)],env=env,stdout=log,stderr=subprocess.STDOUT)
        try:code=proc.wait(timeout=150)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:proc.wait(timeout=8)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            raise AssertionError('UI test timed out: '+(REPORT/f'{driver}-app.log').read_text()[-3000:])
    assert (home/'ui-result.json').exists(),(code,(REPORT/f'{driver}-app.log').read_text()[-3000:])
    result=json.loads((home/'ui-result.json').read_text())
    (REPORT/f'{driver}-ui.json').write_text(json.dumps(result,indent=2))
    assert result['status']=='PASS',result
    assert code==0,code
    samples={s['label']:s for s in result['samples']}
    rates={}
    for name in ['normal','fast','released','blur']:
        a,b=name+'-start',name+'-end'
        rates[name]=((rtc(home/(b+'.state'))-rtc(home/(a+'.state')))%86400)/(samples[b]['time']-samples[a]['time'])
    assert .6<rates['normal']<1.5,rates
    assert rates['fast']>rates['normal']*2,rates
    assert .6<rates['released']<1.5 and .6<rates['blur']<1.5,rates
    assert (rtc(home/'loaded-slot1.state')-rtc(home/'slot1.state'))%86400<1.6,'Load did not restore saved RTC'
    for pid in [result['pid'],result['replayPid']]:
        try:os.kill(pid,0)
        except ProcessLookupError:pass
        else:raise AssertionError('Emulator process survived close: '+str(pid))
    lifecycle=(home/'lifecycle.log').read_text()
    assert lifecycle.count('Game stopped gracefully.')>=2,lifecycle
    assert 'was terminated' not in lifecycle,lifecycle
    result.update({'rtcRates':rates,'closeCleansEngine':True,'nativeCloseGraceful':True,'romSha256Unchanged':hashlib.sha256(ROM.read_bytes()).hexdigest(),'platform':platform.system(),'architecture':platform.machine()})
    (REPORT/f'{driver}-ui.json').write_text(json.dumps(result,indent=2))
    results.append(result)
    print(driver,'real UI/engine PASS',rates,flush=True)
(REPORT/'results.json').write_text(json.dumps({'status':'PASS','suites':results},indent=2))
