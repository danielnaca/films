import json, re, sys, os, time, hashlib, urllib.parse, urllib.request, urllib.error, concurrent.futures as cf

KEY = open('/home/claude/cinema/.tmdb_key').read().strip()
data = json.load(open('/home/claude/cinema/data.json'))
OUT = '/home/claude/cinema/posters'
os.makedirs(OUT, exist_ok=True)

def get(url, timeout=20):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'brc/1.0'}), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429: time.sleep(2 + 2*attempt); continue
            if e.code == 404: return None
            raise
    return None

def search(query, year=None):
    q = urllib.parse.quote(query)
    url = f'https://api.themoviedb.org/3/search/movie?api_key={KEY}&query={q}&include_adult=false'
    if year: url += f'&year={year}'
    b = get(url)
    if not b: return []
    return json.loads(b).get('results', [])

def clean(t):
    t = t.split('|')[0]
    t = re.sub(r'\s*\((.*?)\)\s*$', '', t)
    return t.strip(' \'"‘’“”')

def find(title, year, director):
    base = clean(title)
    m = re.search(r'\(([^)]+)\)\s*$', title)
    alt = m.group(1).strip() if m else None
    if not base: return None
    cands = []
    for b in [base] + ([alt] if alt else []):
        if year:
            cands.append((b, year)); cands.append((b, int(year)+1)); cands.append((b, int(year)-1))
        cands.append((b, None))
    for q, y in cands:
        res = search(q, y)
        if not res: continue
        # prefer exact-ish title match with poster
        def score(r):
            t = (r.get('title') or '').lower(); o = (r.get('original_title') or '').lower(); ql = q.lower()
            s = 0
            if ql in (t, o): s += 10
            elif ql in t or ql in o: s += 4
            if r.get('poster_path'): s += 3
            if year and (r.get('release_date') or '')[:4] == str(year): s += 5
            s += min(r.get('popularity', 0), 20) / 20
            return s
        res.sort(key=score, reverse=True)
        r = res[0]
        if r.get('poster_path') and (y is not None or score(r) >= 7):
            return r
    return None

def key(s):
    return hashlib.md5(f"{clean(s['title']).lower()}|{s.get('year') or ''}".encode()).hexdigest()[:10]

uniq = {}
for s in data['screenings']:
    k = key(s)
    if k not in uniq: uniq[k] = s

def work(item):
    k, s = item
    path = f'{OUT}/{k}.jpg'
    try:
        r = find(s['title'], s.get('year'), s.get('director'))
        if not r: return k, None
        if not os.path.exists(path):
            b = get('https://image.tmdb.org/t/p/w185' + r['poster_path'])
            if not b: return k, None
            open(path, 'wb').write(b)
        return k, {'id': r['id'], 'title': r.get('title'), 'year': (r.get('release_date') or '')[:4]}
    except Exception as e:
        print('ERR', s['title'], e, file=sys.stderr); return k, None

prev = json.load(open('/home/claude/cinema/posters.json'))['meta'] if os.path.exists('/home/claude/cinema/posters.json') else {}
results = dict(prev)
todo = [(k, s) for k, s in uniq.items() if k not in prev]
for rnd in range(3):
    with cf.ThreadPoolExecutor(3) as ex:
        for k, r in ex.map(work, todo):
            results[k] = r
    todo = [(k, s) for k, s in todo if not results.get(k)]
    time.sleep(3)
found = {k: v for k, v in results.items() if v}
json.dump({'map': {k: f'posters/{k}.jpg' for k in found}, 'meta': found}, open('/home/claude/cinema/posters.json', 'w'))
print(f'{len(found)}/{len(uniq)} posters found')
print('missing:', [uniq[k]['title'] for k in results if not results[k]])
