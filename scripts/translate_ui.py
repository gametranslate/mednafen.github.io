"""Build-time machine translations of static UI copy; runtime uses local JSON.
No library paths, game content, user data or settings are sent for translation.
Review generated wording before release; existing translations are preserved.
"""
from pathlib import Path
import concurrent.futures,json,re,time,urllib.request,urllib.parse
ROOT=Path(__file__).resolve().parents[1]
KEYS=json.loads((ROOT/'scripts/ui-messages.json').read_text(encoding='utf-8'))
OUT=ROOT/'src/locales'
def request(text,source,target):
    url='https://translate.googleapis.com/translate_a/single?'+urllib.parse.urlencode({'client':'gtx','sl':source,'tl':target,'dt':'t','q':text})
    for attempt in range(5):
        try:
            data=json.loads(urllib.request.urlopen(url,timeout=30).read())
            return ''.join(s[0] for s in data[0] if s[0])
        except Exception:
            if attempt==4:raise
            time.sleep(2+attempt*2)
def translate(lang,english=None):
    path=OUT/(lang+'.json');data=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    pending=[]
    for key in KEYS:
        if data.get(key,'').strip():continue
        is_vi=bool(re.search('[À-ỹĐđ]',key))
        if lang=='en' and not is_vi or lang=='vi' and is_vi:data[key]=key
        else:pending.append(key)
    batch=[];size=0
    def send(items):
        texts=[english[k] if english else k for k in items]
        result=request(' ||| '.join(texts),'en' if english else 'auto',lang)
        parts=re.split(r'\s*[|｜]\s*[|｜]\s*[|｜]\s*',result)
        if len(parts)!=len(items) or any(not part.strip() for part in parts):
            parts=[request(x,'en' if english else 'auto',lang) for x in texts]
        for key,value in zip(items,parts):data[key]=value.strip()
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        print(lang, len(data), 'translated',flush=True)
    for key in pending:
        value=english[key] if english else key
        if batch and size+len(value)>1400:send(batch);batch=[];size=0
        batch.append(key);size+=len(value)+5
    if batch:send(batch)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(lang,len(data),'messages',flush=True)
    return data
en=translate('en')
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    futures=[pool.submit(translate,lang,en) for lang in ['de','vi','fr','es','it','ko','zh-TW','zh-CN','ja']]
    for f in futures:f.result()
