"""Build the pinned Mednafen source with our Unix display adapter and stage its runtime.

Linux: install build-essential/pkg-config/libsdl2-dev/libflac-dev/zlib1g-dev/libasound2-dev.
macOS: install pkg-config and flac (for example with Homebrew); SDL2 is built below.
Build outputs are isolated from the Windows runtime when --output-root is supplied.
"""
from pathlib import Path
import argparse, hashlib, json, os, platform, re, shlex, shutil, subprocess, sys, tarfile, tempfile, urllib.request

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output-root', type=Path, default=ROOT)
parser.add_argument('--jobs', type=int, default=2)
args = parser.parse_args()
DEST = args.output_root.resolve()
SYSTEM = platform.system()
assert SYSTEM in ['Linux', 'Darwin'], 'Run this script on Linux or macOS'
CACHE = DEST / '.cache/unix-engine'
RES = DEST / 'src-tauri/resources'
ENGINE = RES / 'engine'
for folder in [CACHE, ENGINE]: folder.mkdir(parents=True, exist_ok=True)
assert not (ENGINE / 'mednafen.exe').exists(), 'Use an isolated output root; do not mix Windows and Unix engines'

def run(command, **kwargs):
    print('+', shlex.join(map(str, command)), flush=True)
    subprocess.run(list(map(str, command)), check=True, **kwargs)

def output(command):
    return subprocess.check_output(list(map(str, command)), text=True).strip()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

archive = RES / 'mednafen-1.32.1.tar.xz'
expected = 'de7eb94ab66212ae7758376524368a8ab208234b33796625ca630547dbc83832'
if not archive.exists():
    cached = ROOT / 'src-tauri/resources' / archive.name
    if cached.is_file(): shutil.copy2(cached, archive)
    else: urllib.request.urlretrieve('https://mednafen.github.io/releases/files/' + archive.name, archive)
assert digest(archive) == expected, 'Upstream source SHA-256 mismatch'
SOURCE = CACHE / 'mednafen'
if not (SOURCE/'src/drivers/main.cpp').is_file():
    # Ubuntu 22.04's tarfile backport checks symlinks relative to the archive
    # root, incorrectly rejecting this upstream link. Extract ordinary entries
    # with the data filter, then recreate the one verified, internal symlink.
    with tempfile.TemporaryDirectory(dir=CACHE) as staging:
        with tarfile.open(archive) as tar:
            members = tar.getmembers()
            links = [(m.name, m.linkname) for m in members if m.issym()]
            assert links == [('mednafen/include/mednafen', '../src')], links
            tar.extractall(staging, members=[m for m in members if not m.issym()], filter='data')
        staged = Path(staging)/'mednafen'
        (staged/'include/mednafen').symlink_to('../src', target_is_directory=True)
        if SOURCE.exists(): shutil.rmtree(SOURCE)
        staged.rename(SOURCE)
BUILD = CACHE / ('build-' + platform.machine())
BUILD.mkdir(exist_ok=True)
env = dict(os.environ)
if SYSTEM == 'Darwin':
    env.setdefault('MACOSX_DEPLOYMENT_TARGET', '13.0')
    # Homebrew's sdl2 now resolves to sdl2-compat (with a runtime SDL3 dlopen).
    # Build real SDL2 so the packaged engine has no undeclared SDL3 dependency.
    sdl_archive = CACHE/'SDL2-2.32.10.tar.gz'
    if not sdl_archive.exists():
        urllib.request.urlretrieve('https://github.com/libsdl-org/SDL/releases/download/release-2.32.10/SDL2-2.32.10.tar.gz', sdl_archive)
    assert digest(sdl_archive) == '5f5993c530f084535c65a6879e9b26ad441169b3e25d789d83287040a9ca5165'
    sdl_source = CACHE/'SDL2-2.32.10'
    if not sdl_source.exists():
        with tarfile.open(sdl_archive) as tar: tar.extractall(CACHE, filter='data')
    sdl_build = CACHE/'sdl2-build'
    sdl_build.mkdir(exist_ok=True)
    sdl_prefix = CACHE/'sdl2-runtime'
    if not (sdl_prefix/'lib/libSDL2.dylib').exists():
        run([sdl_source/'configure', '--prefix='+str(sdl_prefix), '--disable-static', '--disable-sdl2-config-rpath'], cwd=sdl_build, env=env)
        run(['make', '-j'+str(max(1,args.jobs))], cwd=sdl_build, env=env)
        run(['make', 'install'], cwd=sdl_build, env=env)
    env['PATH'] = str(sdl_prefix/'bin')+os.pathsep+env['PATH']
    prefixes = [str(sdl_prefix), output(['brew', '--prefix', 'flac'])]
    env['PKG_CONFIG_PATH'] = ':'.join(str(Path(p)/'lib/pkgconfig') for p in prefixes) + ':' + env.get('PKG_CONFIG_PATH', '')
sdl_flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', 'sdl2'], env=env, text=True))
sdl_version = subprocess.check_output(['pkg-config', '--modversion', 'sdl2'], env=env, text=True).strip()
sdk_stamp = BUILD/'sdl-sdk.json'
sdk_identity = json.dumps({'version':sdl_version,'flags':sdl_flags}, sort_keys=True)
if SYSTEM == 'Darwin' and (BUILD/'Makefile').exists() and (not sdk_stamp.exists() or sdk_stamp.read_text()!=sdk_identity):
    # Cached objects compiled against sdl2-compat must not survive switching SDKs.
    run(['make', 'clean'], cwd=BUILD, env=env)
adapter = BUILD / 'sdl-stream.o'
run([env.get('CC', 'cc'), '-O2', '-fPIC', *sdl_flags, '-c', ROOT/'native/sdl-stream.c', '-o', adapter], env=env)
if not (BUILD/'Makefile').exists() or SYSTEM == 'Darwin':
    configure = [SOURCE/'configure', '--disable-dependency-tracking', '--disable-nls', '--disable-jack']
    if SYSTEM == 'Darwin':
        architecture = 'aarch64' if platform.machine() == 'arm64' else platform.machine()
        configure += ['--build=' + architecture + '-apple-darwin' + platform.release()]
    run(configure, cwd=BUILD, env=env)
# The adapter is an executable object, ahead of dynamic SDL. The original core
# source stays intact; SDL symbols are resolved with dlsym(RTLD_NEXT).
configured = re.search(r'^LDFLAGS[ \t]*=[ \t]*(.*)$', (BUILD/'Makefile').read_text(), re.M)
link_flags = (configured[1] + ' ' if configured else '') + str(adapter) + (' -ldl' if SYSTEM == 'Linux' else '')
# LDFLAGS is not a Make dependency: force relinking after recompiling the adapter.
(BUILD/'src/mednafen').unlink(missing_ok=True)
run(['make', '-j' + str(max(1, args.jobs)), 'LDFLAGS=' + link_flags], cwd=BUILD, env=env)
sdk_stamp.write_text(sdk_identity)
executable = ENGINE/'mednafen'
shutil.copy2(BUILD/'src/mednafen', executable)
executable.chmod(0o755)
libs = ENGINE/'lib'
libs.mkdir(exist_ok=True)
if SYSTEM == 'Darwin':
    pending = [(BUILD/'src/mednafen', executable)]
    copied = {}
    basenames = {}
    while pending:
        original, target = pending.pop(0)
        dependencies = [line.strip().split(' (')[0] for line in output(['otool', '-L', original]).splitlines()[1:]]
        for dependency in dependencies:
            if dependency.startswith(('/usr/lib/', '/System/Library/')) or dependency == str(original): continue
            if dependency.startswith('@'):
                if dependency.endswith('/'+original.name): continue
                raise RuntimeError('Unresolved dependency: ' + dependency)
            origin = Path(dependency).resolve()
            assert origin.is_file(), dependency
            destination = libs/origin.name
            if origin not in copied:
                if origin.name in basenames and basenames[origin.name] != origin:
                    raise RuntimeError('Conflicting library basename: '+origin.name)
                basenames[origin.name] = origin
                shutil.copy2(origin,destination);destination.chmod(0o755)
                copied[origin]=destination
                pending.append((origin,destination))
            replacement = '@loader_path/' + ('lib/' if target==executable else '') + destination.name
            run(['install_name_tool','-change',dependency,replacement,target])
        if target!=executable: run(['install_name_tool','-id','@rpath/'+target.name,target])
    for path in [*libs.iterdir(),executable]: run(['codesign','--force','--sign','-',path])
else:
    # Core libraries are supplied by the host/AppImage. Stage codec/SDL libraries
    # beside the engine, and use a relative search path rather than build paths.
    wanted = ('libSDL2','libFLAC','libogg','libz.so','libzstd','libiconv','libcharset')
    for line in output(['ldd',executable]).splitlines():
        match=re.match(r'\s*(\S+)\s+=>\s+(\S+)',line)
        if match and match[1].startswith(wanted):
            source=Path(match[2]);assert source.is_file(),line
            shutil.copy2(source,libs/match[1])
    # Match linuxdeploy's origin fallback in advance so bundling is byte-stable.
    run(['strip','--strip-unneeded',executable])
    run(['patchelf','--set-rpath','$ORIGIN/lib:$ORIGIN',executable])
    for library in libs.iterdir(): run(['patchelf','--set-rpath','$ORIGIN',library])
for name in ['COPYING','ChangeLog']:
    shutil.copy2(SOURCE/name,ENGINE/name)
shutil.copytree(SOURCE/'Documentation',ENGINE/'Documentation',dirs_exist_ok=True)
for name in ['THIRD-PARTY.txt','SDL-LICENSE.txt','FRONTEND-LICENSES.txt']:
    original=ROOT/'src-tauri/resources'/name
    if original.resolve()!=(RES/name).resolve(): shutil.copy2(original,RES/name)
runtime = {p.relative_to(ENGINE).as_posix():digest(p) for p in [executable,*sorted(libs.iterdir())]}
(ENGINE/'RUNTIME-MANIFEST.json').write_text(json.dumps(runtime,sort_keys=True),encoding='utf-8')
manifest={'platform':SYSTEM,'architecture':platform.machine(),'upstreamSourceSha256':expected,
          'adapterSourceSha256':digest(ROOT/'native/sdl-stream.c'),'runtime':runtime,
          'sdlVersion':sdl_version}
(RES/'HOST-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('Unix runtime staged:',ENGINE,flush=True)
run([sys.executable, ROOT/'scripts/generate_settings.py', '--project-root', DEST], env=env)
