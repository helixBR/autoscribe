"""
Translator_offline.py — Motor de traducción offline (Argos Translate) para AutoScribe v1.0
═══════════════════════════════════════════════════════════════════════════════════════════════
Motor soportado:
  · Argos Translate — Red neuronal de traducción pura, instantánea, ~100 MB/par.

Ventajas vs llama-cpp/Qwen:
  · Instantáneo (no LLM — modelo neural de traducción directo)
  · Nunca pierde líneas (traduce línea por línea de forma determinista)
  · ~200 MB RAM vs ~2 GB de Qwen 1.5B
  · Sin descarga de modelo de 1-2 GB: paquetes de idioma de ~100 MB

Instalación:
    pip install argostranslate

Paquetes de idioma (se descargan automáticamente la primera vez que se usan):
    Ubicación: ~/.local/share/argos-translate/
    Tamaño:    ~100 MB por par de idiomas (ej: en→es, ja→es)

Uso desde AutoScribe:
    from Translator_offline import get_argos_translator, translate_structured_argos
    t = get_argos_translator()
    ok, msg = t.test_connection(source="en", target="es")
    texto = translate_structured_argos(text, target="es", source="en", translator=t)
"""

from __future__ import annotations

import re as _re
from typing import Optional, Callable

# ─── IDIOMAS ─────────────────────────────────────────────────────────────────
LANGUAGE_NAMES: dict[str, str] = {
    "es": "Spanish", "en": "English", "fr": "French",
    "de": "German",  "pt": "Portuguese", "it": "Italian",
    "ja": "Japanese", "ko": "Korean",
    "zh-CN": "Simplified Chinese", "ru": "Russian",
}

# ─── REGEXES (compartidas con translate_structured_argos) ────────────────────
_SEP_RE = _re.compile(r'^─{10,}$')
_IMG_RE = _re.compile(r'.*\.(jpg|jpeg|png|bmp|webp|gif|tif)$', _re.IGNORECASE)


# ─── ARGOS TRANSLATE ─────────────────────────────────────────────────────────
class ArgosTranslator:
    """
    Traductor offline usando Argos Translate (~100 MB por par de idiomas).

    Instalación:
        pip install argostranslate

    Paquetes de idioma (se descargan automáticamente la primera vez):
        Los paquetes se guardan en ~/.local/share/argos-translate/

    Uso desde AutoScribe:
        t = ArgosTranslator()
        ok, msg = t.test_connection(source="en", target="es")
        texto = t.translate("Hello world", target="es", source="en")
    """
    engine_id = "argos"

    # Mapeo de códigos AutoScribe → códigos Argos Translate
    _LANG_MAP: dict[str, str] = {
        "es": "es", "en": "en", "fr": "fr",
        "de": "de", "pt": "pt", "it": "it",
        "ja": "ja", "ko": "ko",
        "zh-CN": "zh", "ru": "ru",
    }

    def __init__(self):
        self._installed: set[tuple[str, str]] = set()   # pares (src, tgt) instalados

    # ── Instalación automática de paquetes ────────────────────────────────────
    def _ensure_package(self, src: str = "en", tgt: str = "es") -> bool:
        """
        Verifica que el paquete src→tgt esté instalado.
        Si no, lo descarga automáticamente (requiere internet la primera vez).
        Retorna True si está listo, False si falló.
        """
        pair = (src, tgt)
        if pair in self._installed:
            return True
        try:
            from argostranslate import package, translate
            # Verificar si ya está instalado localmente
            installed = translate.get_installed_languages()
            src_langs = [l for l in installed if l.code == src]
            if src_langs:
                tgt_langs = [t for t in src_langs[0].translations_to if t.code == tgt]
                if tgt_langs:
                    self._installed.add(pair)
                    return True
            # No está instalado → descargar
            print(f"[ArgosTranslator] Descargando paquete {src}→{tgt} (~100 MB)…")
            package.update_package_index()
            available = package.get_available_packages()
            pkg = next(
                (p for p in available if p.from_code == src and p.to_code == tgt),
                None
            )
            if pkg is None:
                print(f"[ArgosTranslator] Paquete {src}→{tgt} no disponible en el índice")
                return False
            package.install_from_path(pkg.download())
            self._installed.add(pair)
            print(f"[ArgosTranslator] Paquete {src}→{tgt} instalado correctamente")
            return True
        except Exception as ex:
            print(f"[ArgosTranslator] Error instalando paquete {src}→{tgt}: {ex}")
            return False

    def is_available(self) -> bool:
        try:
            import argostranslate  # noqa: F401
            return True
        except ImportError:
            return False

    def test_connection(self, source: str = "en", target: str = "es") -> tuple[bool, str]:
        if not self.is_available():
            return False, "✗ Argos Translate no instalado. Ejecuta: pip install argostranslate"
        src = self._LANG_MAP.get(source, source)
        tgt = self._LANG_MAP.get(target, target)
        ok = self._ensure_package(src, tgt)
        if ok:
            return True, f"✓ Argos Translate OK — par {src}→{tgt} listo"
        return False, f"✗ Argos Translate: no se pudo instalar paquete {src}→{tgt}"

    def translate(self, text: str, target: str,
                  source: str = "en", content_type: str = "manga") -> str:
        """
        Traduce text de source→target.
        source por defecto "en" (inglés); ajustar según el idioma del OCR.
        content_type aceptado por compatibilidad de interfaz, no afecta la traducción.
        """
        if not text.strip():
            return text
        from argostranslate import translate as _at
        src = self._LANG_MAP.get(source, source)
        tgt = self._LANG_MAP.get(target, target)
        self._ensure_package(src, tgt)
        installed = _at.get_installed_languages()
        src_lang = next((l for l in installed if l.code == src), None)
        if src_lang is None:
            return text
        tgt_lang = next((t for t in src_lang.translations_to if t.code == tgt), None)
        if tgt_lang is None:
            return text
        return tgt_lang.get_translation(src_lang).translate(text)


# ─── FACTORY ─────────────────────────────────────────────────────────────────
def get_argos_translator() -> ArgosTranslator:
    """Factory para ArgosTranslator."""
    return ArgosTranslator()


# ─── TRADUCCIÓN ESTRUCTURADA LÍNEA A LÍNEA ───────────────────────────────────
def translate_structured_argos(
    text:       str,
    target:     str,
    source:     str,
    translator: ArgosTranslator,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> str:
    """
    Traduce texto línea por línea con Argos Translate.
    Preserva separadores (────), nombres de imagen y líneas vacías.
    Garantiza que NINGUNA línea se pierda (modelo determinista).

    Args:
        text:              Texto completo a traducir.
        target:            Código de idioma destino (ej: "es").
        source:            Código de idioma fuente (ej: "en", "ja").
        translator:        Instancia de ArgosTranslator.
        progress_callback: Callback opcional con progreso 0-100.
    """
    lines  = text.split("\n")
    result = list(lines)

    translatable = [
        (i, l) for i, l in enumerate(lines)
        if l.strip()
        and not _SEP_RE.match(l.strip())
        and not _IMG_RE.match(l.strip())
    ]
    total = len(translatable)

    for done, (i, line) in enumerate(translatable):
        try:
            translated = translator.translate(line.strip(), target, source)
            result[i] = translated if translated.strip() else line
        except Exception:
            pass  # mantener original si falla
        if progress_callback and total > 0:
            progress_callback(int((done + 1) / total * 100))

    return "\n".join(result)