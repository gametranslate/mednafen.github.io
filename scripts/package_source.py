"""Archive committed project source plus the verified corresponding Mednafen source."""
from pathlib import Path
import hashlib, io, json, subprocess, zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = json.loads((ROOT/'package.json').read_text())['version']
OUT = ROOT/'release'
OUT.mkdir(exist_ok=True)
UPSTREAM = ROOT/'src-tauri/resources/mednafen-1.32.1.tar.xz'
assert hashlib.sha256(UPSTREAM.read_bytes()).hexdigest() == 'de7eb94ab66212ae7758376524368a8ab208234b33796625ca630547dbc83832'
prefix = f'Mednafen-Play-{VERSION}-source/'
source = subprocess.check_output(['git', 'archive', '--format=zip', 'HEAD'], cwd=ROOT)
allowed = {'.github', 'native', 'public', 'scripts', 'src', 'src-tauri', 'tests'}
with zipfile.ZipFile(io.BytesIO(source)) as original:
    for name in original.namelist():
        parts = Path(name).parts
        assert len(parts) == 1 or parts[0] in allowed, name
        assert not set(parts) & {'.cache', 'target', 'node_modules', 'engine', '__pycache__'}, name
        assert Path(name).suffix.lower() not in {'.wsc', '.rom', '.sav', '.state', '.exe', '.dll'}, name
    target = OUT/f'Mednafen-Play-{VERSION}-source.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for item in original.infolist():
            if not item.is_dir():
                info = zipfile.ZipInfo(prefix+item.filename, item.date_time)
                info.external_attr = item.external_attr
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, original.read(item))
        archive.write(UPSTREAM, prefix+'src-tauri/resources/'+UPSTREAM.name)
print(target.name, target.stat().st_size, hashlib.sha256(target.read_bytes()).hexdigest())
