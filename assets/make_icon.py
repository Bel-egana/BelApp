"""
Genera assets/icon.ico — ícono de BelApp inspirado en el logo neón:
"B" de CONTORNO + nota musical + barras de ecualizador segmentadas,
en degradé amarillo→rosa con glow, sobre negro redondeado.
Correr:  python assets/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 256
BG = (10, 10, 12, 255)
YELLOW = (255, 235, 0)     # arriba
PINK = (255, 40, 130)      # abajo


def vgrad(w, h, top, bottom):
    g = Image.new('RGB', (w, h))
    gd = ImageDraw.Draw(g)
    for y in range(h):
        t = y / (h - 1)
        gd.line([(0, y), (w, y)],
                fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return g


def load(*names, size=160):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except Exception:
            pass
    return ImageFont.load_default()


# ── Máscara con todas las formas (blanco) ────────────────────────────────────
mask = Image.new('L', (S, S), 0)
m = ImageDraw.Draw(mask)

# Ecualizador segmentado (3 columnas de bloquecitos), izquierda
cols = [(34, 7), (58, 11), (82, 8)]      # (x, cantidad de segmentos)
seg_w, seg_h, gap, base = 17, 11, 6, 214
for x, n in cols:
    for i in range(n):
        y1 = base - (i + 1) * seg_h - i * gap
        m.rounded_rectangle([x, y1, x + seg_w, y1 + seg_h], radius=4, fill=255)

# "B" de contorno (hollow) a la derecha
bfont = load('C:/Windows/Fonts/arialbd.ttf', size=180)
m.text((108, 130), 'B', font=bfont, fill=0, stroke_width=7, stroke_fill=255,
       anchor='lm')

# Nota musical dentro de la B
nfont = load('C:/Windows/Fonts/seguisym.ttf', 'C:/Windows/Fonts/seguisym.ttf',
             size=104)
m.text((150, 138), '♪', font=nfont, fill=255, anchor='mm')

# ── Pintar con degradé + glow + componer ─────────────────────────────────────
grad = vgrad(S, S, YELLOW, PINK).convert('RGBA')
shapes = Image.new('RGBA', (S, S), (0, 0, 0, 0))
shapes.paste(grad, (0, 0), mask)

glow = shapes.filter(ImageFilter.GaussianBlur(9))

icon = Image.new('RGBA', (S, S), (0, 0, 0, 0))
ImageDraw.Draw(icon).rounded_rectangle([0, 0, S - 1, S - 1], radius=46, fill=BG)
for _ in range(3):
    icon.alpha_composite(glow)
icon.alpha_composite(shapes)

out = Path(__file__).parent / 'icon.ico'
icon.save(out, format='ICO',
          sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
icon.save(Path(__file__).parent / 'icon_preview.png')
print('Ícono generado en', out)
