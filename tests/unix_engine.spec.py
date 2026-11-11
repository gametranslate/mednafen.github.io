"""Exercise the native adapter with the authorized ROM and a private socket."""
from pathlib import Path
import gzip,hashlib,json,os,socket,struct,subprocess,tempfile,threading,time
ROOT=Path(__file__).resolve().parents[1]
EXE=Path(os.environ['MEDNAFEN_PLAY_ENGINE'])
ROM=Path(os.environ['MEDNAFEN_PLAY_TEST_ROM'])
assert hashlib.sha256(ROM.read_bytes()).hexdigest()=='20462e3ad8728b4a12b83bcfc22777c7dc0de1f585e11a9c7cbec04170635e49'
REPORT=ROOT/'.cache/unix-engine-qa';REPORT.mkdir(parents=True,exist_ok=True)
def exact(stream,count):
    result=bytearray()
    while len(result)<count:
        piece=stream.recv(count-len(result))
        if not piece:raise EOFError()
        result.extend(piece)
    return bytes(result)
for driver in ['softfb','opengl']:
    with tempfile.TemporaryDirectory(prefix='mp-engine-',dir='/tmp') as directory:
        home=Path(directory);server=socket.socket(socket.AF_UNIX);server.bind(str(home/'display'));server.listen();server.settimeout(20)
        settings=json.loads((ROOT/'src/data/input-defaults.json').read_text())
        settings.update({'sound':'1','sound.driver':'sdl','sound.volume':'100','video.driver':driver,'video.glvsync':'0','filesys.state_comp_level':'0','wswan.xscale':'2','wswan.yscale':'2'})
        config=home/'profile.cfg';config.write_text('\n'.join(k+' '+v for k,v in settings.items())+'\n')
        # SDL's disk backend exercises actual PCM production without playing
        # through the user's speakers. The private raw file is never uploaded.
        audio=home/'audio.raw'
        env=dict(os.environ,MEDNAFEN_HOME=str(home),MEDNAFEN_NOPOPUPS='1',MEDNAFEN_PLAY_SOCKET=str(home/'display'),SDL_MAC_BACKGROUND_APP='1',SDL_AUDIODRIVER='disk',SDL_DISKAUDIOFILE=str(audio))
        state={'frames':0,'colors':0,'error':None}
        with (REPORT/f'{driver}.log').open('w') as log:
            process=subprocess.Popen([str(EXE),'-ovconfig',str(config),str(ROM)],env=env,stdout=log,stderr=subprocess.STDOUT)
            client=None
            try:
                client,_=server.accept();hello=exact(client,8);assert hello[:4]==b'MPH1' and struct.unpack_from('<I',hello,4)[0]==process.pid
                def read():
                    try:
                        while True:
                            header=exact(client,24);magic,w,h,length,frame=struct.unpack('<4sIIIQ',header)
                            assert magic==b'MPF1' and 0<w<=4096 and 0<h<=4096 and length==w*h*4
                            pixels=exact(client,length);state['frames']=frame
                            state['colors']=max(state['colors'],len({pixels[i:i+3] for i in range(0,len(pixels),4)}))
                    except EOFError:pass
                    except Exception as error:state['error']=repr(error)
                reader=threading.Thread(target=read,daemon=True);reader.start()
                def wait(test,label):
                    end=time.monotonic()+20
                    while time.monotonic()<end:
                        if test():return
                        if process.poll() is not None:break
                        time.sleep(.05)
                    raise AssertionError(label+' '+str(state)+'\n'+(REPORT/f'{driver}.log').read_text()[-2000:])
                def command(kind,code=0,flags=0):client.sendall(struct.pack('<4I',kind,code,flags,0))
                def key(code):command(1,code,1);time.sleep(.12);command(1,code,0);time.sleep(.12)
                wait(lambda:state['colors']>4,'No game frame')
                wait(lambda:audio.exists() and audio.stat().st_size>48000 and len(set(audio.read_bytes()))>8,'No non-silent game audio')
                key(58)
                wait(lambda:list((home/'mcs').glob('*.mc0')),'F1 did not save')
                key(60);key(58);wait(lambda:list((home/'mcs').glob('*.mc1')),'F3/F1 slot 1')
                key(59);command(3);assert process.wait(timeout=8)==0
                reader.join(timeout=3);assert not state['error'],state
                pcm=audio.read_bytes()
                state.update({'status':'PASS','driver':driver,'saveLoadSlots':True,'gracefulStop':True,'audioBytes':len(pcm),'audioNonzeroBytes':sum(b!=0 for b in pcm)})
                (REPORT/f'{driver}.json').write_text(json.dumps(state,indent=2));print(driver,state,flush=True)
            finally:
                if process.poll() is None:process.terminate();process.wait(timeout=5)
                if client:client.close()
                server.close()
