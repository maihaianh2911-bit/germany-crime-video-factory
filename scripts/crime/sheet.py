#!/usr/bin/env python3
"""Shot sheet of the finished video for the final check: the full frame of every scene just after it starts and just
before it ends (every tape, row and ring in place), labelled with the scene number, time and the scene edit's name (picks.json "edit").
Usage: sheet.py <video.mp4> <plan.json> <out.jpg>"""
import json, os, sys, tempfile
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ff

video, plan, out = sys.argv[1:4]
plan = json.load(open(plan, encoding='utf-8'))
tmp = tempfile.mkdtemp()
def grab(t):
    ff.run('-ss', f'{t:.2f}', '-i', video, '-frames:v', '1', f'{tmp}/f.png')
    return Image.open(f'{tmp}/f.png').convert('RGB')
tiles = []
TW, TH = 270, 480
for sc in plan['scenes']:
    times = [min(sc['e'] - 0.1, sc['s'] + 0.4)]
    if sc['e'] - sc['s'] > 1.4: times.append(sc['e'] - 0.15)
    for k, t in enumerate(times):
        im = grab(t).resize((TW, TH), Image.LANCZOS)
        tile = Image.new('RGB', (TW, TH + 24), (10, 10, 12)); tile.paste(im, (0, 24))
        ImageDraw.Draw(tile).text((4, 6), f"#{sc['scene']}  {t:.1f}s{'  end' if k else ''}{'  · ' + sc['edit'] if sc.get('edit') else ''}", fill=(255, 210, 90))
        tiles.append(tile)
cols = 6; rows = (len(tiles) + cols - 1) // cols
s = Image.new('RGB', (cols * (TW + 8), rows * (TH + 32)), (12, 12, 14))
for i, t in enumerate(tiles): s.paste(t, ((i % cols) * (TW + 8), (i // cols) * (TH + 32)))
s.save(out, quality=85)
print(out, len(tiles), 'frames')
