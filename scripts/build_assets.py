"""Builds the SVGs the profile README shows, in the Konya Hackerspace "paper" look.

GitHub strips CSS from READMEs, so the look travels as images: cool grey paper, ink type, Anton for the
big words, cobalt offset shadows, lime only for things that are on. Every asset comes in a light and a
dark variant; the README picks one with <picture>.

Fonts are fetched once into .cache/ and subset into each SVG, so the images render the same everywhere.
The Türkiye ranking comes from committers.top; a daily workflow reruns this script to keep it fresh.

    python3 scripts/build_assets.py
"""

import base64
import datetime
import io
import json
import math
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets'
CACHE = ROOT / '.cache'

FONT_URLS = {
    'display': 'https://raw.githubusercontent.com/google/fonts/main/ofl/anton/Anton-Regular.ttf',
    'mono': 'https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexmono/IBMPlexMono-Regular.ttf',
    'mono-bold': 'https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexmono/IBMPlexMono-SemiBold.ttf',
    'sans': 'https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexsans/IBMPlexSans%5Bwdth,wght%5D.ttf',
}

# ── Palette ──────────────────────────────────────────────────────────────────
# Same tokens as khs-portal/src/styles/global.css; dark swaps paper and ink and keeps the accents.
LIGHT = dict(
    bg='#e9ebef', glow='#f6f7f9', surface='#ffffff', text='#0c0f1a', muted='#4d5570', line='#0c0f1a',
    rule='#c9cfdc', accent='#2b3fe0', shadow='#2b3fe0', prompt='#2b3fe0', title_shadow='rgba(43,63,224,.22)',
    grain=.35, wall='#b9bee6', wall_side='#a5abdc', tile_a='#cdd1e6', tile_b='#dde0ef', slab='#0c0f1a',
)
DARK = dict(
    bg='#11141f', glow='#1a1f30', surface='#161b2b', text='#e9ebef', muted='#9aa3bd', line='#e9ebef',
    rule='#2a3048', accent='#7d8bff', shadow='#2b3fe0', prompt='#c8f53c', title_shadow='rgba(125,139,255,.28)',
    grain=.18, wall='#2a3160', wall_side='#232951', tile_a='#262c47', tile_b='#2e3555', slab='#05070d',
)
INK = '#0c0f1a'
LIME = '#c8f53c'
PINK = '#ff5c93'
TEAL = '#13a89e'
COBALT = '#2b3fe0'
WOOD = '#8a6142'
WOOD_TOP = '#a8794f'

# ── Fonts ────────────────────────────────────────────────────────────────────

_fonts = {}


def font_path(key):
    CACHE.mkdir(exist_ok=True)
    path = CACHE / f'{key}.ttf'
    if not path.exists():
        urllib.request.urlretrieve(FONT_URLS[key], path)
        if key == 'sans':
            # Plex Sans ships as a variable font; pin it to Regular.
            from fontTools.varLib.instancer import instantiateVariableFont
            f = TTFont(path)
            instantiateVariableFont(f, {'wght': 400, 'wdth': 100}, inplace=True)
            f.save(path)
    return path


def font(key):
    if key not in _fonts:
        f = TTFont(font_path(key))
        _fonts[key] = (f, f.getBestCmap(), f['hmtx'], f['head'].unitsPerEm)
    return _fonts[key]


def measure(text, key, size, spacing=0.0):
    _, cmap, hmtx, upm = font(key)
    width = 0
    for ch in text:
        glyph = cmap.get(ord(ch)) or cmap.get(ord('?'))
        width += hmtx[glyph][0]
    return width * size / upm + spacing * size * max(len(text) - 1, 0)


def wrap(text, key, size, max_width):
    lines, line = [], ''
    for word in text.split():
        trial = f'{line} {word}'.strip()
        if measure(trial, key, size) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def font_face(key, chars):
    opts = subset.Options()
    opts.flavor = 'woff'
    opts.layout_features = ['kern', 'liga']
    opts.name_IDs = []
    opts.notdef_outline = True
    opts.drop_tables += ['meta']
    f = TTFont(font_path(key), recalcTimestamp=False)
    sub = subset.Subsetter(opts)
    sub.populate(text=''.join(sorted(chars)) + ' ')
    sub.subset(f)
    buf = io.BytesIO()
    f.flavor = 'woff'
    f.save(buf)
    data = base64.b64encode(buf.getvalue()).decode()
    return f"@font-face{{font-family:'{key}';src:url(data:font/woff;base64,{data}) format('woff')}}"


# ── SVG document ─────────────────────────────────────────────────────────────


class Svg:
    def __init__(self, width, height, title):
        self.w, self.h, self.title = width, height, title
        self.parts, self.defs, self.css = [], [], []
        self.chars = {}

    def add(self, markup):
        self.parts.append(markup)

    def text(self, x, y, s, key, size, fill, spacing=0.0, anchor='start', cls='', extra=''):
        self.chars.setdefault(key, set()).update(s)
        ls = f' letter-spacing="{spacing * size:.2f}"' if spacing else ''
        c = f' class="{cls}"' if cls else ''
        self.add(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{key}" font-size="{size}" fill="{fill}"'
            f' text-anchor="{anchor}"{ls}{c}{extra}>{escape(s)}</text>'
        )

    def render(self):
        faces = ''.join(font_face(k, v) for k, v in self.chars.items())
        style = f'<style>{faces}{"".join(self.css)}</style>'
        defs = f'<defs>{"".join(self.defs)}</defs>' if self.defs else ''
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}"'
            f' viewBox="0 0 {self.w} {self.h}" role="img" aria-label="{escape(self.title)}">'
            f'<title>{escape(self.title)}</title>{style}{defs}{"".join(self.parts)}</svg>'
        )

    def save(self, name):
        OUT.mkdir(exist_ok=True)
        (OUT / name).write_text(self.render(), encoding='utf-8')


def grain(svg, opacity):
    svg.defs.append(
        '<filter id="grain" x="0" y="0" width="100%" height="100%">'
        '<feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="3" stitchTiles="stitch"/>'
        '<feColorMatrix values="0 0 0 0 .2 0 0 0 0 .22 0 0 0 0 .3 0 0 0 .45 0"/></filter>'
    )
    return f'<rect width="100%" height="100%" filter="url(#grain)" opacity="{opacity}"/>'


def card(svg, x, y, w, h, fill, line, shadow, offset=6, border=2):
    """The site's card: a filled box, an ink border and a cobalt block shadow down and to the right."""
    svg.add(f'<rect x="{x + offset}" y="{y + offset}" width="{w}" height="{h}" fill="{shadow}"/>')
    b = border / 2
    svg.add(
        f'<rect x="{x + b}" y="{y + b}" width="{w - border}" height="{h - border}" fill="{fill}"'
        f' stroke="{line}" stroke-width="{border}"/>'
    )


def tag(svg, x, y, label, p, kind='outline', size=11):
    """Uppercase mono tag. outline = plain, ink = filled, on = lime (live things only). Returns its width."""
    label = label.upper()
    dot = 10 if kind == 'on' else 0
    w = measure(label, 'mono-bold', size, .08) + 16 + dot
    h = size + 11
    fill, stroke, color = {
        'outline': (p['surface'], p['line'], p['text']),
        'ink': (p['line'], p['line'], p['bg']),
        'on': (LIME, INK, INK),
    }[kind]
    svg.add(f'<rect x="{x + .75}" y="{y + .75}" width="{w - 1.5:.1f}" height="{h - 1.5}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    if dot:
        svg.add(f'<circle cx="{x + 10}" cy="{y + h / 2}" r="3" fill="{INK}"/>')
    svg.text(x + 8 + dot, y + h / 2 + size * .36, label, 'mono-bold', size, color, .08)
    return w


REDUCED = '@media (prefers-reduced-motion:reduce){*{animation:none!important}}'
CURSOR_CSS = '.cursor{animation:blink 1.1s steps(1,end) infinite}@keyframes blink{50%{opacity:0}}'

# ── Isometric room ───────────────────────────────────────────────────────────
# A small cousin of the room on the KHS home page: a slab, two walls, a desk with a screen, a shelf.


class Iso:
    def __init__(self, svg, ox, oy, s, p):
        self.svg, self.ox, self.oy, self.s, self.p = svg, ox, oy, s, p

    def pt(self, x, y, z=0):
        c, sn = math.cos(math.radians(30)), math.sin(math.radians(30))
        return self.ox + (x - y) * c * self.s, self.oy + (x + y) * sn * self.s - z * self.s

    def poly(self, pts, fill, stroke=None, width=1.6):
        d = ' '.join(f'{a:.1f},{b:.1f}' for a, b in (self.pt(*q) for q in pts))
        st = f' stroke="{stroke or INK}" stroke-width="{width}" stroke-linejoin="round"'
        self.svg.add(f'<polygon points="{d}" fill="{fill}"{st}/>')

    def box(self, x, y, z, w, d, h, top, left, right):
        self.poly([(x, y + d, z), (x + w, y + d, z), (x + w, y + d, z + h), (x, y + d, z + h)], left)
        self.poly([(x + w, y, z), (x + w, y + d, z), (x + w, y + d, z + h), (x + w, y, z + h)], right)
        self.poly([(x, y, z + h), (x + w, y, z + h), (x + w, y + d, z + h), (x, y + d, z + h)], top)


def room(svg, ox, oy, s, p):
    iso = Iso(svg, ox, oy, s, p)
    n, wall = 5, 2.7
    # Slab under the floor
    iso.poly([(0, n, 0), (n, n, 0), (n, n, -.35), (0, n, -.35)], p['slab'])
    iso.poly([(n, 0, 0), (n, n, 0), (n, n, -.35), (n, 0, -.35)], p['slab'])
    # Checker floor
    for i in range(n):
        for j in range(n):
            iso.poly([(i, j, 0), (i + 1, j, 0), (i + 1, j + 1, 0), (i, j + 1, 0)],
                     p['tile_a'] if (i + j) % 2 else p['tile_b'], stroke=p['tile_a'], width=.6)
    iso.poly([(0, 0, 0), (n, 0, 0), (n, n, 0), (0, n, 0)], 'none', width=1.6)
    # Walls: back (along x) and left (along y), each with a cobalt baseboard
    iso.poly([(0, 0, 0), (n, 0, 0), (n, 0, wall), (0, 0, wall)], p['wall'])
    iso.poly([(0, 0, 0), (0, n, 0), (0, n, wall), (0, 0, wall)], p['wall_side'])
    iso.poly([(0, 0, 0), (n, 0, 0), (n, 0, .22), (0, 0, .22)], COBALT, width=1.2)
    iso.poly([(0, 0, 0), (0, n, 0), (0, n, .22), (0, 0, .22)], COBALT, width=1.2)
    # Window on the left wall, night outside
    iso.poly([(0, 1.0, .95), (0, 2.4, .95), (0, 2.4, 2.15), (0, 1.0, 2.15)], '#1d2a8f')
    iso.poly([(0, 1.7, .95), (0, 1.7, 2.15)], 'none', width=1.2)
    x, y = iso.pt(0, 2.05, 1.95)
    svg.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="#f6f7f9"/>')
    # The KHS badge on the back wall: an ink frame with a lime hexagon
    iso.poly([(2.9, 0, 1.0), (4.1, 0, 1.0), (4.1, 0, 2.2), (2.9, 0, 2.2)], INK)
    cx, cz, r = 3.5, 1.6, .38
    hexagon = [(cx + r * math.cos(math.radians(a)), 0, cz + r * math.sin(math.radians(a))) for a in range(0, 360, 60)]
    iso.poly(hexagon, 'none', stroke=LIME, width=2)
    # Shelf with three coloured bins
    iso.box(.9, 0, 1.75, 1.5, .35, .08, '#e9ebef', '#c9cfdc', '#c9cfdc')
    for k, c in enumerate([TEAL, PINK, COBALT]):
        iso.box(1.0 + k * .45, .05, 1.83, .32, .25, .26, c, c, c)
    # Desk: top and four legs, a screen and a keyboard
    dx, dy, dw, dd, dh = 1.2, 2.0, 2.4, 1.1, .78
    for lx, ly in [(dx + .08, dy + .08), (dx + dw - .16, dy + .08), (dx + .08, dy + dd - .16), (dx + dw - .16, dy + dd - .16)]:
        iso.box(lx, ly, 0, .08, .08, dh, WOOD, WOOD, WOOD)
    iso.box(dx, dy, dh, dw, dd, .1, WOOD_TOP, WOOD, WOOD)
    iso.box(dx + .9, dy + .15, dh + .1, .65, .08, .5, INK, INK, INK)
    iso.poly([(dx + .95, dy + .23, dh + .17), (dx + 1.5, dy + .23, dh + .17), (dx + 1.5, dy + .23, dh + .55), (dx + .95, dy + .23, dh + .55)], '#0f1a4a', width=1)
    for k, c in enumerate([LIME, TEAL, PINK]):
        iso.poly([(dx + 1.02, dy + .23, dh + .48 - k * .1), (dx + 1.02 + .3 - k * .07, dy + .23, dh + .48 - k * .1)], 'none', stroke=c, width=1.6)
    iso.box(dx + .8, dy + .5, dh + .1, .85, .3, .04, '#e9ebef', '#c9cfdc', '#c9cfdc')
    iso.box(dx + 1.9, dy + .35, dh + .1, .18, .18, .22, PINK, PINK, '#d6336c')
    # Stool
    iso.box(2.5, 3.6, 0, .1, .1, .45, INK, INK, INK)
    iso.box(2.25, 3.35, .45, .6, .6, .1, COBALT, '#1f2fb8', '#1f2fb8')


# ── Assets ───────────────────────────────────────────────────────────────────


def glitch_title(svg, x, y, lines, size, p):
    """Big Anton words with the site's soft cobalt drop, splitting into pink and teal now and then."""
    lh = size * .92
    off = size * .025
    for i, line in enumerate(lines):
        svg.text(x + off, y + i * lh + off, line, 'display', size, p['title_shadow'])
    for i, line in enumerate(lines):
        svg.text(x, y + i * lh, line, 'display', size, p['text'])
    top = y - size * .86
    height = len(lines) * lh
    svg.defs.append(f'<clipPath id="band-a"><rect x="0" y="{top + height * .08:.1f}" width="{svg.w}" height="{height * .34:.1f}"/></clipPath>')
    svg.defs.append(f'<clipPath id="band-b"><rect x="0" y="{top + height * .55:.1f}" width="{svg.w}" height="{height * .3:.1f}"/></clipPath>')
    for band, cls, color in [('band-a', 'ga', PINK), ('band-b', 'gb', TEAL), ('band-a', 'gc', TEAL), ('band-b', 'gd', PINK)]:
        svg.add(f'<g clip-path="url(#{band})"><g class="{cls}">')
        for i, line in enumerate(lines):
            svg.text(x, y + i * lh, line, 'display', size, color)
        svg.add('</g></g>')
    svg.css.append(
        '.ga,.gb,.gc,.gd{opacity:0;animation:9s steps(1,end) infinite}'
        '.ga{animation-name:ga}.gb{animation-name:gb}.gc{animation-name:gc}.gd{animation-name:gd}'
        '@keyframes ga{0%{opacity:0}90%{opacity:1;transform:translate(-5px,0)}91%{transform:translate(4px,0)}92%{transform:translate(-2px,0)}93%{opacity:0;transform:none}}'
        '@keyframes gb{0%{opacity:0}90.5%{opacity:1;transform:translate(5px,0)}91.5%{transform:translate(-3px,0)}92.5%{opacity:0;transform:none}}'
        '@keyframes gc{0%{opacity:0}91%{opacity:.85;transform:translate(3px,0)}92%{opacity:0;transform:none}}'
        '@keyframes gd{0%{opacity:0}91.5%{opacity:.85;transform:translate(-4px,0)}92.5%{opacity:0;transform:none}}'
    )


def header(p, name):
    W, H = 880, 360
    svg = Svg(W, H, 'Abdullah Ilgaz: code artisan, RESTafarian, shutterbug. Konya, Türkiye.')
    svg.defs.append(f'<radialGradient id="glow" cx=".75" cy=".35" r=".7"><stop offset="0" stop-color="{p["glow"]}"/><stop offset="1" stop-color="{p["bg"]}"/></radialGradient>')
    cw, ch = W - 8, H - 8
    card(svg, 0, 0, cw, ch, 'url(#glow)', p['line'], p['shadow'], offset=8)
    svg.add(f'<svg x="2" y="2" width="{cw - 4}" height="{ch - 4}">{grain(svg, p["grain"])}</svg>')

    # Top bar: who and where, like the site's header
    svg.add(f'<rect x="28" y="24" width="14" height="14" fill="{LIME}" stroke="{p["line"]}" stroke-width="1.5"/>')
    svg.text(50, 36, 'theilgaz@khs', 'mono-bold', 13, p['text'])
    w = measure('KONYA, TR', 'mono-bold', 10, .08) + 16
    svg.add(f'<rect x="{cw - 28 - w}" y="22.75" width="{w}" height="18.5" fill="none" stroke="{p["line"]}" stroke-width="1.5"/>')
    svg.text(cw - 28 - w / 2, 35.5, 'KONYA, TR', 'mono-bold', 10, p['text'], .08, anchor='middle')

    # Prompt, title, tagline
    svg.text(28, 84, '$ cd ', 'mono', 14, p['muted'])
    px = 28 + measure('$ cd ', 'mono', 14)
    svg.text(px, 84, '~/konya/theilgaz', 'mono', 14, p['prompt'])
    px += measure('~/konya/theilgaz', 'mono', 14) + 4
    svg.add(f'<rect class="cursor" x="{px:.1f}" y="72" width="8" height="15" fill="{p["prompt"]}"/>')
    glitch_title(svg, 26, 162, ['ABDULLAH', 'ILGAZ'], 84, p)
    svg.text(28, 268, 'code artisan · RESTafarian · shutterbug', 'sans', 17, p['text'])

    # Status chips: a solid one for the role, an outlined one with a live dot
    x, y, h = 28, 288, 34
    label, value = 'NOW', '~/konya-hackerspace'
    lw = measure(label, 'mono-bold', 13, .06) + 26
    vw = measure(value, 'mono-bold', 12) + 24
    svg.add(f'<rect x="{x}" y="{y}" width="{lw + vw}" height="{h}" fill="{INK}" stroke="{p["line"]}" stroke-width="2"/>')
    svg.add(f'<rect x="{x + lw}" y="{y + 7}" width="1" height="{h - 14}" fill="#4d5570"/>')
    svg.text(x + 13, y + 22, label, 'mono-bold', 13, '#ffffff', .06)
    svg.text(x + lw + 12, y + 21.5, value, 'mono-bold', 12, LIME)
    x2 = x + lw + vw + 12
    label2, value2 = 'OPEN TO', 'collaboration'
    lw2 = measure(label2, 'mono-bold', 13, .06) + 26
    vw2 = measure(value2, 'mono-bold', 12) + 38
    svg.add(f'<rect x="{x2 + 1}" y="{y + 1}" width="{lw2 + vw2 - 2}" height="{h - 2}" fill="{p["surface"]}" stroke="{p["line"]}" stroke-width="2"/>')
    svg.add(f'<rect x="{x2 + lw2}" y="{y + 7}" width="1" height="{h - 14}" fill="{p["rule"]}"/>')
    svg.text(x2 + 13, y + 22, label2, 'mono-bold', 13, p['text'], .06)
    svg.add(f'<circle cx="{x2 + lw2 + 16}" cy="{y + h / 2}" r="4" fill="#0f9d58"/>')
    svg.text(x2 + lw2 + 26, y + 21.5, value2, 'mono-bold', 12, p['text'])

    svg.text(28, 342, 'load avg: tea, solder, code · utc+03:00', 'mono', 11, p['muted'])

    room(svg, 652, 118, 30, p)
    # The site's hint bar, pinned under the room
    hint = '$ _ build things, together'
    hw = measure(hint, 'mono', 11) + 22
    hx, hy = 676 - hw / 2, 308
    svg.add(f'<rect x="{hx + 4}" y="{hy + 4}" width="{hw}" height="24" fill="{COBALT}"/>')
    svg.add(f'<rect x="{hx}" y="{hy}" width="{hw}" height="24" fill="{INK}"/>')
    svg.text(hx + 11, hy + 16, '$ _', 'mono', 11, LIME)
    svg.text(hx + 11 + measure('$ _ ', 'mono', 11), hy + 16, 'build things, together', 'mono', 11, '#e9ebef')

    svg.css.append(CURSOR_CSS + REDUCED)
    svg.save(name)


def terminal(p, name):
    W = 880
    rows = [
        ('cmd', 'whoami'),
        ('out', 'Full-stack developer in Konya, Türkiye.'),
        ('out', 'Removing one small friction from someone\'s day is a win.'),
        ('gap', ''),
        ('cmd', 'cat now.txt'),
        ('kv', ('currently', 'user experience and developer experience')),
        ('kv', ('building', 'Konya Hackerspace, together with friends')),
        ('kv', ('sharing', 'code samples and write-ups')),
        ('kv', ('open to', 'open-source collaboration')),
        ('gap', ''),
        ('prompt', ''),
    ]
    lh, top = 24, 74
    body_h = sum(10 if k == 'gap' else lh for k, _ in rows)
    H = top + body_h + 66
    svg = Svg(W, H, 'whoami: full-stack developer in Konya, Türkiye. Currently UX and DX, building Konya Hackerspace.')
    cw, ch = W - 8, H - 8
    border = '#0c0f1a' if p is LIGHT else '#2a3048'
    card(svg, 0, 0, cw, ch, INK, border, COBALT, offset=8)
    svg.add(f'<line x1="2" y1="40" x2="{cw - 2}" y2="40" stroke="#1c2133" stroke-width="1"/>')
    svg.text(22, 26, 'theilgaz@khs:~', 'mono', 12, '#6b7390')
    svg.text(cw - 22, 26, 'zsh', 'mono', 12, '#6b7390', anchor='end')

    y, i = top, 0
    for kind, val in rows:
        if kind == 'gap':
            y += 10
            continue
        delay = i * .28
        svg.add(f'<g class="ln" style="animation-delay:{delay:.2f}s">')
        if kind in ('cmd', 'prompt'):
            svg.text(24, y, '$', 'mono-bold', 14, LIME)
            if val:
                svg.text(42, y, val, 'mono', 14, '#e9ebef')
            else:
                svg.add(f'<rect class="cursor" x="42" y="{y - 12}" width="8" height="15" fill="{LIME}"/>')
        elif kind == 'out':
            svg.text(42, y, val, 'mono', 14, '#c9cfdc')
        else:
            k, v = val
            svg.text(42, y, k, 'mono', 14, TEAL)
            svg.text(42 + 120, y, v, 'mono', 14, '#c9cfdc')
        svg.add('</g>')
        y += lh
        i += 1

    # Chips under the prompt, as on the site's terminal
    x = 24
    y = H - 8 - 50
    for chip in ['run mahfuz', 'cat fastql', 'ls ~/projects', 'ping ilg.az']:
        w = measure(chip, 'mono', 11) + 18
        svg.add(f'<rect x="{x + .5}" y="{y + .5}" width="{w}" height="23" fill="none" stroke="#2a3048"/>')
        svg.text(x + 9.5, y + 16, chip, 'mono', 11, '#9aa3bd')
        x += w + 8

    svg.css.append(
        '.ln{animation:ln .01s steps(1,end) both}@keyframes ln{from{opacity:0}to{opacity:1}}'
        + CURSOR_CSS + REDUCED
    )
    svg.save(name)


def section(p, name, title, cmd, note=''):
    W, H = 880, 74
    svg = Svg(W, H, title.title())
    svg.text(2, 20, '$ ', 'mono', 13, p['muted'])
    svg.text(2 + measure('$ ', 'mono', 13), 20, cmd, 'mono', 13, p['prompt'])
    size = 36
    off = size * .04
    svg.text(2 + off, 62 + off, title, 'display', size, p['title_shadow'])
    svg.text(2, 62, title, 'display', size, p['text'])
    if note:
        svg.text(W - 2, 60, note, 'mono', 12, p['muted'], anchor='end')
    svg.save(name)


STACK = [
    ('.NET', 'ink'), ('C#', 'ink'), ('TypeScript', 'ink'), ('React', 'ink'),
    ('Node.js', 'outline'), ('PostgreSQL', 'outline'), ('Redis', 'outline'), ('Docker', 'outline'),
    ('AWS', 'outline'), ('Azure', 'outline'), ('GCP', 'outline'),
]


def stack(p, name):
    W = 880
    svg = Svg(W, 64, 'Stack: ' + ', '.join(s for s, _ in STACK))
    x, y = 2, 4
    for label, kind in STACK:
        w = measure(label.upper(), 'mono-bold', 12, .08) + 16
        if x + w > W - 2:
            x, y = 2, y + 34
        tag(svg, x, y, label, p, kind, size=12)
        x += w + 8
    # Legend
    ly = y + 46
    svg.add(f'<rect x="2.75" y="{ly - 9.25}" width="10" height="10" fill="{p["line"]}" stroke="{p["line"]}" stroke-width="1.5"/>')
    svg.text(20, ly, 'daily drivers', 'mono', 11, p['muted'])
    lx = 20 + measure('daily drivers', 'mono', 11) + 18
    svg.add(f'<rect x="{lx + .75}" y="{ly - 9.25}" width="10" height="10" fill="none" stroke="{p["line"]}" stroke-width="1.5"/>')
    svg.text(lx + 18, ly, 'also in the toolbox', 'mono', 11, p['muted'])
    svg.h = ly + 6
    svg.save(name)


PROJECTS = [
    ('mahfuz', 'Your Quran companion: a clean, fast reading experience for the web.',
     [('Live', 'on'), ('RamadanHacks winner', 'ink'), ('TypeScript', 'outline')]),
    ('fastql', 'A lightweight, fluent SQL query builder for .NET.',
     [('.NET', 'outline'), ('C#', 'outline')]),
    ('winforms-dependency-injection', 'Practical dependency injection patterns demonstrated in .NET WinForms.',
     [('.NET', 'outline'), ('C#', 'outline')]),
    ('FGX', 'Repacked FGX components for Delphi, ready to drop into your project.',
     [('Delphi', 'outline')]),
]


def project(p, name, repo, desc, tags):
    W, H = 432, 212
    svg = Svg(W, H, f'{repo}: {desc}')
    cw, ch = W - 8, H - 8
    card(svg, 0, 0, cw, ch, p['surface'], p['line'], p['shadow'], offset=7)
    svg.text(22, 34, f'~/theilgaz/{repo}', 'mono', 12, p['prompt'])
    title = repo.upper()
    size = 34
    while measure(title, 'display', size) > cw - 44:
        size -= 1
    off = size * .04
    svg.text(21 + off, 76 + off, title, 'display', size, p['title_shadow'])
    svg.text(21, 76, title, 'display', size, p['text'])
    for i, line in enumerate(wrap(desc, 'sans', 14.5, cw - 44)[:3]):
        svg.text(22, 106 + i * 21, line, 'sans', 14.5, p['muted'])
    x, y = 22, ch - 22 - 22
    for label, kind in tags:
        x += tag(svg, x, y, label, p, kind) + 6
    svg.save(name)


RANK_URL = 'https://committers.top/rank_only/turkey.json'
RANK_USER = 'theilgaz'
RANKS = [('user', 'public commits'), ('user_public', 'public contributions'), ('user_private', 'all contributions')]


def fetch_rank():
    with urllib.request.urlopen(RANK_URL, timeout=30) as r:
        data = json.load(r)
    ranks = []
    for key, label in RANKS:
        listed = data[key]
        ranks.append((listed.index(RANK_USER) + 1 if RANK_USER in listed else None, len(listed), label))
    asof = datetime.datetime.strptime(data['data_asof'][:10], '%Y-%m-%d').strftime('%-d %b %Y')
    return ranks, asof


def rank(p, name, ranks, asof):
    W, H = 880, 208
    best = ', '.join(f'#{r} in {label}' for r, _, label in ranks if r)
    svg = Svg(W, H, f'committers.top Türkiye ranking: {best}. As of {asof}.')
    cw, ch = W - 8, H - 8
    card(svg, 0, 0, cw, ch, p['surface'], p['line'], p['shadow'], offset=7)
    svg.text(22, 34, '~/committers.top/turkey', 'mono', 12, p['prompt'])
    svg.text(cw - 22, 34, f'as of {asof}', 'mono', 11, p['muted'], anchor='end')
    col = (cw - 44) / len(ranks)
    for i, (r, listed, label) in enumerate(ranks):
        x = 22 + i * col + (14 if i else 0)
        if i:
            svg.add(f'<rect x="{22 + i * col:.1f}" y="58" width="1.5" height="92" fill="{p["rule"]}"/>')
        value = f'#{r}' if r else f'{listed}+'
        size = 66
        off = size * .04
        svg.text(x + off, 124 + off, value, 'display', size, p['title_shadow'])
        svg.text(x, 124, value, 'display', size, p['text'])
        svg.text(x + 2, 148, label.upper(), 'mono-bold', 11, p['text'], .08)
    svg.text(22, ch - 20, 'most active github users in türkiye · refreshed daily', 'mono', 11, p['muted'])
    svg.save(name)


def main():
    ranks, asof = fetch_rank()
    for p, suffix in [(LIGHT, 'light'), (DARK, 'dark')]:
        header(p, f'header-{suffix}.svg')
        terminal(p, f'about-{suffix}.svg')
        stack(p, f'stack-{suffix}.svg')
        section(p, f'h-about-{suffix}.svg', 'ABOUT', 'whoami')
        section(p, f'h-stack-{suffix}.svg', 'STACK', 'ls ~/tools', '# what the hands reach for')
        section(p, f'h-projects-{suffix}.svg', 'SELECTED PROJECTS', 'ls ~/projects', '# 4 of 114')
        section(p, f'h-rank-{suffix}.svg', 'RANKING', 'rank --country tr', '# via committers.top')
        rank(p, f'rank-{suffix}.svg', ranks, asof)
        for repo, desc, tags in PROJECTS:
            project(p, f'p-{repo.lower()}-{suffix}.svg', repo, desc, tags)
    print('\n'.join(sorted(f'{f.name:34} {f.stat().st_size / 1024:6.1f} KB' for f in OUT.glob('*.svg'))))


if __name__ == '__main__':
    main()
