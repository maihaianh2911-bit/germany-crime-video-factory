"""Sound effects of the case-file board, synthesized here (no samples, nothing to license): a typewriter key for
every typed character, a paper slap when a tape lands, a thud for a stamp, a paper swish when a print or a card
arrives, a short whoosh at a cut, a pencil scratch for handwriting and rings, a low boom for a chapter head and the
quiet moments, a soft ping for a map pin. Used when picks.json says "sfx": true (version B, 15/11/2026).

events(plan) lists (time, sound) from a built plan (build.py); render(events, total, path) mixes them into one mono
WAV (48 kHz, like the music bed) that CrimeV plays under the voice. Every sound is seeded, so a render is repeatable.
"""
import numpy as np
from scipy import signal

SR = 48000
LEVEL = {'key': 0.16, 'scratch': 0.22, 'slap': 0.42, 'slap_red': 0.55, 'stamp': 0.95, 'swish': 0.3, 'drop': 0.4,
         'whoosh': 0.22, 'boom': 0.6, 'ping': 0.3, 'tick': 0.18}


def _f(x, kind, f):
    b, a = signal.butter(2, np.asarray(f) / (SR / 2), kind)
    return signal.lfilter(b, a, x)


def _t(d):
    return np.arange(int(d * SR)) / SR


def _norm(x):
    return x / (np.abs(x).max() or 1)


def key(r):
    """A typewriter key: a sharp click, the wooden body of the machine, a little metal."""
    t = _t(0.07)
    x = (0.9 * _f(r.uniform(-1, 1, t.size), 'highpass', 1800) * np.exp(-t / 0.0022)
         + 0.55 * np.sin(2 * np.pi * (210 + 70 * r.rand()) * t) * np.exp(-t / 0.016)
         + 0.12 * np.sin(2 * np.pi * (2900 + 600 * r.rand()) * t) * np.exp(-t / 0.007))
    return _norm(x) * (0.75 + 0.5 * r.rand())


def slap(r, low=False):
    """A strip of tape slapped on the board: a dull paper hit."""
    t = _t(0.22)
    x = _f(r.uniform(-1, 1, t.size), 'lowpass', 2400) * np.exp(-t / 0.022) + (0.9 if low else 0.55) * np.sin(2 * np.pi * (78 if low else 105) * t) * np.exp(-t / 0.05)
    return _norm(x)


def stamp(r):
    """A rubber stamp: a heavy thud and the rattle of the desk."""
    t = _t(0.5)
    f = 58 + 30 * np.exp(-t / 0.03)
    x = (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.13) + 0.6 * _f(r.uniform(-1, 1, t.size), 'lowpass', 900) * np.exp(-t / 0.045)
         + 0.35 * _f(r.uniform(-1, 1, t.size), 'highpass', 3000) * np.exp(-t / 0.004))
    return _norm(x)


def swish(r, d=0.3):
    """Paper sliding over the board."""
    t = _t(d)
    x = _f(r.uniform(-1, 1, t.size), 'bandpass', [1300, 6000]) * np.sin(np.pi * t / d) ** 2
    return _norm(x)


def drop(r):
    """A print falling on the board: a short swish and the soft tap of its landing."""
    a = swish(r, 0.2) * 0.8
    t = _t(0.12)
    tap = _f(r.uniform(-1, 1, t.size), 'lowpass', 500) * np.exp(-t / 0.018) + 0.7 * np.sin(2 * np.pi * 135 * t) * np.exp(-t / 0.035)
    x = np.zeros(int(0.32 * SR)); x[:a.size] += a; i = int(0.17 * SR); x[i:i + tap.size] += _norm(tap)
    return _norm(x)


def whoosh(r, d=0.38):
    """Air at a cut: noise whose colour rises from low to high."""
    t = _t(d)
    n = r.uniform(-1, 1, t.size)
    lo, hi = _f(n, 'bandpass', [250, 900]), _f(n, 'bandpass', [1400, 4500])
    k = t / d
    x = (lo * (1 - k) + hi * k) * np.sin(np.pi * k) ** 1.5
    return _norm(x)


def boom(r):
    """A low cinematic hit: a falling sub tone and a burst of dark noise."""
    t = _t(1.8)
    f = 36 + 46 * np.exp(-t / 0.5)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.8) + 0.45 * _f(r.uniform(-1, 1, t.size), 'lowpass', 300) * np.exp(-t / 0.12)
    x[: int(0.004 * SR)] *= np.linspace(0, 1, int(0.004 * SR))
    return _norm(x)


def scratch(r, d):
    """A pencil writing: bright noise in strokes."""
    d = min(1.0, max(0.25, d))
    t = _t(d)
    strokes = 0.35 + 0.65 * np.abs(np.sin(2 * np.pi * (7 + 4 * r.rand()) * t + np.cumsum(r.normal(0, 0.02, t.size))))
    x = _f(r.uniform(-1, 1, t.size), 'bandpass', [2200, 7500]) * strokes * np.minimum(1, np.minimum(t / 0.03, (d - t) / 0.05))
    return _norm(x)


def ping(r):
    """A map pin: a soft bell."""
    t = _t(0.9)
    x = (np.sin(2 * np.pi * 1320 * t) + 0.4 * np.sin(2 * np.pi * 1985 * t)) * np.exp(-t / 0.3)
    x[: int(0.003 * SR)] *= np.linspace(0, 1, int(0.003 * SR))
    return _norm(x)


def tick(r):
    """The marker of the year bar moving on: a dry click."""
    t = _t(0.05)
    return _norm(_f(r.uniform(-1, 1, t.size), 'bandpass', [1500, 5000]) * np.exp(-t / 0.006))


def _typed(text, s, cps):
    return [(s + k / cps, 'key') for k, ch in enumerate(text) if not ch.isspace()]


def events(plan):
    """(time, sound) of everything that moves in a built plan."""
    ev = [(0.0, 'boom')] if plan['scenes'] and plan['scenes'][0].get('hook_q') else []
    for sc in plan['scenes']:
        s0 = sc['s']
        if sc.get('hush'): ev.append((s0, 'boom'))
        elif s0 > 0: ev.append((max(0, s0 - 0.1), 'whoosh'))
        h = sc.get('head')
        if h and h.get('from') is None: ev.append((s0, 'boom'))
        elif h and h.get('from') == 'mid' and h['mode'] == 'top': ev.append((s0, 'whoosh'))
        for it in sc['items']:
            t, late = it['s'], it['s'] > s0 + 0.01
            kind = it['type']
            if kind == 'photo':
                if late and not it.get('bleed'): ev.append((t - 0.12, 'drop'))
                for rg in it.get('rings', []):
                    ev.append((rg['s'], 'ping' if rg.get('shape') == 'pin' else 'scratch:0.5'))
                if it.get('zoom'): ev.append((it['zoom']['s'], 'whoosh'))
            elif kind == 'sticker':
                ev.append((t, 'swish'))
            elif kind == 'tape':
                ev.append((t, 'slap_red' if it.get('color') == 'red' else 'slap'))
            elif kind == 'card':
                if late: ev.append((t, 'swish'))
                if it.get('head'): ev += _typed(it['head'], t, 40)
                for rw in it.get('rows', []):
                    if it['style'] == 'lined': ev.append((rw['s'], f"scratch:{len(rw['l']) / 45:.2f}"))
                    else: ev += _typed(rw['l'], rw['s'], 32) + _typed(rw.get('r', ''), rw['s'] + 0.15, 32)
                if it.get('note'): ev.append((it['note']['s'], 'slap'))
                if it.get('stamp'): ev.append((it['stamp']['s'], 'stamp'))
            elif kind == 'stat':
                ev += [(rw['s'], 'slap') for rw in it['rows']]
            elif kind == 'string':
                ev.append((t, 'swish:0.18'))
    for k, m in enumerate((plan.get('timeline') or {}).get('marks', [])):
        ev.append((m, 'tick'))
    return sorted(ev)


def render(ev, total, path, write, seed=11):
    """Mix the events into `total` seconds and write them with write(path, samples)."""
    r = np.random.RandomState(seed)
    out = np.zeros(int((total + 2) * SR))
    for t, name in ev:
        kind, _, arg = name.partition(':')
        if kind == 'key': x = key(r)
        elif kind in ('slap', 'slap_red'): x = slap(r, low=kind == 'slap_red')
        elif kind == 'swish': x = swish(r, float(arg) if arg else 0.3)
        elif kind == 'scratch': x = scratch(r, float(arg or 0.5))
        else: x = {'stamp': stamp, 'drop': drop, 'whoosh': whoosh, 'boom': boom, 'ping': ping, 'tick': tick}[kind](r)
        i = int(max(0, t) * SR)
        if i >= out.size: continue
        x = x[: out.size - i] * LEVEL[kind]
        out[i:i + x.size] += x
    out = np.tanh(out * 1.1) / np.tanh(1.1)   # soft limit where sounds pile up
    write(path, out[: int(total * SR)])
    return len(ev)
