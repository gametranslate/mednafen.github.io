"""Build the SDL window adapter; preserve the upstream DLL unchanged."""
from pathlib import Path
import subprocess, re, shutil, zipfile, hashlib, urllib.request, json
ROOT=Path(__file__).resolve().parents[1]
vswhere=Path(r'C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe')
vs=subprocess.check_output([str(vswhere),'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
VC=Path(vs)/'VC'
archive=ROOT/'.cache/SDL2-2.28.5.zip'
if not archive.exists():urllib.request.urlretrieve('https://github.com/libsdl-org/SDL/releases/download/release-2.28.5/SDL2-2.28.5.zip',archive)
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='97bd14ee0ec67494d2b93f1a4f7da2bf891103c57090d96fdcc2b019d885c76a'
if not (ROOT/'.cache/SDL2-2.28.5/include/SDL.h').is_file():
    with zipfile.ZipFile(archive) as z:z.extractall(ROOT/'.cache')
TOOLS=sorted((VC/'Tools/MSVC').iterdir())[-1]/'bin/Hostx64/x64'
ENGINE=ROOT/'src-tauri/resources/engine'
BUILD=ROOT/'.cache/host-build'
BUILD.mkdir(parents=True,exist_ok=True)
UPSTREAM=ENGINE/'SDL2_original.dll'
assert hashlib.sha256((ROOT/'.cache/mednafen-1.32.1-win64.zip').read_bytes()).hexdigest()=='3b680ce6b50a17bcbb2ac611e38962ee469e399b412cc435ffacd6e7f6fb1982'
with zipfile.ZipFile(ROOT/'.cache/mednafen-1.32.1-win64.zip') as archive:
    UPSTREAM.write_bytes(archive.read('SDL2.dll'))
exports=subprocess.check_output([str(TOOLS/'dumpbin.exe'),'/exports',str(UPSTREAM)],text=True)
names=re.findall(r'^\s+\d+\s+[0-9A-F]+\s+[0-9A-F]+\s+(SDL_\w+)',exports,re.M)
overrides=set(re.findall(r'SDLCALL (SDL_\w+)\(', (ROOT/'native/sdl-host.c').read_text()))
assert overrides and len(names)>500
forward=BUILD/'forwards.c'
forward.write_text('\n'.join('#pragma comment(linker, "/export:'+n+('' if n in overrides else '=SDL2_original.'+n)+'")' for n in names))
script=BUILD/'build.cmd'
script.write_text('@echo off\ncall "'+str(VC/'Auxiliary/Build/vcvars64.bat')+'" >nul\ncl /nologo /LD /O2 /MT /I"'+str(ROOT/'.cache/SDL2-2.28.5/include')+'" "'+str(ROOT/'native/sdl-host.c')+'" "'+str(forward)+'" /link /Brepro /OUT:"'+str(BUILD/'SDL2.dll')+'" user32.lib shell32.lib\n')
subprocess.run(['cmd','/c',str(script)],cwd=BUILD,check=True)
shutil.copy2(BUILD/'SDL2.dll',ENGINE/'SDL2.dll')
shutil.copy2(ROOT/'.cache/SDL2-2.28.5/LICENSE.txt',ROOT/'src-tauri/resources/SDL-LICENSE.txt')
print('Adapter built;',len(names),'SDL exports;',len(overrides),'window functions adapted')

manifest={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['native/sdl-host.c','src-tauri/resources/engine/SDL2.dll','src-tauri/resources/engine/SDL2_original.dll','src-tauri/resources/engine/mednafen.exe']}
(ROOT/'src-tauri/resources/HOST-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
