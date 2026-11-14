"""Layout of the case-file board (1080×1920), shared by build.py (the plan drawn by src/crime/CrimeV.tsx).

Measured on the owner's sample 00-video-mau/MAU-HO-SO.mp4 (576×1024, ×1.875): a dark brushed-wood board; black-and-
white press prints with a white border, slightly turned, one large or two to six small; paper tapes (yellow
handwriting, red serif, white typewriter) slapped on next to them when the voice names a thing; paper cards typed
line by line (names and ages, times, a DNA comparison with a red stamp), a lined notebook with a ticked list, a beige
case folder with a photo clipped in; big typewriter numbers; cut-out objects with a white paper edge; red strings
between the prints of an evidence board; a chapter head ("HỒ SƠ 2000" on a black strip, the case name in bold italic
serif on torn paper) at the top of a chapter, first alone in the middle; the subtitle, a small white box with the
spoken words, under the board (centre y ≈ 1600).

Everything Claude writes in picks.json by name ("pos": "main", "pin": "bl" …) is resolved here into pixels.
"""
import math, zlib

W, H = 1080, 1920
TOP, TOP_HEAD, BOTTOM = 130, 372, 1470   # the board area: under the chapter head when one is shown
SUB_Y, SUB_W, SUB_PX = 1600, 940, 40     # subtitle box: centre y, max width, font size
CREDIT_Y = 1872
HEAD_TOP = {'kicker': 196, 'title': 284}     # centre y of the chapter head's two rows (top of the board)
HEAD_MID = {'kicker': 820, 'title': 922}     # the same, alone in the middle of the board (a chapter opens)

# photos and stickers: name → (centre x, centre y as a fraction of the area, width, max height as a fraction)
PHOTO = {'main': (540, 0.45, 800, 0.84), 'wide': (540, 0.5, 990, 0.9), 'center': (540, 0.46, 640, 0.62),
         'top': (540, 0.26, 780, 0.5), 'bottom': (540, 0.75, 780, 0.47),
         'left': (320, 0.34, 580, 0.62), 'right': (765, 0.65, 560, 0.62),
         'small': (320, 0.17, 470, 0.32), 'small-r': (760, 0.17, 470, 0.32),
         'g1': (295, 0.16, 430, 0.3), 'g2': (785, 0.19, 430, 0.3), 'g3': (300, 0.5, 430, 0.3),
         'g4': (780, 0.53, 430, 0.3), 'g5': (295, 0.84, 430, 0.3), 'g6': (785, 0.86, 430, 0.3)}
# cards: name → (centre x, centre y fraction, width, height fraction)
CARD = {'main': (540, 0.5, 900, 0.97), 'top': (540, 0.25, 880, 0.48), 'bottom': (540, 0.76, 880, 0.46),
        'center': (540, 0.5, 860, 0.62)}
TAPE_PX = {'yellow': 58, 'red': 54, 'white': 58}
ROW_H = {'paper': 96, 'lined': 80}
STAT_ROW = 170
BORDER = 14                              # white border of a print (inside its box)


def area(head):
    return (TOP_HEAD if head else TOP, BOTTOM)


def rot_of(key, k, lo=0.8, hi=2.6):
    """A small turn (degrees) seeded by a name, alternating left and right with the item's index."""
    r = (zlib.crc32(f'{key}/{k}'.encode()) % 1000) / 1000
    return round((lo + (hi - lo) * r) * (1 if k % 2 else -1), 2)


def place(pos, aspect, head, big=None):
    """Box [x, y, w, h] of a photo or sticker of this aspect (w/h) at a named place or [cx, cy, w]."""
    t, b = area(head)
    if isinstance(pos, (list, tuple)):
        cx, cy, w = pos; mh = (b - t) * 0.97
    else:
        if pos not in PHOTO: raise SystemExit(f'picks.json: "pos" "{pos}" không có (dùng: {", ".join(PHOTO)} hoặc [cx, cy, w])')
        cx, fy, w, fh = PHOTO[pos]; cy = t + (b - t) * fy; mh = (b - t) * fh
    if big: w = big
    h = w / aspect
    if h > mh: h = mh; w = h * aspect
    if w > W - 40: w = W - 40; h = w / aspect
    x, y = cx - w / 2, cy - h / 2
    x = min(max(x, 20), W - 20 - w); y = min(max(y, t - 30), b + 30 - h)
    return [round(x, 1), round(y, 1), round(w, 1), round(h, 1)]


def card_box(pos, head, h=None):
    t, b = area(head)
    if isinstance(pos, (list, tuple)):
        cx, cy, w = pos[:3]; hh = h or (pos[3] if len(pos) > 3 else 600)
    else:
        if pos not in CARD: raise SystemExit(f'picks.json: card "pos" "{pos}" không có (dùng: {", ".join(CARD)} hoặc [cx, cy, w, h])')
        cx, fy, w, fh = CARD[pos]; cy = t + (b - t) * fy; hh = h or (b - t) * fh
    return [round(cx - w / 2, 1), round(cy - hh / 2, 1), w, round(hh, 1)]


def in_card(card, aspect):
    """A photo clipped into a folder card: across the card, in its upper part."""
    x, y, w, h = card
    pw = w - 150; ph = pw / aspect
    if ph > h * 0.62: ph = h * 0.62; pw = ph * aspect
    return [round(x + (w - pw) / 2, 1), round(y + h * 0.43 - ph / 2, 1), round(pw, 1), round(ph, 1)]


PINS = ('tl', 'tr', 'bl', 'br', 'top', 'bottom', 'above', 'below', 'below-l', 'below-r', 'center', 'left', 'right')


def pin(box, where, n, px):
    """Anchor of a tape on a box [x, y, w, h]: (x, y centre of the tape, align). n = tapes already on this pin
    (they stack downwards, as the sample's three tapes under each corner)."""
    x, y, w, h = box
    step = px * 1.42 * n
    a = {'tl': (x - 16, y + 10, 'left'), 'tr': (x + w + 16, y + 10, 'right'),
         'bl': (x - 16, y + h - 24, 'left'), 'br': (x + w + 16, y + h - 24, 'right'),
         'top': (x + w / 2, y + 8, 'center'), 'bottom': (x + w / 2, y + h - 8, 'center'),
         'above': (x + w / 2, y - px * 0.9, 'center'), 'below': (x + w / 2, y + h + px * 1.1, 'center'),
         'below-l': (x + 20, y + h + px * 1.1, 'left'), 'below-r': (x + w - 20, y + h + px * 1.1, 'right'),
         'center': (x + w / 2, y + h / 2, 'center'), 'left': (x - 16, y + h / 2, 'left'), 'right': (x + w + 16, y + h / 2, 'right')}
    if where not in a: raise SystemExit(f'picks.json: "pin" "{where}" không có (dùng: {", ".join(PINS)} hoặc "xy": [x, y])')
    ax, ay, al = a[where]
    ax = min(max(ax, 22), W - 22)
    return round(ax, 1), round(ay + step, 1), al


def string_end(box):
    """Where a red string is pinned on an item: the middle of its top edge, a little inside."""
    x, y, w, h = box
    return [round(x + w / 2, 1), round(y + min(26, h * 0.1), 1)]


def fit_view(view, aspect_px, img_w, img_h):
    """Grow view [x0, y0, x1, y1] (fractions of the picture) around its centre to the box aspect (w/h in pixels),
    then shift/shrink it to stay inside the picture."""
    x0, y0, x1, y1 = view
    vw, vh = (x1 - x0) * img_w, (y1 - y0) * img_h
    if vw / vh < aspect_px: vw = vh * aspect_px
    else: vh = vw / aspect_px
    if vw > img_w: vw = img_w; vh = vw / aspect_px
    if vh > img_h: vh = img_h; vw = vh * aspect_px
    cx, cy = (x0 + x1) / 2 * img_w, (y0 + y1) / 2 * img_h
    cx = min(img_w - vw / 2, max(vw / 2, cx)); cy = min(img_h - vh / 2, max(vh / 2, cy))
    return [round((cx - vw / 2) / img_w, 5), round((cy - vh / 2) / img_h, 5), round((cx + vw / 2) / img_w, 5), round((cy + vh / 2) / img_h, 5)]


def aspect_of(s):
    a, b = map(float, str(s).split(':')); return a / b


def clamp_aspect(a):
    return min(1.8, max(0.6, a))


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])
