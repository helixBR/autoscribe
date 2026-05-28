"""
process_manager.py — Gestor de procesos para AutoScribe v1.0
============================================================
Suspende procesos del sistema que consumen CPU/RAM innecesariamente
mientras PaddleOCR u otro motor pesado está activo, y los reanuda
automáticamente al finalizar (incluso si hay error o cancelación).

Mejora v1.1: tras suspender cada proceso llama EmptyWorkingSet (Windows)
para vaciar sus páginas físicas de RAM inmediatamente, liberando 1-4 GB
reales que PaddleOCR puede aprovechar sin paginar en disco.

Uso rápido (integración en AutoScribe):
    from process_manager import ProcessSnapshot

    # Antes de iniciar el OCR worker:
    snap = ProcessSnapshot()
    snap.freeze(log_cb=self.log_panel.add)

    # Al terminar (en _on_done, _on_error, _on_cancel):
    snap.thaw(log_cb=self.log_panel.add)

Compatibilidad:
    Windows  — usa NtSuspendProcess (psutil) + EmptyWorkingSet (ctypes/psapi)
    Linux    — envía SIGSTOP / SIGCONT  (EmptyWorkingSet es no-op)
    macOS    — envía SIGSTOP / SIGCONT  (EmptyWorkingSet es no-op)
"""

from __future__ import annotations

import os
import sys
import signal
import logging
from typing import Any, List, Optional, Callable

log = logging.getLogger("autoscribe.procmgr")

# ─── EmptyWorkingSet (Windows) — libera RAM física de procesos suspendidos ───
# Cuando un proceso se suspende, Windows puede mantener sus páginas en RAM.
# EmptyWorkingSet fuerza al kernel a moverlas al archivo de paginación,
# liberando RAM física real para que PaddleOCR no pagine en disco.
import ctypes as _ctypes

# ─── psutil (dependencia opcional) — importar ANTES de las funciones que lo usan
try:
    import psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False
    psutil = None  # type: ignore

def _empty_working_set(pid: int) -> bool:
    """
    Llama a EmptyWorkingSet(pid) en Windows para vaciar las páginas físicas
    de un proceso suspendido. Retorna True si tuvo éxito.
    Solo tiene efecto en Windows; en Linux/macOS es no-op (retorna True).
    """
    if sys.platform != "win32":
        return True
    try:
        PROCESS_ALL_ACCESS = 0x1F0FFF
        handle = _ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not handle:
            return False
        ok = bool(_ctypes.windll.psapi.EmptyWorkingSet(handle))
        _ctypes.windll.kernel32.CloseHandle(handle)
        return ok
    except Exception:
        return False


# ─── Prioridad y afinidad CPU del proceso actual (PaddleOCR) ─────────────────
# Durante el OCR: elevar prioridad a ABOVE_NORMAL + usar todos los núcleos.
# Al terminar: restaurar estado original.

_saved_nice  = None   # prioridad original
_saved_affin = None   # afinidad CPU original


def _boost_self_cpu(log_cb=None):
    global _saved_nice, _saved_affin
    if not _PSUTIL_OK:
        return
    try:
        me = psutil.Process()
        _saved_nice  = me.nice()
        _saved_affin = me.cpu_affinity() if hasattr(me, "cpu_affinity") else None
        # Elevar prioridad del proceso actual
        if sys.platform == "win32":
            me.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
        else:
            try:
                me.nice(-5)
            except (PermissionError, OSError):
                pass
        # Usar todos los nucleos logicos disponibles
        if _saved_affin is not None:
            all_cpus = list(range(psutil.cpu_count(logical=True) or 1))
            try:
                me.cpu_affinity(all_cpus)
            except (psutil.AccessDenied, OSError):
                pass
        if log_cb:
            n = psutil.cpu_count(logical=True) or 1
            log_cb(f"[ProcessMgr] CPU boost activo — ABOVE_NORMAL, {n} nucleos")
    except Exception as ex:
        if log_cb:
            log_cb(f"[ProcessMgr] CPU boost fallo: {ex}")


def _restore_self_cpu(log_cb=None):
    global _saved_nice, _saved_affin
    if not _PSUTIL_OK or _saved_nice is None:
        return
    try:
        me = psutil.Process()
        me.nice(_saved_nice)
        if _saved_affin is not None:
            try:
                me.cpu_affinity(_saved_affin)
            except (psutil.AccessDenied, OSError):
                pass
        if log_cb:
            log_cb("[ProcessMgr] CPU restaurada a prioridad normal")
    except Exception:
        pass
    finally:
        _saved_nice  = None
        _saved_affin = None

# ─── CONSTANTES ──────────────────────────────────────────────────────────────

# Porcentaje mínimo de CPU (promedio 1 s) para considerar un proceso "pesado".
# Baja este número para suspender más agresivamente.
CPU_THRESHOLD_PCT: float = 5.0

# MB de RAM mínimos para considerar un proceso candidato a suspender.
# 80 MB: balance entre agresividad y estabilidad — evita tocar procesos ligeros.
RAM_THRESHOLD_MB: float = 80.0

# Si True, tras suspender cada proceso se llama EmptyWorkingSet para liberar
# sus páginas físicas de RAM inmediatamente (solo Windows).
# Poner en False si notas que algún proceso tarda en reanudar.
FORCE_EMPTY_WS: bool = True

# Nombre del proceso actual (para no suicidarse)
_SELF_PID: int = os.getpid()

# ─── LISTA NEGRA — procesos que NUNCA se suspenden ───────────────────────────
# Añadir aquí cualquier proceso crítico para el sistema o para AutoScribe.
_NEVER_SUSPEND: set[str] = {
    # Sistema Windows
    "system", "system idle process", "smss.exe", "csrss.exe",
    "wininit.exe", "winlogon.exe", "lsass.exe", "lsm.exe",
    "services.exe", "svchost.exe", "dwm.exe", "explorer.exe",
    "taskmgr.exe", "spoolsv.exe", "conhost.exe", "ntoskrnl.exe",
    "audiodg.exe", "fontdrvhost.exe", "sihost.exe", "ctfmon.exe",
    "securityhealthservice.exe", "antimalware service executable",
    "msmpeng.exe", "msdtc.exe", "wuauclt.exe",
    # Sistema Linux / macOS
    "init", "systemd", "kernel_task", "launchd", "kthreadd",
    "kworker", "ksoftirqd", "migration", "rcu_sched",
    # Antivirus comunes (suspenderlos puede bloquear el sistema)
    "avgui.exe", "avguard.exe", "mbam.exe", "mbamservice.exe",
    "bdagent.exe", "ekrn.exe", "nod32.exe",
    # AutoScribe y sus dependencias directas
    "autoscribe", "python.exe", "python3", "python", "pythonw.exe",
    # "run.py" eliminado — el lanzador ya no existe (las vars OneDNN están en AutoScribe_v1.0.py)
}

# ─── LISTA BLANCA — procesos que SÍ se suspenden si cumplen el umbral ────────
# Deja vacía para modo automático (se usa la heurística CPU/RAM).
# Si la llenas, SOLO estos procesos serán candidatos.
WHITELIST_NAMES: list[str] = []

# ─── APPS CONOCIDAS PESADAS (se añaden como candidatos adicionales) ──────────
# Se suspenden si están corriendo, independientemente del umbral CPU/RAM.
# Comentar/descomentar según las preferencias del usuario.
KNOWN_HEAVY_APPS: set[str] = {
    # Navegadores
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
    "opera.exe", "vivaldi.exe", "arc.exe",
    # Comunicación
    "discord.exe", "slack.exe", "teams.exe", "zoom.exe",
    "skype.exe",
    # Multimedia / Streaming
    "spotify.exe", "vlc.exe", "mpv.exe", "obs64.exe", "obs.exe",
    "streamlabs obs.exe",
    # Juegos / launchers
    "steam.exe", "epicgameslauncher.exe", "gog galaxy.exe",
    "playnite.exe",
    # Edición / Diseño
    "photoshop.exe", "lightroom.exe", "premiere.exe", "afterfx.exe",
    "illustrator.exe", "gimp-2.10.exe",
    # IDEs (solo suspender si el usuario lo desea — pueden tener procesos bg)
    # "code.exe", "pycharm64.exe", "idea64.exe",
    # Torrent / P2P
    "utorrent.exe", "bittorrent.exe", "qbittorrent.exe",
    # AMD / GPU software (visible en task manager — consume RAM bg)
    "amd software.exe", "amdsoftware.exe", "radeon software.exe",
    "amdrsserv.exe", "amdow.exe", "cnext.exe", "cncmd.exe",
    # WPS Office background services
    "wpsoffice.exe", "wps.exe", "et.exe", "wpp.exe", "wpspdf.exe",
    "wpscloudsvr.exe", "wpsupdate.exe",
    # Microsoft 365 Copilot / Office background
    "copilot.exe", "microsoft.sharepoint.exe", "officeclicktorun.exe",
    "msedgewebview2.exe",
    # Windows Enlace Móvil / Phone Link
    "phoneexperiencehost.exe", "yourphone.exe",
    # Windows Widgets
    "widgetservice.exe", "widgets.exe",
    # Acrobat background sync
    "adobecollabsync.exe", "acrobat.exe", "acrobatnotificationclient.exe",
}


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _proc_name_lower(proc: Any) -> str:
    """Nombre del proceso en minúsculas, sin excepción."""
    try:
        return proc.name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return ""


def _is_safe_to_touch(proc: Any) -> bool:
    """True si el proceso puede ser candidato a suspender."""
    try:
        name = _proc_name_lower(proc)
        if not name:
            return False
        # Nunca tocar el proceso actual ni sus hijos directos
        if proc.pid == _SELF_PID:
            return False
        try:
            parent = proc.parent()
            if parent and parent.pid == _SELF_PID:
                return False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        # Lista negra
        if name in _NEVER_SUSPEND:
            return False
        # Procesos del sistema Windows (PID bajos + sin exe accessible)
        if sys.platform == "win32" and proc.pid < 8:
            return False
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return False


def _is_heavy(proc: Any) -> bool:
    """
    True si el proceso consume suficiente CPU o RAM para valer la pena
    suspenderlo, O si está en la lista de apps pesadas conocidas.
    """
    name = _proc_name_lower(proc)
    if name in KNOWN_HEAVY_APPS:
        return True
    if WHITELIST_NAMES and name not in [w.lower() for w in WHITELIST_NAMES]:
        return False
    try:
        cpu = proc.cpu_percent(interval=0)   # primera lectura (siempre 0.0)
        mem_mb = proc.memory_info().rss / (1024 * 1024)
        return mem_mb >= RAM_THRESHOLD_MB
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return False


def _suspend_proc(proc: Any) -> bool:
    """Suspende el proceso. Retorna True si tuvo éxito."""
    try:
        proc.suspend()
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return False


def _resume_proc(proc: Any) -> bool:
    """Reanuda el proceso. Retorna True si tuvo éxito."""
    try:
        proc.resume()
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        return False


# ─── API PÚBLICA ─────────────────────────────────────────────────────────────

class ProcessSnapshot:
    """
    Captura el estado de los procesos candidatos en el momento de freeze(),
    los suspende, y los reanuda con thaw().

    Uso recomendado (con try/finally para garantizar el thaw):

        snap = ProcessSnapshot()
        snap.freeze(log_cb=self.log_panel.add)
        try:
            worker.start()
            worker.wait()       # o bloqueo equivalente
        finally:
            snap.thaw(log_cb=self.log_panel.add)

    En AutoScribe, la integración es asíncrona: llamar freeze() antes de
    worker.start() y thaw() en los slots _on_done / _on_error / _on_cancel.
    """

    def __init__(
        self,
        cpu_threshold: float = CPU_THRESHOLD_PCT,
        ram_threshold_mb: float = RAM_THRESHOLD_MB,
    ):
        self._cpu_thr = cpu_threshold
        self._ram_thr = ram_threshold_mb
        self._suspended_pids: list[int] = []   # PIDs que suspendimos
        self._frozen = False

    # ── freeze ────────────────────────────────────────────────────────────────
    def freeze(self, log_cb: Optional[Callable[[str], None]] = None) -> int:
        """
        Detecta y suspende los procesos pesados en ejecución.

        Returns:
            Número de procesos efectivamente suspendidos.
        """
        def _log(msg: str):
            log.info(msg)
            if log_cb:
                log_cb(msg)

        if not _PSUTIL_OK:
            _log("[ProcessMgr] psutil no instalado — instala con: pip install psutil")
            return 0

        if self._frozen:
            _log("[ProcessMgr] ⚠ Ya hay un snapshot activo. Llama thaw() primero.")
            return 0

        # Primera pasada CPU (para inicializar contadores)
        candidates: List[Any] = []
        for proc in psutil.process_iter(["pid", "name", "status"]):
            if not _is_safe_to_touch(proc):
                continue
            # Omitir procesos ya suspendidos (no queremos doble-suspender)
            try:
                if proc.status() in (psutil.STATUS_STOPPED, psutil.STATUS_ZOMBIE):
                    continue
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            candidates.append(proc)

        # Segunda pasada: leer CPU real (interval=0.2 da lectura válida)
        # Hacemos esto en lote para ser más eficientes
        _cpu_map: dict[int, float] = {}
        for proc in candidates:
            try:
                _cpu_map[proc.pid] = proc.cpu_percent(interval=0)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        import time
        time.sleep(0.25)   # breve pausa para que los contadores sean válidos

        for proc in candidates:
            try:
                _cpu_map[proc.pid] = proc.cpu_percent(interval=0)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                _cpu_map[proc.pid] = 0.0

        # Filtrar por peso y suspender
        suspended_count = 0
        for proc in candidates:
            try:
                name = _proc_name_lower(proc)
                cpu = _cpu_map.get(proc.pid, 0.0)
                try:
                    mem_mb = proc.memory_info().rss / (1024 * 1024)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    mem_mb = 0.0

                is_heavy = (
                    name in KNOWN_HEAVY_APPS
                    or cpu >= self._cpu_thr
                    or mem_mb >= self._ram_thr
                )
                if WHITELIST_NAMES:
                    is_heavy = is_heavy and (name in [w.lower() for w in WHITELIST_NAMES])

                if not is_heavy:
                    continue

                if _suspend_proc(proc):
                    self._suspended_pids.append(proc.pid)
                    suspended_count += 1
                    freed_note = ""
                    if FORCE_EMPTY_WS:
                        ws_ok = _empty_working_set(proc.pid)
                        freed_note = " | RAM vaciada ✓" if ws_ok else " | RAM vaciar ✗"
                    _log(f"[ProcessMgr] ⏸ Suspendido: {proc.name()} (PID {proc.pid}) "
                         f"| CPU {cpu:.1f}% | RAM {mem_mb:.0f} MB{freed_note}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                continue

        self._frozen = True
        if suspended_count:
            _log(f"[ProcessMgr] ✓ {suspended_count} proceso(s) suspendido(s) → más CPU/RAM para OCR")
        else:
            _log("[ProcessMgr] ℹ Sin procesos pesados detectados (nada que suspender)")

        # Elevar prioridad CPU del proceso actual (PaddleOCR) tras suspender competidores
        _boost_self_cpu(log_cb=log_cb)

        return suspended_count

    # ── thaw ──────────────────────────────────────────────────────────────────
    def thaw(self, log_cb: Optional[Callable[[str], None]] = None) -> int:
        """
        Reanuda todos los procesos suspendidos por freeze().

        Returns:
            Número de procesos efectivamente reanudados.
        """
        def _log(msg: str):
            log.info(msg)
            if log_cb:
                log_cb(msg)

        if not _PSUTIL_OK:
            return 0

        if not self._frozen:
            return 0

        resumed_count = 0
        failed: list[int] = []

        for pid in self._suspended_pids:
            try:
                proc = psutil.Process(pid)
                if _resume_proc(proc):
                    resumed_count += 1
                    _log(f"[ProcessMgr] ▶ Reanudado: {proc.name()} (PID {pid})")
                else:
                    failed.append(pid)
            except psutil.NoSuchProcess:
                # El proceso terminó solo mientras estaba suspendido — OK
                _log(f"[ProcessMgr] ℹ PID {pid} ya no existe (terminó estando suspendido)")
            except (psutil.AccessDenied, OSError) as e:
                _log(f"[ProcessMgr] ⚠ No se pudo reanudar PID {pid}: {e}")
                failed.append(pid)

        self._suspended_pids.clear()
        self._frozen = False

        # Restaurar prioridad y afinidad antes de reanudar los demas procesos
        _restore_self_cpu(log_cb=log_cb)

        if resumed_count:
            _log(f"[ProcessMgr] ✓ {resumed_count} proceso(s) reanudado(s)")
        if failed:
            _log(f"[ProcessMgr] ⚠ {len(failed)} proceso(s) no pudieron reanudarse: {failed}")

        return resumed_count

    # ── propiedades de estado ──────────────────────────────────────────────────
    @property
    def is_frozen(self) -> bool:
        return self._frozen

    @property
    def suspended_count(self) -> int:
        return len(self._suspended_pids)

    def __repr__(self) -> str:
        return (f"<ProcessSnapshot frozen={self._frozen} "
                f"suspended={len(self._suspended_pids)}>")


# ─── FUNCIONES DE CONVENIENCIA ────────────────────────────────────────────────

def is_available() -> bool:
    """True si psutil está instalado y el módulo puede funcionar."""
    return _PSUTIL_OK


def list_candidates(
    cpu_threshold: float = CPU_THRESHOLD_PCT,
    ram_threshold_mb: float = RAM_THRESHOLD_MB,
) -> List[dict]:
    """
    Lista los procesos que serían suspendidos, sin suspender nada.
    Útil para diagnóstico desde la UI o la consola.

    Returns:
        Lista de dicts con keys: pid, name, cpu_pct, ram_mb, reason
    """
    if not _PSUTIL_OK:
        return []

    results = []
    for proc in psutil.process_iter(["pid", "name", "status"]):
        if not _is_safe_to_touch(proc):
            continue
        try:
            if proc.status() in (psutil.STATUS_STOPPED, psutil.STATUS_ZOMBIE):
                continue
            name = _proc_name_lower(proc)
            cpu = proc.cpu_percent(interval=0)
            mem_mb = proc.memory_info().rss / (1024 * 1024)
            reason = []
            if name in KNOWN_HEAVY_APPS:
                reason.append("app conocida")
            if cpu >= cpu_threshold:
                reason.append(f"CPU {cpu:.1f}%")
            if mem_mb >= ram_threshold_mb:
                reason.append(f"RAM {mem_mb:.0f}MB")
            if reason:
                results.append({
                    "pid":     proc.pid,
                    "name":    proc.name(),
                    "cpu_pct": cpu,
                    "ram_mb":  mem_mb,
                    "reason":  ", ".join(reason),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue

    return results


# ─── CLI DE DIAGNÓSTICO ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== ProcessManager — Diagnóstico ===")
    if not is_available():
        print("ERROR: psutil no instalado. Ejecuta: pip install psutil")
        sys.exit(1)

    print(f"CPU threshold: {CPU_THRESHOLD_PCT}%  |  RAM threshold: {RAM_THRESHOLD_MB} MB\n")
    candidates = list_candidates()
    if not candidates:
        print("No se detectaron candidatos a suspender con los umbrales actuales.")
    else:
        print(f"{'PID':>7}  {'Nombre':<35}  {'CPU':>6}  {'RAM':>8}  Razón")
        print("─" * 75)
        for c in sorted(candidates, key=lambda x: -x["ram_mb"]):
            print(f"{c['pid']:>7}  {c['name']:<35}  {c['cpu_pct']:>5.1f}%  "
                  f"{c['ram_mb']:>6.0f}MB  {c['reason']}")
    print()