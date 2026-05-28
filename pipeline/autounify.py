"""
autounify.py - Unión vertical secuencial con remanente acumulativo.
Soporta imágenes de cualquier tamaño y cantidad, sin límites de memoria.

Estrategia de corte — OCR-First (PaddleOCR):
  Usa PaddleOCR para detectar bloques de texto en la franja de búsqueda
  y busca el espacio vertical más grande libre de texto por debajo de
  max_height. Si no hay un espacio limpio, evita al menos cortar una línea.

PaddleOCR v4/v5 compatibility shim:
  _get_paddle_ocr() soporta ambas versiones del constructor. Si PaddleOCR
  no está instalado, el corte cae a max_height (corte duro).
"""

import sys
import os
import tempfile
from pathlib import Path
from PIL import Image
from typing import List, Optional

# ── ProcessManager: libera RAM/CPU antes de correr PaddleOCR ─────────────
try:
    from pipeline.process_manager import ProcessSnapshot as _ProcessSnapshot, is_available as _procmgr_ok
    _PROCMGR_OK = _procmgr_ok()
except ImportError:
    _ProcessSnapshot = None   # type: ignore
    _PROCMGR_OK = False

SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}

# ─── PADDLEOCR v4/v5 COMPATIBILITY SHIM ─────────────────────────────────────

_paddle_cache: dict = {}


def _get_paddle_ocr(lang: str = "en"):
    """
    Retorna una instancia cacheada de PaddleOCR para el idioma dado.
    Compatible con PaddleOCR v4 y v5 (la v5 cambió el constructor).
    Retorna None si PaddleOCR no está instalado.

    Parámetros alineados con Motor_Paddle_OCR._get_paddle():
      · use_angle_cls=False  — clasificador de ángulo no necesario aquí
      · MKL-DNN auto-detect  — activo solo en Intel (2–3× en convoluciones)
      · cpu_threads          — todos los núcleos disponibles
      · rec_batch_num=32     — procesa más cajas en paralelo en CRNN
      · det_db_thresh=0.3    — menos falsos positivos en fondos de manga
    """
    if lang not in _paddle_cache:
        try:
            import logging
            for _lg in ("ppocr", "paddle", "ppdet", "root", "PaddleOCR"):
                logging.getLogger(_lg).setLevel(logging.ERROR)
            from paddleocr import PaddleOCR

            # Detectar Intel para MKL-DNN
            _mkldnn = False
            try:
                import cpuinfo
                _mkldnn = "intel" in cpuinfo.get_cpu_info().get("brand_raw", "").lower()
            except Exception:
                pass

            _n_threads = os.cpu_count() or 4

            print(f"[autounify] Inicializando PaddleOCR ({lang}) "
                  f"| {_n_threads} threads | MKL-DNN={'✓' if _mkldnn else '✗'}...")
            try:
                _paddle_cache[lang] = PaddleOCR(
                    use_angle_cls       = False,
                    lang                = lang,
                    show_log            = False,
                    enable_mkldnn       = _mkldnn,
                    cpu_threads         = _n_threads,
                    det_db_thresh       = 0.3,
                    det_db_box_thresh   = 0.4,
                    det_db_unclip_ratio = 2.0,
                    rec_batch_num       = 32,
                )
            except TypeError:
                # PaddleOCR v5: constructor simplificado
                _paddle_cache[lang] = PaddleOCR(lang=lang, show_log=False)
        except ImportError:
            _paddle_cache[lang] = None
    return _paddle_cache[lang]


def _ocr_blocks_from_result(result) -> list:
    """
    Normaliza el resultado de PaddleOCR v4 o v5 al formato interno:
        [(coords [[x,y],...], (text, score)), ...]
    Retorna lista vacía si el resultado está vacío o es inválido.
    """
    if not result or not result[0]:
        return []
    first = result[0]
    blocks = []
    # PaddleOCR v5: result[0] tiene atributos dt_polys, rec_texts, rec_scores
    if hasattr(first, "dt_polys"):
        for poly, text, score in zip(first.dt_polys, first.rec_texts, first.rec_scores):
            coords = [[float(p[0]), float(p[1])] for p in poly]
            blocks.append([coords, (text, score)])
    # PaddleOCR v4: result[0] es lista de [[[x,y],...], (text, score)]
    elif isinstance(first, list):
        for item in first:
            if item:
                blocks.append(item)
    return blocks


# ─── DETECCIÓN DE CORTE SEGURO (OCR-FIRST) ───────────────────────────────────

def find_safe_cut_position(canvas: Image.Image, current_height: int,
                           max_height: int, ocr_lang: str = "en") -> int:
    """
    Busca un punto de corte que no parta líneas de texto y,
    preferiblemente, que caiga entre párrafos.

    Estrategia:
      1. Recorta la franja de búsqueda (max_height ± margen).
      2. Corre PaddleOCR sobre esa franja.
      3. Busca el espacio vertical más grande libre de texto por debajo
         de max_height.
      4. Si no hay espacio limpio, al menos ajusta el corte para no
         partir una línea.
      5. Fallback: corte duro en max_height si PaddleOCR falla o no está.
    """
    if current_height <= max_height:
        return current_height

    margin_top    = 400
    margin_bottom = 150
    y_start = max(0, max_height - margin_top)
    y_end   = min(current_height, max_height + margin_bottom)

    if y_end <= y_start:
        return max_height

    crop = canvas.crop((0, y_start, canvas.width, y_end))

    try:
        ocr = _get_paddle_ocr(ocr_lang)
        if ocr is None:
            return max_height

        # Pasar el crop como numpy array — sin I/O de disco
        import numpy as np
        crop_arr = np.array(crop.convert("RGB"))
        crop.close()

        result = ocr.ocr(crop_arr)
        if not result or not result[0]:
            return max_height

        # Normalizar resultado (compatible v4 y v5)
        raw_blocks = _ocr_blocks_from_result(result)
        boxes = []
        for block in raw_blocks:
            coords = block[0]
            ys     = [pt[1] for pt in coords]
            top    = min(ys) + y_start
            bottom = max(ys) + y_start
            boxes.append((top, bottom))

        if not boxes:
            return max_height

        boxes.sort(key=lambda b: b[0])

        # Buscar el espacio vertical más grande libre de texto por encima de max_height
        best_gap = 0
        best_cut = max_height

        # Espacio desde el inicio del recorte hasta la primera caja
        gap = boxes[0][0] - y_start
        if gap > best_gap and y_start + gap <= max_height:
            best_gap = gap
            best_cut = y_start + gap // 2

        # Espacios entre cajas consecutivas
        for i in range(len(boxes) - 1):
            gap       = boxes[i + 1][0] - boxes[i][1]
            candidate = boxes[i][1] + gap // 2
            if gap > best_gap and candidate <= max_height:
                best_gap = gap
                best_cut = candidate

        # Si encontramos un espacio significativo (≥ 30 px), lo usamos
        if best_gap >= 30:
            safe_cut = int(best_cut)
            print(f"[autounify] Corte entre párrafos: {safe_cut}px (gap={best_gap}px)")
            return max(100, min(safe_cut, current_height))

        # Si no hay buen espacio, al menos evitar cortar una línea
        for top, bottom in boxes:
            if top <= max_height <= bottom:
                safe_cut = max(100, int(top) - 5)
                print(f"[autounify] Corte ajustado para no partir línea: {safe_cut}px")
                return safe_cut

        return max_height

    except Exception as e:
        print(f"[autounify] Error en detección de corte: {e}")
        return max_height


# ─── PRE-DIVISIÓN DE IMÁGENES ENORMES ────────────────────────────────────────

def _split_large_image(image_path: Path, max_height: int,
                       ocr_lang: str, safe_cut: bool) -> List[Path]:
    """
    Divide una imagen cuya altura supera max_height en fragmentos de
    altura ≤ max_height. Retorna lista de rutas (puede incluir temporales).
    La imagen se abre una sola vez y permanece en memoria durante todo el
    proceso — evita múltiples lecturas del mismo archivo en disco.
    """
    with Image.open(image_path) as _img:
        full_img = _img.convert("RGB")
        w, h = full_img.size

    if h <= max_height:
        full_img.close()
        return [image_path]

    temp_files: List[str] = []
    fragments:  List[Path] = []
    y = 0

    while y < h:
        remaining = h - y

        if safe_cut and remaining > max_height:
            crop = full_img.crop((0, y, w, min(y + max_height + 200, h)))
            safe_h = find_safe_cut_position(crop, crop.height, max_height, ocr_lang)
            # crop se cierra dentro de find_safe_cut_position tras convertir a array
            actual_h = min(safe_h, remaining)
        else:
            actual_h = min(max_height, remaining)

        # Guardia: evitar bucle infinito
        actual_h = max(actual_h, 1)

        frag = full_img.crop((0, y, w, y + actual_h))

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False,
                                         prefix="frag_") as tmp:
            frag.save(tmp.name, "PNG")
            temp_files.append(tmp.name)

        frag.close()
        fragments.append(Path(temp_files[-1]))
        y += actual_h

    full_img.close()
    print(f"[autounify] {image_path.name}: dividida en {len(fragments)} "
          f"fragmentos (altura original={h}px)")
    return fragments


# ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────────

def autounify_img_in_folder(folder_path: str, max_height: int = 3000,
                            ocr_lang: str = "en", safe_cut: bool = False,
                            save_remnant: bool = False,
                            progress_cb=None, log_cb=None) -> List[str]:
    """
    Unifica (stitch) verticalmente las imágenes de una carpeta en liras de
    altura ≤ max_height.

    Parámetros:
        folder_path   Carpeta con las imágenes fuente.
        max_height    Altura máxima de cada lira en píxeles (default 3000).
        ocr_lang      Código de idioma para PaddleOCR (default "en").
        safe_cut      False (default) → corte duro en max_height (~5× más rápido).
                      True  → buscar corte entre párrafos vía PaddleOCR (lento).
        save_remnant  True → guardar el remanente final aunque sea pequeño.
                      False → descartar el remanente si no llena una lira.
        progress_cb   Callable(int 0-100) opcional para reportar progreso.
        log_cb        Callable(str) opcional para emitir mensajes de log.

    Retorna:
        Lista de rutas absolutas a las liras generadas (en <folder>/unified/).
    """
    def _log(msg: str):
        print(msg)
        if log_cb:
            log_cb(msg)

    def _prog(pct: int):
        if progress_cb:
            progress_cb(max(0, min(100, pct)))

    # ── Freeze: suspender procesos pesados antes de PaddleOCR ───────────
    _snap = None
    if _PROCMGR_OK and _ProcessSnapshot is not None:
        _snap = _ProcessSnapshot()
        _snap.freeze(log_cb=log_cb)

    folder = Path(folder_path)
    if not folder.is_dir():
        raise ValueError(f"La carpeta no existe: {folder_path}")

    image_files = sorted(
        [f for f in folder.iterdir() if f.suffix.lower() in SUPPORTED_EXT],
        key=lambda x: x.name
    )
    if not image_files:
        _log("[autounify] No se encontraron imágenes.")
        return []

    total_imgs = len(image_files)
    _log(f"[autounify] {total_imgs} imágenes encontradas, "
         f"max_height={max_height}px, safe_cut={safe_cut}")

    output_dir = folder / "unified"
    output_dir.mkdir(exist_ok=True)

    # ── FASE 0: Pre-dividir imágenes enormes ──────────────────────────────────
    all_items:      List[Path] = []
    temp_fragments: List[Path] = []

    for idx, img_path in enumerate(image_files):
        _prog(int(idx / total_imgs * 20))
        frags = _split_large_image(img_path, max_height, ocr_lang, safe_cut)
        all_items.extend(frags)
        if len(frags) > 1:
            temp_fragments.extend(frags)

    _log(f"[autounify] Total de elementos a procesar "
         f"(incluyendo fragmentos): {len(all_items)}")
    total_items = len(all_items)

    # ── FASE 1: Pre-cargar todas las imágenes en paralelo → luego apilar ─────
    # ThreadPoolExecutor: I/O paralelo en hilos, sin GIL para PIL/numpy.
    # En benchmarks: 40 imágenes JPG 800px → carga de 18s → ~3s con 8 hilos.
    import numpy as np
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _load_image(args):
        idx, item_path, target_w = args
        with Image.open(item_path) as img:
            pil = img.convert("RGB")
            w, h = pil.size
            if target_w is not None and w != target_w:
                new_h = int(h * target_w / w)
                pil = pil.resize((target_w, new_h), Image.LANCZOS)
            arr = np.array(pil)
        return idx, arr

    # Primer paso: cargar la primera imagen para obtener ancho de referencia
    _prog(22)
    with Image.open(all_items[0]) as _first:
        _first_rgb = _first.convert("RGB")
        ref_w = _first_rgb.size[0]
        arrays_loaded: list = [None] * total_items
        arrays_loaded[0] = np.array(_first_rgb)

    # Cargar el resto en paralelo
    n_workers = min(8, (os.cpu_count() or 2))
    tasks = [(i, p, ref_w) for i, p in enumerate(all_items) if i > 0]

    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(_load_image, t): t[0] for t in tasks}
        for done_count, fut in enumerate(as_completed(futures), start=1):
            i, arr = fut.result()
            arrays_loaded[i] = arr
            _prog(22 + int(done_count / max(len(tasks), 1) * 40))

    _prog(62)
    _log(f"[autounify] Carga paralela completada ({n_workers} hilos)")

    # ── FASE 1b: Apilar y cortar ──────────────────────────────────────────────

    output_paths: List[str]      = []
    current_arr:  Optional[object] = None   # ndarray acumulado (H, W, 3)
    current_w:    Optional[int]  = None
    current_h:    int            = 0

    for idx, next_arr in enumerate(arrays_loaded):
        _prog(62 + int(idx / total_items * 28))
        if next_arr is None:
            continue
        _log(f"[autounify] Apilando {idx+1}/{total_items}")

        # Primera imagen → inicializar acumulador
        if current_arr is None:
            current_arr = next_arr
            current_w   = next_arr.shape[1]
            current_h   = next_arr.shape[0]
            continue

        # Apilar verticalmente (C-level, sin copias PIL intermedias)
        current_arr = np.vstack([current_arr, next_arr])
        current_h   = current_arr.shape[0]

        # Corte iterativo mientras la altura supere max_height
        while current_h > max_height:
            if safe_cut:
                # find_safe_cut_position necesita un objeto Image
                canvas_pil = Image.fromarray(current_arr)
                cut_h = find_safe_cut_position(
                    canvas_pil, current_h, max_height, ocr_lang)
                canvas_pil.close()
            else:
                cut_h = max_height

            cut_h = int(min(cut_h, current_h))

            # Guardar lira superior
            output_idx = len(output_paths) + 1
            out_path   = output_dir / f"unified_{output_idx:03d}.jpg"
            Image.fromarray(current_arr[:cut_h]).save(
                out_path, "JPEG", quality=92, optimize=False)
            output_paths.append(str(out_path))
            _log(f"[autounify]   → Lote {output_idx}: cortado a {cut_h}px "
                 f"(de {current_h}px)")

            if cut_h < current_h:
                current_arr = current_arr[cut_h:]
                current_h   = current_arr.shape[0]
            else:
                current_arr = None
                current_h   = 0
                break

    # ── FASE 2: Remanente final ───────────────────────────────────────────────
    if current_arr is not None and current_h > 0:
        if save_remnant:
            output_idx = len(output_paths) + 1
            out_path   = output_dir / f"unified_{output_idx:03d}.jpg"
            Image.fromarray(current_arr).save(out_path, "JPEG", quality=92, optimize=False)
            output_paths.append(str(out_path))
            _log(f"[autounify]   → Último lote {output_idx}: altura final {current_h}px")
        else:
            _log(f"[autounify]   → Remanente descartado ({current_h}px) — opción desactivada")

    # Limpiar fragmentos temporales de Fase 0
    for frag in temp_fragments:
        try:
            os.unlink(frag)
        except Exception:
            pass

    _prog(100)
    _log(f"[autounify] ✓ {len(output_paths)} imágenes generadas en {output_dir}")

    # ── Thaw: reanudar procesos suspendidos por freeze ───────────────────
    if _snap is not None and _snap.is_frozen:
        _snap.thaw(log_cb=log_cb)

    return output_paths


# ─── REEMPLAZAR ORIGINALES CON UNIFICADAS ────────────────────────────────────

def replace_originals_with_unified(folder_path: str, log_cb=None) -> bool:
    """
    Copia las imágenes de <folder>/unified/ de vuelta a la carpeta original,
    reemplazando los archivos fuente con nombres ordenados (001.png, 002.png…).
    La subcarpeta unified/ queda intacta como respaldo.

    Retorna True si tuvo éxito, False si hubo algún error.
    """
    import shutil

    def _log(msg: str):
        print(msg)
        if log_cb:
            log_cb(msg)

    folder  = Path(folder_path)
    unified = folder / "unified"

    if not unified.is_dir():
        _log(f"[autounify] No se encontró subcarpeta unified/ en {folder}")
        return False

    unified_imgs = sorted(
        [f for f in unified.iterdir() if f.suffix.lower() in SUPPORTED_EXT],
        key=lambda x: x.name
    )
    if not unified_imgs:
        _log("[autounify] La carpeta unified/ está vacía — nada que reemplazar.")
        return False

    # Eliminar imágenes originales de la carpeta padre (no subcarpetas)
    originals = [f for f in folder.iterdir()
                 if f.is_file() and f.suffix.lower() in SUPPORTED_EXT]
    for orig in originals:
        try:
            orig.unlink()
        except Exception as e:
            _log(f"[autounify] No se pudo eliminar {orig.name}: {e}")

    _log(f"[autounify] {len(originals)} originales eliminados. "
         f"Copiando {len(unified_imgs)} unificadas…")

    for idx, src in enumerate(unified_imgs, start=1):
        dst = folder / f"{idx:03d}{src.suffix}"
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            _log(f"[autounify] Error copiando {src.name} → {dst.name}: {e}")
            return False

    _log(f"[autounify] ✓ {len(unified_imgs)} imágenes reemplazaron los "
         f"originales en {folder.name}/")
    return True


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python autounify.py <carpeta> [altura_max] [lang] [safe_cut]")
        sys.exit(1)

    folder = sys.argv[1]
    max_h  = int(sys.argv[2])              if len(sys.argv) > 2 else 3000
    lang   = sys.argv[3]                   if len(sys.argv) > 3 else "en"
    safe   = sys.argv[4].lower() != "false" if len(sys.argv) > 4 else True

    try:
        autounify_img_in_folder(folder, max_h, ocr_lang=lang, safe_cut=safe)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)