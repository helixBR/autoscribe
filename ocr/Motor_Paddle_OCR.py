"""
Motor_Paddle_Simple.py — Motor OCR y Orquestador Principal de AutoScribe v1.0
===============================================================================
Motor ÚNICO que coordina el pipeline completo:

  MODO SIMPLE (por defecto):
    Imagen → Preprocesamiento (rescale+CLAHE+unsharp) → PaddleOCR (pasada única) → Texto

Compatible con PaddleOCR v2 y v3.
Interfaz Qt: OCRWorker, UnifyWorker, extract_video_frames.
"""

# ─── PADDLE / OneDNN — ANTES DE CUALQUIER IMPORT QUE TOQUE PADDLE ──────────
import os
os.environ["FLAGS_use_mkldnn"]      = "0"
os.environ["FLAGS_enable_pir_api"]  = "0"
os.environ["FLAGS_use_pir_api"]     = "0"
os.environ["PADDLE_DISABLE_ONEDNN"] = "1"
os.environ["OMP_NUM_THREADS"]       = "1"
os.environ["KMP_DUPLICATE_LIB_OK"]  = "TRUE"
# ─────────────────────────────────────────────────────────────────────────────
import os, sys, json, re, tempfile
from pathlib import Path
from typing import List, Dict, Optional, Set, Union, Tuple

# ─── PREPROCESAMIENTO ÓPTIMO PARA PADDLEOCR ──────────────────────────────────
# PaddleOCR detecta mejor cuando:
#   · Lado largo entre 960–1920 px  (su det model opera a 960 px; encima es
#     redundante y solo ralentiza sin mejorar la detección)
#   · Contraste local alto (CLAHE por zonas, no histograma global)
#   · Bordes nítidos  (unsharp mask suave — endurece trazos de texto)
# Todo en memoria: PIL + numpy array, sin I/O de disco.
#
# Jerarquía de dependencias:
#   PIL (Pillow) — REQUERIDO para rescale y unsharp mask
#   OpenCV (cv2) — OPCIONAL para CLAHE; si no está, se salta ese paso

_PADDLE_MAX_SIDE = 1920   # px — máximo útil para PaddleOCR (solo downscale)


def _preprocess_for_paddle(path_str: str):
    """
    Preprocesa la imagen en memoria para condiciones óptimas de PaddleOCR:
      1. Reescalar (solo downscale): si el lado largo supera 1920 px,
         se reduce con LANCZOS manteniendo proporciones exactas.
         Imágenes pequeñas o dentro del rango se pasan sin cambio de tamaño
         (subir con interpolación empeora la calidad para OCR).
      2. CLAHE (8×8 tiles, clipLimit=2.0): ecualización de contraste local
         aplicada solo en el canal L (luminancia en LAB), sin alterar color.
         Requiere OpenCV; si no está disponible, se omite este paso.
      3. Unsharp mask (radio=1.5, 60%, umbral=3): endurece bordes de glifos.
         Más suave que el filtro SHARPEN estándar — no crea halos en fondos.

    Retorna ndarray uint8 (H, W, 3) RGB listo para ocr.ocr(), o None si falla.
    En caso de None, ocr_imagen() usará el path original como fallback.
    """
    try:
        from PIL import Image, ImageFilter
        import numpy as np

        img = Image.open(path_str).convert("RGB")
        w, h = img.size

        # ── 1. Reescalar (solo downscale) ────────────────────────────────────
        long_side = max(w, h)
        if long_side > _PADDLE_MAX_SIDE:
            scale = _PADDLE_MAX_SIDE / long_side
            img = img.resize(
                (int(w * scale), int(h * scale)),
                resample=Image.Resampling.LANCZOS,
            )

        # ── 2. CLAHE — contraste local adaptativo (requiere OpenCV) ──────────
        try:
            import cv2
            arr = np.array(img)
            lab  = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            lab   = cv2.merge((clahe.apply(l), a, b))
            img   = Image.fromarray(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB))
        except ImportError:
            pass   # sin OpenCV → continuar sin CLAHE

        # ── 3. Unsharp mask suave — nitidez de bordes de glifos ──────────────
        img = img.filter(
            ImageFilter.UnsharpMask(radius=1.5, percent=60, threshold=3)
        )

        return np.array(img, dtype=np.uint8)

    except Exception as e:
        print(f"[Preprocess] _preprocess_for_paddle falló: {e}")
        return None



# ─── DETECCIÓN DE GUTTERS DE PANEL ───────────────────────────────────────────
def detect_panel_gutters(
    image_path_or_array,
    dark_thresh: float = 1.5,   # % de píxeles oscuros que define "fila de gutter blanco"
    min_px:      int   = 1,     # ancho mínimo del gutter en píxeles (1 para líneas negras)
) -> List[Tuple[float, float, float]]:
    """
    Detecta las franjas horizontales de separación entre paneles de manga.

    Detecta DOS tipos de barreras:
      1. Espacios blancos entre paneles (gutter clásico):
         filas con < dark_thresh % de píxeles oscuros → muy blancas.
      2. Líneas negras separadoras entre viñetas pegadas:
         filas con > 70 % de píxeles oscuros → línea de borde real.
         Crítico cuando dos paneles comparten borde sin margen blanco.

    Se ignora el 5% de cada extremo horizontal (bordes decorativos).
    Acepta path (str/Path) o ndarray numpy (H,W,3) RGB.
    Retorna: List[(y_start, y_end, y_mid)] de cada barrera detectada.
    """
    try:
        import numpy as np
        if isinstance(image_path_or_array, np.ndarray):
            arr = image_path_or_array
            if arr.ndim == 3:
                arr = arr.mean(axis=2).astype(np.uint8)
        else:
            from PIL import Image as _PIL
            arr = np.array(_PIL.open(str(image_path_or_array)).convert("L"))

        H, W = arr.shape
        mg = max(1, int(W * 0.05))
        col = arr[:, mg : W - mg]
        dark_pct = (col <= 50).sum(axis=1) / col.shape[1] * 100.0

        # Barrera = gutter blanco O línea negra separadora
        barrier = (dark_pct < dark_thresh) | (dark_pct > 70.0)

        ranges: List[Tuple[int, int]] = []
        in_r, s = False, 0
        for y in range(H):
            if barrier[y] and not in_r:
                s = y; in_r = True
            elif not barrier[y] and in_r:
                ranges.append((s, y - 1)); in_r = False
        if in_r:
            ranges.append((s, H - 1))

        return [
            (float(s), float(e), (s + e) / 2.0)
            for s, e in ranges
            if (e - s + 1) >= min_px
        ]
    except Exception:
        return []


from PyQt6.QtCore import QThread, pyqtSignal

ROOT_DIR = Path(__file__).parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

SUPPORTED_IMG = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".gif"}
SUPPORTED_VID = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv"}
VOCAB_UNIFIED_FILE = ROOT_DIR / "autoscribe_vocab_unified.json"

_SEP_RE   = re.compile(r'^─{10,}$')        # línea de separador ────────
_IMG_RE   = re.compile(r'.*\.(jpg|jpeg|png|bmp|webp|gif|tif|tiff)$', re.IGNORECASE)

# Separador visual que se inserta entre páginas en el texto de salida.
# TextEditorWidget._display_formatted lo detecta para colorear y navegación.
_SEP_LINE = "─" * 42


# ─── CACHÉ DE PADDLEOCR ───────────────────────────────────────────────────────
_paddle_cache: Dict = {}

def _get_paddle(lang: str):
    """
    Crea o devuelve instancia PaddleOCR. Caché LRU-1: solo mantiene el
    modelo más reciente en RAM (~1 GB por idioma). Compartida con
    autounify_crop_paddle.py para evitar cargar el modelo dos veces.

    Optimizaciones aplicadas:
      · use_angle_cls=False  — no cargar el clasificador de ángulo (~300 MB
                               ahorrados) ya que siempre se llama cls=False.
      · enable_mkldnn        — activado automáticamente solo en CPUs Intel;
                               da 2–3× de velocidad en convoluciones.
      · cpu_threads          — todos los núcleos lógicos disponibles.
      · rec_batch_num=32     — procesa hasta 32 burbujas en paralelo dentro
                               del CRNN; reduce lotes en páginas densas.
      · det_db_thresh=0.3    — elimina falsos positivos en fondos de manga
                               (tramados, gradientes) sin perder texto real.
      · det_db_box_thresh=0.4— cajas más limpias, menos ruido de borde.
      · det_db_unclip_ratio=2.0 — expansión de caja suficiente para burbujas.
    """
    if lang in _paddle_cache:
        return _paddle_cache[lang]

    if _paddle_cache:
        evicted = next(iter(_paddle_cache))
        print(f"[Motor] Liberando modelo lang={evicted} de RAM (LRU-1)")
        _paddle_cache.pop(evicted, None)
        try:
            import gc; gc.collect()
        except Exception:
            pass

    try:
        from paddleocr import PaddleOCR
    except ImportError:
        print("[Motor] PaddleOCR no instalado.")
        _paddle_cache[lang] = None
        return None

    # ── Detectar CPU Intel para activar MKL-DNN de forma segura ──────────────
    # MKL-DNN solo es estable en Intel; en AMD/ARM puede crashear con ciertos
    # modelos de PaddleOCR. py-cpuinfo es opcional — si no está, se deja off.
    _mkldnn = False
    try:
        import cpuinfo
        _mkldnn = "intel" in cpuinfo.get_cpu_info().get("brand_raw", "").lower()
    except Exception:
        pass

    _n_threads = os.cpu_count() or 4

    try:
        _paddle_cache[lang] = PaddleOCR(
            use_angle_cls       = False,   # clasificador de ángulo no usado → -300 MB RAM
            lang                = lang,
            use_gpu             = False,
            show_log            = False,
            enable_mkldnn       = _mkldnn,
            cpu_threads         = _n_threads,
            det_db_thresh       = 0.3,     # menos falsos positivos en fondos de manga
            det_db_box_thresh   = 0.4,     # cajas más limpias
            det_db_unclip_ratio = 2.0,     # expansión suficiente para burbujas
            rec_batch_num       = 32,      # hasta 32 burbujas en paralelo en CRNN
        )
        mkl_note = f"MKL-DNN ✓" if _mkldnn else "MKL-DNN ✗ (no Intel)"
        print(f"[Motor] PaddleOCR v2 OK — lang={lang} | {_n_threads} threads | {mkl_note}")
        return _paddle_cache[lang]
    except (TypeError, AttributeError):
        pass
    except Exception as e:
        print(f"[Motor] Fallo v2: {e}")

    try:
        _paddle_cache[lang] = PaddleOCR(lang=lang, use_gpu=False, show_log=False)
        print(f"[Motor] PaddleOCR v3 OK — lang={lang}")
        return _paddle_cache[lang]
    except Exception as e:
        print(f"[Motor] Fallo v3: {e}")
        _paddle_cache[lang] = None
        return None


# ─── PARSER UNIVERSAL ────────────────────────────────────────────────────────
def _es_bloque(item) -> bool:
    if not isinstance(item, (list, tuple)) or len(item) < 2:
        return False
    pts = item[0]
    if not isinstance(pts, (list, tuple)) or len(pts) < 3:
        return False
    return isinstance(pts[0], (list, tuple)) and len(pts[0]) >= 2

def _extraer_bloques(resultado) -> List[Tuple]:
    if resultado is None:
        return []
    encontrados = []
    def _buscar(data, depth=0):
        if data is None or depth > 6:
            return
        if _es_bloque(data):
            encontrados.append(data); return
        if isinstance(data, (list, tuple)):
            for item in data:
                _buscar(item, depth + 1)
        elif isinstance(data, dict):
            for v in data.values():
                _buscar(v, depth + 1)
    _buscar(resultado)
    bloques = []
    for b in encontrados:
        try:
            pts  = b[0]
            info = b[1]
            texto = str(info[0]).strip() if isinstance(info, (list, tuple)) else str(info).strip()
            conf  = float(info[1]) if isinstance(info, (list, tuple)) and len(info) > 1 else 1.0
            if texto:
                bloques.append((pts, texto, conf))
        except Exception:
            continue
    return bloques




# ─── OCR DIRECTO (MODO SIMPLE) ────────────────────────────────────────────────
def ocr_imagen(
    image_path:      Union[str, Path],
    lang:            str   = "en",
    rtl:             bool  = False,
    vertical:        bool  = False,
    log_cb                 = None,
    precomputed_arr        = None,   # ndarray precalculado por el prefetch worker
) -> str:
    """
    Corre PaddleOCR en la imagen (pasada única, cls=False) y devuelve el texto.

    precomputed_arr — si no es None, se usa directamente como input del OCR
        sin releer el disco ni volver a preprocesar. El OCRWorker lo calcula
        en background mientras el hilo principal procesa la imagen anterior.

    rtl=True      → orden de lectura derecha-izquierda (manga horizontal)
    vertical=True → texto vertical japonés: columnas derecha-a-izquierda,
                    dentro de cada columna de arriba a abajo.
    """
    def log(m):
        print(m)
        if log_cb: log_cb(m)

    path_str = str(image_path)
    ocr = _get_paddle(lang)
    if ocr is None:
        log(f"  [!] PaddleOCR no disponible (lang={lang})")
        return ""

    log(f"  >> {Path(path_str).name}")

    # ── Preprocesar en memoria: rescale + CLAHE + unsharp mask ───────────────
    # Se usa el array precalculado si el OCRWorker lo suministra vía prefetch;
    # si no, se calcula ahora. Fallback a path_str si ambos fallan.
    arr_pre = precomputed_arr if precomputed_arr is not None \
              else _preprocess_for_paddle(path_str)
    ocr_input = arr_pre if arr_pre is not None else path_str

    # ── Pasada única: sin corrección de ángulo (rápida) ──────────────────────
    res1 = None
    try:
        res1 = ocr.ocr(ocr_input, cls=False)
    except Exception as e:
        log(f"  [!] Pasada OCR (cls=False): {e}")

    bloques = _extraer_bloques(res1) if res1 is not None else []
    log(f"  >> {len(bloques)} bloques detectados")

    if not bloques:
        log("  >> OCR sin resultado")
        return ""

    items = []
    for pts, texto, conf in bloques:
        try:
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            items.append({
                "texto": texto,
                "top": min(ys), "bot": max(ys),
                "left": min(xs), "right": max(xs),
                "cx": (min(xs) + max(xs)) / 2,
                "cy": (min(ys) + max(ys)) / 2,
            })
        except Exception:
            continue

    if not items:
        return ""

    alt_media = sum(it["bot"] - it["top"] for it in items) / len(items)

    # ── Detectar gutters reales de la imagen ──────────────────────────────────
    # Se pasa arr_pre si está disponible: evita releer el disco y ya tiene el
    # mismo espacio de coordenadas que los bloques detectados.
    panel_gutters = detect_panel_gutters(arr_pre if arr_pre is not None else path_str)
    if panel_gutters:
        log(f"  >> {len(panel_gutters)} gutters de panel detectados")

    if vertical:
        # ── Texto vertical japonés ────────────────────────────────────────────
        # Agrupar por columnas (eje X), leer columnas de derecha a izquierda,
        # y dentro de cada columna de arriba a abajo.
        col_tol = max(10, min(60, alt_media * 1.0))
        columnas: List[List] = []
        for it in sorted(items, key=lambda x: x["cx"]):
            placed = False
            for col in columnas:
                ref_cx = sum(x["cx"] for x in col) / len(col)
                if abs(it["cx"] - ref_cx) <= col_tol:
                    col.append(it); placed = True; break
            if not placed:
                columnas.append([it])
        columnas.sort(key=lambda c: -sum(x["cx"] for x in c) / len(c))
        lineas = []
        for col in columnas:
            col.sort(key=lambda x: x["cy"])
            lineas.append(" ".join(x["texto"] for x in col))
        return "\n".join(lineas)

    # ── Texto horizontal (LTR o RTL) — Union-Find por solapamiento X ─────────
    # Algoritmo portado de crop_paddle.merge_boxes_bubbles:
    # En lugar de agrupar por bandas Y (que falla cuando dos burbujas side-by-side
    # tienen líneas entrelazadas en Y), usamos Union-Find con solapamiento horizontal
    # como criterio de fusión. Dos bloques pertenecen a la misma burbuja si:
    #   · Su gap Y es < gap_y_intra  Y  su solapamiento X es ≥ 15% del ancho mínimo
    # Son burbujas distintas si:
    #   · Su gap Y es > gap_y_inter  (umbral dinámico basado en alt_media)
    # Palabras en la misma línea (gap Y muy pequeño + gap X pequeño) también se unen.
    # Los gutters detectados en la imagen actúan como barreras absolutas:
    #   · Si entre los bloques A y B existe un gutter real (franja blanca entre paneles),
    #     NO se fusionan aunque todos los demás criterios digan que sí.

    line_h       = alt_media
    gap_y_intra  = max(8,  line_h * 0.65)          # interlineado interno de burbuja
    gap_x_same   = max(20, line_h * 1.80)           # palabras en la misma línea
    gap_y_inter  = max(40, min(110, line_h * 2.5))  # separación entre burbujas distintas
    X_OVERLAP_MIN = 0.15                             # solapamiento X mínimo para fusión

    def _crosses_gutter(bot_a: float, top_b: float) -> bool:
        """True si existe un gutter de panel entre bot_a y top_b."""
        for g_start, g_end, _ in panel_gutters:
            if g_start >= bot_a and g_end <= top_b:
                return True   # gutter completamente contenido en el gap
        return False

    # ── Union-Find ────────────────────────────────────────────────────────────
    n_items = len(items)
    uf = list(range(n_items))

    def _uf_find(x):
        while uf[x] != x:
            uf[x] = uf[uf[x]]
            x = uf[x]
        return x

    def _uf_union(a, b):
        uf[_uf_find(a)] = _uf_find(b)

    # Ordenar por top para que el break del bucle interior sea válido
    by_top = sorted(range(n_items), key=lambda i: items[i]["top"])

    for ii in range(len(by_top)):
        idx_a = by_top[ii]
        a = items[idx_a]
        for jj in range(ii + 1, len(by_top)):
            idx_b = by_top[jj]
            b = items[idx_b]

            y_gap = b["top"] - a["bot"]
            if y_gap > gap_y_inter:
                break  # lista ordenada por top → los siguientes son aún más lejanos

            # ── Barrera de gutter: nunca fusionar si hay un panel real entre ellos ──
            # Independiente de cualquier otro criterio — si hay un gutter de imagen
            # entre bot_a y top_b, son definitivamente de viñetas distintas.
            if y_gap > 0 and panel_gutters and _crosses_gutter(a["bot"], b["top"]):
                continue

            # Solapamiento horizontal
            x_ovlp = min(a["right"], b["right"]) - max(a["left"], b["left"])
            min_w   = min(a["right"] - a["left"], b["right"] - b["left"])
            has_x_ovlp = (x_ovlp / max(min_w, 1)) >= X_OVERLAP_MIN

            if y_gap < 0:
                # Verticalmente superpuestos (texto en capas o multi-columna)
                if has_x_ovlp:
                    _uf_union(idx_a, idx_b)
            elif y_gap <= gap_y_intra:
                if has_x_ovlp:
                    # Misma burbuja: líneas apiladas con alineación horizontal
                    _uf_union(idx_a, idx_b)
                elif y_gap <= line_h * 0.30:
                    # Misma línea horizontal: gap Y muy pequeño, gap X aceptable
                    x_gap = max(a["left"] - b["right"], b["left"] - a["right"], 0)
                    # Umbral estricto (0.6× line_h en vez de 1.8×) para separar
                    # interpalabra real (≤ 0.6× font_h) del gutter entre paneles
                    # adyacentes ("ESPECIALLY FOR YOU." vs globo de diálogo, etc.)
                    if x_gap <= max(15, line_h * 0.60):
                        _uf_union(idx_a, idx_b)

    # ── Agrupar componentes ───────────────────────────────────────────────────
    from collections import defaultdict as _dd
    comp: dict = _dd(list)
    for i in range(n_items):
        comp[_uf_find(i)].append(i)

    # ── Ordenar burbujas por flujo de lectura ─────────────────────────────────
    # Criterio principal: top de la burbuja (de arriba a abajo).
    # Criterio secundario: posición X según RTL/LTR (derecha a izquierda o viceversa).
    def _bub_key(idxs):
        top = min(items[i]["top"]  for i in idxs)
        cx  = sum(items[i]["cx"]   for i in idxs) / len(idxs)
        return (top, -cx if rtl else cx)

    bubbles = sorted(comp.values(), key=_bub_key)

    # ── Dentro de cada burbuja: ordenar líneas + palabras ────────────────────
    bubble_groups: List[List[str]] = []
    bub_tol = max(8, line_h * 0.50)

    for idxs in bubbles:
        bub_items = [items[i] for i in idxs]
        bub_items.sort(key=lambda it: it["cy"])

        # Agrupar por líneas horizontales dentro de la burbuja
        lineas_grp: List[List] = []
        for it in bub_items:
            placed = False
            for lg in lineas_grp:
                ref = sum(x["cy"] for x in lg) / len(lg)
                if abs(it["cy"] - ref) <= bub_tol:
                    lg.append(it); placed = True; break
            if not placed:
                lineas_grp.append([it])

        lineas_grp.sort(key=lambda lg: sum(x["cy"] for x in lg) / len(lg))
        lineas_txt = []
        for lg in lineas_grp:
            lg_s = sorted(lg, key=lambda it: -it["cx"] if rtl else it["cx"])
            lineas_txt.append(" ".join(it["texto"] for it in lg_s))
        bubble_groups.append(lineas_txt)

    return "\n".join(" ".join(grp) for grp in bubble_groups)


# ─── POST-PROCESO COMPLETO ────────────────────────────────────────────────────
# Portado de Motor_Paddle_OCR.py — punto único de limpieza de texto

_CJK_RE = re.compile(
    r'[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF'
    r'\u3040-\u309F\u30A0-\u30FF'
    r'\uAC00-\uD7AF\u1100-\u11FF]'
)

def _contains_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _merge_hyphenated_words(text: str) -> str:
    """
    Fusiona fragmentos partidos por guión (THINK-\nING → THINKING).

    Guarda de fusión: si el fragmento derecho empieza en mayúscula Y es una
    palabra independiente válida en inglés (según pyspellchecker), NO se fusiona.
    Esto separa interrupciones de burbuja ("Mishi-\nRight!") de particiones
    silábicas reales ("CON-\nTROLLING").
    Si pyspellchecker no está instalado, la guarda no aplica (se fusiona igual
    que antes para no perder funcionalidad).
    """
    spell = _get_spell()

    def _should_fuse(left: str, right: str) -> bool:
        """
        True si los fragmentos deben fusionarse en una sola palabra.
        False si el fragmento derecho es una palabra independiente (interrupción).

        Jerarquía de decisión (solo entra si right[0].isupper() y right válido):
          Regla 1 — Combinada válida: si left+right forma una palabra del
            diccionario (anyway, whatever...) → fusionar siempre.
          Regla 2 — Ambas partes son palabras autónomas con mayúscula:
            left[0].isupper() Y left en dict → interrupción real de burbuja.
          Regla 3 — Left es nombre propio desconocido (mayúscula, no en dict,
            longitud ≥4) → interrupción de personaje.
          Regla 4 — Default: left es prefijo/palabra-minúscula sin autonomía
            → partición silábica OCR → fusionar.
        """
        if not right or not spell:
            return True
        right_clean = re.sub(r"[^a-zA-Z]", "", right).lower()
        if not right_clean or len(right_clean) < 3:
            return True

        if right[0].isupper() and right_clean in spell:
            left_clean = re.sub(r"[^a-zA-Z]", "", left).lower()
            combined   = left_clean + right_clean
            if combined in spell:
                return True
            if left[0].isupper() and left_clean in spell:
                return False
            if left[0].isupper() and left_clean not in spell and len(left_clean) >= 4:
                return False
            return True

        return True

    # ── 1) Partición cross-línea ──────────────────────────────────────────────
    def _fuse_cross(m):
        return m.group(1) + m.group(2) if _should_fuse(m.group(1), m.group(2)) else m.group(0)

    text = re.sub(
        r'(\w{2,})-\s*\n\s*(\w+)',
        _fuse_cross,
        text,
    )

    # ── 2) Partición en la misma línea ────────────────────────────────────────
    def _fuse_same(m):
        return m.group(1) + m.group(2) if _should_fuse(m.group(1), m.group(2)) else m.group(0)

    text = re.sub(
        r'\b(\w{2,})-\s+(\w{2,})',
        _fuse_same,
        text,
    )

    return text


def _remove_scan_marks(text: str) -> str:
    """Elimina líneas de watermark: QUANTUMSCANS, 'read on...', dominios .org, etc."""
    text = re.sub(
        r'^.*?(?:(?:u|q)antum\s+scans|read\s+on\s+(?:\S+\s+)*the\s+fastest\s+releases).*$',
        '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'\b(?:quantumscans?|qbantumscans?)\b.*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b\S+\.org\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'^\s+$', '', text, flags=re.MULTILINE)
    return text.strip()


def _fix_ocr_artifacts(text: str) -> str:
    replacements = [
        (r'(?<!\w)(\d)(the\b)',          r'\2'),   # "1the" → "the" (borde de panel)
        (r'(?<!\w)(\d)(a\b|an\b|it\b)',  r'\2'),   # "1a", "1an", "1it" → limpio
        (r'\b[Ff]\s+0\b', ''),                     # "F 0" → artefacto de borde
        # ELIMINADO: r'\b[Uu]\s+[Ll][Hh]\b' → podía borrar fragmentos de diálogo
        (r'\b\d+\s+[A-Za-z]\s+\d+\b', ''),        # "3 X 7" → artefacto numérico
        (r'\s+1\s*$', ''),                         # "texto 1" al final de línea
        # CORREGIDO: I! solo se elimina cuando va pegado a un dígito o al inicio
        # de línea con símbolo — evitaba que "IT" (leído como "I!") desapareciera
        (r'(?<=\d)\s*I!\s*', ' '),                 # "3I!" → " " (borde de panel numérico)
        (r'^I!\s*', ''),                            # "I! texto" solo al inicio absoluto de línea
        # ELIMINADO: r'\s+TE\s*$' y r'\s+TE\s+' → borraban "THE" mal leído como "TE"
        #   en medio de diálogo CAPS; nunca fue un artefacto confiable
        (r'\b75\s+T\s+I\b', ''),    (r'\bH\s+T\b', ''),  # artefactos muy específicos
        (r'^\+{2,}\s*$', ''),       (r'^\+{2,}\s*[A-Z]?\s*$', ''),
        # ELIMINADO: r'\bte\b' → con IGNORECASE borraba "TE","Te","te" como palabra
        #   suelta, eliminando "THE" mal leído y cualquier "te" legítimo en diálogo
    ]
    for pat, repl in replacements:
        text = re.sub(pat, repl, text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    return text


_SFX_RE = re.compile(
    r'^(?:[A-Z]{2,}\-[A-Z]{2,}|[A-Z]{3,}(?:GH|RR|NG|BOOM|BANG|CRASH|WHAM|'
    r'POW|ZAP|SLAM|CRACK|THUD|WHOOSH|SPLASH|GRUNT|GASP|GULP|SIGH|YELP|'
    r'ROAR|GROWL|HISS|BUZZ|CLICK|CLACK|SNAP|THUMP|RUMBLE|SCREECH|'
    r'SCREAMS?|YELLS?|CRIES|AHH+|OHH+|UGH+|ARG+H?|GRR+|AHEM|'
    r'HAHA+|HEHE+|HMM+|TSK|KA(?:POW|BOOM)|Z+|HA)+$)',
    re.IGNORECASE)

def _is_onomatopoeia(word: str) -> bool:
    return bool(_SFX_RE.match(word.strip()))


# Palabras cortas válidas en diálogo de manga — protegidas antes de garbage_patterns.
# Sin esto, "OH","HA","HM" pasaban el check len<=2 pero luego eran eliminadas
# por el patrón ^[A-Z]{2}$ en garbage_patterns.
_MANGA_OK: frozenset = frozenset({
    # Artículo y pronombre — len=1, sin esto son filtrados como basura
    'i','a',
    'it','is','at','an','in','of','or','if','to','up','my','by','as','us','we','me','be','do','so',
    'no','ok','go','hi','oh','ah','aw','ew','ow','ha','he','hm','eh','uh','um','er','yo','oi','ay','oy',
    'hey','huh','hmm','aah','ooh','tch','tsk','bah','meh','yep','nah','duh','wow','yay','oof','ugh','boo','aha','pfft','yes',
    # Palabras de 2 letras comunes en diálogo
    'am','do','go','he','if','is','it','me','my','no','of','ok','on','or','so','to','up','us','we',
})

# ── Precompilados a nivel de módulo — se crean UNA sola vez ──────────────────
_VALID_CLUSTERS = re.compile(
    r'^(?:str|sch|scr|shr|spl|spr|squ|thr|chr|phr|nth|ph|wh|sh|ch|gh|kn|wr|ps)',
    re.IGNORECASE)
_CONSONANT_CLUSTER_RE = re.compile(r'^[bcdfghjklmnpqrstvwxyz]{3}', re.IGNORECASE)
_SHORT_SFX_RE = re.compile(r'^[A-Za-z]{1,6}[-…!?.]+\s*$')
_GARBAGE_COMPILED = [re.compile(p) for p in [
    r'^[A-Z]\s+\d+$',          r'^[A-Z]\s+[A-Z]{2}$',
    r'^\d+\s+[A-Z]\s+\d+$',    r'^\+\+\+\s+[A-Z]$',
    r'^[B-DF-HJ-NP-TV-Z]{2}$', r'^[A-Z]$',
    r'^\d{3,}$',
    r'^[A-Z]\s+[A-Z]\s+[A-Z]$',r'^\s*\+\+\+\s*[A-Z]\s*$',
    r'^\s*[A-Z]\s+\d+\s*$',    r'^\s*\d+\s+[A-Z]\s*$',
    r'^\+{2,}\s*[A-Z]?\s*$',   r'.*[↑↓→←▲▼►◄]+.*',
]]

def _is_obvious_garbage(line: str) -> bool:
    stripped = line.strip()
    if not stripped: return True
    if _contains_cjk(stripped): return False
    if _is_onomatopoeia(stripped): return False
    if _SHORT_SFX_RE.match(stripped): return False
    # Whitelist ANTES de garbage_patterns — evita que ^[A-Z]{2}$ elimine "OH","HA","HM"
    if stripped.lower() in _MANGA_OK: return False
    if len(stripped) <= 2: return True
    if stripped.isdigit(): return True
    for pat in _GARBAGE_COMPILED:
        if pat.match(stripped): return True
    letter_count = sum(ch.isalpha() for ch in stripped)
    if len(stripped) > 4 and letter_count / len(stripped) < 0.15: return True
    # Clúster inicial de consonantes imposible en inglés → basura OCR
    if (len(stripped) >= 5
            and _CONSONANT_CLUSTER_RE.match(stripped)
            and not _VALID_CLUSTERS.match(stripped)):
        return True
    return False


def _filter_garbage(text: str, remove_sfx: bool = False) -> str:
    if not text: return text
    result = []
    for line in text.split('\n'):
        stripped = line.strip()
        # Preservar siempre separadores visuales y nombres de imagen
        if _SEP_RE.match(stripped) or _IMG_RE.match(stripped):
            result.append(line); continue
        if remove_sfx and _is_onomatopoeia(stripped): continue
        if _is_obvious_garbage(line): continue
        result.append(line)
    return '\n'.join(result)


def _remove_duplicate_phrases(text: str) -> str:
    lines   = text.split('\n')
    cleaned = []; prev = None; count = 0
    for line in lines:
        stripped = line.strip()
        if stripped == prev and stripped:
            count += 1
            if count <= 1: cleaned.append(line)
        else:
            count = 0; cleaned.append(line)
        prev = stripped
    return '\n'.join(cleaned)


def _fix_dollar_sign(text: str) -> str:
    return re.sub(r'\$([A-Z])', r'S\1', text)


def _fix_contractions(text: str) -> str:
    # Contracciones largas: "couldn't" leído como "coulon't", "shouldn't" como "shoulon't"
    text = re.sub(r'\b([A-Za-z]{4,})on\'t\b', r"\1DN'T", text, flags=re.IGNORECASE)
    text = re.sub(r'\b([A-Za-z]{4,})n,t\b',   r"\1N'T",  text, flags=re.IGNORECASE)
    # Contracciones cortas: "Didn't" leído como "Dion't" (OCR confunde 'dn' con 'on')
    # Patrón: 1–3 letras + "ion't" → mismas letras + "idn't"
    # "Dion't" → prefix="D", ion't → "D"+"idn't" → "Didn't"
    # "DION'T" → prefix="D", ION'T → "D"+"IDN'T" → "DIDN'T"
    def _restore_short_contraction(m):
        prefix = m.group(1)
        full_match = m.group(0)
        # Detectar case mirando el primer char DEL SUFIJO "ion't" (no el prefijo solo)
        # "Dion't": primer char después del prefix es 'i' (minúscula) → "idn't"
        # "DION'T": primer char después del prefix es 'I' (mayúscula) → "IDN'T"
        first_suffix_char = full_match[len(prefix)]  # 'i' o 'I'
        suffix = "IDN'T" if first_suffix_char.isupper() else "idn't"
        return prefix + suffix
    text = re.sub(
        r"\b([A-Za-z]{1,3})ion't\b",
        _restore_short_contraction,
        text,
        flags=re.IGNORECASE,
    )
    # Apóstrofo fusionado: "i'say" → "I say", "i'really" → "I really"
    # Solo cuando sigue una palabra real de 3+ letras (no contracciones: 'm, 'll, 've…)
    text = re.sub(r"\bi'([a-zA-Z]{3,})\b", r"I \1", text)
    return text


# ─── CORRECTOR ESTADÍSTICO (pyspellchecker) ──────────────────────────────────
# Corrige errores sistemáticos de PaddleOCR en texto inglés de manga sin
# necesitar diccionarios manuales. Funciona con cualquier palabra en inglés.
#
# Errores que resuelve:
#   1. Mixed-case aleatorio:  HeAr→hear, WhAt→what, lIKE→like, yOu→you
#   2. Confusión de chars:    uith→with, neus→news, on1y→only, pouer→power
#   3. Errores residuales:    begause→because, minoraur→minotaur
#
# No toca: todo-CAPS válido, SFX/onomatopeyas, contracciones, nombres propios.

_spell_checker  = None
_spell_enabled  = True   # se pone False si pyspellchecker no está instalado
_spell_cache: Dict[str, str] = {}   # caché palabra_lower → corrección_lower

# Sustituciones de dígitos/símbolos OCR → letras
_DIGIT_MAP = str.maketrans("01568|\\", "oisgbil")

# Confusiones de secuencia de caracteres frecuentes en PaddleOCR
_OCR_SEQ_SUBS = [("u", "w"), ("n", "u"), ("rn", "m")]

# Patrón de palabras que NUNCA se corrigen:
#   - sin letras, muy cortas, contracciones, compuestas con guión
#   - cualquier letra repetida 3+ veces (HAAAAH, GRR, ZZZ → SFX/exclamaciones)
_SPELL_SKIP_RE = re.compile(
    r"^(?:[^a-zA-Z]+|.{1,2}|.*['\-].*|.*(.)\1{2,}.*)$"
)


def _get_spell():
    """Retorna instancia SpellChecker, o None si no está instalado."""
    global _spell_checker, _spell_enabled
    if not _spell_enabled:
        return None
    if _spell_checker is not None:
        return _spell_checker
    try:
        from spellchecker import SpellChecker
        _spell_checker = SpellChecker()
    except ImportError:
        _spell_enabled = False
    return _spell_checker


def _is_mixed_case_ocr(word: str) -> bool:
    """
    True si la palabra tiene capitalización aleatoria típica de OCR en manga.
    Ejemplos positivos: HeAr, WhAt, lIKE, hAD, yOu, DiD, ArounD, BEeen
    Ejemplos negativos: WELL, But, hello, I (estos son case válido)
    """
    if word.isupper() or word.islower():
        return False
    if word[0].isupper() and word[1:].islower():
        return False   # capitalización normal tipo "Hello"
    # Hay mayúsculas mezcladas con minúsculas en posiciones inesperadas
    return any(c.isupper() for c in word[1:]) and any(c.islower() for c in word)


def _ocr_candidates(word_low: str) -> List[str]:
    """
    Genera variantes de la palabra aplicando sustituciones de confusión OCR.
    El orden importa: se prueba primero el candidato más probable.
    """
    candidates = []
    # Sustituir dígitos/símbolos por letras similares
    replaced = word_low.translate(_DIGIT_MAP)
    if replaced != word_low:
        candidates.append(replaced)
    # Sustituciones de secuencia (u→w es la más frecuente en manga)
    for wrong, right in _OCR_SEQ_SUBS:
        if wrong in word_low:
            candidates.append(word_low.replace(wrong, right))
    return candidates


def _restore_case(original: str, corrected: str) -> str:
    """Aplica la capitalización del original a la palabra corregida."""
    if original.isupper():
        return corrected.upper()
    if original[0].isupper() and original[1:].islower():
        return corrected.capitalize()
    return corrected


def _levenshtein(a: str, b: str) -> int:
    """Distancia de edición mínima entre dos strings."""
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j+1]+1, curr[j]+1, prev[j]+(ca != cb)))
        prev = curr
    return prev[-1]


def _safe_correction(original: str, corrected: str) -> bool:
    """
    Decide si una corrección estadística es segura para aplicar.

    Rechaza correcciones que:
    - Reducen la longitud más de 2 caracteres (p.ej. "wataru"→"water" pierde 2,
      pero "arakida"→"arabia" pierde 3 → rechazada).
    - Tienen distancia de edición > 2 respecto al original (cambio demasiado grande
      para ser un error tipográfico de OCR; más probablemente un nombre propio).
    - El original tiene ≥7 letras y la distancia es > 1 (nombres largos son casi
      siempre propios; solo corregir si hay 1 carácter equivocado claro).

    Esta función es agnóstica al idioma y al contenido: solo evalúa geometría
    de edición, por lo que funciona igual con cualquier nombre propio sin necesitar
    un diccionario manual.
    """
    dist = _levenshtein(original, corrected)
    len_diff = len(original) - len(corrected)  # positivo = corrected es más corto

    # Corrección demasiado agresiva en longitud
    if len_diff > 2:
        return False
    # Distancia de edición demasiado grande
    if dist > 2:
        return False
    # Para palabras de 5+ caracteres solo aceptar correcciones de 1 carácter.
    # Con dist=2 el corrector estadístico sustituye nombres propios por palabras
    # comunes frecuentes (wataru→water, mihail→mihai...) sin que haya un error
    # OCR real. Los errores genuinos de OCR de 1 char (uith→with, neus→news)
    # son suficientemente capturados con dist=1.
    if len(original) >= 5 and dist > 1:
        return False
    # Bloquear el patrón "última letra eliminada en palabra corta":
    # El spellchecker sugiere "rum" para "rumi", "him" para "himi", etc. — en
    # manga estos son nombres propios, no errores OCR. Un error OCR real añade
    # o sustituye caracteres, rara vez elimina exactamente la última letra de
    # una palabra corta. Regla: si corrected == original[:-1] (mismo prefijo,
    # solo falta la última letra) en palabras de ≤7 chars → rechazar.
    if (len(original) <= 7
            and len_diff == 1
            and original.lower().startswith(corrected.lower())
            and len(corrected) == len(original) - 1):
        return False
    return True


def _correct_word(word: str, spell, known_names: Set[str]) -> str:
    """
    Corrige una sola palabra del texto OCR de manga.
    Usa caché por palabra lowercase para evitar recalcular palabras repetidas.
    """
    if not word or _SPELL_SKIP_RE.match(word):
        return word
    if re.search(r"[^a-zA-Z0-9'\-]", word):
        return word

    low = word.lower()

    # Caché global — evita recalcular correcciones en palabras repetidas
    if low in _spell_cache:
        corrected_low = _spell_cache[low]
        return _restore_case(word, corrected_low) if corrected_low != low else word

    if low in known_names or word in known_names:
        _spell_cache[low] = low
        return word

    # ── Estrategia 1: mixed-case aleatorio ───────────────────────────────────
    if _is_mixed_case_ocr(word):
        if low in spell:
            _spell_cache[low] = low
            return low
        corrected = spell.correction(low)
        if corrected and corrected != low and _safe_correction(low, corrected):
            _spell_cache[low] = corrected
            return corrected
        _spell_cache[low] = low
        return low

    # ── Estrategia 2: error de carácter en palabra con case normal ───────────
    if low not in spell:
        for cand in _ocr_candidates(low):
            if cand in spell:
                _spell_cache[low] = cand
                return _restore_case(word, cand)
        if not any(c.isdigit() for c in low):
            corrected = spell.correction(low)
            if corrected and corrected != low and _safe_correction(low, corrected):
                _spell_cache[low] = corrected
                return _restore_case(word, corrected)

    _spell_cache[low] = low
    return word


def _spellcheck_line(line: str, spell, known_names: Set[str]) -> str:
    """Aplica corrección estadística a una línea completa preservando espacios."""
    if not line.strip() or _contains_cjk(line):
        return line
    # Tokenizar preservando espacios y puntuación pegada
    parts = re.split(r'(\s+)', line)
    return ''.join(
        _correct_word(t, spell, known_names) if t.strip() else t
        for t in parts
    )


def _spellcheck_text(text: str, known_names: Set[str]) -> str:
    """Aplica _spellcheck_line a cada línea del texto OCR."""
    spell = _get_spell()
    if spell is None:
        return text   # pyspellchecker no instalado → no-op silencioso
    return '\n'.join(
        _spellcheck_line(line, spell, known_names)
        for line in text.split('\n')
    )


def post_process_ocr_text(
    text:      str,
    case_mode: str      = "original",
    vocab:     Set[str] = None,
    keep_sfx:  bool     = True,
) -> str:
    """
    Post-procesado completo del texto OCR.
    Incluye corrector estadístico (pyspellchecker) que corrige de forma general
    los errores de PaddleOCR en texto inglés de manga sin diccionarios manuales.
    """
    if not text: return text
    if vocab is None: vocab = set()

    text = text.replace('\r', '\n')
    text = re.sub(r'([!?,;:])([A-Za-z])', r'\1 \2', text)
    # Merge de palabras partidas PRIMERO — antes de convertir guiones en em-dash.
    # Si el em-dash corre antes: "com-" → "com—" y "fortable" queda huérfano.
    # Orden correcto: unir particiones → luego convertir guiones residuales en —
    text = _merge_hyphenated_words(text)
    # Normalizar em-dash: guiones residuales al final de línea (palabras cortas)
    # Solo aplica a palabras que NO fueron fusionadas en el paso anterior.
    text = re.sub(r'\b(\w{1,5})-\s*$', r'\1—', text, flags=re.MULTILINE)
    text = _remove_scan_marks(text)
    text = _fix_ocr_artifacts(text)
    text = _remove_duplicate_phrases(text)
    text = _fix_dollar_sign(text)
    text = _fix_contractions(text)
    text = _filter_garbage(text, remove_sfx=not keep_sfx)

    # Corrector estadístico: funciona con cualquier palabra en inglés
    # Los nombres propios del vocab se protegen automáticamente
    text = _spellcheck_text(text, known_names=vocab)

    if   case_mode == "upper":     text = text.upper()
    elif case_mode == "lower":     text = text.lower()
    elif case_mode == "capitalize":
        text = ". ".join(s.strip().capitalize() for s in text.split(". "))

    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
    return text.strip()


# Alias de compatibilidad para imports externos
def post_proceso_minimo(texto: str, case_mode: str = "original") -> str:
    return post_process_ocr_text(texto, case_mode=case_mode)


# ─── EXTRACCIÓN DE VIDEO ──────────────────────────────────────────────────────
def extract_video_frames(video_path: str, fps: float = 1.0, log_cb=None) -> List[str]:
    def log(m):
        print(m)
        if log_cb: log_cb(m)
    frames = []
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            log(f"[Video] No se pudo abrir: {video_path}"); return frames
        video_fps = cap.get(cv2.CAP_PROP_FPS) or 24
        frame_interval = max(1, int(video_fps / fps))
        out_dir = Path(video_path).parent / "frames"
        out_dir.mkdir(exist_ok=True)
        for _old in sorted(out_dir.glob("frame_*.png")):
            try: _old.unlink()
            except Exception: pass
        idx = saved = 0
        while True:
            ret, frame = cap.read()
            if not ret: break
            if idx % frame_interval == 0:
                fname = out_dir / f"frame_{saved:05d}.png"
                cv2.imwrite(str(fname), frame)
                frames.append(str(fname)); saved += 1
            idx += 1
        cap.release()
        log(f"[Video] {saved} frames extraídos")
    except ImportError:
        log("[Video] OpenCV no disponible")
    except Exception as e:
        log(f"[Video] Error: {e}")
    return frames


# ─── VOCAB ────────────────────────────────────────────────────────────────────
_UNIFIED_CACHE: Optional[Dict] = None

def _load_unified() -> Dict[str, str]:
    global _UNIFIED_CACHE
    if _UNIFIED_CACHE is not None:
        return _UNIFIED_CACHE
    try:
        if VOCAB_UNIFIED_FILE.exists():
            data = json.loads(VOCAB_UNIFIED_FILE.read_text(encoding="utf-8"))
            _UNIFIED_CACHE = {e["word"]: e["lang"] for e in data.get("entries", [])}
        else:
            _UNIFIED_CACHE = {}
    except Exception:
        _UNIFIED_CACHE = {}
    return _UNIFIED_CACHE

def load_vocab_for_lang(ocr_lang: str) -> Set[str]:
    unified = _load_unified()
    if ocr_lang == "es":                             allowed = {"es", "sfx", "genre"}
    elif ocr_lang in ("japan", "korean", "ch", "chinese_cht"): allowed = {"ja", "en", "sfx", "genre"}
    elif ocr_lang == "pt":                           allowed = {"es", "en", "sfx", "genre"}
    else:                                            allowed = {"en", "sfx", "genre"}
    return {w for w, l in unified.items() if l in allowed}

def save_vocab_unified(vocab_dict: Dict[str, str]):
    global _UNIFIED_CACHE
    _UNIFIED_CACHE = vocab_dict.copy()
    entries = [{"word": w, "lang": vocab_dict[w]} for w in sorted(vocab_dict)]
    data = {"version": "1.0", "description": "Vocabulario unificado AutoScribe", "entries": entries}
    try:
        VOCAB_UNIFIED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# ─── WORKER OCR ───────────────────────────────────────────────────────────────
class OCRWorker(QThread):
    """
    Worker QThread — Motor OCR principal de AutoScribe.

    Parámetros clave:
      crop_pipeline    : True → pipeline por burbujas (autounify_crop_paddle)
                         False → OCR directo por imagen (por defecto)
      vertical_japanese: True → lectura en columnas para texto vertical japonés.
                         Solo activar manualmente cuando el contenido lo requiera.
                         No afecta el funcionamiento cuando está desactivado.
    """
    progress        = pyqtSignal(int)
    status_msg      = pyqtSignal(str)
    log_msg         = pyqtSignal(str)
    finished_ok     = pyqtSignal(str)
    error           = pyqtSignal(str)
    new_words_found = pyqtSignal(set)
    stats_update    = pyqtSignal(dict)

    def __init__(
        self,
        image_paths:      List[Path],
        output_folder:    str,
        fmt:              str  = "txt",
        translate_to:     str  = "",
        case_mode:        str  = "original",
        folder_name:      str  = "output",
        ocr_lang:         str  = "en",
        use_gpu:          bool = False,
        online_learning:  bool = False,
        keep_sfx:         bool = True,
        rtl:              bool = False,
        crop_pipeline:    bool = False,
        vertical_japanese: bool = False,
    ):
        super().__init__()
        self.image_paths      = image_paths
        self.output_folder    = output_folder
        self.fmt              = fmt
        self.translate_to     = translate_to
        self.case_mode        = case_mode
        self.folder_name      = folder_name
        self.ocr_lang         = ocr_lang
        self.use_gpu          = use_gpu
        self.online_learning  = online_learning
        self.keep_sfx         = keep_sfx
        self.rtl              = rtl
        self.crop_pipeline    = crop_pipeline
        self.vertical_japanese = vertical_japanese
        self._cancel          = False

    def cancel(self):
        self._cancel = True

    def _ocr_imagen_simple(self, img_path: Path, precomputed_arr=None) -> str:
        """OCR directo en la imagen completa. Acepta array preprocesado del prefetch."""
        if img_path.suffix.lower() in SUPPORTED_VID:
            frames = extract_video_frames(
                str(img_path), fps=1.0,
                log_cb=lambda m: self.log_msg.emit(m))
            textos = []
            for f in frames:
                if self._cancel: break
                t = ocr_imagen(Path(f), lang=self.ocr_lang, rtl=self.rtl,
                               vertical=self.vertical_japanese,
                               log_cb=lambda m: self.log_msg.emit(m))
                if t.strip():
                    textos.append(t.strip())
            return "\n\n".join(textos)
        return ocr_imagen(
            img_path,
            lang            = self.ocr_lang,
            rtl             = self.rtl,
            vertical        = self.vertical_japanese,
            log_cb          = lambda m: self.log_msg.emit(m),
            precomputed_arr = precomputed_arr,
        )

    def _ocr_imagen_crop(self, img_path: Path) -> str:
        """OCR con pipeline de detección de burbujas."""
        from ocr.crop_paddle import extract_text_with_crop_pipeline
        reading_order = "rtl" if self.rtl else "ltr"
        return extract_text_with_crop_pipeline(
            image_path=img_path,
            lang=self.ocr_lang,
            reading_order=reading_order,
            use_gpu=self.use_gpu,
            vertical=self.vertical_japanese,
            log_cb=lambda m: self.log_msg.emit(m),
        )

    def run(self):
        # ── ProcessManager: suspender apps pesadas, elevar prioridad CPU ──────
        # Libera RAM y ciclos de CPU antes de que PaddleOCR cargue su modelo.
        # thaw() se llama en el bloque finally → garantizado incluso con error.
        _snap = None
        try:
            from pipeline.process_manager import ProcessSnapshot
            _snap = ProcessSnapshot()
            _snap.freeze(log_cb=lambda m: self.log_msg.emit(m))
        except Exception as _pm_err:
            self.log_msg.emit(f"[ProcessMgr] No disponible: {_pm_err}")

        try:
            from concurrent.futures import ThreadPoolExecutor
            total = len(self.image_paths)
            pages_raw:  List[tuple] = []
            paginas:    List[str]   = []
            total_chars = total_words = 0

            modo = "Crop-Burbujas" if self.crop_pipeline else "Simple"
            vert = " + Vertical" if self.vertical_japanese else ""
            self.log_msg.emit(
                f"[Motor] Modo: {modo}{vert} | Lang: {self.ocr_lang} | "
                f"{'RTL' if self.rtl else 'LTR'} | {total} imagen(es)"
            )

            vocab = load_vocab_for_lang(self.ocr_lang)

            # ── Prefetch: preprocesar imagen N+1 en background mientras se ──
            # ejecuta el OCR de la imagen N. ThreadPoolExecutor con 1 worker
            # porque el cuello de botella es PaddleOCR (single-thread), no el
            # preprocesamiento. El worker solo hace PIL+CLAHE+unsharp (~30 ms).
            with ThreadPoolExecutor(max_workers=1, thread_name_prefix="pre") as _pool:

                # Lanzar preproceso de la primera imagen antes del bucle
                _future_pre = (
                    _pool.submit(_preprocess_for_paddle, str(self.image_paths[0]))
                    if total > 0 and not self.crop_pipeline
                    else None
                )

                for i, img_path in enumerate(self.image_paths):
                    if self._cancel:
                        break

                    self.status_msg.emit(f"[Motor] {img_path.name} ({i+1}/{total})")
                    self.log_msg.emit(f"▸ {img_path.name}")

                    # Recoger array preprocesado (ya listo, calculado en paralelo)
                    _arr_pre = None
                    if _future_pre is not None:
                        try:
                            _arr_pre = _future_pre.result()
                        except Exception:
                            _arr_pre = None
                        _future_pre = None

                    # Lanzar preproceso de la siguiente imagen YA (en paralelo
                    # con el OCR que arranca ahora en el hilo principal)
                    if not self.crop_pipeline and i + 1 < total:
                        _future_pre = _pool.submit(
                            _preprocess_for_paddle, str(self.image_paths[i + 1])
                        )

                    if self.crop_pipeline:
                        txt = self._ocr_imagen_crop(img_path)
                    else:
                        txt = self._ocr_imagen_simple(img_path, precomputed_arr=_arr_pre)

                    if txt and txt.strip():
                        pages_raw.append((img_path.name, txt.strip()))
                        total_chars += len(txt.strip())
                        total_words += len(txt.strip().split())

                    self.progress.emit(int((i + 1) / total * 85))
                    self.stats_update.emit({
                        "images": i + 1, "total": total,
                        "chars": total_chars, "words": total_words,
                    })

            if self._cancel:
                self.error.emit("Cancelado por el usuario."); return

            # ── Post-proceso por página + separadores visuales ───────────────
            self.status_msg.emit("Post-procesando...")
            self.log_msg.emit(
                f"[Post] scan-marks, artifacts, garbage, vocab ({len(vocab)} palabras)"
            )
            for img_name, raw_txt in pages_raw:
                txt_clean = post_process_ocr_text(
                    raw_txt,
                    case_mode = self.case_mode,
                    vocab     = vocab,
                    keep_sfx  = self.keep_sfx,
                )
                if txt_clean.strip():
                    paginas.append(
                        f"{_SEP_LINE}\n{img_name}\n{_SEP_LINE}\n{txt_clean.strip()}"
                    )

            texto_final = "\n".join(paginas)

            if self.translate_to and texto_final.strip():
                self.status_msg.emit("Traduciendo...")
                # La traducción la gestiona AutoScribe via TranslationWorker.
                # Motor_Paddle_OCR sólo emite el texto; AutoScribe aplica
                # translate_structured / translate_structured_argos sobre él.

            self.progress.emit(95)
            out_dir  = Path(self.output_folder)
            out_dir.mkdir(parents=True, exist_ok=True)
            base     = self.folder_name or "output"
            fmt_low  = self.fmt.lower().replace(".", "")
            out_path = out_dir / f"{base}.{fmt_low}"
            if out_path.exists():
                import time as _t
                out_path = out_dir / f"{base}_{int(_t.time())}.{fmt_low}"

            if fmt_low == "docx":
                try:
                    from docx import Document
                    from docx.shared import Pt
                    doc = Document()
                    doc.styles["Normal"].font.name = "Arial"
                    doc.styles["Normal"].font.size = Pt(11)
                    for linea in texto_final.split("\n"):
                        doc.add_paragraph(linea)
                    doc.save(str(out_path))
                except ImportError:
                    out_path = out_path.with_suffix(".txt")
                    out_path.write_text(texto_final, encoding="utf-8")
            else:
                out_path.write_text(texto_final, encoding="utf-8")

            self.progress.emit(100)
            self.stats_update.emit({
                "images": total, "total": total,
                "chars": len(texto_final), "words": len(texto_final.split()),
            })
            self.log_msg.emit(f"✓ Guardado: {out_path}")
            self.finished_ok.emit(str(out_path))

        except Exception as e:
            import traceback as _tb
            tb_str = _tb.format_exc()
            print(tb_str)
            self.error.emit(f"Error crítico: {e}\n\n{tb_str}")

        finally:
            # ── Restaurar procesos y prioridad CPU siempre ───────────────────
            if _snap is not None:
                try:
                    _snap.thaw(log_cb=lambda m: self.log_msg.emit(m))
                except Exception:
                    pass


# ─── WORKER UNIFY ─────────────────────────────────────────────────────────────
class UnifyWorker(QThread):
    """Worker QThread para AutoUnify. Coordina autounify.py."""
    progress   = pyqtSignal(int)
    status_msg = pyqtSignal(str)
    finished   = pyqtSignal(list)
    error      = pyqtSignal(str)

    def __init__(self, src_folder: str, ocr_lang: str = "en",
                 max_height: int = 3000, safe_cut: bool = True,
                 save_remnant: bool = False):
        super().__init__()
        self.src_folder   = src_folder
        self.ocr_lang     = ocr_lang
        self.max_height   = max_height
        self.safe_cut     = safe_cut
        self.save_remnant = save_remnant
        self._cancel      = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            from pipeline.autounify import autounify_img_in_folder
            paths = autounify_img_in_folder(
                self.src_folder, self.max_height, self.ocr_lang,
                self.safe_cut, self.save_remnant,
                progress_cb=lambda p: self.progress.emit(p),
                log_cb=lambda m: self.status_msg.emit(m))
            self.finished.emit(paths)
        except Exception as e:
            self.error.emit(str(e))


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python Motor_Paddle_Simple.py <imagen_o_carpeta> [lang] [rtl] [--vertical] [--crop]")
        sys.exit(1)
    target   = Path(sys.argv[1])
    lang     = sys.argv[2] if len(sys.argv) > 2 else "en"
    rtl      = len(sys.argv) > 3 and sys.argv[3].lower() == "rtl"
    vertical = "--vertical" in sys.argv
    crop     = "--crop" in sys.argv
    imgs = [target] if target.is_file() else sorted(
        f for f in target.iterdir() if f.suffix.lower() in SUPPORTED_IMG)
    for img in imgs:
        print(f"\n{'='*60}\n{img.name}\n{'='*60}")
        if crop:
            from ocr.crop_paddle import extract_text_with_crop_pipeline
            t = extract_text_with_crop_pipeline(
                img, lang=lang, reading_order="rtl" if rtl else "ltr",
                vertical=vertical, log_cb=print)
        else:
            t = ocr_imagen(img, lang=lang, rtl=rtl, vertical=vertical, log_cb=print)
        print(t if t.strip() else "(sin texto detectado)")