"""
Resolución de rutas que funciona tanto corriendo con Python como dentro
de un .exe de PyInstaller ("congelado").

- frozen_app_dir: dónde viven los datos que se ESCRIBEN (config, historial).
  Congelado → al lado del .exe. Normal → al lado del código.
- resource_dir: dónde viven los recursos de SOLO LECTURA empaquetados (web/).
  Congelado → carpeta temporal _MEIPASS. Normal → al lado del código.
"""
from pathlib import Path


def frozen_app_dir(frozen, exe_dir, file_dir):
    """Carpeta para datos escribibles. Lógica pura (testeable)."""
    return Path(exe_dir) if frozen else Path(file_dir)


def resource_dir(meipass, file_dir):
    """Carpeta de recursos de solo lectura. Lógica pura (testeable)."""
    return Path(meipass) if meipass else Path(file_dir)
