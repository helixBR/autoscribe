"""
Translator_online.py — Motores de traducción ONLINE para AutoScribe v1.0
═══════════════════════════════════════════════════════════════════════════
Motores soportados:
  · DeepL API       — Máxima precisión terminológica
  · Claude Sonnet   — Fidelidad emocional y matices literarios
  · Groq            — Inferencia ultrarrápida (hasta 10× más rápido que Claude)

Mejoras v1.2:
  · Traducción en LOTE (batch): translate_structured() ahora envía TODAS las
    líneas en UNA sola llamada a la API, numeradas con [N] para mantener el orden.
    Resultado: 200 líneas = 1 llamada (antes = 200 llamadas).
    Tiempo estimado: ~2–4 s en lugar de ~3 min.
  · Corrección OCR integrada en el system prompt (Opción A):
    El modelo corrige silenciosamente errores de OCR (caracteres rotos,
    palabras partidas, símbolos garbled) y traduce en una sola llamada.
  · Pivot automático por inglés:
    Para pares sin ruta directa confiable (ja→es, ko→es, zh→es, etc.)
    se hace el salto internamente: fuente→en→destino.
    El usuario no necesita configurar nada.

Uso desde AutoScribe:
    from Translator_online import get_online_translator, translate_structured
    t = get_online_translator("groq", api_key="TU_KEY")
    texto = translate_structured(text, target="es", content_type="manga",
                                 translator=t, source="ja")
"""

from __future__ import annotations
import re
from typing import Optional

# ─── IDIOMAS ──────────────────────────────────────────────────────────────────
LANGUAGE_NAMES: dict[str, str] = {
    "es": "Spanish", "en": "English", "fr": "French",
    "de": "German",  "pt": "Portuguese", "it": "Italian",
    "ja": "Japanese", "ko": "Korean",
    "zh-CN": "Simplified Chinese", "zh-TW": "Traditional Chinese",
    "ru": "Russian", "ar": "Arabic",
}

# Idiomas disponibles en el selector de la UI
DEST_LANGS: list[tuple[str, str]] = [
    ("No traduc.", ""),
    ("Español",    "es"),
    ("English",    "en"),
    ("中文 简",    "zh-CN"),
    ("日本語",     "ja"),
    ("한국어",     "ko"),
    ("Français",   "fr"),
    ("Deutsch",    "de"),
    ("Português",  "pt"),
    ("Русский",    "ru"),
]

# ─── PIVOT: pares que necesitan pasar por inglés ──────────────────────────────
_PIVOT_SOURCES: set[str] = {"ja", "ko", "zh-CN", "zh-TW", "ar", "ru", "hi"}


def _needs_pivot(source: str, target: str) -> bool:
    return (
        source in _PIVOT_SOURCES
        and target not in ("en", "")
        and source != target
    )


# ─── SYSTEM PROMPTS ───────────────────────────────────────────────────────────
# Instrucción de batch que se añade automáticamente cuando se envían varias líneas.
# Usa el formato [N] como prefijo para garantizar que el modelo preserve el orden.
_BATCH_INSTRUCTION = (
    "\n\nIMPORTANT — BATCH FORMAT:\n"
    "The input is a numbered list of lines in the format:\n"
    "  [1] line one\n"
    "  [2] line two\n"
    "  ...\n"
    "You MUST return EXACTLY the same number of lines with the SAME [N] prefix:\n"
    "  [1] translated line one\n"
    "  [2] translated line two\n"
    "  ...\n"
    "Rules:\n"
    "- Never merge, split, skip, or reorder lines\n"
    "- Never add extra lines or commentary\n"
    "- If a line is a sound effect or untranslatable, return it as-is with its [N]\n"
    "- Output ONLY the numbered translated lines — nothing else"
)

_PROMPTS: dict[str, str] = {
    "manga": (
        "You are a professional manga/manhwa/manhua translator. "
        "The input text was extracted by OCR and may have minor recognition errors "
        "(broken characters, split words, garbled symbols, wrong kanji/hangul). "
        "First silently correct any obvious OCR errors, then translate to natural, "
        "emotionally resonant {lang}. Rules:\n"
        "- Preserve onomatopoeia style (SFX) or adapt it naturally\n"
        "- Keep dialogue SHORT and punchy — text must fit in speech bubbles\n"
        "- Preserve emotional intensity: exclamations, hesitations (...), CAPS emphasis\n"
        "- Do NOT add explanations, notes, or annotations\n"
        "- Output ONLY the final translation — never the corrected original\n"
        "- Preserve the exact line structure given (same number of lines)"
    ),
    "novel": (
        "You are a literary translator specializing in light novels and web novels. "
        "The input text was extracted by OCR and may have minor recognition errors. "
        "First silently correct any obvious OCR errors, then translate to fluent, "
        "natural {lang} prose. Rules:\n"
        "- Maintain narrative voice and each character's personality\n"
        "- Preserve descriptive richness and scene atmosphere\n"
        "- Adapt honorifics naturally (e.g. -kun, -san can be kept or explained contextually)\n"
        "- Translate idioms and cultural references naturally\n"
        "- Do NOT add explanations or annotations\n"
        "- Output ONLY the translation preserving paragraph structure"
    ),
    "technical": (
        "You are a technical translator. "
        "The input text was extracted by OCR and may have minor recognition errors. "
        "First silently correct any obvious OCR errors, then translate to precise, "
        "formal {lang}. Rules:\n"
        "- Use standard technical / domain-specific terminology\n"
        "- Be 100% literal — no interpretations, no embellishments\n"
        "- Preserve all numbers, units, codes, proper nouns and formatting\n"
        "- Output ONLY the translated text"
    ),
    "_pivot_to_en": (
        "You are a professional translator. "
        "The input text was extracted by OCR from a {src_lang} source and may have "
        "minor recognition errors (broken characters, split words, garbled symbols). "
        "First silently correct any obvious OCR errors, then translate to natural English. "
        "Rules:\n"
        "- Preserve the exact line structure (same number of lines)\n"
        "- Do NOT add explanations, notes, or annotations\n"
        "- Output ONLY the English translation"
    ),
}


def _system_prompt(content_type: str, target: str,
                   source: str = "", batch: bool = False) -> str:
    lang     = LANGUAGE_NAMES.get(target, target)
    template = _PROMPTS.get(content_type, _PROMPTS["manga"])
    prompt   = template.format(lang=lang)
    if batch:
        prompt += _BATCH_INSTRUCTION
    return prompt


def _pivot_prompt(source: str, batch: bool = False) -> str:
    src_lang = LANGUAGE_NAMES.get(source, source)
    prompt   = _PROMPTS["_pivot_to_en"].format(src_lang=src_lang)
    if batch:
        prompt += _BATCH_INSTRUCTION
    return prompt


# ─── REGEX para parsear la respuesta batch ────────────────────────────────────
# Acepta: "[3] texto", "[3]texto", "3. texto", "3) texto"
_BATCH_LINE_RE = re.compile(r'^\[(\d+)\][.\s]?\s*(.*)', re.DOTALL)
_BATCH_LINE_ALT_RE = re.compile(r'^(\d+)[.)]\s+(.*)', re.DOTALL)


def _parse_batch_response(response: str, expected: int) -> dict[int, str]:
    """
    Parsea la respuesta batch del modelo.
    Retorna un dict { índice_1based: texto_traducido }.
    Soporta formatos [N] texto y N. texto / N) texto.
    """
    parsed: dict[int, str] = {}
    for line in response.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = _BATCH_LINE_RE.match(line) or _BATCH_LINE_ALT_RE.match(line)
        if m:
            n    = int(m.group(1))
            text = m.group(2).strip()
            if 1 <= n <= expected:
                parsed[n] = text
    return parsed


# ─── BASE ─────────────────────────────────────────────────────────────────────
class BaseOnlineTranslator:
    engine_id: str = "base"

    def translate(self, text: str, target: str,
                  source: str = "auto",
                  content_type: str = "manga") -> str:
        raise NotImplementedError

    def is_available(self) -> bool:
        return False

    def test_connection(self) -> tuple[bool, str]:
        return False, "No implementado"

    def _apply_pivot(self, text: str, source: str, target: str,
                     content_type: str, batch: bool = False) -> str:
        en_text = self._translate_direct(text, target="en", source=source,
                                         content_type=content_type,
                                         pivot_step=True, batch=batch)
        return self._translate_direct(en_text, target=target, source="en",
                                      content_type=content_type,
                                      pivot_step=False, batch=batch)

    def _translate_direct(self, text: str, target: str, source: str,
                          content_type: str, pivot_step: bool = False,
                          batch: bool = False) -> str:
        raise NotImplementedError


# ─── DEEPL ────────────────────────────────────────────────────────────────────
class DeepLTranslator(BaseOnlineTranslator):
    """
    Traductor usando DeepL API Free o Pro.
    DeepL tiene rutas directas para todos los pares soportados,
    por lo que NO usa pivot. La corrección OCR no aplica (motor determinista).
    Instalar: pip install deepl
    """
    engine_id = "deepl"

    _LANG_MAP: dict[str, str] = {
        "es": "ES",    "en": "EN-US", "fr": "FR",
        "de": "DE",    "pt": "PT-BR", "it": "IT",
        "ja": "JA",    "ko": "KO",    "zh-CN": "ZH",
        "zh-TW": "ZH", "ru": "RU",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        self._client = None

    def _get_client(self):
        if self._client is None:
            import deepl  # type: ignore
            self._client = deepl.Translator(self.api_key)
        return self._client

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import deepl  # noqa: F401
            return True
        except ImportError:
            return False

    def test_connection(self) -> tuple[bool, str]:
        try:
            client = self._get_client()
            usage = client.get_usage()
            return True, f"✓ DeepL OK — {usage.character.count:,} / {usage.character.limit:,} chars"
        except Exception as ex:
            return False, f"✗ DeepL: {ex}"

    def translate(self, text: str, target: str,
                  source: str = "auto",
                  content_type: str = "manga") -> str:
        if not text.strip():
            return text
        deepl_lang = self._LANG_MAP.get(target, target.upper())
        deepl_src  = self._LANG_MAP.get(source) if source not in ("auto", "") else None
        client = self._get_client()
        result = client.translate_text(text, target_lang=deepl_lang,
                                       source_lang=deepl_src)
        return result.text

    def _translate_direct(self, text: str, target: str, source: str,
                          content_type: str, pivot_step: bool = False,
                          batch: bool = False) -> str:
        return self.translate(text, target, source, content_type)


# ─── CLAUDE ───────────────────────────────────────────────────────────────────
class ClaudeTranslator(BaseOnlineTranslator):
    """
    Traductor usando Claude Sonnet (Anthropic API).
    Prioriza fidelidad emocional y matices literarios.
    Corrige errores de OCR silenciosamente en la misma llamada.
    Usa pivot automático para pares sin ruta directa confiable.
    Instalar: pip install anthropic
    """
    engine_id = "claude"
    MODEL     = "claude-sonnet-4-20250514"

    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic  # type: ignore
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    def test_connection(self) -> tuple[bool, str]:
        try:
            client = self._get_client()
            client.messages.create(
                model=self.MODEL, max_tokens=5,
                messages=[{"role": "user", "content": "Hi"}]
            )
            return True, f"✓ Claude OK — modelo: {self.MODEL}"
        except Exception as ex:
            return False, f"✗ Claude: {ex}"

    def translate(self, text: str, target: str,
                  source: str = "auto",
                  content_type: str = "manga") -> str:
        if not text.strip():
            return text
        src = source if source not in ("auto", "") else "en"
        if _needs_pivot(src, target):
            return self._apply_pivot(text, source=src, target=target,
                                     content_type=content_type)
        return self._translate_direct(text, target=target, source=src,
                                      content_type=content_type)

    def _translate_direct(self, text: str, target: str, source: str,
                          content_type: str, pivot_step: bool = False,
                          batch: bool = False) -> str:
        client = self._get_client()
        system = (_pivot_prompt(source, batch=batch) if pivot_step
                  else _system_prompt(content_type, target, source, batch=batch))
        msg = client.messages.create(
            model=self.MODEL,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": text}],
        )
        return msg.content[0].text.strip()


# ─── GROQ ─────────────────────────────────────────────────────────────────────
class GroqTranslator(BaseOnlineTranslator):
    """
    Traductor usando Groq API (inferencia ultrarrápida — hasta 10× más rápido que Claude).
    Corrige errores de OCR silenciosamente en la misma llamada.
    Usa pivot automático para pares sin ruta directa confiable.
    Tier gratuito: 6,000 req/día · 500,000 tokens/min.
    Documentación: https://console.groq.com
    Instalación: pip install groq
    """
    engine_id = "groq"
    MODELS: list[str] = [
        "llama-3.3-70b-versatile",   # mejor calidad, tier gratuito OK
        "llama-3.1-8b-instant",      # más rápido, menor calidad
        "gemma2-9b-it",              # alternativa Google
    ]
    DEFAULT_MODEL = MODELS[0]

    def __init__(self, api_key: str, model: str = ""):
        self.api_key = api_key.strip()
        self.model   = model.strip() or self.DEFAULT_MODEL
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import Groq  # type: ignore
            self._client = Groq(api_key=self.api_key)
        return self._client

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import groq  # noqa: F401
            return True
        except ImportError:
            return False

    def test_connection(self) -> tuple[bool, str]:
        try:
            client = self._get_client()
            client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
            )
            return True, f"✓ Groq OK — modelo: {self.model}"
        except Exception as ex:
            return False, f"✗ Groq: {ex}"

    def translate(self, text: str, target: str,
                  source: str = "auto",
                  content_type: str = "manga") -> str:
        if not text.strip():
            return text
        src = source if source not in ("auto", "") else "en"
        if _needs_pivot(src, target):
            return self._apply_pivot(text, source=src, target=target,
                                     content_type=content_type)
        return self._translate_direct(text, target=target, source=src,
                                      content_type=content_type)

    def _translate_direct(self, text: str, target: str, source: str,
                          content_type: str, pivot_step: bool = False,
                          batch: bool = False) -> str:
        client = self._get_client()
        system = (_pivot_prompt(source, batch=batch) if pivot_step
                  else _system_prompt(content_type, target, source, batch=batch))
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": text},
            ],
            max_tokens=4096,
            temperature=0.10,
        )
        return resp.choices[0].message.content.strip()


# ─── FACTORY ──────────────────────────────────────────────────────────────────
def get_online_translator(engine: str,
                          api_key: str,
                          model: str = "") -> BaseOnlineTranslator:
    """
    Retorna el traductor online adecuado.
    engine: "deepl" | "claude" | "groq"
    """
    engine = engine.lower().strip()
    if engine == "deepl":
        return DeepLTranslator(api_key)
    if engine == "claude":
        return ClaudeTranslator(api_key)
    if engine == "groq":
        return GroqTranslator(api_key, model)
    raise ValueError(f"Motor online desconocido: '{engine}'. "
                     "Usa 'deepl', 'claude' o 'groq'.")


# ─── REGEX estructurales ──────────────────────────────────────────────────────
_SEP_RE = re.compile(r'^─{10,}$')
_IMG_RE = re.compile(r'.*\.(jpg|jpeg|png|bmp|webp|gif|tif)$', re.IGNORECASE)


# ─── TRADUCCIÓN ESTRUCTURADA EN LOTE ─────────────────────────────────────────
def translate_structured(
    text:        str,
    target:      str,
    content_type: str,
    translator:  BaseOnlineTranslator,
    source:      str = "auto",
    progress_callback=None,
) -> str:
    """
    Traduce el texto completo en UNA SOLA llamada a la API.

    Estrategia batch:
      1. Separa las líneas en "traducibles" y "protegidas" (vacías, ────, imágenes).
      2. Numera las líneas traducibles: [1] línea, [2] línea, …
      3. Envía el bloque numerado en una sola llamada al traductor.
      4. Parsea la respuesta por prefijo [N] y reensambla en el orden original.

    Si el parseo falla o devuelve líneas de menos, se intenta fallback línea a línea
    solo para las que no se recibieron (raro, pero seguro).

    DeepL: no usa batch (su API acepta el bloque completo directamente, no necesita
    numeración — simplemente se envía el texto y se devuelve en el mismo orden).

    Args:
        text:              Texto completo a traducir.
        target:            Código de idioma destino (ej: "es").
        content_type:      "manga" | "novel" | "technical".
        translator:        Instancia de BaseOnlineTranslator.
        source:            Código de idioma fuente (ej: "ja", "ko", "zh-CN", "auto").
        progress_callback: Opcional — función(int 0-100) para barra de progreso.
    """
    lines  = text.split("\n")
    result = list(lines)  # copia que iremos llenando

    # ── DeepL: enviar el bloque completo directamente (sin numeración) ────────
    if translator.engine_id == "deepl":
        try:
            translated = translator.translate(text, target, source, content_type)
            if progress_callback:
                progress_callback(100)
            return translated
        except Exception:
            pass  # fallback al método normal abajo

    # ── Identificar líneas traducibles y sus índices originales ───────────────
    translatable: list[tuple[int, str]] = []   # (índice_en_result, texto)
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not _SEP_RE.match(s) and not _IMG_RE.match(s):
            translatable.append((i, s))

    if not translatable:
        if progress_callback:
            progress_callback(100)
        return text

    # ── Construir bloque numerado ─────────────────────────────────────────────
    # Formato: "[1] texto\n[2] texto\n..."
    numbered_lines = [f"[{n+1}] {txt}" for n, (_, txt) in enumerate(translatable)]
    batch_input    = "\n".join(numbered_lines)
    total          = len(translatable)

    # ── Una sola llamada a la API ─────────────────────────────────────────────
    src = source if source not in ("auto", "") else "en"
    try:
        if _needs_pivot(src, target) and translator.engine_id != "deepl":
            # Pivot también en modo batch: source→en (batch), luego en→target (batch)
            en_block = translator._translate_direct(
                batch_input, target="en", source=src,
                content_type=content_type, pivot_step=True, batch=True
            )
            raw_response = translator._translate_direct(
                en_block, target=target, source="en",
                content_type=content_type, pivot_step=False, batch=True
            )
        else:
            raw_response = translator._translate_direct(
                batch_input, target=target, source=src,
                content_type=content_type, pivot_step=False, batch=True
            )
    except Exception as ex:
        print(f"[translate_structured] Error en llamada batch: {ex}")
        if progress_callback:
            progress_callback(100)
        return text  # fallback: devolver original si la API falla

    # ── Parsear respuesta numerada ────────────────────────────────────────────
    parsed = _parse_batch_response(raw_response, expected=total)

    # ── Reensamblar en el orden original ─────────────────────────────────────
    missing: list[tuple[int, str]] = []   # líneas que el modelo no devolvió
    for n, (orig_idx, orig_line) in enumerate(translatable):
        translated_text = parsed.get(n + 1)
        if translated_text:
            result[orig_idx] = translated_text
        else:
            missing.append((orig_idx, orig_line))  # se intentará fallback

    # ── Fallback para líneas no recibidas (raro) ──────────────────────────────
    if missing:
        print(f"[translate_structured] Batch incompleto — reintentando {len(missing)} línea(s)")
        for orig_idx, orig_line in missing:
            try:
                fb = translator._translate_direct(
                    orig_line, target=target, source=src,
                    content_type=content_type, pivot_step=False, batch=False
                )
                if fb.strip():
                    result[orig_idx] = fb
            except Exception:
                pass  # mantener original

    if progress_callback:
        progress_callback(100)

    return "\n".join(result)