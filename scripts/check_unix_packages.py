"""Validate extracted desktop artifacts; publishable outputs contain no QA files."""
from pathlib import Path
import argparse,hashlib,json,os,platform,plistlib,shutil,subprocess

parser=argparse.ArgumentParser()
parser.add_argument('--skip-game-tests',action='store_true',help='Package only; explicitly records NOT_RUN, never PASS')
args=parser.parse_args()

ROOT=Path(__file__).resolve().parents[1]
VERSION=json.loads((ROOT/'package.json').read_text())['version']
RELEASE=ROOT/'release';RELEASE.mkdir(exist_ok=True)
QA=ROOT/'.cache/unix-package';QA.mkdir(parents=True,exist_ok=True)
BUNDLE=ROOT/'src-tauri/target/release/bundle'
system=platform.system()
arch={'x86_64':'x64','arm64':'arm64','aarch64':'arm64'}[platform.machine()]
env=dict(os.environ,MEDNAFEN_PLAY_TEST_ROM=str(ROOT/'.cache/fixtures/test.wsc'))
if system=='Linux':
    package=next((BUNDLE/'appimage').glob('*.AppImage'))
    subprocess.run([str(package),'--appimage-extract'],cwd=QA,check=True,stdout=subprocess.DEVNULL)
    extracted=QA/'squashfs-root'
    executable=extracted/'AppRun'
    env.update(APPDIR=str(extracted),MEDNAFEN_PLAY_TEST_EXE=str(executable),MEDNAFEN_PLAY_EXPECT_RESOURCE_ROOT=str(extracted),GDK_BACKEND='x11',SDL_VIDEODRIVER='x11')
    command=['xvfb-run','-a','-s','-screen 0 1280x960x24','dbus-run-session','--','python3',str(ROOT/'tests/unix_ui.spec.py')]
    destination=RELEASE/f'Mednafen-Play-{VERSION}-linux-{arch}.AppImage'
else:
    app=next((BUNDLE/'macos').glob('*.app'))
    # Homebrew dependencies can raise the minimum OS above the Rust build target.
    versions=[(13,0)]
    engine=app/'Contents/Resources/resources/engine'
    for path in [engine/'mednafen',*list((engine/'lib').glob('*.dylib'))]:
        text=subprocess.check_output(['otool','-l',str(path)],text=True)
        import re
        for version in re.findall(r'\bminos\s+([\d.]+)',text): versions.append(tuple(map(int,version.split('.'))))
    minimum='.'.join(map(str,max(versions)))
    info=app/'Contents/Info.plist'
    data=plistlib.loads(info.read_bytes());data['LSMinimumSystemVersion']=minimum;info.write_bytes(plistlib.dumps(data))
    subprocess.run(['codesign','--force','--sign','-',str(app)],check=True)
    destination=RELEASE/f'Mednafen-Play-{VERSION}-macos-{arch}.zip'
    subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(app),str(destination)],check=True)
    subprocess.run(['ditto','-x','-k',str(destination),str(QA)],check=True)
    extracted=QA/app.name
    subprocess.run(['codesign','--verify','--deep','--strict',str(extracted)],check=True)
    executable=extracted/'Contents/MacOS/mednafen-play'
    env.update(MEDNAFEN_PLAY_TEST_EXE=str(executable),MEDNAFEN_PLAY_EXPECT_RESOURCE_ROOT=str(extracted))
    command=['python3',str(ROOT/'tests/unix_ui.spec.py')]
manifests=list(extracted.rglob('RUNTIME-MANIFEST.json'))
assert len(manifests)==1,manifests
for name,expected in json.loads(manifests[0].read_text()).items():
    path=manifests[0].parent/name
    assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,'Packager changed engine runtime: '+name
fixture=Path(env['MEDNAFEN_PLAY_TEST_ROM'])
fixture_hash=hashlib.sha256(fixture.read_bytes()).digest() if fixture.is_file() else None
for path in extracted.rglob('*'):
    if not path.is_file():continue
    assert path.suffix.lower() not in {'.wsc','.ws','.rom','.sav','.state','.mc0','.mc1'},'Private game data in package: '+str(path)
    assert path.name not in {'library.json','mednafen.cfg','play-profile.cfg','ui-result.json'},'Profile in package: '+str(path)
    if fixture_hash and path.stat().st_size==fixture.stat().st_size:
        assert hashlib.sha256(path.read_bytes()).digest()!=fixture_hash,'Fixture in package: '+str(path)
if not args.skip_game_tests:
    assert fixture_hash,'Supply .cache/fixtures/test.wsc or explicitly use --skip-game-tests'
    subprocess.run(command,check=True,env=env,cwd=ROOT)
if system=='Linux':shutil.copy2(package,destination);destination.chmod(0o755)
report={'status':'NOT_RUN' if args.skip_game_tests else 'PASS','platform':system,'architecture':arch,'package':destination.name,'bytes':destination.stat().st_size,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'runtimeManifestVerified':True,'testedExtractedPackage':not args.skip_game_tests,'romNotIncluded':True}
if system=='Darwin':report['minimumMacOS']=minimum;report['signing']='ad-hoc';report['notarized']=False
(RELEASE/f'validation-{system.lower()}-{arch}.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
