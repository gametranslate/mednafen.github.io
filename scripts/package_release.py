"""Package only verified engine resources and explicit project source files."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads((ROOT / 'package.json').read_text())['version']
NAME = f'Mednafen-Play-{VERSION}-windows-x64'
OUT = ROOT / 'release'
OUT.mkdir(exist_ok=True)
ENGINE = ROOT / 'src-tauri/resources/engine'
ARCHIVE = ROOT / '.cache/mednafen-1.32.1-win64.zip'
EXE = ROOT / 'src-tauri/target/release/mednafen-play.exe'
SETUP = ROOT / f'src-tauri/target/release/bundle/nsis/Mednafen Play_{VERSION}_x64-setup.exe'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert digest(ARCHIVE) == '3b680ce6b50a17bcbb2ac611e38962ee469e399b412cc435ffacd6e7f6fb1982'
with zipfile.ZipFile(ARCHIVE) as original:
    engine_files = [n for n in original.namelist() if not n.endswith('/')]
    for name in engine_files:
        assert hashlib.sha256(original.read(name)).hexdigest() == digest(ENGINE / ('SDL2_original.dll' if name=='SDL2.dll' else name)), name
    engine_files += ['SDL2_original.dll']
    manifest=json.loads((ROOT/'src-tauri/resources/HOST-MANIFEST.json').read_text())
    for path,expected in manifest.items():assert digest(ROOT/path)==expected,path
    assert digest(ENGINE/'SDL2.dll')==digest(ROOT/'.cache/host-build/SDL2.dll')
    extras = {p.relative_to(ENGINE).as_posix() for p in ENGINE.rglob('*') if p.is_file()} - set(engine_files)
    assert not extras, f'Remove generated engine files before building: {sorted(extras)}'
SOURCE = ROOT / 'src-tauri/resources/mednafen-1.32.1.tar.xz'
assert digest(SOURCE) == 'de7eb94ab66212ae7758376524368a8ab208234b33796625ca630547dbc83832'
assert EXE.is_file() and SETUP.is_file(), 'Run npm run desktop:build first'

with zipfile.ZipFile(OUT / f'{NAME}.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    z.write(EXE, NAME + '/mednafen-play.exe')
    z.write(ROOT / 'HUONG-DAN.md', NAME + '/HUONG-DAN.md')
    z.write(ROOT / 'PORTS.md', NAME + '/PORTS.md')
    z.write(ROOT / 'VALIDATION.md', NAME + '/VALIDATION.md')
    for name in engine_files:
        z.write(ENGINE / name, NAME + '/resources/engine/' + name)
    for name in ['THIRD-PARTY.txt','SDL-LICENSE.txt','FRONTEND-LICENSES.txt','HOST-MANIFEST.json', SOURCE.name]:
        z.write(ROOT / 'src-tauri/resources' / name, NAME + '/resources/' + name)

shutil.copy2(SETUP, OUT / f'{NAME}-setup.exe')
source_files = ['.gitignore', 'index.html', 'package.json', 'package-lock.json',
                'tsconfig.json', 'vite.config.ts', 'README.md', 'HUONG-DAN.md', 'PORTS.md',
                'src-tauri/Cargo.toml', 'src-tauri/Cargo.lock', 'src-tauri/build.rs',
                'src-tauri/tauri.conf.json', 'src-tauri/resources/THIRD-PARTY.txt', 'src-tauri/resources/SDL-LICENSE.txt', 'src-tauri/resources/FRONTEND-LICENSES.txt', 'src-tauri/resources/HOST-MANIFEST.json']
for folder in ['native', 'src', 'public', 'scripts', 'tests', 'src-tauri/src',
               'src-tauri/icons', 'src-tauri/capabilities']:
    source_files += [p.relative_to(ROOT).as_posix() for p in (ROOT / folder).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts]
if (ROOT / 'VALIDATION.md').exists():
    source_files.append('VALIDATION.md')
with zipfile.ZipFile(OUT / f'Mednafen-Play-{VERSION}-source.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for name in sorted(set(source_files)):
        z.write(ROOT / name, f'Mednafen-Play-{VERSION}-source/' + name)
artifacts = [OUT / f'{NAME}-setup.exe', OUT / f'{NAME}.zip', OUT / f'Mednafen-Play-{VERSION}-source.zip']
(OUT / f'SHA256SUMS-{VERSION}.txt').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in artifacts), encoding='utf-8')
for p in artifacts:
    print(f'{p.name}: {p.stat().st_size:,} bytes')
print('Upstream EXE and renamed SDL verified; separate host adapter verified; no ROMs, BIOS or runtime state packaged.')
