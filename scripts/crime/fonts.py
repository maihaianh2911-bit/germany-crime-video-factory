#!/usr/bin/env python3
"""Add the fonts a plan needs. Usage: fonts.py <plan.json> <fontsource_dir> <public_dir>

<fontsource_dir> holds the unpacked npm packages of scripts/crime/get_fonts.sh. For every role of the plan's language
in fonts.json (sub, mono, serif, hand) only the @font-face chunks whose unicode-range holds characters of this
video are copied to <public_dir>/crime/fonts/ and listed in plan["fonts"] (family, file, range, weight, style;
CrimeV registers them with FontFace).
"""
import json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def faces(src, lang):
    """[(role, {family, file (path in the package dir), range, weight, style})] of every @font-face of the roles."""
    roles = json.load(open(os.path.join(HERE, 'fonts.json'), encoding='utf-8'))[lang]['roles']
    out = []
    for role, r in roles.items():
        for pkg, css in r['css']:
            for blk in re.findall(r'@font-face\s*{(.*?)}', open(os.path.join(src, pkg, css), encoding='utf-8').read(), re.S):
                f = re.search(r"url\(\./files/([^)]+\.woff2)\)", blk).group(1)
                prop = lambda k, d: (re.search(k + r':\s*([^;]+);', blk) or [None, d])[1].strip()
                out.append((role, {'family': prop('font-family', r['family']).strip("'\""), 'path': os.path.join(src, pkg, 'files', f),
                                   'file': f, 'range': prop('unicode-range', 'U+0-10FFFF'), 'weight': prop('font-weight', '400'),
                                   'style': prop('font-style', 'normal')}))
    return out


def ranges(ur):
    rs = []
    for part in ur.split(','):
        part = part.strip().replace('U+', '')
        a, b = part.split('-') if '-' in part else (part, part)
        rs.append((int(a, 16), int(b, 16)))
    return rs


if __name__ == '__main__':
    plan_path, src, pub = sys.argv[1], sys.argv[2], sys.argv[3]
    plan = json.load(open(plan_path, encoding='utf-8'))
    text = json.dumps(plan, ensure_ascii=False)
    chars = set(text) | set(text.upper()) | set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789ÄÖÜäöüß—–„“‚‘«».,:;!?()/+-=≠→✓?・「」（）、。 　')
    os.makedirs(f'{pub}/crime/fonts', exist_ok=True)
    out, seen = [], set()
    for role, f in faces(src, plan.get('lang', 'ja')):
        if f['file'] in seen or not any(any(a <= ord(c) <= b for a, b in ranges(f['range'])) for c in chars): continue
        seen.add(f['file'])
        shutil.copy(f['path'], f'{pub}/crime/fonts/{f["file"]}')
        out.append({'family': f['family'], 'file': f'crime/fonts/{f["file"]}', 'range': f['range'], 'weight': f['weight'], 'style': f['style']})
    plan['fonts'] = out
    json.dump(plan, open(plan_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(len(out), 'font chunks')
