#!/usr/bin/env python3
"""Diagnose the picture search: run it once more for a list of queries and log what every archive answered.

Usage: probe_images.py <out_dir> <spec.json> [<old index.json>]

Runs scripts/find_images.py exactly as a normal search (same queries, same limits), with every request watched:
per query and archive the number of hits the archive has, the number it returned, the number left after the
licence filter, the time and any error; every picture download that failed; what was dropped as too small or as a
duplicate. Then, for each free-text query, one more call to Wikimedia Commons with 50 results, to see how many
usable pictures lie beyond the 8 a search keeps. With <old index.json> (the search of the video) the new result
is compared with it, page by page. The spec may hold other queries than the video's (run.py: crime/<N>/probe.json).
→ <out_dir>/probe.json, index.json and the contact sheets sheet_<k>.jpg (the pictures themselves are removed: this
is a diagnosis, the video keeps its own pictures). Never exits with an error: what failed is in probe.json.
"""
import contextlib, io, json, os, re, sys, time, traceback, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import find_images as F

out, spec = sys.argv[1], sys.argv[2]
old_index = sys.argv[3] if len(sys.argv) > 3 else None
queries = json.load(open(spec, encoding='utf-8'))
CUR = {'q': None}
API, DOWN, PER = [], [], {}          # api calls, picture downloads, {(query, source): {...}}
API_HOSTS = ('commons.wikimedia.org', 'api.openverse.org', 'api.europeana.eu', 'www.loc.gov', 'collectionapi.metmuseum.org',
             'api.artic.edu', 'openaccess-api.clevelandart.org')
_get, _js, _search = F.get, F.js, F.search


def get(url, tries=4, raw=True):
    host = urllib.parse.urlsplit(url).netloc
    t0, err = time.time(), ''
    try:
        return _get(url, tries, raw)
    except Exception as e:
        err = f'{type(e).__name__}: {getattr(e, "code", "")} {str(e)[:80]}'.strip()
        raise
    finally:
        (API if host in API_HOSTS else DOWN).append({'q': CUR['q'], 'host': host, 's': round(time.time() - t0, 2), 'err': err})


def js(url):
    commons = url.startswith(F.COMMONS) and 'generator=search' in url
    d = _js(url + ('&gsrinfo=totalhits' if commons else ''))
    host = urllib.parse.urlsplit(url).netloc
    if commons:
        raw = {'total': ((d.get('query') or {}).get('searchinfo') or {}).get('totalhits'), 'returned': len((d.get('query') or {}).get('pages', {}))}
        src = 'commons'
    elif host == 'api.openverse.org':
        raw, src = {'total': d.get('result_count'), 'returned': len(d.get('results', []))}, 'openverse'
    elif host == 'api.europeana.eu':
        raw, src = {'total': d.get('totalResults'), 'returned': len(d.get('items', []))}, 'europeana'
    elif host == 'www.loc.gov' and '/photos/?' in url:
        raw, src = {'total': (d.get('pagination') or {}).get('of'), 'returned': len(d.get('results', []))}, 'loc'
    else:
        return d
    PER.setdefault((CUR['q'], src), {}).update(raw)
    return d


def watched(src, fn):
    def run(q, n):
        t0 = time.time(); rec = PER.setdefault((CUR['q'], src), {})
        try:
            res = fn(q, n); rec['usable'] = len(res); return res
        except Exception as e:
            rec['error'] = f'{type(e).__name__}: {getattr(e, "code", "")} {str(e)[:100]}'.strip(); raise
        finally:
            rec['seconds'] = round(time.time() - t0, 1)
    return run


def search(q, **kw):
    CUR['q'] = q
    return _search(q, **kw)


F.get, F.js, F.search = get, js, search
for s in list(F.FIND):
    F.FIND[s] = watched(s, F.FIND[s])

report = {'started': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()), 'queries': [], 'problems': []}
t0 = time.time(); buf = io.StringIO()
try:
    sys.argv = ['find_images.py', out, '--spec', spec]
    with contextlib.redirect_stdout(buf):
        F.main()
except BaseException as e:   # SystemExit too: the diagnosis goes on with what there is
    report['problems'].append(f'search stopped: {type(e).__name__}: {str(e)[:200]}')
log = buf.getvalue(); print(log)
report['seconds_search'] = round(time.time() - t0)
m = re.search(r'dropped: (\d+) too small, (\d+) duplicates(?:, (\d+) not showing)?', log)
report['dropped'] = {'too_small': int(m.group(1)), 'duplicates': int(m.group(2)), 'not_fitting': int(m.group(3) or 0)} if m else None
report['ranking'] = 'on' if F.Clip.model is not None else 'off'
try: index = json.load(open(f'{out}/index.json', encoding='utf-8'))
except Exception: index = []
old = {}
if old_index and os.path.exists(old_index):
    old = {g['k']: g for g in json.load(open(old_index, encoding='utf-8'))}

# beyond the 8 kept: how many usable pictures Commons has for each free-text query (one call of 50)
CUR['q'] = 'depth'; F.js = _js
for g in index or [{'k': k, 'query': q.get('q', '?') if isinstance(q, dict) else q, 'results': []} for k, q in enumerate(queries, 1)]:
    q = g['query']
    row = {'k': g['k'], 'query': q, 'kept': len(g['results']), 'candidates': g.get('candidates'), 'kept_by_source': {}, 'error': g.get('error'),
           'match': [r['match'] for r in g['results'] if 'match' in r], 'wikidata': g.get('wikidata')}
    for r in g['results']:
        s = r['source'].split('/')[0]; row['kept_by_source'][s] = row['kept_by_source'].get(s, 0) + 1
    row['sources'] = {s: v for (qq, s), v in PER.items() if qq == q}
    if g['k'] in old:
        if old[g['k']]['query'] == q:
            a, b = {r['page'] for r in old[g['k']]['results']}, {r['page'] for r in g['results']}
            row['vs_first_search'] = {'kept_then': len(a), 'same': len(a & b), 'new_now': len(b - a), 'gone_now': len(a - b)}
    if isinstance(q, str) and not q.startswith('File:') and F.source_of(q)[0] not in F.ABOUT:
        term = F.source_of(q)[1]
        try:
            res = F.commons(term, 50)
            big = [r for r in res if not (r.get('width') and r.get('height')) or min(r['width'], r['height']) >= F.MIN_SIDE]
            row['commons_50'] = {'usable': len(res), 'usable_big_enough': len(big)}
        except Exception as e:
            row['commons_50'] = {'error': str(e)[:100]}
        time.sleep(0.5)
    report['queries'].append(row)

if old:
    then, now = {r['page'] for g in old.values() for r in g['results']}, {r['page'] for g in index for r in g['results']}
    report['vs_first_search'] = {'pictures_then': len(then), 'pictures_now': len(now), 'in_both': len(then & now), 'new_now': len(now - then)}
fails = [d for d in DOWN if d['err']]
report['downloads'] = {'tried': len(DOWN), 'failed': len(fails), 'seconds': round(sum(d['s'] for d in DOWN)),
                       'failed_by_host': {h: sum(1 for d in fails if d['host'] == h) for h in sorted({d['host'] for d in fails})},
                       'failed_examples': fails[:12]}
api_fail = [d for d in API if d['err']]
report['api'] = {'calls': len(API), 'failed': len(api_fail), 'seconds': round(sum(d['s'] for d in API)),
                 'calls_by_host': {h: sum(1 for d in API if d['host'] == h) for h in sorted({d['host'] for d in API})},
                 'failed_examples': api_fail[:12]}
report['refused_sources'] = sorted(F.REFUSED)
report['seconds_total'] = round(time.time() - t0)
for f in os.listdir(out) if os.path.isdir(out) else []:   # keep the sheets and the lists, not ~100 full pictures
    if re.match(r'^\d+-\d+\.jpg$', f): os.remove(os.path.join(out, f))
os.makedirs(out, exist_ok=True)
json.dump(report, open(f'{out}/probe.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({k: report.get(k) for k in ('seconds_total', 'ranking', 'dropped', 'vs_first_search', 'downloads', 'api', 'refused_sources', 'problems')}, ensure_ascii=False, indent=1))
