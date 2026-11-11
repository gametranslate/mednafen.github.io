"""Extract packages without running an installer; test each on a private desktop."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,time,zipfile
ROOT=Path(__file__).resolve().parents[1]
VERSION=json.loads((ROOT/'package.json').read_text())['version']
NAME=f'Mednafen-Play-{VERSION}-windows-x64'
HOME=ROOT/'.cache'/('package-qa-'+str(time.time_ns()));HOME.mkdir()
with zipfile.ZipFile(ROOT/'release'/f'{NAME}.zip') as z:
    assert not any(Path(n).suffix.lower() in ['.wsc','.nes','.sfc','.sav','.mcs'] for n in z.namelist())
    z.extractall(HOME/'zip')
seven=shutil.which('7z') or 'C:/Program Files/7-Zip/7z.exe'
subprocess.run([seven,'x',str(ROOT/'release'/f'{NAME}-setup.exe'),'-o'+str(HOME/'installer'),'-y'],check=True,capture_output=True)
paths={'zip':HOME/'zip'/NAME/'mednafen-play.exe','installer':HOME/'installer/mednafen-play.exe'}
expected_bytes=(ROOT/'src-tauri/target/release/mednafen-play.exe').read_bytes()
expected=hashlib.sha256(expected_bytes).hexdigest()
results={}
for kind,exe in paths.items():
    if os.environ.get('MEDNAFEN_PLAY_PACKAGE_ONLY') not in [None,kind]:
        continue
    actual=exe.read_bytes()
    # Tauri patches exactly the bundle marker for NSIS, restoring UNK in the standalone EXE.
    normalized=actual.replace(b'__TAURI_BUNDLE_TYPE_VAR_NSS',b'__TAURI_BUNDLE_TYPE_VAR_UNK') if kind=='installer' else actual
    assert normalized==expected_bytes,'Executable differs beyond the Tauri NSIS marker'
    manifest=json.loads((exe.parent/'resources/HOST-MANIFEST.json').read_text())
    for name in ['mednafen.exe','SDL2.dll','SDL2_original.dll']:
        assert hashlib.sha256((exe.parent/'resources/engine'/name).read_bytes()).hexdigest()==manifest['src-tauri/resources/engine/'+name]
    results[kind]={'exeSha256':hashlib.sha256(actual).hexdigest()}
    for suite in ['session','startup','clipping','keyboard']:
        env=dict(os.environ,PYTHONUTF8='1',MEDNAFEN_PLAY_TEST_EXE=str(exe))
        run=subprocess.run(['python',str(ROOT/'tests'/f'{suite}.spec.py')],cwd=ROOT,env=env,text=True,encoding='utf-8',capture_output=True)
        (HOME/f'{kind}-{suite}.log').write_text(run.stdout+'\n'+run.stderr,encoding='utf-8')
        print(kind,suite,'PASS' if run.returncode==0 else 'FAIL',flush=True)
        if run.returncode:raise RuntimeError(run.stdout+'\n'+run.stderr)
        results[kind][suite]='PASS'
(HOME/'results.json').write_text(json.dumps({'version':VERSION,'paths':{k:str(v) for k,v in paths.items()},'results':results,'exeSha256':expected},indent=2))
(ROOT/'.cache'/f'package-qa-paths-{VERSION}.json').write_text(json.dumps({'home':str(HOME),'paths':{k:str(v) for k,v in paths.items()}},indent=2))
print('Package checks passed:',HOME,flush=True)
