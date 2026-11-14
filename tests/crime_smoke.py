#!/usr/bin/env python3
"""Smoke test of the crime pipeline on made-up data (no 11labs, no picture search, no generator, no network):
pictures → prep.py → build.py → fonts.py (when FONTSOURCE is set) → preview.py (Remotion stills, needs node_modules and
the fonts) → checks of every item type of the case-file board, and with --still three Remotion frames (a print with
its tapes and the subtitle box, then a ring before and after it is drawn). Uses the channel's language
(prompts/channel.json). Run from the repo root: python3 tests/crime_smoke.py [--still]"""
import json, os, re, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'crime'))
import ff, layout, captions
from channel import LANG

N = '0'
tmp = tempfile.mkdtemp(prefix='crime-smoke-')
job, pub, imgsrc, out = (os.path.join(tmp, d) for d in ('job', 'public', 'imgsrc', 'out'))
voice = os.path.join(pub, 'crime', N, 'voice')
for d in (job, os.path.join(imgsrc, '1'), voice, out): os.makedirs(d)
run = lambda *a: subprocess.run(a, check=True, cwd=ROOT)

# pictures: a landscape street photo, a portrait AI illustration, a landscape newspaper page, an object on white
rng = np.random.RandomState(1)
for name, (w, h) in {'1-1.jpg': (1600, 1200), '2-1.jpg': (1024, 1536), '1-2.jpg': (2000, 1300)}.items():
    yy, xx = np.mgrid[0:h, 0:w]
    a = np.stack([150 + 60 * np.sin(xx / 70.0), 110 + 50 * np.cos(yy / 50.0), 80 + 0 * xx], axis=2) + rng.normal(0, 10, (h, w, 3))
    Image.fromarray(a.clip(0, 255).astype(np.uint8)).save(os.path.join(imgsrc, '1', name), quality=90)
obj = Image.new('RGB', (1024, 1024), (246, 246, 244)); from PIL import ImageDraw
ImageDraw.Draw(obj).polygon([(150, 700), (820, 260), (880, 300), (230, 760)], fill=(60, 60, 64))
ImageDraw.Draw(obj).rectangle((120, 690, 260, 800), fill=(30, 25, 20)); obj.save(os.path.join(imgsrc, '1', '3-1.jpg'), quality=92)
json.dump([{'k': 1, 'query': 'test', 'results': [
    {'title': 'Street.jpg', 'source': 'commons', 'page': 'https://commons.wikimedia.org/wiki/File:Street.jpg', 'license': 'CC BY-SA 4.0', 'artist': 'A', 'date': '1976', 'file': '1-1.jpg'},
    {'title': 'Paper.jpg', 'source': 'europeana', 'page': 'https://www.europeana.eu/item/x', 'license': 'Public domain', 'artist': 'B', 'date': '', 'file': '1-2.jpg'}]},
    {'k': 2, 'query': 'gen: a small bedroom', 'ai': True, 'results': [
    {'title': 'a small bedroom', 'source': 'ai/openai', 'page': '', 'license': 'AI-generated', 'artist': 'AI (openai)', 'ai': True, 'file': '2-1.jpg'}]},
    {'k': 3, 'query': 'gen: a knife', 'ai': True, 'results': [
    {'title': 'a kitchen knife', 'source': 'ai/openai', 'page': '', 'license': 'AI-generated', 'artist': 'AI (openai)', 'ai': True, 'file': '3-1.jpg'}]}],
    open(os.path.join(imgsrc, '1', 'index.json'), 'w'))

# voice: silent lines of known length, with word times for line 2
if LANG == 'ja':
    lines = ['1976年、ドイツで23歳の女性が亡くなった。', '彼女の名前は、アンネリーゼ・ミシェル。', '部屋の壁には、十字架が並んでいた。', 'なぜ誰も止めなかったのか？']
    title = 'アンネリーゼ・ミシェル事件'; w2, w4 = '2/アンネリーゼ', '4/止め'
else:
    lines = ['Im Jahr 1976 starb in Bayern eine 23-jährige Frau.', 'Ihr Name war Anneliese Michel.', 'An den Wänden hingen Kreuze.', 'Warum hat niemand eingegriffen?']
    title = 'Der Fall Anneliese Michel'; w2, w4 = '2/Anneliese', '4/niemand'
durs = [4.2, 2.6, 3.0, 2.4]; rows = []
for i, (t, d) in enumerate(zip(lines, durs), 1):
    f = f'line_{i:02d}.mp3'
    ff.run('-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', str(d), '-c:a', 'libmp3lame', '-q:a', '5', os.path.join(voice, f))
    rows.append({'i': i, 'text': t, 'tts': t, 'voice': 'clone_x', 'file': f, 'duration': round(ff.duration(os.path.join(voice, f)), 3)})
rows[1]['align'] = [[0.0, 0.1], [0.5, 1.6], [1.0, 2.5]]   # the second half of line 2 starts late
json.dump(rows, open(os.path.join(voice, 'lines.json'), 'w', encoding='utf-8'), ensure_ascii=False)

json.dump({'title': title, 'lines': lines, 'queries': ['test'], 'gen': [{'gen': 'a small bedroom'}]},
          open(os.path.join(job, 'script.json'), 'w', encoding='utf-8'), ensure_ascii=False)
json.dump({'images': {'street': {'src': '1/1-1.jpg'}, 'room': {'src': '1/2-1.jpg'}, 'knife': {'src': '1/3-1.jpg', 'look': 'cutout'},
                      'paper': {'src': '1/1-2.jpg', 'look': 'clean', 'blur': [[0.1, 0.1, 0.3, 0.3]]}},
           'scenes': [
               {'at': 1, 'items': [{'photo': 'street', 'pos': 'main'},
                                   {'tape': 'Blut', 'color': 'red', 'pin': 'bl', 'at': 1.3}, {'tape': 'DNA', 'pin': 'br', 'at': 1.4},
                                   {'tape': 'Fingerabdrücke', 'pin': 'bl', 'at': 1.5}, {'tape': '25+ JAHRE', 'color': 'white', 'pin': 'top', 'at': 1.7}]},
               {'at': 2, 'head': {'kicker': 'AKTE 1976', 'title': 'Familie Michel'}},
               {'at': w2, 'items': [{'card': 'paper', 'head': 'NACHT 30./31.12.2000', 'rows': [['Anneliese Michel', '23 J.'], ['Josef M.', '55 J.', 2.6], ['≠', '', 2.7, ]],
                                     'note': {'text': 'im eigenen Haus', 'at': 2.8}, 'stamp': {'text': 'UNGELÖST', 'at': 2.9}}]},
               {'at': 3, 'head': False, 'items': [{'photo': 'street', 'pos': 'g1'}, {'photo': 'paper', 'pos': 'g4', 'at': 3.2}, {'string': [0, 1], 'at': 3.3},
                                                  {'sticker': 'knife', 'pos': 'g5', 'w': 380, 'at': 3.4},
                                                  {'stat': [['130', 'Paare\nin ganz Japan', 3.5], ['12', 'ermittelt', 3.7, 'yellow']], 'xy': [480, 1000]}]},
               {'at': 4, 'items': [{'photo': 'room', 'pos': 'top', 'view': [0.2, 0.1, 0.8, 0.6], 'ring': {'box': [0.3, 0.2, 0.7, 0.4], 'at': w4}},
                                   {'card': 'lined', 'pos': 'bottom', 'rows': [['gegessen', '', 4.2], ['geschlafen', '', 4.4]]},
                                   {'tape': 'Täter?', 'pin': 'tr', 'on': 0}]}]},
          open(os.path.join(job, 'picks.json'), 'w', encoding='utf-8'), ensure_ascii=False)

S = os.path.join(ROOT, 'scripts', 'crime')
run(sys.executable, os.path.join(S, 'prep.py'), os.path.join(job, 'picks.json'), imgsrc, os.path.join(pub, 'crime', N, 'img'))
run(sys.executable, os.path.join(S, 'build.py'), job, pub, N, imgsrc, out)
plan_p = os.path.join(out, 'plan.json')
if os.environ.get('FONTSOURCE'):
    run(sys.executable, os.path.join(S, 'fonts.py'), plan_p, os.environ['FONTSOURCE'], pub)
rend = os.path.join(tmp, 'renders'); os.makedirs(rend)
shutil.copytree(voice, os.path.join(rend, 'voice')); shutil.copytree(imgsrc, os.path.join(rend, 'img'))
run(sys.executable, os.path.join(S, 'preview.py'), job, rend, os.path.join(out, 'preview.jpg'))

plan = json.load(open(plan_p, encoding='utf-8'))
speech = sum(r['duration'] for r in rows)
assert speech + 1 < plan['duration'] < speech + 4, plan['duration']
sc = plan['scenes']
assert len(sc) == 5 and plan['lang'] == LANG and plan['title'] == title
assert sc[0]['s'] == 0 and sc[-1]['e'] == plan['duration'] and all(a['e'] == b['s'] for a, b in zip(sc, sc[1:]))   # no gaps
assert sc[0]['head'] is None and sc[1]['head']['mode'] == 'mid' and sc[2]['head']['mode'] == 'top' and sc[2]['head']['from'] == 'mid'
assert sc[3]['head'] is None and sc[4]['head'] is None                                                   # head: false clears it
ph = sc[0]['items'][0]; assert ph['type'] == 'photo' and not ph['ai'] and ph['credit'] == 'A / CC BY-SA 4.0' and sc[0]['credit'].endswith('A / CC BY-SA 4.0')
inner = (ph['box'][2] - 2 * layout.BORDER) / (ph['box'][3] - 2 * layout.BORDER); v = ph['view']
assert abs((v[2] - v[0]) * ph['w'] / ((v[3] - v[1]) * ph['h']) - inner) < 0.01                          # view fits the print
tp = [i for i in sc[0]['items'] if i['type'] == 'tape']
assert [t_['text'] for t_ in tp] == ['Blut', 'DNA', 'Fingerabdrücke', '25+ JAHRE'] and tp[2]['y'] > tp[0]['y'] and tp[0]['align'] == 'left'
assert all(tp[k]['s'] < tp[k + 1]['s'] for k in range(3)) and tp[1]['x'] > ph['box'][0] + ph['box'][2]   # stacked, timed, right pin
cd = sc[2]['items'][0]; assert cd['type'] == 'card' and cd['rows'][1]['s'] > cd['rows'][0]['s'] and cd['stamp']['s'] > cd['note']['s']
w2t = captions.time_at(captions.anchor(lines[1], w2.split('/')[1], LANG) / captions.weight(lines[1], LANG), rows[1]['duration'], rows[1]['align'])
assert w2t > 0.5 and abs(sc[2]['s'] - (plan['voice'][1]['s'] + w2t - 0.05 - 0.12)) < 0.02                # "2/word" anchor with word times
kinds = [i['type'] for i in sc[3]['items']]; assert kinds[-1] == 'string' and 'sticker' in kinds and 'stat' in kinds
st = next(i for i in sc[3]['items'] if i['type'] == 'string'); g1 = sc[3]['items'][0]['box']
assert st['a'][0] == g1[0] + g1[2] / 2
sk = next(i for i in sc[3]['items'] if i['type'] == 'sticker'); assert sk['ai'] and sk['src'].endswith('.png')
assert Image.open(os.path.join(pub, sk['src'])).mode == 'RGBA' and Image.open(os.path.join(pub, sk['src'])).getextrema()[3][0] == 0   # transparent around
rm = sc[4]['items'][0]; assert rm['ai'] and rm['rings'][0]['s'] > sc[4]['s'] and sc[4]['items'][1]['style'] == 'lined'
tq = sc[4]['items'][2]; assert tq['align'] == 'right' and tq['x'] > rm['box'][0] + rm['box'][2]
subs = plan['subs']
assert all(a['s'] < a['e'] <= b['s'] + 1e-6 for a, b in zip(subs, subs[1:])), 'subtitles overlap'
assert len(subs) >= len(lines) and all(len(c['text']) <= 40 for c in subs), [c['text'] for c in subs]
joined = ('' if LANG == 'ja' else ' ').join(c['text'] for c in subs)
assert joined == ('' if LANG == 'ja' else ' ').join(lines), joined
srt = open(os.path.join(out, 'subtitles.srt'), encoding='utf-8').read(); assert srt.count('-->') == len(lines)
cred = open(os.path.join(out, 'credits.txt'), encoding='utf-8').read()
assert 'Street.jpg' in cred and 'AI' in cred and 'a small bedroom' in cred
src = json.load(open(os.path.join(out, 'sources.json'), encoding='utf-8'))
assert len(src['scenes']) == 5 and any(x.get('ai') for x in src['scenes'][4]['items']) and src['pictures'][0]['page']
assert os.path.getsize(os.path.join(pub, 'crime', N, 'bed.wav')) > 100000 and os.path.exists(os.path.join(pub, 'crime', N, 'bg.jpg'))
assert Image.open(os.path.join(out, 'preview.jpg')).size[0] > 1000
if os.environ.get('FONTSOURCE'):
    plan = json.load(open(plan_p, encoding='utf-8')); assert len(plan['fonts']) >= 4 and all(os.path.exists(os.path.join(pub, f['file'])) for f in plan['fonts'])

if '--still' in sys.argv:
    t1 = sc[0]['e'] - 0.1                    # the print with its four tapes
    t_ring = rm['rings'][0]['s']
    ts = [f'{t1:.2f}', f'{t_ring - 0.3:.2f}', f'{t_ring + 0.7:.2f}']
    run('node', os.path.join(S, 'stills.mjs'), plan_p, pub, os.path.join(out, 'still'), *ts)
    c = np.asarray(Image.open(os.path.join(out, f'still_{ts[0]}.png')).convert('RGB')).astype(int)
    a = np.asarray(Image.open(os.path.join(out, f'still_{ts[1]}.png')).convert('RGB')).astype(int)
    b = np.asarray(Image.open(os.path.join(out, f'still_{ts[2]}.png')).convert('RGB')).astype(int)
    assert a.shape[:2] == (960, 540), a.shape
    assert 10 < c[5:40, 5:60].mean() < 90, 'dark board expected'
    x, y, w, h = [v / 2 for v in ph['box']]
    assert c[int(y + 12):int(y + h - 12), int(x + 12):int(x + w - 12)].std() > 15, 'picture missing'
    yellow = (c[..., 0] > 200) & (c[..., 1] > 170) & (c[..., 2] < 110)
    assert yellow.sum() > 400, 'no yellow tape'
    redt = (c[..., 0] > 150) & (c[..., 1] < 70) & (c[..., 2] < 70)
    assert redt.sum() > 300, 'no red tape'
    sy = int(layout.SUB_Y / 2); band = c[sy - 14:sy + 14]
    assert ((band > 225).all(axis=2)).mean() > 0.05, 'no subtitle box'
    x, y, w, h = [v / 2 for v in rm['box']]
    reg = (slice(int(y), int(y + h)), slice(int(x), int(x + w)))
    assert (np.abs(a[reg] - b[reg]).sum(axis=2) > 80).sum() > 300, 'ring was not drawn'
print(f'crime smoke test OK ({LANG}):', round(plan['duration'], 1), 's,', len(sc), 'scenes,', len(subs), 'subtitles,', tmp)
