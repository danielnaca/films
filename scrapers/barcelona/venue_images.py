"""Per-venue fallback images for screenings TMDB couldn't match.
Downloads the venue's own still/poster, centre-crops to 2:3, saves as posters/<key>.jpg."""
import json, re, os, io, sys, hashlib, html, urllib.parse, urllib.request, difflib
from PIL import Image

ROOT = '/home/claude/cinema'
OUT = f'{ROOT}/posters'
DL = '/tmp/claude-0/-home-claude/9d105bb5-c22c-584f-abcf-144f5b49121f/scratchpad/dl'
os.makedirs(DL, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh) ArthouseBarcelona/1.0'}

def get(url, timeout=25):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()

def page(url):
    return get(url).decode('utf-8', 'replace')

def clean(t):
    t = t.split('|')[0]; t = re.sub(r'\s*\((.*?)\)\s*$', '', t); return t.strip(' \'"‘’“”')

def key(s):
    return hashlib.md5(f"{clean(s['title']).lower()}|{s.get('year') or ''}".encode()).hexdigest()[:10]

def og_image(url, prefer=None):
    h = page(url)
    imgs = re.findall(r'<meta[^>]+(?:property|name)="(?:og:image|twitter:image)"[^>]+content="([^"]+)"', h)
    imgs += re.findall(r'<meta[^>]+content="([^"]+)"[^>]+(?:property|name)="(?:og:image|twitter:image)"', h)
    imgs = [html.unescape(i) for i in imgs]
    if prefer:
        for i in imgs:
            if re.search(prefer, i): return i
    return imgs[0] if imgs else None

# ---- venue rules -------------------------------------------------------
_filmoteca_index = None
def filmoteca(s):
    """agenda page links /web/ca/film/<slug>; match by title, take the hero img."""
    global _filmoteca_index
    if _filmoteca_index is None:
        h = page('https://www.filmoteca.cat/web/ca/view-agenda-mensual')
        _filmoteca_index = {}
        for m in re.finditer(r'href="(/web/ca/film/[^"]+)"[^>]*>(.*?)</a>', h, re.S):
            txt = re.sub(r'<[^>]+>', ' ', m.group(2)); txt = html.unescape(re.sub(r'\s+', ' ', txt)).strip()
            _filmoteca_index.setdefault(m.group(1), set()).add(txt.lower())
        for m in re.finditer(r'href="(/web/ca/film/[^"]+)"', h):
            _filmoteca_index.setdefault(m.group(1), set())
    want = clean(s.get('aka') or s['title']).lower()
    best, score = None, 0
    for path, texts in _filmoteca_index.items():
        slug = path.rsplit('/', 1)[-1].replace('-', ' ')
        cands = list(texts) + [slug]
        sc = max(difflib.SequenceMatcher(None, want, c).ratio() for c in cands)
        if want in slug or slug in want: sc = max(sc, .9)
        if sc > score: best, score = path, sc
    if score < .6: return None
    h = page('https://www.filmoteca.cat' + best)
    m = re.search(r'<img src="(/web/sites/default/files/styles/subcapcalera[^"]+)"', h)
    return 'https://www.filmoteca.cat' + html.unescape(m.group(1)) if m else None

def phenomena(s):
    h = page(s['url'])
    m = re.search(r'<img[^>]+src="(https://phenomena-experience\.com/imagenes/[^"]+_H\.jpg)"', h)
    if m: return m.group(1)
    m = re.search(r'<img[^>]+src="(https://phenomena-experience\.com/obj/[^"]+\.jpe?g)"', h)
    return m.group(1) if m else None

def girona_verdi(s):
    # bizcochito serves -pos (poster) and -sld (slide): prefer the poster
    return og_image(s['url'], prefer=r'-pos\.')

def generic_og(s):
    return og_image(s['url'])

_inedit_index = None
def inedit(s):
    global _inedit_index
    if '/docs/' in s['url']:
        return og_image(s['url'])
    if _inedit_index is None:
        h = page('https://es.in-edit.org/ca/programacio-2026/')
        _inedit_index = sorted(set(re.findall(r'href="(https://es\.in-edit\.org/ca/docs/[^"]+)"', h)))
    want = clean(s['title']).lower()
    best, score = None, 0
    for u in _inedit_index:
        slug = u.rstrip('/').rsplit('/', 1)[-1]; slug = re.sub(r'-\d+$', '', slug).replace('-', ' ')
        sc = difflib.SequenceMatcher(None, want, slug).ratio()
        if sc > score: best, score = u, sc
    return og_image(best) if score > .55 else None

RULES = {
    'filmoteca': filmoteca, 'phenomena': phenomena, 'girona': girona_verdi, 'verdi': girona_verdi,
    'xcentric': generic_og, 'zumzeig': generic_og, 'institut-francais': generic_og,
    'caixaforum': generic_og, 'mooby-aribau': inedit, 'mooby-arenas': generic_og, 'renoir': None,
}

def crop_save(b, path):
    im = Image.open(io.BytesIO(b)).convert('RGB')
    w, h = im.size
    if w * 3 > h * 2:          # wider than 2:3 → crop sides
        nw = int(h * 2 / 3); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:                      # taller → crop top/bottom
        nh = int(w * 3 / 2); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    im = im.resize((300, 450), Image.LANCZOS)
    im.save(path, 'JPEG', quality=82, optimize=True)

d = json.load(open(f'{ROOT}/data.json'))
done = {}; log = []
for s in d['screenings']:
    if s.get('poster'): continue
    k = key(s)
    if k in done:
        s['poster'] = done[k]; continue
    rule = RULES.get(s['venue_id'])
    img = None
    try:
        if rule: img = rule(s)
        if img:
            if img.startswith('//'): img = 'https:' + img
            if img.startswith('/'): img = urllib.parse.urljoin(s['url'], img)
            img = urllib.parse.quote(img, safe=':/?&=%()$_-.')
            b = get(img)
            if len(b) > 3000:
                crop_save(b, f'{OUT}/{k}.jpg')
                done[k] = f'posters/{k}.jpg'; s['poster'] = done[k]
                log.append(('OK', s['venue_id'], s['title'][:50]))
                continue
    except Exception as e:
        log.append(('ERR', s['venue_id'], s['title'][:50], str(e)[:60])); done[k] = None; continue
    done[k] = None; log.append(('MISS', s['venue_id'], s['title'][:50]))

json.dump(d, open(f'{ROOT}/data.json', 'w'), ensure_ascii=False, separators=(',', ':'))
for l in log: print(*l)
print('with poster:', sum(1 for s in d['screenings'] if s['poster']), '/', len(d['screenings']))
