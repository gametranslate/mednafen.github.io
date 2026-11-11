from pathlib import Path
import re, json, os, shutil, subprocess
ROOT = Path(__file__).resolve().parents[1]
cache = ROOT / '.cache'
engine = ROOT / 'src-tauri/resources/engine'
runtime = cache / 'schema-engine'
runtime.mkdir(parents=True, exist_ok=True)
# Windows Mednafen writes stdout/stderr beside its executable. Keep generated
# files in the cache instead of contaminating the distribution resources.
for binary in [engine / 'mednafen.exe', *engine.glob('*.dll')]:
    shutil.copy2(binary, runtime / binary.name)
dump = cache / 'settings.def'
home = cache / 'schema-home'
home.mkdir(exist_ok=True)
env = dict(os.environ, MEDNAFEN_HOME=str(home), MEDNAFEN_NOPOPUPS='1')
dump.unlink(missing_ok=True)
# Mednafen returns -1 after successfully handling dump-only commands (main.cpp).
result = subprocess.run([str(runtime / 'mednafen.exe'), '-dump_settings_def', str(dump)], env=env, cwd=home,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
if not dump.exists():
    raise RuntimeError('Settings export failed: ' + str(result.returncode))
lines = dump.read_text(encoding='utf-8').splitlines()
def unescape(s):
    s = s.replace(r'\005', '').replace(r'\n', '\n').replace(r'\t', ' ').replace(r'\"', '"').replace(r"\'", "'")
    return s.strip()
items = []
i = 0
while i < len(lines):
    key, flags, desc, extra, kind, default, minimum, maximum = lines[i:i+8]
    i += 8
    n = int(lines[i]); i += 1
    options = []
    for _ in range(n):
        value, label, help_text = lines[i:i+3]; i += 3
        options.append({'value': value, 'label': unescape(label) or value, 'description': unescape(help_text)})
    n = int(lines[i]); i += 1
    aliases = lines[i:i+n]; i += n
    items.append({'key':key,'flags':flags.split(),'description':unescape(desc),'help':unescape(extra),'type':kind.replace('MDFNST_','').lower(),'default':default,'min':minimum,'max':maximum,'options':options,'aliases':aliases})
target = ROOT / 'src/data/settings.json'
target.write_text(json.dumps(items,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'{len(items)} settings exported to {target.name}; {target.stat().st_size} bytes')
lookup = {x['key']:x for x in items}
for key in ['video.fs','sound.volume','video.driver','video.glvsync','nes.stretch','nes.videoip','ffspeed','srwframes','ss.bios_jp','ss.bios_na_eu']:
    x=lookup.get(key)
    print(json.dumps(x,ensure_ascii=False))
