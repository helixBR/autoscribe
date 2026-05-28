"""
crop_paddle.py — Etapa 2: Detección, recorte y preprocesado de burbujas de texto
=================================================================================
AutoScribe v1.0 — Módulo intermedio entre autounify.py y Motor_Paddle_OCR.py

PIPELINE:
  1. PaddleOCR detecta cajas de texto (líneas individuales)
  2. merge_boxes_bubbles() fusiona cajas cercanas → una por burbuja/narración
  3. Cada burbuja se recorta, preprocesa y se pasa al OCR
  4. Una línea de texto por burbuja → output limpio

PREPROCESADO AUTOMÁTICO (transparente):
  - Resolución: upscale si el recorte es muy pequeño, downscale si es enorme
  - Fondo oscuro (texto narrativo/flotante): inversión de bits + escala de grises
    → PaddleOCR trabaja siempre con texto negro sobre blanco puro
  - Binarización adaptativa: elimina grises intermedios para máximo contraste

DEPENDENCIAS: Solo PaddleOCR, PIL, numpy (cv2 opcional — mejora calidad).
Motor_Paddle_OCR.py provee la caché compartida de modelos (lazy import).
"""

from __future__ import annotations
print("[CropPaddle] v2 cargado OK")

import math
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Set, Callable, Tuple

from PIL import Image as PILImage

# ─── RUTAS ────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
_ROOT = _HERE.parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ─── CONSTANTES ───────────────────────────────────────────────────────────────
CROP_PADDING     = 17   # px de margen al recortar cada burbuja
ROW_TOLERANCE    = 35   # px tolerancia para agrupar cajas en la misma fila
MIN_BOX_AREA     = 200  # área mínima de una caja válida
MIN_BOX_WIDTH    = 15
MIN_BOX_HEIGHT   = 10
BUBBLE_MERGE_GAP = 35   # px distancia máxima para fusionar cajas (manhwa/webtoon)
BUBBLE_MERGE_GAP_X = 30
BUBBLE_MERGE_GAP_Y = 12


# ─── CACHÉ COMPARTIDA DE PADDLEOCR ────────────────────────────────────────────

def _get_ocr(lang: str):
    """
    Obtiene instancia PaddleOCR. Usa la caché de Motor_Paddle_OCR cuando
    está disponible (evita cargar dos modelos en RAM). Cae a caché local si no.
    """
    try:
        from ocr.Motor_Paddle_OCR import _get_paddle
        return _get_paddle(lang)
    except ImportError:
        pass

    _cache = _get_ocr.__dict__.setdefault("_local_cache", {})
    if lang not in _cache:
        try:
            from paddleocr import PaddleOCR
            os.environ.setdefault("FLAGS_use_mkldnn", "0")
            os.environ.setdefault("PADDLE_DISABLE_ONEDNN", "1")
            try:
                _cache[lang] = PaddleOCR(
                    use_angle_cls=True, lang=lang,
                    use_gpu=False, show_log=False,
                    enable_mkldnn=False,
                )
            except (TypeError, AttributeError):
                _cache[lang] = PaddleOCR(lang=lang, use_gpu=False, show_log=False)
        except ImportError:
            _cache[lang] = None
        except Exception as e:
            print(f"[CropPaddle] Error PaddleOCR (lang={lang}): {e}")
            _cache[lang] = None
    return _cache.get(lang)


# ─── PARSER UNIVERSAL ─────────────────────────────────────────────────────────

def _parse_result(result) -> List[List]:
    """Parser universal PaddleOCR v2 y v3."""
    boxes: List[List] = []
    if not result:
        return boxes

    if hasattr(result[0], "boxes"):
        for item in result:
            for box in (item.boxes or []):
                boxes.append([[list(p) for p in box]])
        return boxes

    raw = result[0] if result else []
    if not raw:
        return boxes

    for item in raw:
        if item is None:
            continue
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            first = item[0]
            if isinstance(first, (list, tuple)) and len(first) == 4:
                inner = first[0]
                if isinstance(inner, (list, tuple)) and len(inner) == 2:
                    boxes.append([first])
                else:
                    boxes.append([item])
            elif isinstance(first, (list, tuple)) and isinstance(first[0], (list, tuple)):
                boxes.append([first])
            else:
                boxes.append([item])
    return boxes


# ─── UTILIDADES DE CAJA ───────────────────────────────────────────────────────

def _box_coords(box: List) -> Tuple:
    """(x1, y1, x2, y2, cx, cy, w, h) de una caja PaddleOCR."""
    pts = box[0]
    xs  = [p[0] for p in pts]
    ys  = [p[1] for p in pts]
    x1, y1 = min(xs), min(ys)
    x2, y2 = max(xs), max(ys)
    return x1, y1, x2, y2, (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1


def _is_valid_box(box: List) -> bool:
    x1, y1, x2, y2, *_, w, h = _box_coords(box)
    return w >= MIN_BOX_WIDTH and h >= MIN_BOX_HEIGHT and w * h >= MIN_BOX_AREA


def _make_rect_box(x1: float, y1: float, x2: float, y2: float) -> List:
    return [[[float(x1), float(y1)], [float(x2), float(y1)],
             [float(x2), float(y2)], [float(x1), float(y2)]]]


# ─── FUSIÓN DE CAJAS → BURBUJAS ───────────────────────────────────────────────

def _calc_text_metrics(boxes: List[List]):
    """
    Calcula altura mediana y ancho mediano de las cajas de texto detectadas.
    Se usa como referencia dinámica para los umbrales de fusión:
      - line_h  : altura típica de una línea de texto (px)
      - char_w  : ancho típico de una caja de texto (px)

    Lógica:
      · Interlineado DENTRO de una burbuja ≈ 0–0.5 × line_h
      · Espacio ENTRE burbujas distintas   ≈ 1.0–3.0 × line_h
      → gap_y_max = line_h * 0.6   (fusiona líneas internas, rechaza burbujas externas)
      → gap_x_max = line_h * 1.5   (fusiona palabras/fragmentos de la misma línea)
    """
    if not boxes:
        return 16.0, 60.0
    heights = []
    widths  = []
    for box in boxes:
        x1, y1, x2, y2, *_ = _box_coords(box)
        h = y2 - y1
        w = x2 - x1
        if h > 4 and w > 4:
            heights.append(h)
            widths.append(w)
    if not heights:
        return 16.0, 60.0
    heights.sort()
    widths.sort()
    return heights[len(heights) // 2], widths[len(widths) // 2]


def merge_boxes_bubbles(
    boxes:       List[List],
    merge_gap:   int   = BUBBLE_MERGE_GAP,
    merge_gap_x: int   = BUBBLE_MERGE_GAP_X,
    merge_gap_y: int   = BUBBLE_MERGE_GAP_Y,
    max_center_dist: float = 0.0,
) -> List[List]:
    """
    Fusiona cajas de texto cercanas en grupos (burbujas/globos de diálogo).
    Usa Union-Find con umbrales DINÁMICOS basados en la altura mediana del texto.

    Lógica dinámica (no gaps fijos):
      · line_h  = altura mediana de todas las cajas detectadas en la imagen.
      · gap_y_max = line_h * 0.60  → solo fusiona líneas con interlineado normal.
        Si el espacio vertical supera 60% de la altura del texto, son burbujas distintas.
      · gap_x_max = line_h * 1.80  → fusiona fragmentos de la misma línea/palabra.
      · Además se exige solapamiento horizontal ≥ 15% para fusiones verticales,
        lo que impide que columnas side-by-side se unan aunque estén cerca en Y.

    Ventaja vs gaps fijos:
      · En imágenes con texto grande (títulos, SFX) los umbrales crecen proporcionalmente.
      · En imágenes con texto pequeño los umbrales se reducen, evitando fusiones falsas.
      · No hay "número mágico" que ajustar manualmente por tipo de manga/manhwa.
    """
    n = len(boxes)
    if n <= 1:
        return boxes[:]

    # ── Calcular métricas de texto para umbrales dinámicos ───────────────────
    line_h, _ = _calc_text_metrics(boxes)

    # gap_y: distancia vertical máxima para fusionar → interlineado interno.
    # 0.60 × line_h: si el texto mide 20px, solo fusiona líneas a ≤12px entre sí.
    # Si mide 40px (texto grande), acepta hasta 24px de separación interna.
    dyn_gap_y = line_h * 0.60

    # gap_x: distancia horizontal máxima para fusionar → palabras partidas o
    # fragmentos de la misma caja dentro de una burbuja.
    # 1.80 × line_h da margen para espacios entre palabras sin unir columnas.
    dyn_gap_x = line_h * 1.00  # reducido: 1.80 unía burbujas side-by-side

    aabbs = []
    for box in boxes:
        x1, y1, x2, y2, *_ = _box_coords(box)
        aabbs.append((x1, y1, x2, y2))

    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        pi, pj = find(i), find(j)
        if pi != pj:
            parent[pi] = pj

    for i in range(n):
        x1i, y1i, x2i, y2i = aabbs[i]
        for j in range(i + 1, n):
            x1j, y1j, x2j, y2j = aabbs[j]
            if max_center_dist > 0.0:
                cxi = (x1i + x2i) * 0.5; cyi = (y1i + y2i) * 0.5
                cxj = (x1j + x2j) * 0.5; cyj = (y1j + y2j) * 0.5
                if math.sqrt((cxi - cxj) ** 2 + (cyi - cyj) ** 2) > max_center_dist:
                    continue

            gap_x = max(0.0, max(x1i, x1j) - min(x2i, x2j))
            gap_y = max(0.0, max(y1i, y1j) - min(y2i, y2j))

            # Solapamiento horizontal relativo al ancho de la caja más pequeña.
            # Necesario para fusiones verticales: dos cajas en columnas distintas
            # pueden estar a gap_y=5px pero sin solapamiento X → burbujas distintas.
            w_i = max(1.0, x2i - x1i)
            w_j = max(1.0, x2j - x1j)
            x_overlap = max(0.0, min(x2i, x2j) - max(x1i, x1j))
            x_overlap_ratio = x_overlap / min(w_i, w_j)

            # Regla de fusión:
            # A) Mismo eje Y (gap_y muy pequeño, ≤10% line_h): pueden estar
            #    en columnas distintas pero son la misma línea → fusionar
            #    si también el gap_x es razonable.
            # B) Distintas líneas (gap_y > 10% line_h): exigir solapamiento X
            #    para garantizar que pertenecen a la misma columna/burbuja.
            if gap_x <= dyn_gap_x and gap_y <= dyn_gap_y:
                if gap_y <= line_h * 0.10 or x_overlap_ratio >= 0.15:
                    union(i, j)

    groups: dict = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    merged = []
    for indices in groups.values():
        gx1 = min(aabbs[i][0] for i in indices)
        gy1 = min(aabbs[i][1] for i in indices)
        gx2 = max(aabbs[i][2] for i in indices)
        gy2 = max(aabbs[i][3] for i in indices)
        merged.append(_make_rect_box(gx1, gy1, gx2, gy2))
    return merged


# ─── ORDENAMIENTO POR FLUJO DE LECTURA ────────────────────────────────────────

def sort_boxes_reading_order(
    boxes: List,
    reading_order: str = "ltr",
    row_tolerance: int = ROW_TOLERANCE,
) -> List:
    """
    Ordena burbujas por orden de lectura.

    - LTR (manhwa/webtoon): izquierda→derecha, fila por fila de arriba a abajo.
    - RTL (manga japonés horizontal): derecha→izquierda, fila por fila.
    - vertical: se maneja en sort_boxes_vertical_order.

    Tolerancia de fila dinámica: usa la altura mediana de las burbujas * 0.30.
    Esto evita que dos burbujas grandes side-by-side (h > 100px) se agrupen en
    la misma fila por tener centros Y cercanos, lo que causaba que el texto se
    emitiera intercalado (linea de burbuja A, linea de burbuja B...) en lugar
    de burbuja completa A y luego burbuja completa B.
    """
    if not boxes:
        return boxes

    def _cy(box):
        _, y1, _, y2, *_ = _box_coords(box)
        return (y1 + y2) / 2.0

    def _h(box):
        _, y1, _, y2, *_ = _box_coords(box)
        return max(1.0, y2 - y1)

    # Tolerancia dinamica: 30% de la altura mediana.
    # Burbujas pequeñas (h~30px) → ~9px estricto (misma linea).
    # Burbujas medianas (h~80px) → ~24px (agrupa lineas del mismo panel).
    # Burbujas grandes (h~200px) → ~60px (NO agrupa viñetas side-by-side).
    # Siempre al menos row_tolerance para no romper casos normales.
    heights = sorted(_h(b) for b in boxes)
    median_h = heights[len(heights) // 2]
    # 0.40 (antes 0.30): más generoso para no perder burbujas laterales pequeñas
    # que tienen cy ligeramente distinto al de la fila donde deberían caer.
    # row_tolerance sigue siendo el piso mínimo (default 35px).
    dyn_tol = max(row_tolerance, median_h * 0.40)

    rows: List[List] = []
    cur:  List       = []
    ref_cy = -9999.0

    for box in sorted(boxes, key=_cy):
        cy = _cy(box)
        if not cur:
            cur.append(box); ref_cy = cy
        elif abs(cy - ref_cy) <= dyn_tol:
            cur.append(box)
            ref_cy = sum(_cy(b) for b in cur) / len(cur)
        else:
            rows.append(cur)
            cur = [box]; ref_cy = cy
    if cur:
        rows.append(cur)

    ordered = []
    for row in rows:
        row.sort(key=lambda b: _box_coords(b)[0], reverse=(reading_order == "rtl"))
        ordered.extend(row)
    return ordered


def sort_boxes_vertical_order(boxes: List) -> List:
    """
    Ordena burbujas para texto vertical japonés:
    columnas de derecha a izquierda, dentro de cada columna de arriba a abajo.
    """
    if not boxes:
        return boxes

    def _cx(box):
        x1, _, x2, *_ = _box_coords(box)
        return (x1 + x2) / 2.0

    def _cy(box):
        _, y1, _, y2, *_ = _box_coords(box)
        return (y1 + y2) / 2.0

    # Ancho típico de burbuja: tolerancia de columna
    if boxes:
        widths = [_box_coords(b)[6] for b in boxes]
        col_tol = max(20, sorted(widths)[len(widths) // 2] * 0.7)
    else:
        col_tol = 40

    columns: List[List] = []
    for box in sorted(boxes, key=_cx):
        placed = False
        for col in columns:
            ref_cx = sum(_cx(b) for b in col) / len(col)
            if abs(_cx(box) - ref_cx) <= col_tol:
                col.append(box); placed = True; break
        if not placed:
            columns.append([box])

    # Columnas de derecha a izquierda
    columns.sort(key=lambda c: -sum(_cx(b) for b in c) / len(c))
    ordered = []
    for col in columns:
        col.sort(key=_cy)  # top to bottom within column
        ordered.extend(col)
    return ordered


# ─── RECORTE DE BURBUJA ───────────────────────────────────────────────────────

def crop_box_from_image(
    image: PILImage.Image,
    box: List,
    padding: int = CROP_PADDING,
) -> Optional[PILImage.Image]:
    """Recorta una región (burbuja) de la imagen con padding."""
    pts = box[0]
    xs  = [p[0] for p in pts]
    ys  = [p[1] for p in pts]
    w, h = image.size
    x1 = max(0, int(min(xs)) - padding)
    y1 = max(0, int(min(ys)) - padding)
    x2 = min(w, int(max(xs)) + padding)
    y2 = min(h, int(max(ys)) + padding)
    if x2 <= x1 or y2 <= y1 or (x2 - x1) * (y2 - y1) < MIN_BOX_AREA:
        return None
    return image.crop((x1, y1, x2, y2))


# ─── PREPROCESADO DE RECORTE ─────────────────────────────────────────────────

# Rango óptimo de resolución para PaddleOCR en recortes de burbuja
_CROP_MIN_H  = 40    # px de alto mínimo para texto legible
_CROP_MAX_H  = 900   # px de alto máximo antes de downscale (subido de 600)
_CROP_TGT_H  = 120   # alto objetivo al que escalar recortes pequeños


def _detect_bg_type(gray_arr) -> str:
    """
    Detecta el tipo de fondo del recorte analizando los bordes:

    - 'white'   : claro y uniforme  → burbuja de diálogo clásica
    - 'dark'    : oscuro o texto claro sobre fondo coloreado
                  (cyan/blanco sobre negro o verde, SFX con fondo)
    - 'complex' : gradiente/textura → panel con fondo dibujado
    """
    try:
        import numpy as np
        h, w = gray_arr.shape[:2]
        m = max(6, min(20, int(min(h, w) * 0.10)))
        border = np.concatenate([
            gray_arr[:m,  :].ravel(), gray_arr[-m:, :].ravel(),
            gray_arr[:,  :m].ravel(), gray_arr[:, -m:].ravel()
        ])
        mean_b = float(border.mean())
        std_b  = float(border.std())

        # Analizar interior para detectar texto claro sobre fondo coloreado.
        # En pizarrones (texto blanco sobre verde), el interior tiene píxeles
        # muy claros (texto) + píxeles medios (fondo verde → ~100-150 en gris).
        # La varianza interior es alta pero mean no es <85 → antes era "complex".
        interior = gray_arr[m:h-m, m:w-m] if h > 2*m and w > 2*m else gray_arr
        # Porcentaje de píxeles muy claros (>200) en el interior
        pct_bright = float((interior > 200).sum()) / max(interior.size, 1)

        if mean_b > 200 and std_b < 30:
            return "white"
        elif mean_b < 85:
            return "dark"
        elif pct_bright > 0.12 and mean_b < 160:
            # Fondo coloreado medio (verde, azul, etc.) con texto claro:
            # tratar como "dark" para aplicar inversión de bits
            return "dark"
        else:
            return "complex"
    except Exception:
        return "white"


def _scale_crop(img, target_h: int):
    """Escala la imagen manteniendo proporción para alcanzar target_h."""
    try:
        import cv2
        h, w = img.shape[:2]
        scale = target_h / h
        new_w = max(1, int(w * scale))
        new_h = target_h
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    except Exception:
        return img


def _preprocess_crop(crop_path: str, lang: str = "en") -> str:
    """
    Preprocesa un recorte de burbuja para maximizar precisión de PaddleOCR.

    Flujo automático:
      1. Ajuste de resolución: upscale si < _CROP_MIN_H, downscale si > _CROP_MAX_H
      2. Detección de tipo de fondo:
           - 'white'   → denoise + binarización gaussiana
           - 'dark'    → INVERSIÓN DE BITS → escala de grises invertida
                         (texto blanco/cyan → negro puro sobre blanco puro)
           - 'complex' → filtro bilateral + binarización adaptativa fuerte
      3. Siempre garantiza texto NEGRO sobre fondo BLANCO (PaddleOCR óptimo)

    Retorna ruta a PNG temporal. El caller es responsable de borrarlo.
    """
    try:
        import cv2
        import numpy as np

        img = cv2.imread(str(crop_path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("imread=None")

        h, w = img.shape[:2]

        # ── 1. Ajuste de resolución ──────────────────────────────────────────
        if h < _CROP_MIN_H:
            img = _scale_crop(img, _CROP_TGT_H)
            h, w = img.shape[:2]
        elif h > _CROP_MAX_H:
            img = _scale_crop(img, _CROP_MAX_H)
            h, w = img.shape[:2]

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Detectar bg con versión original (sin escalar) para más precisión
        gray_orig_img = cv2.imread(str(crop_path), cv2.IMREAD_GRAYSCALE)
        bg = _detect_bg_type(gray_orig_img if gray_orig_img is not None else gray)

        # ── 2. Pipeline según tipo de fondo ──────────────────────────────────
        if bg == "dark":
            # Texto claro sobre fondo oscuro/coloreado → INVERSIÓN DE BITS
            # Aplica CLAHE primero para normalizar iluminación desigual
            # (texto en esquina brillante vs esquina oscura del pizarrón)
            try:
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                gray_eq = clahe.apply(gray)
            except Exception:
                gray_eq = gray
            inverted  = cv2.bitwise_not(gray_eq)
            denoised  = cv2.fastNlMeansDenoising(inverted, h=12)
            binarized = cv2.adaptiveThreshold(
                denoised, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 3
            )
            # Verificar que texto quedó negro (mayoría de píxeles blancos = fondo)
            if cv2.countNonZero(binarized) < binarized.size * 0.5:
                pass  # correcto: texto negro sobre blanco
            else:
                binarized = cv2.bitwise_not(binarized)
            # Sharpen final
            kernel = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]], dtype=np.float32)
            final  = cv2.cvtColor(cv2.filter2D(binarized, -1, kernel), cv2.COLOR_GRAY2BGR)

        elif bg == "white":
            # Burbuja clásica blanca → denoise + binarización suave
            denoised  = cv2.fastNlMeansDenoising(gray, h=10)
            binarized = cv2.adaptiveThreshold(
                denoised, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            if cv2.countNonZero(binarized) < binarized.size * 0.5:
                binarized = cv2.bitwise_not(binarized)
            kernel = np.array([[-1,-1,-1],[-1,9,-1],[-1,-1,-1]], dtype=np.float32)
            final  = cv2.cvtColor(cv2.filter2D(binarized, -1, kernel), cv2.COLOR_GRAY2BGR)

        else:  # complex
            # Panel con fondo dibujado → bilateral fuerte + binarización adaptativa
            filtered  = cv2.bilateralFilter(gray, 9, 75, 75)
            c_val     = 8 if lang in ("ch", "chinese_cht", "japan", "korean") else 11
            binarized = cv2.adaptiveThreshold(
                filtered, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, c_val
            )
            if cv2.countNonZero(binarized) < binarized.size * 0.5:
                binarized = cv2.bitwise_not(binarized)
            final = cv2.cvtColor(binarized, cv2.COLOR_GRAY2BGR)

        fd, out = tempfile.mkstemp(suffix=".png", prefix="cp_pre_")
        os.close(fd)
        cv2.imwrite(out, final, [cv2.IMWRITE_PNG_COMPRESSION, 0])
        return out

    except ImportError:
        pass
    except Exception:
        pass

    # ── Fallback PIL (sin cv2) ────────────────────────────────────────────────
    try:
        from PIL import ImageFilter
        import numpy as np

        with PILImage.open(str(crop_path)) as img:
            w, h = img.size
            # Ajuste de resolución
            if h < _CROP_MIN_H:
                scale = max(2, _CROP_TGT_H // max(h, 1))
                img_rgb = img.convert("RGB").resize((w * scale, h * scale), PILImage.LANCZOS)
            else:
                img_rgb = img.convert("RGB")

        gray_pil = img_rgb.convert("L")
        arr      = np.array(gray_pil)
        mean_bg  = float(arr[:max(6, arr.shape[0]//10), :].mean())

        if mean_bg < 85:  # fondo oscuro → invertir
            gray_pil = gray_pil.point(lambda p: 255 - p)

        sharpened = gray_pil.filter(ImageFilter.UnsharpMask(radius=1.5, percent=160, threshold=2))
        hist = sharpened.histogram()
        cum  = 0; thr = 128
        for i, v in enumerate(hist):
            cum += v
            if cum >= sum(hist) * 0.5:
                thr = i; break
        binarized = sharpened.point(lambda p: 255 if p > max(80, min(thr, 200)) else 0)
        arr2 = np.array(binarized)
        if np.count_nonzero(arr2) < arr2.size * 0.5:
            binarized = binarized.point(lambda p: 255 - p)

        fd, out = tempfile.mkstemp(suffix=".png", prefix="cp_pre_")
        os.close(fd)
        binarized.convert("RGB").save(out, "PNG")
        return out

    except Exception:
        return str(crop_path)


# ─── OCR DE UNA BURBUJA ───────────────────────────────────────────────────────

def _ocr_bubble(
    crop_path: "str | Path",
    lang:      str  = "en",
    reading_order: str = "ltr",
    vertical:  bool = False,
) -> str:
    """
    OCR de una sola burbuja recortada.
    reading_order: 'ltr' (manhwa) | 'rtl' (manga horizontal)
    vertical: True → texto vertical japonés (columnas R→L, T→B dentro de cada col)
    """
    ocr = _get_ocr(lang)
    if ocr is None:
        return ""

    preprocessed = _preprocess_crop(str(crop_path), lang=lang)
    cleanup = (preprocessed != str(crop_path))

    result  = None
    result2 = None
    try:
        # Pasada 1: sin corrección de ángulo (rápida, base principal)
        try:
            result = ocr.ocr(preprocessed, cls=False)
        except Exception:
            result = None
        # Pasada 2: con corrección de ángulo (recupera texto omitido/rotado)
        try:
            result2 = ocr.ocr(preprocessed, cls=True)
        except Exception:
            result2 = None
    finally:
        if cleanup:
            try: os.unlink(preprocessed)
            except Exception: pass

    # Combinar ambas pasadas
    if not result and not result2:
        return ""
    if not result:
        result = result2
    elif result2:
        try:
            from ocr.Motor_Paddle_OCR import _merge_ocr_passes, _extraer_bloques
            b1 = _extraer_bloques(result)
            b2 = _extraer_bloques(result2)
            merged_bloques = _merge_ocr_passes(b1, b2, iou_thr=0.35, conf_thr=0.70)
            result = [[([pts, (txt, conf)]) for pts, txt, conf in merged_bloques]]
        except Exception:
            pass

    items = []
    for page in (result if isinstance(result, list) else [result]):
        if page is None:
            continue
        for entry in (page if isinstance(page, list) else []):
            if entry is None:
                continue
            try:
                if (isinstance(entry, (list, tuple)) and len(entry) >= 2
                        and isinstance(entry[0], (list, tuple))
                        and isinstance(entry[0][0], (list, tuple))):
                    pts  = entry[0]
                    info = entry[1]
                    texto = str(info[0]).strip() if isinstance(info, (list, tuple)) else str(info).strip()
                    if not texto:
                        continue
                    ys = [float(p[1]) for p in pts]
                    xs = [float(p[0]) for p in pts]
                    items.append({
                        "texto": texto,
                        "cy": (min(ys) + max(ys)) / 2,
                        "cx": (min(xs) + max(xs)) / 2,
                        "top": min(ys),
                        "left":  min(xs),
                        "right": max(xs),
                    })
            except Exception:
                continue

    if not items:
        return ""

    if vertical:
        # Texto vertical: agrupar por columnas (eje X), leer R→L, T→B dentro de col
        alt_media = sum(abs(it["cy"] - it["top"]) * 2 for it in items) / max(1, len(items))
        col_tol   = max(10, min(50, alt_media * 1.0))
        columns: List[List] = []
        for it in sorted(items, key=lambda x: x["cx"]):
            placed = False
            for col in columns:
                ref_cx = sum(x["cx"] for x in col) / len(col)
                if abs(it["cx"] - ref_cx) <= col_tol:
                    col.append(it); placed = True; break
            if not placed:
                columns.append([it])
        columns.sort(key=lambda c: -sum(x["cx"] for x in c) / len(c))
        lineas = []
        for col in columns:
            col.sort(key=lambda x: x["cy"])
            lineas.append(" ".join(x["texto"] for x in col))
        return "\n".join(lineas)

    # Texto horizontal: agrupar en bandas
    items.sort(key=lambda it: it["cy"])
    alt_media = sum(abs(it["cy"] - it["top"]) * 2 for it in items) / max(1, len(items))
    line_tol  = max(12, min(60, alt_media * 0.7))
    bandas: List[List] = []
    for it in items:
        placed = False
        for banda in bandas:
            ref_cy = sum(x["cy"] for x in banda) / len(banda)
            if abs(it["cy"] - ref_cy) <= line_tol:
                banda.append(it); placed = True; break
        if not placed:
            bandas.append([it])
    bandas.sort(key=lambda b: sum(x["cy"] for x in b) / len(b))

    # ── Separar viñetas side-by-side dentro de cada banda ────────────────────
    # Si el gap horizontal entre ítems es grande → viñetas distintas en la misma fila.
    # Cada columna lateral se emite como línea separada para no mezclar diálogos.
    def _col_groups_bubble(banda: List) -> List[List]:
        avg_w = sum(it["right"] - it["left"] for it in banda) / max(len(banda), 1)
        gap_thr = max(avg_w * 0.3, alt_media * 0.6)
        by_x = sorted(banda, key=lambda it: it["cx"])
        grupos: List[List] = [[by_x[0]]]
        for k in range(1, len(by_x)):
            gap_x = by_x[k]["left"] - by_x[k-1]["right"]
            if gap_x >= gap_thr:
                grupos.append([by_x[k]])
            else:
                grupos[-1].append(by_x[k])
        return grupos

    rtl_b = (reading_order == "rtl")
    lineas = []
    for banda in bandas:
        col_groups = _col_groups_bubble(banda)
        if len(col_groups) > 1:
            ordered = list(reversed(col_groups)) if rtl_b else col_groups
            for col in ordered:
                col_s = sorted(col, key=lambda it: it["cx"], reverse=rtl_b)
                lineas.append(" ".join(it["texto"] for it in col_s))
        else:
            banda.sort(key=lambda it: it["cx"], reverse=rtl_b)
            lineas.append(" ".join(it["texto"] for it in banda))
    return "\n".join(lineas)


# ─── POST-PROCESO MÍNIMO DE BURBUJA ──────────────────────────────────────────

def _collapse_bubble(text: str) -> str:
    """Junta líneas de una burbuja en una sola línea (un párrafo)."""
    return " ".join(l.strip() for l in text.splitlines() if l.strip())


def _deduplicate(text: str) -> str:
    """Elimina texto duplicado que PaddleOCR genera en paneles anchos."""
    if not text or len(text) < 6:
        return text
    import re
    tokens = re.findall(r"\S+", text)
    n = len(tokens)
    if n < 4:
        return text
    best_len = 0; best_end = n
    for seq_len in range(n // 2, 2, -1):
        seq = [t.lower() for t in tokens[:seq_len]]
        for start in range(seq_len, n - seq_len + 1):
            candidate = [t.lower() for t in tokens[start:start + seq_len]]
            if sum(a == b for a, b in zip(seq, candidate)) / seq_len >= 0.80:
                if seq_len > best_len:
                    best_len = seq_len; best_end = start
                break
    if best_len >= 4 and best_len >= n * 0.35:
        return " ".join(tokens[:best_end]).strip()
    mid = len(text) // 2
    fh  = text[:mid].strip().lower()
    sh  = text[mid:].strip().lower()
    if fh and sh and 0.70 <= len(sh) / max(len(fh), 1) <= 1.43:
        common = sum(min(fh.count(c), sh.count(c)) for c in set(fh))
        if common / max(len(fh), len(sh), 1) >= 0.78:
            return text[:mid].strip()
    return text


# ─── FUSIÓN POR COLUMNAS (previene mezcla de burbujas side-by-side) ─────────────

def _merge_by_columns(boxes: List[List], img_w: int) -> List[List]:
    """
    Fusiona cajas de texto en dos fases para evitar mezclar burbujas side-by-side.

    Problema que resuelve:
        PaddleOCR detecta líneas individuales. Dos burbujas lado a lado generan
        cajas intercaladas en Y:
            Y=420 "WELL,"          ← burbuja izquierda
            Y=445 "IT'S THE DARK," ← burbuja derecha
            Y=460 "THAT'S"         ← burbuja izquierda
        Si se fusiona todo junto, el gap_x grande las separa pero el sort posterior
        las mezcla. La solución es fusionar por columnas X primero.

    Fase 1 — Separar en columnas X:
        Divide el ancho de la imagen en columnas según la distribución de centros X
        de las cajas. Usa clustering 1D (sort + gap) con umbral = 15% del ancho.
        Cajas en la misma franja X pertenecen a la misma burbuja/columna.

    Fase 2 — Fusionar dentro de cada columna:
        Dentro de cada columna, aplica merge_boxes_bubbles normal.
        Las líneas internas de cada burbuja se fusionan en un solo bbox.

    Resultado: una caja por burbuja, sin mezcla entre columnas.
    """
    if not boxes:
        return []

    # ── Fase 1: clustering 1D por centro X ───────────────────────────────────
    # Calcular centro X de cada caja
    cx_list = []
    for box in boxes:
        x1, y1, x2, y2, *_ = _box_coords(box)
        cx_list.append((x1 + x2) / 2.0)

    # Ordenar por centro X
    order = sorted(range(len(boxes)), key=lambda i: cx_list[i])
    sorted_cx = [cx_list[i] for i in order]
    sorted_boxes = [boxes[i] for i in order]

    # Gap mínimo para considerar columnas distintas: 12% del ancho de imagen.
    # Dos burbujas side-by-side en un manhwa estándar están separadas al menos
    # un 15-20% del ancho total. Usamos 12% para tener margen.
    col_gap_thr = img_w * 0.12

    # También usar métricas de texto: si los textos son grandes, el umbral sube
    line_h, _ = _calc_text_metrics(boxes)
    col_gap_thr = max(col_gap_thr, line_h * 2.5)

    columns: List[List[List]] = []  # lista de columnas, cada una es lista de boxes
    cur_col: List[List] = [sorted_boxes[0]]
    cur_max_x = _box_coords(sorted_boxes[0])[2]  # x2 de la caja actual

    for k in range(1, len(sorted_boxes)):
        box = sorted_boxes[k]
        x1, y1, x2, y2, *_ = _box_coords(box)
        cx = (x1 + x2) / 2.0

        # Gap desde el borde derecho del grupo actual al centro de la nueva caja
        gap = cx - cur_max_x
        if gap > col_gap_thr:
            columns.append(cur_col)
            cur_col = [box]
            cur_max_x = x2
        else:
            cur_col.append(box)
            cur_max_x = max(cur_max_x, x2)

    if cur_col:
        columns.append(cur_col)

    # ── Fase 2: merge dentro de cada columna ─────────────────────────────────
    all_bubbles: List[List] = []
    for col_boxes in columns:
        merged = merge_boxes_bubbles(col_boxes)
        all_bubbles.extend(merged)

    return all_bubbles


# ─── PIPELINE PRINCIPAL ───────────────────────────────────────────────────────

def extract_text_with_crop_pipeline(
    image_path:    "str | Path",
    lang:          str  = "en",
    reading_order: str  = "ltr",
    vocab:         Optional[Set[str]] = None,
    use_gpu:       bool = False,
    merge_gap:     int  = BUBBLE_MERGE_GAP,
    vertical:      bool = False,
    log_cb:        Optional[Callable] = None,
) -> str:
    """
    Pipeline completo para una imagen:
      1. Detecta cajas de texto con PaddleOCR
      2. Fusiona cajas → burbujas
      3. Ordena por flujo de lectura (LTR / RTL / vertical japonés)
      4. Recorta, preprocesa y hace OCR de cada burbuja
      5. Retorna una línea por burbuja

    vertical=True activa lectura en columnas para texto japonés vertical.
    """
    def _log(m):
        print(m)
        if log_cb: log_cb(m)

    image_path = Path(image_path)
    ocr = _get_ocr(lang)
    if ocr is None:
        _log("[CropPaddle] PaddleOCR no disponible")
        return ""

    try:
        full_image = PILImage.open(image_path).convert("RGB")
    except Exception as e:
        _log(f"[CropPaddle] Error abriendo {image_path.name}: {e}")
        return ""

    # ── Paso 1: Detección ────────────────────────────────────────────────────
    try:
        result = ocr.ocr(str(image_path), cls=False)
    except Exception as e:
        _log(f"[CropPaddle] Error detección: {e}")
        full_image.close()
        return ""

    raw_boxes   = _parse_result(result)
    valid_boxes = [b for b in raw_boxes if _is_valid_box(b)]
    _log(f"[CropPaddle] {image_path.name}: {len(raw_boxes)} cajas → {len(valid_boxes)} válidas")

    if not valid_boxes:
        _log("[CropPaddle] Sin cajas válidas")
        full_image.close()
        return ""

    # ── Paso 2: Agrupar por columna X primero, luego fusionar → burbujas ────
    # PaddleOCR detecta líneas individuales. Si hay dos burbujas lado a lado,
    # sus líneas se intercalan en Y (burbuja_izq_Y=420, burbuja_der_Y=445...).
    # Si fusionamos todo junto, las columnas se mezclan aunque el gap_x sea grande.
    # Solución: separar primero en columnas X, fusionar dentro de cada columna,
    # luego unir todos los grupos resultantes.
    img_w, img_h = full_image.size
    bubble_boxes = _merge_by_columns(valid_boxes, img_w)
    _log(f"[CropPaddle] Fusión: {len(valid_boxes)} cajas → {len(bubble_boxes)} burbujas")

    # ── Paso 3: Ordenar por flujo de lectura ─────────────────────────────────
    if vertical:
        ordered = sort_boxes_vertical_order(bubble_boxes)
        _log(f"[CropPaddle] Orden: Vertical japonés (R→L, T→B) | {len(ordered)} burbujas")
    else:
        ordered = sort_boxes_reading_order(bubble_boxes, reading_order=reading_order)
        _log(f"[CropPaddle] Orden: {'RTL' if reading_order == 'rtl' else 'LTR'} | {len(ordered)} burbujas")

    # ── Paso 4: OCR por burbuja ──────────────────────────────────────────────
    bubble_lines: List[str] = []
    temp_files:   List[str] = []

    for idx, box in enumerate(ordered):
        crop = crop_box_from_image(full_image, box, padding=CROP_PADDING)
        if crop is None:
            continue
        try:
            fd, crop_path = tempfile.mkstemp(suffix=".png", prefix="cp_bbl_")
            os.close(fd)
            crop.save(crop_path, "PNG")
            temp_files.append(crop_path)
        except Exception as e:
            _log(f"[CropPaddle]   [{idx+1}] Error guardando recorte: {e}")
            crop.close(); continue
        finally:
            crop.close()

        try:
            raw  = _ocr_bubble(crop_path, lang=lang, reading_order=reading_order, vertical=vertical)
            raw  = _deduplicate(raw)
            line = _collapse_bubble(raw)
            if line:
                bubble_lines.append(line)
                _log(f"[CropPaddle]   [{idx+1}/{len(ordered)}] ✓ '{line[:70]}'")
        except Exception as e:
            _log(f"[CropPaddle]   [{idx+1}/{len(ordered)}] ✗ {e}")

    full_image.close()
    for tf in temp_files:
        try: os.unlink(tf)
        except Exception: pass

    if not bubble_lines:
        _log("[CropPaddle] Sin resultados de burbujas")
        return ""

    return "\n".join(bubble_lines)


# ─── COMPATIBILIDAD CON AUTOSCRIBE ────────────────────────────────────────────
# OCRWorkerCropPaddle se mantiene aquí para que AutoScribe_v1_0.py
# pueda importarlo sin cambios. Internamente delega todo a Motor_Paddle_OCR.

from PyQt6.QtCore import QThread, pyqtSignal

class OCRWorkerCropPaddle(QThread):
    """
    Alias de compatibilidad — delega en Motor_Paddle_OCR.OCRWorker.
    Drop-in para AutoScribe_v1_0.py.
    """
    progress        = pyqtSignal(int)
    status_msg      = pyqtSignal(str)
    log_msg         = pyqtSignal(str)
    finished_ok     = pyqtSignal(str)
    error           = pyqtSignal(str)
    new_words_found = pyqtSignal(set)
    stats_update    = pyqtSignal(dict)

    def __init__(self, image_paths, output_folder, fmt="txt", translate_to="",
                 case_mode="original", folder_name="output", ocr_lang="en",
                 use_gpu=False, online_learning=False, keep_sfx=True,
                 rtl=True, merge_gap=BUBBLE_MERGE_GAP, vertical_japanese=False):
        super().__init__()
        from ocr.Motor_Paddle_OCR import OCRWorker
        self._worker = OCRWorker(
            image_paths=image_paths, output_folder=output_folder,
            fmt=fmt, translate_to=translate_to, case_mode=case_mode,
            folder_name=folder_name, ocr_lang=ocr_lang, use_gpu=use_gpu,
            online_learning=online_learning, keep_sfx=keep_sfx,
            rtl=rtl, vertical_japanese=vertical_japanese,
            # crop_pipeline=False (default) — modo simple, mejor calidad que crop-burbuja
        )
        # Reenviar señales del worker interno
        self._worker.progress.connect(self.progress)
        self._worker.status_msg.connect(self.status_msg)
        self._worker.log_msg.connect(self.log_msg)
        self._worker.finished_ok.connect(self.finished_ok)
        self._worker.error.connect(self.error)
        self._worker.new_words_found.connect(self.new_words_found)
        self._worker.stats_update.connect(self.stats_update)
        self._cancel = False

    def cancel(self):
        self._cancel = True
        self._worker.cancel()

    def run(self):
        self._worker.run()


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python crop_paddle.py <imagen> [lang] [ltr|rtl] [gap] [--vertical]")
        sys.exit(0)
    img   = sys.argv[1]
    lang  = sys.argv[2] if len(sys.argv) > 2 else "en"
    order = sys.argv[3] if len(sys.argv) > 3 else "ltr"
    gap   = int(sys.argv[4]) if len(sys.argv) > 4 else BUBBLE_MERGE_GAP
    vert  = "--vertical" in sys.argv
    print(f"Imagen: {img} | Lang: {lang} | Orden: {order} | Gap: {gap}px | Vertical: {vert}")
    print("─" * 60)
    texto = extract_text_with_crop_pipeline(
        img, lang=lang, reading_order=order, merge_gap=gap,
        vertical=vert, log_cb=print)
    print("\n─── RESULTADO (una línea = una burbuja) ───")
    for i, linea in enumerate(texto.splitlines(), 1):
        print(f"  [{i:02d}] {linea}")
    print(f"\nTotal: {len([l for l in texto.splitlines() if l.strip()])} burbujas")