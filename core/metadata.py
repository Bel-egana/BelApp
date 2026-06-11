"""
Metadata de audio: detección de extensiones y lectura/escritura de tags
ID3 (mp3/wav/aiff) y Vorbis (flac) usando mutagen.

Si mutagen no está instalado, MUTAGEN_OK queda en False y las funciones
de tags degradan con elegancia (read devuelve {}, write devuelve False).
"""
from pathlib import Path

try:
    from mutagen.id3 import (ID3, TALB, TCON, TDRC, TIT2, TPE1, TPUB,
                             ID3NoHeaderError)
    from mutagen.flac import FLAC
    MUTAGEN_OK = True
except ImportError:
    MUTAGEN_OK = False

AUDIO_EXTS = {'.mp3', '.wav', '.aiff', '.flac', '.m4a'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}


def is_audio(name):
    return Path(name).suffix.lower() in AUDIO_EXTS


def is_image(name):
    return Path(name).suffix.lower() in IMAGE_EXTS


def read_id3(filepath):
    """Lee los tags del archivo. Devuelve solo los campos con valor."""
    tags = {}
    if not MUTAGEN_OK:
        return tags
    try:
        ext = filepath.suffix.lower()
        if ext in ('.mp3', '.wav', '.aiff'):
            audio = ID3(str(filepath))

            def g(k):
                v = audio.get(k)
                return str(v.text[0]).strip() if v and hasattr(v, 'text') and v.text else ''

            tags = {'artist': g('TPE1') or g('TPE2'), 'title': g('TIT2'),
                    'album': g('TALB'), 'label': g('TPUB'), 'genre': g('TCON'),
                    'year': str(g('TDRC') or g('TYER'))[:4]}
        elif ext == '.flac':
            audio = FLAC(str(filepath))

            def gf(k):
                return (audio.get(k.lower()) or [''])[0].strip()

            tags = {'artist': gf('artist'), 'title': gf('title'), 'album': gf('album'),
                    'label': gf('organization') or gf('label'), 'genre': gf('genre'),
                    'year': (gf('date') or gf('year'))[:4]}
    except Exception:
        pass
    return {k: v for k, v in tags.items() if v}


def write_id3_tags(filepath, artist, title, album, label, genre, year):
    """Escribe los tags. Devuelve True si pudo, False si no."""
    if not MUTAGEN_OK:
        return False
    try:
        ext = filepath.suffix.lower()
        if ext in ('.mp3', '.wav', '.aiff'):
            try:
                tags = ID3(str(filepath))
            except ID3NoHeaderError:
                tags = ID3()
            tags['TIT2'] = TIT2(encoding=3, text=title)
            tags['TPE1'] = TPE1(encoding=3, text=artist)
            tags['TALB'] = TALB(encoding=3, text=album)
            tags['TPUB'] = TPUB(encoding=3, text=label)
            tags['TCON'] = TCON(encoding=3, text=genre)
            tags['TDRC'] = TDRC(encoding=3, text=year)
            tags.save(str(filepath))
            return True
        elif ext == '.flac':
            audio = FLAC(str(filepath))
            audio['title'] = title
            audio['artist'] = artist
            audio['album'] = album
            audio['organization'] = label
            audio['genre'] = genre
            audio['date'] = year
            audio.save()
            return True
    except Exception:
        return False
    return False
