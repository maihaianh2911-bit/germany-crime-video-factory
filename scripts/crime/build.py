#!/usr/bin/env python3
"""Plan of a case-file video for the CrimeV composition, plus music bed, subtitles and picture credits.

Usage: build.py <job_dir crime/N> <public_dir> <N> <img_src_dir> <out_dir>
Reads <job_dir>/script.json (title, lines), <job_dir>/picks.json (images, scenes), <public_dir>/crime/<N>/voice/
lines.json (measured line lengths, Whisper word times) and the prepared pictures in <public_dir>/crime/<N>/img/.
Writes <out_dir>/plan.json, subtitles.srt, credits.txt, sources.json, edits.md and <public_dir>/crime/<N>/bed.wav, bg.jpg.

Timing: every line starts after the previous one plus a pause (0.4 s after a sentence end, 0.22 s otherwise). A
scene starts at its "at" and lasts until the next one (hard cuts); inside it every item appears at its own "at".
"at" is a line number (fractional = part-way through the line) or "<line>/<word>": the moment that word is spoken
(Whisper word times; German: the first word of the line starting with it, Japanese: the first occurrence).
The subtitles are pieces of up to ~38 characters (captions.subs), each shown while it is spoken.
Positions: scripts/crime/layout.py. The format of picks.json is described in AGENT_CRIME.md §2. A scene with
"edit": "<name>" first gets the places of that scene edit (scripts/crime/edits.py, the catalogue); <out_dir>/edits.md
lists every scene with its edit and Claude's "why" for the owner.
"""
import json, os, re, sys
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import music_gen as mg
import layout as L
import captions as C
import edits as E
import prep
import sfx as SFX
from channel import LANG, AI_TAG

job, pub, N, imgsrc, out = sys.argv[1:6]
base = f'crime/{N}'
spec = json.load(open(f'{job}/script.json', encoding='utf-8'))
picks = json.load(open(f'{job}/picks.json', encoding='utf-8'))
lines = json.load(open(f'{pub}/{base}/voice/lines.json', encoding='utf-8'))
dur = {r['i']: r['duration'] for r in lines}
text = {r['i']: r['text'] for r in lines}
align = {r['i']: r.get('align') or [] for r in lines}
os.makedirs(out, exist_ok=True)
END = ('。', '」', '？', '！', '.', '?', '!', '"', '“', '”', '»')
FONTS = json.load(open(os.path.join(HERE, 'fonts.json'), encoding='utf-8'))[LANG]['roles']
CREDIT_PFX = {'de': 'Foto: ', 'ja': '写真: '}[LANG]


def fail(msg):
    raise SystemExit(f'picks.json: {msg}')


# ---- index of every searched / generated picture (licences, authors, AI flag)
idx = {}
for rnd in sorted(os.listdir(imgsrc)) if os.path.isdir(imgsrc) else []:
    ip = os.path.join(imgsrc, rnd, 'index.json')
    if os.path.exists(ip):
        for q in json.load(open(ip, encoding='utf-8')):
            for r in q['results']:
                if r.get('file'): idx[f"{rnd}/{r['file']}"] = r


def image(name):
    if name not in picks['images']: fail(f'không có ảnh "{name}" trong "images"')
    return picks['images'][name]


def is_ai(name):
    it = image(name)
    return bool(it.get('ai', (idx.get(it['src']) or {}).get('ai', False)))


size = {}
def img_file(name):
    f = prep.out_name(name, image(name))
    if f not in size: size[f] = Image.open(f'{pub}/{base}/img/{f}').size
    return f, size[f]


def credit_of(name):
    if is_ai(name): return ''
    it = image(name); r = idx.get(it['src']) or {}
    artist = re.sub(r'\s+', ' ', it.get('artist') or r.get('artist') or '').strip()[:50]
    if LANG != 'ja' and any(ord(c) > 0x2000 for c in artist):   # the German fonts have no Japanese: the full name is in credits.txt
        artist = {'commons': 'Wikimedia Commons'}.get(r.get('source', ''), r.get('source', '').split('/')[-1].capitalize() or 'unbekannt')
    return ' / '.join(x for x in (artist,
                                  it.get('license') or r.get('license') or '') if x)


# ---- voice timeline and subtitles
# before the first line / after the last one: "lead" leaves room for a hook card, "tail" for a closing card
LEAD, TAIL = float(picks.get('lead', 0.3)), float(picks.get('tail', 1.8))
t = LEAD; starts = {}; subs = []; voice = []; srt = []
for i in range(1, len(lines) + 1):
    starts[i] = t
    voice.append({'s': round(t, 3), 'src': f'{base}/voice/{lines[i - 1]["file"]}'})
    total_w = C.weight(text[i], LANG)
    for txt, before in C.subs(text[i], LANG):
        cs = t + C.time_at(before / total_w, dur[i], align[i]) - 0.08
        subs.append({'s': round(max(0, cs), 3), 'e': round(t + dur[i] + 0.3, 3), 'text': txt, 'line': i})
    srt.append({'s': round(t, 3), 'e': round(t + dur[i], 3), 'text': text[i]})
    t += dur[i] + (0.4 if text[i].rstrip().endswith(END) else 0.22)
total = round(t - 0.22 + TAIL, 3)
for x, y in zip(subs, subs[1:]):   # a piece stays until the next one, or a moment after its line ends
    x['e'] = round(min(y['s'], x['e']) if y['line'] != x['line'] else y['s'], 3)
subs[-1]['e'] = round(min(total - 0.3, subs[-1]['e'] + 0.5), 3)
subs = [c for c in subs if c['e'] - c['s'] > 0.05]
for x, y in zip(srt, srt[1:]): x['e'] = round(min(y['s'], x['e'] + 0.5), 3)


def at_time(a, what='"at"'):
    """Moment of an "at": a line number (fractional = part-way through the line) or "<line>/<word>"."""
    if isinstance(a, str) and '/' in a:
        ln, word = a.split('/', 1)
        try: k = int(ln)
        except ValueError: fail(f'{what} "{a}": phải là "số câu/từ", ví dụ "3/Blut"')
        if k not in starts: fail(f'{what} "{a}": không có câu {k}')
        before = C.anchor(text[k], word.strip(), LANG)
        if before is None: fail(f'{what} "{a}": không thấy từ "{word}" trong câu {k}: {text[k]}')
        return starts[k] + C.time_at(before / C.weight(text[k], LANG), dur[k], align[k]) - 0.05
    try: li = float(a)
    except (TypeError, ValueError): fail(f'{what} {a!r}: phải là số câu (3, 3.5) hoặc "3/Wort"')
    k = int(li); k = min(max(starts), max(min(starts), k))
    return starts[k] + (li - int(li)) * dur[k]


# ---- scenes
scenes_in = picks.get('scenes') or fail('chưa có "scenes"')
bounds = [0.0] + [at_time(sc.get('at', 1), f'cảnh {j + 2} "at"') - 0.12 for j, sc in enumerate(scenes_in[1:])] + [total]
scenes, head, prev_head = [], None, None
used_imgs = []
for j, sc in enumerate(scenes_in):
    s, e = bounds[j], bounds[j + 1]
    sc = E.apply(sc, j + 1, fail)   # "edit": the template's places for what Claude left out; untouched without it
    if e - s < 0.8: fail(f'cảnh {j + 1} ("at" {sc.get("at")}): chỉ hiện {e - s:.2f} s (kiểm tra "at")')
    if 'head' in sc:
        h = sc['head']
        head = ({'kicker': h.get('kicker', ''), 'title': h.get('title', '')} if isinstance(h, dict) else
                {'kicker': h[0], 'title': h[1] if len(h) > 1 else ''} if isinstance(h, list) and h else None)
    items_in = sc.get('items') or []
    mode = 'mid' if head and not items_in else 'top'
    hd = None
    if head:
        same = prev_head and prev_head['kicker'] == head['kicker'] and prev_head['title'] == head['title']
        hd = {**head, 'mode': mode, 'from': prev_head['mode'] if same else None, 's': round(s, 3)}
    prev_head = hd
    top = bool(hd and mode == 'top')

    def when(it, key='at', dflt=None):
        v = it.get(key)
        return round(min(e - 0.25, max(s, at_time(v, f'cảnh {j + 1} "{key}"'))), 3) if v is not None else dflt

    items, boxes, pins, last_box, last_card = [], [], {}, None, None
    for k, it in enumerate(items_in):
        ts = when(it, 'at', round(s, 3)); te = when(it, 'out')
        it_out = {'s': ts, **({'e': te} if te else {})}
        box = None
        if 'photo' in it or 'sticker' in it:
            kind = 'photo' if 'photo' in it else 'sticker'
            name = it[kind]; f, (w, h) = img_file(name); used_imgs.append(name)
            view = it.get('view') or [0, 0, 1, 1]
            vasp = (view[2] - view[0]) * w / ((view[3] - view[1]) * h)
            asp = L.aspect_of(it['aspect']) if it.get('aspect') else (L.clamp_aspect(vasp) if kind == 'photo' else w / h)
            pos = it.get('pos', 'main' if kind == 'photo' else 'center')
            if pos == 'in':
                if not last_card: fail(f'cảnh {j + 1} mục {k + 1}: "pos": "in" cần một card "folder" phía trước')
                box = L.in_card(last_card, asp)
            elif pos == 'full' and kind == 'photo':   # the whole frame, no border: a quiet moment
                box = [0, 0, L.W, L.H]
            else:
                box = L.place(pos, asp, top, it.get('w'))
            o = {'type': kind, 'src': f'{base}/img/{f}', 'w': w, 'h': h, 'box': box, 'ai': is_ai(name),
                 'rot': it.get('rot', L.rot_of(name, k, 4, 14) if kind == 'sticker' else L.rot_of(name, k)), 'credit': credit_of(name)}
            if kind == 'photo' and pos == 'full':
                o['bleed'] = True; o['rot'] = 0
            if kind == 'photo':
                bas = (box[2] / box[3]) if o.get('bleed') else (box[2] - 2 * L.BORDER) / (box[3] - 2 * L.BORDER)
                o['view'] = L.fit_view(view, bas, w, h)
                o['drift'] = 0 if it.get('still') else it.get('drift', 0.1)
                z = it.get('zoom')
                if z:
                    zs = at_time(z['at']) if z.get('at') else ts + 0.4
                    o['zoom'] = {'to': L.fit_view(z['to'], bas, w, h), 's': round(zs, 3), 'e': round(zs + z.get('dur', 1.6), 3)}
                    o['drift'] = 0
                rings = it.get('rings') or ([it['ring']] if it.get('ring') else [])
                o['rings'] = [{'s': when(r, 'at', ts), 'box': r['box'], 'shape': r.get('shape', 'ellipse'),
                               'color': r.get('color', 'yellow')} for r in rings]
            last_box = box
        elif 'card' in it:
            style = it['card']
            if style not in ('paper', 'lined', 'folder'): fail(f'cảnh {j + 1}: "card" phải là paper, lined hoặc folder')
            box = L.card_box(it.get('pos', 'main'), top, it.get('h'))
            rows = []
            for r in it.get('rows') or []:
                if isinstance(r, str): r = {'l': r}
                elif isinstance(r, list): r = {'l': r[0], 'r': r[1] if len(r) > 1 else '', **({'at': r[2]} if len(r) > 2 else {})}
                rows.append({'l': r.get('l', ''), 'r': r.get('r', ''), 's': when(r, 'at', ts), 'color': r.get('color', '')})
            note = it.get('note'); stamp = it.get('stamp')
            note = note if isinstance(note, dict) else ({'text': note} if note else None)
            stamp = stamp if isinstance(stamp, dict) else ({'text': stamp} if stamp else None)
            need = (160 if it.get('head') else 50) + len(rows) * L.ROW_H.get(style, 96) + (140 if note else 0)
            if style != 'folder' and need > box[3] + 1:
                fail(f'cảnh {j + 1}: card có {len(rows)} dòng, cần cao {need} px nhưng card chỉ cao {box[3]:.0f} px (bớt dòng hoặc "pos": "main")')
            o = {'type': 'card', 'style': style, 'box': box, 'rot': it.get('rot', L.rot_of(style, k, 0.3, 1.2)),
                 'head': it.get('head', ''), 'rows': rows, 'tab': it.get('tab', ''), 'corner': it.get('corner', ''),
                 'note': {'text': note['text'], 's': when(note, 'at', ts)} if note else None,
                 'stamp': {'text': stamp['text'], 's': when(stamp, 'at', ts)} if stamp else None}
            last_box = last_card = box
        elif 'tape' in it:
            color = it.get('color', 'yellow')
            if color not in L.TAPE_PX: fail(f'cảnh {j + 1}: tape "color" phải là yellow, red hoặc white')
            px = it.get('size') or round(L.TAPE_PX[color] * (1.45 if it.get('big') else 1) * float(picks.get('tape_scale', 1)))
            # never wider than the frame: an estimate of the strip's width (glyph widths of the three tape fonts)
            est = len(it['tape']) * px * {'red': 0.56, 'white': 0.62, 'yellow': 0.47}[color] + 0.75 * px
            if est > 960: px = int(px * 960 / est)
            if it.get('xy'):
                x, y = it['xy']; al = it.get('align', 'center')
            else:
                tgt = boxes[it['on']] if isinstance(it.get('on'), int) and it['on'] < len(boxes) and boxes[it['on']] else last_box
                where = it.get('pin', 'bottom' if tgt else 'center')
                if not tgt:
                    a0, a1 = L.area(top); tgt = [60, a0, L.W - 120, a1 - a0]
                key = (tuple(tgt), where); n = pins.get(key, 0); pins[key] = n + 1
                x, y, al = L.pin(tgt, where, n, px)
            o = {'type': 'tape', 'text': it['tape'], 'color': color, 'px': px, 'x': x, 'y': y, 'align': al,
                 'rot': it.get('rot', L.rot_of(it['tape'], k, 0.5, 3.5))}
        elif 'stat' in it:
            rows = []
            for r in it['stat']:
                if isinstance(r, list): r = {'n': r[0], 'text': r[1] if len(r) > 1 else '', **({'at': r[2]} if len(r) > 2 else {}), **({'color': r[3]} if len(r) > 3 else {})}
                rows.append({'n': str(r['n']), 'text': r.get('text', ''), 's': when(r, 'at', ts), 'color': r.get('color', 'white')})
            a0, a1 = L.area(top)
            x, y = it.get('xy') or [110, (last_box[1] + last_box[3] + 60) if last_box else a0 + 60]
            if y + len(rows) * L.STAT_ROW > a1 + 40: fail(f'cảnh {j + 1}: "stat" tràn xuống dưới (đặt ảnh nhỏ hơn hoặc "xy")')
            o = {'type': 'stat', 'x': x, 'y': y, 'rows': rows}
            box = [x, y, 860, len(rows) * L.STAT_ROW]
        elif 'string' in it:
            a, b = it['string']
            if not all(isinstance(q, int) and q < len(boxes) and boxes[q] for q in (a, b)):
                fail(f'cảnh {j + 1}: "string" {it["string"]} phải nối hai mục có khung (ảnh, sticker, card) đứng trước nó')
            o = {'type': 'string', 'a': L.string_end(boxes[a]), 'b': L.string_end(boxes[b])}
        else:
            fail(f'cảnh {j + 1} mục {k + 1}: không rõ loại (photo, sticker, tape, card, stat, string)')
        boxes.append(box if box is not None and o['type'] != 'tape' else None)
        items.append({**o, **it_out})
    # strings are pinned on top of the prints
    items = [x for x in items if x['type'] != 'string'] + [x for x in items if x['type'] == 'string']
    cred = []
    for x in items:
        if x.get('credit') and x['credit'] not in cred: cred.append(x['credit'])
    scenes.append({'s': round(s, 3), 'e': round(e, 3), 'scene': j + 1, 'head': hd, 'items': items, **({'hush': True} if sc.get('hush') else {}),
                   'credit': (CREDIT_PFX + ' · '.join(cred)) if cred else '', **({'edit': sc['edit']} if sc.get('edit') else {})})
open(f'{out}/edits.md', 'w', encoding='utf-8').write(E.listing(scenes_in, text, bounds))
if E.repeats(scenes_in):
    print('chú ý: cảnh ' + ', '.join(map(str, E.repeats(scenes_in))) + ' dùng cùng kiểu edit với cảnh ngay trước nó (nên đổi kiểu)')

# ---- music bed and board background
mu = {'style': 'tension', 'key': 'D', 'mode': 'minor', 'bpm': 70, 'energy': 0.3, **spec.get('music', {})}
music = mg.render([{'from': 0, 'to': total, **mu}], lambda v: v, total)
bed = music / (np.abs(music).max() or 1) * 0.8
mg.write_wav(f'{pub}/{base}/bed.wav', bed)
prep.board(f'{pub}/{base}/bg.jpg')

# ---- the year bar ("timeline": [[label, at], …]): the marker moves to each year when its "at" comes
timeline = None
if picks.get('timeline'):
    tl = picks['timeline']
    if not all(isinstance(x, list) and len(x) == 2 for x in tl) or len({str(x[0]) for x in tl}) > 6: fail('"timeline" phải là [["1968", "14/Jahre"], …], tối đa 6 năm')
    labels = sorted({str(x[0]) for x in tl})   # the bar shows each year once, in order; the story may go back in time
    timeline = {'labels': labels, 'marks': [round(at_time(x[1], '"timeline"'), 3) for x in tl], 'idx': [labels.index(str(x[0])) for x in tl]}
    if timeline['marks'] != sorted(timeline['marks']): fail('"timeline": các mốc phải theo thứ tự lời đọc (năm có thể lùi lại)')

plan = {'duration': total, 'lang': LANG, 'title': spec.get('title', ''), 'aiTag': AI_TAG, 'timeline': timeline,
        'faces': {k: v['family'] for k, v in FONTS.items()}, 'bg': f'{base}/bg.jpg',
        'scenes': scenes, 'subs': subs, 'voice': voice, 'music': f'{base}/bed.wav',
        'musicVolume': spec.get('music_volume', 0.14), 'fonts': []}
if picks.get('sfx'):   # sound effects for every motion (sfx.py), mixed into one track under the voice
    n_ev = SFX.render(SFX.events(plan), total, f'{pub}/{base}/sfx.wav', mg.write_wav)
    plan['sfx'], plan['sfxVolume'] = f'{base}/sfx.wav', float(picks.get('sfx_volume', 0.6))
json.dump(plan, open(f'{out}/plan.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def ts_(v):
    ms = int(round(v * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s_, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s_:02d},{ms:03d}'
with open(f'{out}/subtitles.srt', 'w', encoding='utf-8') as f:
    for k, sb in enumerate(srt, 1): f.write(f"{k}\n{ts_(sb['s'])} --> {ts_(sb['e'])}\n{sb['text']}\n\n")

# ---- sources: every picture used (title, author, date, licence, page, AI or not)
seen, rows, ai_rows, src_rows = set(), [], [], []
for name in dict.fromkeys(used_imgs):
    it = image(name); r = idx.get(it['src']) or {}
    ai = is_ai(name)
    page = it.get('page') or r.get('page') or ''
    key = page or it['src']
    if key in seen: continue
    seen.add(key)
    date = re.sub(r'date QS.*', '', r.get('date') or '').strip()
    artist = it.get('artist') or re.sub(r'\s+', ' ', r.get('artist') or '').strip()
    lic = it.get('license') or r.get('license') or ('AI-generated' if ai else '?')
    ttl = it.get('title') or r.get('title') or it['src']
    srcname = r.get('source', 'own' if it['src'].startswith('own/') else '')
    src_rows.append({'name': name, 'src': it['src'], 'title': ttl, 'artist': artist, 'date': date, 'license': lic, 'page': page, 'ai': ai})
    if ai: ai_rows.append(f'- {ttl} ({srcname or "AI"})')
    else: rows.append(f"- {ttl} — {artist}{f' ({date})' if date else ''} — {lic}{f' [{srcname}]' if srcname else ''}" + (f"\n  {page}" if page else ''))
txt = 'Nguồn ảnh (ảnh CC BY và CC BY-SA phải ghi tên tác giả và giấy phép trong mô tả video):\n\n' + ('\n'.join(rows) or '(không có ảnh thật)') + '\n'
if ai_rows:
    note = {'ja': '※一部の画像はAIで生成したイメージです（実際の写真ではありません）。',
            'de': 'Hinweis: Einige Bilder sind KI-generierte Illustrationen (keine echten Fotos).'}[LANG]
    txt += f'\nẢnh minh họa tạo bằng AI (không phải ảnh thật, có chữ "{AI_TAG}" trên video). Nên ghi trong mô tả video:\n{note}\n\n' + '\n'.join(ai_rows) + '\n'
open(f'{out}/credits.txt', 'w', encoding='utf-8').write(txt)
scene_rows = []
for sc in scenes:
    said = [c['text'] for c in subs if sc['s'] - 0.01 <= c['s'] < sc['e']]
    scene_rows.append({'scene': sc['scene'], 'start': sc['s'], 'end': sc['e'], 'said': said, **({'edit': sc['edit']} if sc.get('edit') else {}),
                       'head': (sc['head'] or {}).get('title', ''),
                       'items': [{'type': x['type'], **({'image': x['src'].rsplit('/', 1)[-1], 'ai': x['ai']} if 'src' in x else {}),
                                  **({'text': x['text']} if 'text' in x else {})} for x in sc['items']]})
json.dump({'pictures': src_rows, 'scenes': scene_rows}, open(f'{out}/sources.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'total {total} s; {len(scenes)} scenes; {len(subs)} subtitles; ' + ', '.join(f"{x['scene']}:{x['s']:.1f}–{x['e']:.1f}" for x in scenes))
