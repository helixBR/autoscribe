"""
ocr_space.py — Motor OCR via OCR.space API para AutoScribe v1.0
================================================================
Motor independiente compatible con la interfaz de Motor_Paddle_OCR.py.
AutoScribe lo llama directamente para extraer texto de mangas/manhwas/manhuas.

NUEVO v1.1 — Pipeline inteligente:
  En lugar de mandar la imagen completa a OCR.space, el worker ahora
  ejecuta el mismo flujo de 3 pasos que el motor híbrido:
    1. unify        → une las imágenes de la carpeta en liras (UnifyWorkerSpace)
    2. paddle_crop  → usa PaddleOCR para detectar cuadros de texto y recortarlos
    3. ocr_space    → envía cada recorte a OCR.space (imágenes más pequeñas,
                       más precisión, menos consumo de cuota)

  Esto reduce drásticamente el tamaño de cada request (recortes ≈ 20-80 KB
  en lugar de liras de ≈ 500 KB-5 MB) y mejora la tasa de reconocimiento
  porque OCR.space recibe una sola burbuja/viñeta por request.

  Si PaddleOCR no está disponible, el modo FALLBACK envía la imagen completa
  como antes (comportamiento v1.0).

Señales QThread expuestas (idénticas a OCRWorker de Motor_Paddle_OCR):
    progress(int)        → 0-100
    status_msg(str)      → mensaje corto para status bar
    log_msg(str)         → entrada detallada para LogPanel
    finished_ok(str)     → path del .txt / .docx generado
    error(str)           → mensaje de error
    stats_update(dict)   → {"images":N, "chars":N, "words":N, "total":N}

Re-exporta desde autounify_space.py:
    UnifyWorkerSpace     → compatible con UnifyWorker de Motor_Paddle_OCR
"""

from __future__ import annotations

import base64
import io
import re
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from PIL import Image as PILImage
from PyQt6.QtCore import QThread, pyqtSignal

# ── Re-exportar UnifyWorkerSpace desde autounify_space ────────────────────────
from pipeline.autounify_space import UnifyWorkerSpace  # noqa: F401  (re-export)

# ── Importar utilidades de detección de cajas desde crop_paddle ───────────────
try:
    from ocr.crop_paddle import (
        _get_paddle_det,
        _parse_paddle_result,
        _box_area,
        sort_boxes_for_reading,
        crop_box,
        MIN_BOX_AREA,
        CROP_PADDING,
    )
    _PADDLE_CROP_OK = True
except ImportError:
    _PADDLE_CROP_OK = False

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────
OCR_SPACE_URL = "https://api.ocr.space/parse/image"

_FREE_DELAY  = 0.5    # segundos entre requests (tier gratuito)
_PRO_DELAY   = 0.05   # segundos entre requests (tier pro)
_TIMEOUT     = 60     # segundos de timeout por request

# Mapa de códigos de idioma AutoScribe → OCR.space
LANG_MAP: dict[str, str] = {
    "ch":     "chs",   # Chinese Simplified
    "ch_tra": "cht",   # Chinese Traditional
    "en":     "eng",   # English
    "ja":     "jpn",   # Japanese
    "japan":  "jpn",   # alias PaddleOCR
    "ko":     "kor",   # Korean
    "korean": "kor",   # alias PaddleOCR
    "es":     "spa",   # Spanish
    "fr":     "fre",   # French
    "de":     "ger",   # German
    "ru":     "rus",   # Russian
    "pt":     "por",   # Portuguese
    "ar":     "ara",   # Arabic
    "it":     "ita",   # Italian
    "nl":     "dut",   # Dutch
    "pl":     "pol",   # Polish
    "tr":     "tur",   # Turkish
    # Passthroughs
    "eng": "eng", "jpn": "jpn", "kor": "kor",
    "spa": "spa", "chs": "chs", "cht": "cht",
}

_SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif", ".webp"}

# Tamaño máximo de recorte para enviar como JPEG a OCR.space (en bytes)
_MAX_CROP_BYTES = 900_000   # ~900 KB (margen bajo el límite free de 1 MB)
_CROP_QUALITY   = 92        # calidad JPEG para recortes


# ─────────────────────────────────────────────────────────────────────────────
#  CLIENTE API PURO (sin Qt, testeable de forma independiente)
# ─────────────────────────────────────────────────────────────────────────────
class OCRSpaceClient:
    """
    Cliente REST para la API de OCR.space.
    Sin dependencias Qt: se puede usar en scripts, tests, o desde workers.
    """

    def __init__(self, api_key: str, engine: int = 2, is_pro: bool = False):
        self.api_key  = api_key
        self.engine   = engine
        self.delay    = _PRO_DELAY if is_pro else _FREE_DELAY
        self._session = requests.Session()

    def ocr_file(self, path: Path, lang: str = "eng",
                 detect_orient: bool = True, scale: bool = True) -> str:
        if not path.exists():
            raise FileNotFoundError(f"Imagen no encontrada: {path}")
        payload = self._build_payload(path, lang, detect_orient, scale)
        resp    = self._session.post(OCR_SPACE_URL, data=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        return self._parse_response(resp.json())

    def ocr_pil_image(self, image: PILImage.Image, lang: str = "eng",
                      detect_orient: bool = False) -> str:
        """
        Envía una PIL.Image directamente (sin guardar a disco).
        Útil para enviar recortes de memoria sin I/O intermedio.
        """
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=_CROP_QUALITY)
        raw = buf.getvalue()

        # Si el recorte es demasiado grande, reducir calidad
        if len(raw) > _MAX_CROP_BYTES:
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=70)
            raw = buf.getvalue()

        b64 = base64.b64encode(raw).decode()
        payload = {
            "apikey":            self.api_key,
            "base64Image":       f"data:image/jpeg;base64,{b64}",
            "language":          lang,
            "OCREngine":         str(self.engine),
            "isOverlayRequired": "false",
            "detectOrientation": str(detect_orient).lower(),
            "scale":             "true",
        }
        resp = self._session.post(OCR_SPACE_URL, data=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        return self._parse_response(resp.json())

    def test_connection(self) -> tuple[bool, str]:
        try:
            b64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQV"
                   "R42mP8/5+hHgAHggJ/PchI6QAAAABJRU5ErkJggg==")
            payload = {
                "apikey":      self.api_key,
                "base64Image": f"data:image/png;base64,{b64}",
                "language":    "eng",
                "OCREngine":   "1",
            }
            r = self._session.post(OCR_SPACE_URL, data=payload, timeout=15)
            r.raise_for_status()
            d = r.json()
            if d.get("IsErroredOnProcessing"):
                msgs = d.get("ErrorMessage", ["Error desconocido"])
                msg  = msgs[0] if isinstance(msgs, list) else str(msgs)
                return False, f"✗ API error: {msg}"
            return True, "✓ Conexión exitosa con OCR.space"
        except requests.HTTPError as e:
            return False, f"✗ HTTP {e.response.status_code}: verifica tu API key"
        except Exception as e:
            return False, f"✗ Error de conexión: {e}"

    def _build_payload(self, path: Path, lang: str,
                       detect_orient: bool, scale: bool) -> dict:
        """
        Lee la imagen y la comprime si supera _MAX_CROP_BYTES para evitar
        el error 413 (Payload Too Large) tanto en tier free como en PRO.
        """
        with open(path, "rb") as f:
            raw = f.read()

        # ── Comprimir si supera el límite ────────────────────────────────────
        if len(raw) > _MAX_CROP_BYTES:
            try:
                img = PILImage.open(path).convert("RGB")
                # Primer intento: reducir calidad JPEG
                for quality in (85, 70, 55, 40):
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=quality)
                    raw = buf.getvalue()
                    if len(raw) <= _MAX_CROP_BYTES:
                        break
                # Segundo intento: también reducir resolución al 75%
                if len(raw) > _MAX_CROP_BYTES:
                    w, h = img.size
                    for scale_f in (0.75, 0.50, 0.35):
                        small = img.resize(
                            (int(w * scale_f), int(h * scale_f)),
                            PILImage.LANCZOS
                        )
                        buf = io.BytesIO()
                        small.save(buf, format="JPEG", quality=70)
                        raw = buf.getvalue()
                        small.close()
                        if len(raw) <= _MAX_CROP_BYTES:
                            break
                img.close()
            except Exception:
                pass  # si PIL falla, intentar enviar el original de todas formas

        ext  = path.suffix.lower().lstrip(".")
        mime = "image/jpeg" if len(raw) < _MAX_CROP_BYTES * 1.1 else f"image/{'jpeg' if ext == 'jpg' else ext}"
        b64  = base64.b64encode(raw).decode()
        return {
            "apikey":            self.api_key,
            "base64Image":       f"data:{mime};base64,{b64}",
            "language":          lang,
            "OCREngine":         str(self.engine),
            "isOverlayRequired": "false",
            "detectOrientation": str(detect_orient).lower(),
            "scale":             str(scale).lower(),
            "isTable":           "false",
        }

    @staticmethod
    def _parse_response(data: dict) -> str:
        if data.get("IsErroredOnProcessing"):
            msgs = data.get("ErrorMessage", ["Error desconocido"])
            raise RuntimeError("; ".join(msgs) if isinstance(msgs, list) else str(msgs))
        results = data.get("ParsedResults") or []
        if not results:
            return ""
        parts = []
        for r in results:
            text = r.get("ParsedText", "").strip()
            if text:
                parts.append(text)
        return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
#  PIPELINE: PaddleOCR crop → OCR.space
# ─────────────────────────────────────────────────────────────────────────────
def _extract_crops_from_image(
    image_path: Path,
    ocr_lang: str,
    reading_order: str,
    log_cb,
) -> List[PILImage.Image]:
    """
    Usa PaddleOCR para detectar cuadros de texto en image_path y retorna
    la lista de recortes PIL en el orden correcto de lectura.
    Retorna lista vacía si PaddleOCR no está disponible o no detecta nada.
    """
    def _log(m):
        if log_cb: log_cb(m)

    if not _PADDLE_CROP_OK:
        _log("[OCR.space] PaddleOCR no disponible — modo fallback (imagen completa)")
        return []

    ocr = _get_paddle_det(ocr_lang)
    if ocr is None:
        _log("[OCR.space] PaddleOCR no instalado — modo fallback")
        return []

    try:
        result = ocr.ocr(str(image_path), cls=False)
    except Exception as e:
        _log(f"[OCR.space] Error PaddleOCR en {image_path.name}: {e}")
        return []

    raw_boxes   = _parse_paddle_result(result)
    valid_boxes = [b for b in raw_boxes if _box_area(b) >= MIN_BOX_AREA]
    _log(f"[OCR.space] Paddle detectó {len(raw_boxes)} bloques → {len(valid_boxes)} válidos")

    if not valid_boxes:
        _log("[OCR.space] Sin bloques — modo fallback (imagen completa)")
        return []

    ordered = sort_boxes_for_reading(
        valid_boxes,
        reading_order=reading_order,
    )

    try:
        full_image = PILImage.open(image_path).convert("RGB")
    except Exception as e:
        _log(f"[OCR.space] Error abriendo {image_path.name}: {e}")
        return []

    crops: List[PILImage.Image] = []
    for box in ordered:
        crop = crop_box(full_image, box, padding=CROP_PADDING)
        if crop is not None:
            crops.append(crop)

    full_image.close()
    _log(f"[OCR.space] {len(crops)} recortes listos para enviar")
    return crops


# ─────────────────────────────────────────────────────────────────────────────
#  OCR WORKER COMPATIBLE CON AUTOSCRIBE
# ─────────────────────────────────────────────────────────────────────────────
class OCRWorkerSpace(QThread):
    """
    Worker Qt compatible con OCRWorker de Motor_Paddle_OCR.py.

    Pipeline v1.1:
      Para cada imagen unificada:
        1. PaddleOCR detecta cuadros de texto y los recorta en orden de lectura.
        2. Cada recorte se envía a OCR.space como JPEG en memoria (sin guardar disco).
        3. El texto de todos los recortes se ensambla en orden.

      Si PaddleOCR no está disponible: FALLBACK → envía imagen completa (v1.0).

    Señales (misma interfaz que OCRWorker original):
        progress(int)       0→100
        status_msg(str)     status bar
        log_msg(str)        log panel
        finished_ok(str)    path .txt / .docx generado
        error(str)          descripción del error
        stats_update(dict)  {"images","chars","words","total"}
    """

    progress     = pyqtSignal(int)
    status_msg   = pyqtSignal(str)
    log_msg      = pyqtSignal(str)
    finished_ok  = pyqtSignal(str)
    error        = pyqtSignal(str)
    stats_update = pyqtSignal(dict)

    def __init__(
        self,
        image_paths:   List[Path],
        output_folder: str,
        fmt:           str,
        translate_to:  str,
        case_mode:     str,
        folder_name:   str,
        ocr_lang:      str,
        api_key:       str,
        engine:        int   = 2,
        is_pro:        bool  = False,
        keep_sfx:      bool  = False,
        reading_order: str   = "rtl",   # "rtl" manga | "ltr" manhwa
        use_crop_pipeline: bool = True, # False = modo fallback (imagen completa)
        parent               = None,
    ):
        super().__init__(parent)
        self._paths        = image_paths
        self._out_dir      = Path(output_folder)
        self._fmt          = fmt
        self._translate    = translate_to
        self._case         = case_mode
        self._name         = folder_name
        self._ocr_lang_raw = ocr_lang
        self._lang         = LANG_MAP.get(ocr_lang, "eng")
        self._keep_sfx     = keep_sfx
        self._reading      = reading_order
        self._use_crop     = use_crop_pipeline
        self._cancelled    = False
        self._client       = OCRSpaceClient(api_key, engine, is_pro)

        self._total_chars  = 0
        self._total_words  = 0

    def cancel(self):
        self._cancelled = True

    # ── HILO PRINCIPAL ────────────────────────────────────────────────────────
    def run(self):
        try:
            self._out_dir.mkdir(parents=True, exist_ok=True)
            fmt_lower = self._fmt.lower().replace(".", "")
            out_file  = self._out_dir / f"{self._name}.{fmt_lower}"

            total = len(self._paths)
            if total == 0:
                self.error.emit("Sin imágenes para procesar")
                return

            pipeline_mode = (
                "PaddleOCR→Crop→OCR.space" if (_PADDLE_CROP_OK and self._use_crop)
                else "Directo a OCR.space (sin crop)"
            )
            self.log_msg.emit(
                f"🌐 Motor: OCR.space Engine {self._client.engine} "
                f"| Lang: {self._lang} | Pipeline: {pipeline_mode}"
            )
            self.log_msg.emit(f"📁 Salida: {out_file}")

            plain_lines: List[str] = []   # para DOCX
            blocks:      List[str] = []   # para TXT

            for i, path in enumerate(self._paths):
                if self._cancelled:
                    self.error.emit("Proceso cancelado por el usuario")
                    return

                self.status_msg.emit(f"OCR.space [{i+1}/{total}]: {path.name}")
                self.log_msg.emit(f"  ↳ Procesando {path.name}…")

                # Elegir pipeline: crop inteligente vs. imagen completa
                if _PADDLE_CROP_OK and self._use_crop:
                    text = self._process_with_crop_pipeline(path)
                else:
                    text = self._ocr_single_file(path)

                text = self._post_process(text)

                self._total_chars += len(text)
                self._total_words += len(text.split())

                # Acumular para DOCX (texto limpio sin marcadores HTML)
                plain_lines.append(f"── {path.name} ──")
                plain_lines.extend(text.split("\n") if text else ["(sin texto detectado)"])
                plain_lines.append("")

                # Bloque para TXT
                block = self._format_block(i + 1, path.name, text, self._fmt)
                blocks.append(block)

                pct = int((i + 1) / total * 100)
                self.progress.emit(pct)
                self.stats_update.emit({
                    "images": i + 1,
                    "chars":  self._total_chars,
                    "words":  self._total_words,
                    "total":  total,
                })

                if i < total - 1:
                    time.sleep(self._client.delay)

            # ── Escribir archivo final ────────────────────────────────────
            # FIX: asegurar que nunca se guarde un DOCX vacío
            if not plain_lines or all(not l.strip() for l in plain_lines):
                plain_lines = ["(Sin texto detectado en ninguna imagen)"]

            if fmt_lower == "docx":
                self._save_docx(out_file, plain_lines)
            else:
                final = "\n\n".join(blocks) if blocks else "(Sin texto detectado)"
                out_file.write_text(final, encoding="utf-8")

            self.progress.emit(100)
            self.log_msg.emit(
                f"✅ Completado: {out_file.name} "
                f"({self._total_chars} chars / {self._total_words} palabras)"
            )
            self.finished_ok.emit(str(out_file))

        except Exception as ex:
            self.error.emit(f"OCRWorkerSpace: {ex}")

    # ── PIPELINE INTELIGENTE: PaddleOCR crop → OCR.space ─────────────────────
    def _process_with_crop_pipeline(self, path: Path) -> str:
        """
        Pipeline completo para una imagen:
          1. PaddleOCR detecta cuadros de texto y los recorta en orden de lectura.
          2. Cada recorte PIL se envía a OCR.space como JPEG en memoria.
          3. Ensambla el texto de todos los recortes en orden.

        Si no se detectan cuadros válidos, hace fallback a imagen completa.
        """
        crops = _extract_crops_from_image(
            image_path    = path,
            ocr_lang      = self._ocr_lang_raw,
            reading_order = self._reading,
            log_cb        = lambda m: self.log_msg.emit(m),
        )

        if not crops:
            # Fallback: imagen completa
            self.log_msg.emit(f"  ↳ Fallback: enviando {path.name} completo…")
            return self._ocr_single_file(path)

        self.log_msg.emit(f"  ↳ Enviando {len(crops)} recortes a OCR.space…")
        texts: List[str] = []
        for j, crop in enumerate(crops):
            if self._cancelled:
                break
            try:
                text = self._ocr_pil_with_retry(crop)
                if text and text.strip():
                    texts.append(text.strip())
                    self.log_msg.emit(f"     [{j+1}/{len(crops)}] ✓ '{text.strip()[:50]}'")
                else:
                    self.log_msg.emit(f"     [{j+1}/{len(crops)}] — (vacío)")
                # Rate-limit entre recortes (menos agresivo que entre imágenes)
                if j < len(crops) - 1:
                    time.sleep(self._client.delay * 0.5)
            except Exception as e:
                self.log_msg.emit(f"     [{j+1}/{len(crops)}] ✗ Error: {e}")

        return "\n\n".join(texts)

    def _ocr_pil_with_retry(self, image: PILImage.Image, max_retries: int = 3) -> str:
        """Envía un PIL.Image a OCR.space con reintentos."""
        last_err: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                return self._client.ocr_pil_image(image, lang=self._lang)
            except requests.HTTPError as e:
                code = e.response.status_code if e.response else 0
                if code == 429:
                    wait = 5 * (attempt + 1)
                    self.log_msg.emit(f"  ⚠ Rate limit — esperando {wait}s…")
                    time.sleep(wait)
                    last_err = e
                elif code in (500, 502, 503):
                    time.sleep(3 * (attempt + 1))
                    last_err = e
                else:
                    raise
            except (requests.ConnectionError, requests.Timeout) as e:
                time.sleep(3)
                last_err = e
        self.log_msg.emit(f"  ✗ Falló después de {max_retries} intentos: {last_err}")
        return ""

    # ── OCR IMAGEN COMPLETA (fallback / modo legacy) ──────────────────────────
    def _ocr_single_file(self, path: Path) -> str:
        """OCR una imagen completa con reintentos (modo fallback)."""
        last_err: Optional[Exception] = None
        for attempt in range(3):
            try:
                return self._client.ocr_file(path, lang=self._lang)
            except requests.HTTPError as e:
                code = e.response.status_code if e.response else 0
                if code == 429:
                    wait = 5 * (attempt + 1)
                    self.log_msg.emit(f"  ⚠ Rate limit — esperando {wait}s…")
                    time.sleep(wait)
                    last_err = e
                elif code in (500, 502, 503):
                    self.log_msg.emit(f"  ⚠ Error servidor ({code}) — reintento {attempt+1}/3…")
                    time.sleep(3 * (attempt + 1))
                    last_err = e
                else:
                    raise
            except (requests.ConnectionError, requests.Timeout) as e:
                self.log_msg.emit(f"  ⚠ Timeout/conexión — reintento {attempt+1}/3…")
                time.sleep(3)
                last_err = e
        self.log_msg.emit(f"  ✗ Falló después de 3 intentos: {last_err}")
        return ""

    # ── HELPERS ───────────────────────────────────────────────────────────────
    def _post_process(self, text: str) -> str:
        if not text:
            return text
        if not self._keep_sfx:
            text = re.sub(r"\[.*?\]", "", text)
            text = re.sub(r"\*[^*]+\*", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        if self._case == "upper":
            text = text.upper()
        elif self._case == "lower":
            text = text.lower()
        elif self._case == "title":
            text = text.title()
        return text

    @staticmethod
    def _format_block(page: int, filename: str, text: str, fmt: str) -> str:
        sep    = "─" * 40
        header = f"<!-- PAGE {page}: {filename} -->"
        if fmt == "html":
            body = text.replace("\n", "<br>") if text else "<em>(sin texto)</em>"
            return (f'<div class="page-block">'
                    f'<p class="page-header">▌ Página {page} — {filename}</p>'
                    f'<p>{body}</p></div>')
        else:
            content = text if text else "(sin texto detectado)"
            return f"{header}\n{sep}\n{content}\n{sep}"

    def _save_docx(self, out_file: Path, lines: List[str]):
        """
        Guarda el texto en formato DOCX.
        FIX: asegura que nunca se guarde vacío — siempre al menos un párrafo.
        """
        try:
            from docx import Document
            from docx.shared import Pt
            doc = Document()
            style = doc.styles["Normal"]
            style.font.name = "Arial"
            style.font.size = Pt(11)

            has_content = any(l.strip() for l in lines)
            if not has_content:
                lines = ["(Sin texto detectado en las imágenes procesadas)"]

            for line in lines:
                doc.add_paragraph(line)

            doc.save(str(out_file))
            self.log_msg.emit(f"✓ DOCX guardado: {out_file.name} ({len(lines)} párrafos)")

        except ImportError:
            txt_path = out_file.with_suffix(".txt")
            txt_path.write_text("\n".join(lines), encoding="utf-8")
            self.log_msg.emit(f"⚠ python-docx no disponible → guardado como .txt: {txt_path.name}")


# ─────────────────────────────────────────────────────────────────────────────
#  METADATOS / INFO DEL MOTOR
# ─────────────────────────────────────────────────────────────────────────────
ENGINE_INFO = {
    "id":          "space",
    "name":        "OCR.space API",
    "description": (
        "Motor cloud vía API REST. Sin instalación local. "
        "Pipeline inteligente: PaddleOCR→Crop→OCR.space. "
        "Tier free: 500 req/día | PRO: sin límite."
    ),
    "requires":    ["requests", "Pillow"],
    "requires_opt": ["paddleocr (para pipeline crop inteligente)"],
    "langs":       list(LANG_MAP.keys()),
    "pipeline":    _PADDLE_CROP_OK,
    "engines":     {
        1: "Rápido — multilenguaje, bueno para caracteres especiales",
        2: "Preciso — mejor en fondos complejos, texto rotado, baja resolución",
    },
    "api_url":     "https://ocr.space/ocrapi",
    "key_url":     "https://ocr.space/ocrapi/freekey",
}


def get_engine_info() -> dict:
    return ENGINE_INFO