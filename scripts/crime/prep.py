#!/usr/bin/env python3
"""Crop, size and style the pictures chosen in picks.json. Usage: prep.py <picks.json> <img_root> <out_dir>

picks.json "images": {"<name>": {"src": "<round>/<file>" (picture search or AI illustration) or "own/<file>"
(crime/<N>/own/), "rotate": 90 | -90 | 180 (optional, before the crop), "crop": [x0, y0, x1, y1] (0..1, optional:
removes borders, captions, watermarks), "look": "print" (default: the sample's black-and-white press print — hard
contrast, a fine halftone screen, grain, a few specks) | "clean" (true colours, sharp: documents, maps) |
"cutout" (the object alone, its plain background removed, in black and white with a thick white paper edge: a
sticker, as the sample's knife, bag and DNA strand — needs a picture of one object on a plain or softly graded
background; "tol": 1.5–2.5 also removes a soft shadow, 0.6 keeps a pale object apart from a pale background),
"blur": [[x0, y0, x1, y1], …] (optional: faces or details to blur — children, uninvolved people, names)}}
→ <out_dir>/<name>.jpg (<name>.png for a cutout). The grain is seeded by the name, so a picture looks the same in
every render. board(path) writes the dark brushed-wood background of the board.
"""
import json, os, sys, zlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def _gray(im):
    a = np.asarray(im.convert('RGB')).astype(np.float32) / 255
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def _print(l, seed, specks=True):
    """Black-and-white press print as the sample: levels stretched, an S-curve, a fine halftone screen at 45°,
    grain, a soft vignette and a few dust specks. l: luminance 0..1 (H×W). Returns an L image."""
    rng = np.random.RandomState(seed)
    H, W = l.shape
    lo, hi = np.percentile(l, 1.5), np.percentile(l, 98.5)
    l = np.clip((l - lo) / max(0.05, hi - lo), 0, 1)
    l = l * l * (3 - 2 * l) * 0.7 + l * 0.3                               # S-curve: harder contrast
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cell = max(4.0, max(W, H) / 330)                                      # ~330 dots across the long side
    u, v = (xx + yy) / (cell * 1.4142), (xx - yy) / (cell * 1.4142)
    screen = 0.5 + 0.25 * (np.cos(2 * np.pi * u) + np.cos(2 * np.pi * v))
    dots = (l > screen).astype(np.float32)
    mid = 1 - np.abs(l - 0.5) * 2                                         # the screen shows in the greys
    l = l * (1 - 0.3 * mid) + dots * 0.3 * mid
    r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    l *= 1 - 0.32 * np.clip(r - 0.55, 0, None) ** 1.4                     # vignette
    l += rng.normal(0, 0.035, (H, W))                                      # grain
    l = 0.04 + np.clip(l, 0, 1) * 0.9                                      # paper black / paper white
    out = Image.fromarray((np.clip(l, 0, 1) * 255).astype(np.uint8), 'L')
    if specks:
        d = ImageDraw.Draw(out); s = max(W, H) / 1400
        for _ in range(int(rng.randint(10, 24))):
            x, y, rad = rng.rand() * W, rng.rand() * H, (0.7 + rng.rand() ** 3 * 2.5) * s
            d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=int(200 + rng.rand() * 55) if rng.rand() < 0.7 else int(rng.rand() * 40))
    return out


def _mask(im, tol=1.0):
    """Object mask of a picture of one object on a plain background: the background is what is connected to the
    border and close to the border's colour. Returns a bool array, or None when no clear object is found."""
    from scipy import ndimage as nd
    a = np.asarray(im.convert('RGB')).astype(np.float32)
    H, W = a.shape[:2]
    # the background as a smooth surface (a quadratic in x and y, per colour) fitted to the border: a plain backdrop
    # with a light gradient (a studio sweep, a shadowed table) is still one background
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    bm = np.zeros((H, W), bool); bm[:3] = bm[-3:] = True; bm[:, :3] = bm[:, -3:] = True
    X, Y = xx / W - 0.5, yy / H - 0.5
    basis = lambda X, Y: np.stack([np.ones_like(X), X, Y, X * X, Y * Y, X * Y], -1)
    coef, *_ = np.linalg.lstsq(basis(X[bm], Y[bm]), a[bm], rcond=None)
    model = basis(X, Y) @ coef
    edge_d = np.sqrt(((a[bm] - model[bm]) ** 2).sum(1))
    spread = np.percentile(edge_d, 90)
    dist = np.sqrt(((a - model) ** 2).sum(2))
    near = nd.gaussian_filter(dist, 1.2) < max(28.0, spread * 2.2) * tol
    lab, n = nd.label(near)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    obj = ~np.isin(lab, list(border))
    obj = nd.binary_opening(obj, iterations=2)
    lab, n = nd.label(obj)
    if not n: return None
    sizes = nd.sum(obj, lab, range(1, n + 1))
    keep = [i + 1 for i, s in enumerate(sizes) if s >= max(sizes.max() * 0.08, H * W * 0.002)]
    obj = nd.binary_fill_holes(np.isin(lab, keep))
    share = obj.mean()
    return obj if 0.03 < share < 0.92 else None


def cutout(im, seed, tol=1.0):
    """The object of `im` on transparency, in the print look, with a white paper edge (RGBA)."""
    from scipy import ndimage as nd
    m = _mask(im, tol)
    W, H = im.size
    if m is None:   # no plain background: the whole picture becomes a rectangular sticker
        print(f'  cutout: no plain background found, the whole picture is used', file=sys.stderr)
        m = np.ones((H, W), bool); m[:2] = m[-2:] = False; m[:, :2] = m[:, -2:] = False
    pad = int(max(W, H) * 0.04)
    l = np.pad(_gray(im), pad, mode='edge'); m = np.pad(m, pad)
    soft = nd.gaussian_filter(m.astype(np.float32), 1.0)
    rim = nd.binary_dilation(m, iterations=max(6, int(max(W, H) * 0.016)))
    rng = np.random.RandomState(seed)   # a slightly uneven paper edge
    wob = nd.gaussian_filter(rng.rand(*m.shape).astype(np.float32), max(W, H) * 0.01)
    rim = rim | (nd.binary_dilation(m, iterations=max(8, int(max(W, H) * 0.022))) & (wob > np.median(wob)))
    rim = nd.gaussian_filter(rim.astype(np.float32), 1.0)
    p = np.asarray(_print(l, seed, specks=False)).astype(np.float32) / 255
    g = p * soft + 0.95 * (1 - soft)                                       # object, else paper white
    rgb = np.stack([g * 0.99, g * 0.98, g * 0.95], 2)
    out = Image.fromarray((np.dstack([rgb, np.clip(np.maximum(rim, soft), 0, 1)]) * 255).astype(np.uint8), 'RGBA')
    return out.crop(out.getbbox())


def prepare(it, root, name='x'):
    """One picture of picks.json "images", cropped, blurred where asked and styled (PIL image)."""
    im = Image.open(os.path.join(root, it['src'])).convert('RGB')
    if it.get('rotate'):
        im = im.rotate(it['rotate'], expand=True)
    if it.get('crop'):
        x0, y0, x1, y1 = it['crop']; W, H = im.size
        im = im.crop((round(x0 * W), round(y0 * H), round(x1 * W), round(y1 * H)))
    for x0, y0, x1, y1 in it.get('blur') or []:   # faces of children / uninvolved people, names
        W, H = im.size; box = (round(x0 * W), round(y0 * H), round(x1 * W), round(y1 * H))
        reg = im.crop(box); rad = max(8, (box[2] - box[0]) // 6)
        im.paste(reg.resize((max(1, reg.width // rad), max(1, reg.height // rad))).resize(reg.size, Image.NEAREST).filter(ImageFilter.GaussianBlur(rad / 2)), box)
    W, H = im.size
    if max(W, H) < 1400:   # small sources are enlarged here so the browser never scales them up
        k = 1400 / max(W, H); im = im.resize((round(W * k), round(H * k)), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=50, threshold=2))
    if max(im.size) > 2000:
        k = 2000 / max(im.size); im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    look = it.get('look', 'print')
    seed = zlib.crc32(name.encode())
    if look == 'clean':
        return im
    if look == 'cutout':
        return cutout(im, seed, it.get('tol', 1.0))
    if look != 'print':
        raise SystemExit(f'picks.json: ảnh "{name}": "look" phải là print, clean hoặc cutout (không phải "{look}")')
    return _print(_gray(im), seed).convert('RGB')


def board(path, W=1080, H=1920, seed=7):
    """Dark brushed-wood background of the board: long horizontal grain, a few darker streaks, a warm grey."""
    from scipy import ndimage as nd
    rng = np.random.RandomState(seed)
    n = rng.normal(0, 1, (H, W)).astype(np.float32)
    grain = nd.gaussian_filter(n, (0.8, 60)) * 9 + nd.gaussian_filter(n, (6, 240)) * 30
    rows = nd.gaussian_filter(rng.normal(0, 1, H).astype(np.float32), 18)[:, None] * 6
    base = 36 + grain + rows
    rgb = np.stack([base * 1.06, base * 1.0, base * 0.93], 2)
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).save(path, quality=90)


def out_name(name, it):
    return f"{name}.{'png' if it.get('look') == 'cutout' else 'jpg'}"


if __name__ == '__main__':
    picks, root, out = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out, exist_ok=True)
    for name, it in json.load(open(picks, encoding='utf-8'))['images'].items():
        im = prepare(it, root, name)
        p = os.path.join(out, out_name(name, it))
        im.save(p, **({} if p.endswith('.png') else {'quality': 92}))
        print(name, im.size)
