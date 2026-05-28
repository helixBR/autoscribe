"""
launcher.py — AutoScribe Self-Installing Launcher
==================================================
Compilar con Nuitka:

    python.exe -m nuitka --onefile --windows-console-mode=disable ^
      --enable-plugin=tk-inter ^
      --output-filename=AutoScribe.exe --output-dir=. ^
      --include-data-files=Requirements.txt=Requirements.txt ^
      --include-data-files=python-embed.zip=python-embed.zip ^
      --include-data-files=AutoScribe_v1_0.pyc=AutoScribe_v1_0.pyc ^
      --windows-icon-from-ico=assets\logos\icon.ico ^
      --assume-yes-for-downloads launcher.py

Flujo:
  1. Si es la primera vez:
       a. Extrae python-embed.zip a una carpeta temporal
       b. Usa ese Python para crear venv en AppData\Local\AutoScribe\venv
       c. Instala Requirements.txt en el venv
       d. Borra el Python temporal silenciosamente
  2. Agrega el venv a sys.path e importa main() directamente
     — sin subprocess, sin Python externo, todo en el mismo proceso
"""

import os
import sys
import subprocess
import threading
import shutil
import zipfile
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# Suprimir ventanas de consola en Windows
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

# ─── RUTAS BASE ───────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

# venv local junto a la app — se crea en assets\venv la primera vez
VENV_DIR   = BASE_DIR / "assets" / "venv"
STAMP_FILE = VENV_DIR / ".autoscribe_ready"

# Archivos embebidos en el .exe
REQUIREMENTS = BASE_DIR / "Requirements.txt"
PYTHON_EMBED = BASE_DIR / "python-embed.zip"

# ─── COLORES ──────────────────────────────────────────────────────────────────
BG         = "#0A0015"
BG2        = "#130025"
ACCENT     = "#C800FF"
ACCENT2    = "#8800BB"
TEXT       = "#E8D0FF"
TEXT_DIM   = "#7050A0"
TEXT_MUTED = "#3D2060"
SUCCESS    = "#00FF88"
ERROR_COL  = "#FF4060"

# ─── VERIFICACIÓN ─────────────────────────────────────────────────────────────
def venv_is_ready() -> bool:
    venv_python = VENV_DIR / "Scripts" / "python.exe"
    return venv_python.exists() and STAMP_FILE.exists()


# ─── VENTANA DE INSTALACIÓN ───────────────────────────────────────────────────
class InstallerWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AutoScribe — Configuración inicial")
        self.root.geometry("560x360")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_request)

        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"560x360+{(sw-560)//2}+{(sh-360)//2}")

        self._cancelled  = False
        self._install_ok = False
        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("default")
        style.configure(
            "AS.Horizontal.TProgressbar",
            troughcolor=BG2, background=ACCENT,
            bordercolor=BG, lightcolor=ACCENT,
            darkcolor=ACCENT2, thickness=8,
        )

    def _build_ui(self):
        frame = tk.Frame(self.root, bg=BG, bd=0)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        tk.Frame(frame, bg=ACCENT, height=3).pack(fill="x")

        tk.Label(frame, text="⚡ AutoScribe",
                 font=("Segoe UI", 26, "bold"),
                 fg=ACCENT, bg=BG).pack(pady=(28, 4))

        tk.Label(frame, text="Configurando el entorno por primera vez",
                 font=("Segoe UI", 10),
                 fg=TEXT_DIM, bg=BG).pack()

        tk.Label(frame, text=f"Instalando en: {VENV_DIR}",
                 font=("Segoe UI", 8),
                 fg=TEXT_MUTED, bg=BG).pack(pady=(4, 0))

        tk.Frame(frame, bg=TEXT_MUTED, height=1).pack(
            fill="x", padx=50, pady=16)

        self.progress = ttk.Progressbar(
            frame, style="AS.Horizontal.TProgressbar",
            length=460, mode="indeterminate")
        self.progress.pack()

        self.status_var = tk.StringVar(value="Preparando instalación...")
        tk.Label(frame, textvariable=self.status_var,
                 font=("Segoe UI", 9),
                 fg=TEXT, bg=BG, wraplength=500).pack(pady=(14, 0))

        self.detail_var = tk.StringVar(value="")
        tk.Label(frame, textvariable=self.detail_var,
                 font=("Segoe UI", 8),
                 fg=TEXT_DIM, bg=BG, wraplength=500).pack(pady=(4, 0))

        tk.Label(frame,
                 text="Este proceso solo ocurre una vez  ·  No cierres esta ventana",
                 font=("Segoe UI", 8),
                 fg=TEXT_MUTED, bg=BG).pack(side="bottom", pady=16)

    def _on_close_request(self):
        if not self._install_ok:
            if messagebox.askyesno(
                "Cancelar instalación",
                "¿Cancelar la instalación?\n\n"
                "AutoScribe no podrá ejecutarse hasta que se complete."
            ):
                self._cancelled = True
                self.root.destroy()

    def set_status(self, msg: str, detail: str = ""):
        self.status_var.set(msg)
        self.detail_var.set(detail)
        self.root.update_idletasks()

    def run(self) -> bool:
        self.progress.start(12)
        thread = threading.Thread(target=self._install_thread, daemon=True)
        thread.start()
        self.root.mainloop()
        return self._install_ok

    def _install_thread(self):
        temp_python_dir = None
        venv_python = VENV_DIR / "Scripts" / "python.exe"
        try:
            # ── Limpiar venv roto ─────────────────────────────────────────────
            if VENV_DIR.exists() and not STAMP_FILE.exists():
                self.root.after(0, self.set_status,
                                "Limpiando instalación previa incompleta...")
                shutil.rmtree(VENV_DIR, ignore_errors=True)

            # ── Extraer Python embebido temporal ──────────────────────────────
            self.root.after(0, self.set_status,
                            "Preparando instalador...",
                            "Extrayendo Python temporal")

            if not PYTHON_EMBED.exists():
                raise RuntimeError(
                    f"No se encontró python-embed.zip en:\n{PYTHON_EMBED}\n\n"
                    "Reinstala AutoScribe."
                )

            temp_python_dir = Path(tempfile.mkdtemp(prefix="autoscribe_py_"))
            with zipfile.ZipFile(str(PYTHON_EMBED), "r") as zf:
                zf.extractall(str(temp_python_dir))

            embed_python = temp_python_dir / "python.exe"
            if not embed_python.exists():
                raise RuntimeError("python-embed.zip no contiene python.exe")

            # ── Habilitar site-packages en el embed ───────────────────────────
            self.root.after(0, self.set_status,
                            "Preparando instalador...",
                            "Configurando pip")

            pth_files = list(temp_python_dir.glob("python*._pth"))
            if pth_files:
                pth = pth_files[0]
                content = pth.read_text(encoding="utf-8")
                content = content.replace("#import site", "import site")
                pth.write_text(content, encoding="utf-8")

            # ── Descargar e instalar pip ──────────────────────────────────────
            import urllib.request
            get_pip = temp_python_dir / "get-pip.py"
            urllib.request.urlretrieve(
                "https://bootstrap.pypa.io/get-pip.py", str(get_pip)
            )
            subprocess.run(
                [str(embed_python), str(get_pip), "-q"],
                capture_output=True,
                creationflags=_NO_WINDOW
            )

            # ── Crear venv ────────────────────────────────────────────────────
            VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
            self.root.after(0, self.set_status, "Creando entorno virtual...")

            subprocess.run(
                [str(embed_python), "-m", "pip", "install", "virtualenv", "-q"],
                capture_output=True,
                creationflags=_NO_WINDOW
            )
            result = subprocess.run(
                [str(embed_python), "-m", "virtualenv", str(VENV_DIR)],
                capture_output=True, text=True,
                creationflags=_NO_WINDOW
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"No se pudo crear el entorno virtual:\n{result.stderr}"
                )

            # ── Instalar dependencias ─────────────────────────────────────────
            self.root.after(0, self.set_status,
                            "Instalando dependencias...",
                            "Descargando paquetes (puede tardar 5-10 min)")

            proc = subprocess.Popen(
                [str(venv_python), "-m", "pip", "install",
                 "-r", str(REQUIREMENTS), "--no-warn-script-location"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                creationflags=_NO_WINDOW
            )

            for line in proc.stdout:
                line = line.strip()
                if line.startswith(("Collecting", "Downloading",
                                    "Installing", "Successfully")):
                    short = line[:70] + ("..." if len(line) > 70 else "")
                    self.root.after(0, self.set_status,
                                    "Instalando dependencias...", short)

            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(
                    "pip terminó con errores. Revisa tu conexión a internet "
                    "y vuelve a intentarlo."
                )

            # ── Escribir stamp ────────────────────────────────────────────────
            STAMP_FILE.write_text("ok", encoding="utf-8")
            self._install_ok = True
            self.root.after(0, self._on_success)

        except Exception as exc:
            self.root.after(0, self._on_error, str(exc))

        finally:
            if temp_python_dir and temp_python_dir.exists():
                shutil.rmtree(temp_python_dir, ignore_errors=True)

    def _on_success(self):
        self.progress.stop()
        self.progress.config(mode="determinate", value=100, maximum=100)
        ttk.Style(self.root).configure(
            "AS.Horizontal.TProgressbar", background=SUCCESS)
        self.set_status(
            "✓ Instalación completada  —  Iniciando AutoScribe...", "Listo")
        self.root.after(1800, self.root.destroy)

    def _on_error(self, msg: str):
        self.progress.stop()
        ttk.Style(self.root).configure(
            "AS.Horizontal.TProgressbar", background=ERROR_COL)
        self.set_status("✗ Error durante la instalación", "")
        messagebox.showerror(
            "Error de instalación",
            f"No se pudo completar la instalación:\n\n{msg}\n\n"
            "Cierra esta ventana e intenta de nuevo."
        )
        self._cancelled = True
        self.root.destroy()


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
def main():
    # 1. Instalar si es la primera vez
    if not venv_is_ready():
        window = InstallerWindow()
        ok = window.run()
        if not ok:
            sys.exit(0)

    # 2. Lanzar AutoScribe con el Python del venv — sin importar el módulo
    venv_python = VENV_DIR / "Scripts" / "python.exe"
    pyc_file    = BASE_DIR / "AutoScribe_v1_0.pyc"

    result = subprocess.run(
        [str(venv_python), str(pyc_file)],
        creationflags=_NO_WINDOW
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
