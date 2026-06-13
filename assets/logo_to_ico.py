"""
Convierte assets/logo.png en assets/icon.ico (cuadrado, multi-tamaño).
Centra el logo en un lienzo cuadrado con fondo negro (como el logo).
Correr:  python assets/logo_to_ico.py
"""
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
BG = (10, 10, 12, 255)

src = Image.open(HERE / 'logo.png').convert('RGBA')
side = max(src.size)
canvas = Image.new('RGBA', (side, side), BG)
canvas.paste(src, ((side - src.width) // 2, (side - src.height) // 2), src)

icon = canvas.resize((256, 256), Image.LANCZOS)
icon.save(HERE / 'icon.ico', format='ICO',
          sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
icon.save(HERE / 'icon_preview.png')
print('icon.ico generado desde logo.png')
