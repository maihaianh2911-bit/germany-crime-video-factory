#!/usr/bin/env python3
"""Depth maps for the full-frame pictures of a video, so the renderer can move the camera *into* them (a 2.5D
parallax: near things move more than far ones). Usage: depth.py <picks.json> <img_root> <out_dir>

Only when picks.json has "fx": {"depth": true}; only pictures a scene shows with "pos": "full" (a print lying on
the board is flat paper and stays flat). → <out_dir>/<name>.depth.jpg (grey: white = near), read by build.py.
Model: Depth Anything V2 Small (Apache-2.0), ONNX export from github.com/fabio-sim/Depth-Anything-ONNX; the file is
taken from $DEPTH_MODEL or downloaded once to ~/.cache/crime-depth/. Runs on the CPU (~1 s per picture).
"""
import json, os, sys, urllib.request
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep

URL = 'https://github.com/fabio-sim/Depth-Anything-ONNX/releases/download/v2.0.0/depth_anything_v2_vits.onnx'
SIDE = 518   # the model's training size (a multiple of its 14 px patches)


def model_path():
    p = os.environ.get('DEPTH_MODEL') or os.path.expanduser('~/.cache/crime-depth/depth_anything_v2_vits.onnx')
    if not os.path.exists(p):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        urllib.request.urlretrieve(URL, p + '.part'); os.replace(p + '.part', p)
    return p


def full_names(picks):
    return sorted({it['photo'] for sc in picks.get('scenes') or [] for it in sc.get('items') or []
                   if isinstance(it, dict) and it.get('photo') and it.get('pos') == 'full'})


def depth_of(sess, im):
    """Relative depth of a PIL picture, 0 (far) … 1 (near), at the picture's size (an L image, softened)."""
    a = np.asarray(im.convert('RGB').resize((SIDE, SIDE), Image.BICUBIC)).astype(np.float32) / 255
    a = (a - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    d = sess.run(None, {sess.get_inputs()[0].name: a.transpose(2, 0, 1)[None].astype(np.float32)})[0].squeeze()
    lo, hi = np.percentile(d, 1), np.percentile(d, 99)
    d = np.clip((d - lo) / max(1e-6, hi - lo), 0, 1)
    out = Image.fromarray((d * 255).astype(np.uint8), 'L').resize(im.size, Image.BICUBIC)
    return out.filter(ImageFilter.GaussianBlur(max(im.size) / 260))   # soft edges: no tearing where near meets far


if __name__ == '__main__':
    picks_f, root, out = sys.argv[1], sys.argv[2], sys.argv[3]
    picks = json.load(open(picks_f, encoding='utf-8'))
    if not (picks.get('fx') or {}).get('depth'):
        sys.exit(0)
    names = full_names(picks)
    if names:
        import onnxruntime as ort
        sess = ort.InferenceSession(model_path(), providers=['CPUExecutionProvider'])
        os.makedirs(out, exist_ok=True)
        for n in names:
            im = prep.prepare({**picks['images'][n], 'look': 'clean'}, root, n)   # same crop and size as the print
            depth_of(sess, im).save(os.path.join(out, f'{n}.depth.jpg'), quality=90)
            print('depth', n, im.size)
