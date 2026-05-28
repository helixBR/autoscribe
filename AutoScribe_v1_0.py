"""
AutoScribe_v1_0.py — Interfaz Principal UNIFICADA (Futurista · HUD Edition)
═══════════════════════════════════════════════════════════════════════════════
Conecta: Motor_Paddle_OCR.py | autounify.py | Translator_online.py | Translator_offline.py
Tema:    autoscribe_hud_theme.py  ← REQUERIDO en la misma carpeta

Cambios v1.0 → HUD Edition:
  · Paleta unificada HUD (cyan neón / negro profundo / Orbitron / Share Tech Mono).
  · WormProgressBar → HudProgressBar  (worm effect idéntico, estética HUD).
  · Header → HudHeaderBar (ring giratorio animado con EKG integrado).
  · Footer → HudFooterStrip (LED + barras de frecuencia + versión).
  · Tabs → HudTabWidget (pestañas Orbitron con borde-top cyan).
  · QPushButton#red → objectName «hud_primary» (mapeo automático vía CSS).
  · QPushButton#ghost → objectName «hud_ghost».
  · Compatibilidad CSS: todos los objectNames legacy (#panel, #header, etc.)
    siguen funcionando — sin tocar los paneles secundarios.
  · HudToastManager: reemplaza QMessageBox en estados informativos.
  · Mismo comportamiento funcional — CERO cambios en workers / OCR / lógica.

Dependencias nuevas (solo UI):
    autoscribe_hud_theme.py   ← en la misma carpeta que este archivo.
"""

# ─── PADDLE / OneDNN — DEBE IR ANTES DE CUALQUIER IMPORT ─────────────────────
import os
os.environ["FLAGS_use_mkldnn"]      = "0"
os.environ["PADDLE_DISABLE_ONEDNN"] = "1"
os.environ["OMP_NUM_THREADS"]       = "1"
os.environ["KMP_DUPLICATE_LIB_OK"]  = "TRUE"
# ─────────────────────────────────────────────────────────────────────────────

import sys, json, hashlib, re, time, subprocess, shutil
try:
    from send2trash import send2trash as _send2trash
    _HAS_SEND2TRASH = True
except ImportError:
    _HAS_SEND2TRASH = False
    def _send2trash(p): pass
from pathlib import Path
from typing import List, Dict, Optional

_BASE_DIR = Path(__file__).parent
import sys as _sys
if str(_BASE_DIR) not in _sys.path:
    _sys.path.insert(0, str(_BASE_DIR))

# ─── HUD THEME ───────────────────────────────────────────────────────────────
from ui.autoscribe_hud_theme import (
    HUD_QSS, apply_hud_theme,
    HudPanelFrame, HudHeaderBar,
    HudLabel, HudSectionLabel,
    HudButton, HudGhostButton, HudDangerButton,
    HudComboBox, HudLineEdit, HudCheckBox,
    HudProgressBar as HudProgressBarWidget,
    HudTabWidget,
    HudClockWidget, HudEkgWidget, HudRightColumn,
    HudToastManager, HudFileItem,
    HudModuleRow, HudSystemBar, HudFooterStrip,
    TacticalCorners,
    HudNetworkBar,
    # ── v3.0 nuevos widgets ────────────────────────────────────────────────
    HudTabSwitcher,
    HudSystemMonitor,
    HudConsolePanel,
    HudSystemStatePanel,
    HudLiveStatsPanel,
    HudRichToolbar,
    HudWordCounter,
    HudUserPanel as HudUserPanelWidget,
    HudMangaLibraryPanel,
    TutorialPanel,
    C_CYAN, C_RED, C_GREEN, C_TX, C_TX_DIM, C_TX_MID,
    C_BG, C_CYAN_DARK,
)
# ─────────────────────────────────────────────────────────────────────────────

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QFrame, QComboBox,
    QLineEdit, QMessageBox, QCheckBox, QDialog, QScrollArea, QSplitter,
    QTextEdit, QTabWidget, QListWidget, QListWidgetItem, QSizePolicy,
    QToolButton, QSpinBox, QAbstractItemView, QTreeWidget, QTreeWidgetItem,
    QGridLayout, QSlider, QDialogButtonBox, QPlainTextEdit, QStackedWidget
)
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QRectF, QPointF, QPoint, QSize,
    QSettings,
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QColor, QPainterPath, QLinearGradient, QRadialGradient,
    QBrush, QPen, QIcon, QFont, QDragEnterEvent, QDropEvent, QCursor, QMovie,
    QMouseEvent
)

# Multimedia opcional (PyQt6-Qt6-Multimedia) para video de fondo
try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    _HAS_MULTIMEDIA = True
except ImportError:
    _HAS_MULTIMEDIA = False

# ── WormProgressBar → alias a HudProgressBar para compatibilidad total ───────
WormProgressBar = HudProgressBarWidget

# ── Opciones de idioma OCR ───────────────────────────────────────────────────
OCR_LANG_OPTIONS = [
    ("Inglés",       "en"),  ("Español",      "es"),  ("Japonés",      "japan"),
    ("Coreano",      "korean"), ("Chino Simp.",  "ch"),  ("Chino Trad.",  "chinese_cht"),
    ("Árabe",        "ar"),  ("Francés",      "fr"),  ("Alemán",       "german"),
    ("Portugués",    "pt"),  ("Italiano",     "it"),  ("Ruso",         "ru"),
    ("Hindi",        "hi"),
]
TEXT_CASE_OPTIONS = [
    ("MAYÚSCULAS",  "upper"), ("minúsculas",  "lower"), ("Capitalizar", "capitalize"),
]
_PADDLE_PANEL_OK = True

# ─── GRACEFUL IMPORTS ────────────────────────────────────────────────────────
try:
    from ocr.ocr_space import OCRWorkerSpace, UnifyWorkerSpace as UnifyWorkerSpace_OCRSpace
    SPACE_OK = True
except ImportError:
    SPACE_OK = False; OCRWorkerSpace = None; UnifyWorkerSpace_OCRSpace = None

try:
    from ocr.Motor_Paddle_OCR import OCRWorker, UnifyWorker, extract_video_frames
    MOTOR_OK = True
except ImportError:
    MOTOR_OK = False; OCRWorker = UnifyWorker = extract_video_frames = None

try:
    from ocr.crop_paddle import OCRWorkerCropPaddle
except ImportError:
    OCRWorkerCropPaddle = None

HYBRID_OK = False; OCRWorkerHybrid = None

try:
    from pipeline.autounify import autounify_img_in_folder
    UNIFY_OK = True
except ImportError:
    UNIFY_OK = False

try:
    from pipeline.process_manager import ProcessSnapshot, is_available as _procmgr_available
    PROCMGR_OK = _procmgr_available()
except ImportError:
    PROCMGR_OK = False; ProcessSnapshot = None

try:
    from translation.Translator_online import (
        get_online_translator, translate_structured as _online_translate_structured,
        DEST_LANGS as _ONLINE_DEST_LANGS
    )
    ONLINE_OK = True
except ImportError:
    ONLINE_OK = False; get_online_translator = None; _online_translate_structured = None

try:
    from translation.Translator_offline import (
        get_argos_translator, translate_structured_argos as _offline_translate_structured,
    )
    OFFLINE_OK = True
except ImportError:
    OFFLINE_OK = False; get_argos_translator = None; _offline_translate_structured = None

TRANS_OK = ONLINE_OK or OFFLINE_OK

# ─── WORKERS DE TRADUCCIÓN ───────────────────────────────────────────────────
class ModelLoadWorker(QThread):
    finished = pyqtSignal(object, str)
    def __init__(self, engine_id: str, key_or_path: str, gpu_layers: int = 0):
        super().__init__()
        self._engine_id = engine_id; self._key_or_path = key_or_path; self._gpu_layers = gpu_layers
    def run(self):
        try:
            if self._engine_id in ("deepl", "claude", "groq"):
                t = get_online_translator(self._engine_id, self._key_or_path)
                ok, msg = t.test_connection()
                self.finished.emit(t if ok else None, msg)
            elif self._engine_id == "offline":
                t = get_argos_translator()
                ok, msg = t.test_connection()
                self.finished.emit(t if ok else None, msg)
            else:
                self.finished.emit(None, "Sin motor seleccionado")
        except Exception as ex:
            self.finished.emit(None, f"✗ Error: {ex}")

class TranslationWorker(QThread):
    finished = pyqtSignal(str); error = pyqtSignal(str); progress = pyqtSignal(int)
    def __init__(self, translator_widget, text: str, target: str):
        super().__init__()
        self._tw = translator_widget; self._text = text; self._target = target
    def run(self):
        try:
            result = self._tw._translate_structured(
                self._text, self._target, progress_cb=lambda p: self.progress.emit(p))
            self.finished.emit(result)
        except Exception as ex:
            self.error.emit(str(ex))

# ─── PATHS ────────────────────────────────────────────────────────────────────
BASE       = Path(__file__).parent
LOGOS_DIR  = BASE / "assets" / "logos"
FONDOS_DIR = BASE / "assets" / "fondos"
CONFIG_F   = BASE / "autoscribe_config.json"
USERS_F    = BASE / "autoscribe_users.json"
LOGO_PNG   = str(LOGOS_DIR / "hx.png")
LOGO_ICO   = str(LOGOS_DIR / "hx.ico")

SUPPORTED_IMG = {".jpg",".jpeg",".png",".bmp",".tiff",".tif",".webp",".ico",".svg",".avif",".jxl"}
SUPPORTED_GIF = {".gif"}   # animados via QMovie
SUPPORTED_VID = {".mp4",".avi",".mov",".mkv",".webm",".flv",".wmv",".m4v"}

# ─── BACKEND ──────────────────────────────────────────────────────────────────
BACKEND_URL = "https://autoscribe-backend.onrender.com"



OCR_ENGINE_OPTIONS   = [("1. PaddleOCR", "paddle")]
READING_ORDER_OPTIONS = [("RTL — Manga  (→←)", "rtl"), ("LTR — Manhwa (←→)", "ltr")]
ORIENTATION_OPTIONS   = [("Auto-detectar", "auto"), ("Horizontal", "horizontal"), ("Vertical", "vertical")]
DEST_LANGS = [
    ("No traduc.",""), ("Español","es"), ("English","en"),
    ("中文 简","zh-CN"), ("日本語","ja"), ("한국어","ko"),
    ("Français","fr"), ("Deutsch","de"), ("Português","pt"), ("Русский","ru"),
]

# ─── PALETA HUD (reemplaza los valores legacy — mismos nombres de variable) ───
# Los widgets que usan estos como strings inline conservan su funcionamiento.
A   = C_RED          # "#ff3355"  (accent rojo → danger)
A2  = "#cc1a35"
AG  = "#ff6677"
BG  = C_BG           # "#010307"
BD  = "#0a2540"
TX  = C_TX           # "#e3f7ff"
DM  = C_TX_DIM       # "#2e6a88"
MT  = "#0d2033"
GR  = C_GREEN        # "#00ff9d"
OR  = "#ffd44d"
CY  = C_CYAN         # "#00eaff"
CY2 = C_CYAN_DARK    # "#005f96"
PU  = "#9d4edd"

# ─── APP_QSS: HUD_QSS + mapa de compatibilidad para objectNames legacy ───────
# Todos los paneles que usan setObjectName("panel"), "ghost", "red", etc.
# siguen funcionando sin tocarlos.
_COMPAT_QSS = f"""
QFrame#panel {{
    background: transparent;
    border: none;
}}
QFrame#panel_glow {{
    background: transparent;
    border: none;
}}
QFrame#sectionHeader {{
    background: rgba(1,8,24,200);
    border: 1px solid rgba(0,180,255,30); border-radius: 3px;
}}
QFrame#statusbar {{
    background: rgba(1,4,10,235);
    border-top: 1px solid rgba(0,180,255,36);
}}
QFrame#translatorbar {{
    background: rgba(3,12,32,210);
    border-top: 1px solid rgba(0,180,255,30);
}}
QFrame#loginCard {{
    background: rgba(2,9,24,235);
    border: 1px solid rgba(0,180,255,64); border-radius: 8px;
}}

/* Botones legacy mapeados a HUD */
QPushButton#red {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(180,25,45,220), stop:1 rgba(255,51,85,235));
    color: #ffffff; border: 1px solid rgba(255,51,85,90);
    font-family: 'Orbitron','Segoe UI',sans-serif;
    font-size: 10px; font-weight: 700; letter-spacing: 0.8px;
    border-radius: 3px; padding: 5px 14px;
}}
QPushButton#red:hover {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 rgba(220,30,55,240), stop:1 rgba(255,80,100,255));
    border-color: {C_RED};
}}
QPushButton#red:disabled {{
    background: rgba(40,15,20,160); border-color: rgba(100,30,45,60);
    color: rgba(180,100,110,100);
}}
QPushButton#ghost {{
    background: transparent; color: {C_TX_DIM};
    border: 1px solid rgba(0,180,255,25); border-radius: 3px;
    padding: 3px 8px; font-size: 10px;
    font-family: 'Rajdhani','Segoe UI',sans-serif; font-weight: 600;
}}
QPushButton#ghost:hover {{
    border-color: rgba(0,180,255,80); color: {C_TX};
    background: rgba(0,180,255,15);
}}
QPushButton#cyan {{
    background: rgba(0,180,255,18); color: {C_CYAN};
    border: 1px solid rgba(0,180,255,50); border-radius: 3px;
    padding: 3px 8px; font-size: 10px;
}}
QPushButton#cyan:hover {{
    background: rgba(0,180,255,35); border-color: {C_CYAN};
}}

/* Labels legacy */
QLabel#dim    {{ color: {C_TX_DIM}; }}
QLabel#accent {{ color: {C_RED}; font-weight: bold; }}
QLabel#cyan   {{ color: {C_CYAN}; font-size: 9px; letter-spacing:1px; font-weight:bold; }}

/* Checkbox legacy */
QCheckBox {{ color: {C_TX}; spacing: 5px; font-size: 11px; }}
QCheckBox::indicator {{
    width:13px; height:13px; border:1px solid rgba(0,180,255,64);
    border-radius:2px; background:rgba(0,0,0,77);
}}
QCheckBox::indicator:checked {{
    background: rgba(0,234,255,64); border-color: {C_CYAN};
}}
QCheckBox::indicator:hover {{ border-color: rgba(0,180,255,128); }}

QGroupBox {{
    color: {C_TX_DIM}; border: 1px solid rgba(0,180,255,25);
    border-radius: 3px; margin-top: 8px; padding-top: 6px;
    font-size: 10px; letter-spacing: 1px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 8px; padding: 0 4px; color: {C_CYAN};
}}

QProgressBar {{
    background: rgba(0,180,255,15); border: none; border-radius: 3px;
    text-align: center; color: {C_TX}; font-size: 10px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C_CYAN_DARK}, stop:1 {C_CYAN}); border-radius:2px;
}}
"""

APP_QSS = HUD_QSS + _COMPAT_QSS

# ─── TEMAS ALTERNATIVOS ───────────────────────────────────────────────────────

_CHK_FUTURISTIC = f"""
    QCheckBox {{
        color:{TX}; spacing:5px; font-size:10px; background:transparent;
    }}
    QCheckBox::indicator {{
        width:12px; height:12px;
        border:1px solid rgba(0,180,255,64); border-radius:2px;
        background:rgba(0,0,0,77);
    }}
    QCheckBox::indicator:checked {{
        background:rgba(0,234,255,64); border-color:{CY};
    }}
    QCheckBox::indicator:hover {{ border-color:rgba(0,180,255,128); }}
"""
_COMBO_FUTURISTIC = f"""
    QComboBox {{
        background:rgba(0,4,16,128); color:{TX};
        border:1px solid rgba(0,180,255,36); border-radius:3px;
        padding:2px 6px; font-size:10px; font-weight:600;
        font-family:'Rajdhani','Segoe UI',sans-serif;
    }}
    QComboBox:focus {{ border:1px solid rgba(0,180,255,128); outline:none; }}
    QComboBox::drop-down {{ border:none; width:16px; background:transparent; }}
    QComboBox::down-arrow {{ image:none; border:none; }}
    QComboBox QAbstractItemView {{
        background:rgba(2,9,30,245); color:{TX};
        border:1px solid rgba(0,180,255,51); border-radius:3px; outline:none;
        selection-background-color:rgba(0,180,255,46);
    }}
    QComboBox QAbstractItemView::item {{ padding:3px 6px; border:none; }}
    QComboBox QAbstractItemView::item:selected {{ background:rgba(0,180,255,46); }}
"""
_ROW_FUTURISTIC = f"""
    QFrame {{
        background:rgba(0,10,30,130);
        border:1px solid rgba(0,180,255,20); border-radius:3px;
    }}
"""
_LBL_DIM     = f"color:rgba(46,106,136,0.90);font-size:10px;background:transparent;border:none;"
_LBL_SECTION = f"color:{CY};font-size:9px;font-weight:bold;letter-spacing:1.5px;background:transparent;"

# ─── UTILS ────────────────────────────────────────────────────────────────────
def load_cfg() -> Dict:
    try:
        if CONFIG_F.exists():
            return json.loads(CONFIG_F.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def save_cfg(cfg: Dict):
    try:
        CONFIG_F.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

import urllib.request as _urllib_req
import urllib.error  as _urllib_err

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def is_unlimited() -> bool:
    """OCR ilimitado para todos los usuarios registrados."""
    return True

# ─── AUTH: backend primero, caché local como fallback ─────────────────────────
def _api_post(endpoint: str, payload: dict) -> dict:
    """POST JSON al backend. Lanza RuntimeError con el mensaje del servidor si falla."""
    data = json.dumps(payload).encode()
    req  = _urllib_req.Request(
        f"{BACKEND_URL}{endpoint}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _urllib_req.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except _urllib_err.HTTPError as e:
        body = e.read().decode()
        try:
            msg = json.loads(body).get("detail", body)
        except Exception:
            msg = body
        raise RuntimeError(msg)
    except Exception as ex:
        raise RuntimeError(str(ex))

def _cache_load() -> dict:
    try:
        if USERS_F.exists():
            return json.loads(USERS_F.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def _cache_save(email: str, info: dict):
    cache = _cache_load()
    cache[email.strip().lower()] = info
    try:
        USERS_F.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def load_users() -> dict:
    return _cache_load()

def save_user(email: str, name: str, password: str, role: str = "usuario"):
    """Registra en el backend y guarda en caché local."""
    _api_post("/register", {"email": email.strip().lower(), "password": password, "name": name})
    _cache_save(email.strip().lower(), {"hash": _hash(password), "role": role, "name": name})

def check_login(email: str, password: str) -> Optional[Dict]:
    """Login contra el backend; si no hay red usa caché local."""
    try:
        resp = _api_post("/login", {"email": email.strip().lower(), "password": password})
        # resp puede traer: {email, name, role, ...}
        info = {
            "hash": _hash(password),
            "role": resp.get("role", "usuario"),
            "name": resp.get("name", email.split("@")[0]),
        }
        _cache_save(email.strip().lower(), info)
        return info
    except RuntimeError:
        raise   # error de credenciales → propagar
    except Exception:
        # Sin red → fallback a caché local
        cache = _cache_load()
        info  = cache.get(email.strip().lower())
        if info and info.get("hash") == _hash(password):
            return info
        return None

def scan_fondos() -> List[Path]:
    paths = []
    if FONDOS_DIR.exists():
        for f in sorted(FONDOS_DIR.iterdir()):
            if f.suffix.lower() in SUPPORTED_IMG | SUPPORTED_GIF | SUPPORTED_VID:
                paths.append(f)
    return paths

def scan_images_in_folder(folder: Path) -> List[Path]:
    try:
        files = [f for f in folder.iterdir() if f.suffix.lower() in SUPPORTED_IMG]
        return sorted(files, key=_natural_key)
    except Exception:
        return []

def _natural_key(p: Path) -> list:
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', p.name)]


# ══════════════════════════════════════════════════════════════════════════════
#  PANELES UI INTEGRADOS
# ══════════════════════════════════════════════════════════════════════════════

class CollapsibleSection(QFrame):
    """Sección plegable HUD con cabecera animada y esquinas tácticas."""
    def __init__(self, title: str, parent=None, collapsed: bool = True):
        super().__init__(parent)
        self.setObjectName("panel")
        self._collapsed = collapsed
        self._build(title)

    def _build(self, title: str):
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)

        self._hdr = QFrame()
        self._hdr.setObjectName("sectionHeader")
        self._hdr.setFixedHeight(28)
        self._hdr.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        hl = QHBoxLayout(self._hdr)
        hl.setContentsMargins(8, 0, 8, 0); hl.setSpacing(6)

        self._arrow = QLabel("▸")
        self._arrow.setStyleSheet(f"color:{CY};font-size:10px;font-weight:bold;min-width:10px;")
        hl.addWidget(self._arrow)

        lbl = HudSectionLabel(title)
        hl.addWidget(lbl); hl.addStretch()
        self._lay.addWidget(self._hdr)

        self._body = QWidget()
        body_lay = QVBoxLayout(self._body)
        body_lay.setContentsMargins(6, 5, 6, 6); body_lay.setSpacing(4)
        self._body_lay = body_lay
        self._body.setVisible(not self._collapsed)
        self._lay.addWidget(self._body)
        self._hdr.mousePressEvent = lambda e: self.toggle()

    def toggle(self):
        self._collapsed = not self._collapsed
        self._body.setVisible(not self._collapsed)
        self._arrow.setText("▾" if not self._collapsed else "▸")

    def expand(self):
        self._collapsed = False; self._body.setVisible(True); self._arrow.setText("▾")

    def collapse(self):
        self._collapsed = True; self._body.setVisible(False); self._arrow.setText("▸")

    def add_widget(self, w: QWidget): self._body_lay.addWidget(w)
    def add_layout(self, lay): self._body_lay.addLayout(lay)
    def body_layout(self): return self._body_lay


# ─── MODULES SECTION ──────────────────────────────────────────────────────────
class ModulesSection(QFrame):
    """Panel de módulos expandibles con lógica de exclusividad.

    Reglas:
      · Máximo 2 módulos abiertos simultáneamente.
      · El módulo marcado como ``exclusive`` al abrirse cierra todos los demás.
      · Si intenta abrirse un módulo no-exclusivo mientras el exclusivo está
        abierto, el exclusivo se cierra primero.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 4, 0, 4)
        self._lay.setSpacing(2)
        self._sections: List["CollapsibleSection"] = []
        self._exclusive_idx: Optional[int] = None

    def add_module(
        self,
        icon: str,
        title: str,
        widget: QWidget,
        exclusive: bool = False,
    ) -> "CollapsibleSection":
        idx = len(self._sections)
        sec = CollapsibleSection(f"{icon} {title}", collapsed=True)
        sec.add_widget(widget)

        # ── reemplazar el handler de click de la cabecera ────────────────────
        def _hdr_click(ev, _idx=idx, _sec=sec):
            was_collapsed = _sec._collapsed
            if was_collapsed:
                self._on_about_to_open(_idx)
            _sec.toggle()

        sec._hdr.mousePressEvent = _hdr_click
        self._sections.append(sec)
        if exclusive:
            self._exclusive_idx = idx
        self._lay.addWidget(sec)
        return sec

    def _on_about_to_open(self, opening_idx: int):
        """Aplica reglas de exclusividad antes de abrir ``opening_idx``."""
        # FIX BUG3: usar _close_section() en lugar de sec.collapse() directo para
        # que _toggled se dispare y cierre también el panel flotante asociado.
        # Caso 1: el módulo que se abre ES el exclusivo → cerrar todos los demás
        if opening_idx == self._exclusive_idx:
            for i, sec in enumerate(self._sections):
                if i != opening_idx and not sec._collapsed:
                    self._close_section(sec)
            return

        # Caso 2: módulo no-exclusivo abre → cerrar el exclusivo si estuviera abierto
        if self._exclusive_idx is not None:
            exc = self._sections[self._exclusive_idx]
            if not exc._collapsed:
                self._close_section(exc)

        # Caso 3: máximo 2 módulos abiertos → cerrar el más antiguo si ya hay 2
        open_idxs = [i for i, s in enumerate(self._sections) if not s._collapsed]
        if len(open_idxs) >= 2:
            self._close_section(self._sections[open_idxs[0]])

    def _close_section(self, sec: "CollapsibleSection"):
        """Cierra una sección pasando por su toggle hooked para que se cierre
        también el panel flotante asociado (si _hook_module reemplazó sec.toggle)."""
        # FIX BUG3 & BUG7: si toggle fue reemplazado por _toggled (via _hook_module),
        # llamar sec.toggle() dispara _toggled que a su vez llama _close_module_panel.
        # Si toggle NO fue reemplazado (sección sin hook), se comporta igual que collapse().
        if not sec._collapsed:
            sec.toggle()

    def collapse_all(self):
        # FIX BUG7: usar _close_section para cerrar tambien los paneles flotantes
        for sec in self._sections:
            self._close_section(sec)


# ─── PADDLE OCR PANEL ─────────────────────────────────────────────────────────
class PaddleOCRPanel(QFrame):
    lang_changed = pyqtSignal(str)

    def __init__(self, cfg: Dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QFrame { background: transparent; border: none; }")
        self._cfg = cfg; self._build()

    def _lbl(self, t: str) -> QLabel:
        l = QLabel(t); l.setStyleSheet(_LBL_DIM); return l

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(3)

        r1 = QFrame(); r1.setStyleSheet(_ROW_FUTURISTIC); r1.setFixedHeight(30)
        h1 = QHBoxLayout(r1); h1.setContentsMargins(8, 0, 6, 0); h1.setSpacing(5)
        self.lang_combo = QComboBox()
        self.lang_combo.setStyleSheet(_COMBO_FUTURISTIC)
        self.lang_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for name, _ in OCR_LANG_OPTIONS: self.lang_combo.addItem(name)
        saved_lang = self._cfg.get("ocr_lang", "en")
        self.lang_combo.setCurrentIndex(next((i for i,(_, c) in enumerate(OCR_LANG_OPTIONS) if c == saved_lang), 0))
        self.lang_combo.currentIndexChanged.connect(self._on_lang)
        h1.addWidget(self._lbl("OCR:")); h1.addWidget(self.lang_combo, 1); lay.addWidget(r1)

        r2 = QFrame(); r2.setStyleSheet(_ROW_FUTURISTIC); r2.setFixedHeight(30)
        h2 = QHBoxLayout(r2); h2.setContentsMargins(8, 0, 6, 0); h2.setSpacing(5)
        self.fmt_combo = QComboBox(); self.fmt_combo.setStyleSheet(_COMBO_FUTURISTIC)
        self.fmt_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus); self.fmt_combo.addItems(["TXT", "DOCX"])
        saved_fmt = self._cfg.get("fmt", "TXT")
        self.fmt_combo.setCurrentIndex(["TXT","DOCX"].index(saved_fmt) if saved_fmt in ["TXT","DOCX"] else 0)
        self.case_combo = QComboBox(); self.case_combo.setStyleSheet(_COMBO_FUTURISTIC)
        self.case_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for name, _ in TEXT_CASE_OPTIONS: self.case_combo.addItem(name)
        saved_case = self._cfg.get("case_mode", "capitalize")
        self.case_combo.setCurrentIndex(next((i for i,(_, c) in enumerate(TEXT_CASE_OPTIONS) if c == saved_case), 0))
        h2.addWidget(self._lbl("Fmt:")); h2.addWidget(self.fmt_combo, 1)
        h2.addWidget(self._lbl("Caso:")); h2.addWidget(self.case_combo, 1); lay.addWidget(r2)

        r3 = QFrame(); r3.setStyleSheet(_ROW_FUTURISTIC); r3.setFixedHeight(28)
        h3 = QHBoxLayout(r3); h3.setContentsMargins(10, 0, 10, 0); h3.setSpacing(10)
        self.online_check = QCheckBox("🌐 Online")
        self.online_check.setChecked(self._cfg.get("online_learning", True))
        self.online_check.setStyleSheet(_CHK_FUTURISTIC)
        self.sfx_check = QCheckBox("💥 SFX")
        self.sfx_check.setChecked(self._cfg.get("keep_sfx", True))
        self.sfx_check.setStyleSheet(_CHK_FUTURISTIC)
        h3.addWidget(self.online_check); h3.addStretch(); h3.addWidget(self.sfx_check); lay.addWidget(r3)

        r4 = QFrame(); r4.setStyleSheet(_ROW_FUTURISTIC); r4.setFixedHeight(28)
        h4 = QHBoxLayout(r4); h4.setContentsMargins(10, 0, 10, 0); h4.setSpacing(10)
        self.rtl_check = QCheckBox("📖 RTL (Manga)")
        self.rtl_check.setChecked(self._cfg.get("rtl", True))
        self.rtl_check.setStyleSheet(_CHK_FUTURISTIC)
        self.crop_paddle_check = type("_AlwaysTrue", (), {
            "isChecked": staticmethod(lambda: True),
            "setChecked": staticmethod(lambda _v: None),
        })()
        h4.addWidget(self.rtl_check); h4.addStretch(); lay.addWidget(r4)

        r5 = QFrame(); r5.setStyleSheet(_ROW_FUTURISTIC); r5.setFixedHeight(28)
        h5 = QHBoxLayout(r5); h5.setContentsMargins(10, 0, 10, 0)
        self.vertical_check = QCheckBox("🈸 Vertical JP")
        self.vertical_check.setChecked(self._cfg.get("vertical_japanese", False))
        self.vertical_check.setStyleSheet(_CHK_FUTURISTIC)
        h5.addWidget(self.vertical_check); h5.addStretch(); lay.addWidget(r5)

    def _on_lang(self, idx: int):
        code = OCR_LANG_OPTIONS[idx][1] if idx < len(OCR_LANG_OPTIONS) else "en"
        self.lang_changed.emit(code)

    def get_lang_code(self) -> str:
        idx = self.lang_combo.currentIndex()
        return OCR_LANG_OPTIONS[idx][1] if idx < len(OCR_LANG_OPTIONS) else "en"

    def get_lang_name(self) -> str:
        idx = self.lang_combo.currentIndex()
        return OCR_LANG_OPTIONS[idx][0] if idx < len(OCR_LANG_OPTIONS) else "Inglés"

    def get_fmt(self) -> str: return self.fmt_combo.currentText()
    def get_crop_pipeline(self) -> bool: return True
    def get_rtl(self) -> bool: return self.rtl_check.isChecked()
    def get_vertical_japanese(self) -> bool: return self.vertical_check.isChecked()
    def get_case_code(self) -> str:
        idx = self.case_combo.currentIndex()
        return TEXT_CASE_OPTIONS[idx][1] if idx < len(TEXT_CASE_OPTIONS) else "capitalize"

_PaddleOCRPanel = PaddleOCRPanel


# ─── AUTO UNIFY PANEL ─────────────────────────────────────────────────────────
class AutoUnifyPanel(QFrame):
    remnant_toggled = pyqtSignal(bool)
    def __init__(self, cfg: Dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QFrame { background: transparent; border: none; }")
        self._cfg = cfg; self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(4)
        r1 = QHBoxLayout(); r1.setSpacing(6)
        lbl = QLabel("Alt.máx:"); lbl.setStyleSheet(_LBL_DIM); r1.addWidget(lbl)
        self._maxh = QSpinBox(); self._maxh.setRange(500, 10000)
        self._maxh.setValue(self._cfg.get("max_height", 3000))
        self._maxh.setSingleStep(500); self._maxh.setMaximumWidth(70)
        self._maxh.setStyleSheet("font-size:10px;"); r1.addWidget(self._maxh)
        self.remnant_check = QCheckBox("Remanente")
        self.remnant_check.setChecked(self._cfg.get("save_remnant", False))
        self.remnant_check.setStyleSheet(_CHK_FUTURISTIC)
        self.remnant_check.toggled.connect(self.remnant_toggled.emit)
        r1.addWidget(self.remnant_check); r1.addStretch(); lay.addLayout(r1)

    def get_max_height(self) -> int: return self._maxh.value()
    def get_save_remnant(self) -> bool: return self.remnant_check.isChecked()


# ─── TRADUCTOR PANEL ──────────────────────────────────────────────────────────
_TR_LANGUAGES = [
    ("No traducir", ""), ("Español", "es"), ("Inglés", "en"),
    ("Chino Simplificado", "zh-CN"), ("Chino Tradicional", "zh-TW"),
    ("Coreano", "ko"), ("Japonés", "ja"), ("Francés", "fr"),
    ("Portugués", "pt"), ("Alemán", "de"), ("Italiano", "it"), ("Árabe", "ar"),
]

class TraductorPanel(QFrame):
    def __init__(self, cfg: Dict, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QFrame { background: transparent; border: none; }")
        self._cfg = cfg; self._build()

    def _build(self):
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(0)
        r1 = QFrame(); r1.setStyleSheet(_ROW_FUTURISTIC); r1.setFixedHeight(30)
        h1 = QHBoxLayout(r1); h1.setContentsMargins(8, 0, 6, 0); h1.setSpacing(6)
        lbl = QLabel("Destino:"); lbl.setStyleSheet(_LBL_DIM)
        self.tr_combo = QComboBox(); self.tr_combo.setStyleSheet(_COMBO_FUTURISTIC)
        self.tr_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for name, _ in _TR_LANGUAGES: self.tr_combo.addItem(name)
        saved_tr = self._cfg.get("translate_to", "")
        self.tr_combo.setCurrentIndex(next((i for i,(_, c) in enumerate(_TR_LANGUAGES) if c == saved_tr), 0))
        h1.addWidget(lbl); h1.addWidget(self.tr_combo, 1); lay.addWidget(r1)

    def get_translate_to(self) -> str:
        idx = self.tr_combo.currentIndex()
        return _TR_LANGUAGES[idx][1] if idx < len(_TR_LANGUAGES) else ""

    def get_case_mode(self) -> str: return "original"


# ─── BUBBLE WIDGET ────────────────────────────────────────────────────────────
class BubbleWidget(QWidget):
    restore_requested = pyqtSignal()
    SIZE = 64

    def __init__(self, cfg: Dict, parent=None):
        super().__init__(parent,
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.SIZE, self.SIZE)
        self._cfg = cfg; self._drag_pos = None
        src = QPixmap(LOGO_PNG)
        self._pix = (src.scaled(self.SIZE, self.SIZE,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)
                     if not src.isNull() else src)
        x = cfg.get("bubble_x", -1); y = cfg.get("bubble_y", -1)
        if x >= 0 and y >= 0: self.move(x, y)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - self.SIZE - 24, screen.bottom() - self.SIZE - 24)

    def paintEvent(self, e):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self._pix.isNull():
            painter.drawPixmap((self.SIZE - self._pix.width()) // 2,
                               (self.SIZE - self._pix.height()) // 2, self._pix)
        painter.end()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._cfg["bubble_x"] = self.pos().x(); self._cfg["bubble_y"] = self.pos().y()
            save_cfg(self._cfg)
        self._drag_pos = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self.restore_requested.emit()

    def contextMenuEvent(self, e): self.restore_requested.emit()


# ─── LOGIN DIALOG — HUD Edition ───────────────────────────────────────────────
class LoginDialog(QDialog):
    login_ok = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True); self.setFixedSize(390, 500)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._drag_pos = None; self._mode = "login"; self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        self._card = QFrame(self); self._card.setObjectName("loginCard")
        self._cl = QVBoxLayout(self._card)
        self._cl.setContentsMargins(36, 32, 36, 32); self._cl.setSpacing(14)

        logo_lbl = QLabel()
        pix = QPixmap(LOGO_PNG)
        if not pix.isNull():
            logo_lbl.setPixmap(pix.scaled(52, 52, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation))
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self._cl.addWidget(logo_lbl)

        self._title_lbl = QLabel("AutoScribe")
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setStyleSheet(
            f"font-family:'Orbitron','Segoe UI',sans-serif;"
            f"font-size:22px;font-weight:700;color:{TX};letter-spacing:3px;")
        self._cl.addWidget(self._title_lbl)

        self._sub_lbl = QLabel("HELIX EDITION · Iniciar Sesión")
        self._sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub_lbl.setStyleSheet(f"font-size:10px;color:{DM};letter-spacing:1px;")
        self._cl.addWidget(self._sub_lbl); self._cl.addSpacing(4)

        self._name_field = QLineEdit(); self._name_field.setPlaceholderText("Nombre completo")
        self._name_field.setMinimumHeight(36); self._name_field.hide()
        self._cl.addWidget(self._name_field)

        self._email = QLineEdit(); self._email.setPlaceholderText("Correo electrónico")
        self._email.setMinimumHeight(36); self._cl.addWidget(self._email)

        self._pw = QLineEdit(); self._pw.setPlaceholderText("Contraseña")
        self._pw.setEchoMode(QLineEdit.EchoMode.Password); self._pw.setMinimumHeight(36)
        self._pw.returnPressed.connect(self._try_action); self._cl.addWidget(self._pw)

        row = QHBoxLayout()
        self._remember = QCheckBox("Mantener sesión"); row.addWidget(self._remember)
        row.addStretch(); self._cl.addLayout(row)

        self._err = QLabel("")
        self._err.setStyleSheet(f"color:{A}; font-size:11px;")
        self._err.setAlignment(Qt.AlignmentFlag.AlignCenter); self._cl.addWidget(self._err)

        # ── HudButton como botón de acción ───────────────────────────────────
        self._action_btn = HudButton("INGRESAR")
        self._action_btn.setMinimumHeight(38)
        self._action_btn.clicked.connect(self._try_action); self._cl.addWidget(self._action_btn)

        self._toggle_btn = HudGhostButton("¿No tienes cuenta? Registrarse")
        self._toggle_btn.setMinimumHeight(32)
        self._toggle_btn.clicked.connect(self._toggle_mode); self._cl.addWidget(self._toggle_btn)

        cr = QLabel("Created by Helix"); cr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cr.setStyleSheet(f"font-size:10px; color:{MT};"); self._cl.addWidget(cr)
        root.addWidget(self._card)

    def _toggle_mode(self):
        self._mode = "register" if self._mode == "login" else "login"
        is_reg = self._mode == "register"
        self._name_field.setVisible(is_reg)
        self._sub_lbl.setText("HELIX EDITION · " + ("Registro" if is_reg else "Iniciar Sesión"))
        self._action_btn.setText("REGISTRAR" if is_reg else "INGRESAR")
        self._toggle_btn.setText("¿Ya tienes cuenta? Iniciar sesión" if is_reg else "¿No tienes cuenta? Registrarse")
        self._err.clear()

    def _try_action(self):
        email = self._email.text().strip(); pw = self._pw.text()
        if not email or not pw:
            self._err.setText("Completa todos los campos."); return
        self._action_btn.setEnabled(False)
        self._err.setText("Conectando...")
        from PyQt6.QtWidgets import QApplication as _QApp
        _QApp.processEvents()
        try:
            if self._mode == "register":
                name = self._name_field.text().strip()
                if not name:
                    self._err.setText("Ingresa tu nombre.")
                    self._action_btn.setEnabled(True); return
                save_user(email, name, pw)
                info = {"hash": _hash(pw), "role": "usuario", "name": name}
            else:
                info = check_login(email, pw)
                if not info:
                    self._err.setText("Correo o contraseña incorrectos.")
                    self._action_btn.setEnabled(True); return
        except RuntimeError as ex:
            self._err.setText(str(ex)[:80])
            self._action_btn.setEnabled(True); return
        except Exception:
            self._err.setText("Sin conexión al servidor.")
            self._action_btn.setEnabled(True); return
        self._action_btn.setEnabled(True)
        cfg = load_cfg()
        cfg["remember_email"] = email if self._remember.isChecked() else cfg.pop("remember_email", None) or ""
        save_cfg(cfg)
        self.login_ok.emit({**info, "email": email}); self.accept()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(self.pos() + e.globalPosition().toPoint() - self._drag_pos)
            self._drag_pos = e.globalPosition().toPoint()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QRadialGradient(self.width()/2, self.height()/2, self.width()*0.6)
        grad.setColorAt(0, QColor(0, 180, 255, 20)); grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(self.rect(), QBrush(grad)); p.end()


# ─── OUTPUT DOC PANEL ─────────────────────────────────────────────────────────
class OutputDocPanel(HudPanelFrame):
    file_selected    = pyqtSignal(str)
    start_requested  = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent=parent, titulo="ARCHIVOS DE TEXTO", show_header=True)
        self.setContentsMargins(8, 36, 8, 8)
        self._files: List[Path] = []; self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(5)

        # ── Header con botones de gestión ────────────────────────────────────
        hdr = QHBoxLayout(); hdr.setSpacing(3)
        lbl = HudSectionLabel("ARCHIVOS DE TEXTO"); hdr.addWidget(lbl); hdr.addStretch()

        _btn_style = (
            "QToolButton{background:rgba(0,20,50,120);color:rgba(0,200,255,180);"
            "border:1px solid rgba(0,180,255,35);border-radius:3px;"
            "font-size:11px;min-width:22px;max-width:22px;min-height:22px;max-height:22px;}"
            "QToolButton:hover{background:rgba(0,180,255,30);color:#00eaff;"
            "border-color:rgba(0,180,255,80);}")
        _del_style = (
            "QToolButton{background:rgba(40,0,0,120);color:rgba(255,80,80,160);"
            "border:1px solid rgba(255,60,60,35);border-radius:3px;"
            "font-size:11px;min-width:22px;max-width:22px;min-height:22px;max-height:22px;}"
            "QToolButton:hover{background:rgba(180,0,0,50);color:#ff4444;"
            "border-color:rgba(255,60,60,90);}")

        self._ref_btn = QToolButton(); self._ref_btn.setText("↺")
        self._ref_btn.setToolTip("Actualizar lista desde carpeta de salida")
        self._ref_btn.setStyleSheet(_btn_style)
        self._ref_btn.clicked.connect(self._refresh); hdr.addWidget(self._ref_btn)

        self._del_btn = QToolButton(); self._del_btn.setText("🗑")
        self._del_btn.setToolTip("Enviar archivo seleccionado a la papelera")
        self._del_btn.setStyleSheet(_del_style)
        self._del_btn.clicked.connect(self._delete_selected); hdr.addWidget(self._del_btn)

        clr = QToolButton(); clr.setText("✕"); clr.setToolTip("Limpiar lista (no borra archivos)")
        clr.setStyleSheet(_btn_style); clr.setFixedSize(22, 22)
        clr.clicked.connect(self._clear); hdr.addWidget(clr)
        lay.addLayout(hdr)

        # ── Lista con menú contextual ─────────────────────────────────────────
        self._list = QListWidget()
        self._list.setToolTip("Doble clic: abrir  |  Clic derecho: opciones")
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._ctx_menu)
        self._list.itemDoubleClicked.connect(self._open_item)
        lay.addWidget(self._list, 1)

        self._count_lbl = QLabel("Sin archivos")
        self._count_lbl.setStyleSheet(f"color:{DM};font-size:10px;"); lay.addWidget(self._count_lbl)

        hb = QHBoxLayout(); hb.setSpacing(5)
        self._start_btn = HudButton("▶ INICIAR")
        self._start_btn.clicked.connect(self.start_requested.emit)
        self._cancel_btn = HudDangerButton("■")
        self._cancel_btn.setFixedWidth(32); self._cancel_btn.setEnabled(False)
        self._cancel_btn.setToolTip("Cancelar")
        self._cancel_btn.clicked.connect(self.cancel_requested.emit)
        hb.addWidget(self._start_btn, 1); hb.addWidget(self._cancel_btn); lay.addLayout(hb)

        self._prog = HudProgressBarWidget()
        self._prog.setValue(0); lay.addWidget(self._prog)

    def load_folder(self, folder_path: str):
        p = Path(folder_path)
        if not p.is_dir(): return
        self._folder_path = str(p)
        self._clear()
        files = sorted([f for f in p.iterdir() if f.suffix.lower() in (".docx", ".txt")], key=_natural_key)
        for f in files: self.add_file(str(f))

    def _refresh(self):
        """Recarga la carpeta de salida actual."""
        folder = getattr(self, "_folder_path", None)
        if folder:
            self.load_folder(folder)

    def add_file(self, path: str):
        p = Path(path)
        if p not in self._files:
            self._files.append(p)
            self._files = sorted(self._files, key=_natural_key)
            self._list.clear()
            for f in self._files:
                icon = "📝" if f.suffix == ".docx" else "📄"
                self._list.addItem(f"{icon} {f.name}")
            self._count_lbl.setText(f"{len(self._files)} archivo{'s' if len(self._files)!=1 else ''}")

    def _delete_selected(self):
        row = self._list.currentRow()
        if row < 0 or row >= len(self._files):
            return
        p = self._files[row]
        if not p.exists():
            self._files.pop(row); self._list.takeItem(row)
            self._count_lbl.setText(f"{len(self._files)} archivo{'s' if len(self._files)!=1 else ''}")
            return
        if _HAS_SEND2TRASH:
            try:
                _send2trash(str(p))
                self._files.pop(row); self._list.takeItem(row)
                self._count_lbl.setText(f"{len(self._files)} archivo{'s' if len(self._files)!=1 else ''}")
            except Exception as ex:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", f"No se pudo mover a la papelera:\n{ex}")
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Sin soporte", "send2trash no instalado.\nEjecuta: pip install send2trash")

    def _ctx_menu(self, pos):
        row = self._list.currentRow()
        if row < 0 or row >= len(self._files): return
        p = self._files[row]
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:rgba(2,10,28,240);color:#a0c8e0;"
            f"border:1px solid rgba(0,180,255,60);border-radius:4px;padding:4px;}}"
            f"QMenu::item{{padding:5px 16px;border-radius:3px;}}"
            f"QMenu::item:selected{{background:rgba(0,180,255,40);color:#fff;}}")
        act_open  = menu.addAction("📂  Abrir en editor")
        menu.addSeparator()
        act_del   = menu.addAction("🗑  Enviar a la papelera")
        act_del.setEnabled(_HAS_SEND2TRASH and p.exists())
        chosen = menu.exec(self._list.mapToGlobal(pos))
        if chosen == act_open:
            self.file_selected.emit(str(p))
        elif chosen == act_del:
            self._delete_selected()

    def _clear(self): self._files.clear(); self._list.clear(); self._count_lbl.setText("Sin archivos")

    def _open_item(self, item: QListWidgetItem):
        row = self._list.row(item)
        if 0 <= row < len(self._files): self.file_selected.emit(str(self._files[row]))

    def set_running(self, running: bool):
        self._start_btn.setEnabled(not running); self._cancel_btn.setEnabled(running)

    def set_progress(self, v: int): self._prog.setValue(v)


# ─── FOLDER QUEUE PANEL ───────────────────────────────────────────────────────
# ─── DRAGGABLE MODULE PANEL ───────────────────────────────────────────────────
class DraggableModulePanel(QFrame):
    """Panel flotante arrastrable con posición persistente."""
    closed = pyqtSignal(str)   # emite el panel_id al cerrar

    def __init__(self, panel_id: str, widget: QWidget, width: int,
                 saved_pos: "tuple[int,int] | None" = None, parent=None):
        super().__init__(parent)
        self._panel_id  = panel_id
        self._drag_pos  = None
        self._pos_saved = False

        self.setFixedWidth(width)
        self.setObjectName("mod_panel_float")
        self.setStyleSheet(
            "QFrame#mod_panel_float{"
            "background:rgba(0,6,22,242);"
            "border:1px solid rgba(0,180,255,70);"
            "border-radius:4px;}")
        self.setWindowFlags(Qt.WindowType.SubWindow)

        c_lay = QVBoxLayout(self)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(0)

        # Header arrastrable
        self._hdr = QFrame()
        self._hdr.setFixedHeight(24)
        self._hdr.setCursor(Qt.CursorShape.SizeAllCursor)
        self._hdr.setStyleSheet(
            "background:rgba(0,18,48,220);"
            "border-bottom:1px solid rgba(0,180,255,90);border-radius:4px 4px 0 0;")
        hdr_lay = QHBoxLayout(self._hdr)
        hdr_lay.setContentsMargins(8, 0, 4, 0); hdr_lay.setSpacing(4)
        hdr_lbl = QLabel(panel_id)
        hdr_lbl.setStyleSheet(
            f"font-family:'Orbitron','Segoe UI',sans-serif;"
            f"font-size:8px;font-weight:700;color:{CY};letter-spacing:1px;"
            f"background:transparent;")
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(16, 16)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton{background:transparent;color:rgba(255,80,100,180);"
            "border:none;font-size:9px;font-weight:700;}"
            "QPushButton:hover{color:#ff3355;}")
        close_btn.clicked.connect(lambda: self.closed.emit(panel_id))
        hdr_lay.addWidget(hdr_lbl); hdr_lay.addStretch(); hdr_lay.addWidget(close_btn)
        c_lay.addWidget(self._hdr)

        widget.setParent(self)
        c_lay.addWidget(widget)
        self.adjustSize()

        if saved_pos:
            self.move(saved_pos[0], saved_pos[1])

    # ── Arrastre por el header ────────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._hdr.geometry().contains(e.pos()):
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            new_pos = e.globalPosition().toPoint() - self._drag_pos
            # Limitar dentro del parent
            if self.parent():
                pr = self.parent().rect()
                new_pos.setX(max(0, min(new_pos.x(), pr.width()  - self.width())))
                new_pos.setY(max(0, min(new_pos.y(), pr.height() - self.height())))
            self.move(new_pos)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        self._pos_saved = True
        super().mouseReleaseEvent(e)

    def saved_position(self) -> "tuple[int,int]":
        return (self.pos().x(), self.pos().y())


class FolderQueuePanel(HudPanelFrame):
    unify_folders_run = pyqtSignal(list)
    ST_WAIT = "⏳"; ST_PROC = "⚙"; ST_DONE = "✓"; ST_ERR = "⚠"

    def __init__(self, parent=None):
        super().__init__(parent=parent, titulo="", show_header=False)
        self.setContentsMargins(8, 36, 8, 8)
        self._unify_folders: List[str] = []; self._unify_status: List[str] = []
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(4)
        hdr = QHBoxLayout()
        hdr.addStretch()
        lay.addLayout(hdr)

        maxh_row = QHBoxLayout(); maxh_row.setSpacing(4)
        maxh_row.addWidget(QLabel("Alt.máx:"))
        self._maxh = QSpinBox(); self._maxh.setRange(500, 10000)
        self._maxh.setValue(3000); self._maxh.setSingleStep(500); self._maxh.setMaximumWidth(68)
        maxh_row.addWidget(self._maxh); maxh_row.addStretch(); lay.addLayout(maxh_row)

        self._unify_list = DroppableListWidget()
        self._unify_list.setMinimumHeight(80)
        self._unify_list.setMaximumHeight(200)
        self._unify_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._unify_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._unify_list.setStyleSheet(
            f"QListWidget{{font-size:10px;border:1px dashed rgba(0,180,255,40);}}"
            f"QListWidget::item{{padding:2px 4px;}}"
        )
        self._unify_list.setToolTip("Arrastra carpetas aquí o usa + Añadir")
        self._unify_list.folders_dropped.connect(self._bulk_add); lay.addWidget(self._unify_list)

        btns = QHBoxLayout(); btns.setSpacing(4); btns.setContentsMargins(0, 2, 0, 0)
        add_btn = HudGhostButton("+ Añadir"); add_btn.clicked.connect(self._add_folders)
        rem_btn = HudGhostButton("– Quitar"); rem_btn.clicked.connect(self._rem_folder)
        btns.addWidget(add_btn, 1); btns.addWidget(rem_btn, 1); lay.addLayout(btns)

        dd_hint = QLabel("↕ arrastra carpetas aquí directamente")
        dd_hint.setStyleSheet(f"color:{DM};font-size:9px;font-style:italic;")
        dd_hint.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.addWidget(dd_hint)

        run_btn = HudGhostButton("⚡ Unificar todo"); run_btn.clicked.connect(self._run_all)
        lay.addWidget(run_btn)

    def get_max_height(self) -> int: return self._maxh.value()

    def _add_folders(self):
        import sys
        if sys.platform == "win32":
            self._picker = _FolderPickerThread()
            self._picker.folders_ready.connect(self._bulk_add); self._picker.start()
        else:
            folders = []
            while True:
                f = QFileDialog.getExistingDirectory(self, f"Carpeta {len(folders)+1} (Cancelar para terminar)")
                if not f: break
                if f not in folders: folders.append(f)
            self._bulk_add(folders)

    def _bulk_add(self, folders: List[str]):
        for folder in folders:
            if folder not in self._unify_folders:
                self._unify_folders.append(folder); self._unify_status.append(self.ST_WAIT)
                item = QListWidgetItem(f"{self.ST_WAIT} 📁 {Path(folder).name}")
                item.setToolTip(folder); self._unify_list.addItem(item)
                self._unify_list.scrollToBottom()

    def _rem_folder(self):
        row = self._unify_list.currentRow()
        if 0 <= row < len(self._unify_folders):
            self._unify_folders.pop(row); self._unify_status.pop(row)
            self._unify_list.takeItem(row)

    def _run_all(self):
        pending = [f for f, s in zip(self._unify_folders, self._unify_status) if s != self.ST_DONE]
        if not pending:
            QMessageBox.information(self, "AutoUnify", "Añade carpetas primero."); return
        self.unify_folders_run.emit(pending)

    def set_unify_status(self, folder: str, status: str):
        if folder in self._unify_folders:
            idx = self._unify_folders.index(folder)
            self._unify_status[idx] = status
            item = self._unify_list.item(idx)
            if item: item.setText(f"{status} 📁 {Path(folder).name}")


# ─── TEXT EDITOR WIDGET ───────────────────────────────────────────────────────
class TextEditorWidget(HudPanelFrame):
    image_hinted   = pyqtSignal(str)
    save_completed = pyqtSignal()          # ← NEW: emitido tras cada guardado

    def __init__(self, parent=None):
        super().__init__(parent=parent, titulo="EDITOR DE TEXTO", show_header=True, arrow_header=True)
        self.setContentsMargins(6, 36, 6, 6)
        self._history: List[str] = []; self._redo_stack: List[str] = []
        self._current_path: Optional[str] = None
        self._block_to_img: Dict[int, str] = {}
        self._clean_txt: str = ""
        lay = QVBoxLayout(self); lay.setContentsMargins(6, 6, 6, 6); lay.setSpacing(3)

        # ── Cabecera compacta ─────────────────────────────────────────────────
        tb = QHBoxLayout(); tb.setSpacing(4)
        self._path_lbl = QLabel("Sin documento")
        self._path_lbl.setStyleSheet(f"color:{DM};font-size:10px;")
        self._path_lbl.setMaximumWidth(200); tb.addWidget(self._path_lbl); tb.addStretch()
        lay.addLayout(tb)

        # ── Editor QTextEdit ─────────────────────────────────────────────────
        self._editor = QTextEdit()
        self._editor.setPlaceholderText("El texto extraído aparecerá aquí para editar…")
        self._editor.setFont(QFont("Consolas", 11))
        self._editor.textChanged.connect(self._on_change)
        self._editor.cursorPositionChanged.connect(self._on_cursor_moved)

        # ── HudRichToolbar (punto 11) ─────────────────────────────────────────
        self._toolbar = HudRichToolbar(self._editor)
        lay.addWidget(self._toolbar)
        lay.addWidget(self._editor)

    def _on_cursor_moved(self): return

    def get_font_size(self) -> int: return self._editor.font().pointSize()
    def set_font_size(self, v: int):
        self._editor.setFont(QFont("Consolas", v))
        if self._block_to_img or (hasattr(self, '_clean_txt') and self._clean_txt):
            self._rebuild_html()

    def _apply_case(self, fn):
        raw = getattr(self, '_clean_txt', None) or self._editor.toPlainText()
        lines = raw.split("\n"); result = [fn(line) if line.strip() else line for line in lines]
        new_text = "\n".join(result)
        self._editor.blockSignals(True); self._clean_txt = new_text; self._rebuild_html()
        self._editor.blockSignals(False); self._history.append(new_text)

    def _to_upper(self): self._apply_case(str.upper)
    def _to_lower(self): self._apply_case(str.lower)
    def _to_title(self):
        def sentence_case(s: str) -> str:
            if not s: return s
            parts = re.split(r'([.!?…]+\s+)', s); result = []
            for part in parts:
                if re.match(r'[.!?…]+\s+', part): result.append(part)
                elif part:
                    result.append(part[0].upper() + part[1:].lower() if len(part) > 1 else part.upper())
            return ''.join(result)
        self._apply_case(sentence_case)

    def _on_change(self):
        txt = self._editor.toPlainText(); self._clean_txt = txt
        if self._history and self._history[-1] == txt: return
        if len(self._history) > 80: self._history.pop(0)
        self._history.append(txt); self._redo_stack.clear()

    def undo(self):
        if len(self._history) > 1:
            self._redo_stack.append(self._history.pop()); self._editor.blockSignals(True)
            self._display_formatted(self._history[-1]); self._editor.blockSignals(False)

    def redo(self):
        if self._redo_stack:
            txt = self._redo_stack.pop(); self._history.append(txt)
            self._editor.blockSignals(True); self._display_formatted(txt); self._editor.blockSignals(False)

    def save(self):
        path = self._current_path
        if not path:
            p, _ = QFileDialog.getSaveFileName(self, "Guardar como", "", "Word (*.docx);;Texto (*.txt)")
            if not p: return
            self._current_path = p; self._path_lbl.setText(Path(p).name); path = p
        try:
            txt = self._editor.toPlainText()
            if path.lower().endswith(".docx"):
                from docx import Document
                if Path(path).exists():
                    doc = Document(path)
                    for para in doc.paragraphs: para.clear()
                    lines = txt.split("\n")
                    for i, line in enumerate(lines):
                        if i < len(doc.paragraphs): doc.paragraphs[i].text = line
                        else: doc.add_paragraph(line)
                    while len(doc.paragraphs) > len(lines):
                        p_elem = doc.paragraphs[-1]._element; p_elem.getparent().remove(p_elem)
                else:
                    doc = Document()
                    for line in txt.split("\n"): doc.add_paragraph(line)
                doc.save(path)
            else:
                Path(path).write_text(txt, encoding="utf-8")
            QMessageBox.information(self, "Guardado", f"✓ {Path(path).name}")
            self.save_completed.emit()          # ← notifica al word counter
        except Exception as ex:
            QMessageBox.critical(self, "Error al guardar", str(ex))

    def load_file(self, path: str):
        self._current_path = path; self._path_lbl.setText(Path(path).name)
        try:
            if path.endswith(".docx"):
                from docx import Document
                doc = Document(path); txt = "\n".join(p.text for p in doc.paragraphs)
            else:
                txt = Path(path).read_text(encoding="utf-8", errors="replace")
            self._display_formatted(txt); self._history = [txt]; self._redo_stack.clear()
        except Exception as ex:
            self._editor.setPlainText(f"Error al cargar: {ex}")

    def _display_formatted(self, txt: str):
        self._editor.blockSignals(True); self._block_to_img = {}
        SEP_RE = re.compile(r'^─{10,}$', re.MULTILINE)
        lines = txt.split("\n")
        if SEP_RE.search(txt):
            text_lines = []; current_img = ""; i = 0; block_num = 0
            while i < len(lines):
                stripped = lines[i].strip()
                if re.fullmatch(r'─{10,}', stripped):
                    img_name = lines[i+1].strip() if i+1 < len(lines) else ""
                    if img_name: current_img = img_name
                    skip = 1
                    if i+2 < len(lines) and re.fullmatch(r'─{10,}', lines[i+2].strip()): skip = 2
                    i += skip + 1; continue
                else:
                    text_lines.append(lines[i]); self._block_to_img[block_num] = current_img; block_num += 1
                i += 1
            clean_txt = "\n".join(text_lines); fs = self._editor.font().pointSize()
            html_parts = [f"<html><body style='background:transparent;color:#e3f7ff;"
                          f"font-family:Consolas,monospace;font-size:{fs}pt;'>"]
            for line in text_lines:
                s = line.strip()
                if s:
                    escaped = s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                    html_parts.append(f'<p style="margin:1px 0;">{escaped}</p>')
                else: html_parts.append('<p style="margin:3px 0;"> </p>')
            html_parts.append("</body></html>"); self._editor.setHtml("".join(html_parts))
            self._clean_txt = clean_txt
        else:
            self._block_to_img = {}; self._clean_txt = txt; self._editor.setPlainText(txt)
        self._editor.blockSignals(False)

    def _rebuild_html(self):
        if not hasattr(self, '_clean_txt') or not self._clean_txt: return
        fs = self._editor.font().pointSize()
        html_parts = [f"<html><body style='background:transparent;color:#e3f7ff;"
                      f"font-family:Consolas,monospace;font-size:{fs}pt;'>"]
        for line in self._clean_txt.split("\n"):
            s = line.strip()
            if s:
                escaped = s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
                html_parts.append(f'<p style="margin:1px 0;">{escaped}</p>')
            else: html_parts.append('<p style="margin:3px 0;"> </p>')
        html_parts.append("</body></html>")
        self._editor.blockSignals(True); self._editor.setHtml("".join(html_parts))
        self._editor.blockSignals(False)

    def set_text(self, text: str):
        self._display_formatted(text); self._history = [text]; self._redo_stack.clear()

    def get_text(self) -> str:
        if self._clean_txt: return self._clean_txt
        return self._editor.toPlainText()

    def apply_translation(self, translated: str):
        current = self._editor.toPlainText()
        if not self._history or self._history[-1] != current: self._history.append(current)
        self._redo_stack.clear(); self._editor.blockSignals(True)
        self._display_formatted(translated); self._editor.blockSignals(False)
        self._history.append(translated)


# ─── IMAGE COMPARATOR WIDGET ──────────────────────────────────────────────────
class ImageComparatorWidget(HudPanelFrame):
    navigate            = pyqtSignal(int)
    expansion_requested = pyqtSignal(bool)   # True=expandir, False=restaurar

    # Formatos de video reconocidos
    VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".m4v"}

    def __init__(self, parent=None):
        super().__init__(parent=parent, titulo="REFERENCIA", show_header=True)
        self.setContentsMargins(6, 36, 6, 6)
        self._current_img: Optional[Path] = None
        self._src_folder:  Optional[Path] = None
        self._highlight_rect = None
        self._hover_rect     = None
        self._pix_orig       = None
        # Video state
        self._vid_player: Optional[object] = None
        self._vid_widget: Optional[QWidget] = None
        self._vid_audio:  Optional[object] = None
        self._is_video   = False
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(6, 4, 6, 6); lay.setSpacing(3)
        hdr = QHBoxLayout()
        hdr.addStretch()
        self._name_lbl = QLabel("")
        self._name_lbl.setStyleSheet(f"color:{DM};font-size:10px;")
        hdr.addWidget(self._name_lbl)
        lay.addLayout(hdr)

        # ── Imagen estática ───────────────────────────────────────────────────
        self._scroll = QScrollArea(); self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._img_lbl = QLabel("← Anterior  |  Siguiente →\n\nSelecciona una imagen")
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._img_lbl.setStyleSheet(f"color:{DM}; font-size:11px;")
        self._img_lbl.setScaledContents(False)
        self._scroll.setWidget(self._img_lbl)
        lay.addWidget(self._scroll, 1)
        self._lay = lay

    def set_src_folder(self, folder: Path): self._src_folder = folder

    def _resolve_image_path(self, path: Path) -> Path:
        if self._src_folder and self._src_folder.is_dir():
            candidate = self._src_folder / path.name
            if candidate.exists(): return candidate
        return path

    # ── Video ─────────────────────────────────────────────────────────────────
    def _stop_video(self):
        if self._vid_player:
            try: self._vid_player.stop()
            except Exception: pass
        if self._vid_widget:
            self._vid_widget.hide()
            self._vid_widget.setParent(None)
            self._vid_widget = None
        self._vid_player = None
        self._vid_audio  = None
        self._is_video   = False
        self._scroll.show()

    def _play_video(self, path: Path):
        """Crea el player de video, detecta orientación y emite señal de expansión."""
        if not _HAS_MULTIMEDIA:
            self._img_lbl.setText(f"⚠ PyQt6-Qt6-Multimedia no instalado.\n{path.name}")
            return

        self._stop_video()
        self._is_video = True
        self._scroll.hide()

        from PyQt6.QtCore import QUrl
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        from PyQt6.QtMultimediaWidgets import QVideoWidget

        self._vid_widget = QVideoWidget(self)
        self._vid_widget.setStyleSheet("background:black;")
        self._lay.addWidget(self._vid_widget, 1)

        self._vid_audio = QAudioOutput()
        self._vid_audio.setVolume(0.8)

        self._vid_player = QMediaPlayer()
        self._vid_player.setAudioOutput(self._vid_audio)
        self._vid_player.setVideoOutput(self._vid_widget)

        # Detectar orientación cuando el video esté listo
        self._vid_player.videoOutputChanged.connect(lambda: None)   # init signal
        self._vid_player.metaDataChanged.connect(self._on_video_meta)

        # Loop
        self._vid_player.mediaStatusChanged.connect(
            lambda s: self._vid_player.play()
            if s == QMediaPlayer.MediaStatus.EndOfMedia else None)

        self._vid_player.setSource(QUrl.fromLocalFile(str(path)))
        self._vid_player.play()
        self._vid_widget.show()

    def _on_video_meta(self):
        """Detecta ancho/alto del video y decide si expandir."""
        if not self._vid_player: return
        try:
            meta = self._vid_player.metaData()
            res  = meta.value(meta.Key.Resolution) if hasattr(meta, 'Key') else None
            if res is None:
                # Fallback: usar tamaño del QVideoWidget después de un tick
                QTimer.singleShot(500, self._guess_orientation_from_widget)
                return
            w, h = res.width(), res.height()
            self._apply_orientation(w, h)
        except Exception:
            QTimer.singleShot(500, self._guess_orientation_from_widget)

    def _guess_orientation_from_widget(self):
        if self._vid_widget:
            vw = self._vid_widget.width()
            vh = self._vid_widget.height()
            self._apply_orientation(vw, vh)

    def _apply_orientation(self, vw: int, vh: int):
        if vw <= 0 or vh <= 0: return
        is_landscape = vw > vh
        self.expansion_requested.emit(is_landscape)
        if not is_landscape:
            # Portrait: ajustar ancho del widget al ratio del video
            ratio = vw / vh
            max_h = self.height() - 60
            target_w = int(max_h * ratio)
            if self._vid_widget:
                self._vid_widget.setMaximumWidth(max(200, target_w))

    # ── Imagen ────────────────────────────────────────────────────────────────
    def show_image(self, path: Path):
        if path.suffix.lower() in self.VIDEO_EXTS:
            self._name_lbl.setText(f"▶ {path.name}")
            self._play_video(path)
            return
        if self._is_video:
            self._stop_video()
            self.expansion_requested.emit(False)

        resolved = self._resolve_image_path(path)
        self._current_img = resolved
        self._name_lbl.setText(resolved.name)
        pix = QPixmap(str(resolved))
        if pix.isNull():
            pix = QPixmap(str(path))
            if pix.isNull():
                self._img_lbl.setText(f"No se pudo cargar:\n{path.name}")
                self._pix_orig = None; return
        self._pix_orig = pix
        self._render_image()
        QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(0))

    def _render_image(self):
        if self._pix_orig is None: return
        avail_w = self._scroll.viewport().width()
        if avail_w < 10: avail_w = self._scroll.width() - 10
        scaled = self._pix_orig.scaledToWidth(avail_w, Qt.TransformationMode.SmoothTransformation)
        self._img_lbl.setPixmap(scaled)
        self._img_lbl.setFixedSize(scaled.width(), scaled.height())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._pix_orig and not self._is_video: self._render_image()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and not self._is_video:
            self.navigate.emit(-1 if e.position().x() < self.width() / 2 else 1)
        super().mousePressEvent(e)


# ─── IMAGE BROWSER PANEL ──────────────────────────────────────────────────────
class ImageBrowserPanel(HudPanelFrame):
    image_selected = pyqtSignal(Path)

    def __init__(self, parent=None):
        super().__init__(parent=parent, titulo="IMÁGENES", show_header=True)
        self.setContentsMargins(6, 36, 6, 6)
        self._folders: List[Path] = []; self._all_images: List[Path] = []; self._current_idx = -1
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(6, 6, 6, 6); lay.setSpacing(4)
        hb = QHBoxLayout()
        lbl = QLabel("IMÁGENES"); lbl.setStyleSheet(f"color:{A};font-size:10px;font-weight:bold;letter-spacing:1px;")
        hb.addWidget(lbl); hb.addStretch()
        self._count_lbl = QLabel(""); self._count_lbl.setStyleSheet(f"color:{DM};font-size:9px;")
        hb.addWidget(self._count_lbl); lay.addLayout(hb)

        hint = QLabel("↑ Vinculado a la carpeta de Salida")
        hint.setStyleSheet(f"color:{DM};font-size:9px;font-style:italic;"); lay.addWidget(hint)

        self._tree = QTreeWidget(); self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(True); self._tree.setAnimated(True); self._tree.setIndentation(14)
        self._tree.setDragEnabled(True); self._tree.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._tree.setStyleSheet(f"QTreeWidget{{font-size:10px;border:1px solid {BD};}}"
                                  f"QTreeWidget::item{{padding:2px 3px;}}")
        self._tree.itemClicked.connect(self._on_item_click)
        self._tree.itemDoubleClicked.connect(self._on_item_double)
        self._tree.startDrag = self._start_drag; lay.addWidget(self._tree, 1)

        hint2 = QLabel("↕ arrastra carpetas a Carpetas Abiertas")
        hint2.setStyleSheet(f"color:{DM};font-size:9px;font-style:italic;"); lay.addWidget(hint2)

    def _start_drag(self, actions):
        from PyQt6.QtCore import QMimeData, QUrl
        from PyQt6.QtGui import QDrag
        folders = []
        for item in self._tree.selectedItems():
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if isinstance(data, Path) and data.is_dir(): folders.append(data)
            elif item.parent() is None:
                node_data = item.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(node_data, Path): folders.append(node_data)
        if not folders: return
        mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(f)) for f in folders])
        drag = QDrag(self._tree); drag.setMimeData(mime); drag.exec(actions)

    def load_output_folder(self, folder_path: str):
        p = Path(folder_path)
        if not p.is_dir(): return
        self._folders = []; self._all_images = []; self._current_idx = -1; self._tree.clear()
        all_dirs = [p] + sorted([d for d in p.iterdir() if d.is_dir()], key=_natural_key)
        for d in all_dirs:
            imgs = scan_images_in_folder(d)
            if imgs: self._folders.append(d); self._add_folder_node(d); self._all_images.extend(imgs)
        total = len(self._all_images)
        self._count_lbl.setText(f"{total} img" if total else "")

    def _add_folder_node(self, folder: Path):
        imgs = scan_images_in_folder(folder)
        node = QTreeWidgetItem(self._tree, [f"📁 {folder.name}  ({len(imgs)})"])
        node.setData(0, Qt.ItemDataRole.UserRole, folder); node.setToolTip(0, str(folder))
        if imgs:
            placeholder = QTreeWidgetItem(node, [""])
            placeholder.setData(0, Qt.ItemDataRole.UserRole, None)
        return node

    def _on_item_double(self, item: QTreeWidgetItem, col: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        # Si es imagen: abrir en visor del sistema
        if data and isinstance(data, Path) and data.is_file():
            import subprocess, sys
            try:
                if sys.platform == "win32":   subprocess.Popen(["explorer", str(data)])
                elif sys.platform == "darwin": subprocess.Popen(["open", str(data)])
                else:                          subprocess.Popen(["xdg-open", str(data)])
            except Exception: pass
            return
        # Si es carpeta: expandir/colapsar (comportamiento original)
        folder = data
        if not isinstance(folder, Path): return
        if item.childCount() == 1 and item.child(0).data(0, Qt.ItemDataRole.UserRole) is None:
            item.takeChild(0)
            for img in scan_images_in_folder(folder):
                child = QTreeWidgetItem(item, [img.name]); child.setData(0, Qt.ItemDataRole.UserRole, img)
        item.setExpanded(not item.isExpanded())

    def _on_item_click(self, item: QTreeWidgetItem, col: int):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and isinstance(data, Path) and data.is_file():
            self._current_idx = self._all_images.index(data) if data in self._all_images else -1
            self.image_selected.emit(data)

    def _rebuild_image_list(self):
        self._all_images = []
        for f in self._folders: self._all_images.extend(scan_images_in_folder(f))
        total = len(self._all_images)
        self._count_lbl.setText(f"{total} img" if total else "")

    def navigate(self, direction: int):
        if not self._all_images: return
        new_idx = max(0, min(len(self._all_images)-1, self._current_idx + direction))
        if new_idx != self._current_idx or self._current_idx == -1:
            self._current_idx = new_idx; path = self._all_images[new_idx]
            self.image_selected.emit(path); self._highlight_path(path)

    def _highlight_path(self, target: Path):
        def search(parent: QTreeWidgetItem) -> bool:
            for i in range(parent.childCount()):
                child = parent.child(i); d = child.data(0, Qt.ItemDataRole.UserRole)
                if d == target: self._tree.setCurrentItem(child); self._tree.scrollToItem(child); return True
                if search(child): return True
            return False
        for i in range(self._tree.topLevelItemCount()):
            if search(self._tree.topLevelItem(i)): break

    def show_by_name(self, img_name: str):
        if not img_name: return
        target: Optional[Path] = None; stem = Path(img_name).stem.lower()
        for path in self._all_images:
            if path.name.lower() == img_name.lower() or path.stem.lower() == stem:
                target = path; break
        if target is None: return
        try: self._current_idx = self._all_images.index(target)
        except ValueError: pass
        self._expand_and_select(target); self.image_selected.emit(target)

    def _expand_and_select(self, target: Path):
        for i in range(self._tree.topLevelItemCount()):
            node = self._tree.topLevelItem(i); folder = node.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(folder, Path) or target.parent != folder: continue
            if node.childCount() == 1 and node.child(0).data(0, Qt.ItemDataRole.UserRole) is None:
                node.takeChild(0)
                for img in scan_images_in_folder(folder):
                    child = QTreeWidgetItem(node, [img.name]); child.setData(0, Qt.ItemDataRole.UserRole, img)
            node.setExpanded(True)
            for j in range(node.childCount()):
                child = node.child(j)
                if child.data(0, Qt.ItemDataRole.UserRole) == target:
                    self._tree.setCurrentItem(child)
                    self._tree.scrollToItem(child, QAbstractItemView.ScrollHint.PositionAtCenter); return

    def set_folder(self, folder: Path):
        target = folder if folder.is_dir() else folder.parent
        if target not in self._folders:
            self._folders.append(target); node = self._add_folder_node(target)
            self._rebuild_image_list()
            if node.childCount() == 1 and node.child(0).data(0, Qt.ItemDataRole.UserRole) is None:
                node.takeChild(0)
                for img in scan_images_in_folder(target):
                    child = QTreeWidgetItem(node, [img.name]); child.setData(0, Qt.ItemDataRole.UserRole, img)
            node.setExpanded(True)


# ─── LOG PANEL ────────────────────────────────────────────────────────────────
class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(8, 6, 8, 6); lay.setSpacing(4)
        hb = QHBoxLayout()
        lbl = HudSectionLabel("LOG"); hb.addWidget(lbl); hb.addStretch()
        clr = QToolButton(); clr.setText("🗑"); clr.setToolTip("Limpiar")
        clr.setFixedSize(24, 22); clr.clicked.connect(self.clear); hb.addWidget(clr)
        lay.addLayout(hb)
        self._log = QTextEdit(); self._log.setReadOnly(True)
        self._log.setFont(QFont("Share Tech Mono, Consolas", 9))
        self._log.setStyleSheet(
            f"background:rgba(0,4,14,200); color:{C_GREEN}; "
            f"border:1px solid rgba(0,180,255,20); border-radius:3px;"
        )
        lay.addWidget(self._log)

    def add(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        self._log.append(f'<span style="color:{C_TX_DIM}">[{ts}]</span> {msg}')
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def clear(self): self._log.clear()


# ─── STATS PANEL ──────────────────────────────────────────────────────────────
class StatsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(8)
        lbl = HudSectionLabel("ESTADÍSTICAS"); lay.addWidget(lbl)
        self._stats = {
            "images":  self._row("🖼 Imágenes",  "0"),
            "chars":   self._row("📝 Caracteres", "0"),
            "words":   self._row("📖 Palabras",   "0"),
            "time":    self._row("⏱ Tiempo",      "0s"),
            "queue":   self._row("📋 Cola",        "0"),
        }
        for d in self._stats.values(): lay.addWidget(d["f"])
        lay.addStretch()

    def _row(self, label: str, value: str) -> Dict:
        f = QFrame(); f.setObjectName("panel")
        h = QHBoxLayout(f); h.setContentsMargins(8, 5, 8, 5)
        lbl = QLabel(label); val = QLabel(value)
        val.setStyleSheet(f"color:{CY};font-weight:bold;font-family:'Orbitron','Segoe UI',sans-serif;")
        h.addWidget(lbl); h.addStretch(); h.addWidget(val)
        return {"f": f, "val": val}

    def update_stats(self, data: Dict):
        for key, d in self._stats.items():
            if key in data: d["val"].setText(str(data[key]))


# ─── NATIVE WIN32 MULTI-FOLDER PICKER ─────────────────────────────────────────
class _FolderPickerThread(QThread):
    folders_ready = pyqtSignal(list)
    def run(self):
        import sys, ctypes, ctypes.wintypes
        results: List[str] = []
        if sys.platform != "win32": self.folders_ready.emit(results); return

        class GUID(ctypes.Structure):
            _fields_ = [("Data1",ctypes.c_ulong),("Data2",ctypes.c_ushort),
                        ("Data3",ctypes.c_ushort),("Data4",ctypes.c_ubyte*8)]
            def __init__(self,l,w1,w2,b=(0,)*8):
                super().__init__(l,w1,w2,(ctypes.c_ubyte*8)(*b))

        CLSID_FOD = GUID(0xDC1C5A9C,0xE88A,0x4DDE,(0xA5,0xA1,0x60,0xF8,0x2A,0x20,0xAE,0xF7))
        IID_FOD   = GUID(0xD57C7288,0xD4AD,0x4768,(0xBE,0x02,0x9D,0x96,0x95,0x32,0xD9,0x60))
        FOS_PICKFOLDERS=0x20; FOS_ALLOWMULTISELECT=0x200
        SIGDN_FILESYSPATH=ctypes.c_int(0x80058000).value; FT=ctypes.WINFUNCTYPE
        ole32=ctypes.WinDLL("ole32")
        if ole32.CoInitialize(None) not in (0,1): self.folders_ready.emit(results); return
        try:
            p_dlg=ctypes.c_void_p()
            if ole32.CoCreateInstance(ctypes.byref(CLSID_FOD),None,1,ctypes.byref(IID_FOD),ctypes.byref(p_dlg))!=0: return
            vt=ctypes.cast(ctypes.cast(p_dlg,ctypes.POINTER(ctypes.c_void_p))[0],ctypes.POINTER(ctypes.c_void_p))
            Release=FT(ctypes.HRESULT,ctypes.c_void_p)(vt[2])
            Show=FT(ctypes.HRESULT,ctypes.c_void_p,ctypes.wintypes.HWND)(vt[3])
            SetOptions=FT(ctypes.HRESULT,ctypes.c_void_p,ctypes.c_uint32)(vt[9])
            GetOptions=FT(ctypes.HRESULT,ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32))(vt[10])
            GetResults=FT(ctypes.HRESULT,ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p))(vt[27])
            opts=ctypes.c_uint32(0); GetOptions(p_dlg,ctypes.byref(opts))
            SetOptions(p_dlg,opts.value|FOS_PICKFOLDERS|FOS_ALLOWMULTISELECT)
            if Show(p_dlg,ctypes.wintypes.HWND(0))==0:
                p_arr=ctypes.c_void_p()
                if GetResults(p_dlg,ctypes.byref(p_arr))==0 and p_arr.value:
                    avt=ctypes.cast(ctypes.cast(p_arr,ctypes.POINTER(ctypes.c_void_p))[0],ctypes.POINTER(ctypes.c_void_p))
                    ReleaseArr=FT(ctypes.HRESULT,ctypes.c_void_p)(avt[2])
                    GetCount=FT(ctypes.HRESULT,ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32))(avt[7])
                    GetItemAt=FT(ctypes.HRESULT,ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_void_p))(avt[8])
                    cnt=ctypes.c_uint32(0); GetCount(p_arr,ctypes.byref(cnt))
                    for i in range(cnt.value):
                        p_item=ctypes.c_void_p()
                        if GetItemAt(p_arr,i,ctypes.byref(p_item))==0 and p_item.value:
                            ivt=ctypes.cast(ctypes.cast(p_item,ctypes.POINTER(ctypes.c_void_p))[0],ctypes.POINTER(ctypes.c_void_p))
                            ReleaseItem=FT(ctypes.HRESULT,ctypes.c_void_p)(ivt[2])
                            GetDisplayName=FT(ctypes.HRESULT,ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(ctypes.c_void_p))(ivt[5])
                            p_str=ctypes.c_void_p()
                            if GetDisplayName(p_item,SIGDN_FILESYSPATH,ctypes.byref(p_str))==0 and p_str.value:
                                path=ctypes.wstring_at(p_str.value)
                                if path: results.append(path)
                                ole32.CoTaskMemFree(p_str.value)
                            ReleaseItem(p_item)
                    ReleaseArr(p_arr)
            Release(p_dlg)
        except Exception: pass
        finally: ole32.CoUninitialize()
        self.folders_ready.emit(results)


class MultiFolderDialog(QDialog):
    def __init__(self, parent=None, already: List[str] = None):
        super().__init__(parent)
        self.setWindowTitle("Añadir carpetas a la cola OCR")
        self.setMinimumSize(500, 380); self.setStyleSheet(APP_QSS)
        self._folders: List[str] = list(already or []); self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(8); lay.setContentsMargins(16, 16, 16, 16)
        info = QLabel("📂  Pulsa <b>Añadir carpeta</b> para ir añadiendo carpetas una a una.<br>"
                      "Cuando hayas seleccionado todas, pulsa <b>Confirmar</b>.")
        info.setWordWrap(True); info.setStyleSheet(f"color:{TX};font-size:11px;"); lay.addWidget(info)
        self._list = QListWidget(); self._list.setStyleSheet(f"font-size:11px;")
        for f in self._folders:
            item = QListWidgetItem(f"📁  {Path(f).name}"); item.setToolTip(f); self._list.addItem(item)
        lay.addWidget(self._list, 1)
        self._count_lbl = QLabel(self._count_text()); self._count_lbl.setStyleSheet(f"color:{DM};font-size:10px;")
        lay.addWidget(self._count_lbl)
        mid = QHBoxLayout()
        add_btn = HudButton("📂  Añadir carpeta"); add_btn.clicked.connect(self._add)
        rem_btn = HudGhostButton("🗑  Quitar"); rem_btn.clicked.connect(self._remove)
        mid.addWidget(add_btn, 2); mid.addWidget(rem_btn, 1); lay.addLayout(mid)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("✓  Confirmar")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); lay.addWidget(bb)

    def _count_text(self):
        n = len(self._folders); return f"{n} carpeta{'s' if n != 1 else ''} en lista"

    def _add(self):
        n = len(self._folders) + 1; folder = QFileDialog.getExistingDirectory(self, f"Seleccionar carpeta {n}")
        if folder and folder not in self._folders:
            self._folders.append(folder); item = QListWidgetItem(f"📁  {Path(folder).name}")
            item.setToolTip(folder); self._list.addItem(item); self._count_lbl.setText(self._count_text())

    def _remove(self):
        row = self._list.currentRow()
        if 0 <= row < len(self._folders):
            self._folders.pop(row); self._list.takeItem(row); self._count_lbl.setText(self._count_text())

    def get_folders(self) -> List[str]: return list(self._folders)


class SubFolderTree(QTreeWidget):
    """
    Árbol de subcarpetas con imágenes expandibles inline.

    ─ Clic izquierdo en carpeta  → expande / colapsa
    ─ Clic izquierdo en imagen   → emite image_clicked (para el visor)
    ─ Clic derecho en cualquier  → selecciona / deselecciona el ítem
                                   (para usar con los botones de cola)
    """
    image_clicked = pyqtSignal(Path)

    # Tipos de ítem guardados en UserRole
    KIND_FOLDER = "folder"
    KIND_IMAGE  = "image"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        # Desactivar selección automática con clic izquierdo — la controlamos manualmente
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setIndentation(14)
        self.setStyleSheet(
            "QTreeWidget{font-size:10px;border:1px dashed rgba(0,180,255,30);"
            "background:transparent;}"
            "QTreeWidget::item{padding:2px 4px;}"
            "QTreeWidget::item:selected{background:rgba(0,180,255,50);"
            "color:#ffffff;}"
            "QTreeWidget::item:hover{background:rgba(0,180,255,15);}"
            "QTreeWidget::branch{background:transparent;}")
        # Re-habilitar multi-selección real (gestionada por nosotros vía clic derecho)
        self.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)

    # ── Helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _role(item):
        """Devuelve (kind, payload) o (None, None)."""
        d = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(d, tuple) and len(d) == 2:
            return d
        return None, None

    def selectedFolders(self) -> list:
        """Devuelve los paths (str) de carpetas marcadas con clic derecho."""
        result = []
        for item in self.selectedItems():
            kind, payload = self._role(item)
            if kind == SubFolderTree.KIND_FOLDER:
                result.append(payload)
        return result

    # ── Eventos de ratón ────────────────────────────────────────────────────
    def mousePressEvent(self, e: QMouseEvent):
        item = self.itemAt(e.pos())

        if e.button() == Qt.MouseButton.LeftButton:
            if item is None:
                super().mousePressEvent(e)
                return
            kind, payload = self._role(item)
            if kind == SubFolderTree.KIND_FOLDER:
                item.setExpanded(not item.isExpanded())
            elif kind == SubFolderTree.KIND_IMAGE:
                self.image_clicked.emit(payload)
            # NO llamar super() → evita que el clic izquierdo cambie la selección

        elif e.button() == Qt.MouseButton.RightButton:
            if item is None:
                return
            kind, payload = self._role(item)
            if kind == SubFolderTree.KIND_FOLDER:
                # Toggle selección del nodo carpeta
                item.setSelected(not item.isSelected())
            # Las imágenes no se seleccionan (solo sirven para el visor)

        else:
            super().mousePressEvent(e)


class DroppableListWidget(QListWidget):
    folders_dropped = pyqtSignal(list)
    def __init__(self, parent=None):
        super().__init__(parent); self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
        else: super().dragEnterEvent(e)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
        else: super().dragMoveEvent(e)

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            folders = [url.toLocalFile() for url in e.mimeData().urls() if Path(url.toLocalFile()).is_dir()]
            if folders: self.folders_dropped.emit(folders)
            e.acceptProposedAction()
        else: super().dropEvent(e)


class PastePathsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("Pegar rutas de carpetas")
        self.setMinimumSize(520, 300); self.setStyleSheet(APP_QSS); self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(8); lay.setContentsMargins(16, 16, 16, 16)
        info = QLabel("Pega las rutas de las carpetas (una por línea).<br>"
                      "<span style='color:#888'>Tip Windows: selecciona carpetas en el Explorador → "
                      "Shift+clic derecho → <b>Copiar como ruta de acceso</b></span>")
        info.setWordWrap(True); info.setStyleSheet(f"color:{TX};font-size:11px;"); lay.addWidget(info)
        self._text = QPlainTextEdit()
        self._text.setPlaceholderText('C:\\Manga\\Capitulo 8\nC:\\Manga\\Capitulo 9')
        self._text.setStyleSheet("font-size:11px;font-family:'Share Tech Mono','Consolas',monospace;")
        lay.addWidget(self._text, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("✓  Añadir rutas")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); lay.addWidget(bb)

    def get_folders(self) -> List[str]:
        folders = []
        for raw in self._text.toPlainText().splitlines():
            path = raw.strip().strip('"')
            if path and Path(path).is_dir(): folders.append(path)
        return folders


# ─── CONFIG PANEL ─────────────────────────────────────────────────────────────
class ConfigPanel(QWidget):
    ocr_folder_enqueued        = pyqtSignal(str)
    ocr_folders_changed        = pyqtSignal(list)
    out_folder_changed         = pyqtSignal(str)
    autounify_folder_requested = pyqtSignal(str)
    image_preview_requested    = pyqtSignal(Path)  # imagen → visor REFERENCIA
    ST_WAIT = "⏳"; ST_PROC = "⚙"; ST_DONE = "✓"; ST_ERR = "⚠"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cfg = load_cfg(); self._ocr_folders: List[str] = []; self._ocr_status: List[str] = []
        self._build()

    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner = QWidget()
        lay = QVBoxLayout(inner); lay.setContentsMargins(6, 6, 6, 6); lay.setSpacing(5)

        # ── OCR Engine section ────────────────────────────────────────────────
        sec_ocr = CollapsibleSection("OCR Engine", collapsed=False)
        self._paddle_panel = _PaddleOCRPanel(self._cfg)
        sec_ocr.add_widget(self._paddle_panel)
        self._ocr_lang = self._paddle_panel.lang_combo; self._fmt = self._paddle_panel.fmt_combo

        motor_row = QHBoxLayout(); motor_row.setSpacing(4)
        motor_lbl = QLabel("Motor:"); motor_lbl.setStyleSheet(_LBL_DIM); motor_row.addWidget(motor_lbl)
        self._motor_cb = QComboBox(); self._motor_cb.setStyleSheet(_COMBO_FUTURISTIC)
        self._motor_cb.addItems(["🚀 PaddleOCR", "🌐 OCR.space API"])
        self._motor_cb.currentIndexChanged.connect(self._on_motor_changed)
        motor_row.addWidget(self._motor_cb, 1); sec_ocr.add_layout(motor_row)

        self._space_frame = QFrame(); self._space_frame.setObjectName("panel")
        sf_lay = QVBoxLayout(self._space_frame); sf_lay.setContentsMargins(6, 6, 6, 6); sf_lay.setSpacing(4)
        self._space_key_label = QLabel("OCR.space API Key:"); self._space_key_label.setStyleSheet(_LBL_DIM)
        sf_lay.addWidget(self._space_key_label)
        key_row = QHBoxLayout()
        self._space_key_edit = QLineEdit(); self._space_key_edit.setPlaceholderText("Pega tu API key…")
        self._space_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._space_key_toggle = QToolButton(); self._space_key_toggle.setText("👁"); self._space_key_toggle.setFixedWidth(24)
        self._space_key_toggle.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self._space_key_edit); key_row.addWidget(self._space_key_toggle); sf_lay.addLayout(key_row)
        self._space_engine_combo = QComboBox(); self._space_engine_combo.setStyleSheet(_COMBO_FUTURISTIC)
        self._space_engine_combo.addItems(["Engine 1 — Rápido", "Engine 2 — Preciso"])
        self._space_engine_combo.setCurrentIndex(1); sf_lay.addWidget(self._space_engine_combo)
        self._space_frame.setVisible(False); sec_ocr.add_widget(self._space_frame)

        self._orient_cb = QComboBox()
        self._orient_cb.addItems(["Auto","Horiz. LTR","Horiz. RTL","Vert. LTR","Vert. RTL"])
        self._orient_cb.setCurrentIndex(1); self._orient_cb.setVisible(False)
        self._order_cb = QComboBox(); self._order_cb.addItems(["RTL","LTR"]); self._order_cb.setVisible(False)
        # sec_ocr oculto del panel derecho — accesible vía módulo CONFIGURACIÓN flotante
        # FIX BUG1: guardar referencia en self._sec_ocr para evitar que el GC destruya
        # sec_ocr (y con él _paddle_panel) al no tener ningún parent asignado.
        self._sec_ocr = sec_ocr
        lay.addWidget(sec_ocr)   # añadir al layout mantiene el parent y evita GC
        sec_ocr.setVisible(False)

        # AutoUnify movido al módulo AUTOUNIFY (panel izquierdo)

        # ── Carpetas OCR section ──────────────────────────────────────────────
        sec_folders = CollapsibleSection("Carpetas OCR", collapsed=False)

        # ── 1.1 Subcarpetas disponibles — árbol de imágenes integrado ────────
        # El panel IMÁGENES se fusionó aquí: muestra carpetas/imgs de la salida
        # y permite arrastrarlas a Cola OCR directamente desde el mismo apartado.
        sub_lbl = QLabel("Subcarpetas disponibles:")
        sub_lbl.setStyleSheet(f"font-size:9px;color:rgba(0,180,255,160);padding:2px 0;")
        sec_folders.add_widget(sub_lbl)

        # Header de conteo (antes era "IMÁGENES  732 img")
        _sub_hdr = QHBoxLayout()
        self._img_count_lbl = QLabel("")
        self._img_count_lbl.setStyleSheet(f"color:{DM};font-size:9px;")
        _sub_hdr.addStretch(); _sub_hdr.addWidget(self._img_count_lbl)
        sec_folders.add_layout(_sub_hdr)

        # ── Árbol expandible: carpetas + imágenes inline ──────────────────────
        # Clic izquierdo → expandir carpeta / ver imagen en visor
        # Clic derecho   → seleccionar carpeta para los botones de cola
        self._sub_list = SubFolderTree()
        self._sub_list.setMinimumHeight(120); self._sub_list.setMaximumHeight(280)
        self._sub_list.setToolTip(
            "🖱 Clic izquierdo en carpeta → expandir/colapsar\n"
            "🖼 Clic izquierdo en imagen  → ver en visor REFERENCIA\n"
            "📌 Clic derecho en carpeta   → seleccionar para cola")
        self._sub_list.image_clicked.connect(self.image_preview_requested)
        sec_folders.add_widget(self._sub_list)

        # ── Botones de acción sobre la selección de _sub_list ────────────────
        add_sel_btn = HudGhostButton("→ Agregar seleccionadas a cola OCR")
        add_sel_btn.setStyleSheet("font-size:9px;padding:3px 6px;")
        add_sel_btn.setToolTip("Clic derecho en carpetas para seleccionarlas, luego este botón")
        add_sel_btn.clicked.connect(self._add_selected_to_ocr)
        sec_folders.add_widget(add_sel_btn)

        au_btn = HudGhostButton("⛓ Agregar seleccionadas a AutoUnify")
        au_btn.setStyleSheet(
            "QPushButton{"
            "font-size:9px;padding:3px 6px;"
            "color:rgba(0,230,180,200);"
            "border:1px solid rgba(0,230,180,60);"
            "background:transparent;}"
            "QPushButton:hover{"
            "color:#ffffff;"
            "border-color:rgba(0,230,180,180);"
            "background:rgba(0,230,180,22);}"
            "QPushButton:pressed{"
            "background:rgba(0,230,180,40);}"
        )
        au_btn.setToolTip("Clic derecho en carpetas para seleccionarlas, luego este botón")
        au_btn.clicked.connect(self._add_selected_to_autounify)
        sec_folders.add_widget(au_btn)

        # ── Cola OCR (carpetas confirmadas) ───────────────────────────────────
        cola_lbl = QLabel("Cola OCR:")
        cola_lbl.setStyleSheet(f"font-size:9px;color:rgba(0,180,255,160);padding:2px 0;")
        sec_folders.add_widget(cola_lbl)

        self._ocr_list = DroppableListWidget()
        self._ocr_list.setMinimumHeight(60); self._ocr_list.setMaximumHeight(110)
        self._ocr_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._ocr_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._ocr_list.setStyleSheet(
            f"QListWidget{{font-size:10px;border:1px dashed rgba(0,180,255,40);}}"
            f"QListWidget::item{{padding:2px 4px;}}")
        self._ocr_list.setToolTip("Arrastra carpetas aquí o usa + Añadir")
        self._ocr_list.folders_dropped.connect(self._on_folders_dropped)
        sec_folders.add_widget(self._ocr_list)

        ocr_btns = QHBoxLayout(); ocr_btns.setSpacing(3)
        add_ocr = HudGhostButton("+ Añadir"); add_ocr.setToolTip("Añadir carpetas a la cola")
        add_ocr.clicked.connect(self._add_ocr_folders_dialogo)
        rem_ocr = HudGhostButton("– Quitar"); rem_ocr.clicked.connect(self._rem_ocr_folder)
        ocr_btns.addWidget(add_ocr, 1); ocr_btns.addWidget(rem_ocr, 1); sec_folders.add_layout(ocr_btns)

        paste_btn = HudGhostButton("⌨ Pegar rutas")
        paste_btn.setStyleSheet("font-size:9px;padding:2px 6px;")
        paste_btn.setToolTip("Shift+clic derecho en el Explorador → Copiar como ruta de acceso")
        paste_btn.clicked.connect(self._add_ocr_folders_pegar); sec_folders.add_widget(paste_btn)

        lay.addWidget(sec_folders)

        # ── Controles de procesamiento (viven en ConfigPanel, visibles en
        # el panel flotante CONFIGURACIÓN — no se añaden al layout visible) ──
        cfg0 = self._cfg
        self._maxh = QSpinBox(); self._maxh.setRange(500, 10000)
        self._maxh.setValue(cfg0.get("max_height", 3000))
        self._maxh.setSingleStep(500)
        self._autounify_cb = QCheckBox()
        self._autounify_cb.setChecked(bool(cfg0.get("use_autounify", True)))
        self._replace_cb = QCheckBox()
        self._replace_cb.setChecked(bool(cfg0.get("replace_originals", False)))

        # ── _out_lbl: QLineEdit oculto que almacena la carpeta de salida ──────
        # Se usa como stub para get_params() y _pick_out(); no se muestra en UI.
        self._out_lbl = QLineEdit()
        self._out_lbl.hide()
        self._out_lbl.setText(cfg0.get("out_folder", ""))

        lay.addStretch()

        scroll.setWidget(inner); outer.addWidget(scroll)

        cfg = load_cfg()
        saved_mode = cfg.get("ocr_mode", "classic"); mode_to_idx = {"classic": 0, "space": 1}
        self._motor_cb.setCurrentIndex(mode_to_idx.get(saved_mode, 0))
        self._on_motor_changed(self._motor_cb.currentIndex())
        self._load_cfg_to_ui()

    def _load_cfg_to_ui(self):
        cfg = self._cfg
        if self._paddle_panel is not None:
            if cfg.get("ocr_lang"):
                for i, (_, c) in enumerate(OCR_LANG_OPTIONS):
                    if c == cfg["ocr_lang"]: self._paddle_panel.lang_combo.setCurrentIndex(i); break
            if cfg.get("fmt"):
                idx = self._paddle_panel.fmt_combo.findText(cfg["fmt"])
                if idx >= 0: self._paddle_panel.fmt_combo.setCurrentIndex(idx)
            if "online_learning" in cfg: self._paddle_panel.online_check.setChecked(bool(cfg["online_learning"]))
            if "keep_sfx" in cfg: self._paddle_panel.sfx_check.setChecked(bool(cfg["keep_sfx"]))
            if "vertical_japanese" in cfg: self._paddle_panel.vertical_check.setChecked(bool(cfg["vertical_japanese"]))
            if cfg.get("reading_order"): self._paddle_panel.rtl_check.setChecked(cfg["reading_order"] == "rtl")
        if cfg.get("case_mode") and self._paddle_panel is not None and hasattr(self._paddle_panel, "case_combo"):
            for i, (_, c) in enumerate(TEXT_CASE_OPTIONS):
                if c == cfg.get("case_mode"): self._paddle_panel.case_combo.setCurrentIndex(i); break
        if cfg.get("out_folder"):
            if hasattr(self, '_out_lbl'): self._out_lbl.setText(cfg["out_folder"])
            QTimer.singleShot(0, lambda: self.out_folder_changed.emit(cfg["out_folder"]))
        if hasattr(self, "_orient_cb"):
            orient_map_inv = {"auto":0,"horizontal_ltr":1,"horizontal_rtl":2,"vertical_ltr":3,"vertical_rtl":4}
            self._orient_cb.setCurrentIndex(orient_map_inv.get(cfg.get("orientation","auto"),0))
        if hasattr(self, "_replace_cb"): self._replace_cb.setChecked(bool(cfg.get("replace_originals",False)))
        if hasattr(self, "_autounify_cb"): self._autounify_cb.setChecked(bool(cfg.get("use_autounify",True)))
        if cfg.get("space_api_key"): self._space_key_edit.setText(cfg["space_api_key"])
        if cfg.get("space_engine") is not None:
            engine_idx = int(cfg["space_engine"]) - 1
            if 0 <= engine_idx < self._space_engine_combo.count():
                self._space_engine_combo.setCurrentIndex(engine_idx)

    def _add_selected_to_ocr(self):
        """Agrega las carpetas seleccionadas (clic derecho) a la cola OCR."""
        for path in self._sub_list.selectedFolders():
            if path not in self._ocr_folders:
                self._ocr_folders.append(path)
                self._ocr_status.append(self.ST_WAIT)   # FIX: listas sincronizadas
                st_item = QListWidgetItem(f"⏳  {Path(path).name}")
                st_item.setData(Qt.ItemDataRole.UserRole, path)
                self._ocr_list.addItem(st_item)
                self.ocr_folder_enqueued.emit(path)
        self._sub_list.clearSelection()

    def _add_selected_to_autounify(self):
        """Agrega las carpetas seleccionadas (clic derecho) al panel AutoUnify."""
        for path in self._sub_list.selectedFolders():
            self.autounify_folder_requested.emit(path)
        self._sub_list.clearSelection()

    def populate_sub_folders(self, manga_path: str):
        """Llena SubFolderTree con las subcarpetas y sus imágenes."""
        self._sub_list.clear()
        p = Path(manga_path)
        total_imgs = 0
        for d in sorted(p.iterdir(), key=_natural_key):
            if not d.is_dir(): continue
            imgs = sorted([f for f in d.iterdir()
                           if f.suffix.lower() in SUPPORTED_IMG | SUPPORTED_GIF],
                          key=_natural_key)
            total_imgs += len(imgs)
            node = QTreeWidgetItem(self._sub_list)
            node.setText(0, f"📁  {d.name}  ({len(imgs)})")
            node.setData(0, Qt.ItemDataRole.UserRole,
                         (SubFolderTree.KIND_FOLDER, str(d)))
            node.setExpanded(False)
            for img in imgs:
                child = QTreeWidgetItem(node)
                child.setText(0, f"   🖼  {img.name}")
                child.setData(0, Qt.ItemDataRole.UserRole,
                              (SubFolderTree.KIND_IMAGE, img))
        if hasattr(self, "_img_count_lbl"):
            self._img_count_lbl.setText(f"{total_imgs} imágenes")

    def _add_ocr_folders_dialogo(self):
        import sys
        if sys.platform == "win32":
            self._picker = _FolderPickerThread()
            self._picker.folders_ready.connect(self._bulk_add_folders); self._picker.start()
        else:
            dlg = MultiFolderDialog(self, already=list(self._ocr_folders))
            if dlg.exec() == QDialog.DialogCode.Accepted: self._bulk_add_folders(dlg.get_folders())

    def _on_folders_dropped(self, folders: List[str]): self._bulk_add_folders(folders)

    def _add_ocr_folders_pegar(self):
        dlg = PastePathsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            folders = dlg.get_folders()
            if not folders:
                QMessageBox.warning(self, "Sin rutas válidas",
                    "No se encontraron carpetas válidas.\n"
                    "Asegúrate de pegar rutas completas (ej: C:\\Manga\\Cap1)."); return
            self._bulk_add_folders(folders)

    def _bulk_add_folders(self, folders: List[str]):
        added = 0
        for folder in folders:
            if folder not in self._ocr_folders:
                self._ocr_folders.append(folder); self._ocr_status.append(self.ST_WAIT)
                item = QListWidgetItem(f"{self.ST_WAIT} 📁 {Path(folder).name}")
                item.setToolTip(folder); self._ocr_list.addItem(item); self._ocr_list.scrollToBottom()
                self.ocr_folder_enqueued.emit(folder); added += 1
        if added: self.ocr_folders_changed.emit(list(self._ocr_folders))

    def _rem_ocr_folder(self):
        row = self._ocr_list.currentRow()
        if 0 <= row < len(self._ocr_folders):
            self._ocr_folders.pop(row); self._ocr_status.pop(row); self._ocr_list.takeItem(row)
            self.ocr_folders_changed.emit(list(self._ocr_folders))

    def set_ocr_status(self, folder: str, status: str):
        if folder in self._ocr_folders:
            idx = self._ocr_folders.index(folder); self._ocr_status[idx] = status
            item = self._ocr_list.item(idx)
            if item: item.setText(f"{status} 📁 {Path(folder).name}")

    def get_ocr_folders(self) -> List[str]: return list(self._ocr_folders)

    def _pick_out(self):
        f = QFileDialog.getExistingDirectory(self, "Carpeta de salida")
        if f:
            if hasattr(self, '_out_lbl'): self._out_lbl.setText(f)
            self.out_folder_changed.emit(f)

    def get_params(self) -> Dict:
        out = self._out_lbl.text().strip()
        ocr_lang        = self._paddle_panel.get_lang_code()
        fmt             = self._paddle_panel.get_fmt()
        case_mode       = self._paddle_panel.get_case_code()
        online_learning = self._paddle_panel.online_check.isChecked()
        keep_sfx        = self._paddle_panel.sfx_check.isChecked()
        crop_pipeline   = self._paddle_panel.get_crop_pipeline()
        reading_order   = "rtl" if self._paddle_panel.get_rtl() else "ltr"
        vertical_jp     = self._paddle_panel.get_vertical_japanese()
        params = {
            "src_folder": "", "out_folder": out, "ocr_lang": ocr_lang, "fmt": fmt,
            "case_mode": case_mode, "online_learning": online_learning, "keep_sfx": keep_sfx,
            "max_height": self._maxh.value(),
            "use_autounify": self._autounify_cb.isChecked() if hasattr(self,"_autounify_cb") else True,
            "save_remnant": True,
            "replace_originals": self._replace_cb.isChecked() if hasattr(self,"_replace_cb") else False,
            "ocr_mode": self.get_ocr_mode(), "reading_order": reading_order,
            "orientation": self.get_orientation(), "space_api_key": self._space_key_edit.text().strip(),
            "space_engine": self._space_engine_combo.currentIndex() + 1,
            "crop_pipeline": crop_pipeline, "vertical_japanese": vertical_jp,
        }
        cfg = load_cfg(); cfg.update({k: params[k] for k in [
            "ocr_lang","fmt","out_folder","ocr_mode","reading_order","orientation",
            "space_api_key","space_engine","replace_originals","use_autounify",
            "online_learning","keep_sfx","crop_pipeline","vertical_japanese"]}); save_cfg(cfg)
        return params

    def _on_motor_changed(self, idx: int): self._space_frame.setVisible(idx == 1)

    def _toggle_key_visibility(self):
        is_hidden = self._space_key_edit.echoMode() == QLineEdit.EchoMode.Password
        self._space_key_edit.setEchoMode(QLineEdit.EchoMode.Normal if is_hidden else QLineEdit.EchoMode.Password)

    def get_ocr_mode(self):
        return "space" if self._motor_cb.currentIndex() == 1 else "classic"

    def get_reading_order(self):
        return "rtl" if (self._paddle_panel and self._paddle_panel.get_rtl()) else "ltr"

    def get_orientation(self):
        orient_map = {0:"auto",1:"horizontal_ltr",2:"horizontal_rtl",3:"vertical_ltr",4:"vertical_rtl"}
        return orient_map.get(self._orient_cb.currentIndex(),"auto")

    def set_src_folder(self, folder: str): pass


# ─── USER PANEL ───────────────────────────────────────────────────────────────
class UserPanel(HudPanelFrame):
    logout_requested = pyqtSignal()

    def __init__(self, user_info: Dict, parent=None):
        super().__init__(parent=parent, show_header=False)
        self.setContentsMargins(8, 6, 8, 6)
        lay = QVBoxLayout(self); lay.setContentsMargins(8, 6, 8, 6); lay.setSpacing(4)
        info_row = QHBoxLayout(); info_row.setSpacing(8)
        av = QLabel("👤"); av.setStyleSheet("font-size:26px;"); av.setFixedSize(36, 36)
        av.setAlignment(Qt.AlignmentFlag.AlignCenter); info_row.addWidget(av)
        text_col = QVBoxLayout(); text_col.setSpacing(1)
        name_lbl = QLabel(user_info.get("name", "Usuario"))
        name_lbl.setStyleSheet(f"font-size:11px;font-weight:bold;color:{TX};"); name_lbl.setWordWrap(True)
        text_col.addWidget(name_lbl)
        email_lbl = QLabel(user_info.get("email", "—"))
        email_lbl.setStyleSheet(f"color:{DM};font-size:9px;"); email_lbl.setWordWrap(True)
        text_col.addWidget(email_lbl)
        role = user_info.get("role", "usuario")
        role_lbl = QLabel("★ Admin" if role == "admin" else "● Usuario")
        role_lbl.setStyleSheet(f"color:{A if role=='admin' else GR};font-size:9px;font-weight:bold;")
        text_col.addWidget(role_lbl); info_row.addLayout(text_col, 1); lay.addLayout(info_row)
        unlimited_lbl = QLabel("✓ OCR ilimitado y gratuito")
        unlimited_lbl.setStyleSheet(f"color:{GR};font-size:9px;font-weight:bold;text-align:center;")
        unlimited_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.addWidget(unlimited_lbl)

        kofi_btn = HudGhostButton("☕ Apoyar en Ko-fi")
        kofi_btn.setFixedHeight(24)
        kofi_btn.clicked.connect(self._open_donation); lay.addWidget(kofi_btn)

        logout = HudGhostButton("⇠ Cerrar sesión"); logout.setFixedHeight(24)
        logout.clicked.connect(self.logout_requested.emit); lay.addWidget(logout)

    def _open_donation(self):
        import webbrowser
        webbrowser.open("https://ko-fi.com/autoscribeapp")


# ─── API KEY STORE ────────────────────────────────────────────────────────────
class ApiKeyStore:
    _ENGINES = ("groq", "claude", "deepl")
    _PATH    = BASE / "keys" / "api_keys.json"

    def __init__(self):
        self._data:   Dict[str, List[Dict[str, str]]] = {e: [] for e in self._ENGINES}
        self._active: Dict[str, Optional[str]]        = {e: None for e in self._ENGINES}
        self._load()

    def _load(self):
        if self._PATH.exists():
            try:
                raw = json.loads(self._PATH.read_text(encoding="utf-8"))
                self._data = raw.get("keys", self._data); self._active = raw.get("active", self._active)
                for e in self._ENGINES: self._data.setdefault(e, []); self._active.setdefault(e, None)
            except Exception: pass

    def save(self):
        self._PATH.parent.mkdir(parents=True, exist_ok=True)
        self._PATH.write_text(json.dumps({"keys":self._data,"active":self._active},indent=2,ensure_ascii=False),encoding="utf-8")

    def get_entries(self, engine: str) -> List[Dict[str, str]]: return list(self._data.get(engine, []))

    def add(self, engine: str, label: str, key: str):
        entry = {"label": label.strip(), "key": key.strip()}
        self._data.setdefault(engine, []).append(entry)
        if self._active.get(engine) is None: self._active[engine] = key.strip()
        self.save()

    def remove(self, engine: str, key: str):
        self._data[engine] = [e for e in self._data[engine] if e["key"] != key]
        if self._active.get(engine) == key:
            entries = self._data[engine]; self._active[engine] = entries[0]["key"] if entries else None
        self.save()

    def set_active(self, engine: str, key: str): self._active[engine] = key; self.save()
    def get_active_key(self, engine: str) -> Optional[str]: return self._active.get(engine)
    def get_active_label(self, engine: str) -> str:
        key = self.get_active_key(engine)
        if not key: return "Sin API key"
        for e in self._data.get(engine, []):
            if e["key"] == key: return e["label"]
        return "Sin API key"


# ─── API MANAGER WINDOW ───────────────────────────────────────────────────────
_ENGINE_LABELS = {"groq": "Groq", "claude": "Claude (Anthropic)", "deepl": "DeepL"}

class ApiManagerWindow(QDialog):
    key_selected = pyqtSignal(str, str, str)

    def __init__(self, engine: str, store: ApiKeyStore, parent=None):
        super().__init__(parent, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self._engine = engine; self._store = store
        self.setWindowTitle(f"API Keys — {_ENGINE_LABELS.get(engine, engine)}")
        self.setMinimumWidth(430); self.setMaximumWidth(520); self.setStyleSheet(APP_QSS)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self._build(); self._refresh_list()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(16, 14, 16, 16); root.setSpacing(10)
        title = QLabel(f"🔑  {_ENGINE_LABELS.get(self._engine, self._engine)}")
        title.setStyleSheet(f"color:{CY};font-family:'Orbitron','Segoe UI',sans-serif;font-size:13px;font-weight:700;")
        root.addWidget(title); root.addWidget(self._sep("Keys guardadas"))
        self._list = QListWidget(); self._list.setFixedHeight(155)
        self._list.setToolTip("Haz clic en una key para activarla"); self._list.itemClicked.connect(self._on_item_clicked)
        root.addWidget(self._list)
        row_del = QHBoxLayout(); row_del.setSpacing(6)
        self._btn_del = HudDangerButton("🗑  Eliminar seleccionada"); self._btn_del.clicked.connect(self._delete_selected)
        row_del.addStretch(); row_del.addWidget(self._btn_del); root.addLayout(row_del)
        root.addWidget(self._sep("Agregar nueva API key"))
        lbl_name = QLabel("Nombre / etiqueta  (opcional):"); lbl_name.setStyleSheet(f"color:{DM};font-size:10px;")
        root.addWidget(lbl_name)
        self._inp_label = QLineEdit(); self._inp_label.setPlaceholderText("ej: Principal, Backup, Trabajo…")
        root.addWidget(self._inp_label)
        lbl_key = QLabel("API Key:"); lbl_key.setStyleSheet(f"color:{DM};font-size:10px;"); root.addWidget(lbl_key)
        key_row = QHBoxLayout(); key_row.setSpacing(6)
        self._inp_key = QLineEdit(); self._inp_key.setPlaceholderText("Pega aquí tu API key…")
        self._inp_key.setEchoMode(QLineEdit.EchoMode.Password); key_row.addWidget(self._inp_key, 1)
        self._btn_show = QPushButton("👁"); self._btn_show.setFixedWidth(34)
        self._btn_show.setCheckable(True); self._btn_show.setObjectName("ghost")
        self._btn_show.toggled.connect(lambda on: self._inp_key.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        key_row.addWidget(self._btn_show); root.addLayout(key_row)
        act_row = QHBoxLayout(); act_row.setSpacing(8)
        btn_cancel = HudGhostButton("Cancelar"); btn_cancel.clicked.connect(self._clear_form)
        btn_save = HudButton("✓  Guardar"); btn_save.clicked.connect(self._save_new)
        act_row.addStretch(); act_row.addWidget(btn_cancel); act_row.addWidget(btn_save); root.addLayout(act_row)
        root.addWidget(self._sep())
        self._lbl_active = QLabel(); self._lbl_active.setWordWrap(True)
        self._lbl_active.setStyleSheet(f"color:{DM};font-size:10px;"); root.addWidget(self._lbl_active)

    @staticmethod
    def _sep(text: str = "") -> QWidget:
        w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 4, 0, 0); h.setSpacing(6)
        if text:
            lbl = QLabel(text); lbl.setStyleSheet(f"color:{CY};font-size:10px;font-weight:600;")
            h.addWidget(lbl)
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"border:none;border-top:1px solid rgba(0,180,255,25);")
        h.addWidget(line, 1); return w

    def _refresh_list(self):
        self._list.clear(); active_key = self._store.get_active_key(self._engine)
        entries = self._store.get_entries(self._engine)
        if not entries:
            ph = QListWidgetItem("  Sin keys guardadas — agrega una abajo")
            ph.setFlags(Qt.ItemFlag.NoItemFlags); ph.setForeground(QColor(DM)); self._list.addItem(ph)
        else:
            for entry in entries:
                is_active = entry["key"] == active_key
                item = QListWidgetItem(f"{'▶  ' if is_active else '    '}{entry['label']}   {self._mask(entry['key'])}")
                item.setData(Qt.ItemDataRole.UserRole, entry)
                if is_active: item.setForeground(QColor(CY))
                self._list.addItem(item)
        self._update_active_label()

    @staticmethod
    def _mask(key: str) -> str:
        if len(key) <= 12: return "•" * len(key)
        return f"{key[:6]}{'•'*(len(key)-10)}{key[-4:]}"

    def _on_item_clicked(self, item: QListWidgetItem):
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not entry: return
        self._store.set_active(self._engine, entry["key"])
        self.key_selected.emit(self._engine, entry["key"], entry["label"]); self.close()

    def _delete_selected(self):
        item = self._list.currentItem()
        if not item: return
        entry = item.data(Qt.ItemDataRole.UserRole)
        if not entry: return
        if QMessageBox.question(self, "Eliminar key", f"¿Eliminar «{entry['label']}»?\nNo se puede deshacer.",
                                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self._store.remove(self._engine, entry["key"]); self._refresh_list()

    def _save_new(self):
        label = self._inp_label.text().strip(); key = self._inp_key.text().strip()
        if not key: self._inp_key.setPlaceholderText("⚠  Ingresa una API key primero"); return
        if not label: label = f"Key {len(self._store.get_entries(self._engine))+1}"
        self._store.add(self._engine, label, key); self._clear_form(); self._refresh_list()

    def _clear_form(self):
        self._inp_label.clear(); self._inp_key.clear()
        self._inp_key.setPlaceholderText("Pega aquí tu API key…")

    def _update_active_label(self):
        label = self._store.get_active_label(self._engine); key = self._store.get_active_key(self._engine)
        self._lbl_active.setText(f"Activa: {label}  ({self._mask(key)})" if key else "Sin key activa — agrega una arriba")


# ─── TRANSLATOR WIDGET ────────────────────────────────────────────────────────
class TranslatorWidget(QFrame):
    config_requested = pyqtSignal()  # emitida cuando el usuario pulsa ⚙ → ir a CONFIG

    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("panel")
        self._editor_ref: Optional[TextEditorWidget] = None
        self._translator = None; self._engine_id = "none"; self._cfg_expanded = False
        self._key_store = ApiKeyStore(); self._api_win = None; self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(5)
        hdr = QHBoxLayout()
        hdr.addStretch()
        self._cfg_btn = QToolButton(); self._cfg_btn.setText("⚙")
        self._cfg_btn.setToolTip("Configurar motor de traducción"); self._cfg_btn.setFixedSize(26, 24)
        self._cfg_btn.setStyleSheet(f"color:{DM};background:transparent;border:none;font-size:15px;")
        self._cfg_btn.clicked.connect(self._toggle_cfg); hdr.addWidget(self._cfg_btn); lay.addLayout(hdr)

        self._cfg_frame = QFrame(); self._cfg_frame.setObjectName("panel")
        cf = QVBoxLayout(self._cfg_frame); cf.setContentsMargins(6, 6, 6, 6); cf.setSpacing(4)
        mr = QHBoxLayout(); mr.setSpacing(4); mr.addWidget(QLabel("Motor:"))
        self._engine_cb = QComboBox(); self._engine_cb.setStyleSheet("font-size:10px;")
        self._engine_cb.addItems(["— Sin traductor —","🌐 DeepL API","🤖 Claude Sonnet","⚡ Groq (rápido · gratis)","💻 Offline"])
        self._engine_cb.currentIndexChanged.connect(self._on_engine_changed); mr.addWidget(self._engine_cb, 1); cf.addLayout(mr)
        self._key_lbl = QLabel("API Key:"); self._key_lbl.setStyleSheet(f"color:{DM};font-size:10px;"); cf.addWidget(self._key_lbl)
        key_row = QHBoxLayout(); key_row.setSpacing(4)
        self._key_edit = QLineEdit(); self._key_edit.setPlaceholderText("Pegar API key aquí…")
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password); self._key_edit.setStyleSheet("font-size:10px;")
        key_row.addWidget(self._key_edit, 1)
        self._key_mgr_btn = QToolButton(); self._key_mgr_btn.setText("🔑"); self._key_mgr_btn.setFixedSize(26, 24)
        self._key_mgr_btn.setToolTip("Gestionar API keys guardadas"); self._key_mgr_btn.clicked.connect(self._open_key_manager)
        key_row.addWidget(self._key_mgr_btn); cf.addLayout(key_row)
        self._connect_btn = HudGhostButton("✓ Aplicar configuración")
        self._connect_btn.setStyleSheet("font-size:10px;"); self._connect_btn.clicked.connect(self._apply_engine_cfg)
        cf.addWidget(self._connect_btn)
        self._status_lbl = QLabel("Sin motor seleccionado")
        self._status_lbl.setStyleSheet(f"color:{DM};font-size:9px;"); self._status_lbl.setWordWrap(True); cf.addWidget(self._status_lbl)
        self._cfg_frame.setVisible(False); lay.addWidget(self._cfg_frame)

        ct_row = QHBoxLayout(); ct_row.setSpacing(4); ct_row.addWidget(QLabel("Tipo:"))
        self._content_cb = QComboBox(); self._content_cb.setStyleSheet("font-size:10px;")
        self._content_cb.addItems(["Manga/Manhwa","Novela","Técnico"]); ct_row.addWidget(self._content_cb, 1); lay.addLayout(ct_row)

        prompt_hdr = QHBoxLayout()
        prompt_lbl = QLabel("PROMPT"); prompt_lbl.setStyleSheet(f"color:{DM};font-size:9px;font-weight:bold;letter-spacing:1px;")
        prompt_hdr.addWidget(prompt_lbl); prompt_hdr.addStretch()
        self._prompt_toggle = QToolButton(); self._prompt_toggle.setText("▸ Personalizar")
        self._prompt_toggle.setStyleSheet(f"color:{DM};background:transparent;border:none;font-size:9px;")
        self._prompt_toggle.clicked.connect(self._toggle_prompt_panel); prompt_hdr.addWidget(self._prompt_toggle)
        lay.addLayout(prompt_hdr)

        self._prompt_frame = QFrame(); self._prompt_frame.setObjectName("panel")
        self._prompt_frame.setVisible(False)
        pf = QVBoxLayout(self._prompt_frame); pf.setContentsMargins(6, 6, 6, 6); pf.setSpacing(4)
        pdesc = QLabel("System prompt enviado al modelo.\nUsa {lang} donde quieras el idioma destino.")
        pdesc.setStyleSheet(f"color:{DM};font-size:9px;"); pdesc.setWordWrap(True); pf.addWidget(pdesc)
        self._prompt_edit = QPlainTextEdit()
        self._prompt_edit.setStyleSheet(
            f"background:rgba(0,4,14,200);color:{TX};border:1px solid {BD};border-radius:3px;"
            "font-family:'Share Tech Mono','Consolas',monospace;font-size:9px;")
        self._prompt_edit.setMinimumHeight(80); self._prompt_edit.setMaximumHeight(120)
        self._prompt_edit.setPlaceholderText("Deja vacío para usar el prompt por defecto…")
        self._default_prompt_text = "You are a manga translator. Translate to {lang}. Output ONLY the translation."
        self._prompt_edit.setPlainText(self._default_prompt_text)
        self._prompt_edit.textChanged.connect(self._on_prompt_changed); pf.addWidget(self._prompt_edit)
        prompt_footer = QHBoxLayout()
        self._prompt_char_lbl = QLabel(f"{len(self._default_prompt_text)} chars")
        self._prompt_char_lbl.setStyleSheet(f"color:{DM};font-size:9px;"); prompt_footer.addWidget(self._prompt_char_lbl)
        prompt_footer.addStretch()
        reset_btn = HudGhostButton("↺ Default"); reset_btn.setStyleSheet("font-size:9px;padding:2px 6px;")
        reset_btn.clicked.connect(self._reset_prompt); prompt_footer.addWidget(reset_btn)
        clear_btn = HudGhostButton("✕ Vaciar"); clear_btn.setStyleSheet("font-size:9px;padding:2px 6px;")
        clear_btn.clicked.connect(lambda: self._prompt_edit.clear()); prompt_footer.addWidget(clear_btn)
        pf.addLayout(prompt_footer)
        pnote = QLabel("💡 Vacío = prompt automático por tipo.\nTexto = se usa exactamente.")
        pnote.setStyleSheet(f"color:{DM};font-size:8px;font-style:italic;"); pnote.setWordWrap(True); pf.addWidget(pnote)
        lay.addWidget(self._prompt_frame)

        dest_row = QHBoxLayout(); dest_row.setSpacing(4); dest_row.addWidget(QLabel("Destino:"))
        self._dest_lang = QComboBox(); self._dest_lang.setStyleSheet("font-size:10px;")
        for name, _ in DEST_LANGS: self._dest_lang.addItem(name)
        dest_row.addWidget(self._dest_lang, 1); lay.addLayout(dest_row)


        self._trans_btn = HudButton("▶  TRADUCIR"); self._trans_btn.setMinimumHeight(34)
        self._trans_btn.clicked.connect(self._do_translate); lay.addWidget(self._trans_btn)

        self._trans_prog = HudProgressBarWidget(); self._trans_prog.setValue(0); self._trans_prog.setVisible(False)
        lay.addWidget(self._trans_prog)
        self._trans_pct_lbl = QLabel("")
        self._trans_pct_lbl.setStyleSheet(f"color:{DM};font-size:9px;"); self._trans_pct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._trans_pct_lbl.setVisible(False); lay.addWidget(self._trans_pct_lbl)

        self._refresh_models(); self._on_engine_changed(0); self._load_translator_cfg()

    def _load_translator_cfg(self):
        cfg = load_cfg(); engine_map_rev = {"deepl":1,"claude":2,"groq":3,"offline":4}
        saved_engine = cfg.get("trans_engine","none"); idx = engine_map_rev.get(saved_engine, 0)
        if idx > 0: self._engine_cb.setCurrentIndex(idx); self._on_engine_changed(idx)
        saved_key = cfg.get("trans_api_key","")
        if saved_key: self._key_edit.setText(saved_key)
        saved_dest = cfg.get("trans_dest_lang","")
        if saved_dest:
            for i,(_, code) in enumerate(DEST_LANGS):
                if code == saved_dest: self._dest_lang.setCurrentIndex(i); break
        saved_ct = cfg.get("trans_content_type",0)
        if 0 <= int(saved_ct) < self._content_cb.count(): self._content_cb.setCurrentIndex(int(saved_ct))

    def _save_translator_cfg(self):
        cfg = load_cfg(); engine_map = {1:"deepl",2:"claude",3:"groq",4:"offline"}
        idx = self._engine_cb.currentIndex()
        cfg["trans_engine"] = engine_map.get(idx,"none")
        cfg["trans_api_key"] = self._key_edit.text().strip() if idx in (1,2,3) else ""
        cfg["trans_dest_lang"] = DEST_LANGS[self._dest_lang.currentIndex()][1]
        cfg["trans_content_type"] = self._content_cb.currentIndex(); save_cfg(cfg)

    def _toggle_cfg(self):
        # La rosca navega a la pestaña CONFIG (Biblioteca + Configurar Traductor)
        self.config_requested.emit()

    def _toggle_prompt_panel(self):
        visible = not self._prompt_frame.isVisible(); self._prompt_frame.setVisible(visible)
        self._prompt_toggle.setText("▾ Personalizar" if visible else "▸ Personalizar")

    def _on_prompt_changed(self):
        txt = self._prompt_edit.toPlainText(); self._prompt_char_lbl.setText(f"{len(txt)} chars")

    def _reset_prompt(self): self._prompt_edit.setPlainText(self._default_prompt_text)

    def _get_custom_prompt(self) -> str:
        txt = self._prompt_edit.toPlainText().strip()
        return "" if (not txt or txt == self._default_prompt_text.strip()) else txt

    def _on_engine_changed(self, idx: int):
        is_online = idx in (1, 2, 3)
        self._key_lbl.setVisible(is_online); self._key_edit.setVisible(is_online); self._key_mgr_btn.setVisible(is_online)
        if is_online:
            engine_map = {1:"deepl",2:"claude",3:"groq"}; engine = engine_map.get(idx,"")
            if engine: active = self._key_store.get_active_key(engine); self._key_edit.setText(active or "")
        else: self._key_edit.clear()

    def _open_key_manager(self):
        engine_map = {1:"deepl",2:"claude",3:"groq"}; idx = self._engine_cb.currentIndex()
        engine = engine_map.get(idx)
        if not engine: return
        self._api_win = ApiManagerWindow(engine, self._key_store, parent=self)
        self._api_win.key_selected.connect(self._on_key_selected); self._api_win.show()

    def _on_key_selected(self, engine: str, key: str, label: str):
        self._key_edit.setText(key); self._status_lbl.setText(f"🔑 {label} seleccionada — pulsa Aplicar")

    def _refresh_models(self): pass

    def _apply_engine_cfg(self):
        idx = self._engine_cb.currentIndex(); self._translator = None; self._engine_id = "none"
        engine_map = {1:"deepl",2:"claude",3:"groq",4:"offline"}; engine = engine_map.get(idx,"none")
        if engine == "none": self._status_lbl.setText("Sin motor — elige uno arriba"); return
        if engine in ("deepl","claude","groq"):
            if not ONLINE_OK: self._status_lbl.setText("✗ Translator_online.py no encontrado"); return
            key = self._key_edit.text().strip()
            if not key: key = self._key_store.get_active_key(engine) or ""
            if key: self._key_edit.setText(key)
            if not key:
                label = {"deepl":"DeepL","claude":"Anthropic (Claude)","groq":"Groq"}[engine]
                self._status_lbl.setText(f"✗ Ingresa la API Key de {label}"); return
            key_or_path = key
        else:
            if not OFFLINE_OK: self._status_lbl.setText("✗ Translator_offline.py no encontrado"); return
            key_or_path = ""
        self._status_lbl.setText("⏳ Verificando motor…"); self._connect_btn.setEnabled(False)
        self._load_worker = ModelLoadWorker(engine, key_or_path, 0)
        self._load_worker.finished.connect(self._on_model_loaded); self._load_worker.start()

    def _on_model_loaded(self, translator, msg: str):
        self._connect_btn.setEnabled(True); self._status_lbl.setText(msg)
        if translator is not None:
            self._translator = translator
            if hasattr(translator, 'engine_id'): self._engine_id = translator.engine_id
            self._save_translator_cfg()

    def _content_type(self) -> str: return ["manga","novel","technical"][self._content_cb.currentIndex()]

    def _on_font_changed(self, v: int):
        if self._editor_ref: self._editor_ref.set_font_size(v)

    def set_editor(self, e: TextEditorWidget): self._editor_ref = e

    def _translate_structured(self, text: str, target: str, progress_cb=None) -> str:
        if self._translator is None: raise RuntimeError("No hay motor de traducción configurado.")
        ct = self._content_type()
        if self._engine_id in ("deepl","claude","groq"):
            if _online_translate_structured: return _online_translate_structured(text, target, ct, self._translator)
        elif self._engine_id == "argos":
            if _offline_translate_structured:
                source_lang = getattr(self, '_ocr_source_lang', 'en')
                return _offline_translate_structured(text, target, source_lang, self._translator, progress_callback=progress_cb)
        import re as _re
        SEP = _re.compile(r'^─{10,}$'); IMG = _re.compile(r'.*\.(jpg|jpeg|png|bmp|webp|gif|tif)$', _re.IGNORECASE)
        result = []
        for line in text.split("\n"):
            s = line.strip()
            if not s or SEP.match(s) or IMG.match(s): result.append(line)
            else:
                try: result.append(self._translator.translate(s, target, ct))
                except Exception: result.append(line)
        return "\n".join(result)

    def _do_translate(self):
        if not self._editor_ref: return
        target = DEST_LANGS[self._dest_lang.currentIndex()][1]
        if not target: QMessageBox.information(self, "Traducir", "Selecciona idioma destino."); return
        if self._translator is None:
            QMessageBox.warning(self, "Sin motor", "Pulsa ⚙ → 'Aplicar configuración' primero."); return
        text = self._editor_ref.get_text()
        if not text.strip(): QMessageBox.information(self, "Traducir", "No hay texto para traducir."); return
        self._trans_btn.setEnabled(False); self._trans_btn.setText("⏳ Traduciendo…")
        self._trans_prog.setValue(1); self._trans_prog.setVisible(True)
        self._trans_pct_lbl.setText("Preparando traducción…"); self._trans_pct_lbl.setVisible(True)
        self._trans_worker = TranslationWorker(self, text, target)
        self._trans_worker.finished.connect(self._on_translation_done)
        self._trans_worker.error.connect(self._on_translation_error)
        self._trans_worker.progress.connect(self._on_trans_progress); self._trans_worker.start()

    def _on_trans_progress(self, pct: int):
        self._trans_prog.setValue(pct); self._trans_pct_lbl.setText(f"Traduciendo… {pct}%")

    def _on_translation_done(self, result: str):
        if self._editor_ref: self._editor_ref.apply_translation(result)
        self._trans_btn.setEnabled(True); self._trans_btn.setText("▶  TRADUCIR")
        self._trans_prog.setValue(100); self._trans_pct_lbl.setText("✓ Traducción completada")
        QTimer.singleShot(2000, self._hide_trans_progress)

    def _on_translation_error(self, err: str):
        QMessageBox.critical(self, "Error de traducción", err)
        self._trans_btn.setEnabled(True); self._trans_btn.setText("▶  TRADUCIR"); self._hide_trans_progress()

    def _hide_trans_progress(self):
        self._trans_prog.setValue(0); self._trans_prog.setVisible(False); self._trans_pct_lbl.setVisible(False)


class TranslatorBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("translatorbar")
        self._expanded = False; self._editor_ref: Optional[TextEditorWidget] = None; self._widget_ref = None
        main_lay = QVBoxLayout(self); main_lay.setContentsMargins(0, 0, 0, 0); main_lay.setSpacing(0)
        hdr = QFrame(); hdr.setObjectName("translatorbar")
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(12, 5, 12, 5)
        self._toggle_btn = QToolButton(); self._toggle_btn.setText("▸ TRADUCTOR")
        self._toggle_btn.setStyleSheet(f"color:{CY};font-weight:bold;font-size:11px;background:transparent;border:none;")
        self._toggle_btn.clicked.connect(self._toggle); hl.addWidget(self._toggle_btn); hl.addStretch()
        hl.addWidget(QLabel("Panel de traducción del documento activo")); main_lay.addWidget(hdr)
        self._content = QFrame(); self._content.setObjectName("translatorbar")
        cl = QHBoxLayout(self._content); cl.setContentsMargins(12, 6, 12, 6); cl.setSpacing(8)
        undo_btn = QToolButton(); undo_btn.setText("↩"); undo_btn.setToolTip("Deshacer"); undo_btn.clicked.connect(self._undo)
        redo_btn = QToolButton(); redo_btn.setText("↪"); redo_btn.setToolTip("Rehacer"); redo_btn.clicked.connect(self._redo)
        cl.addWidget(undo_btn); cl.addWidget(redo_btn)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine); sep.setStyleSheet(f"color:{BD};"); cl.addWidget(sep)
        self._trans_btn = HudButton("▶ Traducir"); self._trans_btn.setMinimumWidth(85)
        self._trans_btn.clicked.connect(self._do_translate); cl.addWidget(self._trans_btn)
        cl.addWidget(QLabel("Fuente:"))
        self._font_size = QSpinBox(); self._font_size.setRange(8, 48); self._font_size.setValue(12)
        self._font_size.setMaximumWidth(52); self._font_size.valueChanged.connect(self._apply_font)
        cl.addWidget(self._font_size); cl.addStretch(); cl.addWidget(QLabel("Destino:"))
        self._dest_lang = QComboBox()
        for name, _ in DEST_LANGS: self._dest_lang.addItem(name)
        self._dest_lang.setMinimumWidth(110); cl.addWidget(self._dest_lang)
        self._content.setVisible(False); main_lay.addWidget(self._content)

    def _toggle(self):
        self._expanded = not self._expanded; self._content.setVisible(self._expanded)
        self._toggle_btn.setText(("▾" if self._expanded else "▸") + " TRADUCTOR")

    def set_editor(self, e: TextEditorWidget): self._editor_ref = e
    def set_widget_ref(self, w): self._widget_ref = w
    def _undo(self):
        if self._editor_ref: self._editor_ref.undo()
    def _redo(self):
        if self._editor_ref: self._editor_ref.redo()
    def _apply_font(self, v: int):
        if self._editor_ref: self._editor_ref.set_font_size(v)

    def _do_translate(self):
        if not self._editor_ref: return
        target = DEST_LANGS[self._dest_lang.currentIndex()][1]
        if not target: QMessageBox.information(self, "Traducir", "Selecciona idioma destino."); return
        text = self._editor_ref.get_text()
        if not text.strip(): QMessageBox.information(self, "Traducir", "No hay texto para traducir."); return
        if self._widget_ref is not None and self._widget_ref._translator is not None:
            self._trans_btn.setEnabled(False); self._trans_btn.setText("⏳…")
            self._trans_worker = TranslationWorker(self._widget_ref, text, target)
            self._trans_worker.finished.connect(self._on_bar_translation_done)
            self._trans_worker.error.connect(self._on_bar_translation_error); self._trans_worker.start()
        else:
            QMessageBox.warning(self, "Sin motor", "Pulsa ⚙ en el panel TRADUCTOR (izquierda) → 'Aplicar configuración' primero.")

    def _on_bar_translation_done(self, result: str):
        if self._editor_ref: self._editor_ref.apply_translation(result)
        self._trans_btn.setEnabled(True); self._trans_btn.setText("▶ Traducir")

    def _on_bar_translation_error(self, err: str):
        QMessageBox.critical(self, "Error de traducción", err)
        self._trans_btn.setEnabled(True); self._trans_btn.setText("▶ Traducir")


# ─── BACKGROUND WIDGET ────────────────────────────────────────────────────────
class BackgroundWidget(QWidget):
    """
    Fondo animado de la ventana principal.
    Soporta: imágenes estáticas (todos los formatos Qt), GIF animados (QMovie),
    y video (QMediaPlayer si PyQt6-Multimedia está instalado).
    Rota automáticamente entre todos los archivos en fondos/.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)

        self._fondos   = scan_fondos()
        self._idx      = 0
        self._opacity  = 0.22          # ligeramente más visible

        # Estado de reproducción actual
        self._pix:   Optional[QPixmap] = None   # imagen estática
        self._movie: Optional[QMovie]  = None   # GIF animado

        # Video (opcional) — widget hijo transparente
        self._vid_widget = None
        self._vid_player = None
        self._vid_audio  = None

        # Imagen GIF: label invisible para recibir frames de QMovie
        self._gif_label = QLabel(self)
        self._gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gif_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._gif_label.hide()

        if self._fondos:
            self._load_current()

        # Rotación automática cada 15 s (sólo si hay varios fondos)
        self._rot_timer = QTimer(self)
        self._rot_timer.timeout.connect(self._next)
        if len(self._fondos) > 1:
            self._rot_timer.start(15000)

    # ── Carga ────────────────────────────────────────────────────────────────
    def _stop_current(self):
        """Detiene cualquier reproducción activa."""
        if self._movie:
            self._movie.stop(); self._movie = None
        if self._vid_player:
            try: self._vid_player.stop()
            except Exception: pass
        if self._vid_widget:
            self._vid_widget.hide()
        self._gif_label.hide()
        self._pix = None

    def _load_current(self):
        if not self._fondos: return
        self._stop_current()
        f = self._fondos[self._idx]
        ext = f.suffix.lower()

        if ext in SUPPORTED_GIF:
            self._load_gif(f)
        elif ext in SUPPORTED_VID:
            self._load_video(f)
        else:
            self._load_image(f)
        self.update()

    def _load_image(self, path: Path):
        pix = QPixmap(str(path))
        self._pix = pix if not pix.isNull() else None

    def _load_gif(self, path: Path):
        movie = QMovie(str(path))
        movie.setScaledSize(QSize(self.width() or 1920, self.height() or 1080))
        movie.frameChanged.connect(self._on_gif_frame)
        movie.start()
        self._movie = movie
        self._gif_label.setMovie(movie)
        self._gif_label.show()

    def _on_gif_frame(self):
        """Reescala el frame del GIF a la geometría actual."""
        if not self._movie: return
        frame = self._movie.currentPixmap()
        if not frame.isNull():
            self._gif_label.setPixmap(
                frame.scaled(self.size(),
                             Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                             Qt.TransformationMode.SmoothTransformation))
        self.update()

    def _load_video(self, path: Path):
        if not _HAS_MULTIMEDIA:
            # Fallback: mostrar primer frame como imagen estática
            self._load_image(path); return
        try:
            from PyQt6.QtCore import QUrl
            if self._vid_widget is None:
                from PyQt6.QtMultimediaWidgets import QVideoWidget
                self._vid_widget = QVideoWidget(self)
                self._vid_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                self._vid_widget.lower()
            if self._vid_player is None:
                self._vid_player = QMediaPlayer(self)
                self._vid_audio  = QAudioOutput(self)
                self._vid_audio.setVolume(0)           # fondo mudo
                self._vid_player.setAudioOutput(self._vid_audio)
                self._vid_player.setVideoOutput(self._vid_widget)
                # Loop infinito
                self._vid_player.mediaStatusChanged.connect(
                    lambda s: self._vid_player.play()
                    if s == QMediaPlayer.MediaStatus.EndOfMedia else None)
            self._vid_player.setSource(QUrl.fromLocalFile(str(path)))
            self._vid_widget.setGeometry(self.rect())
            self._vid_widget.show()
            self._vid_player.play()
        except Exception:
            self._load_image(path)

    # ── Rotación ─────────────────────────────────────────────────────────────
    def _next(self):
        if not self._fondos: return
        self._idx = (self._idx + 1) % len(self._fondos)
        self._load_current()

    def pause_rotation(self):  self._rot_timer.stop()
    def resume_rotation(self):
        if len(self._fondos) > 1: self._rot_timer.start(15000)

    # ── Layout ───────────────────────────────────────────────────────────────
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._gif_label.setGeometry(self.rect())
        if self._vid_widget:
            self._vid_widget.setGeometry(self.rect())
        if self._movie:
            self._movie.setScaledSize(self.size())

    # ── Pintura ──────────────────────────────────────────────────────────────
    def paintEvent(self, e):
        # GIF y video se renderizan en sus propios widgets — sólo imagen estática aquí
        if not self._pix: return
        p = QPainter(self)
        p.setOpacity(self._opacity)
        scaled = self._pix.scaled(self.size(),
                                   Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                   Qt.TransformationMode.SmoothTransformation)
        x = (self.width()  - scaled.width())  // 2
        y = (self.height() - scaled.height()) // 2
        p.drawPixmap(x, y, scaled)
        p.end()



# ─── MAIN WINDOW ─────────────────────────────────────────────────────────────

class HudTitleBar(QFrame):
    """Barra de título HUD personalizada: logo, título, controles propios."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hud_titlebar")
        self.setFixedHeight(32)
        self.setStyleSheet(
            "QFrame#hud_titlebar{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(0,8,24,245),stop:0.5 rgba(0,15,40,230),stop:1 rgba(0,8,24,245));"
            "border-bottom:1px solid rgba(0,180,255,60);}")
        self._drag_pos = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 6, 0)
        lay.setSpacing(6)

        # Logo + título (pasamos al parent para rellenar desde MainWindow)
        self._logo_lbl = QLabel()
        self._logo_lbl.setFixedSize(20, 20)
        lay.addWidget(self._logo_lbl)

        self._title_lbl = QLabel("AutoScribe  v1.0")
        self._title_lbl.setStyleSheet(
            "font-family:'Orbitron','Segoe UI',sans-serif;"
            "font-size:10px;font-weight:700;color:#00eaff;"
            "letter-spacing:1.5px;background:transparent;border:none;")
        lay.addWidget(self._title_lbl)

        self._edition_lbl = QLabel("— HELIX HUD Edition")
        self._edition_lbl.setStyleSheet(
            "font-family:'Rajdhani','Segoe UI',sans-serif;"
            "font-size:9px;color:rgba(0,180,255,140);background:transparent;border:none;")
        lay.addWidget(self._edition_lbl)
        lay.addStretch()

        # ── Botones de control futuristas ─────────────────────────────────
        _base = (
            "QPushButton{background:transparent;border:none;border-radius:9px;"
            "font-size:10px;font-weight:900;"
            "min-width:18px;max-width:18px;min-height:18px;max-height:18px;"
            "padding:0;margin:0;}")

        _base_icon = (
            "QPushButton{background:transparent;border:none;border-radius:3px;"
            "font-size:11px;font-weight:900;"
            "min-width:20px;max-width:20px;min-height:20px;max-height:20px;"
            "padding:0;margin:0;}")

        _btn_cy = "QPushButton{color:rgba(0,200,255,200);}"                    "QPushButton:hover{background:rgba(0,180,255,25);color:#00eaff;"                    "border:1px solid rgba(0,200,255,70);}"

        self._btn_hide = QPushButton("⊟")
        self._btn_hide.setStyleSheet(_base_icon + _btn_cy)
        self._btn_hide.setToolTip("Ocultar en bandeja")

        self._btn_min = QPushButton("─")
        self._btn_min.setStyleSheet(_base_icon + "QPushButton{color:rgba(0,200,255,200);font-size:9px;}"
                         "QPushButton:hover{background:rgba(0,180,255,25);color:#00eaff;"
                         "border:1px solid rgba(0,200,255,70);}")
        self._btn_min.setToolTip("Minimizar")

        self._btn_max = QPushButton("□")
        self._btn_max.setStyleSheet(_base_icon + "QPushButton{color:rgba(0,200,255,200);font-size:13px;}"
                         "QPushButton:hover{background:rgba(0,180,255,25);color:#00eaff;"
                         "border:1px solid rgba(0,200,255,70);}")
        self._btn_max.setToolTip("Maximizar / Restaurar")

        self._btn_close = QPushButton("✕")
        self._btn_close.setStyleSheet(_base_icon + _btn_cy)
        self._btn_close.setToolTip("Cerrar")

        # Separador visual antes de los botones
        # ── Botón ℹ Tutorial (siempre visible en title bar) ─────────────────
        self._btn_info = QPushButton("ℹ")
        self._btn_info.setStyleSheet(
            "QPushButton{background:transparent;border:none;border-radius:3px;"
            "font-size:12px;font-weight:900;"
            "min-width:20px;max-width:20px;min-height:20px;max-height:20px;"
            "padding:0;margin:0;color:rgba(0,200,255,180);}"
            "QPushButton:hover{background:rgba(0,180,255,25);color:#00eaff;"
            "border:1px solid rgba(0,200,255,70);}")
        self._btn_info.setToolTip("ℹ  Información / Tutorial")
        lay.addWidget(self._btn_info)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color:rgba(0,180,255,25);max-width:1px;margin:6px 4px;")
        lay.addWidget(sep)
        lay.addSpacing(2)
        for btn in [self._btn_hide, self._btn_min, self._btn_max, self._btn_close]:
            lay.addWidget(btn)
        lay.addSpacing(2)

    def set_logo(self, pixmap):
        if not pixmap.isNull():
            self._logo_lbl.setPixmap(
                pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.window().frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.window().move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, e):
        w = self.window()
        if w.isMaximized():
            w.showNormal()
        else:
            w.showMaximized()

class MainWindow(QMainWindow):
    def __init__(self, user_info: Dict):
        super().__init__()
        self._user_info = user_info; self._cfg = load_cfg()
        self._ocr_worker = None; self._unify_worker = None
        self._proc_snapshot = None; self._pending_params: Optional[Dict] = None
        self._proc_start_time = 0.0; self._bubble: Optional[BubbleWidget] = None
        self._folder_queue: List[Dict] = []; self._queue_idx = -1; self._queue_running = False
        self._unify_queue: List[str] = []; self._unify_queue_idx = -1; self._unify_queue_running = False

        self.setWindowTitle("AutoScribe v1.0 — HELIX HUD Edition")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._set_icon(); self.setMinimumSize(1200, 700); self.resize(1400, 820)
        # Centrar en pantalla
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.move(sg.center() - self.rect().center())
        self._build_ui()
        # ── HudToastManager: notificaciones flotantes ────────────────────────
        self._toast = HudToastManager(self)
        self._apply_saved_cfg()
        # ── Tutorial overlay ─────────────────────────────────────────────────
        self._tutorial = TutorialPanel(self.centralWidget())
        self._tutorial.setGeometry(self.centralWidget().rect())
        self._tutorial.closed.connect(self._on_tutorial_closed)
        self._tutorial.hide()
        # Arrancar en CONFIG para que el usuario elija manga primero
        QTimer.singleShot(0, lambda: self._tab_switcher._sel(1))
        # Mostrar tutorial en primera ejecución
        QTimer.singleShot(250, self._maybe_show_tutorial)

    # ── Tutorial ─────────────────────────────────────────────────────────────
    _SETTINGS_KEY_TUTORIAL = "autoscribe/tutorial_shown_v2"

    def _maybe_show_tutorial(self):
        """Muestra el tutorial si es la primera vez que se ejecuta la app."""
        settings = QSettings("AutoScribe", "AutoScribe")
        if not settings.value(self._SETTINGS_KEY_TUTORIAL, False, type=bool):
            self._show_tutorial()

    def _show_tutorial(self):
        """Muestra el overlay tutorial desde el paso 0."""
        if hasattr(self, "_tutorial"):
            cw = self.centralWidget()
            self._tutorial.setGeometry(0, 0, cw.width(), cw.height())
            self._tutorial.show_from_start()
            self._tutorial.raise_()

    def _on_tutorial_closed(self):
        """Marca el tutorial como visto y guarda en QSettings."""
        settings = QSettings("AutoScribe", "AutoScribe")
        settings.setValue(self._SETTINGS_KEY_TUTORIAL, True)

    def _set_icon(self):
        if Path(LOGO_ICO).exists(): self.setWindowIcon(QIcon(LOGO_ICO))
        elif Path(LOGO_PNG).exists(): self.setWindowIcon(QIcon(LOGO_PNG))

    def _build_ui(self):
        central = QWidget(self); self.setCentralWidget(central)
        central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        central.setAutoFillBackground(False)
        central.setStyleSheet("background: transparent;")
        self._bg = BackgroundWidget(central)
        self._bg.setGeometry(0, 0, 9999, 9999); self._bg.lower()

        root = QVBoxLayout(central); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        # ══ CUSTOM TITLE BAR (frameless) ════════════════════════════════════
        self._title_bar = HudTitleBar()
        pix_logo = QPixmap(LOGO_PNG)
        self._title_bar.set_logo(pix_logo)
        self._title_bar._btn_min.clicked.connect(self.showMinimized)
        self._title_bar._btn_max.clicked.connect(
            lambda: self.showNormal() if self.isMaximized() else self.showMaximized())
        self._title_bar._btn_close.clicked.connect(self.close)
        self._title_bar._btn_info.clicked.connect(self._show_tutorial)
        self._title_bar._btn_hide.clicked.connect(self._go_bubble)
        root.addWidget(self._title_bar)

        # ══ HEADER HUD (status, EKG, motor, latencia, reloj) ══════════════
        hdr = HudHeaderBar()
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(8, 0, 8, 0); hl.setSpacing(6)

        # Dejar espacio para el ring animado del HudHeaderBar (cx+r ≈ 36px desde borde)
        hl.addSpacing(36)

        # STATUS separado del EKG: label "STATUS:" fijo + valor pulsante
        status_prefix = QLabel("STATUS:")
        status_prefix.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:rgba(0,180,255,120);background:transparent;border:none;")
        self._status_mode_lbl = QLabel("IDLE")
        self._status_mode_lbl.setStyleSheet(
            f"font-family:'Orbitron','Segoe UI',sans-serif;"
            f"font-size:9px;font-weight:700;color:{CY};letter-spacing:1px;"
            f"background:transparent;border:none;")
        hl.addWidget(status_prefix)
        hl.addWidget(self._status_mode_lbl)

        # Separador visual entre STATUS y EKG
        sep_v = QFrame(); sep_v.setFrameShape(QFrame.Shape.VLine)
        sep_v.setStyleSheet("color:rgba(0,180,255,35);max-width:1px;margin:8px 6px;")
        hl.addWidget(sep_v)

        # EKG — solo muestra la línea animada (STATUS ya está arriba)
        self._ekg = HudEkgWidget()
        self._ekg.setFixedSize(160, 46)
        hl.addWidget(self._ekg)

        # Motor activo — extremo DERECHO del header (stretch lo empuja al final)
        hl.addStretch()
        sep_m = QFrame(); sep_m.setFrameShape(QFrame.Shape.VLine)
        sep_m.setStyleSheet("color:rgba(0,180,255,35);max-width:1px;margin:8px 4px;")
        hl.addWidget(sep_m)
        hl.addSpacing(6)
        motor_lbl = QLabel("MOTOR:")
        motor_lbl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:8px;color:rgba(0,180,255,100);")
        self._motor_hdr_lbl = QLabel("✓ PaddleOCR")
        self._motor_hdr_lbl.setStyleSheet(
            f"font-family:'Rajdhani','Segoe UI',sans-serif;"
            f"font-size:10px;font-weight:700;color:{CY};")
        hl.addWidget(motor_lbl); hl.addWidget(self._motor_hdr_lbl)
        hl.addSpacing(10)  # margen en el borde derecho


        # Stub silenciosos para compatibilidad con código que actualiza estos labels
        for attr in ("_hdr_imgs", "_hdr_chars", "_hdr_words", "_hdr_queue"):
            lbl = QLabel(""); lbl.hide(); setattr(self, attr, lbl)

        # ══ MID ROW: header (solo izquierda) + columna derecha desde arriba ═══
        mid_row = QHBoxLayout(); mid_row.setContentsMargins(0, 0, 0, 0); mid_row.setSpacing(0)

        # Lado izquierdo: header + body apilados verticalmente
        left_side = QVBoxLayout(); left_side.setContentsMargins(0, 0, 0, 0); left_side.setSpacing(0)
        left_side.addWidget(hdr)

        # ══ BODY (solo paneles izquierdo y central) ══════════════════════════
        body = QHBoxLayout(); body.setContentsMargins(8, 0, 8, 4); body.setSpacing(8)

        # ── PANEL IZQUIERDO ──────────────────────────────────────────────────
        left_scroll = QScrollArea(); left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        left_scroll.setMinimumWidth(185); left_scroll.setMaximumWidth(220)
        left_inner = QWidget()
        ll = QVBoxLayout(left_inner); ll.setContentsMargins(0, 0, 0, 0); ll.setSpacing(5)

        # Archivos de texto (OutputDocPanel)
        self.output_docs = OutputDocPanel()
        self.output_docs.file_selected.connect(self._open_doc)
        self.output_docs.start_requested.connect(self._on_start)
        self.output_docs.cancel_requested.connect(self._on_cancel)
        ll.addWidget(self.output_docs, 3)

        # ── MÓDULOS (punto 1 + 7) — expandibles con exclusividad ─────────────
        mod_hdr_frame = QFrame(); mod_hdr_frame.setObjectName("sectionHeader"); mod_hdr_frame.setFixedHeight(26)
        mod_h = QHBoxLayout(mod_hdr_frame); mod_h.setContentsMargins(8, 0, 8, 0)
        mod_icon = QLabel("◈"); mod_icon.setStyleSheet(f"color:{CY};font-size:10px;")
        mod_title = QLabel("MÓDULOS"); mod_title.setStyleSheet(
            f"font-family:'Orbitron','Segoe UI',sans-serif;font-size:9px;"
            f"font-weight:700;letter-spacing:1.5px;color:{CY};")
        mod_h.addWidget(mod_icon); mod_h.addWidget(mod_title); mod_h.addStretch()
        ll.addWidget(mod_hdr_frame)

        self._modules = ModulesSection()

        # Sub-widget de AutoUnify (FolderQueuePanel + ImageBrowserPanel juntos)
        self.folder_queue_panel = FolderQueuePanel()
        self.folder_queue_panel.unify_folders_run.connect(self._do_unify_queue)

        # ImageBrowserPanel vive dentro del módulo AUTOUNIFY (cola OCR + imágenes)
        # Las conexiones con img_comparator y text_editor se hacen en la sección
        # "Conexiones adicionales" más abajo, cuando ambos widgets ya existen.
        self.img_browser = ImageBrowserPanel()

        # El _autounify_container es un placeholder 0-altura;
        # folder_queue_panel se reparenta al panel flotante al abrir el módulo.
        _autounify_placeholder = QWidget(); _autounify_placeholder.setFixedHeight(0)
        self._modules.add_module("⛓", "AUTOUNIFY", _autounify_placeholder, exclusive=True)

        # TranslatorWidget existe como standalone (se reparenta al panel flotante)
        self.translator_widget = TranslatorWidget()
        _traductor_placeholder = QWidget(); _traductor_placeholder.setFixedHeight(0)
        self._modules.add_module("⚙", "TRADUCTOR", _traductor_placeholder)

        # Sub-widget de Configuración — abre/cierra el ConfigPanel del panel derecho
        _cfg_shortcut = QWidget()
        _cfg_shortcut.setFixedHeight(0)  # no ocupa espacio en el módulo
        self._modules.add_module("⚙", "MOTOR OCR", _cfg_shortcut)
        # Conectar toggle del módulo al panel derecho
        # La conexión se hace después de crear _config_scroll (más abajo en _build_ui)
        self._pending_cfg_module_connect = True

        ll.addWidget(self._modules)

        # ── SISTEMA (punto 2) — monitor en tiempo real ───────────────────────
        self._sys_monitor = HudSystemMonitor()
        ll.addWidget(self._sys_monitor)

        ll.addStretch()
        left_scroll.setWidget(left_inner); body.addWidget(left_scroll)

        # ── PANEL CENTRAL ────────────────────────────────────────────────────
        center_frame = QWidget()   # contenedor neutro — los paneles hijos tienen sus propias luces
        center_frame.setContentsMargins(0, 0, 0, 0)
        cl = QVBoxLayout(center_frame); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(4)

        # ── Solo el TabSwitcher (EDITOR/CONFIG + latencia + POWER) ────────
        self._tab_switcher = HudTabSwitcher()
        self._tab_switcher.on_tab_changed(self._on_view_switched)
        cl.addWidget(self._tab_switcher)

        # Inicializar referencias de stats (usadas internamente, no visibles)
        self._stat_imgs  = None
        self._stat_chars = None
        self._stat_words = None
        self._stat_queue = None
        self._status_lbl = QLabel()  # oculto, solo para compatibilidad interna

        # ── QStackedWidget: EDITOR (idx=0) / CONFIG (idx=1) ──────────────────
        self._center_stack = QStackedWidget()

        # ·· PÁGINA EDITOR ··
        editor_page = QWidget()
        ep_lay = QVBoxLayout(editor_page); ep_lay.setContentsMargins(0, 0, 0, 0); ep_lay.setSpacing(3)

        self.text_editor = TextEditorWidget()
        self.img_comparator = ImageComparatorWidget()
        self.img_comparator.navigate.connect(self.img_browser_panel_navigate)

        self._editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._editor_splitter.setChildrenCollapsible(True)
        self._editor_splitter.addWidget(self.text_editor)
        self._editor_splitter.addWidget(self.img_comparator)
        self._editor_splitter.setSizes([500, 500]); self._editor_splitter.setHandleWidth(4)
        self._editor_splitter_normal = [500, 500]   # tamaños normales guardados
        ep_lay.addWidget(self._editor_splitter, 1)

        # Expansión de REFERENCIA cuando hay video landscape
        self.img_comparator.expansion_requested.connect(self._on_ref_expansion)

        # HudWordCounter (punto 12) — contador + estado guardado
        self._word_counter = HudWordCounter(self.text_editor._editor)
        self.text_editor.save_completed.connect(self._word_counter.mark_saved)
        ep_lay.addWidget(self._word_counter)

        self._center_stack.addWidget(editor_page)  # índice 0 = EDITOR

        # ·· PÁGINA CONFIG ··
        config_center_page = QWidget()
        cc_lay = QVBoxLayout(config_center_page)
        cc_lay.setContentsMargins(4, 2, 4, 4)
        cc_lay.setSpacing(3)

        # Título — barra delgada de solo 22px
        cfg_title = QLabel("⚙  CONFIGURACIÓN GENERAL")
        cfg_title.setFixedHeight(22)
        cfg_title.setStyleSheet(
            f"font-family:'Orbitron','Segoe UI',sans-serif;"
            f"font-size:9px;font-weight:700;color:{CY};"
            f"letter-spacing:2px;"
            f"border-bottom:1px solid rgba(0,180,255,50);"
            f"padding:0px 4px 2px 4px;background:transparent;")
        cc_lay.addWidget(cfg_title)

        # CONFIG page: manga library | config del traductor (splitter horizontal)
        self._manga_library = HudMangaLibraryPanel()
        self._manga_library.manga_selected.connect(self._on_manga_selected)

        # Panel derecho de CONFIG: SOLO config de motor/API (punto 5)
        # El panel de traducción completo (5.1) vive solo en el módulo TRADUCTOR flotante.
        _cfg_right = HudPanelFrame(titulo="CONFIGURACIÓN GENERAL", show_header=True)
        _cfg_right.setContentsMargins(0, 32, 0, 0)
        _cfg_right.setMinimumWidth(220)
        _cfg_right.setMaximumWidth(320)
        _cfg_right_lay = QVBoxLayout(_cfg_right)
        _cfg_right_lay.setContentsMargins(0, 0, 0, 0)
        _cfg_right_lay.setSpacing(0)

        # Header provisto por HudPanelFrame arriba

        # Mini panel punto 5: reparentar _cfg_frame del TranslatorWidget aquí
        # (Motor, API Key, Aplicar, Status) — siempre visible y expandido
        _cfg_frame = self.translator_widget._cfg_frame
        _cfg_frame.setParent(_cfg_right)
        _cfg_frame.setVisible(True)   # siempre visible aquí (no toggle)

        _tr_mini = QWidget()
        _tr_mini_lay = QVBoxLayout(_tr_mini)
        _tr_mini_lay.setContentsMargins(6, 6, 6, 6); _tr_mini_lay.setSpacing(4)
        _tr_mini_lay.addWidget(_cfg_frame)
        _tr_mini_lay.addStretch()
        _tr_hint = QLabel("▸ Módulo TRADUCTOR → Tipo, Prompt, TRADUCIR")
        _tr_hint.setStyleSheet(f"font-size:8px;color:{DM};font-style:italic;padding:2px 4px;")
        _tr_mini_lay.addWidget(_tr_hint)

        # ── Botón Tutorial ───────────────────────────────────────────────────
        _tut_btn = HudGhostButton("ℹ  Información / Tutorial")
        _tut_btn.setFixedHeight(26)
        _tut_btn.clicked.connect(self._show_tutorial)
        _tr_mini_lay.addWidget(_tut_btn)

        _kofi_btn = HudGhostButton("☕  Apoyar en Ko-fi")
        _kofi_btn.setFixedHeight(26)
        _kofi_btn.clicked.connect(lambda: __import__("webbrowser").open("https://ko-fi.com/autoscribeapp"))
        _tr_mini_lay.addWidget(_kofi_btn)
        _cfg_right_lay.addWidget(_tr_mini, 1)

        # Splitter manga_library | translator config
        _cfg_splitter = QSplitter(Qt.Orientation.Horizontal)
        _cfg_splitter.setHandleWidth(3)
        _cfg_splitter.addWidget(self._manga_library)
        _cfg_splitter.addWidget(_cfg_right)
        _cfg_splitter.setSizes([700, 280])

        cc_lay.addWidget(_cfg_splitter, 1)
        # ── Botón Información / Tutorial en página CONFIG ───────────────
        _info_sep = QFrame(); _info_sep.setFrameShape(QFrame.Shape.HLine)
        _info_sep.setStyleSheet("color:rgba(0,180,255,25);margin:4px 0;")
        config_center_page.layout().addWidget(_info_sep)
        _info_btn = HudGhostButton("ℹ  Información / Tutorial")
        _info_btn.setToolTip("Ver el tutorial de AutoScribe desde el principio")
        _info_btn.setStyleSheet(_info_btn.styleSheet() + "font-size:9px;letter-spacing:0.5px;")
        _info_btn.clicked.connect(self._show_tutorial)
        config_center_page.layout().addWidget(_info_btn)

        self._center_stack.addWidget(config_center_page)  # índice 1 = CONFIG

        cl.addWidget(self._center_stack, 1)

        # ── PANELES INFERIORES (punto 3) ──────────────────────────────────────
        bottom_row = QHBoxLayout(); bottom_row.setSpacing(6); bottom_row.setContentsMargins(0, 2, 0, 0)

        # Consola del sistema
        self.log_panel = HudConsolePanel()
        self.log_panel.setMinimumHeight(130); self.log_panel.setMaximumHeight(160)
        bottom_row.addWidget(self.log_panel, 1)

        # Estado del sistema
        self._sys_state = HudSystemStatePanel()
        self._sys_state.setMinimumHeight(130)
        self._sys_state.setMaximumHeight(160)
        bottom_row.addWidget(self._sys_state, 1)

        # Estadísticas en vivo
        self._live_stats = HudLiveStatsPanel()
        self._live_stats.setMinimumHeight(130); self._live_stats.setMaximumHeight(160)
        bottom_row.addWidget(self._live_stats, 1)

        cl.addLayout(bottom_row)
        body.addWidget(center_frame, 1)

        # ── PANEL DERECHO: sistema de paneles flotantes ────────────────────────
        # Contiene: user_panel (fijo) + área de paneles modulares (máx 2 simultáneos)
        right = HudPanelFrame(show_header=False)
        right.setFixedWidth(255)
        right.setContentsMargins(0, 0, 0, 0)
        rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(4)

        # Header CONFIG
        cfg_tab_hdr = QFrame(); cfg_tab_hdr.setObjectName("sectionHeader"); cfg_tab_hdr.setFixedHeight(26)
        cth_lay = QHBoxLayout(cfg_tab_hdr); cth_lay.setContentsMargins(8, 0, 8, 0)
        cth_lbl = QLabel("CONFIG")
        cth_lbl.setStyleSheet(
            f"font-family:'Orbitron','Segoe UI',sans-serif;"
            f"font-size:9px;font-weight:700;color:{CY};letter-spacing:1.5px;border-top:2px solid {CY};")
        cth_lay.addWidget(cth_lbl); cth_lay.addStretch()
        rl.addWidget(cfg_tab_hdr)

        # ConfigPanel (OCR Engine) — siempre visible en el panel derecho
        self.config_panel = ConfigPanel()
        self.config_panel.ocr_folder_enqueued.connect(self._enqueue_ocr_folder)
        self.config_panel.autounify_folder_requested.connect(
            lambda f: self.folder_queue_panel._bulk_add([f]))
        self.config_panel.image_preview_requested.connect(
            self.img_comparator.show_image)   # imagen → visor REFERENCIA
        _cfg_scroll = QScrollArea(); _cfg_scroll.setWidgetResizable(True)
        _cfg_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _cfg_scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        _cfg_scroll.setWidget(self.config_panel)
        rl.addWidget(_cfg_scroll, 1)

        # Panel de usuario — tamaño fijo, nunca se estira
        self.user_panel = HudUserPanelWidget(self._user_info)
        self.user_panel.logout_requested.connect(self._logout)
        self.user_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        rl.addWidget(self.user_panel)
        self._right_layout = rl

        self._right_panel = right   # ref para expandir/colapsar en modo video

        # ── Reloj: panel propio encima de CONFIG en la columna derecha ─────────
        self._clock = HudClockWidget()
        self._clock.setFixedSize(265, 110)  # +10px para holgura del halo
        self._clock.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        right_col = HudRightColumn(self._clock, right, clock_stretch=0, bottom_stretch=1)
        right_col.setFixedWidth(265)  # +10px para holgura del halo del reloj

        # ── Sistema de paneles modulares flotantes ─────────────────────────────
        # Paneles adicionales se abren a la IZQUIERDA del panel derecho fijo.
        # Máx 2 paneles abiertos; el 3ro desplaza al más antiguo.
        self._module_panels: List[QFrame] = []   # lista de paneles abiertos [izq, der]
        self._panel_saved_positions: dict = {}        # panel_id → (x, y) última posición
        self._module_panels_bar = body  # layout donde se insertan (antes del right)

        left_side.addLayout(body, 1)          # header + body en la columna izquierda
        mid_row.addLayout(left_side, 1)       # columna izquierda ocupa todo el espacio sobrante
        mid_row.addWidget(right_col)          # columna derecha arranca al mismo nivel que el header
        root.addLayout(mid_row, 1)

        # ── Conexiones adicionales ────────────────────────────────────────────
        self.translator_widget.set_editor(self.text_editor)

        # ── Módulos → paneles flotantes ───────────────────────────────────────
        # Hook cada CollapsibleSection para que al expandirse abra su panel
        def _hook_module(idx, panel_id, factory):
            try:
                sec = self._modules._sections[idx]
                # El body del CollapsibleSection nunca debe mostrarse: el contenido
                # va al panel flotante. Forzamos height=0 para evitar gaps visuales.
                sec._body.setMaximumHeight(0)
                sec._body.hide()
                def _toggled(s=sec, pid=panel_id, f=factory):
                    # Alternar solo el estado lógico + flecha; body permanece oculto
                    s._collapsed = not s._collapsed
                    s._arrow.setText("▾" if not s._collapsed else "▸")
                    if not s._collapsed:
                        self._open_module_panel(pid, f())
                    else:
                        for p in list(self._module_panels):
                            if getattr(p, "_panel_id", None) == pid:
                                self._close_module_panel(p)
                sec.toggle = _toggled
            except Exception as ex:
                print(f"[hook_module {panel_id}] {ex}")

        # ── Factories de paneles: devuelven un WRAPPER nuevo cada vez ─────────
        # El widget real (folder_queue_panel, etc.) se reparenta al wrapper.
        # Al cerrar el panel, el wrapper se destruye pero el widget real
        # sobrevive porque se saca del parent antes de deleteLater().

        # ── Factory AUTOUNIFY: FolderQueuePanel real ─────────────────────────
        def _make_autounify_panel():
            return self.folder_queue_panel

        # ── Factory TRADUCTOR: TranslatorWidget real ──────────────────────────
        def _make_translator_panel():
            return self.translator_widget

        # ── Factory CONFIGURACIÓN: mini OCR Engine ────────────────────────────
        def _make_config_panel():
            w = QWidget()
            l = QVBoxLayout(w); l.setContentsMargins(6, 6, 6, 6); l.setSpacing(6)
            cp = self.config_panel

            # ── PaddleOCR panel (reparentado) ─────────────────────────────────
            pp = cp._paddle_panel
            if pp:
                pp.setParent(w)
                l.addWidget(pp)

            # ── Motor espejo bidireccional ────────────────────────────────────
            m_row = QHBoxLayout()
            m_lbl = QLabel("Motor:"); m_lbl.setStyleSheet(f"font-size:9px;color:{DM};")
            m_mirror_cb = QComboBox()
            m_mirror_cb.setStyleSheet(cp._motor_cb.styleSheet())
            for i in range(cp._motor_cb.count()):
                m_mirror_cb.addItem(cp._motor_cb.itemText(i))
            m_mirror_cb.setCurrentIndex(cp._motor_cb.currentIndex())
            m_mirror_cb.currentIndexChanged.connect(cp._motor_cb.setCurrentIndex)
            cp._motor_cb.currentIndexChanged.connect(m_mirror_cb.setCurrentIndex)
            m_row.addWidget(m_lbl); m_row.addWidget(m_mirror_cb, 1)
            l.addLayout(m_row)

            # ── Separador ────────────────────────────────────────────────────
            sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
            sep.setStyleSheet(f"color:rgba(0,180,255,30);margin:2px 0;"); l.addWidget(sep)

            # ── Max Height espejo ─────────────────────────────────────────────
            maxh_row = QHBoxLayout(); maxh_row.setSpacing(4)
            maxh_lbl = QLabel("Max H:"); maxh_lbl.setStyleSheet(f"font-size:9px;color:{DM};")
            maxh_spin = QSpinBox(); maxh_spin.setRange(500, 10000)
            maxh_spin.setSingleStep(500); maxh_spin.setMaximumWidth(78)
            maxh_spin.setStyleSheet("font-size:10px;")
            maxh_spin.setToolTip("Altura máxima de imagen procesada (px)")
            maxh_spin.setValue(cp._maxh.value())
            maxh_spin.valueChanged.connect(cp._maxh.setValue)
            cp._maxh.valueChanged.connect(maxh_spin.setValue)
            maxh_row.addWidget(maxh_lbl); maxh_row.addWidget(maxh_spin); maxh_row.addStretch()
            l.addLayout(maxh_row)

            # ── AutoUnify checkbox espejo ─────────────────────────────────────
            au_cb = QCheckBox("⛓ AutoUnify")
            au_cb.setStyleSheet(f"font-size:9px;color:{TX};")
            au_cb.setToolTip("Unificar imágenes automáticamente tras el OCR")
            au_cb.setChecked(cp._autounify_cb.isChecked())
            au_cb.toggled.connect(cp._autounify_cb.setChecked)
            cp._autounify_cb.toggled.connect(au_cb.setChecked)
            l.addWidget(au_cb)

            # ── Reemplazar originales checkbox espejo ─────────────────────────
            rep_cb = QCheckBox("🔄 Reemplazar imágenes originales")
            rep_cb.setStyleSheet(f"font-size:9px;color:{TX};")
            rep_cb.setToolTip("Sobreescribir imágenes originales con el resultado procesado")
            rep_cb.setChecked(cp._replace_cb.isChecked())
            rep_cb.toggled.connect(cp._replace_cb.setChecked)
            cp._replace_cb.toggled.connect(rep_cb.setChecked)
            l.addWidget(rep_cb)

            return w

        _hook_module(0, "AUTOUNIFY", _make_autounify_panel)
        _hook_module(1, "TRADUCTOR", _make_translator_panel)
        _hook_module(2, "MOTOR OCR", _make_config_panel)
        # Rosca del panel TRADUCTOR → ir a pestaña CONFIG central
        self.translator_widget.config_requested.connect(lambda: self._tab_switcher._sel(1))
        self.config_panel.out_folder_changed.connect(self.output_docs.load_folder)
        self.config_panel.out_folder_changed.connect(self.img_browser.load_output_folder)
        # img_browser ↔ img_comparator (ambos ya existen aquí)
        self.img_browser.image_selected.connect(self.img_comparator.show_image)
        self.text_editor.image_hinted.connect(self.img_browser.show_by_name)

        # ══ FOOTER — HudFooterStrip ══════════════════════════════════════════
        self._footer = HudFooterStrip()
        root.addWidget(self._footer)

    def _on_view_switched(self, idx: int):
        """Conmuta entre EDITOR (0) y CONFIG (1) en el centro."""
        if hasattr(self, "_center_stack"):
            self._center_stack.setCurrentIndex(idx)
        # Refrescar biblioteca al entrar a CONFIG
        if idx == 1 and hasattr(self, "_manga_library"):
            self._manga_library.refresh()

    # ─── Sistema de paneles modulares ────────────────────────────────────────
    # Ancho por panel
    _PANEL_WIDTHS = {
        "AUTOUNIFY":     240,
        "TRADUCTOR":     250,
        "MOTOR OCR": 255,
    }
    _PANEL_STACK_OFFSET = 6  # px de separación entre paneles apilados

    def _open_module_panel(self, panel_id: str, widget: QWidget, width: int = 0):
        """Abre un panel flotante arrastrable sobre el área central.
        Máx 2 paneles. Si hay 2, cierra el más antiguo."""
        # Toggle: si ya está abierto, cerrarlo
        for p in self._module_panels:
            if getattr(p, "_panel_id", None) == panel_id:
                self._close_module_panel(p)
                return

        # Si hay 2 paneles, cerrar el más antiguo
        if len(self._module_panels) >= 2:
            self._close_module_panel(self._module_panels[0])

        w = width or self._PANEL_WIDTHS.get(panel_id, 230)
        saved = self._panel_saved_positions.get(panel_id, None)
        if saved is None:
            # Posición inicial: apilado a la izquierda del panel CONFIG
            slot   = len(self._module_panels)
            right_x = self.width() - 260
            top_y   = 70
            x = right_x - w * (slot + 1) - self._PANEL_STACK_OFFSET * slot
            saved = (max(0, x), top_y)

        container = DraggableModulePanel(panel_id, widget, w, saved_pos=saved, parent=self)
        container.closed.connect(lambda pid: self._close_module_panel(
            next((p for p in self._module_panels if getattr(p, "_panel_id", None) == pid), None)))
        container.show()
        container.raise_()
        self._module_panels.append(container)

    def _position_module_panel(self, container: QFrame, slot: int):
        """Posiciona el panel (solo si no tiene posición guardada por el usuario)."""
        if getattr(container, "_pos_saved", False):
            return   # el usuario lo movió — respetar su posición
        right_x = self.width() - 260
        top_y   = 70
        panel_w = container.width()
        x = right_x - panel_w * (slot + 1) - self._PANEL_STACK_OFFSET * slot
        container.move(max(0, x), top_y)

    def _reposition_all_panels(self):
        """Reposicionar paneles que no han sido movidos manualmente."""
        for i, p in enumerate(self._module_panels):
            self._position_module_panel(p, i)

    def _close_module_panel(self, container):
        if container is None: return
        if container in self._module_panels:
            self._module_panels.remove(container)
        pid = getattr(container, "_panel_id", "")
        # Guardar posición antes de destruir
        if pid:
            self._panel_saved_positions[pid] = container.saved_position()
        # Rescatar widgets reales antes de destruir el contenedor
        try:
            if pid == "AUTOUNIFY" and self.folder_queue_panel.parent() is container:
                self.folder_queue_panel.setParent(None)  # type: ignore
            if pid == "TRADUCTOR" and self.translator_widget.parent() is container:
                self.translator_widget.setParent(None)   # type: ignore
            if pid == "MOTOR OCR":
                pp = self.config_panel._paddle_panel
                if pp and pp.parent() is not None and pp.parent() is not self.config_panel:
                    pp.setParent(self.config_panel)  # type: ignore
                    sec_ocr = getattr(self.config_panel, "_sec_ocr", None)
                    if sec_ocr is not None:
                        sec_ocr.add_widget(pp)
        except Exception:
            pass
        container.hide()
        container.setParent(None)   # type: ignore
        container.deleteLater()

    def _toggle_module_panel(self, panel_id: str, widget_factory):
        """Toggle: si está abierto cierra, si está cerrado abre."""
        for p in self._module_panels:
            if getattr(p, "_panel_id", None) == panel_id:
                self._close_module_panel(p)
                return
        self._open_module_panel(panel_id, widget_factory())

    def _enqueue_ocr_folder_safe(self, folder: str):
        """Proxy: enqueue desde el ConfigPanel de la página CONFIG."""
        try:
            self._enqueue_ocr_folder(folder)
        except Exception:
            pass

    def _on_cfg_page_out_folder(self, folder: str):
        """Sincroniza carpeta de salida desde el ConfigPanel de la página CONFIG."""
        try:
            self.img_browser.load_output_folder(folder)
            self.output_docs.load_folder(folder)
        except Exception:
            pass

    # Nombre de la carpeta de salida automática — cambiar aquí si se quiere otro nombre
    _HELIX_OUT_DIRNAME = "⚡ OUTPUT"

    def _on_manga_selected(self, manga_path: str):
        """Carga un manga desde la biblioteca para trabajar en el editor.
        Crea automáticamente la carpeta de salida dentro del manga:
          <manga>/⚡ OUTPUT/
        y la registra como carpeta de salida activa.
        """
        from pathlib import Path
        p = Path(manga_path)
        if not p.is_dir():
            return

        # ── Crear carpeta de salida automática ────────────────────────────────
        out_dir = p / self._HELIX_OUT_DIRNAME
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as ex:
            self._set_status(f"⚠ No se pudo crear carpeta de salida: {ex}")
            return

        out_str = str(out_dir)

        # ── Registrar como carpeta de salida en el ConfigPanel ───────────────
        if hasattr(self.config_panel, "_out_lbl"):
            self.config_panel._out_lbl.setText(out_str)
        self.config_panel.out_folder_changed.emit(out_str)

        # ── Cargar imágenes y subcarpetas ─────────────────────────────────────
        self.img_browser.load_output_folder(out_str)
        self.output_docs.load_folder(out_str)

        if hasattr(self.config_panel, "populate_sub_folders"):
            self.config_panel.populate_sub_folders(str(p))

        # ── Log + status ──────────────────────────────────────────────────────
        self.log_panel.add(f"📖 Manga: {p.name}")
        self.log_panel.add(f"📂 Salida: {out_str}")
        self._tab_switcher._sel(0)   # ir al EDITOR; subcarpetas visibles en panel derecho
        self._set_status(f"📖 {p.name}  →  ⚡ OUTPUT creado  |  Selecciona subcarpetas en 'Carpetas OCR' →")

    # ── Proxy: navegar imágenes desde comparator ─────────────────────────────
    def img_browser_panel_navigate(self, direction: int): self.img_browser.navigate(direction)

    # ── HELPERS UI ───────────────────────────────────────────────────────────
    def _mini_stat(self, icon: str, val: str) -> QLabel:
        lbl = QLabel(f"{icon} {val}")
        lbl.setStyleSheet(f"color:{DM};font-size:10px;padding:0 6px;"); return lbl

    def _stat_pill(self, label: str, val: str) -> QFrame:
        f = QFrame(); f.setObjectName("panel"); f.setMaximumHeight(34)
        h = QHBoxLayout(f); h.setContentsMargins(8, 2, 8, 2); h.setSpacing(5)
        vl = QLabel(val); vl.setStyleSheet(f"color:{CY};font-size:13px;font-weight:bold;font-family:'Orbitron','Segoe UI',sans-serif;")
        ll = QLabel(label); ll.setStyleSheet(f"color:{DM};font-size:8px;letter-spacing:1.5px;font-family:'Orbitron','Segoe UI',sans-serif;")
        h.addWidget(vl); h.addWidget(ll); f._val_lbl = vl; return f  # type: ignore

    def _update_pill(self, pill: QFrame, val: str):
        if hasattr(pill, "_val_lbl"): pill._val_lbl.setText(val)  # type: ignore

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg); self.log_panel.add(msg)
        # EKG + label status dinámico
        if hasattr(self, "_ekg"):
            low = msg.lower()
            if "completad" in low or msg.startswith("✓"):
                self._ekg.set_status("LISTO", "#00ff9d"); _st = ("LISTO", "#00ff9d")
            elif "procesand" in low or "unificand" in low or "iniciand" in low:
                self._ekg.set_status("PROCESANDO", "#ffd44d"); _st = ("PROCESANDO", "#ffd44d")
            elif "error" in low or msg.startswith("⚠"):
                self._ekg.set_status("ERROR", "#ff3355"); _st = ("ERROR", "#ff3355")
            else:
                self._ekg.set_status("IDLE", "#2e6a88"); _st = ("IDLE", "#2e6a88")
            if hasattr(self, "_status_mode_lbl"):
                self._status_mode_lbl.setText(_st[0])
                self._status_mode_lbl.setStyleSheet(
                    f"font-family:'Orbitron','Segoe UI',sans-serif;"
                    f"font-size:9px;font-weight:700;color:{_st[1]};letter-spacing:1px;"
                    f"background:transparent;border:none;")
        # Sistema state en idle cuando termina
        if hasattr(self, "_sys_state"):
            low = msg.lower()
            if "completad" in low or msg.startswith("✓"):
                self._sys_state.set_active(False)
        # Toasts para estados clave
        if hasattr(self, '_toast'):
            low = msg.lower()
            if msg.startswith("✓") or "completad" in low:
                self._toast.show(msg, "ok")
            elif msg.startswith("⚠") or "error" in low:
                self._toast.show(msg, "warn")

    def _apply_saved_cfg(self): pass

    # ── BURBUJA ───────────────────────────────────────────────────────────────
    def _go_bubble(self):
        """Oculta la ventana principal y muestra la burbuja flotante."""
        if not self._bubble:
            self._bubble = BubbleWidget(self._cfg)
            self._bubble.restore_requested.connect(self._restore_from_bubble)
        # Ocultar ventana DESPUÉS de crear la burbuja para evitar estado zombie
        self.hide()
        self._bubble.show()
        self._bubble.raise_()
        self._bubble.activateWindow()

    def _restore_from_bubble(self):
        """Restaura la ventana principal desde la burbuja."""
        if self._bubble:
            self._bubble.hide()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ── COLA OCR ──────────────────────────────────────────────────────────────
    def _enqueue_ocr_folder(self, folder: str):
        self._set_status(f"Carpeta en cola: {Path(folder).name}")
        self._update_pill(self._stat_queue, str(len(self.config_panel.get_ocr_folders())))

    def _on_start(self):
        if not MOTOR_OK:
            QMessageBox.critical(self, "Motor no disponible",
                "Motor OCR no encontrado.\nColoca Motor_Paddle_OCR.py en la misma carpeta."); return
        queue_folders = self.config_panel.get_ocr_folders()
        if queue_folders:
            params_base = self.config_panel.get_params()
            self._folder_queue = []
            for f in queue_folders:
                p = dict(params_base); p["src_folder"] = f
                self._folder_queue.append({"params": p, "folder": f, "done": False})
            self._queue_idx = -1; self._queue_running = True
            self._update_pill(self._stat_queue, str(len(self._folder_queue)))
            self._process_next_queue_item()
        else:
            params = self.config_panel.get_params(); src = params["src_folder"]; out = params["out_folder"]
            if not src or not Path(src).is_dir():
                QMessageBox.warning(self, "Config. incompleta",
                    "Configura la carpeta de entrada en CONFIG\no añade carpetas en el panel izquierdo."); return
            if not out:
                QMessageBox.warning(self, "Config. incompleta", "Configura la carpeta de salida en CONFIG."); return
            self._folder_queue = [{"params": params, "folder": src, "done": False}]
            self._queue_idx = -1; self._queue_running = True; self._update_pill(self._stat_queue, "1")
            self._process_next_queue_item()

    def _process_next_queue_item(self):
        next_idx = self._queue_idx + 1
        while next_idx < len(self._folder_queue) and self._folder_queue[next_idx].get("done"):
            next_idx += 1
        if next_idx >= len(self._folder_queue):
            self._queue_running = False
            self._set_status(f"✓ Cola completada ({len(self._folder_queue)} carpetas procesadas)")
            self.output_docs.set_running(False); self.output_docs.set_progress(100); return
        self._queue_idx = next_idx; item = self._folder_queue[self._queue_idx]
        params = item["params"]; folder = item["folder"]
        self.config_panel.set_ocr_status(folder, FolderQueuePanel.ST_PROC)
        self._proc_start_time = time.time()
        self._set_status(f"Procesando [{self._queue_idx+1}/{len(self._folder_queue)}]: {Path(folder).name}…")
        self.output_docs.set_running(True); self.output_docs.set_progress(0)
        # Activar panel de estado
        if hasattr(self, "_sys_state"):
            self._sys_state.set_active(True); self._sys_state.set_progress(0)
        self.img_comparator.set_src_folder(Path(folder)); self._start_unify_then_ocr(params)

    def _on_unify_done(self, paths: List[str]):
        if not paths: self._set_status("⚠ Unify: sin imágenes generadas"); self._on_folder_done_error("Sin imágenes generadas"); return
        self._set_status(f"✓ {len(paths)} imágenes → iniciando OCR…")
        if paths: self.img_browser.set_folder(Path(paths[0]).parent)
        params = self._pending_params; expanded = sorted([Path(p) for p in paths], key=_natural_key)
        folder_name = Path(params["src_folder"]).name or "output"; ocr_mode = params.get("ocr_mode","classic")
        self.log_panel.add(f"🔧 Modo OCR seleccionado: {ocr_mode.upper()}")
        if ocr_mode == "space" and SPACE_OK and OCRWorkerSpace is not None:
            api_key = params.get("space_api_key","")
            if not api_key:
                QMessageBox.warning(self,"API Key requerida","Configura tu API key de OCR.space en CONFIG.")
                self._on_folder_done_error("Sin API key de OCR.space"); return
            self.log_panel.add("🌐 Usando motor OCR.space API"); self._start_space_worker(expanded, params, folder_name, api_key)
        else:
            self._start_classic_worker(expanded, params, folder_name)

    def _start_unify_then_ocr(self, params: Dict):
        self._pending_params = params
        if not params.get("use_autounify", True):
            src = Path(params["src_folder"]); exts = {".png",".jpg",".jpeg",".webp",".bmp",".tiff",".tif"}
            orig_images = sorted([str(p) for p in src.iterdir() if p.suffix.lower() in exts],
                                  key=lambda p: _natural_key(Path(p)))
            if not orig_images:
                self._set_status("⚠ Sin imágenes en la carpeta (AutoUnify desactivado)")
                self._on_folder_done_error("Sin imágenes originales"); return
            self.log_panel.add(f"⛓ AutoUnify omitido → {len(orig_images)} imágenes originales")
            self._on_unify_done(orig_images); return
        self._set_status("Unificando imágenes…"); ocr_mode = params.get("ocr_mode","classic")
        if ocr_mode == "space" and SPACE_OK and UnifyWorkerSpace_OCRSpace is not None:
            self._unify_worker = UnifyWorkerSpace_OCRSpace(
                src_folder=params["src_folder"], ocr_lang=params["ocr_lang"],
                max_height=params["max_height"], auto_unify=True, save_remnant=True)
        else:
            self._unify_worker = UnifyWorker(params["src_folder"], params["ocr_lang"], params["max_height"], True, True)
        self._unify_worker.progress.connect(self.output_docs.set_progress)
        self._unify_worker.status_msg.connect(self._set_status)
        self._unify_worker.finished.connect(self._on_unify_done)
        self._unify_worker.error.connect(self._on_error); self._unify_worker.start()

    def _start_classic_worker(self, files: List[Path], params: Dict, folder_name: str):
        rtl = params.get("reading_order","rtl") == "rtl"; vertical_jp = params.get("vertical_japanese", False)
        if MOTOR_OK and OCRWorkerCropPaddle is not None:
            self._ocr_worker = OCRWorkerCropPaddle(
                image_paths=files, output_folder=params["out_folder"], fmt=params["fmt"],
                translate_to="", case_mode=params["case_mode"], folder_name=folder_name,
                ocr_lang=params["ocr_lang"], use_gpu=False, online_learning=params["online_learning"],
                keep_sfx=params["keep_sfx"], rtl=rtl)
            self._connect_ocr_worker_signals(); self._ocr_worker.start()
            self.log_panel.add(f"🔍 Worker Crop-First Pipeline iniciado (RTL={rtl})")
        elif MOTOR_OK and OCRWorker is not None:
            self._ocr_worker = OCRWorker(
                image_paths=files, output_folder=params["out_folder"], fmt=params["fmt"],
                translate_to="", case_mode=params["case_mode"], folder_name=folder_name,
                ocr_lang=params["ocr_lang"], use_gpu=False, online_learning=params["online_learning"],
                keep_sfx=params["keep_sfx"], vertical_japanese=vertical_jp, rtl=rtl)
            self._connect_ocr_worker_signals(); self._freeze_processes(); self._ocr_worker.start()
            self.log_panel.add(f"🚀 Worker PaddleOCR iniciado (RTL={rtl}, vertical_jp={vertical_jp})")
        else:
            QMessageBox.critical(self,"Motor no disponible","Motor_Paddle_OCR.py no encontrado.")
            self._on_folder_done_error("Motor_Paddle_OCR no disponible")

    def _start_space_worker(self, files: List[Path], params: Dict, folder_name: str, api_key: str):
        self._ocr_worker = OCRWorkerSpace(
            image_paths=files, output_folder=params["out_folder"], fmt=params["fmt"],
            translate_to="", case_mode=params["case_mode"], folder_name=folder_name,
            ocr_lang=params["ocr_lang"], api_key=api_key, engine=params.get("space_engine",2),
            keep_sfx=params["keep_sfx"], reading_order=params.get("reading_order","rtl"), use_crop_pipeline=True)
        self._connect_ocr_worker_signals(); self._freeze_processes(); self._ocr_worker.start()
        self.log_panel.add(f"🚀 Worker OCR.space iniciado | Engine {params.get('space_engine',2)} | Lang: {params['ocr_lang']}")

    def _freeze_processes(self):
        if hasattr(self, "_bg"): self._bg.pause_rotation()
        if not PROCMGR_OK or ProcessSnapshot is None: return
        if self._proc_snapshot and self._proc_snapshot.is_frozen: return
        self._proc_snapshot = ProcessSnapshot(); self._proc_snapshot.freeze(log_cb=self.log_panel.add)

    def _thaw_processes(self):
        if self._proc_snapshot and self._proc_snapshot.is_frozen:
            self._proc_snapshot.thaw(log_cb=self.log_panel.add)
        self._proc_snapshot = None
        if hasattr(self, "_bg"): self._bg.resume_rotation()

    def _connect_ocr_worker_signals(self):
        if not self._ocr_worker: return
        if getattr(self._ocr_worker, "_signals_connected", False): return
        self._ocr_worker._signals_connected = True
        self._ocr_worker.progress.connect(self.output_docs.set_progress)
        # También alimentar el panel de estado del sistema
        if hasattr(self, "_sys_state"):
            self._ocr_worker.progress.connect(self._sys_state.set_progress)
        self._ocr_worker.status_msg.connect(self._set_status)
        self._ocr_worker.log_msg.connect(self.log_panel.add)
        self._ocr_worker.finished_ok.connect(self._on_done)
        self._ocr_worker.error.connect(self._on_error)
        if hasattr(self._ocr_worker, 'stats_update'):
            self._ocr_worker.stats_update.connect(self._update_stats)

    def _delete_unified_folder(self, src_folder: str):
        """Borra definitivamente las carpetas temporales unificadas."""
        p = Path(src_folder)
        for subdir_name in ("_unified", "_unified_space"):
            ud = p / subdir_name
            if ud.exists() and ud.is_dir():
                try:
                    shutil.rmtree(ud)
                    self.log_panel.add(f"🗑 Carpeta temporal eliminada: {ud.name}")
                except Exception as ex:
                    self.log_panel.add(f"⚠ No se pudo eliminar {ud.name}: {ex}")

    def _on_done(self, path: str):
        self._thaw_processes()
        current_folder = (self._folder_queue[self._queue_idx]["folder"]
                          if 0 <= self._queue_idx < len(self._folder_queue) else "")
        if current_folder:
            self._folder_queue[self._queue_idx]["done"] = True
            self.config_panel.set_ocr_status(current_folder, FolderQueuePanel.ST_DONE)
        self._set_status(f"✓ Completado: {Path(path).name}")
        self.output_docs.set_progress(100); self.output_docs.add_file(path)
        self.text_editor.load_file(path); self._set_status(f"Abierto: {Path(path).name}")
        # Paneles de estado
        if hasattr(self, "_sys_state"):
            self._sys_state.set_progress(100); self._sys_state.set_active(False)
        # Borrar carpeta unificada temporal (si replace_originals está desactivado)
        if current_folder:
            params = self._folder_queue[self._queue_idx].get("params", {}) if hasattr(self, "_folder_queue") else {}
            if not params.get("replace_originals", False):
                self._delete_unified_folder(current_folder)
        remaining = sum(1 for it in self._folder_queue if not it.get("done"))
        if remaining > 0:
            self._set_status(
                f"✓ {Path(path).name} listo ({len(self._folder_queue)-remaining}/{len(self._folder_queue)}). Procesando siguiente…")
            QTimer.singleShot(800, self._process_next_queue_item)
        else:
            self.output_docs.set_running(False); self._queue_running = False
            if len(self._folder_queue) > 1:
                self._set_status(f"✓ Cola completada — {len(self._folder_queue)} archivos generados.")
            else:
                QMessageBox.information(self, "✓ Proceso completado", f"Archivo guardado:\n{path}")

    def _on_folder_done_error(self, err: str):
        if 0 <= self._queue_idx < len(self._folder_queue):
            folder = self._folder_queue[self._queue_idx]["folder"]
            self._folder_queue[self._queue_idx]["done"] = True
            self.config_panel.set_ocr_status(folder, FolderQueuePanel.ST_ERR)
        self.output_docs.set_progress(0)
        remaining = sum(1 for it in self._folder_queue if not it.get("done"))
        if remaining > 0: QTimer.singleShot(1000, self._process_next_queue_item)
        else: self.output_docs.set_running(False); self._queue_running = False

    def _on_error(self, err: str):
        self._thaw_processes(); self._set_status(f"⚠ Error: {err}")
        QMessageBox.critical(self, "Error en proceso", err); self._on_folder_done_error(err)

    def _on_cancel(self):
        self._thaw_processes()
        if self._unify_worker and self._unify_worker.isRunning():
            self._unify_worker.cancel(); self._unify_worker.terminate(); self._unify_worker.wait(2000)
        if self._ocr_worker and self._ocr_worker.isRunning(): self._ocr_worker.cancel()
        self._set_status("Proceso cancelado."); self.output_docs.set_running(False)
        self.output_docs.set_progress(0); self._queue_running = False
        if 0 <= self._queue_idx < len(self._folder_queue):
            folder = self._folder_queue[self._queue_idx]["folder"]
            self.config_panel.set_ocr_status(folder, FolderQueuePanel.ST_ERR)

    def _do_unify_queue(self, folders: List[str]):
        if not UNIFY_OK: QMessageBox.warning(self, "Error", "autounify.py no disponible."); return
        self._unify_queue = list(folders); self._unify_queue_idx = -1; self._unify_queue_running = True
        self.output_docs.set_running(True); self._process_next_unify()

    def _process_next_unify(self):
        self._unify_queue_idx += 1
        if self._unify_queue_idx >= len(self._unify_queue):
            self._unify_queue_running = False; self.output_docs.set_running(False)
            total = len(self._unify_queue)
            if total > 1: QMessageBox.information(self, "✓ AutoUnify", f"Todas las carpetas unificadas ({total}).")
            return
        folder = self._unify_queue[self._unify_queue_idx]; max_h = self.folder_queue_panel.get_max_height()
        self._set_status(f"Unificando [{self._unify_queue_idx+1}/{len(self._unify_queue)}]: {Path(folder).name}…")
        self.folder_queue_panel.set_unify_status(folder, FolderQueuePanel.ST_PROC)
        _params_au = self.config_panel.get_params() if hasattr(self,"config_panel") else {}
        self._unify_worker = UnifyWorker(folder, _params_au.get("ocr_lang","en"), max_h)
        self._unify_worker.progress.connect(self.output_docs.set_progress)
        self._unify_worker.status_msg.connect(self._set_status)
        self._unify_worker.finished.connect(lambda paths, f=folder: self._on_unify_manual_done(f, paths))
        self._unify_worker.error.connect(lambda e, f=folder: self._on_unify_manual_error(f, e))
        self._unify_worker.start()

    def _on_unify_manual_done(self, folder: str, paths: List[str]):
        self._set_status(f"✓ {len(paths)} imágenes unificadas en {Path(folder).name}")
        self.folder_queue_panel.set_unify_status(folder, FolderQueuePanel.ST_DONE)
        params = self.config_panel.get_params() if hasattr(self,"config_panel") else {}
        if params.get("replace_originals", False):
            try:
                from pipeline.autounify import replace_originals_with_unified
                ok = replace_originals_with_unified(folder, log_cb=lambda m: self.log_panel.add(m))
                if ok: self._set_status(f"✓ Originales reemplazados en {Path(folder).name}")
                else: self._set_status(f"⚠ No se pudieron reemplazar originales en {Path(folder).name}")
            except ImportError: self.log_panel.add("⚠ autounify.replace_originals_with_unified no disponible")
        QTimer.singleShot(300, self._process_next_unify)

    def _on_unify_manual_error(self, folder: str, err: str):
        self._set_status(f"⚠ Error en {Path(folder).name}: {err}")
        self.folder_queue_panel.set_unify_status(folder, FolderQueuePanel.ST_ERR)
        QTimer.singleShot(300, self._process_next_unify)

    def _open_doc(self, path: str):
        self.text_editor.load_file(path); self._set_status(f"Abierto: {Path(path).name}")

    def _update_stats(self, data: Dict):
        imgs = str(data.get("images","0")); chars = str(data.get("chars","0"))
        words = str(data.get("words","0")); total = str(data.get("total","0"))
        self._update_pill(self._stat_imgs, imgs); self._update_pill(self._stat_chars, chars)
        self._update_pill(self._stat_words, words); self._update_pill(self._stat_queue, total)
        self._hdr_imgs.setText(f"🖼 {imgs}"); self._hdr_chars.setText(f"📝 {chars}"); self._hdr_words.setText(f"📖 {words}")
        elapsed = time.time() - self._proc_start_time if self._proc_start_time else 0
        # ── stats_panel compatibilidad (ya no en tabs, pero por si acaso) ────
        # ── HudLiveStatsPanel (punto 3) ───────────────────────────────────────
        try:
            chars_int = int(chars) if str(chars).isdigit() else 0
            ocr_acc = float(data.get("ocr_acc", 95.0))
            self._live_stats.update_stats({
                "images":  f"{imgs}/{total}",
                "chars":   chars_int,
                "words":   words,
                "ocr_acc": ocr_acc,
            })
        except Exception: pass
        # ── HudSystemStatePanel (punto 3) ────────────────────────────────────
        try:
            progress = data.get("progress", 0)
            self._sys_state.set_progress(int(progress))
            self._sys_state.set_active(True)
            self._sys_state.set_elapsed(elapsed)
        except Exception: pass
        # ── EKG status ────────────────────────────────────────────────────────
        if hasattr(self, "_ekg"):
            self._ekg.set_status("PROCESANDO", "#ffd44d")

    def _logout(self):
        cfg = load_cfg(); cfg.pop("remember_email", None); save_cfg(cfg)
        self.hide()
        dlg = LoginDialog(); _res: List[Optional[Dict]] = [None]
        dlg.login_ok.connect(lambda info: _res.__setitem__(0, info))
        if dlg.exec() == QDialog.DialogCode.Accepted and _res[0]:
            new_info = _res[0]; self._user_info = new_info
            new_up = HudUserPanelWidget(new_info)
            new_up.logout_requested.connect(self._logout)
            self._right_layout.replaceWidget(self.user_panel, new_up)
            self.user_panel.deleteLater(); self.user_panel = new_up
            self.show(); self.raise_(); self.activateWindow()
        else:
            QApplication.instance().quit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "_bg"): self._bg.setGeometry(0, 0, self.width(), self.height())
        # Reposicionar toasts
        if hasattr(self, "_toast"): self._toast._restack()
        # Reposicionar paneles flotantes
        if hasattr(self, "_module_panels"):
            self._reposition_all_panels()
        # reloj embebido en header — sin reposicionamiento
        # Redimensionar tutorial overlay
        if hasattr(self, "_tutorial") and self._tutorial:
            cw = self.centralWidget()
            if cw:
                self._tutorial.setGeometry(0, 0, cw.width(), cw.height())

    # reloj embebido en header, no necesita _reposition_clock

    def _on_ref_expansion(self, expand: bool):
        """
        expand=True  → video landscape: oculta el panel CONFIG derecho,
                        REFERENCIA se expande hacia esa derecha.
                        El editor de texto queda intacto.
        expand=False → video portrait o imagen: CONFIG vuelve a aparecer,
                        splitter vuelve a su estado normal.
        """
        if expand:
            # Guardar tamaños del splitter solo si no estaba expandido
            sizes = self._editor_splitter.sizes() if hasattr(self, "_editor_splitter") else [500, 500]
            if sizes[1] < sum(sizes) * 0.6:
                self._editor_splitter_normal = sizes
            # Ocultar CONFIG — REFERENCIA ocupa su espacio automáticamente
            if hasattr(self, "_right_panel"):
                self._right_panel.hide()
        else:
            # Restaurar CONFIG
            if hasattr(self, "_right_panel"):
                self._right_panel.show()
            # Restaurar splitter a proporciones normales
            if hasattr(self, "_editor_splitter"):
                self._editor_splitter.setSizes(self._editor_splitter_normal)
            pass  # reloj embebido

    def closeEvent(self, e):
        running = ((self._ocr_worker and self._ocr_worker.isRunning()) or
                   (self._unify_worker and self._unify_worker.isRunning()))
        if running:
            r = QMessageBox.question(self, "Proceso en curso", "¿Salir mientras se procesa?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
            if r == QMessageBox.StandardButton.No: e.ignore(); return
            for w in [self._ocr_worker, self._unify_worker]:
                if w and w.isRunning(): w.terminate(); w.wait(2000)
        save_cfg(self._cfg); e.accept()


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    # ── apply_hud_theme: paleta Fusion + HUD_QSS + mapa de compatibilidad ───
    apply_hud_theme(app)
    app.setStyleSheet(APP_QSS)   # sobreescribimos con HUD_QSS + compat aliases

    cfg = load_cfg(); remembered = cfg.get("remember_email", ""); user_info = None
    if remembered:
        users = load_users(); info = users.get(remembered)
        if info: user_info = {**info, "email": remembered}

    if not user_info:
        dlg = LoginDialog(); _result = [None]
        dlg.login_ok.connect(lambda info: _result.__setitem__(0, info))
        if dlg.exec() != QDialog.DialogCode.Accepted or not _result[0]: sys.exit(0)
        user_info = _result[0]

    win = MainWindow(user_info); win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()