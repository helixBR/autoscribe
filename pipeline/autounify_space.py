"""
autounify_space.py — Unificador de imágenes para el motor OCR.space
====================================================================
Conectado a: ocr_space.py  (importado por ocr_space.py y re-exportado)
Llamado por: AutoScribe_v1_0.py → via ocr_space.py → UnifyWorkerSpace

Responsabilidad:
    Unificar (stitch) las páginas de una carpeta de manga/manhwa/manhwa
    usando autounify.py, produciendo imágenes lira verticales listas para
    ser procesadas por OCRWorkerSpace (ocr_space.py).

Interfaz compatible con UnifyWorker de Motor_Paddle_OCR.py:
    Señales:
        progress(int)         0-100
        status_msg(str)       mensaje para status bar
        finished(List[str])   paths de imágenes generadas
        error(str)            descripción del error

Diferencias respecto al UnifyWorker original:
    · No depende de PaddleOCR ni de ningún modelo local.
    · Configurable: puede saltar la unificación si las imágenes ya son
      liras (modo bypass), útil para manhwas que ya vienen en tiras largas.
    · Expone validate_folder() para chequear antes de empezar.

Estructura esperada de carpeta de entrada:
    mi_manga/
        001.jpg
        002.jpg
        ...
        999.jpg   ← imágenes individuales a unificar

Salida (dentro de la misma carpeta o en subcarpeta _unified/):
    mi_manga/_unified/
        lira_001.jpg
        lira_002.jpg
        ...
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt6.QtCore import QThread, pyqtSignal

# ── Import autounify original (no modificado) ─────────────────────────────────
try:
    from pipeline.autounify import autounify_img_in_folder
    _AUTOUNIFY_OK = True
except ImportError:
    _AUTOUNIFY_OK = False
    autounify_img_in_folder = None  # type: ignore

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────
_SUPPORTED_IMG = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif"}

# Tamaño máximo por imagen para tier free de OCR.space (1 MB)
# Para PRO el límite es 5 MB.
FREE_SIZE_LIMIT_BYTES = 1 * 1024 * 1024   # 1 MB
PRO_SIZE_LIMIT_BYTES  = 5 * 1024 * 1024   # 5 MB

# Subcarpeta donde se guardan las liras unificadas
_UNIFIED_SUBDIR = "_unified_space"


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _natural_key(path: Path) -> list:
    """Ordena archivos de forma natural (001 < 002 < 010 < 100)."""
    import re
    parts = re.split(r"(\d+)", path.stem)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def scan_images(folder: Path) -> List[Path]:
    """Devuelve las imágenes de la carpeta ordenadas naturalmente."""
    imgs = [f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in _SUPPORTED_IMG]
    return sorted(imgs, key=_natural_key)


def validate_folder(folder: str | Path) -> Tuple[bool, str]:
    """
    Valida que la carpeta sea apta para procesar.
    Returns: (es_válida, mensaje descriptivo)
    """
    p = Path(folder)
    if not p.exists():
        return False, f"La carpeta no existe: {p}"
    if not p.is_dir():
        return False, f"No es una carpeta: {p}"

    imgs = scan_images(p)
    if not imgs:
        return False, f"Sin imágenes soportadas en: {p.name}"

    # Verificar que al menos una imagen sea legible
    try:
        imgs[0].stat()
    except OSError as e:
        return False, f"Sin acceso a las imágenes: {e}"

    return True, f"✓ {len(imgs)} imágenes encontradas en {p.name}"


def check_image_sizes(images: List[Path], limit_bytes: int = FREE_SIZE_LIMIT_BYTES
                      ) -> List[Path]:
    """
    Filtra y devuelve las imágenes que superan el límite de tamaño.
    Útil para advertir al usuario antes de procesar.
    """
    return [img for img in images if img.stat().st_size > limit_bytes]


# ─────────────────────────────────────────────────────────────────────────────
#  UNIFY WORKER — COMPATIBLE CON AUTOSCRIBE
# ─────────────────────────────────────────────────────────────────────────────
class UnifyWorkerSpace(QThread):
    """
    Worker Qt compatible con UnifyWorker de Motor_Paddle_OCR.py.
    Unifica imágenes de manga/manhwa en liras verticales usando autounify.py,
    preparándolas para ser enviadas a OCR.space.

    Modos de operación:
        "unify"  (default) → llama autounify_img_in_folder (stitch)
        "bypass"           → pasa imágenes directamente sin unificar
                             (útil para manhwas ya en tiras largas)

    Señales (idénticas a UnifyWorker de Motor_Paddle_OCR):
        progress(int)          0-100
        status_msg(str)        mensaje corto para status bar
        finished(List[str])    paths de las imágenes listas (unificadas o no)
        error(str)             descripción del error
    """

    progress   = pyqtSignal(int)
    status_msg = pyqtSignal(str)
    finished   = pyqtSignal(list)    # List[str] paths
    error      = pyqtSignal(str)

    def __init__(
        self,
        src_folder:   str,
        ocr_lang:     str  = "jpn",   # idioma (para log; unify no lo usa)
        max_height:   int  = 5000,    # altura máxima de lira en píxeles
        auto_unify:   bool = True,    # True = unificar | False = bypass
        save_remnant: bool = True,    # guardar "sobrante" si no llena una lira
        mode:         str  = "unify", # "unify" | "bypass"
        is_pro:       bool = False,   # True → no advertir sobre límite 1MB
        parent               = None,
    ):
        super().__init__(parent)
        self._src         = Path(src_folder)
        self._lang        = ocr_lang
        self._max_h       = max_height
        self._auto_unify  = auto_unify
        self._remnant     = save_remnant
        self._mode        = mode if auto_unify else "bypass"
        self._size_limit  = PRO_SIZE_LIMIT_BYTES if is_pro else FREE_SIZE_LIMIT_BYTES
        self._cancelled   = False
        self._out_dir     = self._src / _UNIFIED_SUBDIR

    def cancel(self):
        self._cancelled = True

    # ── HILO PRINCIPAL ────────────────────────────────────────────────────────
    def run(self):
        try:
            ok, msg = validate_folder(str(self._src))
            if not ok:
                self.error.emit(msg)
                return

            self.status_msg.emit(f"Preparando: {self._src.name}…")
            self.progress.emit(5)

            if self._mode == "bypass":
                self._run_bypass()
            else:
                self._run_unify()

        except Exception as ex:
            self.error.emit(f"UnifyWorkerSpace: {ex}")

    # ── MODO BYPASS (sin unificar) ────────────────────────────────────────────
    def _run_bypass(self):
        """
        Modo bypass: pasa las imágenes directamente sin stitch.
        Útil cuando el contenido ya viene en tiras largas (p.ej. webtoons).
        """
        images = scan_images(self._src)
        if not images:
            self.error.emit(f"Sin imágenes en: {self._src.name}")
            return

        self.status_msg.emit(f"Bypass: {len(images)} imágenes → OCR.space")
        self.log_size_warnings(images)

        total = len(images)
        paths: List[str] = []
        for i, img in enumerate(images):
            if self._cancelled:
                self.error.emit("Cancelado por el usuario")
                return
            paths.append(str(img))
            self.progress.emit(int((i + 1) / total * 100))

        self.finished.emit(paths)

    # ── MODO UNIFY (con autounify.py) ─────────────────────────────────────────
    def _run_unify(self):
        """
        Modo unify: llama autounify_img_in_folder para hacer stitch vertical
        de las páginas individuales en liras.
        """
        if not _AUTOUNIFY_OK:
            # Si autounify no está disponible, hacer bypass como fallback
            self.status_msg.emit("⚠ autounify.py no disponible — usando bypass")
            self._run_bypass()
            return

        self.status_msg.emit(f"Unificando: {self._src.name}…")

        # Preparar carpeta de salida limpia
        if self._out_dir.exists():
            shutil.rmtree(self._out_dir)
        self._out_dir.mkdir(parents=True)

        self.progress.emit(10)

        try:
            # Llamar a autounify original
            # autounify_img_in_folder(folder, max_height, ocr_lang, safe_cut, save_remnant, ...)
            # Retorna lista de paths de las liras generadas
            result = autounify_img_in_folder(
                str(self._src),
                max_height=self._max_h,
                ocr_lang=self._lang,
                save_remnant=self._remnant,
            )

            # autounify puede retornar:
            # - List[str]  → paths directamente
            # - List[Path] → paths como Path objects
            # - None       → usamos scan de la carpeta output como fallback
            if result and len(result) > 0:
                paths = [str(p) for p in result]
            else:
                # Fallback: escanear la carpeta de salida
                paths = [str(p) for p in scan_images(self._out_dir)]

            if not paths:
                # Si autounify no generó nada en _out_dir, buscar en src también
                # (algunos autounify guardan in-place)
                in_place = [str(p) for p in scan_images(self._src)
                            if _UNIFIED_SUBDIR not in str(p)]
                if in_place:
                    paths = in_place
                else:
                    self.error.emit("Autounify no generó imágenes")
                    return

            self.log_size_warnings(paths)
            self.progress.emit(90)
            self.status_msg.emit(f"✓ {len(paths)} liras generadas → enviando a OCR.space")
            self.progress.emit(100)
            self.finished.emit(paths)

        except Exception as ex:
            # Si autounify falla, intentar bypass como último recurso
            self.status_msg.emit(f"⚠ Unify falló ({ex}) — intentando bypass…")
            self._run_bypass()

    # ── UTILIDADES ────────────────────────────────────────────────────────────
    def log_size_warnings(self, images):
        """
        Emite advertencias para imágenes que superan el límite de OCR.space.
        No bloquea el proceso, solo informa.
        """
        paths = [Path(p) for p in images] if images and isinstance(images[0], str) else images
        oversized = check_image_sizes(paths, self._size_limit)
        if oversized:
            limit_mb = self._size_limit // (1024 * 1024)
            self.status_msg.emit(
                f"⚠ {len(oversized)} imágenes superan {limit_mb}MB — "
                f"pueden fallar en OCR.space tier free"
            )