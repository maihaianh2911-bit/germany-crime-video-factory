#!/usr/bin/env python3
"""Preview every scene before rendering, drawn by the video's own renderer (Remotion stills of the CrimeV
composition, half size): for each scene a frame just after it starts and one just before it ends (every tape, row,
ring and stamp in place), with the scene number and time. Catches wrong pictures, cut subjects, tapes over a face,
overflowing cards and misplaced rings before a 20-minute render.

Usage: preview.py <crime/N dir with script.json + picks.json> <renders crime/N dir with voice/ and img/> <out.jpg>
       [--scenes 3,4,9]   (only these scenes, faster while fixing)
Needs `npm ci` (node_modules) and the fonts (FONTSOURCE, scripts/crime/get_fonts.sh). Also writes <out>.plan.json
(times of every scene and subtitle) next to the sheet."""
import json, os, shutil, subprocess, sys, tempfile
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))

job, rend, out = sys.argv[1:4]
only = set(int(x) for x in sys.argv[sys.argv.index('--scenes') + 1].split(',')) if '--scenes' in sys.argv else None
tmp = tempfile.mkdtemp(prefix='crime-preview-')
pub = os.path.join(tmp, 'public'); base = os.path.join(pub, 'crime', 'P')
os.makedirs(base); shutil.copytree(os.path.join(rend, 'voice'), os.path.join(base, 'voice'))
imgsrc = os.path.join(tmp, 'img'); shutil.copytree(os.path.join(rend, 'img'), imgsrc)
if os.path.isdir(os.path.join(job, 'own')): shutil.copytree(os.path.join(job, 'own'), os.path.join(imgsrc, 'own'), dirs_exist_ok=True)
run = lambda *a: subprocess.run([sys.executable, *a], check=True, stdout=subprocess.DEVNULL)
run(os.path.join(HERE, 'prep.py'), os.path.join(job, 'picks.json'), imgsrc, os.path.join(base, 'img'))
run(os.path.join(HERE, 'build.py'), job, pub, 'P', imgsrc, os.path.join(tmp, 'out'))
plan_p = os.path.join(tmp, 'out', 'plan.json')
run(os.path.join(HERE, 'fonts.py'), plan_p, os.environ.get('FONTSOURCE', '/tmp/fontsource'), pub)
plan = json.load(open(plan_p, encoding='utf-8'))

frames = []
for sc in plan['scenes']:
    if only and sc['scene'] not in only: continue
    late = max([sc['s']] + [i['s'] for i in sc['items']] + [r['s'] for i in sc['items'] for r in i.get('rows', []) + i.get('rings', [])]
               + [i[k]['s'] for i in sc['items'] for k in ('note', 'stamp') if i.get(k)])
    times = [min(sc['e'] - 0.05, sc['s'] + 0.35)]
    if late > times[0] + 0.1 or sc['e'] - sc['s'] > 3: times.append(max(times[0] + 0.1, sc['e'] - 0.12))
    frames += [(sc['scene'], round(t, 2), k) for k, t in enumerate(times)]
subprocess.run(['node', os.path.join(HERE, 'stills.mjs'), plan_p, pub, os.path.join(tmp, 'st'), *[f'{t:.2f}' for _, t, _ in frames]],
               check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
TW, TH = 270, 480
tiles = []
for n, t, k in frames:
    f = Image.open(os.path.join(tmp, f'st_{t:.2f}.png')).convert('RGB').resize((TW, TH), Image.LANCZOS)
    tile = Image.new('RGB', (TW, TH + 24), (10, 10, 12)); tile.paste(f, (0, 24))
    ImageDraw.Draw(tile).text((4, 6), f"#{n}  {t:.1f}s{'  end' if k else ''}", fill=(255, 210, 90))
    tiles.append(tile)
cols = 6; rows = (len(tiles) + cols - 1) // cols
sheet = Image.new('RGB', (cols * (TW + 8), max(1, rows) * (TH + 32)), (0, 0, 0))
for i, t in enumerate(tiles): sheet.paste(t, ((i % cols) * (TW + 8), (i // cols) * (TH + 32)))
sheet.save(out, quality=85)
json.dump({'duration': plan['duration'], 'scenes': [{'scene': s['scene'], 's': s['s'], 'e': s['e'], 'items': [i['type'] for i in s['items']]} for s in plan['scenes']],
           'subs': [[c['s'], c['text']] for c in plan['subs']]}, open(out + '.plan.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(out, len(tiles), 'frames', f"{plan['duration']:.1f}s")
shutil.rmtree(tmp, ignore_errors=True)
