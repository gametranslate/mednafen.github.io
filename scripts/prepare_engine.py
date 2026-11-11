from pathlib import Path
import hashlib, urllib.request, zipfile, tarfile, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'src-tauri' / 'resources'
CACHE = ROOT / '.cache'
RES.mkdir(parents=True, exist_ok=True)
CACHE.mkdir(exist_ok=True)
files = {
 'mednafen-1.32.1-win64.zip': '3b680ce6b50a17bcbb2ac611e38962ee469e399b412cc435ffacd6e7f6fb1982',
 'mednafen-1.32.1.tar.xz': 'de7eb94ab66212ae7758376524368a8ab208234b33796625ca630547dbc83832',
}
for name, digest in files.items():
    dest = (CACHE if name.endswith('.zip') else RES) / name
    if not dest.exists():
        urllib.request.urlretrieve('https://mednafen.github.io/releases/files/' + name, dest)
    actual = hashlib.sha256(dest.read_bytes()).hexdigest()
    if actual != digest:
        raise RuntimeError('SHA256 mismatch: ' + name + ' ' + actual)
    print(name, 'SHA256 OK', flush=True)
    if name.endswith('.zip'):
        with zipfile.ZipFile(dest) as archive:
            archive.extractall(RES / 'engine')
    else:
        with tarfile.open(dest) as archive:
            archive.extractall(CACHE, filter='data')
print('Engine and corresponding source prepared.', flush=True)

subprocess.run([sys.executable,str(ROOT/'scripts/build_host.py')],check=True)
