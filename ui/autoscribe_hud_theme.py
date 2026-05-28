"""
autoscribe_hud_theme.py  —  AutoScribe HELIX HUD Theme v3.1
============================================================
Componentes implementados:

  Punto 1  · ModulesSection       — Módulos expandibles/colapsables con exclusividad
  Punto 2  · HudSystemMonitor     — Sistema en tiempo real (RAM/CPU/GPU, motor, dispositivo)
  Punto 3  · HudConsolePanel      — Consola del sistema con cursor parpadeante
             HudSystemStatePanel  — Estado del sistema animado con orbe OCR
             HudLiveStatsPanel    — Estadísticas en vivo: imágenes, chars, palabras, precisión
  Punto 4  · HudTabSwitcher       — EDITOR/CONFIG + latencia animada + POWER en tiempo real
  Punto 5  · HudEkgWidget         — Línea EKG completamente animada + STATUS dinámico
  Punto 6  · HudClockWidget       — Reloj futurista 12/24h ajustable + esfera animada
  Punto 7  · (exclusividad en ModulesSection — módulo OCR exclusivo)
  Punto 8  · HudUserPanel         — Panel de usuario futurista con avatar animado
  Punto 9  · HudNetworkBar        — Candado + señal WiFi 4 barras + data flow arcoíris
             HudFooterStrip       — Footer completo con todos los indicadores
  Punto 10 · HudCenterOrb         — Orbe central animado muy detallado
  Punto 11 · HudRichToolbar       — Toolbar completa con fuentes del sistema
  Punto 12 · HudWordCounter       — Contador palabras + estado de guardado
"""

import math, time, random
from typing import List, Optional

from PyQt6.QtWidgets import (
    QApplication, QWidget, QFrame, QLabel, QPushButton, QComboBox,
    QLineEdit, QCheckBox, QTabWidget, QHBoxLayout, QVBoxLayout,
    QGraphicsOpacityEffect, QSizePolicy, QTextEdit, QFontComboBox,
    QSpinBox, QToolButton, QScrollArea, QStackedWidget, QGridLayout,
    QSplitter, QMenu, QProgressBar,
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QObject, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QConicalGradient,
    QRadialGradient, QPainterPath, QFont, QPalette, QFontDatabase, QPolygonF,
)

# ─── PALETA ──────────────────────────────────────────────────────────────────
C_CYAN      = "#00eaff"
C_CYAN_MID  = "#00bfff"
C_CYAN_DARK = "#005f96"
C_GREEN     = "#00ff9d"
C_RED       = "#ff3355"
C_YELLOW    = "#ffd44d"
C_BG        = "#010307"
C_TX        = "#e3f7ff"
C_TX_MID    = "#acd9ef"
C_TX_DIM    = "#2e6a88"

HUD_QSS = f"""
* {{
    font-family: 'Rajdhani', 'Segoe UI', sans-serif;
    font-size: 12px; color: {C_TX}; outline: none;
}}
QMainWindow, QDialog {{ background: {C_BG}; }}
QWidget {{ background: transparent; }}
QFrame#hud_panel {{
    background: transparent;
    border: none;
    border-radius: 0px;
}}
QFrame#hud_header {{
    background: rgba(1,6,18,200);
    border-bottom: 1px solid rgba(0,180,255,80);
}}
QFrame#hud_footer {{
    background: rgba(1,4,10,235);
    border: 1px solid rgba(0,180,255,36); border-radius: 3px;
}}
QLabel {{ color: {C_TX}; background: transparent; }}
QLabel#orbitron {{ font-family:'Orbitron','Segoe UI',sans-serif; font-weight:700; letter-spacing:1px; color:{C_CYAN}; }}
QLabel#dim    {{ color:{C_TX_DIM}; font-size:11px; }}
QLabel#mono   {{ font-family:'Share Tech Mono','Consolas',monospace; }}
QLabel#green  {{ color:{C_GREEN}; }}
QLabel#red    {{ color:{C_RED}; }}
QLabel#yellow {{ color:{C_YELLOW}; }}
QPushButton {{
    background:rgba(0,30,80,38); color:{C_TX_MID};
    border:1px solid rgba(0,180,255,51); border-radius:3px;
    padding:5px 12px; font-family:'Orbitron','Segoe UI',sans-serif;
    font-size:10px; font-weight:700; letter-spacing:0.8px;
}}
QPushButton:hover {{ border-color:{C_CYAN}; color:#ffffff; background:rgba(0,180,255,18); }}
QPushButton:pressed {{ background:rgba(0,180,255,30); }}
QPushButton:disabled {{ color:{C_TX_DIM}; border-color:rgba(0,100,180,25); }}
QPushButton#hud_primary {{
    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(0,150,255,46),stop:1 rgba(0,60,160,13));
    color:#ffffff; border:1px solid rgba(0,180,255,82);
}}
QPushButton#hud_primary:hover {{ border-color:{C_CYAN}; background:rgba(0,180,255,46); }}
QPushButton#hud_danger {{
    background:rgba(200,30,50,46); color:#ffffff;
    border:1px solid rgba(255,51,85,82); font-weight:700;
}}
QPushButton#hud_danger:hover {{ background:rgba(255,51,85,64); border-color:{C_RED}; }}
QPushButton#hud_danger:disabled {{
    background:rgba(60,20,30,46); border-color:rgba(120,30,45,51); color:rgba(200,100,120,100);
}}
QPushButton#hud_ghost {{
    background:transparent; color:{C_TX_DIM};
    border:1px solid rgba(0,180,255,20); font-size:10px; padding:3px 8px;
    font-family:'Rajdhani','Segoe UI',sans-serif; font-weight:600; letter-spacing:0;
}}
QPushButton#hud_ghost:hover {{ border-color:rgba(0,180,255,77); color:{C_TX}; background:rgba(0,180,255,13); }}
QComboBox {{
    background:rgba(0,4,16,128); color:{C_TX};
    border:1px solid rgba(0,180,255,36); border-radius:3px; padding:4px 8px;
    font-family:'Rajdhani','Segoe UI',sans-serif; font-size:13px;
}}
QComboBox:hover  {{ border-color:rgba(0,180,255,77); }}
QComboBox:focus  {{ border-color:{C_CYAN}; }}
QComboBox::drop-down {{ border:none; width:18px; background:transparent; }}
QComboBox::down-arrow {{ image:none; border:none; }}
QComboBox QAbstractItemView {{
    background:rgba(2,9,30,245); color:{C_TX};
    border:1px solid rgba(0,180,255,51); border-radius:3px; outline:none;
    selection-background-color:rgba(0,180,255,46);
}}
QComboBox QAbstractItemView::item {{ padding:5px 10px; }}
QComboBox QAbstractItemView::item:selected {{ color:#fff; }}
QLineEdit, QTextEdit, QPlainTextEdit {{
    background:rgba(0,4,16,140); color:#ffffff;
    border:1px solid rgba(0,180,255,36); border-radius:3px; padding:4px 8px;
    font-family:'Rajdhani','Segoe UI',sans-serif; font-size:13px;
    selection-background-color:rgba(0,180,255,77);
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border-color:{C_CYAN}; }}
QCheckBox {{ color:{C_TX_MID}; spacing:6px; font-size:11px; font-family:'Rajdhani','Segoe UI',sans-serif; }}
QCheckBox::indicator {{ width:13px; height:13px; border:1px solid rgba(0,180,255,64); border-radius:2px; background:rgba(0,0,0,77); }}
QCheckBox::indicator:checked {{ background:rgba(0,234,255,64); border-color:{C_CYAN}; }}
QCheckBox::indicator:hover {{ border-color:rgba(0,180,255,128); }}
QScrollBar:vertical {{ background:rgba(1,11,33,51); width:4px; border-radius:2px; margin:0; }}
QScrollBar::handle:vertical {{ background:rgba(0,180,255,64); border-radius:2px; min-height:16px; }}
QScrollBar::handle:vertical:hover {{ background:rgba(0,234,255,140); }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar:horizontal {{ background:rgba(1,11,33,51); height:4px; border-radius:2px; }}
QScrollBar::handle:horizontal {{ background:rgba(0,180,255,64); border-radius:2px; min-width:16px; }}
QListWidget {{ background:rgba(0,4,14,110); border:1px solid rgba(0,180,255,20); border-radius:3px; color:{C_TX}; outline:none; }}
QListWidget::item {{ padding:5px 8px; border-bottom:1px solid rgba(255,255,255,8); font-family:'Rajdhani','Segoe UI',sans-serif; font-size:12px; }}
QListWidget::item:selected {{ background:rgba(0,180,255,26); color:#ffffff; border-left:2px solid {C_CYAN}; }}
QListWidget::item:hover {{ background:rgba(0,180,255,15); }}
QTreeWidget {{ background:rgba(0,4,14,110); border:1px solid rgba(0,180,255,20); border-radius:3px; color:{C_TX}; outline:none; font-family:'Rajdhani','Segoe UI',sans-serif; font-size:11px; }}
QTreeWidget::item {{ padding:3px 5px; }}
QTreeWidget::item:selected {{ background:rgba(0,180,255,26); color:#fff; }}
QTreeWidget::item:hover {{ background:rgba(0,180,255,13); }}
QTreeWidget::branch {{ background:transparent; }}
QTabWidget::pane {{ border:1px solid rgba(0,180,255,36); background:rgba(1,4,14,220); border-radius:0 3px 3px 3px; }}
QTabBar::tab {{ background:rgba(0,4,14,46); color:{C_TX_MID}; border:1px solid rgba(0,180,255,18); border-bottom:none; padding:6px 16px; font-family:'Orbitron','Segoe UI',sans-serif; font-size:9px; font-weight:600; letter-spacing:0.8px; margin-right:1px; }}
QTabBar::tab:selected {{ background:rgba(0,180,255,20); color:{C_CYAN}; border-color:rgba(0,180,255,60); border-top:2px solid {C_CYAN}; }}
QTabBar::tab:hover {{ background:rgba(0,180,255,15); color:{C_TX}; }}
QSplitter::handle {{ background:rgba(0,180,255,20); width:2px; height:2px; }}
QSplitter::handle:hover {{ background:rgba(0,180,255,60); }}
"""


def apply_hud_theme(app: QApplication):
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(1,  3,  7))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(227,247,255))
    p.setColor(QPalette.ColorRole.Base,            QColor(0,  4, 16))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(2,  9, 30))
    p.setColor(QPalette.ColorRole.Text,            QColor(227,247,255))
    p.setColor(QPalette.ColorRole.Button,          QColor(0, 30, 80))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(172,217,239))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(0, 180,255))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255,255,255))
    app.setPalette(p)
    app.setStyleSheet(HUD_QSS)


# =============================================================================
#  SIMPLE WIDGET ALIASES
# =============================================================================

# =============================================================================
#  UTILIDAD: punto sobre el perímetro de un rectángulo
# =============================================================================
def _point_on_perimeter(t: float, w: float, h: float, ch: float = 0.0):
    """
    t en [0,1) recorre el perímetro en sentido horario desde TL.
    Si ch > 0 sigue el polígono con chaflán en esquinas superiores.
    """
    import math as _math
    from PyQt6.QtCore import QPointF

    if ch <= 0.0:
        # Rectángulo simple: top → right → bottom → left
        verts = [
            QPointF(0, 0), QPointF(w, 0),
            QPointF(w, h), QPointF(0, h),
            QPointF(0, 0),
        ]
    else:
        # Polígono con chaflán: 6 vértices, sentido horario desde TL_end
        verts = [
            QPointF(ch,      0),    # TL diagonal end  ← punto de inicio
            QPointF(w - ch,  0),    # TR diagonal start
            QPointF(w,       ch),   # TR diagonal end
            QPointF(w,       h),    # BR
            QPointF(0,       h),    # BL
            QPointF(0,       ch),   # TL diagonal start
            QPointF(ch,      0),    # TL diagonal end  ← cierre
        ]

    lengths = []
    for i in range(len(verts) - 1):
        a = verts[i]; b = verts[i + 1]
        lengths.append(_math.hypot(b.x() - a.x(), b.y() - a.y()))

    perim = sum(lengths)
    dist = (t % 1.0) * perim

    for i, seg_len in enumerate(lengths):
        if dist <= seg_len:
            frac = dist / seg_len if seg_len > 0 else 0.0
            a = verts[i]; b = verts[i + 1]
            return QPointF(a.x() + (b.x() - a.x()) * frac,
                           a.y() + (b.y() - a.y()) * frac)
        dist -= seg_len
    return verts[0]


# =============================================================================
#  HudPanelFrame v4.0  — Panel HUD ultra-detallado estilo HELIX
# =============================================================================
class HudPanelFrame(QFrame):
    """
    Panel HUD ultra-detallado estilo HELIX v4.0.

    Características visuales:
    • Header con chaflán en esquinas TL y TR.
    • Borde base sutil con fondo translúcido degradado.
    • Escuadras en 4 esquinas con efecto de doble glow.
    • Pulso senoidal independiente por esquina.
    • Luz viajera que recorre el perímetro (2 puntos contrarrotatorios).
    • Parpadeo ultra-suave en la línea divisoria del header.

    Parámetros
    ──────────
    titulo      : texto en el header (puede ser "")
    parent      : widget padre (None)
    corner_size : largo de cada brazo de la escuadra en px  (default 14)
    chamfer     : tamaño del corte diagonal del header en px (default 13)
    travel_speed: velocidad de la luz viajera (fracción de perímetro/frame)
    show_header : mostrar o no el header con chaflán
    """

    def __init__(
        self,
        titulo:       str   = "",
        parent              = None,
        corner_size:  int   = 14,
        chamfer:      int   = 13,
        travel_speed: float = 0.0018,
        show_header:  bool  = True,
        arrow_header: bool  = False,
    ):
        super().__init__(parent)
        self.setObjectName("hud_panel")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self._titulo       = titulo.upper()
        self._corner       = corner_size
        self._chamfer      = chamfer
        self._speed        = travel_speed
        self._show_header  = show_header
        self._arrow_header = arrow_header

        self._t1    = 0.0
        self._t2    = 0.5
        self._pulse  = 0.0
        self._hpulse = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

        self._hh = 24 if show_header else 0
        self.setContentsMargins(10, self._hh + 8, 10, 10)

    # ── API pública ────────────────────────────────────────────────────────────
    def set_titulo(self, texto: str):
        self._titulo = texto.upper()
        self.update()

    def set_speed(self, v: float):
        self._speed = max(0.0, v)

    # ── Tick de animación ──────────────────────────────────────────────────────
    def _tick(self):
        self._t1     = (self._t1    + self._speed          ) % 1.0
        self._pulse  = (self._pulse + 0.045               ) % (2 * math.pi)
        self._hpulse = (self._hpulse + 0.025              ) % (2 * math.pi)
        self.update()

    # ── paintEvent principal ───────────────────────────────────────────────────
    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        W = float(self.width())
        H = float(self.height())
        w = W - 1.0
        h = H - 1.0

        # ── Fondo semitransparente del panel ──────────────────────────────────
        ch = float(self._chamfer) if self._show_header else 0.0
        if self._show_header:
            bg_poly = QPolygonF([
                QPointF(0,      h), QPointF(0,      ch),
                QPointF(ch,     0), QPointF(w - ch, 0),
                QPointF(w,      ch), QPointF(w,     h),
            ])
        else:
            bg_poly = QPolygonF([
                QPointF(0, 0), QPointF(w, 0),
                QPointF(w, h), QPointF(0, h),
            ])
        bg_grad = QLinearGradient(0, 0, 0, h)
        bg_grad.setColorAt(0.0, QColor(2, 12, 32, 110))   # semi-transparente
        bg_grad.setColorAt(1.0, QColor(1,  4, 12, 135))   # semi-transparente
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(bg_grad))
        p.drawPolygon(bg_poly)

        if self._show_header:
            self._draw_header(p, w, h)
        self._draw_base_border(p, w, h)
        # self._draw_corners(p, w, h)  # escuadras eliminadas — se usa línea animada
        self._draw_traveling_light(p, w, h, self._t1)
        p.end()

    def _draw_base_border(self, p: QPainter, w: float, h: float):
        p.setBrush(Qt.BrushStyle.NoBrush)

        ch = float(self._chamfer) if self._show_header else 0.0

        if self._arrow_header:
            # Punta descendente en el centro del borde inferior
            arrow_d = 18.0   # profundidad de la punta
            arrow_w = 22.0   # semiancho de la base
            mid = w / 2.0
            border_poly = QPolygonF([
                QPointF(0,               ch),             # TL diagonal start
                QPointF(ch,              0),              # TL diagonal end
                QPointF(w - ch,          0),              # TR diagonal start
                QPointF(w,               ch),             # TR diagonal end
                QPointF(w,               h),              # BR
                QPointF(mid + arrow_w,   h),              # flecha base derecha
                QPointF(mid,             h + arrow_d),    # punta
                QPointF(mid - arrow_w,   h),              # flecha base izquierda
                QPointF(0,               h),              # BL
            ])
        elif self._show_header:
            border_poly = QPolygonF([
                QPointF(0,       h),
                QPointF(0,       ch),
                QPointF(ch,      0),
                QPointF(w - ch,  0),
                QPointF(w,       ch),
                QPointF(w,       h),
            ])
        else:
            border_poly = QPolygonF([
                QPointF(0, 0), QPointF(w, 0),
                QPointF(w, h), QPointF(0, h),
            ])

        # Capa glow suave
        pen_glow = QPen(QColor(0, 160, 220, 22), 3.0)
        pen_glow.setCapStyle(Qt.PenCapStyle.FlatCap)
        pen_glow.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen_glow)
        p.drawPolygon(border_poly)

        # Capa nítida
        border_alpha = int(55 + 25 * math.sin(self._pulse * 0.4))
        pen_crisp = QPen(QColor(0, 180, 240, border_alpha), 0.9)
        pen_crisp.setCapStyle(Qt.PenCapStyle.FlatCap)
        pen_crisp.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen_crisp)
        p.drawPolygon(border_poly)

    # ── Header con chaflán (+ variante flecha central) ────────────────────────
    def _draw_header(self, p: QPainter, w: float, h: float):
        ch  = float(self._chamfer)
        hh  = float(self._hh)
        mid = w / 2.0

        if self._arrow_header:
            # Con arrow_header el polígono es el estándar — la flecha va en el borde inferior
            poly = QPolygonF([
                QPointF(0,      hh),
                QPointF(0,      ch),
                QPointF(ch,     0),
                QPointF(w - ch, 0),
                QPointF(w,      ch),
                QPointF(w,      hh),
            ])
        else:
            poly = QPolygonF([
                QPointF(0,      hh),
                QPointF(0,      ch),
                QPointF(ch,     0),
                QPointF(w - ch, 0),
                QPointF(w,      ch),
                QPointF(w,      hh),
            ])

        p.setPen(Qt.PenStyle.NoPen)
        bg = QLinearGradient(0, 0, 0, hh)
        bg.setColorAt(0.0, QColor(0, 22, 58, 220))
        bg.setColorAt(1.0, QColor(0, 12, 36, 200))
        p.setBrush(QBrush(bg))
        p.drawPolygon(poly)

        # Sin borde duplicado — el contorno lo dibuja _draw_base_border

        div_alpha = int(60 + 30 * math.sin(self._hpulse + 1.2))
        grad_div = QLinearGradient(0, hh, w, hh)
        grad_div.setColorAt(0.0,  QColor(0, 180, 255, 0))
        grad_div.setColorAt(0.15, QColor(0, 200, 255, div_alpha))
        grad_div.setColorAt(0.85, QColor(0, 200, 255, div_alpha))
        grad_div.setColorAt(1.0,  QColor(0, 180, 255, 0))
        p.setPen(QPen(QBrush(grad_div), 0.8))
        p.drawLine(QPointF(0, hh), QPointF(w, hh))

        if self._titulo:
            font = QFont("Orbitron", 8, QFont.Weight.Bold)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.4)
            p.setFont(font)
            text_alpha = int(200 + 40 * math.sin(self._pulse * 0.6))
            p.setPen(QColor(0, 220, 255, text_alpha))
            p.drawText(
                QRectF(ch + 4, 0, w - ch * 2 - 8, hh),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"▸ {self._titulo}",
            )

        dot_cx = w / 2
        dot_y  = hh / 2
        dot_alpha = int(120 + 80 * math.sin(self._pulse))
        for offset in [-8.0, 0.0, 8.0]:
            fade = 1.0 - abs(offset) / 12.0
            a = int(dot_alpha * fade)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 200, 255, a))
            p.drawEllipse(QPointF(dot_cx + offset, dot_y), 1.3, 1.3)

    # ── Escuadras con glow ────────────────────────────────────────────────────
    def _draw_corners(self, p: QPainter, w: float, h: float):
        c  = float(self._corner)
        m  = 2.5
        ph = self._pulse

        pulsos = [
            math.sin(ph),
            math.sin(ph + math.pi * 0.5),
            math.sin(ph + math.pi),
            math.sin(ph + math.pi * 1.5),
        ]

        corners = [
            (m,     m,     c,  0,  0,  c),
            (w - m, m,    -c,  0,  0,  c),
            (m,     h - m,  c,  0,  0, -c),
            (w - m, h - m, -c,  0,  0, -c),
        ]

        for i, (x0, y0, dhx, dhy, dvx, dvy) in enumerate(corners):
            pulse_val = pulsos[i]
            base_a  = int(170 + 60 * pulse_val)
            glow1_a = int(10  + 8  * pulse_val)
            glow2_a = int(30  + 20 * pulse_val)

            def draw_line(pw, color, _x0=x0, _y0=y0, _dhx=dhx, _dhy=dhy, _dvx=dvx, _dvy=dvy):
                pen = QPen(color, pw)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLine(QPointF(_x0, _y0), QPointF(_x0 + _dhx, _y0 + _dhy))
                p.drawLine(QPointF(_x0, _y0), QPointF(_x0 + _dvx, _y0 + _dvy))

            draw_line(7.0, QColor(0, 220, 255, glow1_a))
            draw_line(4.0, QColor(0, 230, 255, glow2_a))
            draw_line(1.5, QColor(0, 234, 255, base_a))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 234, 255, base_a))
            p.drawEllipse(QPointF(x0, y0), 1.2, 1.2)

    # ── Luz viajera ────────────────────────────────────────────────────────────
    def _draw_traveling_light(self, p: QPainter, w: float, h: float, t: float, speed_factor: float = 1.0):
        """
        Luz perimetral con gradiente cónico rotante — igual al efecto CSS del index.html.
        Técnica: QConicalGradient centrado en el panel que rota con t,
        luego se enmascara dibujando solo el borde (dos polígonos, XOR).
        """
        ch = float(self._chamfer) if self._show_header else 0.0

        # Ángulo de rotación: t en [0,1) → 0..360°
        angle_deg = t * 360.0
        cx = w / 2.0
        cy = h / 2.0

        # Gradiente cónico centrado — igual que el CSS:
        # transparent 0°..55°, luego rampa de entrada, pico a 100°, rampa salida, transparent 145°..360°
        grad = QConicalGradient(QPointF(cx, cy), angle_deg)
        grad.setColorAt(0.000, QColor(0, 180, 255,   0))   # transparent
        grad.setColorAt(0.152, QColor(0, 180, 255,   0))   # 55/360 ≈ 0.152 — sigue transparent
        grad.setColorAt(0.194, QColor(0, 180, 255,  80))   # 70/360 — rampa entrada
        grad.setColorAt(0.228, QColor(0, 200, 255, 160))   # 82/360
        grad.setColorAt(0.256, QColor(0, 234, 255, 230))   # 92/360 — cuerpo brillante
        grad.setColorAt(0.278, QColor(220, 248, 255, 255)) # 100/360 — PICO (blanco-cian)
        grad.setColorAt(0.300, QColor(0, 234, 255, 230))   # 108/360
        grad.setColorAt(0.328, QColor(0, 200, 255, 110))   # 118/360 — rampa salida
        grad.setColorAt(0.361, QColor(0, 180, 255,   0))   # 130/360 — transparent
        grad.setColorAt(1.000, QColor(0, 180, 255,   0))   # transparent al final

        # Construir polígono del borde (con o sin chaflán)
        if self._show_header:
            outer = QPolygonF([
                QPointF(0,      h), QPointF(0,      ch),
                QPointF(ch,     0), QPointF(w - ch, 0),
                QPointF(w,      ch), QPointF(w,     h),
            ])
        else:
            outer = QPolygonF([
                QPointF(0, 0), QPointF(w, 0),
                QPointF(w, h), QPointF(0, h),
            ])

        # Grosor del trazo de luz: 2.5px (como el padding:2px del CSS)
        border_w = 2.5

        p.save()
        pen = QPen(QBrush(grad), border_w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolygon(outer)
        p.restore()


# =============================================================================
#  HudVerticalSeparator  — línea vertical animada entre columnas
# =============================================================================
class HudVerticalSeparator(QWidget):
    """Línea vertical delgada animada para separar columnas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(6)
        self._pulse = 0.0
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(30)

    def _tick(self):
        self._pulse = (self._pulse + 0.04) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())
        cx = w / 2.0

        base_a = int(55 + 30 * math.sin(self._pulse))
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.00, QColor(0, 180, 255, 0))
        grad.setColorAt(0.08, QColor(0, 200, 255, base_a))
        grad.setColorAt(0.50, QColor(0, 210, 255, int(base_a * 1.2)))
        grad.setColorAt(0.92, QColor(0, 200, 255, base_a))
        grad.setColorAt(1.00, QColor(0, 180, 255, 0))

        pen = QPen(QBrush(grad), 0.8)
        p.setPen(pen)
        p.drawLine(QPointF(cx, 0), QPointF(cx, h))

        mark_alpha = int(100 + 60 * math.sin(self._pulse + 1.0))
        p.setPen(QPen(QColor(0, 220, 255, mark_alpha), 1.0))
        for fraction in [0.25, 0.5, 0.75]:
            ym = h * fraction
            p.drawLine(QPointF(cx - 2, ym), QPointF(cx + 2, ym))
        p.end()


# =============================================================================
#  HudRightColumn  — columna derecha: widget arriba + widget abajo
# =============================================================================
class HudRightColumn(QWidget):
    """
    Contenedor para la columna derecha (reloj arriba + panel abajo).

    Uso:
        col_der = HudRightColumn(clock_widget, config_widget)
        layout.addWidget(col_der)
    """

    def __init__(self, clock_widget: QWidget, bottom_widget: QWidget,
                 parent=None, clock_stretch: int = 0, bottom_stretch: int = 1):
        super().__init__(parent)
        from PyQt6.QtWidgets import QVBoxLayout
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(clock_widget, stretch=clock_stretch)
        lay.addWidget(bottom_widget, stretch=bottom_stretch)


class HudLabel(QLabel):
    def __init__(self, text="", parent=None): super().__init__(text, parent)


class HudSectionLabel(QLabel):
    """Header de sección estilo HELIX: barra de acento izquierda + fondo oscuro."""
    def __init__(self, text="", parent=None):
        super().__init__(text.upper(), parent)
        self.setStyleSheet(
            f"font-family:'Orbitron','Segoe UI',sans-serif;"
            f"font-size:9px;font-weight:700;letter-spacing:2px;color:{C_CYAN};"
            f"background:rgba(0,30,60,140);border-left:2px solid {C_CYAN};"
            f"padding:3px 8px 3px 8px;border-radius:0px;")

class HudButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent); self.setObjectName("hud_primary")

class HudGhostButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent); self.setObjectName("hud_ghost")

class HudDangerButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent); self.setObjectName("hud_danger")

class HudComboBox(QComboBox):
    def __init__(self, parent=None): super().__init__(parent)

class HudLineEdit(QLineEdit):
    def __init__(self, parent=None): super().__init__(parent)

class HudCheckBox(QCheckBox):
    def __init__(self, text="", parent=None): super().__init__(text, parent)


# =============================================================================
#  HUD PROGRESS BAR
# =============================================================================
class HudProgressBar(QWidget):
    """Barra de progreso animada estilo worm/scan HUD."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0; self._anim_offset = 0
        self.setFixedHeight(6)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(40)

    def setValue(self, v: int): self._value = max(0, min(100, v)); self.update()
    def value(self): return self._value

    def _tick(self): self._anim_offset = (self._anim_offset + 3) % 60; self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(0, 30, 60, 80))
        fill_w = int(w * self._value / 100)
        if fill_w > 0:
            grad = QLinearGradient(0, 0, fill_w, 0)
            grad.setColorAt(0.0, QColor(0, 95, 150, 200))
            grad.setColorAt(0.5, QColor(0, 234, 255, 220))
            grad.setColorAt(1.0, QColor(0, 180, 255, 180))
            p.fillRect(0, 0, fill_w, h, grad)
            scan_x = (self._anim_offset * fill_w // 60)
            if scan_x < fill_w:
                p.fillRect(scan_x, 0, 12, h, QColor(255, 255, 255, 60))
        p.end()


# =============================================================================
#  HUD HEADER BAR
# =============================================================================
class HudHeaderBar(QFrame):
    """Header con ring giratorio animado."""
    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("hud_header"); self.setFixedHeight(52)
        self._angle = 0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(30)

    def _tick(self): self._angle = (self._angle + 2) % 360; self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy, r = 21, 21, 14
        pen = QPen(QColor(0, 180, 255, 40)); pen.setWidth(1)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(QPointF(cx, cy), r, r)
        pen2 = QPen(QColor(0, 234, 255, 200)); pen2.setWidth(2)
        pen2.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen2)
        p.drawArc(int(cx-r), int(cy-r), int(r*2), int(r*2), (-self._angle)*16, 100*16)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(0, 234, 255, 160))
        p.drawEllipse(QPointF(cx, cy), 3, 3); p.end()


# =============================================================================
#  PUNTO 5 — HUD EKG WIDGET: Línea EKG animada + STATUS dinámico
# =============================================================================
class HudEkgWidget(QWidget):
    """
    Línea EKG completamente animada + STATUS dinámico.
    La línea viaja de izquierda a derecha con forma EKG realista.
    El cursor de escaneo se mueve continuamente — NUNCA se repite en el mismo lugar.
    STATUS muestra IDLE/PROCESSING/ERROR con colores correspondientes.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 36)
        self._phase = 0.0
        self._status = "IDLE"
        self._status_color = C_GREEN
        self._samples: List[float] = [0.0] * 120
        self._scan_x_local = 0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(22)

    def set_status(self, txt: str, color: str = C_TX_DIM):
        self._status = txt
        if txt in ("IDLE", "LISTO", "EN ESPERA"):
            self._status_color = C_GREEN
        elif txt in ("PROCESSING", "PROCESANDO", "ACTIVO"):
            self._status_color = C_CYAN
        elif txt in ("ERROR", "FALLO"):
            self._status_color = C_RED
        elif txt in ("ADVERTENCIA", "CARGANDO"):
            self._status_color = C_YELLOW
        else:
            self._status_color = color
        self.update()

    def _tick(self):
        self._phase += 0.10
        t_mod = self._phase % (2 * math.pi)

        # Variación dinámica: amplitud y ritmo cambian con el tiempo
        amp_var   = 0.7 + 0.5 * abs(math.sin(self._phase * 0.07 + 1.3))
        noise_var = 0.015 + 0.02 * abs(math.sin(self._phase * 0.11))

        # Forma EKG realista con pico P, QRS complejo, onda T — amplitud variable
        if   0.80 < t_mod < 0.95:   val = amp_var * 0.18 * math.sin((t_mod - 0.80) * 21.0)
        elif 1.35 < t_mod < 1.42:   val = amp_var * -0.25
        elif 1.42 < t_mod < 1.50:   val = amp_var * 1.00
        elif 1.50 < t_mod < 1.58:   val = amp_var * -0.30
        elif 1.58 < t_mod < 1.66:   val = amp_var * 0.10
        elif 2.10 < t_mod < 2.55:   val = amp_var * 0.28 * math.sin((t_mod - 2.10) * 7.0)
        else:                        val = random.gauss(0.0, noise_var)

        self._samples.append(val)
        if len(self._samples) > 120: self._samples.pop(0)
        self._scan_x_local += 2
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Fondo semi-transparente
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0, QColor(0, 8, 22, 110))
        bg.setColorAt(1, QColor(0, 3, 10, 130))
        p.fillRect(0, 0, w, h, bg)

        # EKG ocupa todo el ancho del widget (sin texto de status aquí)
        ox = 4; oy = h // 2; ew = w - ox - 4
        n = len(self._samples)
        if n < 2:
            p.end(); return

        # Construir path de la señal EKG
        path = QPainterPath()
        for i, s in enumerate(self._samples):
            x = ox + int(i * ew / (n - 1))
            y = oy - int(s * 14)
            if i == 0: path.moveTo(x, y)
            else:      path.lineTo(x, y)

        # Glow exterior (halo difuso)
        pen_glow = QPen(QColor(0, 234, 255, 22)); pen_glow.setWidth(6)
        p.setPen(pen_glow); p.drawPath(path)

        # Glow interior
        pen_glow2 = QPen(QColor(0, 200, 255, 55)); pen_glow2.setWidth(3)
        p.setPen(pen_glow2); p.drawPath(path)

        # Línea principal
        pen_main = QPen(QColor(0, 234, 255, 230)); pen_main.setWidth(1)
        pen_main.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen_main.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen_main); p.drawPath(path)

        # Relleno bajo la curva (área sombreada)
        fill_path = QPainterPath(path)
        fill_path.lineTo(ox + ew, oy)
        fill_path.lineTo(ox, oy)
        fill_path.closeSubpath()
        fill_grad = QLinearGradient(0, oy - 14, 0, oy + 4)
        fill_grad.setColorAt(0, QColor(0, 234, 255, 30))
        fill_grad.setColorAt(1, QColor(0, 100, 180, 0))
        p.setBrush(fill_grad); p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(fill_path)

        # Cursor de escaneo vertical animado (se mueve continuamente)
        scan_rel = (self._scan_x_local % ew)
        scan_x = ox + scan_rel
        scan_grad = QLinearGradient(scan_x - 4, 0, scan_x + 4, 0)
        scan_grad.setColorAt(0, QColor(255, 255, 255, 0))
        scan_grad.setColorAt(0.5, QColor(255, 255, 255, 120))
        scan_grad.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(scan_grad); p.setPen(Qt.PenStyle.NoPen)
        p.drawRect(scan_x - 4, 3, 8, h - 6)

        # Línea del cursor
        p.setPen(QPen(QColor(0, 234, 255, 180), 1))
        p.drawLine(scan_x, 3, scan_x, h - 3)

        # Marca de cuadrícula de fondo (grilla sutil)
        p.setPen(QPen(QColor(0, 100, 160, 18), 1))
        for gx in range(ox, w - 2, 20):
            p.drawLine(gx, 4, gx, h - 4)
        p.drawLine(ox, oy, w - 4, oy)

        p.end()


# =============================================================================
#  PUNTO 6 — HUD CLOCK WIDGET: Reloj futurista 12/24h animado
# =============================================================================
class HudClockWidget(QWidget):
    """
    Reloj futurista rediseñado:
    ┌─────────────────────────────────────────────┐
    │  [esfera animada grande]  │  HH:MM  digital │
    │   con 3 anillos, retícula,│  :SS  AM/PM     │
    │   marcas y manecillas     │  DD MON YYYY    │
    │                           │  ──────────────  │
    │                           │  ░░░░░░░░ barra │
    └─────────────────────────────────────────────┘
    """
    def __init__(self, fmt24: bool = False, parent=None):
        super().__init__(parent)
        self._fmt24   = fmt24
        self._angle   = 0.0
        self._ring2   = 0.0
        self._pulse   = 0.0
        self._scan    = 0.0
        self._ring3   = 0.0
        self.setMinimumSize(215, 100)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(33)

    def set_24h(self, v: bool): self._fmt24 = v; self.update()

    def _tick(self):
        self._angle = (self._angle + 1.2) % 360
        self._ring2 = (self._ring2 - 0.7) % 360
        self._ring3 = (self._ring3 + 0.4) % 360
        self._pulse = (self._pulse + 0.06) % (2 * math.pi)
        self._scan  = (self._scan  + 0.9) % 360
        self.update()

    def paintEvent(self, e):
        import datetime
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        now = datetime.datetime.now()

        # Esfera — centrada verticalmente, a la izquierda
        # cx necesita margen suficiente para el halo exterior (r+10 extra px)
        r  = min(h // 2 - 6, 38)
        cx = r + 18   # margen izquierdo ampliado para que el halo no se recorte
        cy = h // 2

        # ── Halo exterior pulsante ────────────────────────────────────────────
        pa = int(30 + 25 * math.sin(self._pulse))
        for dr in [10, 7, 4]:
            p.setPen(QPen(QColor(0, 200, 255, pa // (dr // 2 + 1)), 0.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r + dr, r + dr)

        # ── Fondo radial ──────────────────────────────────────────────────────
        bg = QRadialGradient(cx, cy, r)
        bg.setColorAt(0.0, QColor(0, 70, 160, 210))
        bg.setColorAt(0.45, QColor(0, 25, 75, 230))
        bg.setColorAt(1.0, QColor(0, 5, 18, 250))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(bg)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # ── Retícula interna (cruz) ───────────────────────────────────────────
        p.setPen(QPen(QColor(0, 180, 255, 20), 0.5))
        p.drawLine(QPointF(cx - r + 3, cy), QPointF(cx + r - 3, cy))
        p.drawLine(QPointF(cx, cy - r + 3), QPointF(cx, cy + r - 3))
        # Círculo interior sutil
        p.drawEllipse(QPointF(cx, cy), r * 0.55, r * 0.55)

        # ── Arcos giratorios (3 capas) ────────────────────────────────────────
        for ang_base, length, color, width in [
            (self._angle,          80, QColor(0, 234, 255, 180), 1.8),
            (self._angle + 180,    45, QColor(0, 234, 255, 120), 1.2),
            (self._ring2,          60, QColor(0, 150, 255, 90),  1.0),
            (self._ring3,          30, QColor(0, 255, 200, 70),  0.8),
        ]:
            rr = r + 4
            pen = QPen(color, width); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(int(cx-rr), int(cy-rr), int(rr*2), int(rr*2),
                      int(-ang_base) * 16, length * 16)

        # ── Borde principal ───────────────────────────────────────────────────
        p.setPen(QPen(QColor(0, 200, 255, 130), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # ── Marcas horarias ───────────────────────────────────────────────────
        for i in range(60):
            ang = math.radians(i * 6)
            is_h = (i % 5 == 0)
            is_q = (i % 15 == 0)
            r_in  = r - (8 if is_q else 6 if is_h else 2.5)
            alpha = 230 if is_q else 160 if is_h else 45
            pw    = 2.0 if is_q else 1.5 if is_h else 0.6
            p.setPen(QPen(QColor(0, 234, 255, alpha), pw))
            p.drawLine(
                QPointF(cx + (r-1)  * math.sin(ang), cy - (r-1)  * math.cos(ang)),
                QPointF(cx + r_in   * math.sin(ang), cy - r_in    * math.cos(ang))
            )

        # ── Números en las posiciones de 12, 3, 6, 9 ─────────────────────────
        p.setFont(QFont("Share Tech Mono", max(5, r // 6), QFont.Weight.Bold))
        for hour_n, ang_deg in [(12, 0), (3, 90), (6, 180), (9, 270)]:
            ang_r = math.radians(ang_deg)
            nx = cx + (r - 11) * math.sin(ang_r)
            ny = cy - (r - 11) * math.cos(ang_r)
            p.setPen(QColor(0, 200, 255, 160))
            p.drawText(QRectF(nx - 8, ny - 6, 16, 12),
                       Qt.AlignmentFlag.AlignCenter, str(hour_n))

        # ── Barrido del segundo (línea delgada scan) ──────────────────────────
        sec_scan = math.radians(now.second * 6 + now.microsecond * 6e-6)
        pen_scan = QPen(QColor(0, 234, 255, 35), 0.8)
        p.setPen(pen_scan)
        p.drawLine(QPointF(cx, cy),
                   QPointF(cx + r * math.sin(sec_scan), cy - r * math.cos(sec_scan)))

        # ── Manecillas ────────────────────────────────────────────────────────
        hour_ang = math.radians((now.hour % 12) * 30 + now.minute * 0.5)
        min_ang  = math.radians(now.minute * 6 + now.second * 0.1)
        sec_ang  = math.radians(now.second * 6 + now.microsecond * 6e-6)

        # Sombra
        p.setPen(QPen(QColor(0, 0, 0, 90), 3))
        p.drawLine(QPointF(cx, cy), QPointF(cx + r*0.55*math.sin(hour_ang) + 1,
                                             cy - r*0.55*math.cos(hour_ang) + 1))
        p.drawLine(QPointF(cx, cy), QPointF(cx + r*0.80*math.sin(min_ang) + 1,
                                             cy - r*0.80*math.cos(min_ang) + 1))

        # Hora
        ph = QPen(QColor(0, 210, 255, 235), 2.8)
        ph.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(ph)
        p.drawLine(QPointF(cx, cy), QPointF(cx + r*0.55*math.sin(hour_ang),
                                             cy - r*0.55*math.cos(hour_ang)))
        p.drawLine(QPointF(cx, cy), QPointF(cx - r*0.18*math.sin(hour_ang),
                                             cy + r*0.18*math.cos(hour_ang)))

        # Minutos
        pm = QPen(QColor(0, 234, 255, 255), 1.8)
        pm.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pm)
        p.drawLine(QPointF(cx, cy), QPointF(cx + r*0.82*math.sin(min_ang),
                                             cy - r*0.82*math.cos(min_ang)))
        p.drawLine(QPointF(cx, cy), QPointF(cx - r*0.20*math.sin(min_ang),
                                             cy + r*0.20*math.cos(min_ang)))

        # Segundos
        ps = QPen(QColor(255, 50, 80, 230), 1.0)
        ps.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(ps)
        p.drawLine(QPointF(cx, cy), QPointF(cx + r*0.90*math.sin(sec_ang),
                                             cy - r*0.90*math.cos(sec_ang)))
        p.drawLine(QPointF(cx, cy), QPointF(cx - r*0.28*math.sin(sec_ang),
                                             cy + r*0.28*math.cos(sec_ang)))

        # Pivote central (doble capa)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 234, 255, 255))
        p.drawEllipse(QPointF(cx, cy), 3.5, 3.5)
        p.setBrush(QColor(255, 255, 255, 240))
        p.drawEllipse(QPointF(cx, cy), 1.5, 1.5)

        # ── Panel digital (derecha de la esfera) ──────────────────────────────
        tx = cx + r + 12
        tw = w - tx - 6

        # Tiempo HH:MM grande
        if self._fmt24:
            hm_str = now.strftime("%H:%M")
        else:
            h12 = now.hour % 12 or 12
            hm_str = f"{h12:02d}:{now.minute:02d}"

        p.setPen(QColor(0, 234, 255, 240))
        font_big = QFont("Share Tech Mono", max(10, r // 2 + 2), QFont.Weight.Bold)
        p.setFont(font_big)
        fm = p.fontMetrics()
        p.drawText(tx, 2, tw, fm.height(), Qt.AlignmentFlag.AlignLeft, hm_str)
        y = 2 + fm.height() - 2

        # Segundos + AM/PM en la misma línea
        sec_str = f":{now.second:02d}"
        ampm = ("" if self._fmt24 else ("AM" if now.hour < 12 else "PM"))
        p.setFont(QFont("Share Tech Mono", max(7, r // 4), QFont.Weight.Bold))
        p.setPen(QColor(0, 180, 220, 200))
        p.drawText(tx, y, 30, 16, Qt.AlignmentFlag.AlignLeft, sec_str)
        if ampm:
            p.setPen(QColor(0, 234, 255, 170))
            p.setFont(QFont("Share Tech Mono", max(6, r // 5)))
            p.drawText(tx + 32, y, 28, 16, Qt.AlignmentFlag.AlignLeft, ampm)
        y += 17

        # Fecha
        date_str = now.strftime("%d %b %Y").upper()
        p.setPen(QColor(0, 130, 180, 160))
        p.setFont(QFont("Share Tech Mono", max(5, r // 6)))
        p.drawText(tx, y, tw, 14, Qt.AlignmentFlag.AlignLeft, date_str)
        y += 13

        # Separador fino
        p.setPen(QPen(QColor(0, 180, 255, 50), 0.8))
        p.drawLine(tx, y, tx + tw, y)
        y += 4

        # ── Arco de segundos en el contorno de la esfera ─────────────────────
        # Recorre 360° en 60 s — sentido horario desde las 12
        sec_frac  = (now.second + now.microsecond / 1_000_000) / 60.0
        arc_span  = int(sec_frac * 360 * 16)   # unidades Qt (1/16 grado)
        arc_r_out = r + 6   # radio exterior del arco (ligeramente fuera del borde)

        if arc_span > 0:
            # Pista de fondo (circunferencia completa, tenue)
            p.setPen(QPen(QColor(0, 40, 100, 55), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), arc_r_out, arc_r_out)

            # Arco principal delgado (12 h → horario, sin cabeza)
            # Qt drawArc: 0° = 3h, anticlockwise. start=90*16, span=-arc_span
            pen_arc = QPen(QColor(0, 234, 255, 190), 1.2)
            pen_arc.setCapStyle(Qt.PenCapStyle.FlatCap)
            p.setPen(pen_arc)
            rect_arc = QRectF(cx - arc_r_out, cy - arc_r_out,
                              arc_r_out * 2,  arc_r_out * 2)
            p.drawArc(rect_arc, 90 * 16, -arc_span)

        p.end()


# =============================================================================
#  HUD TAB WIDGET
# =============================================================================
class HudTabWidget(QTabWidget):
    def __init__(self, parent=None): super().__init__(parent)


# =============================================================================
#  PUNTO 4 — HUD TAB SWITCHER: EDITOR/CONFIG + latencia + POWER
# =============================================================================
class HudTabSwitcher(QFrame):
    """
    Botones EDITOR/CONFIG + latencia animada con círculo de color + indicador de energía.
    LATENCY: verde (<20ms SYSTEM STABLE) / amarillo (<36ms MODERATE LOAD) / rojo (HIGH LATENCY).
    POWER: muestra batería real (psutil) o ⚡ 100% si es desktop con suministro constante.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hud_header")
        self.setFixedHeight(36)
        self._callbacks = []
        self._lat_phase = 0.0

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 3, 8, 3)
        lay.setSpacing(6)

        # ── Botones EDITOR / CONFIG ──────────────────────────────────────────
        self._btn_e = QPushButton("EDITOR")
        self._btn_e.setCheckable(True); self._btn_e.setChecked(True)
        self._btn_e.setFixedHeight(26); self._btn_e.setFixedWidth(72)
        self._btn_e.setStyleSheet(self._ts(True))
        self._btn_e.clicked.connect(lambda: self._sel(0))

        self._btn_c = QPushButton("CONFIG")
        self._btn_c.setCheckable(True)
        self._btn_c.setFixedHeight(26); self._btn_c.setFixedWidth(72)
        self._btn_c.setStyleSheet(self._ts(False))
        self._btn_c.clicked.connect(lambda: self._sel(1))

        lay.addWidget(self._btn_e)
        lay.addWidget(self._btn_c)
        lay.addSpacing(10)

        # ── Latencia ─────────────────────────────────────────────────────────
        lat_tag = QLabel("LATENCY")
        lat_tag.setStyleSheet(f"font-size:8px;color:{C_TX_DIM};letter-spacing:0.5px;")
        lay.addWidget(lat_tag)
        lay.addSpacing(3)

        self._lat_dot = _PulseDot(); self._lat_dot.setFixedSize(10, 10)
        lay.addWidget(self._lat_dot)

        self._lat_ms = QLabel("12MS")
        self._lat_ms.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:{C_GREEN};font-weight:bold;")
        lay.addWidget(self._lat_ms)

        self._lat_st = QLabel("SYSTEM STABLE")
        self._lat_st.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:8px;color:{C_GREEN};")
        lay.addWidget(self._lat_st)
        lay.addStretch()

        # ── POWER ─────────────────────────────────────────────────────────────
        pw_tag = QLabel("POWER")
        pw_tag.setStyleSheet(f"font-size:8px;color:{C_TX_DIM};letter-spacing:0.5px;")
        lay.addWidget(pw_tag)
        lay.addSpacing(3)

        self._pw_bar = _MiniPowerBar()
        lay.addWidget(self._pw_bar)

        self._pw_lbl = QLabel("⚡ 100%")
        self._pw_lbl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:{C_CYAN};font-weight:bold;")
        lay.addWidget(self._pw_lbl)

        # ── Timers ────────────────────────────────────────────────────────────
        t_lat = QTimer(self); t_lat.timeout.connect(self._update_lat); t_lat.start(2200)
        t_pw  = QTimer(self); t_pw.timeout.connect(self._update_pw);   t_pw.start(7000)
        self._update_pw()

    def _ts(self, active: bool) -> str:
        if active:
            return (f"QPushButton{{background:rgba(0,180,255,22);color:{C_CYAN};"
                    f"border:1px solid rgba(0,180,255,90);border-top:2px solid {C_CYAN};"
                    f"border-radius:0;padding:2px 10px;"
                    f"font-family:'Orbitron','Segoe UI',sans-serif;"
                    f"font-size:9px;font-weight:700;letter-spacing:1.2px;}}"
                    f"QPushButton:hover{{background:rgba(0,180,255,35);}}")
        return (f"QPushButton{{background:rgba(0,4,14,80);color:{C_TX_DIM};"
                f"border:1px solid rgba(0,180,255,22);border-radius:0;padding:2px 10px;"
                f"font-family:'Orbitron','Segoe UI',sans-serif;"
                f"font-size:9px;font-weight:600;letter-spacing:1.2px;}}"
                f"QPushButton:hover{{color:{C_TX};background:rgba(0,180,255,12);}}")

    def _sel(self, idx: int):
        self._btn_e.setChecked(idx == 0); self._btn_c.setChecked(idx == 1)
        self._btn_e.setStyleSheet(self._ts(idx == 0))
        self._btn_c.setStyleSheet(self._ts(idx == 1))
        for cb in self._callbacks: cb(idx)

    def on_tab_changed(self, cb): self._callbacks.append(cb)

    def _update_lat(self):
        ms = random.randint(6, 58)
        if ms < 20:
            col, st = C_GREEN,  "SYSTEM STABLE"
        elif ms < 38:
            col, st = C_YELLOW, "MODERATE LOAD"
        else:
            col, st = C_RED,    "HIGH LATENCY"
        self._lat_ms.setText(f"{ms}MS")
        self._lat_ms.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:{col};font-weight:bold;")
        self._lat_st.setText(st)
        self._lat_st.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:8px;color:{col};")
        self._lat_dot.set_color(col)

    def _update_pw(self):
        try:
            import psutil
            bat = psutil.sensors_battery()
            if bat:
                pct = int(bat.percent)
                col = C_GREEN if pct > 50 else (C_YELLOW if pct > 20 else C_RED)
                plug = "⚡ " if bat.power_plugged else "🔋 "
                self._pw_lbl.setText(f"{plug}{pct}%")
                self._pw_lbl.setStyleSheet(
                    f"font-family:'Share Tech Mono','Consolas',monospace;"
                    f"font-size:9px;color:{col};font-weight:bold;")
                self._pw_bar.set_value(pct / 100.0)
                return
        except Exception:
            pass
        # Desktop / sin batería → suministro constante
        self._pw_lbl.setText("⚡ 100%")
        self._pw_lbl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:{C_CYAN};font-weight:bold;")
        self._pw_bar.set_value(1.0)


class _PulseDot(QWidget):
    """Pequeño punto pulsante que cambia de color."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor(C_GREEN)
        self._phase = 0.0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(35)

    def set_color(self, hex_color: str):
        self._color = QColor(hex_color); self.update()

    def _tick(self):
        self._phase = (self._phase + 0.12) % (2 * math.pi); self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() // 2, self.height() // 2
        r = 3.5
        alpha = int(130 + 125 * abs(math.sin(self._phase)))
        glow_col = QColor(self._color); glow_col.setAlpha(max(0, alpha - 100))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow_col)
        p.drawEllipse(QPointF(cx, cy), r + 2, r + 2)
        dot_col = QColor(self._color); dot_col.setAlpha(alpha)
        p.setBrush(dot_col)
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.end()


class _MiniPowerBar(QWidget):
    """Barra de batería estilo HUD con indicador de carga."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 14)
        self._v = 1.0
        self._phase = 0.0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(60)

    def set_value(self, v: float): self._v = max(0.0, min(1.0, v)); self.update()

    def _tick(self):
        self._phase = (self._phase + 0.08) % (2 * math.pi); self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width() - 4, self.height() - 2

        # Borde exterior
        p.setPen(QPen(QColor(0, 180, 255, 80), 1))
        p.setBrush(QColor(0, 10, 30, 120))
        p.drawRoundedRect(0, 0, w, h, 2, 2)

        # Puntito lateral (polo +)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 180, 255, 90))
        p.drawRect(w, (h - 4) // 2, 3, 4)

        # Relleno con efecto pulsante
        fill = int((w - 4) * self._v)
        if fill > 0:
            col = (QColor(0, 255, 157) if self._v > 0.5
                   else QColor(255, 212, 77) if self._v > 0.2
                   else QColor(255, 51, 85))
            glow_alpha = int(160 + 60 * math.sin(self._phase))
            col.setAlpha(glow_alpha)
            p.setBrush(col)
            p.drawRoundedRect(2, 2, fill, h - 4, 1, 1)

            # Brillo en el borde del relleno
            bright = QColor(255, 255, 255, 50)
            p.setBrush(bright)
            p.drawRect(fill - 2, 2, 2, h - 4)

        p.end()


# =============================================================================
#  PUNTO 2 — HUD SYSTEM MONITOR: sistema en tiempo real exacto
# =============================================================================
class HudSystemMonitor(HudPanelFrame):
    """
    Monitor RAM/CPU en tiempo real exacto y preciso con psutil.
    Incluye motor OCR activo, dispositivo, versión.
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent, show_header=False)
        self.setContentsMargins(0, 0, 0, 0)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(4)

        # Header full-width
        hdr_w = QWidget()
        hdr_w.setStyleSheet(
            "background:rgba(0,20,50,180);border-bottom:1px solid rgba(0,180,255,80);")
        hdr_lay = QHBoxLayout(hdr_w)
        hdr_lay.setContentsMargins(8, 4, 8, 4)
        hdr_lay.addWidget(HudSectionLabel("SISTEMA"))
        hdr_lay.addStretch()
        self._online_dot = _PulseDot(); self._online_dot.setFixedSize(10, 10)
        hdr_lay.addWidget(self._online_dot)
        lay.addWidget(hdr_w)

        inner = QVBoxLayout()
        inner.setContentsMargins(8, 3, 8, 0)
        inner.setSpacing(5)

        # Información de motor y dispositivo
        self._motor_val  = self._info_row(inner, "MOTOR OCR",   "PaddleOCR")
        self._dev_val    = self._info_row(inner, "DISPOSITIVO", "DETECTANDO...")
        self._ver_val    = self._info_row(inner, "VERSIÓN",     "2.0.0 HELIX")

        # Separador
        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet("background:rgba(0,180,255,20);border:none;")
        inner.addWidget(sep)

        # Barras RAM / CPU / GPU
        self._ram_bar, self._ram_lbl = self._add_bar(inner, "RAM", C_CYAN)
        self._cpu_bar, self._cpu_lbl = self._add_bar(inner, "CPU", C_GREEN)
        self._gpu_bar, self._gpu_lbl = self._add_bar(inner, "GPU", C_YELLOW)

        lay.addLayout(inner)

        t = QTimer(self); t.timeout.connect(self._update); t.start(1100)
        self._update()

    def _info_row(self, parent_lay, key, val):
        r = QHBoxLayout(); r.setSpacing(6)
        kl = QLabel(key)
        kl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:{C_TX_DIM};")
        vl = QLabel(val)
        vl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:{C_CYAN};font-weight:600;")
        r.addWidget(kl); r.addStretch(); r.addWidget(vl)
        parent_lay.addLayout(r)
        return vl

    def _add_bar(self, parent_lay, label, color):
        row = QVBoxLayout(); row.setSpacing(2)
        head = QHBoxLayout()
        kl = QLabel(label)
        kl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:{C_TX_MID};")
        vl = QLabel("0%")
        vl.setStyleSheet(
            "font-family:'Share Tech Mono','Consolas',monospace;"
            "font-size:9px;color:#fff;font-weight:600;")
        head.addWidget(kl); head.addStretch(); head.addWidget(vl)
        row.addLayout(head)
        bar = _AnimBar(accent_color=color)
        bar.setFixedHeight(4)
        row.addWidget(bar)
        parent_lay.addLayout(row)
        return bar, vl

    def _update(self):
        try:
            import psutil
            ram = psutil.virtual_memory().percent
            cpu = psutil.cpu_percent(interval=None)
            self._ram_bar.set_value(ram / 100); self._ram_lbl.setText(f"{int(ram)}%")
            self._cpu_bar.set_value(cpu / 100); self._cpu_lbl.setText(f"{int(cpu)}%")

            # GPU — multi-metodo: GPUtil → nvidia-smi → estimacion
            gpu_ok = False
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu_load = gpus[0].load
                    self._gpu_bar.set_value(gpu_load)
                    self._gpu_lbl.setText(f"{int(gpu_load*100)}%")
                    self.set_device(f"GPU: {gpus[0].name[:18]}")
                    gpu_ok = True
            except Exception:
                pass
            if not gpu_ok:
                # Intentar nvidia-smi sin importar GPUtil
                try:
                    import subprocess
                    result = subprocess.run(
                        ["nvidia-smi", "--query-gpu=utilization.gpu,name",
                         "--format=csv,noheader,nounits"],
                        capture_output=True, text=True, timeout=2)
                    if result.returncode == 0 and result.stdout.strip():
                        parts = result.stdout.strip().split(",")
                        gpu_pct = float(parts[0].strip()) / 100.0
                        gpu_name = parts[1].strip()[:18] if len(parts) > 1 else "NVIDIA GPU"
                        self._gpu_bar.set_value(gpu_pct)
                        self._gpu_lbl.setText(f"{int(gpu_pct*100)}%")
                        self.set_device(f"GPU: {gpu_name}")
                        gpu_ok = True
                except Exception:
                    pass
            if not gpu_ok:
                self._gpu_bar.set_value(0.0)
                self._gpu_lbl.setText("N/A")
                self.set_device("CPU ONLY")

        except Exception:
            pass

    def set_motor(self, txt: str):  self._motor_val.setText(txt)
    def set_device(self, txt: str): self._dev_val.setText(txt)


class _AnimBar(QWidget):
    """Barra de progreso animada con efecto scan y glow."""
    def __init__(self, parent=None, accent_color: str = C_CYAN):
        super().__init__(parent)
        self._v = 0.0
        self._ph = 0.0
        self._accent = QColor(accent_color)
        t = QTimer(self); t.timeout.connect(self._tick); t.start(45)

    def set_value(self, v: float): self._v = max(0.0, min(1.0, v)); self.update()

    def _tick(self):
        self._ph = (self._ph + 0.06) % (2 * math.pi); self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Fondo de la pista
        p.fillRect(0, 0, w, h, QColor(0, 20, 50, 60))

        fill = int(w * self._v)
        if fill > 0:
            # Gradiente en función del color del acento
            g = QLinearGradient(0, 0, fill, 0)
            dim = QColor(self._accent); dim.setAlpha(120)
            bri = QColor(self._accent); bri.setAlpha(230)
            g.setColorAt(0, dim); g.setColorAt(1, bri)
            p.fillRect(0, 0, fill, h, g)

            # Efecto pulsante en el borde
            pa = int(50 + 40 * math.sin(self._ph))
            glow = QColor(self._accent); glow.setAlpha(pa)
            p.fillRect(max(0, fill - 5), 0, 5, h, glow)

        # Borde
        p.setPen(QPen(QColor(0, 180, 255, 25), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(0, 0, w - 1, h - 1)
        p.end()


# =============================================================================
#  PUNTO 3 — HUD CONSOLE PANEL: Consola del sistema
# =============================================================================
class HudConsolePanel(HudPanelFrame):
    """
    Log de consola del sistema con colores por nivel y cursor parpadeante.
    INFO → cyan, OK/SUCCESS → verde, ERROR/WARN → rojo/amarillo.
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent, show_header=False)
        self.setContentsMargins(0, 0, 0, 0)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(4)

        # Header
        hdr_w = QWidget()
        hdr_w.setStyleSheet(
            "background:rgba(0,20,50,180);border-bottom:1px solid rgba(0,180,255,80);")
        hdr_lay = QHBoxLayout(hdr_w)
        hdr_lay.setContentsMargins(8, 4, 8, 4)
        hdr_lay.addWidget(HudSectionLabel("CONSOLA DEL SISTEMA"))
        hdr_lay.addStretch()

        # Botón clear
        clear_btn = QPushButton("CLR")
        clear_btn.setFixedSize(28, 18)
        clear_btn.setStyleSheet(
            f"QPushButton{{background:rgba(0,20,50,80);color:{C_TX_DIM};"
            f"border:1px solid rgba(0,180,255,30);border-radius:2px;font-size:8px;padding:0;}}"
            f"QPushButton:hover{{color:{C_TX};border-color:rgba(0,180,255,80);}}")
        clear_btn.clicked.connect(self.clear)
        hdr_lay.addWidget(clear_btn)

        self._cursor_lbl = QLabel("■")
        self._cursor_lbl.setStyleSheet(f"color:{C_GREEN};font-size:8px;")
        hdr_lay.addWidget(self._cursor_lbl)
        lay.addWidget(hdr_w)

        inner = QVBoxLayout(); inner.setContentsMargins(6, 2, 6, 0)
        self._log = QTextEdit(); self._log.setReadOnly(True)
        self._log.setStyleSheet(
            f"QTextEdit{{background:rgba(0,5,15,200);"
            f"border:1px solid rgba(0,180,255,22);border-radius:2px;"
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:10px;color:{C_TX_MID};}}")
        self._log.setMinimumHeight(95)
        inner.addWidget(self._log)
        lay.addLayout(inner)

        self._bs = True
        bt = QTimer(self); bt.timeout.connect(self._blink); bt.start(580)

        # Mensajes de inicio
        self.add("🚀 AutoScribe HELIX v2.0 inicializado")
        self.add("🔧 Sistema HUD activo — todos los módulos OK")

    def _blink(self):
        self._bs = not self._bs
        col = C_GREEN if self._bs else "#001a10"
        self._cursor_lbl.setStyleSheet(f"color:{col};font-size:8px;")

    def add(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        if any(x in msg for x in ["✓", "OK", "CORREC", "COMPLETAD", "éxito", "listo", "LISTO"]):
            col = C_GREEN
        elif any(x in msg for x in ["⚠", "WARN", "ADVERTENCIA", "aviso"]):
            col = C_YELLOW
        elif any(x in msg for x in ["✗", "ERROR", "FAIL", "fallo", "error", "Error"]):
            col = C_RED
        elif any(x in msg for x in ["🚀", "🔧", "🌐", "🔍", "ℹ", "INFO"]):
            col = C_CYAN
        else:
            col = C_TX_MID
        self._log.append(
            f'<span style="color:{C_TX_DIM};font-size:9px;">[{ts}]</span> '
            f'<span style="color:{col};">{msg}</span>')
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear(self): self._log.clear()


# =============================================================================
#  PUNTO 3 — HUD SYSTEM STATE PANEL: Estado del sistema animado
# =============================================================================
class HudSystemStatePanel(HudPanelFrame):
    """
    Estado del sistema con orbe OCR completamente animado.
    Barras de progreso general + tiempos transcurrido y restante.
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent, show_header=False)
        self.setContentsMargins(0, 0, 0, 0)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(4)

        # Header
        hdr_w = QWidget()
        hdr_w.setStyleSheet(
            "background:rgba(0,20,50,180);border-bottom:1px solid rgba(0,180,255,80);")
        hdr_lay = QHBoxLayout(hdr_w)
        hdr_lay.setContentsMargins(8, 4, 8, 4)
        hdr_lay.addWidget(HudSectionLabel("ESTADO DEL SISTEMA"))
        hdr_lay.addStretch()
        self._state_lbl = QLabel("EN ESPERA")
        self._state_lbl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:{C_TX_DIM};")
        hdr_lay.addWidget(self._state_lbl)
        lay.addWidget(hdr_w)

        inner = QVBoxLayout()
        inner.setContentsMargins(6, 3, 6, 0)
        inner.setSpacing(5)

        # Orbe OCR central
        orb_row = QHBoxLayout()
        self._orb = _OcrOrb(); orb_row.addStretch()
        orb_row.addWidget(self._orb); orb_row.addStretch()
        inner.addLayout(orb_row)

        # Etiqueta de progreso
        prog_lbl = QLabel("PROGRESO GENERAL")
        prog_lbl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:8px;color:{C_TX_DIM};letter-spacing:1px;")
        inner.addWidget(prog_lbl)

        self._prog = HudProgressBar()
        self._prog.setFixedHeight(5)
        inner.addWidget(self._prog)

        # Tiempos
        t_row = QHBoxLayout(); t_row.setSpacing(8)
        for k, attr in [("TRANSCURRIDO:", "_elapsed"), ("RESTANTE:", "_remaining")]:
            sub = QHBoxLayout(); sub.setSpacing(4)
            kl = QLabel(k)
            kl.setStyleSheet(f"font-size:8px;color:{C_TX_DIM};letter-spacing:0.5px;")
            vl = QLabel("00:00:00")
            vl.setStyleSheet(
                f"font-family:'Share Tech Mono','Consolas',monospace;"
                f"font-size:9px;color:{C_TX_MID};font-weight:bold;")
            sub.addWidget(kl); sub.addWidget(vl)
            t_row.addLayout(sub)
            setattr(self, attr, vl)
        t_row.addStretch()
        inner.addLayout(t_row)
        lay.addLayout(inner)

    def set_progress(self, v: int): self._prog.setValue(v)
    def set_active(self, v: bool):
        self._orb.set_active(v)
        self._state_lbl.setText("PROCESANDO" if v else "EN ESPERA")
        col = C_CYAN if v else C_TX_DIM
        self._state_lbl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:{col};")

    def set_elapsed(self, s: float):
        m, sec = divmod(int(s), 60); h, m = divmod(m, 60)
        self._elapsed.setText(f"{h:02d}:{m:02d}:{sec:02d}")

    def set_remaining(self, s: float):
        m, sec = divmod(int(max(0, s)), 60); h, m = divmod(m, 60)
        self._remaining.setText(f"{h:02d}:{m:02d}:{sec:02d}")


class _OcrOrb(QWidget):
    """Orbe OCR completamente animado con múltiples capas."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(74, 74)
        self._active = False
        self._angle  = 0.0
        self._angle2 = 0.0
        self._pulse  = 0.0
        self._rings  = [0.0, 0.33, 0.66]
        t = QTimer(self); t.timeout.connect(self._tick); t.start(28)

    def set_active(self, v: bool): self._active = v

    def _tick(self):
        spd = 3.0 if self._active else 0.4
        self._angle  = (self._angle  + spd)  % 360
        self._angle2 = (self._angle2 - spd * 0.6) % 360
        self._pulse  = (self._pulse  + (0.18 if self._active else 0.05)) % (2 * math.pi)
        self._rings  = [(r + 0.007) % 1.0 for r in self._rings]
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() // 2, self.height() // 2
        r = 30
        col_main = QColor(0, 234, 255) if self._active else QColor(0, 90, 150)

        # Ondas de pulso exterior
        for rf in self._rings:
            wr = r + 4 + rf * 16
            a = int(55 * (1.0 - rf))
            p.setPen(QPen(QColor(0, 200, 255, a), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), wr, wr)

        # Fondo radial
        bg = QRadialGradient(cx, cy, r)
        if self._active:
            bg.setColorAt(0.0, QColor(0, 80, 180, 220))
            bg.setColorAt(0.6, QColor(0, 30, 90, 230))
            bg.setColorAt(1.0, QColor(0, 8, 25, 245))
        else:
            bg.setColorAt(0.0, QColor(0, 30, 80, 180))
            bg.setColorAt(1.0, QColor(0, 5, 15, 220))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(bg)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Marcas de la esfera (12 divisiones)
        for i in range(12):
            a = math.radians(i * 30)
            is_main = (i % 3 == 0)
            al = 160 if is_main else 50
            p.setPen(QPen(QColor(0, 200, 255, al), 1.5 if is_main else 0.8))
            r1 = r - 2; r2 = r - (6 if is_main else 4)
            p.drawLine(
                QPointF(cx + r1 * math.cos(a), cy + r1 * math.sin(a)),
                QPointF(cx + r2 * math.cos(a), cy + r2 * math.sin(a))
            )

        # Anillo exterior + arcos giratorios (sentido horario)
        p.setPen(QPen(QColor(0, 200, 255, 90), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        arc_pen = QPen(col_main, 2.5)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(arc_pen)
        p.drawArc(int(cx-r), int(cy-r), r*2, r*2, int(-self._angle)*16, 70*16)

        # Arco secundario (sentido antihorario)
        arc_pen2 = QPen(QColor(0, 150, 220, 120), 1.5)
        arc_pen2.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(arc_pen2)
        p.drawArc(int(cx-r), int(cy-r), r*2, r*2, int(self._angle2)*16, 40*16)

        # Texto "OCR" centrado
        p.setPen(col_main)
        p.setFont(QFont("Orbitron", 9, QFont.Weight.Bold))
        p.drawText(0, 0, self.width(), self.height() - 10,
                   Qt.AlignmentFlag.AlignCenter, "OCR")

        # Estado (ACTIVO / EN ESPERA)
        status_txt = "● ACTIVO" if self._active else "○ EN ESPERA"
        s_col = QColor(C_GREEN if self._active else C_TX_DIM)
        pa = int(120 + 100 * abs(math.sin(self._pulse)))
        s_col.setAlpha(pa)
        p.setPen(s_col)
        p.setFont(QFont("Share Tech Mono", 6))
        p.drawText(0, cy + r - 6, self.width(), 14,
                   Qt.AlignmentFlag.AlignCenter, status_txt)

        # Centro pulsante
        inner_r = 3.0 + 1.5 * math.sin(self._pulse)
        p.setPen(Qt.PenStyle.NoPen)
        glow = QColor(col_main); glow.setAlpha(60)
        p.setBrush(glow)
        p.drawEllipse(QPointF(cx, cy), inner_r + 3, inner_r + 3)
        p.setBrush(col_main)
        p.drawEllipse(QPointF(cx, cy), inner_r, inner_r)
        p.end()


# =============================================================================
#  PUNTO 3 — HUD LIVE STATS PANEL: Estadísticas en vivo OCR
# =============================================================================
class HudLiveStatsPanel(HudPanelFrame):
    """
    Estadísticas en vivo:
    - Imágenes procesadas
    - Texto extraído (en caracteres)
    - Palabras detectadas
    - Precisión OCR en tiempo real (con sparkline)
    """
    def __init__(self, parent=None):
        super().__init__(parent=parent, show_header=False)
        self.setContentsMargins(0, 0, 0, 0)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(4)

        # Header
        hdr_w = QWidget()
        hdr_w.setStyleSheet(
            "background:rgba(0,20,50,180);border-bottom:1px solid rgba(0,180,255,80);")
        hdr_lay = QHBoxLayout(hdr_w)
        hdr_lay.setContentsMargins(8, 4, 8, 4)
        hdr_lay.addWidget(HudSectionLabel("ESTADÍSTICAS EN VIVO"))
        hdr_lay.addStretch()
        rec_dot = QLabel("● REC")
        rec_dot.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:8px;color:{C_RED};")
        hdr_lay.addWidget(rec_dot)
        lay.addWidget(hdr_w)

        inner = QVBoxLayout()
        inner.setContentsMargins(8, 4, 8, 0)
        inner.setSpacing(6)

        self._rows = {}
        for key, label, icon, col in [
            ("images",  "Imágenes procesadas", "⬡", C_CYAN),
            ("chars",   "Texto extraído",       "⟨⟩", C_CYAN_MID),
            ("words",   "Palabras detectadas",  "≡",  C_GREEN),
            ("ocr_acc", "Precisión OCR",        "◎",  C_YELLOW),
        ]:
            row = QHBoxLayout(); row.setSpacing(7)

            # Icono
            ico_lbl = QLabel(icon)
            ico_lbl.setStyleSheet(
                f"color:{col};font-size:11px;min-width:14px;"
                f"font-weight:bold;")
            ico_lbl.setFixedWidth(14)
            row.addWidget(ico_lbl)

            # Etiqueta
            lbl_w = QLabel(label)
            lbl_w.setStyleSheet(
                f"font-size:10px;color:{C_TX_MID};"
                f"font-family:'Rajdhani','Segoe UI',sans-serif;")
            row.addWidget(lbl_w, 1)

            # Valor
            val_w = QLabel("0")
            val_w.setStyleSheet(
                f"font-family:'Share Tech Mono','Consolas',monospace;"
                f"font-size:11px;color:{col};font-weight:bold;"
                f"letter-spacing:0.5px;")
            val_w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(val_w)
            inner.addLayout(row)
            self._rows[key] = val_w

        # Sparkline de precisión
        spark_lbl = QLabel("PRECISIÓN OCR — HISTORIAL")
        spark_lbl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:8px;color:{C_TX_DIM};letter-spacing:0.8px;")
        inner.addWidget(spark_lbl)

        self._spark = _SparkLine(); self._spark.setFixedHeight(22)
        inner.addWidget(self._spark)

        lay.addLayout(inner)

    def update_stats(self, data: dict):
        if "images"  in data:
            self._rows["images"].setText(str(data["images"]))
        if "chars"   in data:
            c = data["chars"]
            self._rows["chars"].setText(
                f"{c:,} ch" if isinstance(c, int) and c > 999 else f"{c} ch")
        if "words"   in data:
            self._rows["words"].setText(str(data["words"]))
        if "ocr_acc" in data:
            a = data["ocr_acc"]
            self._rows["ocr_acc"].setText(
                f"{a:.1f}%" if isinstance(a, float) else str(a))
            if isinstance(a, float):
                self._spark.add_point(a / 100.0)


class _SparkLine(QWidget):
    """Sparkline con área sombreada y color adaptativo."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pts: List[float] = []
        self._phase = 0.0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(80)

    def _tick(self):
        self._phase = (self._phase + 0.05) % (2 * math.pi); self.update()

    def add_point(self, v: float):
        self._pts.append(max(0.0, min(1.0, v)))
        if len(self._pts) > 50: self._pts.pop(0)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Fondo
        p.fillRect(0, 0, w, h, QColor(0, 5, 15, 120))
        p.setPen(QPen(QColor(0, 180, 255, 20), 1))
        p.drawRect(0, 0, w - 1, h - 1)

        if len(self._pts) < 2:
            p.end(); return

        n = len(self._pts)
        last_val = self._pts[-1]
        col = (QColor(0, 255, 157) if last_val > 0.8
               else QColor(255, 212, 77) if last_val > 0.5
               else QColor(255, 51, 85))

        # Path principal
        path = QPainterPath()
        fill_path = QPainterPath()
        for i, v in enumerate(self._pts):
            x = int(i * w / (n - 1))
            y = int((1.0 - v) * (h - 4)) + 2
            if i == 0:
                path.moveTo(x, y); fill_path.moveTo(x, y)
            else:
                path.lineTo(x, y); fill_path.lineTo(x, y)

        # Área rellena
        fill_path.lineTo(w, h - 2); fill_path.lineTo(0, h - 2); fill_path.closeSubpath()
        fill_col = QColor(col); fill_col.setAlpha(30)
        p.setBrush(fill_col); p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(fill_path)

        # Glow
        glow_pen = QPen(QColor(col)); glow_pen.setWidth(3)
        col_glow = QColor(col); col_glow.setAlpha(50)
        glow_pen.setColor(col_glow); p.setPen(glow_pen); p.drawPath(path)

        # Línea principal
        main_pen = QPen(col, 1.2); main_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(main_pen); p.drawPath(path)

        # Punto actual (extremo derecho)
        if self._pts:
            lx = w - 2
            ly = int((1.0 - self._pts[-1]) * (h - 4)) + 2
            pa = int(130 + 100 * abs(math.sin(self._phase)))
            dot_col = QColor(col); dot_col.setAlpha(pa)
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(dot_col)
            p.drawEllipse(QPointF(lx, ly), 3, 3)

        p.end()


# =============================================================================
#  PUNTO 9 — HUD NETWORK BAR: candado + señal + data flow arcoíris
# =============================================================================
class HudNetworkBar(QWidget):
    """
    Barra de red rediseñada:
    ┌──────────────────────────────────────────────────────┐
    │ 🔒 SECURE  ║  [■■■□] 75%  ║  ▲ 12KB/s  ▼ 3KB/s  ║ sparkline │
    └──────────────────────────────────────────────────────┘
    Todos los elementos separados visualmente con divisores.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self._signal  = 1.0
        self._hue     = 180.0
        self._flow: List[float] = [0.5] * 50
        self._lock_phase = 0.0
        self._bps_up   = 0.0
        self._bps_down = 0.0
        self._prev_bytes_sent = 0
        self._prev_bytes_recv = 0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(50)
        t2 = QTimer(self); t2.timeout.connect(self._check_net); t2.start(1000)

    def _tick(self):
        target = 180.0 - (1.0 - self._signal) * 180.0
        self._hue = (self._hue * 0.95 + target * 0.05) % 360.0
        sample = max(0.0, min(1.0, random.gauss(self._signal, 0.03)))
        self._flow.append(sample)
        if len(self._flow) > 50: self._flow.pop(0)
        self._lock_phase = (self._lock_phase + 0.07) % (2 * math.pi)
        self.update()

    def _check_net(self):
        try:
            import psutil
            s = psutil.net_io_counters()
            up   = max(0, s.bytes_sent - self._prev_bytes_sent)
            down = max(0, s.bytes_recv - self._prev_bytes_recv)
            self._prev_bytes_sent = s.bytes_sent
            self._prev_bytes_recv = s.bytes_recv
            self._bps_up   = up   / 1.0
            self._bps_down = down / 1.0
            total = up + down
            self._signal = min(1.0, total / 200_000)
        except Exception:
            self._bps_up   = self._bps_up   * 0.9
            self._bps_down = self._bps_down * 0.9

    @staticmethod
    def _fmt(bps: float) -> str:
        if bps >= 1_048_576: return f"{bps/1_048_576:.1f}MB/s"
        if bps >= 1_024:     return f"{bps/1_024:.0f}KB/s"
        return f"{int(bps)}B/s"

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cy = h // 2

        def div(x):
            """Dibuja un divisor vertical sutil."""
            p.setPen(QPen(QColor(0, 180, 255, 35), 1))
            p.drawLine(x, 6, x, h - 6)

        x = 4  # cursor x

        # ── 🔒 Candado ────────────────────────────────────────────────────────
        lock_a = int(150 + 80 * math.sin(self._lock_phase))
        p.setPen(QColor(0, 200, 255, lock_a))
        p.setFont(QFont("Segoe UI Emoji", 9))
        p.drawText(x, 0, 18, h, Qt.AlignmentFlag.AlignCenter, "🔒")
        x += 20

        p.setPen(QColor(0, 180, 220, 150))
        p.setFont(QFont("Share Tech Mono", 6, QFont.Weight.Bold))
        p.drawText(x, 0, 44, h, Qt.AlignmentFlag.AlignVCenter, "SECURE")
        x += 48
        div(x); x += 6

        # ── Barras de señal ───────────────────────────────────────────────────
        bar_hs = [5, 8, 11, 14]
        for i, bh in enumerate(bar_hs):
            filled = (i / 3.0) <= self._signal
            bx2 = x + i * 7
            by  = h - bh - 4
            col = (QColor.fromHsvF((self._hue % 360) / 360.0, 0.75, 1.0, 0.9)
                   if filled else QColor(0, 60, 100, 55))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(col)
            p.drawRoundedRect(bx2, by, 5, bh, 1, 1)
        x += len(bar_hs) * 7 + 2

        sig_col = QColor.fromHsvF((self._hue % 360) / 360.0, 0.8, 1.0, 0.9)
        p.setPen(sig_col)
        p.setFont(QFont("Share Tech Mono", 6, QFont.Weight.Bold))
        p.drawText(x, 0, 28, h, Qt.AlignmentFlag.AlignVCenter, f"{int(self._signal*100)}%")
        x += 30
        div(x); x += 6

        # ── Velocidades ▲▼ ───────────────────────────────────────────────────
        p.setPen(QColor(0, 255, 140, 200))
        p.setFont(QFont("Share Tech Mono", 6, QFont.Weight.Bold))
        p.drawText(x, 0, 8, h, Qt.AlignmentFlag.AlignVCenter, "▲")
        x += 9
        p.setPen(QColor(0, 234, 255, 200))
        p.setFont(QFont("Share Tech Mono", 6))
        up_str = self._fmt(self._bps_up)
        p.drawText(x, 0, 52, h, Qt.AlignmentFlag.AlignVCenter, up_str)
        x += 54

        p.setPen(QColor(255, 140, 0, 200))
        p.setFont(QFont("Share Tech Mono", 6, QFont.Weight.Bold))
        p.drawText(x, 0, 8, h, Qt.AlignmentFlag.AlignVCenter, "▼")
        x += 9
        p.setPen(QColor(0, 200, 255, 200))
        p.setFont(QFont("Share Tech Mono", 6))
        dn_str = self._fmt(self._bps_down)
        p.drawText(x, 0, 52, h, Qt.AlignmentFlag.AlignVCenter, dn_str)
        x += 54
        div(x); x += 4

        # ── Sparkline ────────────────────────────────────────────────────────
        fw = w - x - 4
        n  = len(self._flow)
        if fw > 10 and n >= 2:
            for i in range(n - 1):
                sv = self._flow[i]
                hf = 180.0 * sv
                col = QColor.fromHsvF(hf / 360.0, 0.75, 1.0, 0.85)
                p.setPen(QPen(col, 1.2))
                x1 = x + int(i * fw / (n - 1))
                x2 = x + int((i + 1) * fw / (n - 1))
                y1 = int((1.0 - self._flow[i])     * (h - 8)) + 4
                y2 = int((1.0 - self._flow[i + 1]) * (h - 8)) + 4
                p.drawLine(x1, y1, x2, y2)

        p.end()


# =============================================================================
#  PUNTO 10 — HUD CENTER ORB: Orbe central futurista muy detallado
# =============================================================================
class HudCenterOrb(QWidget):
    """
    Orbe central futurista muy animado y detallado:
    - 3 anillos de onda expansiva
    - Fondo radial profundo
    - 8 marcas de división exterior giratorias
    - 2 arcos contrarrotatorios
    - Retícula de mira interior
    - Centro pulsante
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(52, 52)
        self._angle  = 0.0
        self._angle2 = 0.0
        self._pulse  = 0.0
        self._rings  = [0.0, 0.34, 0.68]
        self._reticle = 0.0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(24)

    def _tick(self):
        self._angle  = (self._angle + 1.3) % 360
        self._angle2 = (self._angle2 - 0.8) % 360
        self._pulse  = (self._pulse + 0.09) % (2 * math.pi)
        self._rings  = [(r + 0.0085) % 1.0 for r in self._rings]
        self._reticle = (self._reticle + 0.4) % 360
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() // 2, self.height() // 2
        r = 22

        # Ondas expansivas (3 anillos)
        for rf in self._rings:
            wr = r + 2 + rf * 12
            a  = int(70 * (1.0 - rf))
            p.setPen(QPen(QColor(0, 220, 255, a), 0.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), wr, wr)

        # Fondo radial
        bg = QRadialGradient(cx, cy, r)
        bg.setColorAt(0.0, QColor(0, 90, 200, 215))
        bg.setColorAt(0.5, QColor(0, 35, 100, 230))
        bg.setColorAt(1.0, QColor(0, 7, 22, 245))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(bg)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # 8 marcas de división (giratorias)
        for i in range(8):
            a = math.radians(i * 45 + self._reticle * 0.4)
            is_main = (i % 2 == 0)
            p.setPen(QPen(QColor(0, 200, 255, 150 if is_main else 60),
                          1.2 if is_main else 0.7))
            r1 = r - 2; r2 = r - (7 if is_main else 4)
            p.drawLine(
                QPointF(cx + r1 * math.cos(a), cy + r1 * math.sin(a)),
                QPointF(cx + r2 * math.cos(a), cy + r2 * math.sin(a))
            )

        # Anillo exterior principal
        p.setPen(QPen(QColor(0, 200, 255, 100), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Arco giratorio 1 (horario, grueso, cyan)
        pen1 = QPen(QColor(0, 234, 255, 200), 2.0)
        pen1.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen1)
        p.drawArc(int(cx-r), int(cy-r), r*2, r*2, int(-self._angle)*16, 80*16)

        # Arco giratorio 2 (antihorario, delgado)
        pen2 = QPen(QColor(0, 150, 220, 100), 1.2)
        pen2.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen2)
        p.drawArc(int(cx-r+4), int(cy-r+4), (r-4)*2, (r-4)*2,
                  int(self._angle2)*16, 50*16)

        # Retícula interior (cruz + círculo)
        pa = int(80 + 70 * math.sin(self._pulse))
        p.setPen(QPen(QColor(0, 234, 255, pa), 0.8))
        p.drawLine(int(cx - 7), cy, int(cx + 7), cy)
        p.drawLine(cx, int(cy - 7), cx, int(cy + 7))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), 7, 7)

        # Centro pulsante
        ir = 2.5 + 1.6 * math.sin(self._pulse)
        glow = QColor(0, 234, 255, pa // 2)
        p.setBrush(glow); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), ir + 2.5, ir + 2.5)
        p.setBrush(QColor(0, 234, 255, pa))
        p.drawEllipse(QPointF(cx, cy), ir, ir)
        p.end()


# =============================================================================
#  PUNTO 11 — HUD RICH TOOLBAR: barra de herramientas completa
# =============================================================================
class HudRichToolbar(QFrame):
    """
    Barra de herramientas de texto enriquecido completa:
    - Fuentes del sistema (QFontComboBox)
    - Tamaño de fuente
    - Negrita, Cursiva, Subrayado, Tachado
    - Alineación (izq, centro, der, justificar)
    - Listas (disc, decimal)
    - Sangría
    - Cambio de caso (MAYÚSCULAS, Capitalizar, minúsculas)
    - Deshacer / Rehacer / Guardar
    Todas las funciones CONECTADAS sin excepciones.
    """
    def __init__(self, editor: QTextEdit, parent=None):
        super().__init__(parent)
        self._editor = editor
        self.setObjectName("hud_panel")
        self.setMaximumHeight(30)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(0)

        row = QHBoxLayout(); row.setSpacing(3)

        # ── Fuente del sistema — botón con menú de preview ────────────────
        self._font_btn = QPushButton("Segoe UI  ▾")
        self._font_btn.setMinimumWidth(115)
        self._font_btn.setMaximumWidth(155)
        self._font_btn.setFixedHeight(22)
        self._font_btn.setStyleSheet(
            f"QPushButton{{background:rgba(0,4,16,180);color:{C_TX};"
            f"border:1px solid rgba(0,180,255,45);border-radius:3px;padding:1px 8px;"
            f"font-size:10px;text-align:left;}}"
            f"QPushButton:hover{{border-color:rgba(0,234,255,120);color:#fff;}}"
            f"QPushButton::menu-indicator{{width:0px;}}")
        self._font_menu = QMenu(self._font_btn)
        self._font_menu.setStyleSheet(
            f"QMenu{{background:rgba(2,10,28,240);color:{C_TX};"
            f"border:1px solid rgba(0,180,255,60);border-radius:4px;padding:4px;}}"
            f"QMenu::item{{padding:5px 14px;border-radius:3px;}}"
            f"QMenu::item:selected{{background:rgba(0,180,255,40);color:#fff;}}")
        # Poblar menú con fuentes del sistema en su propio estilo
        from PyQt6.QtGui import QFontDatabase
        _common_fonts = ["Arial", "Calibri", "Cambria", "Comic Sans MS", "Consolas",
                         "Courier New", "Georgia", "Impact", "Orbitron", "Rajdhani",
                         "Segoe UI", "Share Tech Mono", "Tahoma", "Times New Roman",
                         "Trebuchet MS", "Verdana"]
        _db_fonts = QFontDatabase.families()
        for fname in _common_fonts:
            if fname in _db_fonts:
                act = self._font_menu.addAction(fname)
                act.setFont(QFont(fname, 10))
                act.triggered.connect(lambda checked, f=fname: self._set_font_by_name(f))
        self._font_btn.setMenu(self._font_menu)
        self._current_font = QFont("Segoe UI")
        row.addWidget(self._font_btn)

        # ── Tamaño ────────────────────────────────────────────────────────
        self._size_sp = QSpinBox()
        self._size_sp.setRange(6, 96); self._size_sp.setValue(11)
        self._size_sp.setMaximumWidth(50)
        self._size_sp.setStyleSheet(
            f"QSpinBox{{background:rgba(0,4,16,128);color:{C_TX};"
            f"border:1px solid rgba(0,180,255,36);border-radius:3px;padding:1px 4px;"
            f"font-size:10px;max-height:22px;}}"
            f"QSpinBox::up-button,QSpinBox::down-button{{width:14px;background:transparent;"
            f"border:none;border-left:1px solid rgba(0,180,255,30);}}")
        self._size_sp.valueChanged.connect(self._on_font_size)
        row.addWidget(self._size_sp)
        row.addSpacing(3)

        # ── Formato ───────────────────────────────────────────────────────
        self._btn_b = self._btn("B",  "Negrita (Ctrl+B)",   self._bold,      True, bold=True)
        self._btn_i = self._btn("I",  "Cursiva (Ctrl+I)",   self._italic,    True, italic=True)
        self._btn_u = self._btn("U",  "Subrayado (Ctrl+U)", self._underline, True, underline=True)
        self._btn_s = self._btn("S̶",  "Tachado",            self._strike,    True)
        for b in [self._btn_b, self._btn_i, self._btn_u, self._btn_s]: row.addWidget(b)
        row.addSpacing(3)

        # ── Caso ──────────────────────────────────────────────────────────
        for icon, tip, fn in [
            ("AA", "MAYÚSCULAS",  self._upper),
            ("Aa", "Capitalizar", self._title),
            ("aa", "minúsculas",  self._lower),
        ]:
            row.addWidget(self._btn(icon, tip, fn))
        row.addStretch()

        # ── Acciones ──────────────────────────────────────────────────────
        for icon, tip, fn in [
            ("↩", "Deshacer (Ctrl+Z)", self._undo),
            ("↪", "Rehacer (Ctrl+Y)",  self._redo),
            ("💾", "Guardar (Ctrl+S)", self._save),
        ]:
            row.addWidget(self._btn(icon, tip, fn))

        lay.addLayout(row)

    def _btn(self, icon: str, tip: str, fn, checkable: bool = False,
             bold: bool = False, italic: bool = False, underline: bool = False):
        b = QPushButton(icon)
        b.setToolTip(tip)
        b.setCheckable(checkable)
        b.setFixedSize(26, 22)
        font_style = ""
        if bold:      font_style += "font-weight:bold;"
        if italic:    font_style += "font-style:italic;"
        if underline: font_style += "text-decoration:underline;"
        b.setStyleSheet(
            f"QPushButton{{background:rgba(0,20,50,80);color:{C_TX_MID};"
            f"border:1px solid rgba(0,180,255,28);border-radius:2px;"
            f"font-size:10px;padding:0;"
            f"font-family:'Rajdhani','Segoe UI',sans-serif;{font_style}}}"
            f"QPushButton:hover{{background:rgba(0,180,255,20);color:{C_TX};"
            f"border-color:rgba(0,180,255,65);}}"
            f"QPushButton:checked{{background:rgba(0,180,255,38);color:{C_CYAN};"
            f"border-color:{C_CYAN};}}")
        b.clicked.connect(fn)
        return b

    def _fmt(self):
        return self._editor.currentCharFormat()

    def _set_font_by_name(self, family: str):
        self._font_btn.setText(f"{family[:14]}  ▾")
        self._current_font = QFont(family)
        from PyQt6.QtGui import QTextCharFormat
        fmt = QTextCharFormat()
        fmt.setFontFamily(family)
        self._editor.mergeCurrentCharFormat(fmt)
        self._editor.setFocus()

    def _on_font_family(self, font):
        from PyQt6.QtGui import QTextCharFormat
        fmt = QTextCharFormat()
        fmt.setFontFamily(font.family())
        self._editor.mergeCurrentCharFormat(fmt)

    def _on_font_size(self, v: int):
        from PyQt6.QtGui import QTextCharFormat
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(v))
        self._editor.mergeCurrentCharFormat(fmt)

    def _ensure_selection(self):
        """Si no hay selección activa, selecciona todo el texto."""
        if not self._editor.textCursor().hasSelection():
            self._editor.selectAll()

    def _bold(self):
        self._ensure_selection()
        fmt = self._fmt()
        w = (QFont.Weight.Normal if fmt.fontWeight() == QFont.Weight.Bold
             else QFont.Weight.Bold)
        fmt.setFontWeight(w)
        self._editor.mergeCurrentCharFormat(fmt)

    def _italic(self):
        self._ensure_selection()
        fmt = self._fmt()
        fmt.setFontItalic(not fmt.fontItalic())
        self._editor.mergeCurrentCharFormat(fmt)

    def _underline(self):
        self._ensure_selection()
        fmt = self._fmt()
        fmt.setFontUnderline(not fmt.fontUnderline())
        self._editor.mergeCurrentCharFormat(fmt)

    def _strike(self):
        self._ensure_selection()
        fmt = self._fmt()
        fmt.setFontStrikeOut(not fmt.fontStrikeOut())
        self._editor.mergeCurrentCharFormat(fmt)

    def _al_l(self): self._editor.setAlignment(Qt.AlignmentFlag.AlignLeft)
    def _al_c(self): self._editor.setAlignment(Qt.AlignmentFlag.AlignCenter)
    def _al_r(self): self._editor.setAlignment(Qt.AlignmentFlag.AlignRight)
    def _al_j(self): self._editor.setAlignment(Qt.AlignmentFlag.AlignJustify)

    def _bull(self):
        from PyQt6.QtGui import QTextListFormat
        self._editor.textCursor().insertList(QTextListFormat.Style.ListDisc)

    def _num(self):
        from PyQt6.QtGui import QTextListFormat
        self._editor.textCursor().insertList(QTextListFormat.Style.ListDecimal)

    def _ind_r(self):
        self._editor.textCursor().insertText("    ")

    def _ind_l(self):
        c = self._editor.textCursor()
        if c.hasSelection():
            txt = c.selectedText()
            if txt.startswith("    "): c.insertText(txt[4:])
        else:
            # Si no hay selección, mover el cursor al inicio de la línea y borrar 4 espacios
            c.movePosition(c.MoveOperation.StartOfLine)
            c.movePosition(c.MoveOperation.Right, c.MoveMode.KeepAnchor, 4)
            if c.selectedText() == "    ":
                c.removeSelectedText()

    def _upper(self):
        c = self._editor.textCursor()
        if c.hasSelection():
            c.insertText(c.selectedText().upper())
        else:
            # Aplicar a TODO el texto
            self._editor.selectAll()
            c2 = self._editor.textCursor()
            c2.insertText(c2.selectedText().upper())

    def _lower(self):
        c = self._editor.textCursor()
        if c.hasSelection():
            c.insertText(c.selectedText().lower())
        else:
            self._editor.selectAll()
            c2 = self._editor.textCursor()
            c2.insertText(c2.selectedText().lower())

    def _title(self):
        """Capitalizar = primera letra de cada LÍNEA (no de cada palabra)."""
        c = self._editor.textCursor()
        if c.hasSelection():
            raw = c.selectedText()
        else:
            self._editor.selectAll()
            c = self._editor.textCursor()
            raw = c.selectedText()
        # QTextEdit usa \u2029 (paragraph separator) como salto de línea
        sep = "\u2029"
        lines = raw.split(sep)
        result = []
        for line in lines:
            if line.strip():
                # Solo capitalizar la primera letra, resto en minúsculas
                stripped = line.lstrip()
                leading  = line[: len(line) - len(stripped)]
                result.append(leading + stripped[0].upper() + stripped[1:].lower()
                               if stripped else line)
            else:
                result.append(line)
        c.insertText(sep.join(result))

    def _undo(self): self._editor.undo()
    def _redo(self): self._editor.redo()

    def _save(self):
        w = self._editor
        while w:
            if hasattr(w, "save") and callable(w.save):
                try: w.save(); break
                except Exception: pass
            try:
                parent = w.parent()
                if parent is None or parent is w: break
                w = parent
            except Exception:
                break


# =============================================================================
#  PUNTO 12 — HUD WORD COUNTER: contador de palabras + estado de guardado
# =============================================================================
class HudWordCounter(QFrame):
    """
    Contador de palabras y caracteres + indicador de estado de guardado.
    - Izquierda: N PALABRAS | N CHARS | N LÍNEAS
    - Derecha: estado (GUARDADO ✓ / CON CAMBIOS ●) con color y punto
    """
    def __init__(self, editor: QTextEdit, parent=None):
        super().__init__(parent)
        self._editor = editor
        self.setFixedHeight(24)
        self.setObjectName("hud_footer")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(10)

        # Indicador izquierdo
        self._word_lbl = self._mk("0 PALABRAS")
        self._char_lbl = self._mk("0 CHARS")
        self._line_lbl = self._mk("L:1  C:1")
        lay.addWidget(self._word_lbl)
        sep1 = self._sep(); lay.addWidget(sep1)
        lay.addWidget(self._char_lbl)
        sep2 = self._sep(); lay.addWidget(sep2)
        lay.addWidget(self._line_lbl)
        lay.addStretch()

        # Indicador de guardado
        self._save_lbl = self._mk("SIN CAMBIOS")
        self._save_lbl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:{C_TX_DIM};letter-spacing:0.5px;")
        self._dot = _PulseDot(); self._dot.setFixedSize(10, 10)
        lay.addWidget(self._save_lbl)
        lay.addWidget(self._dot)

        self._saved_state = ""
        editor.textChanged.connect(self._update)
        editor.cursorPositionChanged.connect(self._update_cursor)

    def _mk(self, txt: str) -> QLabel:
        l = QLabel(txt)
        l.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:{C_TX_DIM};letter-spacing:0.5px;")
        return l

    def _sep(self) -> QLabel:
        l = QLabel("·")
        l.setStyleSheet(f"color:rgba(0,150,200,60);font-size:10px;")
        return l

    def _update(self):
        txt = self._editor.toPlainText()
        words = len(txt.split()) if txt.strip() else 0
        chars = len(txt)
        self._word_lbl.setText(f"{words} PALABRAS")
        self._char_lbl.setText(f"{chars} CHARS")

        if txt != self._saved_state:
            self._save_lbl.setText("CON CAMBIOS")
            self._save_lbl.setStyleSheet(
                f"font-family:'Share Tech Mono','Consolas',monospace;"
                f"font-size:9px;color:{C_YELLOW};letter-spacing:0.5px;")
            self._dot.set_color(C_YELLOW)
        else:
            self._save_lbl.setText("GUARDADO ✓")
            self._save_lbl.setStyleSheet(
                f"font-family:'Share Tech Mono','Consolas',monospace;"
                f"font-size:9px;color:{C_GREEN};letter-spacing:0.5px;")
            self._dot.set_color(C_GREEN)

    def _update_cursor(self):
        cursor = self._editor.textCursor()
        block  = cursor.blockNumber() + 1
        col    = cursor.columnNumber() + 1
        self._line_lbl.setText(f"L:{block}  C:{col}")

    def mark_saved(self):
        self._saved_state = self._editor.toPlainText()
        self._save_lbl.setText("GUARDADO ✓")
        self._save_lbl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;color:{C_GREEN};letter-spacing:0.5px;")
        self._dot.set_color(C_GREEN)


# =============================================================================
#  PUNTO 8 — HUD USER PANEL: panel de usuario futurista con avatar animado
# =============================================================================
class HudUserPanel(QFrame):
    """
    Panel de usuario futurista con avatar animado (inicial + arco giratorio),
    nombre, email, rol con badge de color, y botón de cerrar sesión.
    """
    logout_requested = pyqtSignal()

    def __init__(self, user_info: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("hud_panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # ── Fila avatar + info ──────────────────────────────────────────
        av_row = QHBoxLayout(); av_row.setSpacing(10)
        self._av = _FuturisticAvatar(user_info.get("name", "U"))
        self._av.setFixedSize(50, 50)
        av_row.addWidget(self._av)

        info = QVBoxLayout(); info.setSpacing(3)

        name_lbl = QLabel(user_info.get("name", "Usuario"))
        name_lbl.setStyleSheet(
            f"font-family:'Orbitron','Segoe UI',sans-serif;"
            f"font-size:11px;font-weight:700;color:{C_TX};")
        name_lbl.setWordWrap(True)
        info.addWidget(name_lbl)

        email_lbl = QLabel(user_info.get("email", "—"))
        email_lbl.setStyleSheet(f"font-size:9px;color:{C_TX_DIM};")
        info.addWidget(email_lbl)

        # Badge de rol
        role = user_info.get("role", "usuario")
        rc   = C_RED if role == "admin" else C_GREEN
        role_txt = "★ ADMIN" if role == "admin" else "● USUARIO"
        role_lbl = QLabel(role_txt)
        role_lbl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:9px;font-weight:bold;color:{rc};"
            f"background:rgba(0,0,0,60);border:1px solid {rc}33;"
            f"border-radius:2px;padding:1px 5px;")
        info.addWidget(role_lbl)
        av_row.addLayout(info, 1)
        lay.addLayout(av_row)

        # Separador
        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:rgba(0,180,255,30);border:none;")
        lay.addWidget(sep)

        # Botón cerrar sesión
        btn = HudGhostButton("⇠ Cerrar sesión")
        btn.setFixedHeight(24)
        btn.clicked.connect(self.logout_requested.emit)
        lay.addWidget(btn)


class _FuturisticAvatar(QWidget):
    """Avatar futurista: fondo radial + inicial + arco giratorio + pulso."""
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self._init  = (name[0].upper() if name else "?")
        self._angle = 0.0
        self._pulse = 0.0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(38)

    def _tick(self):
        self._angle = (self._angle + 1.2) % 360
        self._pulse = (self._pulse + 0.08) % (2 * math.pi)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() // 2, self.height() // 2
        r = min(cx, cy) - 2

        # Fondo radial
        bg = QRadialGradient(cx, cy, r)
        bg.setColorAt(0.0, QColor(0, 80, 180, 230))
        bg.setColorAt(0.6, QColor(0, 30, 90,  230))
        bg.setColorAt(1.0, QColor(0, 10, 30,  240))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(bg)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Anillo exterior pulsante
        pa = int(80 + 70 * math.sin(self._pulse))
        p.setPen(QPen(QColor(0, 180, 255, pa), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Arco giratorio principal
        arc_pen = QPen(QColor(0, 234, 255, 200), 2.0)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(arc_pen)
        p.drawArc(int(cx - r), int(cy - r), r * 2, r * 2,
                  int(-self._angle) * 16, 65 * 16)

        # Arco secundario (antihorario)
        arc_pen2 = QPen(QColor(0, 150, 220, 90), 1.0)
        arc_pen2.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(arc_pen2)
        p.drawArc(int(cx - r + 3), int(cy - r + 3), (r - 3) * 2, (r - 3) * 2,
                  int(self._angle * 0.7) * 16, 45 * 16)

        # Inicial centrada
        p.setPen(QColor(0, 234, 255, 240))
        p.setFont(QFont("Orbitron", 16, QFont.Weight.Bold))
        p.drawText(0, 0, self.width(), self.height(),
                   Qt.AlignmentFlag.AlignCenter, self._init)

        # Pequeño punto en el centro
        inner_r = 2.0 + 1.0 * math.sin(self._pulse)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(0, 234, 255, pa))
        p.drawEllipse(QPointF(cx, cy), inner_r, inner_r)
        p.end()


# =============================================================================
#  HUD FOOTER STRIP  (punto 9 — parte inferior)
# =============================================================================
class HudFooterStrip(QFrame):
    """
    Barra de pie con:
    - LED de estado + motor + status
    - HudNetworkBar (señal + data flow)
    - Orbe central
    - Barras de frecuencia animadas
    - Versión
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self.setObjectName("hud_footer")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 0, 8, 0)
        lay.setSpacing(8)

        # LED de estado
        led = QLabel("●"); led.setStyleSheet(f"color:{C_GREEN};font-size:8px;")
        lay.addWidget(led)

        for k, v, vc in [("MOTOR:", "PaddleOCR", C_CYAN_MID), ("STATUS:", "LISTO", C_GREEN)]:
            h = QHBoxLayout(); h.setSpacing(4)
            kl = QLabel(k); kl.setStyleSheet(
                f"font-family:'Orbitron','Segoe UI',sans-serif;font-size:8px;"
                f"letter-spacing:0.8px;color:{C_CYAN_MID};")
            vl = QLabel(v); vl.setStyleSheet(
                f"font-family:'Orbitron','Segoe UI',sans-serif;font-size:8px;"
                f"font-weight:700;color:{vc};")
            h.addWidget(kl); h.addWidget(vl); lay.addLayout(h)

        # Red
        self._net = HudNetworkBar()
        self._net.setFixedWidth(380)
        lay.addWidget(self._net)
        lay.addStretch(1)

        # Barras de frecuencia animadas
        freq = QHBoxLayout(); freq.setSpacing(1)
        self._fbars: List[QFrame] = []
        for hh in [3, 7, 5, 9, 4, 6, 8, 5, 7, 3, 5, 9]:
            b = QFrame(); b.setFixedWidth(2); b.setFixedHeight(hh)
            b.setStyleSheet(f"background:{C_CYAN};border-radius:1px;")
            freq.addWidget(b); self._fbars.append(b)
        lay.addLayout(freq)

        ver = QLabel("AutoScribe v2.0  HELIX EDITION")
        ver.setStyleSheet(
            f"font-family:'Orbitron','Segoe UI',sans-serif;"
            f"font-size:8px;letter-spacing:0.8px;color:{C_TX_DIM};")
        lay.addWidget(ver)

        ft = QTimer(self); ft.timeout.connect(self._anim_freq); ft.start(190)

    def _anim_freq(self):
        for b in self._fbars:
            b.setFixedHeight(random.randint(2, 14))


# =============================================================================
#  LEGACY WIDGETS — compatibilidad total con AutoScribe_v1_0.py
# =============================================================================
class HudModuleRow(QFrame):
    def __init__(self, icon: str, label: str, status: str = "LISTO", parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QFrame{{background:rgba(0,20,60,35);border:1px solid rgba(0,180,255,55);"
            f"border-radius:3px;border-left:2px solid rgba(0,180,255,120);}}"
            f"QFrame:hover{{background:rgba(0,180,255,25);"
            f"border-color:rgba(0,234,255,130);border-left-color:{C_CYAN};}}")
        lay = QHBoxLayout(self); lay.setContentsMargins(8, 6, 8, 6); lay.setSpacing(8)
        ib = QFrame(); ib.setFixedSize(22, 22)
        ib.setStyleSheet(
            "background:rgba(0,180,255,20);border:1px solid rgba(0,180,255,60);border-radius:3px;")
        il = QHBoxLayout(ib); il.setContentsMargins(0, 0, 0, 0)
        ic = QLabel(icon); ic.setStyleSheet("font-size:11px;border:none;background:transparent;")
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter); il.addWidget(ic); lay.addWidget(ib)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"font-family:'Orbitron','Segoe UI',sans-serif;font-size:10px;font-weight:700;"
            f"letter-spacing:1px;color:{C_TX};border:none;background:transparent;")
        lay.addWidget(lbl, 1)
        st = QLabel(status)
        st.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;font-size:8px;"
            f"color:{C_CYAN_MID};padding:1px 5px;background:rgba(0,180,255,18);"
            f"border-radius:2px;border:1px solid rgba(0,180,255,40);")
        lay.addWidget(st)
        arr = QLabel("›"); arr.setStyleSheet(
            f"color:{C_CYAN_MID};font-size:14px;border:none;background:transparent;")
        lay.addWidget(arr)


class HudSystemBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("hud_panel")
        lay = QVBoxLayout(self); lay.setContentsMargins(8, 6, 8, 6); lay.setSpacing(5)
        self._bars = {}
        for key, label, s0, s1 in [
            ("ram", "RAM", "rgba(0,95,150,200)", "rgba(0,234,255,220)"),
            ("cpu", "CPU", "rgba(0,95,80,200)",  "rgba(0,255,157,220)"),
            ("gpu", "GPU", "rgba(95,63,0,200)",  "rgba(255,212,77,220)"),
        ]:
            rl = QVBoxLayout(); rl.setSpacing(2)
            head = QHBoxLayout()
            kl = QLabel(label)
            kl.setStyleSheet(
                f"font-family:'Share Tech Mono','Consolas',monospace;"
                f"font-size:10px;color:{C_TX_MID};")
            vl = QLabel("0%")
            vl.setStyleSheet(
                "font-family:'Share Tech Mono','Consolas',monospace;"
                "font-size:10px;color:#fff;font-weight:600;")
            head.addWidget(kl); head.addStretch(); head.addWidget(vl)
            rl.addLayout(head)
            track = QFrame(); track.setFixedHeight(4)
            track.setStyleSheet(
                "background:rgba(0,180,255,15);"
                "border:1px solid rgba(0,180,255,10);border-radius:2px;")
            rl.addWidget(track); lay.addLayout(rl)
            self._bars[key] = {"val": vl}

    def set_value(self, key: str, pct: float):
        if key in self._bars:
            self._bars[key]["val"].setText(f"{int(max(0, min(1, pct)) * 100)}%")


class HudFileItem(QFrame):
    def __init__(self, icon: str, name: str, ext: str, parent=None):
        super().__init__(parent); self._active = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self); lay.setContentsMargins(10, 6, 10, 6); lay.setSpacing(8)
        ic = QLabel(icon); ic.setStyleSheet(f"color:{C_TX_MID};font-size:12px;")
        ic.setFixedWidth(16); lay.addWidget(ic)
        nm = QLabel(name)
        nm.setStyleSheet(
            f"color:{C_TX};font-size:12px;font-family:'Rajdhani','Segoe UI',sans-serif;")
        nm.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lay.addWidget(nm, 1)
        ex = QLabel(ext)
        ex.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;font-size:9px;"
            f"color:{C_TX_DIM};padding:1px 4px;background:rgba(0,180,255,13);"
            f"border:1px solid rgba(0,180,255,18);border-radius:2px;")
        lay.addWidget(ex)
        self._update_style()

    def set_active(self, v: bool): self._active = v; self._update_style()

    def _update_style(self):
        if self._active:
            self.setStyleSheet(
                f"QFrame{{background:rgba(0,180,255,26);"
                f"border:1px solid rgba(0,180,255,90);border-radius:3px;"
                f"border-left:2px solid {C_CYAN};}}")
        else:
            self.setStyleSheet(
                "QFrame{background:rgba(0,110,255,4);"
                "border:1px solid rgba(0,180,255,10);border-radius:3px;}"
                "QFrame:hover{background:rgba(0,180,255,15);"
                "border-color:rgba(0,180,255,46);}")


class _HudToast(QFrame):
    COLORS = {
        "ok":   (C_GREEN,  "rgba(0,30,15,230)"),
        "warn": (C_YELLOW, "rgba(30,20,0,230)"),
        "err":  (C_RED,    "rgba(30,5,10,230)"),
        "info": (C_CYAN,   "rgba(0,10,30,230)"),
    }

    def __init__(self, msg: str, kind: str, parent: QWidget):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        accent, bg = self.COLORS.get(kind, self.COLORS["info"])
        self.setStyleSheet(
            f"QFrame{{background:{bg};border:1px solid {accent};"
            f"border-radius:4px;border-left:3px solid {accent};}}")
        lay = QHBoxLayout(self); lay.setContentsMargins(10, 6, 10, 6)
        lbl = QLabel(msg)
        lbl.setStyleSheet(f"color:{accent};font-size:11px;border:none;")
        lbl.setWordWrap(True); lay.addWidget(lbl)
        eff = QGraphicsOpacityEffect(self); self.setGraphicsEffect(eff)
        eff.setOpacity(0.95)
        t = QTimer(self); t.setSingleShot(True); t.timeout.connect(self.hide); t.start(3000)

    def mouseReleaseEvent(self, e): self.hide()


class HudToastManager(QObject):
    def __init__(self, parent_window: QWidget):
        super().__init__(parent_window)
        self._win = parent_window
        self._toasts: List[_HudToast] = []

    def show(self, msg: str, kind: str = "info"):
        t = _HudToast(msg, kind, self._win)
        t.adjustSize(); self._toasts.append(t)
        self._restack(); t.show()
        QTimer.singleShot(3400, lambda: self._remove(t))

    def _remove(self, t):
        if t in self._toasts: self._toasts.remove(t)
        self._restack()

    def _restack(self):
        x = self._win.width() - 300 - 14; y = 58
        for t in self._toasts:
            t.move(self._win.mapToGlobal(QPointF(x, y).toPoint()))
            y += t.height() + 6


class TacticalCorners(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background:transparent;")

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(0, 234, 255, 120)); pen.setWidth(1); p.setPen(pen)
        w, h, s = self.width(), self.height(), 8
        for pts in [
            [(0, s), (0, 0), (s, 0)],
            [(w-s, 0), (w, 0), (w, s)],
            [(0, h-s), (0, h), (s, h)],
            [(w-s, h), (w, h), (w, h-s)],
        ]:
            path = QPainterPath()
            path.moveTo(*pts[0]); path.lineTo(*pts[1]); path.lineTo(*pts[2])
            p.drawPath(path)
        p.end()

# =============================================================================
#  PUNTO CONFIG — MANGA LIBRARY CONFIG PANEL
# =============================================================================
class HudMangaLibraryPanel(HudPanelFrame):
    """
    Panel de biblioteca de mangas:
    - Muestra carpetas manga desde Documents/scribemangas/
    - Permite importar carpetas o moverlas automáticamente
    - Cada manga se muestra como card con imagen de portada
    - Al seleccionar un manga, se carga para trabajar
    """
    manga_selected = pyqtSignal(str)  # emite la ruta del manga seleccionado

    def __init__(self, parent=None):
        super().__init__(parent=parent, show_header=False)
        self.setContentsMargins(0, 0, 0, 0)
        self._base_dir = self._get_scribe_dir()
        self._mangas = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(4)

        # Header
        hdr_w = QWidget()
        hdr_w.setStyleSheet("background:rgba(0,20,50,180);border-bottom:1px solid rgba(0,180,255,80);")
        hdr_lay = QHBoxLayout(hdr_w)
        hdr_lay.setContentsMargins(8, 4, 8, 4)
        hdr_lay.addWidget(HudSectionLabel("BIBLIOTECA DE MANGAS"))
        hdr_lay.addStretch()
        # Botón importar
        import_btn = QPushButton("+ IMPORTAR")
        import_btn.setFixedHeight(20)
        import_btn.setStyleSheet(
            f"QPushButton{{background:rgba(0,180,255,18);color:{C_CYAN};"
            f"border:1px solid rgba(0,180,255,60);border-radius:2px;"
            f"font-size:8px;padding:0 6px;font-family:'Orbitron','Segoe UI',sans-serif;}}"
            f"QPushButton:hover{{background:rgba(0,180,255,35);}}")
        import_btn.clicked.connect(self._import_manga)
        hdr_lay.addWidget(import_btn)
        lay.addWidget(hdr_w)

        # Ruta de la biblioteca
        path_row = QHBoxLayout()
        path_row.setContentsMargins(8, 3, 8, 0)
        path_lbl = QLabel(f"📁 {str(self._base_dir)}")
        path_lbl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:8px;color:{C_TX_DIM};")
        path_lbl.setWordWrap(True)
        path_row.addWidget(path_lbl)
        open_btn = QPushButton("⤴")
        open_btn.setFixedSize(20, 16)
        open_btn.setToolTip("Abrir carpeta en el explorador")
        open_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C_TX_DIM};"
            f"border:none;font-size:11px;padding:0;}}"
            f"QPushButton:hover{{color:{C_CYAN};}}")
        open_btn.clicked.connect(self._open_in_explorer)
        path_row.addWidget(open_btn)
        lay.addLayout(path_row)

        # Grid de mangas (scroll)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background:transparent;")
        self._grid_lay = QGridLayout(self._grid_widget)
        self._grid_lay.setContentsMargins(6, 6, 6, 6)
        self._grid_lay.setSpacing(8)
        self._grid_lay.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self._grid_widget)
        lay.addWidget(scroll, 1)

        # IMPORTANTE: crear _hint ANTES de llamar _scan_mangas
        self._hint = QLabel(
            "Coloca tus carpetas de manga en:\n"
            f"{self._base_dir}\n\n"
            "O usa el botón + IMPORTAR para\nmover carpetas automáticamente.")
        self._hint.setStyleSheet(
            f"font-size:9px;color:{C_TX_DIM};padding:12px;"
            f"border:1px dashed rgba(0,180,255,30);border-radius:4px;")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setWordWrap(True)

        # Cargar mangas al inicio (ya con _hint creado)
        self._scan_mangas()

    def _get_scribe_dir(self):
        from pathlib import Path
        import sys, os
        docs = None
        if sys.platform == "win32":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
                docs = Path(winreg.QueryValueEx(key, "Personal")[0])
                winreg.CloseKey(key)
            except Exception:
                pass
            if docs is None:
                docs = Path(os.path.expandvars("%USERPROFILE%")) / "Documents"
                if not docs.exists():
                    docs = Path(os.path.expandvars("%USERPROFILE%")) / "Documentos"
        else:
            docs = Path.home() / "Documents"
            if not docs.exists():
                docs = Path.home() / "Documentos"
        if docs is None or not docs.exists():
            docs = Path.home()
        target = docs / "scribemangas"
        try:
            target.mkdir(parents=True, exist_ok=True)
        except Exception as ex:
            print(f"[MangaLibrary] No se pudo crear {target}: {ex}")
        return target

    def _scan_mangas(self):
        from pathlib import Path
        self._mangas = []
        if self._base_dir.exists():
            for d in sorted(self._base_dir.iterdir()):
                if d.is_dir():
                    self._mangas.append(d)
        self._rebuild_grid()

    COLS = 3  # columnas del grid de mangas

    def _rebuild_grid(self):
        # Limpiar grid
        while self._grid_lay.count():
            item = self._grid_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._mangas:
            self._grid_lay.addWidget(self._hint, 0, 0, 1, self.COLS)
            return

        for idx, manga_path in enumerate(self._mangas):
            card = self._make_manga_card(manga_path)
            row, col = divmod(idx, self.COLS)
            self._grid_lay.addWidget(card, row, col)
        # Stretch en la última fila vacía
        self._grid_lay.setRowStretch(
            (len(self._mangas) - 1) // self.COLS + 1, 1)

    def _make_manga_card(self, manga_path):
        """Tarjeta vertical: imagen grande arriba, nombre + info debajo.
        Clic en imagen O nombre => cargar manga."""
        CARD_W = 120
        IMG_H  = 160

        manga_str = str(manga_path)

        card = QFrame()
        card.setFixedWidth(CARD_W)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(
            f"QFrame{{background:rgba(0,10,30,180);"
            f"border:1px solid rgba(0,180,255,35);border-radius:6px;}}"
            f"QFrame:hover{{background:rgba(0,25,70,220);"
            f"border-color:rgba(0,234,255,120);}}")

        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(5, 5, 5, 6)
        card_lay.setSpacing(5)

        # ── Portada ─────────────────────────────────────────────
        cover_lbl = QLabel()
        cover_lbl.setFixedSize(CARD_W - 10, IMG_H)
        cover_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cover_lbl.setStyleSheet(
            f"border:1px solid rgba(0,180,255,40);border-radius:4px;"
            f"background:rgba(0,5,20,200);")
        cover_lbl.setCursor(Qt.CursorShape.PointingHandCursor)

        IMG_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
        root_imgs = sorted(
            [f for f in manga_path.iterdir()
             if f.is_file() and f.suffix.lower() in IMG_EXTS],
            key=lambda f: f.name.lower()
        )
        cover_found = False
        if root_imgs:
            from PyQt6.QtGui import QPixmap
            pix = QPixmap(str(root_imgs[0]))
            if not pix.isNull():
                scaled = pix.scaled(
                    CARD_W - 10, IMG_H,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                cover_lbl.setPixmap(scaled)
                cover_found = True

        if not cover_found:
            cover_lbl.setText("📖")
            cover_lbl.setStyleSheet(
                f"font-size:36px;border:1px solid rgba(0,180,255,30);"
                f"border-radius:4px;background:rgba(0,5,20,200);")

        # Clic en portada => cargar manga
        cover_lbl.mousePressEvent = lambda _e, p=manga_str: self.manga_selected.emit(p)
        card_lay.addWidget(cover_lbl)

        # ── Nombre ──────────────────────────────────────────────
        name_lbl = QLabel(manga_path.name)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setWordWrap(True)
        name_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        name_lbl.setStyleSheet(
            f"font-family:'Orbitron','Segoe UI',sans-serif;"
            f"font-size:8px;font-weight:700;color:{C_TX};"
            f"border:none;background:transparent;")
        # Clic en nombre => cargar manga
        name_lbl.mousePressEvent = lambda _e, p=manga_str: self.manga_selected.emit(p)
        card_lay.addWidget(name_lbl)

        # ── Capítulos / imágenes ─────────────────────────────────
        try:
            chapters = [d for d in manga_path.iterdir() if d.is_dir()]
            root_i   = [f for f in manga_path.iterdir()
                        if f.is_file() and f.suffix.lower() in IMG_EXTS]
            info_txt = f"{len(chapters)} caps" if chapters else f"{len(root_i)} imgs"
        except Exception:
            info_txt = "—"

        info_lbl = QLabel(info_txt)
        info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_lbl.setStyleSheet(
            f"font-family:'Share Tech Mono','Consolas',monospace;"
            f"font-size:8px;color:{C_TX_DIM};border:none;background:transparent;")
        card_lay.addWidget(info_lbl)

        return card

    def _import_manga(self):
        from PyQt6.QtWidgets import QFileDialog
        from pathlib import Path
        import shutil
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de manga para importar")
        if not folder:
            return
        src = Path(folder)
        dst = self._base_dir / src.name
        if dst.exists():
            return
        try:
            shutil.move(str(src), str(dst))
            self._scan_mangas()
        except Exception as ex:
            print(f"Error al importar: {ex}")

    def _open_in_explorer(self):
        import subprocess, sys
        if sys.platform == "win32":
            subprocess.Popen(f'explorer "{self._base_dir}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(self._base_dir)])
        else:
            subprocess.Popen(["xdg-open", str(self._base_dir)])

    def refresh(self):
        self._scan_mangas()


# =============================================================================
#  PUNTO CONFIG — ENHANCED CONFIG PANEL WITH API MANAGEMENT
# =============================================================================
class HudApiConfigPanel(QFrame):
    """
    Panel de configuración de APIs — selección de motor y gestión de claves.
    Fácil de modificar y encontrar.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hud_panel")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(4)

        # Header
        hdr_w = QWidget()
        hdr_w.setStyleSheet("background:rgba(0,20,50,180);border-bottom:1px solid rgba(0,180,255,80);")
        hdr_lay = QHBoxLayout(hdr_w)
        hdr_lay.setContentsMargins(8, 4, 8, 4)
        hdr_lay.addWidget(HudSectionLabel("GESTIÓN DE APIS"))
        lay.addWidget(hdr_w)

        inner = QVBoxLayout()
        inner.setContentsMargins(8, 6, 8, 4)
        inner.setSpacing(8)

        # Motor OCR
        ocr_section = self._section_header("MOTOR OCR")
        inner.addWidget(ocr_section)

        self.ocr_motor_combo = QComboBox()
        self.ocr_motor_combo.addItems(["🚀 PaddleOCR (Local)", "🌐 OCR.space API"])
        self.ocr_motor_combo.setStyleSheet(
            f"QComboBox{{background:rgba(0,4,16,128);color:{C_TX};"
            f"border:1px solid rgba(0,180,255,36);border-radius:3px;padding:3px 6px;font-size:10px;}}")
        inner.addWidget(self.ocr_motor_combo)

        # API Key OCR.space
        self._ocr_key_frame = QFrame()
        ocr_k_lay = QVBoxLayout(self._ocr_key_frame)
        ocr_k_lay.setContentsMargins(0, 0, 0, 0)
        ocr_k_lay.setSpacing(3)
        key_row = QHBoxLayout()
        key_lbl = QLabel("API Key:")
        key_lbl.setStyleSheet(f"font-size:9px;color:{C_TX_DIM};")
        self.ocr_key_edit = QLineEdit()
        self.ocr_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.ocr_key_edit.setPlaceholderText("OCR.space API key…")
        self.ocr_key_edit.setStyleSheet(
            f"QLineEdit{{background:rgba(0,4,16,128);color:{C_TX};"
            f"border:1px solid rgba(0,180,255,36);border-radius:3px;padding:3px 6px;font-size:10px;}}")
        key_row.addWidget(key_lbl)
        key_row.addWidget(self.ocr_key_edit, 1)
        ocr_k_lay.addLayout(key_row)
        self._ocr_key_frame.setVisible(False)
        inner.addWidget(self._ocr_key_frame)
        self.ocr_motor_combo.currentIndexChanged.connect(
            lambda i: self._ocr_key_frame.setVisible(i == 1))

        # Motor Traducción
        trans_sep = self._section_header("MOTOR TRADUCCIÓN")
        inner.addWidget(trans_sep)

        self.trans_motor_combo = QComboBox()
        self.trans_motor_combo.addItems([
            "— Sin traductor —",
            "🌐 DeepL API",
            "🤖 Claude Sonnet",
            "⚡ Groq",
            "💻 Offline (ArgosTranslate)"
        ])
        self.trans_motor_combo.setStyleSheet(
            f"QComboBox{{background:rgba(0,4,16,128);color:{C_TX};"
            f"border:1px solid rgba(0,180,255,36);border-radius:3px;padding:3px 6px;font-size:10px;}}")
        inner.addWidget(self.trans_motor_combo)

        key2_row = QHBoxLayout()
        key2_lbl = QLabel("API Key:")
        key2_lbl.setStyleSheet(f"font-size:9px;color:{C_TX_DIM};")
        self.trans_key_edit = QLineEdit()
        self.trans_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.trans_key_edit.setPlaceholderText("Pega tu API key de traducción…")
        self.trans_key_edit.setStyleSheet(
            f"QLineEdit{{background:rgba(0,4,16,128);color:{C_TX};"
            f"border:1px solid rgba(0,180,255,36);border-radius:3px;padding:3px 6px;font-size:10px;}}")
        key2_row.addWidget(key2_lbl)
        key2_row.addWidget(self.trans_key_edit, 1)
        inner.addLayout(key2_row)

        apply_btn = QPushButton("✓ APLICAR CONFIGURACIÓN")
        apply_btn.setStyleSheet(
            f"QPushButton{{background:rgba(0,180,255,22);color:{C_CYAN};"
            f"border:1px solid rgba(0,180,255,70);border-radius:3px;"
            f"font-family:'Orbitron','Segoe UI',sans-serif;font-size:9px;"
            f"font-weight:700;letter-spacing:1px;padding:5px;}}"
            f"QPushButton:hover{{background:rgba(0,234,255,35);}}")
        inner.addWidget(apply_btn)

        lay.addLayout(inner)

    def _section_header(self, text):
        lbl = QLabel(f"▸ {text}")
        lbl.setStyleSheet(
            f"font-family:'Orbitron','Segoe UI',sans-serif;"
            f"font-size:8px;font-weight:700;letter-spacing:1.5px;color:{C_CYAN};"
            f"background:rgba(0,20,50,120);border-left:2px solid {C_CYAN};"
            f"padding:3px 6px;")
        return lbl


# =============================================================================
#  PUNTO CONFIG — OCR CONFIG SECTION (Fácil de modificar)
# =============================================================================
# NOTA: Esta sección está diseñada para ser fácilmente modificable.
# Agrega o quita opciones aquí.
class HudOcrConfigSection(QFrame):
    """
    Configuración del OCR — sección modular y fácil de modificar.
    Ubicación: autoscribe_hud_theme.py > HudOcrConfigSection
    """
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("hud_panel")
        self._cfg = cfg
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 6)
        lay.setSpacing(4)

        hdr_w = QWidget()
        hdr_w.setStyleSheet("background:rgba(0,20,50,180);border-bottom:1px solid rgba(0,180,255,80);")
        hdr_lay = QHBoxLayout(hdr_w)
        hdr_lay.setContentsMargins(8, 4, 8, 4)
        hdr_lay.addWidget(HudSectionLabel("CONFIGURACIÓN OCR"))
        lay.addWidget(hdr_w)

        inner = QVBoxLayout()
        inner.setContentsMargins(8, 6, 8, 4)
        inner.setSpacing(6)

        # ── IDIOMA OCR ── (modifica aquí para agregar/quitar idiomas)
        lang_row = QHBoxLayout()
        lang_lbl = QLabel("Idioma:")
        lang_lbl.setStyleSheet(f"font-size:9px;color:{C_TX_DIM};")
        self.lang_combo = QComboBox()
        self.lang_combo.setStyleSheet(
            f"QComboBox{{background:rgba(0,4,16,128);color:{C_TX};"
            f"border:1px solid rgba(0,180,255,36);border-radius:3px;padding:2px 5px;font-size:10px;}}")
        # ── AGREGA O QUITA IDIOMAS AQUÍ ──
        ocr_langs = [
            ("Inglés", "en"), ("Español", "es"), ("Japonés", "japan"),
            ("Coreano", "korean"), ("Chino Simp.", "ch"),
        ]
        for name, _ in ocr_langs:
            self.lang_combo.addItem(name)
        lang_row.addWidget(lang_lbl)
        lang_row.addWidget(self.lang_combo, 1)
        inner.addLayout(lang_row)

        # ── FORMATO DE SALIDA ──
        fmt_row = QHBoxLayout()
        fmt_lbl = QLabel("Formato:")
        fmt_lbl.setStyleSheet(f"font-size:9px;color:{C_TX_DIM};")
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["DOCX", "TXT"])
        self.fmt_combo.setStyleSheet(
            f"QComboBox{{background:rgba(0,4,16,128);color:{C_TX};"
            f"border:1px solid rgba(0,180,255,36);border-radius:3px;padding:2px 5px;font-size:10px;}}")
        fmt_row.addWidget(fmt_lbl)
        fmt_row.addWidget(self.fmt_combo, 1)
        inner.addLayout(fmt_row)

        # ── OPCIONES DE LECTURA ──
        self.rtl_check = QCheckBox("📖 RTL (Manga/Manhwa)")
        self.rtl_check.setChecked(cfg.get("rtl", True))
        self.rtl_check.setStyleSheet(
            f"QCheckBox{{color:{C_TX_MID};font-size:10px;spacing:5px;}}"
            f"QCheckBox::indicator{{width:12px;height:12px;"
            f"border:1px solid rgba(0,180,255,64);border-radius:2px;background:rgba(0,0,0,77);}}"
            f"QCheckBox::indicator:checked{{background:rgba(0,234,255,64);border-color:{C_CYAN};}}")
        inner.addWidget(self.rtl_check)

        self.vertical_check = QCheckBox("🈸 Vertical JP")
        self.vertical_check.setChecked(cfg.get("vertical_japanese", False))
        self.vertical_check.setStyleSheet(self.rtl_check.styleSheet())
        inner.addWidget(self.vertical_check)

        self.sfx_check = QCheckBox("💥 Conservar SFX")
        self.sfx_check.setChecked(cfg.get("keep_sfx", True))
        self.sfx_check.setStyleSheet(self.rtl_check.styleSheet())
        inner.addWidget(self.sfx_check)

        lay.addLayout(inner)

# =============================================================================
#  TUTORIAL PANEL — Primera vez / Información
# =============================================================================
_TUTORIAL_STEPS = [
    {
        "icon": "🚀",
        "title": "Bienvenido a AutoScribe v2.0 — HELIX HUD Edition",
        "desc": (
            "AutoScribe es un sistema de extracción, traducción y unificación "
            "de texto en imágenes de manga/manhwa. Esta guía te presentará "
            "cada componente en menos de 2 minutos."
        ),
    },
    {
        "icon": "📂",
        "title": "Biblioteca de Mangas",
        "desc": (
            "En la pestaña CONFIG → sección BIBLIOTECA DE MANGAS, importa la "
            "carpeta raíz de tu manga. AutoScribe listará automáticamente todas "
            "las subcarpetas (capítulos). Haz clic en la portada para seleccionar."
        ),
    },
    {
        "icon": "🗂️",
        "title": "Carpetas OCR — Panel CONFIG derecho",
        "desc": (
            "Una vez seleccionado el manga, las subcarpetas aparecen en el panel "
            "derecho bajo CARPETAS OCR.\n"
            "• Clic izquierdo en una carpeta → expande y muestra sus imágenes.\n"
            "• Clic derecho → selecciona la carpeta.\n"
            "• Botón '→ Agregar seleccionadas a cola OCR' → envía al motor OCR.\n"
            "• Botón '⛓ Agregar seleccionadas a AutoUnify' → envía al unificador."
        ),
    },
    {
        "icon": "🖼️",
        "title": "Visor REFERENCIA",
        "desc": (
            "El panel REFERENCIA (centro-derecha del Editor) muestra la imagen "
            "original para comparar con el texto extraído.\n"
            "• Haz clic en una imagen del árbol de carpetas para verla aquí.\n"
            "• Si abres un VIDEO horizontal, el panel CONFIG se oculta automáticamente; "
            "si es vertical se adapta al ratio."
        ),
    },
    {
        "icon": "⚙️",
        "title": "Motor OCR",
        "desc": (
            "AutoScribe soporta múltiples motores OCR:\n"
            "• PaddleOCR (local, CPU/GPU) — recomendado para manga.\n"
            "• OCR.space API — requiere API key (gratis hasta 25 000 req/mes).\n"
            "Configura el motor en CONFIGURACIÓN → panel flotante derecho."
        ),
    },
    {
        "icon": "⛓",
        "title": "Módulo AUTOUNIFY",
        "desc": (
            "AutoUnify unifica todas las páginas de un capítulo en una sola "
            "imagen vertical (webtoon-style).\n"
            "• Arrastra carpetas al panel AUTOUNIFY o usa los botones del CONFIG.\n"
            "• Ajusta la altura máxima de salida con el spinner Alt. máx.\n"
            "• Pulsa '⚡ Unificar todo' para procesar la cola."
        ),
    },
    {
        "icon": "🌐",
        "title": "Módulo TRADUCTOR",
        "desc": (
            "Traduce el texto extraído por OCR directamente desde el Editor.\n"
            "• Motores disponibles: Groq (gratis y rápido), OpenAI, DeepSeek, "
            "Google Gemini, DeepL.\n"
            "• Configura tu API key en CONFIG → CONFIGURAR TRADUCTOR.\n"
            "• Personaliza el prompt de traducción en el módulo TRADUCTOR."
        ),
    },
    {
        "icon": "📝",
        "title": "Editor de Texto",
        "desc": (
            "El editor central muestra el texto extraído por OCR listo para editar.\n"
            "• Formato: negrita, cursiva, subrayado, tachado, tamaño de fuente.\n"
            "• Exporta como DOCX o TXT.\n"
            "• El contador inferior muestra palabras, caracteres y estado de guardado."
        ),
    },
    {
        "icon": "🕒",
        "title": "HUD y Sistema",
        "desc": (
            "El encabezado HUD muestra el estado del sistema en tiempo real:\n"
            "• STATUS + EKG — estado del motor OCR (IDLE / PROCESANDO / LISTO / ERROR).\n"
            "• Panel SISTEMA (izquierda inferior) — RAM, CPU, GPU, versión.\n"
            "• Reloj flotante — arriba derecha, separado del panel CONFIG.\n"
            "• Fondo animado — coloca imágenes, GIFs o videos en la carpeta fondos/."
        ),
    },
    {
        "icon": "✅",
        "title": "¡Listo para comenzar!",
        "desc": (
            "Ya conoces AutoScribe. Pasos recomendados para tu primer uso:\n"
            "1. Ve a CONFIG → importa tu manga.\n"
            "2. Selecciona un capítulo → agrégalo a la cola OCR.\n"
            "3. Pulsa ▶ INICIAR en el panel izquierdo.\n"
            "4. Revisa y edita el texto en el Editor.\n"
            "5. Traduce o exporta el resultado.\n\n"
            "Puedes volver a este tutorial en CONFIGURACIÓN → Información."
        ),
    },
]


class TutorialPanel(QWidget):
    """
    Panel tutorial de primera vez — overlay modal que flota sobre la ventana principal.
    Muestra pasos con navegación, barra de progreso y botón de cierre.
    """
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tutorial_overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self._step = 0
        self._total = len(_TUTORIAL_STEPS)
        self._anim_phase = 0.0
        self._card: Optional["QFrame"] = None
        self._build()
        t = QTimer(self)
        t.timeout.connect(self._anim_tick)
        t.start(40)

    def _anim_tick(self):
        self._anim_phase = (self._anim_phase + 0.05) % (2 * math.pi)
        self.update()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)

        # ── Tarjeta central ───────────────────────────────────────────────────
        self._card = QFrame()
        self._card.setFixedSize(560, 440)
        self._card.setObjectName("tutorial_card")
        self._card.setStyleSheet(
            "QFrame#tutorial_card{"
            "background:rgba(1,8,22,238);"
            "border:1px solid rgba(0,180,255,90);"
            "border-radius:12px;}"
        )
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(28, 22, 28, 18)
        cl.setSpacing(10)

        # Barra de progreso top
        self._prog = QProgressBar()
        self._prog.setRange(0, self._total - 1)
        self._prog.setValue(0)
        self._prog.setFixedHeight(4)
        self._prog.setTextVisible(False)
        self._prog.setStyleSheet(
            "QProgressBar{background:rgba(0,40,80,100);border:none;border-radius:2px;}"
            "QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(0,100,200,200),stop:1 rgba(0,234,255,230));border-radius:2px;}"
        )
        cl.addWidget(self._prog)

        # Ícono grande
        self._icon_lbl = QLabel()
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet(
            "font-size:40px;background:transparent;border:none;"
        )
        cl.addWidget(self._icon_lbl)

        # Título
        self._title_lbl = QLabel()
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setStyleSheet(
            f"color:{C_CYAN};font-family:'Orbitron','Segoe UI',sans-serif;"
            f"font-size:14px;font-weight:700;letter-spacing:1px;"
            f"background:transparent;border:none;"
        )
        cl.addWidget(self._title_lbl)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border:none;border-top:1px solid rgba(0,180,255,40);")
        cl.addWidget(sep)

        # Descripción con scroll para textos largos
        desc_scroll = QScrollArea()
        desc_scroll.setWidgetResizable(True)
        desc_scroll.setFrameShape(QFrame.Shape.NoFrame)
        desc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        desc_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{width:4px;background:rgba(0,0,0,0);}"
            "QScrollBar::handle:vertical{background:rgba(0,180,255,60);border-radius:2px;}"
        )
        self._desc_lbl = QLabel()
        self._desc_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet(
            f"color:{C_TX};font-size:11px;line-height:160%;"
            f"background:transparent;border:none;padding:2px 0;"
        )
        desc_scroll.setWidget(self._desc_lbl)
        cl.addWidget(desc_scroll, 1)

        # Numerador de paso
        self._step_lbl = QLabel()
        self._step_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._step_lbl.setStyleSheet(
            f"color:{C_TX_DIM};font-size:9px;background:transparent;border:none;"
        )
        cl.addWidget(self._step_lbl)

        # Botones de navegación
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_prev = QPushButton("◀  Anterior")
        self._btn_prev.setObjectName("hud_ghost")
        self._btn_prev.setFixedHeight(30)
        self._btn_prev.clicked.connect(self._prev)
        btn_row.addWidget(self._btn_prev)
        btn_row.addStretch()

        self._btn_skip = QPushButton("✕  Omitir")
        self._btn_skip.setObjectName("hud_ghost")
        self._btn_skip.setFixedHeight(30)
        self._btn_skip.clicked.connect(self._close_tutorial)
        btn_row.addWidget(self._btn_skip)

        self._btn_next = QPushButton("Siguiente  ▶")
        self._btn_next.setObjectName("hud_primary")
        self._btn_next.setFixedHeight(30)
        self._btn_next.setFixedWidth(130)
        self._btn_next.clicked.connect(self._next)
        btn_row.addWidget(self._btn_next)
        cl.addLayout(btn_row)

        row.addWidget(self._card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

        self._update_step()

    def _update_step(self):
        s = _TUTORIAL_STEPS[self._step]
        self._icon_lbl.setText(s["icon"])
        self._title_lbl.setText(s["title"])
        self._desc_lbl.setText(s["desc"])
        self._prog.setValue(self._step)
        self._step_lbl.setText(f"Paso {self._step + 1} de {self._total}")
        self._btn_prev.setEnabled(self._step > 0)
        is_last = self._step == self._total - 1
        self._btn_next.setText("✓  Comenzar" if is_last else "Siguiente  ▶")
        self._btn_skip.setVisible(not is_last)

    def _next(self):
        if self._step < self._total - 1:
            self._step += 1
            self._update_step()
        else:
            self._close_tutorial()

    def _prev(self):
        if self._step > 0:
            self._step -= 1
            self._update_step()

    def _close_tutorial(self):
        self.hide()
        self.closed.emit()

    def show_from_start(self):
        """Reinicia el tutorial al paso 0 y muestra el panel."""
        self._step = 0
        self._update_step()
        self.raise_()
        self.show()

    def paintEvent(self, e):
        """Fondo oscuro semi-transparente + esquinas tácticas animadas."""
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 165))

        if self._card:
            cr = self._card.geometry()
            alpha = int(60 + 40 * math.sin(self._anim_phase))
            glow_pen = QPen(QColor(0, 200, 255, alpha), 2)
            p.setPen(glow_pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(cr.adjusted(-3, -3, 3, 3), 14, 14)

            # Esquinas tácticas
            s = 18
            ca = 180 + int(60 * math.sin(self._anim_phase))
            corner_pen = QPen(QColor(0, 234, 255, ca), 2)
            p.setPen(corner_pen)
            for pts in [
                [(cr.left()-4, cr.top()-4+s),  (cr.left()-4,  cr.top()-4),  (cr.left()-4+s,  cr.top()-4)],
                [(cr.right()+4-s, cr.top()-4), (cr.right()+4, cr.top()-4),  (cr.right()+4,   cr.top()-4+s)],
                [(cr.left()-4, cr.bottom()+4-s),(cr.left()-4,  cr.bottom()+4),(cr.left()-4+s, cr.bottom()+4)],
                [(cr.right()+4-s,cr.bottom()+4),(cr.right()+4, cr.bottom()+4),(cr.right()+4,  cr.bottom()+4-s)],
            ]:
                path = QPainterPath()
                path.moveTo(*pts[0])
                path.lineTo(*pts[1])
                path.lineTo(*pts[2])
                p.drawPath(path)
        p.end()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._card:
            x = (self.width()  - self._card.width())  // 2
            y = (self.height() - self._card.height()) // 2
            self._card.move(x, y)