#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT
#
# MintMachine: información de hardware, drivers y software para Linux.
#
# Copyright (c) 2026 José Antonio Ramos Miralles «Sombra» <hola@joseantonioramos.es>
# Se concede permiso para usar, copiar, modificar y distribuir este programa
# bajo los términos de la licencia MIT (archivo LICENSE).
#
# Principios de diseño:
#   - Un solo archivo, sin dependencias fuera de lo que trae Linux Mint / LMDE
#     (Python 3 + GTK 3). Las utilidades externas (lspci, lsblk, ip...) se usan
#     si están y, si no, la sección correspondiente se queda más corta.
#   - Solo lee: no cambia nada del sistema, no necesita root y no envía nada
#     a internet.
#   - Las recomendaciones se limitan a acciones seguras desde el propio sistema.
#     Nunca se pide abrir el equipo ni tocar componentes: eso, a un técnico.
#   - Si no hay entorno gráfico, funciona en modo texto.
#
# Uso:
#   python3 mintmachine.py              interfaz gráfica
#   python3 mintmachine.py --texto      informe por terminal
#   python3 mintmachine.py --html informe.html [--anon]
#   python3 mintmachine.py --json | --foro | --csv historico.csv

import argparse
import collections
import csv
import datetime
import getpass
import glob
import html
import io
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import unicodedata

APP = "MintMachine"
AUTHOR = "Sombra"
AUTHOR_FULL = "José Antonio Ramos Miralles «Sombra»"
EMAIL = "hola@joseantonioramos.es"
VERSION = "0.5.4"
JSON_SCHEMA = 2

READONLY = "MintMachine solo lee información. No cambia nada en tu equipo y no envía datos a internet"

DISCLAIMER = ("MintMachine solo lee información: no cambia nada en tu equipo. Sus recomendaciones son "
              "orientativas y se limitan a acciones seguras desde el propio sistema. No abras el equipo "
              "ni manipules sus componentes: cualquier revisión física (limpieza interna, cambio de "
              "disco, memoria o batería) debe hacerla un servicio técnico o el fabricante. Antes de "
              "cualquier cambio importante, haz una copia de seguridad de tus archivos.")

# ───────────────────────────── utilidades ─────────────────────────────

# En Debian el usuario normal no tiene /usr/sbin en el PATH, y ahí viven
# utilidades como iw o dkms.
_PATH = os.environ.get("PATH", "/usr/bin:/bin") + ":/usr/sbin:/sbin"
_ENV = dict(os.environ, LC_ALL="C", LANG="C", PATH=_PATH)


def read(path, default=""):
    try:
        with open(path, "r", errors="replace") as f:
            return f.read().strip()
    except Exception:
        return default


def read_int(path, default=None):
    try:
        return int(read(path))
    except Exception:
        return default


def have(cmd):
    return shutil.which(cmd, path=_PATH)


# Utilidades que se han buscado y no están instaladas: el Diagnóstico las lista con el
# paquete que las trae. Con --debug, cada orden deja una línea en la salida de errores.
_MISSING = set()
_DEBUG = [False]


def _trace(cmd, t0, state):
    """Traza de --debug. Solo el nombre de la orden y sus opciones: ni argumentos (pueden llevar
    rutas o números de serie) ni la salida. No se guarda en ningún archivo."""
    if _DEBUG[0]:
        opts = " ".join(a for a in cmd[1:] if a.startswith("-"))
        print(f"[debug] {time.monotonic() - t0:6.2f} s  {state:<8} {cmd[0]} {opts}".rstrip(), file=sys.stderr)


def run_ok(cmd, timeout=5):
    """True si la orden termina con código 0."""
    exe, t0 = have(cmd[0]), time.monotonic()
    if not exe:
        _MISSING.add(cmd[0])
        _trace(cmd, t0, "falta")
        return False
    try:
        ok = subprocess.run([exe] + list(cmd[1:]), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL, timeout=timeout, env=_ENV).returncode == 0
        _trace(cmd, t0, "bien" if ok else "error")
        return ok
    except Exception as e:
        _trace(cmd, t0, "tiempo" if isinstance(e, subprocess.TimeoutExpired) else "fallo")
        return False


def run(cmd, timeout=8):
    """Ejecuta una orden y devuelve su salida ('' si falla o no existe)."""
    exe, t0 = have(cmd[0]), time.monotonic()
    if not exe:
        _MISSING.add(cmd[0])
        _trace(cmd, t0, "falta")
        return ""
    try:
        p = subprocess.run([exe] + list(cmd[1:]), stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=timeout,
                           env=_ENV, text=True, errors="replace")
        _trace(cmd, t0, "bien" if p.returncode == 0 else "error")
        return p.stdout.strip()
    except Exception as e:
        _trace(cmd, t0, "tiempo" if isinstance(e, subprocess.TimeoutExpired) else "fallo")
        return ""


_ONCE = []


def once(fn):
    """Cachea funciones costosas cuyo resultado no cambia entre refrescos."""
    cache = {}

    def wrapper():
        if "v" not in cache:
            cache["v"] = fn()
        return cache["v"]
    _ONCE.append(cache)
    return wrapper


def clear_cache():
    for c in _ONCE:
        c.clear()


# ─────────────────────────────── idiomas ───────────────────────────────
#
# El texto original está en español. Las traducciones son archivos .po normales
# (po/en.po, po/fr.po...), que cualquiera puede revisar con Poedit o Weblate.
# _() traduce un texto exacto; los textos con datos se escriben como plantilla:
# _("Quedan {n} libres").format(n=...). Los bloques del informe (títulos,
# claves, cabeceras, notas y valores fijos) se traducen solos al construirse.

LANGS = collections.OrderedDict([("es", "Español"), ("en", "English"), ("fr", "Français"),
                                 ("ja", "日本語"), ("zh", "中文（简体）")])
_LANG = ["es"]
_CAT = {}
CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "mintmachine",
                      "config.json")


def _(s):
    return _CAT.get(s, s) if s else s


def po_dirs():
    here = os.path.dirname(os.path.realpath(__file__))
    return [os.path.join(here, "po"), "/usr/share/mintmachine/po"]


def parse_po(path):
    """Lector mínimo de .po: msgid/msgstr con cadenas de varias líneas. Sin plurales ni contextos."""
    cat, key, cur, field = {}, None, [], None

    def unq(t):
        esc = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}
        return re.sub(r'\\(.)', lambda m: esc.get(m.group(1), m.group(1)), t.strip()[1:-1])

    def flush():
        if key is not None and field == "msgstr":
            val = "".join(cur)
            if key and val:
                cat[key] = val
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return {}
    for line in lines + [""]:
        line = line.strip()
        if line.startswith("msgid "):
            flush()
            key, cur, field = None, [unq(line[6:])], "msgid"
        elif line.startswith("msgstr "):
            key, cur, field = "".join(cur), [unq(line[7:])], "msgstr"
        elif line.startswith('"') and field:
            cur.append(unq(line))
        elif not line or line.startswith("#"):
            flush()
            if not line.startswith("#"):
                key, cur, field = None, [], None
    flush()
    return cat


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_config(**kw):
    d = load_config()
    d.update(kw)
    try:
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


# ── historial local: salud de los discos, pruebas y mediciones. Vive junto a la configuración,
# no sale nunca del equipo y se borra con «Desinstalar». MM_SIN_HISTORIAL=1 lo desactiva (pruebas).
HISTORY = os.path.join(os.path.dirname(CONFIG), "historial.json")


def history_load():
    try:
        with open(HISTORY, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def history_save(d):
    if os.environ.get("MM_SIN_HISTORIAL"):
        return
    try:
        os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
        tmp = HISTORY + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=0)
        os.replace(tmp, HISTORY)
    except OSError:
        pass


def history_add(kind, entry, keep=300):
    """Añade una entrada fechada a la lista «kind» del historial y la devuelve entera."""
    d = history_load()
    lst = d.setdefault(kind, [])
    lst.append(dict(entry, t=time.strftime("%Y-%m-%d %H:%M")))
    d[kind] = lst[-keep:]
    history_save(d)
    return d[kind]


def system_language():
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        for v in os.environ.get(var, "").split(":"):
            code = v.split("_")[0].split(".")[0].lower()
            if code in LANGS:
                return code
            if code and code not in ("c", "posix"):
                return "en"            # otro idioma: inglés, que lo entiende más gente
    return "en"


def set_language(code=None):
    code = code or load_config().get("idioma") or system_language()
    code = code if code in LANGS else "en"
    _LANG[0] = code
    _CAT.clear()
    if code != "es":
        for d in po_dirs():
            cat = parse_po(os.path.join(d, code + ".po"))
            if cat:
                _CAT.update(cat)
                break
    return code


def num(x, dec=1):
    """Número con el separador decimal del idioma (coma en español y francés)."""
    try:
        t = f"{float(x):.{dec}f}"
    except Exception:
        return ""
    return t.replace(".", ",") if _LANG[0] in ("es", "fr") else t


def when(dt=None):
    dt = dt or datetime.datetime.now()
    return dt.strftime("%d/%m/%Y %H:%M" if _LANG[0] in ("es", "fr") else "%Y-%m-%d %H:%M")


def human(n, dec=1):
    try:
        n = float(n)
    except Exception:
        return ""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if abs(n) < 1024 or unit == "PiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{num(n, dec)} {unit}"
        n /= 1024


def fold(s):
    """Minúsculas y sin tildes, para buscar."""
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")


def natural(s):
    """Clave de orden natural («card2» antes que «card10») que nunca compara número con texto."""
    return [(0, int(t), "") if t.isdigit() else (1, 0, t) for t in re.split(r"(\d+)", s)]


def pct(part, total):
    return 100.0 * part / total if total else 0.0


def keyvals(text, sep="="):
    d = {}
    for line in text.splitlines():
        if sep in line:
            k, v = line.split(sep, 1)
            d[k.strip()] = v.strip().strip('"')
    return d


_SECRETS = set()           # valores sensibles vistos: se tapan también si reaparecen en otro texto
_SECRETS_RX = [None, 0]


class Sens(str):
    """Valor sensible (número de serie, MAC, IP, nombre...) que se puede ocultar."""

    def __new__(cls, v=""):
        s = super().__new__(cls, v)
        t = str(v).strip()
        if len(t) >= 3 and t not in ("00:00:00:00:00:00",) and not t.isdigit():
            _SECRETS.add(t)
        return s


class SensField(Sens):
    """Sensible solo en su campo: no se busca en el resto de textos (nombres de dispositivos)."""

    def __new__(cls, v=""):
        return str.__new__(cls, v)


def secret(v):
    """Registra un dato privado que no se muestra como campo propio (usuario, carpeta personal)."""
    if v and len(v) >= 3:
        _SECRETS.add(v)


_MAC = re.compile(r"(?<![\w:])(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}(?![\w:])")
_IPV4 = re.compile(r"(?<![\w.:~+-])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\w.~+-])")
_UUID = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
_IPV6 = re.compile(r"(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{1,4}(?![\w:])")


def scrub(s):
    """Tapa datos personales que aparezcan dentro de un texto cualquiera."""
    if not s:
        return s
    if _SECRETS_RX[1] != len(_SECRETS):
        toks = sorted(_SECRETS, key=len, reverse=True)
        _SECRETS_RX[0] = re.compile(r"(?<![\w])(?:" + "|".join(re.escape(t) for t in toks) + r")(?![\w])") \
            if toks else None
        _SECRETS_RX[1] = len(_SECRETS)
    if _SECRETS_RX[0] is not None:
        s = _SECRETS_RX[0].sub(_("(oculto)"), s)
    s = _MAC.sub("xx:xx:xx:xx:xx:xx", s)
    s = _UUID.sub(_("(UUID oculto)"), s)
    s = _IPV4.sub(lambda m: m.group(0) if m.group(0).startswith("127.") else "x.x.x.x", s)
    return _IPV6.sub(lambda m: _("(IPv6 oculta)") if m.group(0) != "::1" and
                     ("::" in m.group(0) or m.group(0).count(":") >= 5) else m.group(0), s)


def show(v, anon=False):
    if anon:
        if isinstance(v, Sens):
            return _("(oculto)") if v else ""
        return scrub(str(v))
    return str(v)


# ───────────────────── modelo de datos de las secciones ─────────────────────

def tr(v):
    """Traduce un valor del informe si es un texto fijo conocido; los datos (modelos, versiones) quedan igual."""
    return v if isinstance(v, Sens) else _(str(v))


def kv(title, rows, adv=False, help=""):
    """Pares clave/valor. adv=True: detalle técnico, que la ventana muestra plegado."""
    return {"type": "kv", "title": _(title), "adv": adv, "help": _(help),
            "rows": [(_(k), tr(v)) for k, v in rows if v not in (None, "")]}


def table(title, headers, rows, adv=False, help=""):
    n = len(headers)
    clean = []
    for r in rows:
        r = [c if isinstance(c, Sens) else ("" if c is None else tr(c)) for c in r]
        clean.append((r + [""] * n)[:n])
    return {"type": "table", "title": _(title), "headers": [_(h) for h in headers], "rows": clean, "adv": adv,
            "help": _(help)}


def bars(title, items, help="", gauge=False):
    """items: [(etiqueta, fracción 0..1, texto)]. gauge=True: la ventana los dibuja como indicadores circulares."""
    return {"type": "bars", "title": _(title), "adv": False, "help": _(help), "gauge": gauge,
            "rows": [(_(l), max(0.0, min(1.0, f)), tr(t)) for l, f, t in items]}


def note(text):
    return {"type": "note", "title": "", "text": _(text), "adv": False}


def chart(title, series, unit):
    """Gráfica temporal. series: [(etiqueta, clave del muestreador)]."""
    with SAMPLER.lock:
        rows = [(_(label), list(SAMPLER.h[key])) for label, key in series if SAMPLER.h[key]]
    return {"type": "chart", "title": _(title), "unit": unit, "rows": rows, "adv": False}


def fmt_unit(v, unit):
    if unit == "B/s":
        return human(v) + "/s"
    return f"{v:.0f} {unit}"


def section(sid, title, blocks):
    blocks = [b for b in blocks if b and (b["type"] == "note" or b["rows"])]   # sin bloques vacíos
    return {"id": sid, "title": _(title), "blocks": blocks}


# Herramientas gráficas del propio sistema a las que puede llevar un aviso del
# diagnóstico. Se abren como programas normales: si necesitan permisos, son
# ellas las que piden la contraseña. MintMachine nunca ejecuta nada como root.
ACTIONS = {
    "updates": ("Abrir el Gestor de actualizaciones", [["mintupdate"], ["update-manager"], ["gnome-software", "--mode=updates"]]),
    "drivers": ("Abrir el Gestor de controladores", [["driver-manager"], ["software-properties-gtk", "--open-tab=4"]]),
    "disks": ("Abrir Discos", [["gnome-disks"]]),
    "usage": ("Ver qué ocupa el disco", [["baobab"]]),
    "backup": ("Abrir Copias de seguridad", [["mintbackup"], ["deja-dup"]]),
    "snapshots": ("Abrir Timeshift", [["timeshift-launcher"], ["timeshift-gtk"]]),
    "firewall": ("Abrir el Cortafuegos", [["gufw"]]),
    "firmware": ("Abrir Firmware", [["gnome-firmware"]]),
    "sysmon": ("Abrir el Monitor del sistema", [["gnome-system-monitor"], ["mate-system-monitor"], ["xfce4-taskmanager"]]),
    "logs": ("Abrir los registros del sistema", [["mintreport"], ["gnome-logs"]]),
    "power": ("Abrir la configuración de energía", [["cinnamon-settings", "power"], ["mate-power-preferences"],
                                                   ["xfce4-power-manager-settings"]]),
}


def action_cmd(key):
    """Primera orden disponible para una acción, o None."""
    for cmd in ACTIONS.get(key, ("", []))[1]:
        if have(cmd[0]):
            return cmd
    return None


class Ctx:
    """Datos compartidos entre recopiladores: resumen y avisos del diagnóstico."""

    def __init__(self):
        self.findings = []   # dicts: level (bad, warn, info, ok), area, text, todo, action
        self.summary = {}
        self.data = {}

    def flag(self, level, area, text, todo="", action=None):
        """Deja un aviso para el Diagnóstico. «todo» dice qué hacer, siempre con acciones
        seguras desde el sistema; «action» es una clave de ACTIONS."""
        self.findings.append({"level": level, "area": _(area), "text": _(text), "todo": _(todo), "action": action})


# ─────────────────── muestreo en vivo (gráficas del Monitor) ───────────────────

HIST = 120          # muestras que se guardan: dos minutos a una por segundo
CPU_CHIPS = ("coretemp", "k10temp", "zenpower", "cpu_thermal")
SKIP_DISKS = ("loop", "ram", "zram", "dm-", "md", "sr", "fd")


class Sampler:
    """Toma una muestra por segundo de CPU, memoria, red, disco, temperatura y procesos."""

    def __init__(self):
        self.lock = threading.Lock()
        self.h = collections.defaultdict(lambda: collections.deque(maxlen=HIST))
        self.cpu = {}        # uso (%) por CPU en el último intervalo; 'cpu' es el total
        self.procs = []      # (cpu %, memoria en bytes, pid, nombre)
        self.apps = {}       # pid → aplicación a la que pertenece (para agrupar procesos)
        self.nprocs = 0
        self._stat, self._io, self._t = {}, None, None
        self._pticks, self._pt, self._n, self._names = {}, None, 0, {}
        self._temp_files = None
        self._nv, self._nv_busy = None, False
        self._rc6, self._rc6_prev = None, None

    def tick(self):
        with self.lock:
            now = time.monotonic()
            dt = now - self._t if self._t else 0
            self._t = now
            for step in (self._cpu, self._mem, lambda: self._net_disk(dt), self._temp, self._gpu):
                try:
                    step()
                except Exception:
                    pass
            if self._n % 2 == 0:
                try:
                    self._processes(now)
                except Exception:
                    pass
            self._n += 1

    def _cpu(self):
        now = {}
        for line in read("/proc/stat").splitlines():
            if line.startswith("cpu"):
                p = line.split()
                v = [int(x) for x in p[1:9]]
                if len(v) >= 5:
                    now[p[0]] = (sum(v), v[3] + v[4])
        res = {}
        for k, (t, i) in now.items():
            if k in self._stat:
                dt, di = t - self._stat[k][0], i - self._stat[k][1]
                if dt > 0:
                    res[k] = 100.0 * (dt - di) / dt
        self._stat = now
        if res:
            self.cpu = res
            self.h["cpu"].append(res.get("cpu", 0.0))

    def _mem(self):
        m = meminfo()
        if m.get("MemTotal"):
            self.h["ram"].append(pct(m["MemTotal"] - m.get("MemAvailable", 0), m["MemTotal"]))
        if m.get("SwapTotal"):
            self.h["swap"].append(pct(m["SwapTotal"] - m.get("SwapFree", 0), m["SwapTotal"]))

    def _net_disk(self, dt):
        rx = tx = 0
        nets = glob.glob("/sys/class/net/*")
        real = [n for n in nets if os.path.exists(n + "/device")] or \
               [n for n in nets if os.path.basename(n) != "lo"]
        for n in real:
            rx += read_int(n + "/statistics/rx_bytes", 0) or 0
            tx += read_int(n + "/statistics/tx_bytes", 0) or 0
        rd = wr = 0
        for line in read("/proc/diskstats").splitlines():
            p = line.split()
            if len(p) > 9 and not p[2].startswith(SKIP_DISKS) and os.path.exists("/sys/block/" + p[2]):
                rd += int(p[5]) * 512
                wr += int(p[9]) * 512
        cur = (rx, tx, rd, wr)
        if self._io and dt > 0:
            for key, a, b in zip(("rx", "tx", "dread", "dwrite"), cur, self._io):
                self.h[key].append(max(0.0, (a - b) / dt))
        self._io = cur

    def _temp(self):
        if self._temp_files is None:
            self._temp_files = []
            for hw in glob.glob("/sys/class/hwmon/hwmon*"):
                if read(hw + "/name") in CPU_CHIPS:
                    self._temp_files += glob.glob(hw + "/temp*_input")
        vals = [v / 1000 for v in (read_int(f) for f in self._temp_files) if v]
        if vals:
            self.h["temp"].append(max(vals))

    def _gpu(self):
        amd = glob.glob("/sys/class/drm/card*/device/gpu_busy_percent")
        if amd:
            v = read_int(amd[0])
            if v is not None:
                self.h["gpu"].append(float(v))
        elif have("nvidia-smi"):
            if self._n % 3 == 0 and not self._nv_busy:     # nvidia-smi tarda: va en segundo plano
                self._nv_busy = True

                def ask():
                    out = run(["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"], 4)
                    try:
                        self._nv = float(out.splitlines()[0])
                    except Exception:
                        pass
                    self._nv_busy = False
                threading.Thread(target=ask, daemon=True).start()
            if self._nv is not None:
                self.h["gpu"].append(self._nv)
        self._gpu_intel()

    def _gpu_intel(self):
        """Uso de la gráfica Intel. El kernel no publica un porcentaje, pero sí el tiempo que la
        gráfica pasa dormida (RC6): lo que no ha estado dormida, ha estado trabajando."""
        if self._rc6 is None:
            self._rc6 = ""
            for pat, enable in (("/sys/class/drm/card[0-9]*/gt/gt0/rc6_residency_ms", "rc6_enable"),          # i915
                                ("/sys/class/drm/card[0-9]*/device/tile0/gt0/gtidle/idle_residency_ms", ""),  # xe
                                ("/sys/class/drm/card[0-9]*/power/rc6_residency_ms", "rc6_enable")):          # i915 antiguo
                for f in sorted(glob.glob(pat)):
                    if not enable or read(os.path.join(os.path.dirname(f), enable)) not in ("0", "0x0"):
                        self._rc6 = f
                        break
                if self._rc6:
                    break
        if not self._rc6:
            return
        ms, now = read_int(self._rc6), time.monotonic()
        if ms is None:
            return
        prev, self._rc6_prev = self._rc6_prev, (ms, now)
        if prev and now - prev[1] > 0.2 and ms >= prev[0]:            # el contador puede dar la vuelta
            idle = (ms - prev[0]) / ((now - prev[1]) * 1000)
            self.h["igpu"].append(max(0.0, min(100.0, 100.0 * (1 - idle))))

    def _processes(self, now):
        clk, page = os.sysconf("SC_CLK_TCK"), os.sysconf("SC_PAGE_SIZE")
        dt = now - self._pt if self._pt else 0
        ticks, rows = {}, []
        for d in os.listdir("/proc"):
            if not d.isdigit():
                continue
            try:
                with open(f"/proc/{d}/stat", errors="replace") as f:
                    st = f.read()
                r = st.rindex(")")
                name, rest = st[st.index("(") + 1:r], st[r + 2:].split()
                t, rss = int(rest[11]) + int(rest[12]), int(rest[21]) * page
            except Exception:
                continue
            if len(name) == 15:          # el kernel recorta el nombre a 15 caracteres
                full = self._names.get(d)
                if full is None:
                    arg0 = read(f"/proc/{d}/cmdline").split("\0")[0]
                    full = os.path.basename(arg0.split()[0]) if arg0 else ""
                    full = full if full.startswith(name) else name
                    self._names[d] = full
                name = full
            ticks[d] = t
            if d not in self.apps:
                self.apps[d] = app_name(read(f"/proc/{d}/cgroup"), proc_exe(d) or name)
            if dt > 0 and d in self._pticks:
                rows.append((100.0 * (t - self._pticks[d]) / clk / dt, rss, d, name))
        self._pticks, self._pt, self.nprocs = ticks, now, len(ticks)
        self._names = {k: v for k, v in self._names.items() if k in ticks}
        self.apps = {k: v for k, v in self.apps.items() if k in ticks}
        if rows:
            self.procs = rows


def proc_exe(pid):
    """Nombre del ejecutable de un proceso ('' si no es nuestro o es un hilo del kernel)."""
    try:
        return os.path.basename(os.readlink(f"/proc/{pid}/exe")).replace(" (deleted)", "")
    except OSError:
        return ""


def app_name(cgroup, fallback):
    """Aplicación a la que pertenece un proceso, según su grupo de control (cgroup).

    Los escritorios que lanzan cada aplicación en su propio grupo (GNOME, KDE, Flatpak, Snap) dan
    el nombre exacto; en el resto se agrupa por ejecutable, que junta por ejemplo todos los
    procesos de un navegador. Solo sale el nombre de la aplicación o del servicio: se descartan
    el número de usuario y el nombre de las instancias (como el de una conexión VPN)."""
    unit = ""
    for line in cgroup.splitlines():
        if line.startswith("0::") or ":name=systemd:" in line:
            unit = line.rsplit("/", 1)[-1].strip()
            break
    m = re.match(r"app-(.+?)(?:-[0-9a-f]+)?\.scope$", unit) or re.match(r"app-(.+?)(?:@.*)?\.service$", unit)
    if m:
        name = m.group(1)
        if name.startswith("flatpak-"):
            name = name[8:]
        elif "-" in name:                       # app-<lanzador>-<aplicación>: los guiones propios van escapados
            name = name.split("-", 1)[1]
        name = re.sub(r"\\x([0-9a-fA-F]{2})", lambda x: chr(int(x.group(1), 16)), name)
        return name or fallback
    m = re.match(r"snap\.([^.]+)\.", unit)
    if m:
        return m.group(1)
    if unit.endswith(".service") and not unit.startswith(("user@", "session-")) and "/system.slice/" in cgroup:
        return unit[:-8].split("@")[0] or fallback
    return fallback


SAMPLER = Sampler()


def sec_monitor(ctx):
    with SAMPLER.lock:
        cores = sorted(((int(k[3:]), v) for k, v in SAMPLER.cpu.items() if k != "cpu"))
        procs, nprocs, owner = list(SAMPLER.procs), SAMPLER.nprocs, dict(SAMPLER.apps)
    psi = []
    for res, label in (("cpu", "CPU"), ("memory", "memoria"), ("io", "disco")):
        m = re.search(r"some avg10=([\d.]+)", read("/proc/pressure/" + res))
        if m:
            psi.append(f"{label} {float(m.group(1)):.0f} %")
            if res == "memory" and float(m.group(1)) >= 10:
                ctx.flag("warn", "Memoria", _("Los programas están esperando por falta de memoria (presión del {n:.0f} %), y eso hace que el equipo vaya lento.").format(n=float(m.group(1))),
                         "Cierra programas o pestañas del navegador que no estés usando. Si te pasa a "
                         "menudo, un servicio técnico puede decirte si tu equipo admite más memoria.", "sysmon")
    procs = [r for r in procs if r[1] > 0 or r[0] >= 0.1]      # sin hilos del kernel inactivos
    by_cpu = sorted(procs, reverse=True)[:8]
    by_mem = sorted(procs, key=lambda r: r[1], reverse=True)[:8]
    apps = {}
    for c, rss, pid, n in procs:
        a = apps.setdefault(owner.get(pid) or n, [0, 0.0, 0])
        a[0], a[1], a[2] = a[0] + 1, a[1] + c, a[2] + rss
    by_app = sorted(apps.items(), key=lambda kv: (kv[1][2], kv[1][1]), reverse=True)[:8]
    blocks = [
        chart("Procesador", [("Uso", "cpu")], "%"),
        chart("Memoria", [("RAM", "ram"), ("Swap", "swap")], "%"),
        chart("Red", [("Bajada", "rx"), ("Subida", "tx")], "B/s"),
        chart("Disco", [("Lectura", "dread"), ("Escritura", "dwrite")], "B/s"),
        chart("Temperatura del procesador", [("CPU", "temp")], "°C"),
        chart("Uso de la gráfica", [("GPU", "gpu"), ("Intel (integrada)", "igpu")], "%"),
        {"type": "cores", "title": _("Uso de cada hilo"), "rows": [(n, v) for n, v in cores]},
        kv("Ahora mismo", [
            ("Carga media (1, 5, 15 min)", " ".join(num(x, 2) for x in read("/proc/loadavg").split()[:3])),
            ("Procesos en marcha", nprocs or ""),
            ("Tiempo perdido esperando recursos (10 s)", ", ".join(psi)),
        ]),
        table("Aplicaciones que más consumen", ["Aplicación", "Procesos", "Memoria", "CPU"],
              [(a, k, human(rss), f"{num(c)} %") for a, (k, c, rss) in by_app],
              help="Suma todos los procesos de cada aplicación; un navegador, por ejemplo, abre "
                   "muchos. La memoria es aproximada: la parte que comparten se cuenta en cada uno."),
        table("Procesos que más procesador usan", ["Proceso", "PID", "CPU", "Memoria"],
              [(n, pid, f"{num(c)} %", human(rss)) for c, rss, pid, n in by_cpu]),
        table("Procesos que más memoria ocupan", ["Proceso", "PID", "Memoria", "CPU"],
              [(n, pid, human(rss), f"{num(c)} %") for c, rss, pid, n in by_mem]),
    ]
    if not SAMPLER.h["cpu"]:
        blocks.append(note("Las gráficas empiezan a llenarse a los pocos segundos de abrir el programa."))
    return section("monitor", "Monitor en vivo", blocks)


# ───────────────────────────────── CPU ─────────────────────────────────

def cpuinfo():
    blocks, cur = [], {}
    for line in read("/proc/cpuinfo").splitlines():
        if not line.strip():
            if cur:
                blocks.append(cur)
                cur = {}
        elif ":" in line:
            k, v = line.split(":", 1)
            cur[k.strip()] = v.strip()
    if cur:
        blocks.append(cur)
    return blocks


@once
def lscpu_info():
    return keyvals(run(["lscpu"]), ":")


@once
def virt_env():
    return run(["systemd-detect-virt"])


def cpu_dirs():
    return sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*"), key=natural)


def cpu_freqs():
    out = []
    for d in cpu_dirs():
        n = int(re.search(r"(\d+)$", d).group(1))
        out.append({"n": n,
                    "cur": read_int(d + "/cpufreq/scaling_cur_freq"),
                    "min": read_int(d + "/cpufreq/cpuinfo_min_freq"),
                    "max": read_int(d + "/cpufreq/cpuinfo_max_freq"),
                    "gov": read(d + "/cpufreq/scaling_governor"),
                    "drv": read(d + "/cpufreq/scaling_driver")})
    return out


def cpu_caches():
    seen = {}
    for idx in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cache/index[0-9]*"):
        level = read(idx + "/level")
        if not level:
            continue
        key = (level, read(idx + "/type"), read(idx + "/size"),
               read(idx + "/ways_of_associativity"))
        seen.setdefault(key, set()).add(read(idx + "/shared_cpu_list"))
    names = {"Data": " de datos", "Instruction": " de instrucciones", "Unified": ""}
    rows = []
    for (level, typ, size, ways), inst in sorted(seen.items()):
        val = f"{len(inst)} × {size}" + (_(", {ways} vías").format(ways=ways) if ways and ways != "0" else "")
        rows.append((f"L{level}{_(names.get(typ, ' ' + typ))}", val))
    return rows


ISETS = [("mmx", "MMX"), ("sse", "SSE"), ("sse2", "SSE2"), ("pni", "SSE3"),
         ("ssse3", "SSSE3"), ("sse4_1", "SSE4.1"), ("sse4_2", "SSE4.2"),
         ("sse4a", "SSE4A"), ("avx", "AVX"), ("avx2", "AVX2"),
         ("avx512f", "AVX-512"), ("avx_vnni", "AVX-VNNI"), ("fma", "FMA3"),
         ("aes", "AES-NI"), ("sha_ni", "SHA"), ("lm", "x86-64"),
         ("vmx", "VT-x"), ("svm", "AMD-V"), ("ht", "HTT"),
         ("neon", "NEON"), ("asimd", "ASIMD"), ("sve", "SVE")]

COOL_TODO = ("Comprueba que las rejillas de ventilación no estén tapadas: no uses el portátil sobre la "
             "cama, el sofá o las piernas, y deja espacio libre alrededor del equipo. Cierra los programas "
             "que no uses. Si sigue pasando, que un servicio técnico revise la refrigeración: no abras "
             "el equipo por tu cuenta.")


def pretty_cpu(model):
    """«Intel(R) Core(TM) i7-1255U CPU @ 1.70GHz» → «Intel Core i7-1255U»."""
    m = re.sub(r"\((R|TM|tm|r)\)|®|™", "", model)
    m = re.sub(r"\s+(CPU\s+)?@\s*[\d.]+\s*GHz", "", m)
    m = re.sub(r"\s+(\d+-Core|Quad-Core|Dual-Core|Six-Core|Eight-Core)\s+Processor$", "", m)
    m = re.sub(r"\s+(CPU|Processor)$", "", m.strip())
    return re.sub(r"\s+", " ", m).strip() or model


VENDORS = {"GenuineIntel": "Intel", "AuthenticAMD": "AMD", "HygonGenuine": "Hygon",
           "CentaurHauls": "VIA/Centaur"}


def cpu_live():
    """Indicadores en vivo de la pestaña Procesador: uso total, frecuencia, temperatura y cada hilo."""
    with SAMPLER.lock:
        usage = dict(SAMPLER.cpu)
        temp = SAMPLER.h["temp"][-1] if SAMPLER.h["temp"] else None
    items = []
    if "cpu" in usage:
        items.append(("Uso total", usage["cpu"] / 100, _("{cpu:.0f} % en uso").format(cpu=usage["cpu"])))
    freqs = cpu_freqs()
    curs = [f["cur"] for f in freqs if f["cur"]]
    maxs = [f["max"] for f in freqs if f["max"]]
    if not curs:
        curs = [float(b["cpu MHz"]) * 1000 for b in cpuinfo() if b.get("cpu MHz")]
    if curs:
        cur = sum(curs) / len(curs) / 1000
        top = max(maxs) / 1000 if maxs else 0
        items.append(("Frecuencia media", min(cur / top, 1) if top else 0,
                      f"{cur:.0f} MHz" + (" · " + _("máxima {mx} MHz").format(mx=f"{top:.0f}") if top else "")))
    if temp is not None:
        items.append(("Temperatura", temp / 100, _("{temp:.0f} °C en el procesador").format(temp=temp)))
    cores = sorted((int(k[3:]), v) for k, v in usage.items() if k != "cpu")
    blocks = [bars("Ahora mismo", items, gauge=True)] if items else []
    if cores:
        blocks.append({"type": "cores", "title": _("Uso de cada hilo"), "rows": cores})
    return blocks


def sec_cpu(ctx):
    blocks = [b for b in cpuinfo() if "processor" in b]
    b0 = blocks[0] if blocks else {}
    ls = lscpu_info()
    model = b0.get("model name") or ls.get("Model name") or platform.processor() or "Desconocido"
    model = re.sub(r"\s+", " ", model)
    threads = len(blocks) or os.cpu_count() or 1
    cores = len({(b.get("physical id", "0"), b.get("core id", b["processor"]))
                 for b in blocks}) or threads
    sockets = len({b.get("physical id", "0") for b in blocks}) or 1
    flags = set((b0.get("flags") or b0.get("Features") or "").split())
    freqs = cpu_freqs()
    with SAMPLER.lock:
        usage = dict(SAMPLER.cpu)

    curs = [f["cur"] for f in freqs if f["cur"]]
    if not curs:
        curs = [float(b["cpu MHz"]) * 1000 for b in blocks if b.get("cpu MHz")]
    mins = [f["min"] for f in freqs if f["min"]]
    maxs = [f["max"] for f in freqs if f["max"]]
    f0 = freqs[0] if freqs else {}

    fam = " / ".join(x for x in (b0.get("cpu family"), b0.get("model"), b0.get("stepping")) if x)
    hybrid = ""
    pc, ec = read("/sys/devices/cpu_core/cpus"), read("/sys/devices/cpu_atom/cpus")
    if pc and ec:
        hybrid = _("Sí: hilos {pc} en núcleos P, hilos {ec} en núcleos E").format(pc=pc, ec=ec)

    virt = virt_env()
    if "vmx" in flags:
        vt = "Intel VT-x disponible"
    elif "svm" in flags:
        vt = "AMD-V disponible"
    else:
        vt = "No detectada (o desactivada en la BIOS)"

    thr = max([read_int(d + "/thermal_throttle/package_throttle_count", 0) or 0 for d in cpu_dirs()]
              + [read_int(d + "/thermal_throttle/core_throttle_count", 0) or 0 for d in cpu_dirs()] + [0])
    if thr:
        ctx.flag("warn" if thr > 500 else "info", "Procesador",
                 _("El procesador ha bajado su velocidad por calor {thr} veces desde que encendiste el equipo.").format(thr=thr),
                 COOL_TODO)

    general = kv("Procesador", [
        ("Modelo", model),
        ("Fabricante", VENDORS.get(b0.get("vendor_id", ""), b0.get("vendor_id", ""))),
        ("Núcleos / hilos", f"{cores} / {threads}"),
        ("Arquitectura híbrida", hybrid),
        ("Frecuencia actual (media)", f"{sum(curs) / len(curs) / 1000:.0f} MHz" if curs else ""),
        ("Rango de frecuencias", f"{min(mins) / 1000:.0f} a {max(maxs) / 1000:.0f} MHz"
         if mins and maxs else ""),
        ("Carga media (1, 5, 15 min)", " ".join(num(x, 2) for x in read("/proc/loadavg").split()[:3])),
        ("Frenazos por temperatura desde el arranque", thr if os.path.isdir(
            "/sys/devices/system/cpu/cpu0/thermal_throttle") else ""),
        ("Virtualización", vt),
        ("Entorno", "Máquina física" if virt in ("", "none") else _("Virtualizado ({virt})").format(virt=virt)),
    ])
    tech = kv("Datos técnicos", [
        ("Arquitectura", platform.machine()),
        ("Familia / modelo / stepping", fam),
        ("Microcódigo", b0.get("microcode", "")),
        ("Zócalos", sockets),
        ("Gobernador / driver", " / ".join(x for x in (f0.get("gov"), f0.get("drv")) if x)),
        ("Direccionamiento", b0.get("address sizes", "")),
        ("Instrucciones", ", ".join(n for f, n in ISETS if f in flags)),
    ], adv=True)

    per_core = []
    for f in freqs:
        u = usage.get(f"cpu{f['n']}")
        per_core.append((_("CPU {n}").format(n=f['n']),
                         f"{f['cur'] / 1000:.0f} MHz" if f["cur"] else "",
                         f"{u:.0f} %" if u is not None else "midiendo"))

    vulns, vulnerable = [], []
    for p in sorted(glob.glob("/sys/devices/system/cpu/vulnerabilities/*")):
        st = read(p)
        name = os.path.basename(p)
        vulns.append((name, st))
        if st.startswith("Vulnerable"):
            vulnerable.append(name)
    if vulnerable:
        ctx.flag("warn", "Procesador", _("El kernel indica fallos de seguridad del procesador sin proteger: "
                                         "{lista}.").format(lista=", ".join(vulnerable)),
                 "Instala las actualizaciones pendientes, incluidas las del kernel, y el microcódigo del "
                 "procesador que ofrezca el Gestor de controladores. Después, reinicia.", "updates")
    ctx.data["cpu_vulnerable"] = vulnerable
    ctx.summary["cpu"] = _("{n} ({cores} núcleos, {threads} hilos)").format(n=pretty_cpu(model), cores=cores, threads=threads)

    return section("cpu", "Procesador", cpu_live() + [
        general,
        table("Hilos en tiempo real", ["Hilo", "Frecuencia", "Uso"], per_core),
        tech,
        kv("Cachés", cpu_caches(), adv=True,
           help="Memoria muy rápida dentro del propio procesador. Más caché suele significar más rendimiento."),
        table("Vulnerabilidades y mitigaciones", ["Vulnerabilidad", "Estado según el kernel"], vulns, adv=True,
              help="Fallos de seguridad conocidos de los procesadores y cómo los neutraliza el kernel. "
                   "«Not affected» y «Mitigation» son buenas noticias; «Vulnerable» no."),
    ])


# ───────────────────────────── placa base ─────────────────────────────

CHASSIS = {3: "Sobremesa", 4: "Sobremesa de perfil bajo", 5: "Pizza box", 6: "Minitorre",
           7: "Torre", 8: "Portátil", 9: "Portátil", 10: "Portátil", 11: "Dispositivo de mano",
           13: "Todo en uno", 14: "Subportátil", 17: "Servidor", 23: "Servidor en rack",
           30: "Tableta", 31: "Convertible", 32: "Desmontable", 35: "Mini PC", 36: "Stick PC"}


def dmi(name):
    v = read("/sys/class/dmi/id/" + name)
    junk = ("to be filled by o.e.m.", "default string", "system product name",
            "system manufacturer", "not specified", "none", "n/a")
    return "" if v.lower() in junk else v


def secure_boot():
    """None = arranque BIOS clásico; True/False = estado; '?' = desconocido."""
    if not os.path.isdir("/sys/firmware/efi"):
        return None
    for p in glob.glob("/sys/firmware/efi/efivars/SecureBoot-*"):
        try:
            with open(p, "rb") as f:
                d = f.read()
            if d:
                return d[-1] == 1
        except Exception:
            pass
    out = run(["mokutil", "--sb-state"])
    if "enabled" in out:
        return True
    if "disabled" in out:
        return False
    return "?"


def sec_board(ctx):
    sb = secure_boot()
    ctx.data["secure_boot"] = sb
    tpm = read("/sys/class/tpm/tpm0/tpm_version_major")
    ctx.data["tpm"] = tpm
    chassis = CHASSIS.get(read_int("/sys/class/dmi/id/chassis_type", 0), "")
    ctx.data["chassis"] = chassis
    comercial = dmi("product_version") if dmi("sys_vendor").upper() == "LENOVO" else ""
    equipo = " ".join(x for x in (dmi("sys_vendor"), comercial or dmi("product_name")) if x)
    placa = " ".join(x for x in (dmi("board_vendor"), dmi("board_name")) if x)
    bios = " ".join(x for x in (dmi("bios_vendor"), dmi("bios_version")) if x)
    ctx.summary["equipo"] = equipo
    ctx.summary["placa"] = placa
    ctx.summary["bios"] = f"{bios} ({dmi('bios_date')})" if bios and dmi("bios_date") else bios
    blocks = [
        kv("Equipo", [
            ("Fabricante", dmi("sys_vendor")), ("Modelo", dmi("product_name")),
            ("Versión", dmi("product_version")), ("Familia", dmi("product_family")),
            ("Formato", chassis),
            ("Número de serie", Sens(read("/sys/class/dmi/id/product_serial"))),
        ]),
        kv("Placa base", [
            ("Fabricante", dmi("board_vendor")), ("Modelo", dmi("board_name")),
            ("Revisión", dmi("board_version")),
        ]),
        kv("BIOS / UEFI", [
            ("Fabricante", dmi("bios_vendor")), ("Versión", dmi("bios_version")),
            ("Fecha", dmi("bios_date")), ("Revisión", dmi("bios_release")),
            ("Modo de arranque", "BIOS clásico (legacy)" if sb is None else "UEFI"),
            ("Secure Boot", {None: "No aplicable", True: "Activado", False: "Desactivado"}.get(sb, "Desconocido")),
            ("TPM", _("Versión {tpm}.x").format(tpm=tpm) if tpm else "No detectado"),
        ]),
    ]
    if not (equipo or placa or bios):
        blocks.append(note("Este sistema no expone datos DMI (habitual en máquinas virtuales, "
                           "contenedores y placas ARM)."))
    return section("placa", "Placa base y BIOS", blocks)


# ─────────────────────────────── memoria ───────────────────────────────

def meminfo():
    d = {}
    for line in read("/proc/meminfo").splitlines():
        k, _sep, v = line.partition(":")
        p = v.split()
        if p:
            try:
                d[k] = int(p[0]) * (1024 if len(p) > 1 else 1)
            except ValueError:
                pass
    return d


@once
def dmi_memory():
    """Módulos de RAM sin root: udev publica los datos de la tabla DMI."""
    props = keyvals(run(["udevadm", "info", "-q", "property", "-p", "/sys/devices/virtual/dmi/id"]))
    mods = {}
    for k, v in props.items():
        m = re.match(r"MEMORY_DEVICE_(\d+)_(.+)", k)
        if m:
            mods.setdefault(int(m.group(1)), {})[m.group(2)] = v
    return props, [mods[i] for i in sorted(mods)]


# Códigos JEDEC JEP106 (banco de continuación + código, con su bit de paridad) de los fabricantes de
# módulos más habituales, tomados de la tabla de decode-dimms (i2c-tools). Algunas BIOS publican el
# fabricante solo así, por ejemplo «04CD» para G.Skill.
JEDEC_RAM = {
    "802C": "Micron", "80AD": "SK hynix", "80CE": "Samsung", "80C1": "Infineon", "8054": "HP",
    "0194": "Smart Modular", "0198": "Kingston", "0132": "Mushkin", "01BA": "PNY", "014F": "Transcend",
    "017A": "Apacer", "029E": "Corsair", "02FE": "Elpida", "830B": "Nanya", "8394": "Mushkin",
    "8316": "Netlist", "8325": "Kingmax", "04B0": "OCZ", "0443": "Ramaxel", "04CB": "ADATA",
    "04CD": "G.Skill", "04EF": "TeamGroup", "8502": "Patriot", "859B": "Crucial", "8551": "Qimonda",
    "8634": "Super Talent", "86D3": "Silicon Power", "865E": "Lexar", "866D": "V-Color", "079E": "Teikon",
    "0746": "Gloway", "07EA": "Transcend", "0813": "Gloway", "08F1": "Asgard", "8A76": "Lexar",
    "0B92": "Kingbank",
}
# Prefijos de referencia propios de cada marca, para cuando la placa no da el fabricante.
RAM_PARTS = [
    (r"F[2-5]-", "G.Skill"), (r"CM[A-Z]", "Corsair"), (r"(KHX|KF\d|KVR|KCP)", "Kingston"),
    (r"(CT\d|BL[SEMT]?\d)", "Crucial"), (r"M(378|471|391|393|386|425|474)[A-Z]", "Samsung"),
    (r"HM[ACT]", "SK hynix"), (r"MTA?\d", "Micron"), (r"(AX[45]U|AD[45]U)", "ADATA"),
    (r"(TF\d|TED\d|TLZ|TDZ)", "TeamGroup"), (r"(PV[ESR]?\d|PSD)", "Patriot"),
]
_RAM_JUNK = {"", "unknown", "undefined", "not specified", "none", "n/a", "na", "manufacturer",
             "to be filled by o.e.m.", "default string", "no dimm", "other"}


def ram_vendor(manufacturer, part):
    """Fabricante de un módulo: el que da la placa, su código JEDEC o, si no hay, el de la referencia."""
    m = (manufacturer or "").strip()
    low = m.lower()
    code = re.sub(r"^0x", "", m.replace(" ", ""), flags=re.I).upper()
    bank = re.match(r"bank\s*(\d+)\s*,\s*hex\s*0x([0-9a-f]{2})", low)
    if bank:                                     # «Bank 5, Hex 0xCD»
        b, c = int(bank.group(1)) - 1, int(bank.group(2), 16) & 0x7F
        par = lambda x: x if bin(x).count("1") % 2 else x | 0x80
        code = f"{par(b):02X}{par(c):02X}"
    hexa = re.fullmatch(r"[0-9A-F]{4,}", code) is not None
    if hexa:
        for k in (code[:4], code[2:4] + code[:2]):
            if k in JEDEC_RAM:
                return JEDEC_RAM[k]
    elif low not in _RAM_JUNK and not low.startswith("manufacturer"):
        return m
    p = (part or "").strip().upper()
    for rx, name in RAM_PARTS:
        if re.match(rx, p):
            return _("{marca} (según la referencia)").format(marca=name)
    if hexa and code.strip("0"):
        return _("Código JEDEC {codigo}").format(codigo=code[:4])
    return _("La placa no lo indica")


def sec_memory(ctx):
    m = meminfo()
    total, avail = m.get("MemTotal", 0), m.get("MemAvailable", 0)
    used = total - avail
    st, sf = m.get("SwapTotal", 0), m.get("SwapFree", 0)
    items = [("RAM", used / total if total else 0,
              _("{n} de {n2} ({n3:.0f} %)").format(n=human(used), n2=human(total), n3=pct(used, total)))]
    if st:
        items.append(("Swap", (st - sf) / st, _("{n} de {n2} ({n3:.0f} %)").format(n=human(st - sf), n2=human(st), n3=pct(st - sf, st))))

    swaps = [l.split() for l in read("/proc/swaps").splitlines()[1:]]
    detalle = kv("Detalle", [
        ("Total instalada (visible)", human(total)),
        ("Disponible", human(avail)),
        ("Caché y búferes", human(m.get("Cached", 0) + m.get("Buffers", 0))),
        ("Memoria compartida", human(m.get("Shmem", 0))),
        ("Memoria de intercambio (swap)", ", ".join(f"{s[0]} ({human(int(s[2]) * 1024) if s[2].isdigit() else s[1]})"
                                                    for s in swaps if len(s) > 2) or "No hay"),
        ("Tendencia a usar swap (swappiness)", read("/proc/sys/vm/swappiness")),
    ])

    zram = []
    for z in sorted(glob.glob("/sys/block/zram*"), key=natural):
        size = read_int(z + "/disksize")
        if not size:
            continue
        st_ = read(z + "/mm_stat").split()
        algo = re.search(r"\[([\w-]+)\]", read(z + "/comp_algorithm"))
        text = human(size) + (f", {algo.group(1)}" if algo else "")
        if len(st_) >= 3 and st_[0].isdigit() and int(st_[0]):
            text += ", " + _("{a} guardados en {b}").format(a=human(int(st_[0])), b=human(int(st_[2])))
        zram.append(f"{os.path.basename(z)}: {text}")
    zswap = {"Y": "Activada", "N": "Desactivada"}.get(read("/sys/module/zswap/parameters/enabled"), "")
    compresion = kv("Memoria comprimida", [("zram", "; ".join(zram)), ("zswap", zswap)], adv=True,
                    help="Linux puede comprimir en la propia RAM lo que menos se usa, en lugar de llevarlo al "
                         "disco. Es más rápido que una swap normal y alivia a los equipos con poca memoria.")

    props, mods = dmi_memory()
    rows, populated = [], 0
    for d in mods:
        present = d.get("PRESENT", "1") != "0" and d.get("SIZE", "0") not in ("", "0")
        if present:
            populated += 1
        speed = d.get("CONFIGURED_SPEED_MTS") or d.get("SPEED_MTS", "")
        rows.append((d.get("LOCATOR", ""),
                     human(d.get("SIZE")) if present else "Vacía",
                     d.get("TYPE", "") if present else "",
                     f"{speed} MT/s" if present and speed else "",
                     d.get("FORM_FACTOR", "") if present else "",
                     ram_vendor(d.get("MANUFACTURER", ""), d.get("PART_NUMBER", "")) if present else "",
                     d.get("PART_NUMBER", "").strip() if present else ""))
    blocks = [bars("Uso", items), detalle, compresion,
              table("Módulos instalados", ["Ranura", "Tamaño", "Tipo", "Velocidad", "Formato",
                                           "Fabricante", "Referencia"], rows)]
    if mods:
        maxcap = props.get("MEMORY_ARRAY_MAX_CAPACITY", "")
        blocks.append(kv("Ampliación", [
            ("Ranuras ocupadas", _("{populated} de {n}").format(populated=populated, n=len(mods))),
            ("Máximo que admite la placa", human(maxcap) if maxcap.isdigit() else ""),
        ]))
        if len(mods) >= 2 and populated == 1:
            ctx.flag("info", "Memoria", "Hay un solo módulo de memoria y queda una ranura libre: la "
                     "memoria trabaja en canal simple.",
                     "No es un fallo. Si algún día quieres más rendimiento o más memoria, un servicio "
                     "técnico puede añadir un módulo igual al que tienes.")
    else:
        blocks.append(note("No se han podido leer los módulos de RAM (ocurre en máquinas "
                           "virtuales y en algunos equipos con memoria soldada)."))

    ce = sum(read_int(f, 0) or 0 for f in glob.glob("/sys/devices/system/edac/mc/mc*/ce_count"))
    ue = sum(read_int(f, 0) or 0 for f in glob.glob("/sys/devices/system/edac/mc/mc*/ue_count"))
    if glob.glob("/sys/devices/system/edac/mc/mc*"):
        blocks.append(kv("Errores de memoria (EDAC)", [("Corregidos", ce), ("Sin corregir", ue)], adv=True,
                         help="Errores que el controlador de memoria ha detectado. Lo normal es 0."))
    if ue:
        ctx.flag("bad", "Memoria", _("El kernel ha registrado {ue} errores de memoria que no ha podido corregir. Es señal de un módulo de memoria defectuoso.").format(ue=ue),
                 "Haz ya una copia de seguridad de tus archivos y lleva el equipo a un servicio técnico o "
                 "al fabricante, sobre todo si está en garantía.", "backup")
    elif ce:
        ctx.flag("warn", "Memoria", _("El kernel ha corregido {ce} errores de memoria.").format(ce=ce),
                 "De momento no se pierde nada, pero puede ser el primer síntoma de un módulo que falla. "
                 "Haz copias de seguridad con regularidad y coméntaselo a un servicio técnico.", "backup")
    if total and avail / total < 0.10:
        ctx.flag("warn", "Memoria", _("Queda poca memoria libre ({n}).").format(n=human(avail)),
                 "Cierra programas o pestañas del navegador que no estés usando.", "sysmon")
    if not st and total and total < 8 * 1024 ** 3:
        ctx.flag("info", "Memoria", "No hay memoria de intercambio (swap) y el equipo tiene menos de 8 GiB de RAM.",
                 "Si algún programa se cierra solo por falta de memoria, pide en el foro de tu distribución "
                 "cómo crear un archivo de intercambio. Si no te pasa, no hace falta hacer nada.")
    sizes = [int(d["SIZE"]) for d in mods if d.get("SIZE", "").isdigit() and int(d["SIZE"]) > 0
             and d.get("PRESENT", "1") != "0"]
    kind = next((d.get("TYPE") for d in mods if d.get("TYPE") and d.get("TYPE") != "Unknown"), "")
    if sizes and len(set(sizes)) == 1:
        ctx.summary["ram"] = _("{n} visibles ({n2} × {n3}{n4})").format(n=human(total), n2=len(sizes), n3=human(sizes[0], 0), n4=' ' + kind if kind else '')
    else:
        ctx.summary["ram"] = human(total)
    ctx.data["ram_frac"] = items[0]
    return section("memoria", "Memoria", blocks)


# ───────────────────────── PCI, gráfica y pantallas ─────────────────────────

@once
def pci_devices():
    devs = []
    out = run(["lspci", "-D", "-vmm", "-k", "-nn"])
    if out:
        for blk in re.split(r"\n\s*\n", out):
            d = {"modules": []}
            for line in blk.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip()
                if k == "Module":
                    d["modules"].append(v)
                else:
                    d[k] = v
            if "Slot" in d:
                devs.append(d)
        return devs
    for p in sorted(glob.glob("/sys/bus/pci/devices/*")):   # sin lspci: solo identificadores
        d = {"Slot": os.path.basename(p), "modules": [],
             "Class": _("Clase [{n}]").format(n=read(p + '/class')[2:6]),
             "Vendor": _("Fabricante [{n}]").format(n=read(p + '/vendor')[2:]),
             "Device": _("Dispositivo [{n}]").format(n=read(p + '/device')[2:])}
        if os.path.exists(p + "/driver"):
            d["Driver"] = os.path.basename(os.path.realpath(p + "/driver"))
        devs.append(d)
    return devs


def split_id(s):
    m = re.match(r"^(.*?)\s*\[([0-9a-fA-F]{4})\]$", s or "")
    return (m.group(1), m.group(2)) if m else (s or "", "")


def pcie_link(sysp):
    """Enlace PCIe actual frente al máximo, legible sin root. '' si no es PCIe."""
    cs, cw = read(sysp + "/current_link_speed"), read(sysp + "/current_link_width")
    ms, mw = read(sysp + "/max_link_speed"), read(sysp + "/max_link_width")
    if not cs or "Unknown" in cs or not cw or cw == "0":
        return ""

    def gen(sp):
        m = re.match(r"([\d.]+)\s*GT/s", sp)
        g = {"2.5": 1, "5.0": 2, "5": 2, "8.0": 3, "8": 3, "16.0": 4, "16": 4, "32.0": 5, "32": 5, "64.0": 6, "64": 6}
        return f"PCIe {g[m.group(1)]}.0" if m and m.group(1) in g else sp
    txt = f"{gen(cs)} x{cw}"
    if ms and mw and (ms != cs or mw != cw):
        txt += f" (máximo {gen(ms)} x{mw}; en reposo es normal que baje)"
    return txt


def gpu_clock(sysp, card):
    """Frecuencia de la gráfica ahora y máxima (Intel i915/xe y AMD), sin root."""
    now = read_int(card + "/gt_act_freq_mhz") or read_int(card + "/gt_cur_freq_mhz")
    mx = read_int(card + "/gt_max_freq_mhz") or read_int(card + "/gt_RP0_freq_mhz")
    if now is None:
        now = read_int(sysp + "/tile0/gt0/freq0/act_freq")
        mx = read_int(sysp + "/tile0/gt0/freq0/max_freq")
    sclk = read(sysp + "/pp_dpm_sclk")
    if now is None and sclk:
        levels = re.findall(r"(\d+)Mhz(\s*\*)?", sclk, re.I)
        cur = [int(v) for v, star in levels if star.strip()]
        now = cur[0] if cur else None
        mx = max((int(v) for v, _s in levels), default=None)
    if now is None:
        return ""
    return f"{now} MHz" + (" (" + _("máxima {mx} MHz").format(mx=mx) + ")" if mx else "")


PNP = {"AAC": "AcerView", "ACI": "ASUS", "ACR": "Acer", "AOC": "AOC", "AUO": "AU Optronics", "AUS": "ASUS",
       "BNQ": "BenQ", "BOE": "BOE", "CMN": "Innolux", "CSO": "CSOT", "DEL": "Dell", "ENC": "EIZO", "GBT": "Gigabyte",
       "GSM": "LG", "HKC": "HKC", "HPN": "HP", "HSD": "HannStar", "HWP": "HP", "HWV": "Huawei", "IVM": "iiyama",
       "IVO": "InfoVision", "LEN": "Lenovo", "LGD": "LG Display", "MEI": "Panasonic", "MSI": "MSI", "NEC": "NEC",
       "PHL": "Philips", "SAM": "Samsung", "SDC": "Samsung Display", "SHP": "Sharp", "SNY": "Sony",
       "VSC": "ViewSonic", "XMI": "Xiaomi", "KTC": "KTC", "SKG": "Skyworth", "TCL": "TCL", "MED": "Medion"}


def parse_edid(data):
    """Datos del monitor a partir de su EDID (bytes o ruta del archivo)."""
    b = data
    if isinstance(data, str):
        try:
            with open(data, "rb") as f:
                b = f.read()
        except Exception:
            return {}
    if len(b) < 128 or b[:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        return {}
    m = (b[8] << 8) | b[9]
    code = "".join(chr(((m >> s) & 31) + 64) for s in (10, 5, 0))
    info = {"code": code, "mfg": PNP.get(code, code), "year": b[17] + 1990 if b[17] else "",
            "week": b[16] if 0 < b[16] < 54 else "", "w": b[21], "h": b[22],
            "digital": bool(b[20] & 0x80)}
    for off in (54, 72, 90, 108):
        d = b[off:off + 18]
        if d[0] == 0 and d[1] == 0:
            text = d[5:18].decode("ascii", "replace").split("\n")[0].strip()
            if d[3] == 0xFC:
                info["name"] = text
            elif d[3] == 0xFF and text:
                info["serial"] = text
            elif d[3] == 0xFD:
                info["vmax"] = d[6] + (255 if d[4] & 0x02 else 0)
        elif "res" not in info:
            clock = (d[0] | d[1] << 8) * 10000
            ha, hb = d[2] | ((d[4] & 0xF0) << 4), d[3] | ((d[4] & 0x0F) << 8)
            va, vb = d[5] | ((d[7] & 0xF0) << 4), d[6] | ((d[7] & 0x0F) << 8)
            info["res"] = f"{ha} × {va}"
            if clock and (ha + hb) and (va + vb):
                info["hz"] = round(clock / ((ha + hb) * (va + vb)))
    return info


@once
def xrandr_verbose():
    """Salida → (EDID, modo actual, principal). Con el driver de NVIDIA el EDID solo se ve aquí."""
    out = {}
    if not os.environ.get("DISPLAY"):
        return out
    cur, hexs, grab, in_mode = None, [], False, False
    for line in run(["xrandr", "--current", "--verbose"], timeout=6).splitlines() + ["X"]:
        m = re.match(r"^(\S+) (connected|disconnected)( primary)?(?: (\d+)x(\d+)\+)?", line)
        if m or not line.startswith((" ", "\t")):
            if cur and hexs:
                out[cur]["edid"] = bytes.fromhex("".join(hexs))
            hexs, grab = [], False
            cur = None
            if m and m.group(2) == "connected":
                cur = m.group(1)
                out[cur] = {"primary": bool(m.group(3)),
                            "mode": f"{m.group(4)} × {m.group(5)}" if m.group(4) else "", "hz": ""}
            continue
        t = line.strip()
        if t == "EDID:":
            grab = True
        elif grab and re.fullmatch(r"[0-9a-f]{32}", t):
            hexs.append(t)
        else:
            grab = False
            if cur and "*current" in t:
                in_mode = True
                hz = re.search(r"(?<![\d.M])([\d.]+)Hz", t)          # formato corto: «1920x1080 60.00*+»
                if hz and not out[cur]["hz"]:
                    out[cur]["hz"] = f"{float(hz.group(1)):.0f} Hz"
            elif cur and in_mode and t.startswith("v:"):           # formato --verbose: «v: ... clock 60.00Hz»
                hz = re.search(r"clock\s+([\d.]+)Hz", t)
                if hz and not out[cur]["hz"]:
                    out[cur]["hz"] = f"{float(hz.group(1)):.0f} Hz"
                in_mode = False
            elif re.match(r"\d+x\d+", t):
                in_mode = False
    return out


def is_wayland():
    return os.environ.get("XDG_SESSION_TYPE") == "wayland" or \
        (bool(os.environ.get("WAYLAND_DISPLAY")) and os.environ.get("XDG_SESSION_TYPE") != "x11")


def _mode(w, h, hz, primary=False, scale=None):
    d = {"mode": f"{int(w)} × {int(h)}" if w and h else "", "hz": f"{float(hz):.0f} Hz" if hz else "",
         "primary": bool(primary)}
    if scale and abs(float(scale) - 1) > 0.01:
        d["scale"] = num(float(scale), 2).rstrip("0").rstrip(",")
    return d


def parse_wlr_randr(text):
    """Salida de «wlr-randr --json» (Sway, Hyprland, labwc y demás compositores wlroots)."""
    out = {}
    try:
        for o in json.loads(text):
            m = next((m for m in o.get("modes", []) if m.get("current")), None)
            if o.get("enabled") and m:
                out[o["name"]] = _mode(m.get("width"), m.get("height"), m.get("refresh"), scale=o.get("scale"))
    except Exception:
        return {}
    return out


def parse_kscreen(text):
    """Salida de «kscreen-doctor -j» (KDE Plasma)."""
    out = {}
    try:
        for o in json.loads(text).get("outputs", []):
            m = next((m for m in o.get("modes", []) if str(m.get("id")) == str(o.get("currentModeId"))), None)
            if o.get("enabled") and o.get("connected", True) and m:
                size = m.get("size", {})
                out[o["name"]] = _mode(size.get("width"), size.get("height"), m.get("refreshRate"),
                                       o.get("priority") == 1 or o.get("primary"), o.get("scale"))
    except Exception:
        return {}
    return out


def parse_display_config(state):
    """Respuesta de GetCurrentState de Mutter (GNOME) o Muffin (Cinnamon), ya convertida a Python.
    Del monitor solo se usa el conector: marca, modelo y número de serie se descartan."""
    out = {}
    try:
        mons, logical = state[1], state[2]
        info = {}
        for lm in logical:
            for spec in lm[5]:
                info[spec[0]] = (lm[4], lm[2])              # principal, escala
        for spec, modes, _props in mons:
            for m in modes:
                if m[6].get("is-current"):
                    primary, scale = info.get(spec[0], (False, None))
                    out[spec[0]] = _mode(m[1], m[2], m[3], primary, scale)
    except Exception:
        return {}
    return out


def display_config_state():
    """Pregunta al compositor por D-Bus, dentro de la sesión del usuario. No sale del equipo."""
    try:
        from gi.repository import Gio
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        for name in ("org.gnome.Mutter.DisplayConfig", "org.cinnamon.Muffin.DisplayConfig"):
            try:
                r = bus.call_sync(name, "/" + name.replace(".", "/"), name, "GetCurrentState", None, None,
                                  Gio.DBusCallFlags.NO_AUTO_START, 3000, None)
                return r.unpack()
            except Exception:
                continue
    except Exception:
        pass
    return None


@once
def compositor_modes():
    """Modo en uso de cada salida en Wayland, donde xrandr solo ve la capa de compatibilidad
    (XWayland) y da nombres y modos que no son los reales."""
    if not is_wayland():
        return {}
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    out = {}
    if "kde" in desktop and have("kscreen-doctor"):
        out = parse_kscreen(run(["kscreen-doctor", "-j"], timeout=5))
    if not out and any(x in desktop for x in ("gnome", "cinnamon", "unity", "budgie", "pantheon")):
        out = parse_display_config(display_config_state())
    if not out and have("wlr-randr"):
        out = parse_wlr_randr(run(["wlr-randr", "--json"], timeout=4))
    return out


def current_modes():
    """Salida → modo en uso. En Wayland responde el compositor; en X11, xrandr."""
    return compositor_modes() or ({} if is_wayland() else xrandr_verbose())


@once
def monitors():
    """Monitores conectados: primero el EDID del kernel; si no hay (driver de NVIDIA), el de xrandr."""
    mons, seen = [], set()
    for c in sorted(glob.glob("/sys/class/drm/card*-*"), key=natural):
        if read(c + "/status") != "connected":
            continue
        e = parse_edid(c + "/edid")
        if e:
            e["port"] = os.path.basename(c).split("-", 1)[1]
            mons.append(e)
            seen.add((e.get("code"), e.get("name"), e.get("serial")))
    for out, x in xrandr_verbose().items():
        e = parse_edid(x.get("edid", b""))
        key = (e.get("code"), e.get("name"), e.get("serial"))
        if e and key not in seen:
            e["port"] = out
            mons.append(e)
            seen.add(key)
    xr = current_modes()
    for e in mons:
        x = xr.get(e["port"]) or next((v for k, v in xr.items() if k.replace("-A-", "-") == e["port"].replace("-A-", "-")), {})
        e["mode"], e["cur_hz"], e["primary"] = x.get("mode", ""), x.get("hz", ""), x.get("primary", False)
        if x.get("scale"):
            e["cur_hz"] = " ".join(t for t in (e["cur_hz"], _("(escala {n})").format(n=x["scale"])) if t)
    return mons


def mon_name(e):
    mfg, name = e.get("mfg", ""), e.get("name", "")
    if name.lower().startswith(mfg.lower()):
        mfg = ""
    return " ".join(x for x in (mfg, name) if x) or e.get("code", "")


def monitor_rows(mons):
    rows = []
    for e in mons:
        size = ""
        if e.get("w") and e.get("h"):
            size = f"{num((e['w'] ** 2 + e['h'] ** 2) ** 0.5 / 2.54)}\" ({e['w']} × {e['h']} cm)"
        rows.append((mon_name(e),
                     size, e.get("res", ""), f"{e['hz']} Hz" if e.get("hz") else "",
                     " @ ".join(x for x in (e.get("mode"), e.get("cur_hz")) if x),
                     e["port"], str(e.get("year", "")), Sens(e.get("serial", ""))))
    return rows


MON_HEADERS = ["Monitor", "Tamaño", "Resolución nativa", "Refresco nativo", "Modo en uso", "Conector",
               "Fabricado en", "Número de serie"]


@once
def glx_info():
    return keyvals(run(["glxinfo", "-B"], timeout=6), ":") if os.environ.get("DISPLAY") else {}


@once
def va_info():
    return run(["vainfo"], timeout=5) if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") else ""


def sec_gpu(ctx):
    blocks, names = [], []
    for d in pci_devices():
        cname, cid = split_id(d.get("Class", ""))
        if not cid.startswith("03"):
            continue
        vname, vid = split_id(d.get("Vendor", ""))
        dname, did = split_id(d.get("Device", ""))
        sysp = "/sys/bus/pci/devices/" + d["Slot"]
        vram = read_int(sysp + "/mem_info_vram_total")
        names.append(f"{vname} {dname}".strip())
        cards = [c for c in glob.glob("/sys/class/drm/card[0-9]*") if "-" not in os.path.basename(c)
                 and os.path.realpath(c + "/device") == os.path.realpath(sysp)]
        blocks.append(kv(_("Tarjeta gráfica: {n}").format(n=dname or cname), [
            ("Fabricante", vname), ("Modelo", dname), ("Tipo", cname),
            ("Identificador PCI", f"{vid}:{did}" if vid else ""),
            ("Ensamblador", split_id(d.get("SVendor", ""))[0]),
            ("Revisión", d.get("Rev", "")),
            ("Driver en uso", d.get("Driver", "Ninguno")),
            ("Módulos disponibles", ", ".join(d["modules"])),
            ("Memoria de vídeo", human(vram) if vram else ""),
            ("Frecuencia", gpu_clock(sysp, cards[0]) if cards else ""),
            ("Enlace PCIe", pcie_link(sysp)),
            ("Ranura", d["Slot"]),
        ]))
        if not d.get("Driver"):
            ctx.flag("warn", "Gráfica", _("La gráfica {dname} no tiene ningún driver cargado.").format(dname=dname),
                     "Abre el Gestor de controladores: si ofrece un driver recomendado para tu gráfica, "
                     "instálalo y reinicia. Si no ofrece nada, pregunta en el foro de tu distribución.", "drivers")

    nv = run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,temperature.gpu",
              "--format=csv,noheader"])
    if nv:
        rows = [[c.strip() for c in l.split(",")] for l in nv.splitlines()]
        blocks.append(table("NVIDIA (driver privativo)", ["GPU", "Versión del driver", "Memoria", "Temperatura °C"], rows))

    g = glx_info()
    session = os.environ.get("XDG_SESSION_TYPE", "")
    blocks.append(kv("Aceleración 3D", [
        ("Renderizador OpenGL", g.get("OpenGL renderer string", "")),
        ("Versión de OpenGL", g.get("OpenGL version string", "")),
        ("Renderizado directo", g.get("direct rendering", "")),
        ("Memoria de vídeo dedicada", g.get("Dedicated video memory", "") or g.get("Video memory", "")),
        ("Servidor gráfico", {"x11": "X11 (Xorg)", "wayland": "Wayland"}.get(session, session)),
    ]))
    if "llvmpipe" in g.get("OpenGL renderer string", "").lower() and virt_env() in ("", "none"):
        ctx.flag("warn", "Gráfica", "La gráfica no está acelerando el 3D: lo está dibujando el procesador "
                 "(llvmpipe), así que vídeos, juegos y efectos irán lentos.",
                 "Abre el Gestor de controladores e instala el driver recomendado para tu gráfica. "
                 "Después, reinicia.", "drivers")

    va_all = re.findall(r"VAProfile(\w+)\s*:\s*VAEntrypointVLD", va_info())
    va = {k for k in ("H264", "HEVC", "VP9", "AV1", "MPEG2", "VP8", "VC1") if any(n.startswith(k) for n in va_all)}
    names_va = [("H264", "H.264"), ("HEVC", "H.265 (HEVC)"), ("VP9", "VP9"), ("AV1", "AV1"),
                ("MPEG2", "MPEG-2"), ("VP8", "VP8"), ("VC1", "VC-1")]
    vk = keyvals(run(["vulkaninfo", "--summary"], timeout=6), "=") \
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") else {}
    blocks.append(kv("Vídeo y Vulkan", adv=True, help="Formatos de vídeo que la gráfica reproduce por sí "
                     "sola, sin cargar al procesador, y versión de Vulkan, que usan los juegos.", rows=[
        ("Decodifica por hardware", ", ".join(n for k, n in names_va if k in va)
         or ("Ningún formato" if va_info() else "")),
        ("No decodifica por hardware", ", ".join(n for k, n in names_va[:4] if k not in va) if va else ""),
        ("Dispositivo Vulkan", vk.get("deviceName", "")),
        ("Versión de Vulkan", vk.get("apiVersion", "")),
        ("Driver Vulkan", " ".join(x for x in (vk.get("driverName"), vk.get("driverInfo")) if x)),
    ]))

    mons = monitors()
    blocks.append(table("Pantallas conectadas", MON_HEADERS, monitor_rows(mons)))
    actual = [(e["port"], e.get("mode", ""), e.get("cur_hz", "")) for e in mons if e.get("mode")]
    if not actual:                 # sin EDID legible: al menos el modo en uso
        for out, x in current_modes().items():
            if x.get("mode"):
                actual.append((out, x["mode"], x.get("hz", "")))
        blocks.append(table("Modo en uso", ["Salida", "Resolución", "Refresco"], actual))
    if is_wayland() and not actual:
        blocks.append(note("En Wayland, el modo en uso lo da el escritorio: MintMachine lo lee en GNOME, "
                           "Cinnamon y KDE Plasma, y en Sway, Hyprland y similares si está instalada la "
                           "utilidad wlr-randr. Los datos de cada monitor sí están completos."))

    ctx.summary["gpu"] = "; ".join(names) or g.get("OpenGL renderer string", "")
    ctx.summary["pantalla"] = "; ".join(
        " ".join(x for x in (mon_name(e), e.get("mode"),
                             ("@ " + e["cur_hz"]) if e.get("cur_hz") else "") if x) for e in mons) \
        or "; ".join(f"{a[1]} @ {a[2]}" if a[2] else a[1] for a in actual)
    if not names and not g:
        blocks.append(note("No se ha detectado ninguna tarjeta gráfica por PCI."))
    return section("grafica", "Gráfica y pantallas", blocks)


def sec_pci(ctx):
    rows = []
    for d in pci_devices():
        vname, vid = split_id(d.get("Vendor", ""))
        dname, did = split_id(d.get("Device", ""))
        rows.append((d["Slot"], split_id(d.get("Class", ""))[0], vname, dname,
                     f"{vid}:{did}" if vid else "", d.get("Driver", "")))
    blocks = [table("Dispositivos PCI y el driver que usa cada uno",
                    ["Ranura", "Clase", "Fabricante", "Dispositivo", "ID", "Driver"], rows)]
    if not rows:
        blocks.append(note("No hay bus PCI visible en este sistema."))
    return section("pci", "Dispositivos PCI", blocks)


# ───────────────────────────── almacenamiento ─────────────────────────────

def fs_usage(mount):
    """total, usado, libre para el usuario, solo lectura. El porcentaje se calcula como df:
    usado / (usado + libre), porque ext4 reserva un 5 % para root que el usuario no puede usar."""
    try:
        s = os.statvfs(mount)
        total = s.f_blocks * s.f_frsize
        free = s.f_bavail * s.f_frsize
        used = (s.f_blocks - s.f_bfree) * s.f_frsize
        return total, used, free, bool(s.f_flag & os.ST_RDONLY)
    except Exception:
        return 0, 0, 0, False


def fs_frac(used, free):
    return used / (used + free) if used + free else 0.0


def usage_text(used, total, free):
    return _("{n} usados de {n2}; quedan {n3} libres").format(n=human(used), n2=human(total), n3=human(free))


@once
def udisks_drives():
    """Salud SMART que el servicio UDisks ya tiene leída: no hace falta root."""
    drives, obj, iface = [], None, None
    for line in run(["udisksctl", "dump"], timeout=8).splitlines():
        if line.startswith("/org/freedesktop/UDisks2/"):
            obj = {"_path": line.strip().rstrip(":")} if "/drives/" in line else None
            if obj is not None:
                drives.append(obj)
        elif obj is not None and line.startswith("  org.freedesktop."):
            iface = line.strip().rstrip(":").split("UDisks2.")[-1]
        elif obj is not None and line.startswith("    ") and ":" in line and not line.startswith("     "):
            k, v = line.strip().split(":", 1)
            obj[f"{iface}.{k}"] = v.strip()
    return drives


def gdbus_attrs(path, method):
    """Atributos SMART que UDisks ya tiene leídos (SmartGetAttributes), sin root ni preguntas.
    Devuelve el texto de la respuesta o '' si UDisks no lo permite o no existe el método."""
    return run(["gdbus", "call", "--system", "--dest", "org.freedesktop.UDisks2", "--object-path", path,
                "--method", method, "{}"], timeout=6)


# Atributos SATA que los fabricantes usan para la vida restante de un SSD (valor normalizado, 100 = nuevo)
SSD_LIFE_ATTRS = (231, 233, 202, 177, 169, 173)


def ssd_wear_sata(path):
    out = gdbus_attrs(path, "org.freedesktop.UDisks2.Drive.Ata.SmartGetAttributes")
    vals = {}
    # Respuesta: ([(byte 0x05, 'reallocated-sector-count', uint16 51, 100, 100, 10, ...), (0xb1, ...)],)
    for m in re.finditer(r"\((?:byte )?(0x[0-9a-fA-F]+|\d+), '[^']*', (?:uint16 )?\d+, (-?\d+),", out):
        vals[int(m.group(1), 0)] = int(m.group(2))
    for i in SSD_LIFE_ATTRS:
        if i in vals and 0 < vals[i] <= 100:
            return 100 - vals[i]
    return None


def nvme_health(path):
    """percent_used, avail_spare, spare_thresh, media_errors (UDisks 2.10 o posterior)."""
    out = gdbus_attrs(path, "org.freedesktop.UDisks2.NVMe.Controller.SmartGetAttributes")
    res = {}
    for k, v in re.findall(r"'(\w+)': <(?:byte |uint16 |uint64 |int64 |uint32 )?([^>]+)>", out):
        try:
            res[k] = int(v, 16) if v.startswith("0x") else int(float(v))
        except ValueError:
            pass
    return res


def wear_text(used):
    if used is None:
        return ""
    return _("{used} % usada (queda un {n} % estimado)").format(used=used, n=max(0, 100 - used))


def disk_key(model, serial):
    """Identificador estable de un disco para el historial, sin guardar su número de serie."""
    import hashlib
    return hashlib.sha1(f"{model}|{serial}".encode()).hexdigest()[:16]


def _delta(a, b):
    return b - a if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None


def disk_history(ctx, raw, record=True):
    """Guarda (una vez al día) el estado SMART de cada disco y lo compara con la medición más antigua."""
    d = history_load()
    hist = d.setdefault("discos", {})
    today = time.strftime("%Y-%m-%d")
    rows = []
    for m in raw:
        h = hist.setdefault(m["id"], [])
        now = {k: m.get(k) for k in ("wear", "bad", "hours", "errors")}
        if record and (not h or h[-1].get("t", "")[:10] != today):
            h.append(dict(now, t=time.strftime("%Y-%m-%d %H:%M")))
            del h[:-400]
        first = h[0] if h else None
        if not first or first.get("t", "")[:10] == today:
            rows.append((m["model"], _("Desde hoy"), wear_text(m.get("wear")) or "", "", "",
                         _("Primera medición: la evolución se verá en los próximos días.")))
            continue
        since = first["t"][:10]
        dw, db, de = _delta(first.get("wear"), now["wear"]), _delta(first.get("bad"), now["bad"]), \
            _delta(first.get("errors"), now["errors"])
        try:
            days = max(1, (datetime.date.today() - datetime.date.fromisoformat(since)).days)
        except ValueError:
            days = 0
        estimate = ""
        if dw and dw > 0 and days >= 30 and now["wear"] is not None and now["wear"] < 100:
            years = (100 - now["wear"]) / (dw / days * 365.25)
            estimate = _("A este ritmo, unos {n} años hasta el 100 % estimado").format(n=num(years, 0) if years >= 2 else num(years))
        rows.append((m["model"], when_date(since),
                     _("{a} % → {b} %").format(a=first.get("wear"), b=now["wear"]) if dw is not None else "",
                     (_("+{n} nuevos").format(n=db) if db and db > 0 else _("Sin cambios")) if db is not None else
                     ((_("+{n} errores nuevos").format(n=de) if de and de > 0 else _("Sin cambios")) if de is not None else ""),
                     _("+{n} h").format(n=_delta(first.get("hours"), now["hours"])) if _delta(first.get("hours"), now["hours"]) else "",
                     estimate))
        if db and db > 0:
            ctx.flag("warn", "Almacenamiento", _("En el disco {model} han aparecido {n} sectores dañados nuevos desde el {fecha}.").format(
                model=m["model"], n=db, fecha=when_date(since)),
                "Que el número crezca indica que el disco se está deteriorando. Haz ya una copia de seguridad de "
                "tus archivos importantes en otro disco o en la nube y consulta con un servicio técnico o con el "
                "fabricante (si está en garantía).", "backup")
        if de and de > 0:
            ctx.flag("warn", "Almacenamiento", _("El SSD {model} ha registrado {n} errores de datos nuevos desde el {fecha}.").format(
                model=m["model"], n=de, fecha=when_date(since)),
                "Haz ya una copia de seguridad de tus archivos importantes en otro disco o en la nube y consulta "
                "con un servicio técnico o con el fabricante (si está en garantía).", "backup")
    if record and raw:
        history_save(d)
    return rows


def when_date(iso):
    """«2026-11-14» → fecha corta en el formato del idioma."""
    try:
        dt = datetime.date.fromisoformat(iso[:10])
    except ValueError:
        return iso
    return dt.strftime("%m/%d/%Y") if _LANG[0] == "en" else (dt.strftime("%Y/%m/%d") if _LANG[0] in ("ja", "zh")
                                                              else dt.strftime("%d/%m/%Y"))


def smart_rows(ctx):
    rows = []
    backup = ("Haz ya una copia de seguridad de tus archivos importantes en otro disco o en la nube. "
              "Después, consulta con un servicio técnico o con el fabricante (si está en garantía) para "
              "sustituir la unidad.")
    for d in udisks_drives():
        model = d.get("Drive.Model", "") or d.get("Drive.Id", "")
        if not model:
            continue
        ata, nvme = d.get("Drive.Ata.SmartSupported"), d.get("NVMe.Controller.SmartUpdated")
        rotating = d.get("Drive.RotationRate", "0") not in ("0", "-1", "")
        if ata == "true" and d.get("Drive.Ata.SmartEnabled") == "true" and d.get("Drive.Ata.SmartUpdated", "0") != "0":
            failing = d.get("Drive.Ata.SmartFailing") == "true"
            bad = int(d.get("Drive.Ata.SmartNumBadSectors", "0") or 0)
            temp = float(d.get("Drive.Ata.SmartTemperature", "0") or 0)
            hours = int(d.get("Drive.Ata.SmartPowerOnSeconds", "0") or 0) // 3600
            wear = None if rotating else ssd_wear_sata(d["_path"])
            ctx.data.setdefault("smart_raw", []).append(dict(
                id=disk_key(model, d.get("Drive.Serial", "")), model=model, wear=wear, bad=max(bad, 0),
                hours=hours or None, errors=None))
            state = "FALLO INMINENTE" if failing else ("Con sectores dañados" if bad > 0 else "Correcto")
            rows.append((model, state, wear_text(wear), f"{temp - 273.15:.0f} °C" if temp > 0 else "",
                         _("{hours} h ({n} años)").format(hours=hours, n=num(hours / 8766)) if hours else "",
                         bad if bad >= 0 else "", d.get("Drive.Ata.SmartSelftestStatus", "")))
            if failing:
                ctx.flag("bad", "Almacenamiento", _("El disco {model} avisa de que va a fallar pronto (SMART).").format(model=model),
                         backup, "backup")
            elif bad > 0:
                ctx.flag("warn", "Almacenamiento", _("El disco {model} tiene {bad} sectores dañados.").format(model=model, bad=bad),
                         _("Algunos sectores dañados no impiden usar el disco, pero si el número crece, el disco "
                           "se está deteriorando.") + " " + _(backup), "backup")
            if wear is not None and wear >= 90:
                ctx.flag("warn", "Almacenamiento", _("El SSD {model} ha consumido el {wear} % de su vida útil estimada.").format(model=model, wear=wear),
                         _("Aún puede funcionar bastante tiempo, pero conviene planificar su sustitución.") + " " + _(backup),
                         "backup")
        elif nvme and nvme != "0":
            warn = d.get("NVMe.Controller.SmartCriticalWarning", "").strip("[] ")
            temp = float(d.get("NVMe.Controller.SmartTemperature", "0") or 0)
            hours = int(d.get("NVMe.Controller.SmartPowerOnHours", "0") or 0)
            h = nvme_health(d["_path"])
            used = h.get("percent_used")
            ctx.data.setdefault("smart_raw", []).append(dict(
                id=disk_key(model, d.get("Drive.Serial", "")), model=model, wear=used, bad=None,
                hours=hours or None, errors=h.get("media_errors")))
            rows.append((model, _("AVISO: {warn}").format(warn=warn) if warn else "Correcto", wear_text(used),
                         f"{temp - 273.15:.0f} °C" if temp > 0 else "",
                         _("{hours} h ({n} años)").format(hours=hours, n=num(hours / 8766)) if hours else "",
                         h.get("media_errors", ""), d.get("NVMe.Controller.SmartSelftestStatus", "")))
            spare, thresh = h.get("avail_spare"), h.get("spare_thresh")
            if warn or (spare is not None and thresh and spare < thresh):
                ctx.flag("bad", "Almacenamiento", (_("El SSD {model} avisa de un problema de salud ({warn}).").format(
                    model=model, warn=warn) if warn else _("El SSD {model} avisa de un problema de salud (le quedan "
                                                           "pocos bloques de reserva).").format(model=model)),
                         backup, "backup")
            elif used is not None and used >= 90:
                ctx.flag("warn", "Almacenamiento", _("El SSD {model} ha consumido el {used} % de su vida útil estimada.").format(model=model, used=used),
                         _("Llegar al 100 % no significa que falle ese día: es la estimación del fabricante. "
                           "Aun así, conviene planificar su sustitución.") + " " + _(backup), "backup")
            elif h.get("media_errors"):
                ctx.flag("warn", "Almacenamiento", _("El SSD {model} ha registrado {media_errors} errores de datos.").format(model=model, media_errors=h['media_errors']), backup, "backup")
        elif ata is not None or "NVMe.Controller.State" in d:
            rows.append((model, "Sin datos SMART", "", "", "", "", ""))
    return rows


READONLY_FS = ("squashfs", "iso9660", "udf", "erofs", "cramfs")


def sec_storage(ctx):
    cols = "NAME,MODEL,SERIAL,SIZE,TYPE,TRAN,ROTA,FSTYPE,MOUNTPOINT,REV,RM,PKNAME"
    try:
        tree = json.loads(run(["lsblk", "-J", "-b", "-o", cols]) or "{}").get("blockdevices", [])
    except Exception:
        tree = []
    truthy = (True, "1", 1)
    disks, parts, usage, encrypted = [], [], [], False
    root_rota = None

    def walk(node, disk):
        nonlocal encrypted, root_rota
        for ch in node.get("children") or []:
            fstype, mnt = ch.get("fstype") or "", ch.get("mountpoint") or ""
            if ch.get("type") == "crypt" or fstype == "crypto_LUKS":
                encrypted = True
            use = ""
            if mnt.startswith("/"):
                total, used, free, ro = fs_usage(mnt)
                if total:
                    use = f"{fs_frac(used, free) * 100:.0f} %"
                    # las imágenes de solo lectura (squashfs, ISO) siempre están al 100 %
                    if not ro and fstype not in READONLY_FS:
                        usage.append((mnt, fs_frac(used, free), usage_text(used, total, free), free))
                if mnt == "/":
                    root_rota = disk.get("rota") in truthy
            parts.append(("/dev/" + ch.get("name", ""), ch.get("type", ""), fstype,
                          human(ch.get("size")), mnt, use))
            walk(ch, disk)

    for d in tree:
        name = d.get("name", "")
        if d.get("type") != "disk" or name.startswith(("zram", "loop", "ram")):
            continue
        tran = d.get("tran") or ""
        if tran == "virtio" or name.startswith(("vd", "xvd")):
            kind = _("Disco virtual")
        elif tran == "nvme" or name.startswith("nvme"):
            kind = _("SSD NVMe")
        elif d.get("rota") in truthy:
            kind = _("Disco duro (HDD)")
        else:
            kind = "SSD" if tran != "usb" else _("Memoria flash")
        if tran == "usb" or d.get("rm") in truthy:
            kind += ", " + _("extraíble")
        sched = re.search(r"\[(\w[\w-]*)\]", read(f"/sys/block/{name}/queue/scheduler"))
        link = ""
        if name.startswith("nvme"):
            link = pcie_link(os.path.realpath(f"/sys/block/{name}/device/device"))
        disks.append(("/dev/" + name, (d.get("model") or "").strip(), human(d.get("size")), kind,
                      tran.upper(), link, d.get("rev") or "", Sens(d.get("serial") or ""),
                      sched.group(1) if sched else ""))
        if d.get("mountpoint"):
            d = dict(d, children=[dict(d, children=None)] + (d.get("children") or []))
        walk(d, d)

    if not tree:   # sin lsblk: al menos los sistemas de archivos montados
        for line in read("/proc/mounts").splitlines():
            p = line.split()
            if len(p) > 2 and p[0].startswith("/dev/"):
                total, used, free, ro = fs_usage(p[1])
                if total and not ro and p[2] not in READONLY_FS:
                    usage.append((p[1], fs_frac(used, free), usage_text(used, total, free), free))
                    parts.append((p[0], "", p[2], human(total), p[1], f"{fs_frac(used, free) * 100:.0f} %"))

    seen = set()
    usage = [u for u in usage if not (u[0] in seen or seen.add(u[0]))]
    full_todo = ("Vacía la papelera y borra o mueve a otro disco lo que no necesites (descargas, vídeos, "
                 "copias antiguas). «Ver qué ocupa el disco» te enseña qué carpetas ocupan más. Si usas "
                 "Timeshift, revisa cuántas instantáneas guarda.")
    for mnt, frac, _txt, free in usage:
        if frac >= 0.97:
            ctx.flag("bad", "Almacenamiento", _("«{mnt}» está prácticamente lleno (quedan {n}). Con el disco lleno pueden fallar las actualizaciones y los programas.").format(mnt=mnt, n=human(free)), full_todo, "usage")
        elif frac >= 0.90:
            ctx.flag("warn", "Almacenamiento", _("«{mnt}» está al {n:.0f} % (quedan {n2}).").format(mnt=mnt, n=frac * 100, n2=human(free)),
                     full_todo, "usage")
    if root_rota and virt_env() in ("", "none"):
        ctx.flag("info", "Almacenamiento", "El sistema está instalado en un disco duro mecánico, que es mucho "
                 "más lento que un SSD.",
                 "No es un fallo. Si el equipo te parece lento, cambiar el disco por un SSD es la mejora que "
                 "más se nota; pídeselo a un servicio técnico, que también puede pasar tus datos.")
    ctx.data["encrypted"] = encrypted
    ctx.data["root_usage"] = next((u for u in usage if u[0] == "/"), None)
    ctx.summary["discos"] = "; ".join(f"{d[1] or d[0]} ({d[2]}, {d[3]})" for d in disks)

    trim = run(["systemctl", "is-enabled", "fstrim.timer"], timeout=3)
    ctx.data["trim"] = trim if trim in ("enabled", "disabled") and any("SSD" in str(d[3]) for d in disks) else ""
    smart = smart_rows(ctx)
    ok = [r for r in smart if r[1] == "Correcto"]
    if smart:
        ctx.summary["salud_discos"] = "Correcta" if len(ok) == len(smart) else \
            _("{n} de {n2} unidades con avisos (mira Almacenamiento)").format(n=len(smart) - len(ok), n2=len(smart))
    blocks = [
        bars("Espacio ocupado", [u[:3] for u in usage]),
        table("Salud de los discos (SMART)", ["Unidad", "Estado", "Vida útil", "Temperatura", "Horas encendido",
                                              "Sectores dañados / errores", "Última autoprueba"], smart,
              help="El propio disco vigila su estado (SMART). «Vida útil» es la estimación de desgaste del "
                   "fabricante para los SSD."),
        table("Evolución de la salud", ["Unidad", "Desde", "Vida útil usada", "Sectores dañados / errores",
                                        "Horas de uso añadidas", "Estimación"], disk_history(ctx, ctx.data.get("smart_raw", [])),
              help="MintMachine guarda en tu equipo una medición al día cada vez que lo abres y la compara con la "
                   "primera. Así se ve si un disco empieza a deteriorarse. No sale de tu equipo."),
        table("Unidades", ["Dispositivo", "Modelo", "Capacidad", "Tipo", "Interfaz", "Enlace", "Firmware",
                           "Número de serie", "Planificador E/S"], disks),
        kv("Mantenimiento", [("TRIM periódico de los SSD", {"enabled": "Activado (fstrim.timer)",
                                                           "disabled": "Desactivado"}.get(trim, ""))],
           help="El TRIM ayuda a que los SSD mantengan su velocidad. Linux Mint lo activa por defecto."),
        table("Particiones y volúmenes", ["Dispositivo", "Tipo", "Sistema de archivos", "Tamaño",
                                          "Montado en", "Uso"], parts, adv=True),
    ]
    if not disks:
        blocks.append(note("No se han detectado unidades físicas (¿falta la utilidad lsblk?)."))
    elif not smart:
        blocks.append(note("No hay datos de salud de los discos: hace falta el servicio UDisks (paquete "
                           "udisks2; para los NVMe, versión 2.10 o posterior). En máquinas virtuales no hay SMART."))
    return section("discos", "Almacenamiento", blocks)


# ───────────────────────────────── red ─────────────────────────────────

def sec_network(ctx):
    addrs = {}
    try:
        for it in json.loads(run(["ip", "-j", "addr"]) or "[]"):
            addrs[it.get("ifname")] = it.get("addr_info", [])
    except Exception:
        pass
    rows, wifi_blocks = [], []
    for p in sorted(glob.glob("/sys/class/net/*"), key=natural):
        name = os.path.basename(p)
        is_wifi = os.path.isdir(p + "/wireless") or os.path.exists(p + "/phy80211")
        if name == "lo":
            kind = "Bucle local"
        elif is_wifi:
            kind = "Wi-Fi"
        elif os.path.exists(p + "/device"):
            kind = "Ethernet"
        else:
            kind = "Virtual"
        speed = read_int(p + "/speed")
        driver = os.path.basename(os.path.realpath(p + "/device/driver")) if os.path.exists(p + "/device/driver") else ""
        v4 = ", ".join(f"{a['local']}/{a.get('prefixlen', '')}" for a in addrs.get(name, []) if a.get("family") == "inet")
        v6 = ", ".join(a["local"] for a in addrs.get(name, []) if a.get("family") == "inet6")
        state = {"up": "Conectada", "down": "Desconectada", "unknown": "",
                 "dormant": "En espera"}.get(read(p + "/operstate"), read(p + "/operstate"))
        if state == "Conectada" and kind in ("Ethernet", "Wi-Fi"):
            ctx.summary.setdefault("red", f"{kind} ({name})")
        rows.append((name, kind, state, f"{speed} Mb/s" if speed and speed > 0 else "", driver,
                     Sens(read(p + "/address")) if name != "lo" else "",
                     Sens(v4) if name != "lo" else v4, Sens(v6) if name != "lo" else v6))
        if is_wifi:
            link = keyvals(run(["iw", "dev", name, "link"]), ":")
            if link.get("SSID"):
                try:
                    mhz = int(float(link.get("freq", "")))
                    band = "2,4 GHz" if mhz < 3000 else "5 GHz" if mhz < 5925 else "6 GHz"
                    ctx.summary["wifi"] = _("banda de {band}").format(band=band)
                    freq = _("{mhz} MHz (banda de {band})").format(mhz=mhz, band=band)
                except ValueError:
                    freq = ""

                def rate(v):
                    p = v.split()
                    return f"{num(p[0])} Mb/s" if p and p[0].replace(".", "").isdigit() else ""
                sig = re.match(r"(-?\d+)", link.get("signal", ""))
                quality = ""
                if sig:
                    dbm = int(sig.group(1))
                    word = ("excelente" if dbm >= -55 else "buena" if dbm >= -67 else "justa" if dbm >= -75 else "débil")
                    quality = f"{dbm} dBm ({_(word)})"
                    if dbm < -75:
                        ctx.flag("info", "Red", _("La señal Wi-Fi es débil ({dbm} dBm): la conexión puede ir lenta o cortarse.").format(dbm=dbm),
                                 "Acércate al router o quita obstáculos entre ambos. Si tu router tiene dos redes "
                                 "(2,4 y 5 GHz), la de 2,4 GHz llega más lejos.")
                wifi_blocks.append(kv(_("Wi-Fi en {name}").format(name=name), [
                    ("Red (SSID)", Sens(link["SSID"])), ("Señal", quality),
                    ("Frecuencia", freq),
                    ("Velocidad de bajada", rate(link.get("rx bitrate", ""))),
                    ("Velocidad de subida", rate(link.get("tx bitrate", ""))),
                ]))
    gw = ""
    try:
        r = json.loads(run(["ip", "-j", "route", "show", "default"]) or "[]")
        gw = ", ".join(_("{n} por {n2}").format(n=x.get('gateway', ''), n2=x.get('dev', '')) for x in r if x.get("gateway"))
    except Exception:
        pass
    dns = [l.split()[1] for l in read("/etc/resolv.conf").splitlines()
           if l.startswith("nameserver") and len(l.split()) > 1]
    bt = [os.path.basename(x) for x in glob.glob("/sys/class/bluetooth/hci*") if ":" not in os.path.basename(x)]
    general = kv("General", [
        ("Nombre del equipo", Sens(socket.gethostname())),
        ("Puerta de enlace", Sens(gw)),
        ("Servidores DNS", ", ".join(dns)),
        ("Bluetooth", ", ".join(bt) if bt else "No detectado"),
    ])
    return section("red", "Red", [general] + wifi_blocks + [
        table("Interfaces", ["Interfaz", "Tipo", "Estado", "Velocidad", "Driver", "MAC", "IPv4", "IPv6"], rows),
    ])


# ───────────────────────────── audio y USB ─────────────────────────────

def sec_audio(ctx):
    cards = []
    for line in read("/proc/asound/cards").splitlines():
        m = re.match(r"^\s*(\d+)\s+\[(\S+)\s*\]:\s*(\S+)\s+-\s+(.*)$", line)
        if m:
            cards.append((m.group(1), m.group(4), m.group(3)))
    pa = keyvals(run(["pactl", "info"], timeout=4), ":")
    blocks = [
        table("Tarjetas de sonido", ["N.º", "Nombre", "Driver"], cards),
        kv("Servidor de sonido", [
            ("Servidor", pa.get("Server Name", "")), ("Versión", pa.get("Server Version", "")),
            ("Salida predeterminada", pa.get("Default Sink", "")),
            ("Entrada predeterminada", pa.get("Default Source", "")),
            ("Formato", pa.get("Default Sample Specification", "")),
        ]),
    ]
    if not cards:
        blocks.append(note("No se ha detectado ninguna tarjeta de sonido."))
    return section("audio", "Sonido", blocks)


def usb_speed(s):
    try:
        v = float(s)
    except ValueError:
        return ""
    return f"{num(v / 1000, 0 if v % 1000 == 0 else 1)} Gb/s" if v >= 1000 else f"{num(v, 0 if v == int(v) else 1)} Mb/s"


def sec_usb(ctx):
    rows = []
    for p in sorted(glob.glob("/sys/bus/usb/devices/*"), key=natural):
        base = os.path.basename(p)
        if base.startswith("usb") or not os.path.exists(p + "/idVendor"):
            continue
        speed = read(p + "/speed")
        drivers = sorted({os.path.basename(os.path.realpath(i + "/driver"))
                          for i in glob.glob(p + "/" + base + ":*") if os.path.exists(i + "/driver")})
        rows.append((base, f"{read(p + '/idVendor')}:{read(p + '/idProduct')}",
                     read(p + "/manufacturer"), read(p + "/product"),
                     f"USB {read(p + '/version').strip()}", usb_speed(speed),
                     read(p + "/bMaxPower"), ", ".join(drivers)))
    blocks = [table("Dispositivos USB conectados", ["Puerto", "ID", "Fabricante", "Producto", "Versión",
                                                    "Velocidad", "Consumo máx.", "Driver"], rows)]
    if not rows:
        blocks.append(note("No hay dispositivos USB conectados (o el sistema no expone el bus USB)."))
    return section("usb", "Dispositivos USB", blocks)


# ─────────────────────────── sensores y energía ───────────────────────────

CHIPS = {"coretemp": "CPU", "k10temp": "CPU", "zenpower": "CPU", "nvme": "SSD NVMe",
         "drivetemp": "Disco", "amdgpu": "Gráfica AMD", "nouveau": "Gráfica NVIDIA",
         "acpitz": "ACPI", "iwlwifi_1": "Wi-Fi", "pch_cannonlake": "Chipset"}


def pwm_mode(chip, enable):
    if enable is None:
        return ""
    if enable == 0:
        return "Sin regulación (al máximo)"
    if enable == 1:
        return "Curva personalizada" if chip == "asus_custom_fan_curve" else "Manual (lo fija un programa)"
    return "Automático (lo decide el firmware)"


def fan_curves(hw, nice):
    """Puntos temperatura → potencia que algunos chips publican (pwmN_auto_pointM_*)."""
    pts = {}
    for f in glob.glob(hw + "/*_auto_point*_pwm"):
        m = re.match(r"(pwm|temp)(\d+)_auto_point(\d+)_pwm$", os.path.basename(f))
        t, pw = read_int(f[:-4] + "_temp"), read_int(f)
        if not m or t is None or pw is None:
            continue
        t = t / 1000 if abs(t) > 1000 else t          # milésimas de grado salvo en algún portátil
        pts.setdefault((m.group(1), int(m.group(2))), []).append((int(m.group(3)), t, pw * 100 / 255))
    rows = []
    for (kind, idx), lst in sorted(pts.items()):
        who = _("Ventilador {idx}").format(idx=idx) if kind == "pwm" else _("Sonda de temperatura {idx}").format(idx=idx)
        rows.append((nice, who, ", ".join(f"{t:.0f} °C → {pw:.0f} %" for _n, t, pw in sorted(lst))))
    return rows


TRIPS = {"active": "acelera el ventilador", "passive": "frena el procesador",
         "hot": "aviso de calor", "critical": "apagado de emergencia"}


def sec_sensors(ctx):
    temps, fans, volts, power, curves = [], [], [], [], []
    cpu_temp, hot = None, {}
    for hw in sorted(glob.glob("/sys/class/hwmon/hwmon*"), key=natural):
        chip = read(hw + "/name") or os.path.basename(hw)
        nice = f"{CHIPS[chip]} ({chip})" if chip in CHIPS else chip
        pwms = {}
        for f in glob.glob(hw + "/pwm[0-9]*"):
            m = re.match(r"pwm(\d+)$", os.path.basename(f))
            if m:
                pwms[int(m.group(1))] = (read_int(f), read_int(f + "_enable"))
        hw_fans = []
        for f in sorted(glob.glob(hw + "/*_input"), key=natural):
            base = f[:-6]
            fname = os.path.basename(base)
            kind = re.match(r"[a-z]+", fname).group(0)
            raw = read_int(f)
            if raw is None:
                continue
            label = read(base + "_label") or fname
            if kind == "temp":
                t = raw / 1000
                if not -40 < t < 150:
                    continue
                mx, crit = read_int(base + "_max"), read_int(base + "_crit")
                lim = " / ".join(f"{x / 1000:.0f} °C" for x in (mx, crit) if x and 0 < x < 200000)
                temps.append((nice, label, f"{num(t)} °C", lim))
                if CHIPS.get(chip) == "CPU":
                    cpu_temp = max(cpu_temp or 0, t)
                near = t >= 95 or bool(crit and 0 < crit < 200000 and t >= crit / 1000 - 5)
                if (near or t >= 85) and (near, t) > hot.get(nice, (False, 0, ""))[:2]:
                    hot[nice] = (near, t, label)
            elif kind == "fan":
                hw_fans.append((int(re.search(r"\d+", fname).group(0)), raw, label, base))
            elif kind == "in":
                volts.append((nice, label, f"{num(raw / 1000, 3)} V"))
            elif kind == "power":
                power.append((nice, label, f"{num(raw / 1e6, 2)} W"))
            elif kind == "curr":
                power.append((nice, label, f"{num(raw / 1000, 3)} A"))
        for idx, rpm, label, base in hw_fans:
            duty = pwms.get(idx) or (list(pwms.values())[0] if len(pwms) == 1 and len(hw_fans) == 1 else None)
            level, fmax = "", read_int(base + "_max")
            if duty and duty[0] is not None:
                level = f"{duty[0] * 100 / 255:.0f} %"
            elif fmax and fmax > 0:
                level = _("{n:.0f} % de su máximo").format(n=min(100, rpm * 100 / fmax))
            fmin = read_int(base + "_min")
            fans.append((nice, label, f"{rpm} RPM" if rpm else "Parado", level,
                         pwm_mode(chip, duty[1]) if duty else "",
                         f"{fmin} RPM" if fmin else ""))
        curves += fan_curves(hw, nice)

    for f in glob.glob("/sys/class/drm/card*/device/gpu_od/fan_ctrl/fan_curve"):   # gráficas AMD
        pts = re.findall(r"^\d+:\s*(\d+)C\s+(\d+)%", read(f), re.M)
        if any(int(pw) for _t, pw in pts):
            curves.append(("Gráfica AMD", "Ventilador", ", ".join(f"{t} °C → {pw} %" for t, pw in pts)))

    for nice, (near, t, label) in hot.items():   # un aviso por chip: su sensor más caliente
        if near:
            ctx.flag("bad", "Temperatura", _("{nice}, sensor {label}: {t:.0f} °C, muy cerca de su límite. Si lo alcanza, el equipo se frenará o se apagará para protegerse.").format(nice=nice, label=label, t=t), COOL_TODO, "sysmon")
        else:
            ctx.flag("warn", "Temperatura", _("{nice}, sensor {label}: {t:.0f} °C, temperatura alta. Puede ser normal mientras el equipo trabaja a fondo (juegos, vídeo, compilar).").format(nice=nice, label=label, t=t), COOL_TODO, "sysmon")

    zones = []
    for z in sorted(glob.glob("/sys/class/thermal/thermal_zone*"), key=natural):
        t = read_int(z + "/temp")
        trips = []
        for tp in sorted(glob.glob(z + "/trip_point_*_temp"), key=natural):
            v, typ = read_int(tp), read(tp[:-5] + "_type")
            if v is not None and 0 < v < 200000:
                trips.append((v, f"{v / 1000:.0f} °C: {_(TRIPS.get(typ, typ))}"))
        if t is not None and -40000 < t < 150000:
            zones.append((read(z + "/type"), f"{num(t / 1000)} °C", "; ".join(x for _v, x in sorted(trips))))
    if not temps:
        temps = [("Zona térmica", z[0], z[1], "") for z in zones]

    cool = {}
    for c in glob.glob("/sys/class/thermal/cooling_device*"):
        cur, mx = read_int(c + "/cur_state"), read_int(c + "/max_state")
        if cur is None or not mx or mx <= 0:
            continue
        g = cool.setdefault(read(c + "/type"), [0, 0, 0.0])
        g[0] += 1
        g[1] += 1 if cur > 0 else 0
        g[2] = max(g[2], cur / mx)
    cooling = [({"Fan": "Ventilador (ACPI)", "Processor": "Freno del procesador"}.get(t, t), n,
                _("{act} de {n} actuando").format(act=act, n=n) if act else "En reposo", f"{lvl * 100:.0f} %")
               for t, (n, act, lvl) in sorted(cool.items())]

    tp = keyvals(read("/proc/acpi/ibm/fan"), ":")
    thinkpad = kv("Ventilador del ThinkPad", [
        ("Velocidad", f"{tp['speed']} RPM" if tp.get("speed") else ""),
        ("Nivel", {"auto": "Automático (lo decide el firmware)", "full-speed": "Al máximo",
                   "disengaged": "Sin límite"}.get(tp.get("level", ""), tp.get("level", ""))),
    ]) if tp else None

    if cpu_temp is not None:
        ctx.summary["temp"] = f"{cpu_temp:.0f} °C"
    spinning = [f for f in fans if f[2] != "Parado"]
    if spinning:
        ctx.summary["fans"] = ", ".join(f"{f[2]}" + (f" ({f[3]})" if f[3] else "") for f in spinning[:3])
    blocks = [
        table("Temperaturas", ["Chip", "Sensor", "Ahora", "Máx. / crítica"], temps,
              help="Cada chip informa de su temperatura. La columna de la derecha es el límite que fija el fabricante."),
        table("Ventiladores", ["Chip", "Ventilador", "Velocidad", "Potencia", "Control", "Mínimo"], fans),
        thinkpad,
        table("Curvas de ventilador programadas", ["Chip", "Canal", "Temperatura → potencia"], curves,
              help="A qué velocidad gira el ventilador según la temperatura."),
        table("Umbrales térmicos del firmware (ACPI)", ["Zona", "Ahora", "Qué ocurre a cada temperatura"],
              [z for z in zones if z[2]], adv=True),
        table("Mecanismos de refrigeración del sistema", ["Mecanismo", "Cantidad", "Estado", "Nivel"], cooling,
              adv=True),
        table("Voltajes", ["Chip", "Sensor", "Valor"], volts, adv=True),
        table("Potencia y corriente", ["Chip", "Sensor", "Valor"], power, adv=True),
    ]
    if not (temps or fans or volts):
        blocks.append(note("Este sistema no publica ningún sensor. Es habitual en máquinas virtuales y en "
                           "algunos equipos cuyo fabricante no ofrece drivers de sensores para Linux."))
    else:
        if not fans:
            blocks.append(note("No aparecen ventiladores. Es normal en muchos equipos: el chip que los controla "
                               "no siempre tiene driver en Linux, y en ese caso la placa los sigue gobernando "
                               "por su cuenta con normalidad."))
        if not curves:
            blocks.append(note("La curva que configuras en la BIOS vive en el chip de la placa y casi "
                               "ningún driver deja leerla. Aparece aquí solo cuando el chip la publica "
                               "(algunas placas con Nuvoton o ITE, portátiles ASUS ROG, gráficas AMD). "
                               "Los umbrales ACPI de arriba son lo más parecido que ofrece el resto."))
    return section("sensores", "Sensores y ventiladores", blocks)


LEVEL_NAMES = {"Full": "Llena", "High": "Alta", "Normal": "Normal", "Low": "Baja", "Critical": "Crítica",
               "Unknown": "Desconocida"}

STATUS = {"Charging": "Cargando", "Discharging": "Descargando", "Full": "Cargada",
          "Not charging": "Sin cargar (enchufada)", "Unknown": "Desconocido"}


PSU_CHIPS = ("corsairpsu",)
PSU_LABELS = {"power total": "Potencia total", "vrm temp": "Temperatura VRM", "case temp": "Temperatura interna",
              "power +12v": "Potencia +12 V", "power +5v": "Potencia +5 V", "power +3.3v": "Potencia +3,3 V"}


def psu_block():
    """Fuentes de alimentación con interfaz USB que el kernel publica como hwmon (driver corsair-psu)."""
    for hw in glob.glob("/sys/class/hwmon/hwmon*"):
        if read(hw + "/name") not in PSU_CHIPS:
            continue
        model, d = "", os.path.realpath(hw + "/device")
        for _i in range(6):                      # el nombre está en el dispositivo USB padre
            if read(d + "/product"):
                model = " ".join(x for x in (read(d + "/manufacturer"), read(d + "/product")) if x)
                break
            d = os.path.dirname(d)
        rows = [("Modelo", model or "Corsair")]
        for f in sorted(glob.glob(hw + "/power*_input"), key=natural):
            v = read_int(f)
            if v is not None:
                lab = read(f[:-6] + "_label") or os.path.basename(f[:-6])
                rows.append((PSU_LABELS.get(lab, lab), f"{num(v / 1e6)} W"))
        for f in sorted(glob.glob(hw + "/temp*_input"), key=natural):
            v = read_int(f)
            if v is not None:
                lab = read(f[:-6] + "_label") or os.path.basename(f[:-6])
                rows.append((PSU_LABELS.get(lab, lab), f"{num(v / 1000)} °C"))
        for f in sorted(glob.glob(hw + "/fan*_input"), key=natural):
            v = read_int(f)
            if v is not None:
                rows.append(("Ventilador", f"{v} RPM"))
        return kv("Fuente de alimentación", rows)
    return None


def sec_power(ctx):
    blocks = []
    for p in sorted(glob.glob("/sys/class/power_supply/*")):
        typ, name = read(p + "/type"), os.path.basename(p)
        if typ == "Battery" and read(p + "/scope") != "Device":
            ctx.data["has_battery"] = True
            unit, div, pre = ("Wh", 1e6, "energy") if os.path.exists(p + "/energy_full") else ("Ah", 1e6, "charge")
            full, design, now = (read_int(f"{p}/{pre}_{x}") for x in ("full", "full_design", "now"))
            health = pct(full, design) if full and design else None
            rate = read_int(p + "/power_now")
            volt = read_int(p + "/voltage_now")
            status = STATUS.get(read(p + "/status"), read(p + "/status"))
            blocks.append(kv(_("Batería {name}").format(name=name), [
                ("Estado", status), ("Carga", f"{read(p + '/capacity')} %"),
                ("Salud", _("{health:.0f} % de la capacidad original").format(health=health) if health else ""),
                ("Capacidad actual", f"{num(full / div)} {unit}" if full else ""),
                ("Capacidad de fábrica", f"{num(design / div)} {unit}" if design else ""),
                ("Ciclos de carga", read(p + "/cycle_count") if read(p + "/cycle_count") not in ("", "0") else ""),
                ("Consumo o carga ahora", f"{num(rate / 1e6)} W" if rate else ""),
                ("Voltaje", f"{num(volt / 1e6, 2)} V" if volt else ""),
                ("Tecnología", read(p + "/technology")),
                ("Fabricante / modelo", " ".join(x for x in (read(p + "/manufacturer"), read(p + "/model_name")) if x)),
            ]))
            if health is not None:
                ctx.summary["bateria"] = _("{n} % de carga, salud {health:.0f} %").format(n=read(p + '/capacity'), health=health)
                ctx.data["bat_now"] = read_int(p + "/capacity")
                bat_todo = ("Es desgaste normal con el uso. Si la autonomía ya no te basta, el fabricante o un "
                            "servicio técnico puede cambiarla por una original. No la desmontes tú: una batería "
                            "de litio dañada puede incendiarse. Si notas que se hincha o deforma la carcasa, "
                            "deja de usar el equipo y llévalo a revisar.")
                if health < 60:
                    ctx.flag("warn", "Batería", _("La batería conserva solo el {health:.0f} % de su capacidad original.").format(health=health),
                             bat_todo)
                elif health < 80:
                    ctx.flag("info", "Batería", _("La batería conserva el {health:.0f} % de su capacidad original.").format(health=health),
                             bat_todo)
        elif typ == "Battery":
            lvl = read(p + "/capacity_level")
            dev = read(p + '/model_name') or name
            # El nombre de un periférico Bluetooth puede llevar el de su dueño: va en un campo que se puede ocultar.
            personal = any(b in dev.lower() for b in ctx.data.get("bt_names", []))
            blocks.append(kv("Batería de un periférico Bluetooth" if personal else
                             _("Batería de {dispositivo}").format(dispositivo=dev), [
                ("Dispositivo", SensField(dev) if personal else ""),
                ("Carga", f"{read(p + '/capacity')} %" if read(p + "/capacity") else LEVEL_NAMES.get(lvl, lvl)),
                ("Estado", STATUS.get(read(p + "/status"), read(p + "/status")))]))
        elif typ in ("Mains", "USB"):
            blocks.append(kv(_("Alimentación {name}").format(name=name), [
                ("Tipo", "Corriente" if typ == "Mains" else "USB"),
                ("Conectada", "Sí" if read(p + "/online") == "1" else "No")]))
    profile = run(["powerprofilesctl", "get"], timeout=3)
    sleep = read("/sys/power/mem_sleep")
    cur = re.search(r"\[(\w+)\]", sleep)
    states = read("/sys/power/state").split()
    limits = [(read_int(b + "/charge_control_start_threshold"), read_int(b + "/charge_control_end_threshold"))
              for b in glob.glob("/sys/class/power_supply/BAT*")]
    limit = next((_("empieza al {a} %, para al {b} %").format(a=a, b=b) if a else _("para al {b} %").format(b=b)
                  for a, b in limits if b and b < 100), "")
    govs = sorted({read(f) for f in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_governor")} - {""})
    epps = sorted({read(f) for f in
                   glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/energy_performance_preference")} - {""})
    on_ac = any(read(a + "/online") == "1" for a in glob.glob("/sys/class/power_supply/*")
                if read(a + "/type") == "Mains")
    if profile == "power-saver" and on_ac:
        ctx.flag("info", "Energía", "El equipo está enchufado, pero tiene activo el perfil de ahorro de energía, "
                 "que limita el rendimiento.",
                 "Si lo notas lento, elige el perfil equilibrado o el de rendimiento en la configuración de "
                 "energía. Si lo prefieres silencioso y fresco, déjalo así.", "power")
    blocks.append(kv("Ahorro de energía", [
        ("Perfil de energía activo", profile),
        ("Perfil del fabricante", read("/sys/firmware/acpi/platform_profile")),
        ("Gobernador del procesador", ", ".join(govs)),
        ("Preferencia entre ahorro y rendimiento", ", ".join(epps)),
        ("Suspensión", {"deep": "Profunda (S3): gasta muy poco", "s2idle": "Ligera (s2idle): gasta algo más"}
         .get(cur.group(1), cur.group(1)) if cur else ""),
        ("Modos de suspensión que admite", ", ".join(sleep.replace("[", "").replace("]", "").split())),
        ("Hibernación", ("Disponible en el kernel" if "disk" in states else "No disponible") if states else ""),
        ("Límite de carga de la batería", limit),
    ]))
    psu = psu_block()
    if psu:
        blocks.insert(0, psu)
    if not ctx.data.get("has_battery"):
        blocks.append(note("Este equipo no tiene batería (o el sistema no la expone)."))
    if not psu and ctx.data.get("chassis") not in ("Portátil", "Subportátil", "Convertible", "Desmontable",
                                                   "Tableta", "Dispositivo de mano"):
        blocks.append(note("Fuente de alimentación: las fuentes de un ordenador de sobremesa no comunican al "
                           "equipo su marca, modelo ni potencia, así que ningún programa puede leerlos. Solo las "
                           "fuentes «inteligentes» con cable USB interno (por ejemplo, Corsair HXi, RMi y AXi) "
                           "envían sus datos, y MintMachine los muestra aquí cuando las detecta. Para saber la "
                           "tuya, mira la factura o la caja del equipo; no abras el equipo para mirar la etiqueta."))
    return section("energia", "Batería y energía", blocks)


# ───────────────────────────── sistema operativo ─────────────────────────────

def fmt_uptime(secs):
    d, r = divmod(int(secs), 86400)
    h, r = divmod(r, 3600)
    return (f"{d} d " if d else "") + _("{h} h {n} min").format(h=h, n=r // 60)


@once
def dpkg_packages():
    out = run(["dpkg-query", "-W", "-f", "${Package}\t${Version}\t${db:Status-Abbrev}\n"], timeout=15)
    pk = {}
    for line in out.splitlines():
        p = line.split("\t")
        if len(p) == 3 and p[2].startswith("ii"):
            pk[p[0]] = p[1]
    return pk


def sec_system(ctx):
    osr = keyvals(read("/etc/os-release"))
    mint = keyvals(read("/etc/linuxmint/info"))
    distro = mint.get("DESCRIPTION") or osr.get("PRETTY_NAME") or platform.system()
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
    if "cinnamon" in desktop.lower():
        desktop = run(["cinnamon", "--version"], timeout=3) or desktop
    session = os.environ.get("XDG_SESSION_TYPE", "")
    try:
        up = float(read("/proc/uptime").split()[0])
    except Exception:
        up = 0
    birth = run(["stat", "-c", "%W", "/"])
    installed = ""
    if birth.isdigit() and int(birth) > 0:
        installed = datetime.datetime.fromtimestamp(int(birth)).strftime("%d/%m/%Y")
    tz = read("/etc/timezone")
    if not tz and "zoneinfo/" in os.path.realpath("/etc/localtime"):
        tz = os.path.realpath("/etc/localtime").split("zoneinfo/")[1]
    boot = run(["systemd-analyze"], timeout=5).splitlines()
    boot = boot[0].replace("Startup finished in ", "") if boot and "Startup finished" in boot[0] else ""
    base = ""
    if mint and read("/etc/debian_version"):
        base = ("Debian " if osr.get("ID_LIKE", "") == "debian" or "debian" in osr.get("ID", "") else "") \
            + read("/etc/debian_version")
    blame = []
    for line in run(["systemd-analyze", "blame", "--no-pager"], timeout=6).splitlines()[:8]:
        m = re.match(r"\s*(.+?)\s+(\S+\.(?:service|mount|device|socket|target|swap))$", line)
        if m:
            blame.append((m.group(2), m.group(1)))
    ctx.summary.update(os=distro, kernel=platform.release(), escritorio=desktop, uptime=fmt_uptime(up))
    return section("sistema", "Sistema operativo", [
        kv("Distribución", [
            ("Sistema", distro), ("Nombre en clave", mint.get("CODENAME") or osr.get("VERSION_CODENAME", "")),
            ("Edición", mint.get("EDITION", "")), ("Base", base),
            ("Instalado el", installed),
        ]),
        kv("Núcleo", [
            ("Kernel", platform.release()), ("Compilación", platform.version()),
            ("Arquitectura", platform.machine()),
            ("Parámetros de arranque", read("/proc/cmdline")),
            ("Sistema de inicio", read("/proc/1/comm")),
        ], adv=True),
        kv("Sesión", [
            ("Escritorio", desktop),
            ("Servidor gráfico", {"x11": "X11 (Xorg)", "wayland": "Wayland"}.get(session, session)),
            ("Intérprete de órdenes", os.environ.get("SHELL", "")),
            ("Idioma", os.environ.get("LANG", "")), ("Zona horaria", tz),
            ("Encendido desde hace", fmt_uptime(up) if up else ""),
            ("Duración del último arranque", boot),
        ]),
        table("Lo que más tardó en el último arranque", ["Unidad", "Tiempo"], blame, adv=True,
              help="Servicios que más tiempo tardaron en arrancar. Varios arrancan a la vez, así que los "
                   "tiempos no se suman."),
    ])


# ─────────────────────────── drivers (módulos del kernel) ───────────────────────────

TAINT = {0: ("P", "hay módulos privativos cargados", "info"),
         1: ("F", "se forzó la carga de un módulo", "warn"),
         4: ("M", "el procesador notificó un error de hardware (machine check)", "bad"),
         5: ("B", "se detectó una página de memoria corrupta", "bad"),
         7: ("D", "el kernel sufrió un fallo grave (oops) en esta sesión", "warn"),
         9: ("W", "el kernel emitió una advertencia en esta sesión", "info"),
         10: ("C", "hay drivers experimentales (staging) cargados", "info"),
         11: ("I", "se aplicó un apaño por un fallo del firmware", "info"),
         12: ("O", "hay módulos externos al kernel (DKMS o de terceros)", "info"),
         13: ("E", "hay módulos sin firmar cargados", "info"),
         14: ("L", "hubo un bloqueo temporal del sistema (soft lockup)", "warn")}

TAINT_TODO = {
    "M": "Suele deberse a calor, a la memoria o a un ajuste de la BIOS fuera de fábrica. Haz una copia de "
         "seguridad y, si se repite o el equipo se cuelga, consúltalo con un servicio técnico.",
    "B": "Puede ser un fallo de la memoria. Haz una copia de seguridad y consúltalo con un servicio técnico "
         "si se repite.",
    "D": "Reinicia el equipo. Si vuelve a pasar, busca el mensaje en «Diagnóstico → errores del registro» y "
         "pregunta en el foro de tu distribución con el informe de MintMachine (con los datos personales ocultos).",
    "L": "Puede ser puntual. Si el equipo se queda congelado a menudo, pregunta en el foro de tu distribución "
         "adjuntando el informe de MintMachine.",
    "F": "Alguien forzó la carga de un driver. Si no lo hiciste tú a propósito, pregunta en el foro de tu "
         "distribución.",
}

MOD_TAINT = {"P": "privativo", "O": "externo al kernel", "E": "sin firmar", "C": "experimental", "F": "forzado"}


def sec_modules(ctx):
    rows, special = [], []
    for line in read("/proc/modules").splitlines():
        p = line.split()
        if len(p) < 4:
            continue
        name = p[0]
        deps = p[3].strip(",").replace(",", ", ") if p[3] != "-" else ""
        taint = read(f"/sys/module/{name}/taint")
        notes = ", ".join(_(MOD_TAINT[c]) for c in taint if c in MOD_TAINT)
        ver = read(f"/sys/module/{name}/version")
        rows.append((name, ver, human(p[1]), p[2], deps, notes))
        if notes:
            special.append((name, ver, notes))
    rows.sort(key=lambda r: r[0])
    mask = read_int("/proc/sys/kernel/tainted", 0) or 0
    estado = []
    for bit, (letter, text, level) in TAINT.items():
        if mask & (1 << bit):
            estado.append((letter, text))
            if level != "info":
                ctx.flag(level, "Kernel", _("El kernel indica que {problema}.").format(problema=_(text)),
                         TAINT_TODO.get(letter, ""))
    dk = [l for l in run(["dkms", "status"], timeout=5).splitlines() if l.strip()]
    blocks = [
        kv("Estado del kernel", [
            ("Módulos cargados", len(rows)),
            ("Kernel «limpio»", "Sí" if mask == 0 else _("No (marca {mask})").format(mask=mask)),
        ] + [(_("Marca {l}").format(l=l), t) for l, t in estado]),
        table("Drivers privativos o externos", ["Módulo", "Versión", "Motivo"], special,
              help="Drivers que no vienen dentro del kernel, como el de NVIDIA. Es normal tenerlos."),
        table("Módulos DKMS", ["Estado"], [(l,) for l in dk],
              help="Drivers externos que se recompilan solos cada vez que se instala un kernel nuevo."),
        table("Todos los módulos cargados", ["Módulo", "Versión", "Tamaño", "En uso", "Lo usan", "Notas"], rows,
              adv=True),
    ]
    if not rows:
        blocks.append(note("No se puede leer la lista de módulos del kernel en este sistema."))
    blocks.append(note("En Linux los drivers son módulos del kernel. Para ver qué driver usa cada "
                       "dispositivo, mira las secciones «Dispositivos PCI» y «Dispositivos USB»."))
    return section("drivers", "Drivers y módulos", blocks)


# ───────────────── registro del kernel y actualizaciones de drivers ─────────────────

@once
def kernel_log():
    """Busca en los mensajes del kernel de este arranque lo que suele indicar problemas."""
    out = run(["journalctl", "-k", "-b", "-q", "--no-pager", "-o", "cat"], timeout=10) or run(["dmesg"], timeout=5)
    res = {"ok": bool(out), "fw": [], "fw_driver": {}, "oom": [], "io": 0, "mce": 0, "thermal": 0}
    for line in out.splitlines():
        m = re.search(r"firmware: failed to load (\S+)|Direct firmware load for (\S+) failed", line)
        if m:
            name = m.group(1) or m.group(2)
            if name not in res["fw"]:
                res["fw"].append(name)
            d = re.match(r"\s*([^\s:]+):? \S+: ", line[:m.start()] + ": ")    # «iwlwifi 0000:04:00.0: …»
            if d and name not in res["fw_driver"]:
                res["fw_driver"][name] = d.group(1)
        m = re.search(r"Out of memory: Killed process \d+ \(([^)]+)\)", line)
        if m:
            res["oom"].append(m.group(1))
        if re.search(r"I/O error, dev|critical medium error|EXT4-fs error|BTRFS error|XFS \(.*\): .*error|"
                     r"ata\d+\.\d+: failed command|nvme\d+: I/O .* timeout", line):
            res["io"] += 1
        if re.search(r"mce: \[Hardware Error\]|Machine check events logged", line):
            res["mce"] += 1
        if "cpu clock throttled" in line:
            res["thermal"] += 1
    return res


@once
def fwupd_info():
    devs, upd = [], {}
    try:
        devs = json.loads(run(["fwupdmgr", "get-devices", "--json"], timeout=15) or "{}").get("Devices", [])
    except Exception:
        pass
    try:
        for d in json.loads(run(["fwupdmgr", "get-updates", "--json"], timeout=20) or "{}").get("Devices", []):
            rel = d.get("Releases") or []
            if rel:
                upd[d.get("DeviceId") or d.get("Name")] = rel[0].get("Version", "")
    except Exception:
        pass
    return devs, upd


DRIVER_RULES = [
    (r"linux-image-(amd64|generic\S*|\S+-amd64|\d\S*)$", "Kernel (trae casi todos los drivers)"),
    (r"(nvidia-driver\S*|nvidia-kernel-dkms|nvidia-dkms-\S+|xserver-xorg-video-nvidia\S*)$", "Gráfica NVIDIA"),
    (r"(libgl1-mesa-dri|mesa-vulkan-drivers|mesa-va-drivers|intel-media-va-driver\S*|"
     r"xserver-xorg-video-(amdgpu|ati|intel|nouveau))$", "Gráfica (drivers libres)"),
    (r"(firmware-\S+|linux-firmware)$", "Firmware de dispositivos"),
    (r"(intel-microcode|amd64-microcode)$", "Microcódigo del procesador"),
    (r"\S+-dkms$", "Driver externo (DKMS)"),
    (r"(bluez|alsa-ucm-conf|libinput10|wireless-regdb|cups|hplip|sane-backends|fwupd)$", "Periféricos"),
]
IMPORTANT_PCI = {"01": "almacenamiento", "02": "red", "03": "gráfica", "04": "sonido o vídeo",
                 "09": "entrada", "0d": "inalámbrico"}


# Archivos que un driver pide siempre aunque ninguna distribución los incluya: que falten es lo normal.
FW_OPTIONAL = {
    "iwl-debug-yoyo.bin": "Configuración de depuración opcional del Wi-Fi Intel, para los desarrolladores de "
                          "Intel. No viene en ningún paquete y el Wi-Fi funciona sin ella.",
}
# Qué dispositivo hay detrás de cada driver y qué paquete de Debian/LMDE trae su firmware
# (en Linux Mint y Ubuntu todo viene en linux-firmware).
FW_DRIVERS = [
    (r"iwlwifi$", "Wi-Fi Intel"), (r"(btusb|btintel|btrtl|bluetooth|hci\d+)$", "Bluetooth"),
    (r"amdgpu$", "Gráfica AMD"), (r"radeon$", "Gráfica AMD (antigua)"), (r"i915|xe$", "Gráfica Intel"),
    (r"nouveau$", "Gráfica NVIDIA (driver libre)"), (r"(r8169|r8152)$", "Red por cable Realtek"),
    (r"(rtw88|rtw89|rtl8\w+)", "Wi-Fi Realtek"), (r"(ath9k|ath10k|ath11k|ath12k)", "Wi-Fi Qualcomm Atheros"),
    (r"(mt76|mt79)", "Wi-Fi MediaTek"), (r"(snd_|sof-|sof_)", "Sonido"),
]
FW_PACKAGES = [
    (r"(iwlwifi-|intel/ibt-)", "firmware-iwlwifi"), (r"(amdgpu/|radeon/)", "firmware-amd-graphics"),
    (r"(rtl_nic/|rtw88/|rtw89/|rtl_bt/|rtlwifi/)", "firmware-realtek"), (r"(ath9k|ath10k/|ath11k/|ath12k/)", "firmware-atheros"),
    (r"(i915/|xe/|nvidia/|mediatek/)", "firmware-misc-nonfree"),
]


def firmware_rows(log, pk):
    """Archivos de firmware que faltan: (archivo, driver, dispositivo, paquete, opcional)."""
    ubuntu = "linux-firmware" in pk
    rows = []
    for f in log["fw"]:
        drv = log.get("fw_driver", {}).get(f, "")
        dev = next((d for rx, d in FW_DRIVERS if drv and re.match(rx, drv, re.I)), "")
        pkg = "" if f in FW_OPTIONAL else ("linux-firmware" if ubuntu else
                                          next((p for rx, p in FW_PACKAGES if re.match(rx, f)), ""))
        rows.append((f, drv, _(dev) if dev else "", pkg, f in FW_OPTIONAL))
    return rows


def sec_updates(ctx):
    pk = dpkg_packages()
    running = platform.release()
    wanted = []
    for name in sorted(pk):
        if re.match(r"linux-image-\d", name) and name != "linux-image-" + running:
            continue                                   # kernels antiguos: no interesan aquí
        for rx, cat in DRIVER_RULES:
            if re.match(rx, name):
                wanted.append((name, cat))
                break
    policy, cur = {}, None
    if wanted:
        for line in run(["apt-cache", "policy"] + [n for n, _c in wanted], timeout=20).splitlines():
            if line and not line.startswith(" ") and line.endswith(":"):
                cur = policy.setdefault(line[:-1], {})
            elif cur is not None and line.startswith("  Installed:"):
                cur["inst"] = line.split(":", 1)[1].strip()
            elif cur is not None and line.startswith("  Candidate:"):
                cur["cand"] = line.split(":", 1)[1].strip()
    rows, pending = [], []
    for name, cat in wanted:
        inst, cand = pk[name], policy.get(name, {}).get("cand", "")
        newer = bool(cand) and cand not in (inst, "(none)") and run_ok(["dpkg", "--compare-versions", cand, "gt", inst])
        if newer:
            pending.append(name)
        rows.append((name, "Hay versión nueva" if newer else ("Al día" if cand else "Sin datos del repositorio"),
                     inst, cand if newer else "", cat))
    rows.sort(key=lambda r: (r[1] != "Hay versión nueva", [c for _r, c in DRIVER_RULES].index(r[4]), r[0]))
    if pending:
        ctx.flag("info", "Drivers", _("Hay versión nueva de: {paquetes}.").format(
                 paquetes=", ".join(pending[:8]) + (" " + _("y otros") if len(pending) > 8 else "")),
                 "Instálala con el Gestor de actualizaciones, como el resto de actualizaciones, y reinicia "
                 "al terminar.", "updates")
    ctx.data["driver_updates"] = len(pending)

    kernels = sorted((n.replace("linux-image-", "") for n in pk if re.match(r"linux-image-\d", n)), key=natural)
    newest = kernels[-1] if kernels else ""
    meta = [n for n in pk if re.match(r"linux-image-(amd64|generic\S*|\S+-amd64)$", n)
            and not re.match(r"linux-image-\d", n)]
    if newest and running in kernels and natural(newest) > natural(running):
        ctx.flag("info", "Drivers", _("Ya está instalado un kernel más nuevo ({newest}), pero sigues usando el anterior.").format(newest=newest),
                 "Reinicia el equipo para empezar a usarlo.")
    if kernels and not meta:
        ctx.flag("info", "Drivers", "El kernel no recibirá versiones nuevas por sí solo (falta el paquete "
                 "linux-image-amd64 o linux-image-generic).",
                 "En Linux Mint los kernels se gestionan desde el Gestor de actualizaciones, menú Ver → Kernels. "
                 "Si no sabes por qué falta, pregunta en el foro antes de tocar nada.", "updates")
    stamps = [os.path.getmtime(x) for x in ["/var/lib/apt/periodic/update-success-stamp", "/var/lib/apt/lists"]
              + glob.glob("/var/lib/apt/lists/*Release") if os.path.exists(x)]
    age = (time.time() - max(stamps)) / 86400 if stamps else None
    if age is not None and age > 10 and pk:
        ctx.flag("info", "Drivers", _("La lista de paquetes se actualizó hace {age:.0f} días: puede haber versiones nuevas que aún no se ven.").format(age=age),
                 "Abre el Gestor de actualizaciones y pulsa «Actualizar» (el botón de refrescar la lista).", "updates")
    resumen = kv("Kernel", [
        ("En ejecución", running),
        ("Más reciente instalado", newest if newest != running else "El mismo que está en ejecución"),
        ("Se actualiza solo mediante", ", ".join(meta) if meta else ("Nada (falta el metapaquete)" if kernels else "")),
        ("Lista de paquetes consultada", (_("Actualizada hace {age:.0f} días").format(age=age) if age >= 1 else "Actualizada hoy")
         if age is not None else ""),
    ])

    devs, upd = fwupd_info()
    fw_rows, fw_pending = [], []
    for d in devs:
        if not d.get("Version"):
            continue
        new = upd.get(d.get("DeviceId")) or upd.get(d.get("Name"))
        updatable = "updatable" in (d.get("Flags") or [])
        if new:
            fw_pending.append(d.get("Name", ""))
        fw_rows.append((d.get("Name", ""), "Hay versión nueva" if new else
                        ("Al día" if updatable else "No se actualiza desde Linux"),
                        d.get("Version", ""), new or "", d.get("Vendor", "")))
    fw_rows.sort(key=lambda r: (r[1] != "Hay versión nueva", r[0]))
    if fw_pending:
        ctx.flag("info", "Firmware", _("El fabricante ha publicado firmware nuevo para: {dispositivos}.").format(
                 dispositivos=", ".join(fw_pending)),
                 "No es urgente salvo que el fabricante lo indique. Si decides instalarlo: haz antes una copia de "
                 "seguridad, enchufa el portátil a la corriente y no apagues el equipo mientras se instala, "
                 "aunque tarde y la pantalla se quede en negro. Si no te sientes seguro, déjalo como está o "
                 "pide ayuda a un técnico.", "firmware")

    nodrv = []
    for d in pci_devices():
        cname, cid = split_id(d.get("Class", ""))
        if not d.get("Driver") and cid[:2] not in ("06", "05", "08", "0c", "11", "ff", ""):
            dname = split_id(d.get("Device", ""))[0]
            nodrv.append((d["Slot"], cname, f"{split_id(d.get('Vendor', ''))[0]} {dname}".strip(),
                          ", ".join(d["modules"]) or "Ninguno conocido"))
            if cid[:2] in IMPORTANT_PCI:
                ctx.flag("warn", "Drivers", _("El dispositivo de {n} «{dname}» no tiene driver cargado.").format(n=IMPORTANT_PCI[cid[:2]], dname=dname),
                         "Abre el Gestor de controladores por si ofrece uno. Si no, pregunta en el foro de tu "
                         "distribución con el informe de MintMachine (con los datos personales ocultos).", "drivers")
    log = kernel_log()
    fwrows = firmware_rows(log, pk)
    faltan = [r for r in fwrows if not r[4]]
    if faltan:
        lista = "; ".join(f"{f} ({dev or drv})" if (dev or drv) else f for f, drv, dev, _p, _o in faltan)
        pkgs = sorted({p for *_r, p, _o in faltan if p})
        ctx.flag("info", "Firmware", _("Falta firmware que pidió un driver: {lista}.").format(lista=lista),
                 _("Si ese dispositivo funciona bien, no hace falta hacer nada: muchos drivers prueban varias "
                   "versiones hasta dar con la instalada. Si falla, instala el paquete {paquete} con el Gestor "
                   "de software o con las actualizaciones pendientes, y reinicia.").format(paquete=", ".join(pkgs))
                 if pkgs else
                 "Si ese dispositivo funciona bien, no hace falta hacer nada: muchos drivers prueban varias "
                 "versiones hasta dar con la instalada. Si falla, instala las actualizaciones pendientes, "
                 "reinicia y, si sigue igual, pregunta en el foro de tu distribución con el informe de "
                 "MintMachine (con los datos personales ocultos).", "updates")

    blocks = [
        resumen,
        table("Paquetes de drivers y firmware", ["Paquete", "Estado", "Instalada", "Disponible", "Qué es"], rows,
              help="Comparación entre lo instalado y lo que ofrecen los repositorios de tu sistema."),
        table("Firmware de los dispositivos (fwupd)", ["Dispositivo", "Estado", "Versión actual",
                                                       "Versión nueva", "Fabricante"], fw_rows),
        table("Dispositivos sin driver cargado", ["Ranura", "Clase", "Dispositivo", "Módulos candidatos"], nodrv),
        table("Firmware que el kernel pidió y no encontró", ["Archivo", "Driver", "Dispositivo", "Paquete que lo trae", "Nota"],
              [(f, drv, dev, p, _(FW_OPTIONAL[f]) if o else "") for f, drv, dev, p, o in fwrows], adv=True),
    ]
    if not have("fwupdmgr"):
        blocks.append(note("Con el paquete fwupd instalado, aquí aparecerían también las actualizaciones "
                           "de BIOS, SSD, docks y periféricos que publica cada fabricante."))
    if faltan:
        blocks.append(note("Que falte un archivo de firmware no siempre es un problema: algunos drivers "
                           "prueban varias versiones hasta dar con la instalada. Si el dispositivo falla, "
                           "el paquete que lo trae suele ser firmware-misc-nonfree, firmware-iwlwifi, "
                           "firmware-realtek o linux-firmware."))
    blocks.append(note("En Linux casi todos los drivers viajan dentro del kernel, así que «tener el último "
                       "driver» equivale a tener el último kernel que ofrece tu distribución. Aparte van el "
                       "driver privativo de NVIDIA, los módulos DKMS, el firmware y el microcódigo. La "
                       "comparación se hace con los repositorios configurados en tu sistema, sin conectar "
                       "con internet: no dice si el fabricante ha publicado algo más nuevo por su cuenta."))
    return section("actualizaciones", "Actualizaciones de drivers", blocks)


# ─────────────────────────────── periféricos ───────────────────────────────

def sec_peripherals(ctx):
    inputs, cur = [], {}
    for line in read("/proc/bus/input/devices").splitlines() + [""]:
        if line.startswith("N: Name="):
            cur["name"] = line.split("=", 1)[1].strip('"')
        elif line.startswith("H: Handlers="):
            cur["h"] = line.split("=", 1)[1].split()
        elif not line.strip() and cur:
            h, name = cur.get("h", []), cur.get("name", "")
            kind = ""
            if any(x.startswith("js") for x in h):
                kind = "Mando de juego"
            elif any(x.startswith("mouse") for x in h):
                kind = "Panel táctil" if re.search(r"touchpad|trackpad|synaptics|elan", name, re.I) else "Ratón o puntero"
            elif "kbd" in h and "leds" in h:
                kind = "Teclado"
            if kind and (name, kind) not in inputs:
                inputs.append((name, kind))
            cur = {}
    cams = []
    for v in sorted(glob.glob("/sys/class/video4linux/video*"), key=natural):
        name = read(v + "/name")
        if name and name not in [c[0] for c in cams]:
            cams.append((name, "/dev/" + os.path.basename(v)))
    printers = [(SensField(l.strip()),) for l in run(["lpstat", "-e"], timeout=4).splitlines() if l.strip()]
    bt = []
    for line in run(["bluetoothctl", "devices"], timeout=4).splitlines():
        p = line.split(" ", 2)
        if len(p) == 3 and p[0] == "Device":
            bt.append((SensField(p[2]), Sens(p[1])))
    # Un teclado o ratón Bluetooth aparece también en la lista de entrada con el mismo nombre,
    # que el usuario puede haber personalizado: se oculta igual que en la tabla de Bluetooth.
    paired = [str(b[0]).lower() for b in bt if len(str(b[0])) >= 3]
    inputs = [(SensField(n) if any(p in n.lower() for p in paired) else n, k) for n, k in inputs]
    ctx.data["bt_names"] = paired
    mons = monitor_rows(monitors())
    blocks = [
        table("Monitores", MON_HEADERS, mons),
        table("Teclados, ratones y mandos", ["Dispositivo", "Tipo"], inputs),
        table("Cámaras", ["Cámara", "Nodo"], cams),
        table("Impresoras configuradas", ["Impresora"], printers),
        table("Dispositivos Bluetooth emparejados", ["Dispositivo", "Dirección"], bt),
    ]
    if not (inputs or cams or printers or bt or mons):
        blocks.append(note("No se ha detectado ningún periférico."))
    return section("perifericos", "Periféricos", blocks)


# ─────────────────────────────── software ───────────────────────────────

KEY_PKGS = [("Biblioteca C (glibc)", ["libc6"]), ("systemd", ["systemd"]),
            ("Servidor Xorg", ["xserver-xorg-core"]), ("Mesa (drivers 3D libres)", ["libgl1-mesa-dri"]),
            ("Driver NVIDIA", ["nvidia-driver", "nvidia-kernel-dkms"]),
            ("Cinnamon", ["cinnamon"]), ("GTK 3", ["libgtk-3-0t64", "libgtk-3-0"]),
            ("PipeWire", ["pipewire"]), ("PulseAudio", ["pulseaudio"]),
            ("NetworkManager", ["network-manager"]), ("GRUB", ["grub-common"]),
            ("Firmware no libre", ["firmware-misc-nonfree", "linux-firmware"]),
            ("Microcódigo Intel", ["intel-microcode"]), ("Microcódigo AMD", ["amd64-microcode"]),
            ("Python", ["python3"]), ("GCC", ["gcc"]), ("Bash", ["bash"]),
            ("Firefox", ["firefox", "firefox-esr"]), ("LibreOffice", ["libreoffice-core"]),
            ("Flatpak", ["flatpak"]), ("Wine", ["wine", "wine64"])]


def apt_repos():
    repos = []
    for f in ["/etc/apt/sources.list"] + sorted(glob.glob("/etc/apt/sources.list.d/*.list")):
        for line in read(f).splitlines():
            p = re.sub(r"\[[^\]]*\]", "", line).split()
            if len(p) >= 3 and p[0] == "deb":
                repos.append((p[1], p[2], " ".join(p[3:]), os.path.basename(f)))
    for f in sorted(glob.glob("/etc/apt/sources.list.d/*.sources")):
        for stanza in re.split(r"\n\s*\n", read(f)):
            d = keyvals(stanza, ":")
            if d.get("URIs") and d.get("Enabled", "yes").lower() != "no":
                repos.append((d["URIs"], d.get("Suites", ""), d.get("Components", ""), os.path.basename(f)))
    return repos


def sec_software(ctx):
    pk = dpkg_packages()
    versions = [("Kernel en ejecución", platform.release())]
    for label, names in KEY_PKGS:
        for n in names:
            if n in pk:
                versions.append((label, pk[n]))
                break
    kernels = sorted((n.replace("linux-image-", "") for n in pk
                      if re.match(r"linux-image-\d", n)), key=natural)
    fl = [l.split("\t") for l in run(["flatpak", "list", "--app", "--columns=name,application,version,origin"],
                                     timeout=10).splitlines() if "\t" in l]
    upg = []
    for line in run(["apt", "list", "--upgradable"], timeout=25).splitlines():
        m = re.match(r"^([^/\s]+)/\S+\s+(\S+)\s+\S+\s+\[upgradable from: (\S+)\]", line)
        if m:
            upg.append((m.group(1), m.group(3), m.group(2)))
    ctx.data["updates"] = len(upg)
    if upg:
        ctx.flag("info", "Software", _("Hay {n} paquetes con actualización pendiente.").format(n=len(upg)),
                 "Instálalas desde el Gestor de actualizaciones. Linux Mint recomienda tener antes una "
                 "instantánea de Timeshift, por si algo no va bien.", "updates")
    ctx.summary["updates"] = (_("{n} pendientes").format(n=len(upg)) if upg else "Al día") if have("apt") else ""
    if os.path.exists("/var/run/reboot-required"):
        ctx.flag("warn", "Software", "Hay actualizaciones instaladas que necesitan reiniciar el equipo para "
                 "completarse.", "Guarda tu trabajo y reinicia cuando puedas.")

    recent = []
    for line in read("/var/log/dpkg.log").splitlines()[-4000:]:
        p = line.split()
        if len(p) >= 6 and p[2] in ("install", "upgrade", "remove"):
            accion = {"install": "Instalado", "upgrade": "Actualizado", "remove": "Eliminado"}[p[2]]
            recent.append((f"{p[0]} {p[1][:5]}", accion, p[3].split(":")[0], p[5] if p[2] != "remove" else p[4]))
    recent = recent[-20:][::-1]

    running = [l.split()[0] for l in run(["systemctl", "list-units", "--type=service", "--state=running",
                                          "--no-legend", "--plain"], timeout=6).splitlines() if l.split()]
    failed = [l.split()[0] for l in run(["systemctl", "list-units", "--state=failed", "--no-legend",
                                         "--plain"], timeout=6).splitlines() if l.split()]
    for u in failed:
        ctx.flag("info", "Servicios", _("El servicio del sistema «{u}» no ha arrancado bien.").format(u=u),
                 "Muchas veces es inofensivo (por ejemplo, si necesita internet y no había conexión). Si notas "
                 "que algo no funciona, pregunta en el foro de tu distribución indicando ese nombre.", "logs")
    auto = []
    for f in sorted(glob.glob(os.path.expanduser("~/.config/autostart/*.desktop"))):
        d = keyvals(read(f))
        if d.get("Hidden", "").lower() != "true" and d.get("X-GNOME-Autostart-enabled", "true").lower() != "false":
            auto.append((d.get("Name", os.path.basename(f)), d.get("Exec", "")))

    blocks = [
        kv("Resumen", [
            ("Paquetes instalados (.deb)", len(pk) or ""),
            ("Aplicaciones Flatpak", len(fl) if have("flatpak") else ""),
            ("Actualizaciones pendientes", len(upg) if have("apt") else ""),
            ("Kernels instalados", ", ".join(kernels)),
            ("Servicios en ejecución", len(running) or ""),
            ("Servicios con fallo", ", ".join(failed) if failed else ("Ninguno" if running else "")),
        ]),
        table("Versiones de los componentes clave", ["Componente", "Versión"], versions),
        table("Actualizaciones pendientes", ["Paquete", "Instalada", "Disponible"], upg[:60], adv=True),
        table("Últimos cambios de paquetes", ["Fecha", "Acción", "Paquete", "Versión"], recent, adv=True),
        table("Aplicaciones Flatpak", ["Nombre", "Identificador", "Versión", "Origen"], fl),
        table("Programas que arrancan con tu sesión", ["Nombre", "Orden"], auto),
        table("Repositorios de software", ["Dirección", "Rama", "Componentes", "Definido en"], apt_repos(), adv=True,
              help="De dónde descarga tu sistema los programas y actualizaciones."),
    ]
    if not pk:
        blocks.append(note("Este sistema no usa paquetes .deb, así que el inventario de software es parcial."))
    return section("software", "Software", blocks)


# ─────────────────────────────── seguridad ───────────────────────────────

def sec_security(ctx):
    sb = ctx.data.get("secure_boot", secure_boot())
    ufw = ""
    if have("ufw"):
        conf = keyvals(read("/etc/ufw/ufw.conf"))
        ufw = {"yes": "ufw activado", "no": "ufw instalado pero desactivado"}.get(conf.get("ENABLED", "").lower(),
                                                                                  "ufw instalado (estado no legible sin root)")
        if conf.get("ENABLED", "").lower() == "no":
            ctx.flag("info", "Seguridad", "El cortafuegos está desactivado.",
                     "En casa, detrás del router, es habitual. Si conectas el equipo a redes públicas "
                     "(cafeterías, hoteles, estaciones), actívalo: abre el Cortafuegos y pon «Estado» en "
                     "activado; la configuración de fábrica vale para casi todo el mundo.", "firewall")
    elif run(["systemctl", "is-active", "firewalld"], timeout=3) == "active":
        ufw = "firewalld activo"
    else:
        ufw = "No se ha detectado ufw ni firewalld"
    listening = set()
    for line in run(["ss", "-H", "-tuln"], timeout=4).splitlines():
        p = line.split()
        if len(p) >= 5:
            addr, _sep, port = p[4].rpartition(":")
            if not addr.startswith(("127.", "[::1]")):
                listening.add(f"{port}/{p[0]}")
    ssh = run(["systemctl", "is-active", "ssh"], timeout=3)
    lsm = read("/sys/kernel/security/lsm")
    lock = re.search(r"\[(\w+)\]", read("/sys/kernel/security/lockdown"))
    vul = ctx.data.get("cpu_vulnerable", [])
    ctx.summary["seguridad"] = ", ".join(x for x in (
        _("Secure Boot activado") if sb is True else "",
        _("disco cifrado") if ctx.data.get("encrypted") else "",
        _("cortafuegos activo") if ufw in ("ufw activado", "firewalld activo") else "") if x)
    aslr = {"2": "Completa", "1": "Parcial", "0": "Desactivada"}.get(read("/proc/sys/kernel/randomize_va_space"), "")
    ctx.data["firewall"] = True if ufw in ("ufw activado", "firewalld activo") else \
        (False if ufw in ("ufw instalado pero desactivado", "No se ha detectado ufw ni firewalld") else None)
    hsi = ""
    if have("fwupdmgr") and have("gdbus"):      # se lee del servicio fwupd del equipo: no se envía nada
        m = re.search(r"HSI:(\d)(!?)", run(["gdbus", "call", "--system", "--dest", "org.freedesktop.fwupd",
                                           "--object-path", "/", "--method", "org.freedesktop.DBus.Properties.Get",
                                           "org.freedesktop.fwupd", "HostSecurityId"], timeout=5))
        if m:
            hsi = _("Nivel {n} de 4").format(n=m.group(1)) + (_(" (con avisos)") if m.group(2) else "")
    return section("seguridad", "Seguridad", [
        kv("Arranque y firmware", [
            ("Modo de arranque", "BIOS clásico (legacy)" if sb is None else "UEFI"),
            ("Secure Boot", {None: "No aplicable", True: "Activado", False: "Desactivado"}.get(sb, "Desconocido")),
            ("TPM", _("Versión {tpm}.x").format(tpm=ctx.data['tpm']) if ctx.data.get("tpm") else "No detectado"),
            ("Bloqueo del kernel (lockdown)", lock.group(1) if lock else ""),
            ("Seguridad del firmware (HSI)", hsi),
        ]),
        kv("Sistema", [
            ("Cifrado de disco (LUKS)", "Detectado" if ctx.data.get("encrypted") else "No detectado"),
            ("Cortafuegos", ufw),
            ("Módulos de seguridad del kernel", lsm),
            ("AppArmor", {"Y": "Activado", "N": "Desactivado"}.get(read("/sys/module/apparmor/parameters/enabled"), "")),
            ("Aleatorización de memoria (ASLR)", aslr),
            ("Servidor SSH", "En marcha" if ssh == "active" else "Parado o no instalado"),
            ("Puertos abiertos a la red", ", ".join(sorted(listening, key=natural)) if listening else "Ninguno"),
            ("Vulnerabilidades de CPU sin mitigar", ", ".join(vul) if vul else "Ninguna"),
            ("Actualizaciones pendientes", ctx.data.get("updates", "")),
        ]),
    ])


# ───────────────────────────── puesta a punto ─────────────────────────────

def timeshift_scheduled():
    """True si Timeshift tiene instantáneas programadas, False si no, None si no se puede saber.
    De su configuración solo se mira si hay disco elegido y programación; no se muestra nada de ella."""
    for path in ("/etc/timeshift/timeshift.json", "/etc/timeshift.json"):
        try:
            conf = json.loads(read(path))
        except ValueError:
            continue
        if isinstance(conf, dict):
            return bool(conf.get("backup_device_uuid")) and any(
                str(v).lower() == "true" for k, v in conf.items() if k.startswith("schedule_"))
    return None


def sec_setup(ctx):
    """Lista de comprobación de lo que conviene dejar hecho tras instalar el sistema."""
    items = []

    def add(ok, area, good, pending, todo="", action=None):
        items.append({"level": "ok" if ok else "info", "area": _(area), "text": _(good if ok else pending),
                      "todo": "" if ok else _(todo), "action": None if ok else action})

    if have("apt") and ctx.data.get("updates") is not None:
        n = ctx.data["updates"]
        add(not n, "Actualizaciones", "El sistema está al día.",
            _("Hay {n} actualizaciones pendientes.").format(n=n),
            "Abre el Gestor de actualizaciones e instálalas: corrigen fallos y problemas de seguridad.", "updates")
    if ctx.data.get("driver_updates") is not None:
        n = ctx.data["driver_updates"]
        add(not n, "Drivers y firmware", "No hay versiones nuevas de drivers ni de firmware en tus repositorios.",
            _("Hay {n} drivers o firmware con versión nueva.").format(n=n),
            "Mira la sección «Actualizaciones de drivers» y usa el Gestor de actualizaciones o el de "
            "controladores.", "drivers")
    if ctx.data.get("firewall") is not None:
        add(ctx.data["firewall"], "Cortafuegos", "El cortafuegos está activado.", "El cortafuegos no está activado.",
            "En casa, detrás del router, es habitual. Actívalo si conectas el equipo a redes públicas.", "firewall")
    if have("timeshift"):
        sched = timeshift_scheduled()
        if sched is not None:
            add(sched, "Instantáneas del sistema", "Timeshift tiene instantáneas programadas.",
                "Timeshift está instalado, pero no tiene instantáneas programadas.",
                "Abre Timeshift y sigue el asistente: una instantánea permite deshacer una actualización que "
                "salga mal. No sustituye a la copia de seguridad de tus archivos.", "snapshots")
    if ctx.data.get("trim"):
        add(ctx.data["trim"] == "enabled", "Discos SSD", "El mantenimiento periódico de los SSD (TRIM) está activado.",
            "El mantenimiento periódico de los SSD (TRIM) no está activado.",
            "Linux Mint lo trae activado de fábrica. Pregunta en el foro de tu distribución cómo volver a activarlo.")
    pk = dpkg_packages()
    if pk:
        codecs = any(n in pk for n in ("mint-meta-codecs", "ubuntu-restricted-extras", "ubuntu-restricted-addons")) \
            or any(n.startswith("libavcodec-extra") for n in pk)
        add(codecs, "Códecs multimedia", "Los códecs multimedia están instalados.",
            "No se han encontrado los códecs multimedia.",
            "Sin ellos, algunos vídeos y canciones no se reproducen. En Linux Mint, busca «Instalar códecs "
            "multimedia» en el menú.")
    hechos = sum(1 for f in items if f["level"] == "ok")
    blocks = []
    if items:
        blocks.append({"type": "status", "title": "", "level": "ok" if hechos == len(items) else "info",
                       "text": _("{n} de {m} puntos en orden").format(n=hechos, m=len(items)), "rows": [1],
                       "adv": False})
        blocks.append(findings_block("Lista de comprobación", items,
                                     help="Lo que conviene dejar hecho después de instalar el sistema. Nada de "
                                          "esto es urgente y MintMachine no cambia nada: cada punto te lleva a "
                                          "la herramienta del sistema que lo hace."))
    else:
        blocks.append(note("No se ha podido comprobar ningún punto en este sistema."))
    return section("puesta", "Puesta a punto", blocks)


# ─────────────────────── diagnóstico y resumen (derivados) ───────────────────────

# Utilidad → (paquete que la trae, qué se deja de ver sin ella)
TOOL_PKGS = collections.OrderedDict([
    ("lspci", ("pciutils", "Gráfica y dispositivos PCI")), ("lsblk", ("util-linux", "Discos y particiones")),
    ("udisksctl", ("udisks2", "Salud de los discos")), ("gdbus", ("libglib2.0-bin", "Desgaste de los SSD")),
    ("ip", ("iproute2", "Direcciones de red")), ("iw", ("iw", "Señal y banda del Wi-Fi")),
    ("glxinfo", ("mesa-utils", "Aceleración 3D")), ("vainfo", ("vainfo", "Vídeo por hardware")),
    ("vulkaninfo", ("vulkan-tools", "Vulkan")), ("fwupdmgr", ("fwupd", "Firmware de los dispositivos")),
    ("xrandr", ("x11-xserver-utils", "Modo de pantalla en X11")), ("pactl", ("pulseaudio-utils", "Servidor de sonido")),
])

LEVELS = {"bad": (0, "Problema"), "warn": (1, "Aviso"), "info": (2, "Sugerencia"), "ok": (3, "Correcto")}


def findings_block(title, items, help="", compact=False):
    """Bloque de avisos del diagnóstico: cada fila es un dict con level, area, text, todo y action.
    compact=True (Inicio): la ventana muestra solo el aviso, sin «qué hacer»."""
    rows = sorted(items, key=lambda f: LEVELS[f["level"]][0])
    for f in rows:
        f["action_label"] = _(ACTIONS[f["action"]][0]) if f.get("action") in ACTIONS and action_cmd(f["action"]) else ""
    return {"type": "findings", "title": _(title), "rows": rows, "adv": False, "help": _(help), "compact": compact}


def health(ctx):
    nb = sum(1 for f in ctx.findings if f["level"] == "bad")
    nw = sum(1 for f in ctx.findings if f["level"] == "warn")
    ni = sum(1 for f in ctx.findings if f["level"] == "info")
    if nb:
        return "bad", (_("Hay algo que necesita tu atención") if nb == 1 else
                       _("Hay {nb} cosas que necesitan tu atención").format(nb=nb))
    if nw:
        return "warn", (_("Hay un aviso que conviene revisar") if nw == 1 else
                        _("Hay {nw} avisos que conviene revisar").format(nw=nw))
    if ni > 1:
        return "ok", _("Todo en orden ({ni} sugerencias opcionales)").format(ni=ni)
    return "ok", _("Todo en orden (1 sugerencia opcional)") if ni else _("Todo en orden")


def sec_diagnosis(ctx):
    counts = collections.Counter()
    for line in run(["journalctl", "-p", "3", "-b", "-q", "--no-pager", "-o", "short", "-n", "500"],
                    timeout=10).splitlines():
        m = re.match(r"^\S+\s+\d+\s+[\d:]+\s+\S+\s+(.*)$", line)
        if m:
            counts[re.sub(r"\[\d+\]", "", m.group(1))[:200]] += 1
    log = kernel_log()
    if log["mce"]:
        ctx.flag("bad", "Hardware", _("El procesador ha notificado {mce} errores de hardware en este arranque.").format(mce=log['mce']),
                 "Pueden deberse a calor, a la memoria o a un ajuste de la BIOS fuera de fábrica. Haz una copia "
                 "de seguridad y consúltalo con un servicio técnico, sobre todo si el equipo se cuelga o se reinicia solo.",
                 "backup")
    if log["io"]:
        ctx.flag("bad", "Almacenamiento", _("Hay {io} errores de lectura o escritura de disco en el registro del kernel.").format(io=log['io']),
                 "Haz ya una copia de seguridad de tus archivos importantes. Mira el estado de los discos en la "
                 "sección Almacenamiento y, si alguno muestra avisos o los errores se repiten, llévalo a un "
                 "servicio técnico. Si el error es de un pendrive o disco USB, prueba en otro puerto o "
                 "expúlsalo siempre antes de desconectarlo.", "backup")
    if log["oom"]:
        ctx.flag("warn", "Memoria", _("El sistema se quedó sin memoria y tuvo que cerrar a la fuerza: "
                                      "{programas}.").format(programas=", ".join(sorted(set(log["oom"])))),
                 "Cierra los programas y pestañas que no uses. Si te pasa a menudo, un servicio técnico puede "
                 "decirte si tu equipo admite más memoria.", "sysmon")
    state, headline = health(ctx)
    ctx.data["health"] = (state, headline)
    blocks = [
        {"type": "status", "title": "", "level": state, "text": headline, "rows": [1], "adv": False},
        findings_block("Conviene revisar", [f for f in ctx.findings if f["level"] in ("bad", "warn")]),
        findings_block("Sugerencias", [f for f in ctx.findings if f["level"] not in ("bad", "warn")],
                       help="No son fallos: son mejoras opcionales o cosas que conviene saber."),
    ]
    if not ctx.findings:
        blocks.append(note("No se ha encontrado nada que revisar."))
    blocks += [
        table("Errores más repetidos en el registro del sistema desde el arranque",
              ["Veces", "Mensaje"], [(n, msg) for msg, n in counts.most_common(10)], adv=True,
              help="Es normal que haya mensajes de error en cualquier equipo. Solo importan si coinciden "
                   "con algo que notes que falla."),
        table("Utilidades opcionales que no están instaladas", ["Utilidad", "Paquete", "Qué se deja de ver"],
              [(t, pkg, what) for t, (pkg, what) in TOOL_PKGS.items() if t in _MISSING], adv=True,
              help="Sin ellas el programa funciona igual, pero algunos apartados salen más cortos. Se instalan "
                   "desde el Gestor de software, buscando el nombre del paquete."),
        note("Qué se revisa: espacio y salud de los discos, temperaturas, batería, memoria, servicios, errores "
             "del registro del kernel, protección del procesador, drivers y actualizaciones."),
        None if log["ok"] else note("No se ha podido leer el registro del kernel porque tu usuario no pertenece al "
                                    "grupo «adm»; esos avisos no se incluyen."),
        note(DISCLAIMER),
    ]
    return section("diagnostico", "Diagnóstico", blocks)


def live_now():
    """Barras de «Ahora mismo» del Inicio: se recalculan cada pocos segundos."""
    items = []
    with SAMPLER.lock:
        cpu = SAMPLER.h["cpu"][-1] if SAMPLER.h["cpu"] else None
        temp = SAMPLER.h["temp"][-1] if SAMPLER.h["temp"] else None
    if cpu is not None:
        items.append(("Procesador", cpu / 100, _("{cpu:.0f} % en uso").format(cpu=cpu)))
    m = meminfo()
    if m.get("MemTotal"):
        used = m["MemTotal"] - m.get("MemAvailable", 0)
        items.append(("Memoria", used / m["MemTotal"], _("{n} de {n2} en uso").format(n=human(used), n2=human(m['MemTotal']))))
    total, used, free, _ro = fs_usage("/")
    if total:
        items.append(("Disco del sistema", fs_frac(used, free), usage_text(used, total, free)))
    if temp is not None:
        items.append(("Temperatura", temp / 100, _("{temp:.0f} °C en el procesador").format(temp=temp)))
    for b in glob.glob("/sys/class/power_supply/BAT*"):
        c = read_int(b + "/capacity")
        if c is not None and read(b + "/scope") != "Device":
            st = _(STATUS.get(read(b + "/status"), read(b + "/status"))).lower()
            items.append(("Batería", c / 100, f"{c} %, {st}"))
            break
    return bars("Ahora mismo", items, gauge=True)


def sec_summary(ctx):
    s = ctx.summary
    state, headline = ctx.data.get("health", ("ok", "Todo en orden"))
    top = [f for f in sorted(ctx.findings, key=lambda f: LEVELS[f["level"]][0]) if f["level"] in ("bad", "warn")][:3]
    sec = section("resumen", "Inicio", [
        {"type": "status", "title": "", "level": state, "text": headline, "rows": [1], "adv": False},
        live_now(),
        findings_block("Lo más importante", top, compact=True) if top else None,
        kv("Equipo", [
            ("Modelo", s.get("equipo")), ("Tipo", ctx.data.get("chassis")),
            ("Placa base", s.get("placa")), ("BIOS", s.get("bios")),
            ("Procesador", s.get("cpu")), ("Memoria", s.get("ram")),
            ("Gráfica", s.get("gpu")), ("Pantalla", s.get("pantalla")),
            ("Almacenamiento", s.get("discos")), ("Salud de los discos", s.get("salud_discos")),
            ("Batería", s.get("bateria")), ("Ventiladores", s.get("fans")),
        ]),
        kv("Sistema", [
            ("Sistema operativo", s.get("os")), ("Kernel", s.get("kernel")),
            ("Escritorio", s.get("escritorio")), ("Encendido desde hace", s.get("uptime")),
            ("Actualizaciones", s.get("updates")), ("Conexión", s.get("red")),
            ("Protección", s.get("seguridad")),
        ]),
    ])
    return sec


# Barra lateral: (identificador, grupo). El grupo se muestra como encabezado.
COLLECTORS = collections.OrderedDict([
    ("monitor", sec_monitor), ("cpu", sec_cpu), ("memoria", sec_memory), ("grafica", sec_gpu),
    ("discos", sec_storage), ("placa", sec_board), ("energia", sec_power), ("sensores", sec_sensors),
    ("red", sec_network), ("audio", sec_audio), ("perifericos", sec_peripherals), ("usb", sec_usb),
    ("pci", sec_pci), ("sistema", sec_system), ("actualizaciones", sec_updates), ("drivers", sec_modules),
    ("software", sec_software), ("seguridad", sec_security), ("puesta", sec_setup),
])
GROUPS = {"cpu": "Hardware", "sistema": "Sistema y software"}     # primera sección de cada grupo
LIVE = {"resumen", "monitor", "cpu", "memoria", "sensores"}     # secciones que se refrescan solas
TITLES = {"resumen": "Inicio", "diagnostico": "Diagnóstico", "cpu": "Procesador", "placa": "Placa base y BIOS",
          "memoria": "Memoria", "grafica": "Gráfica y pantallas", "discos": "Almacenamiento", "red": "Red",
          "audio": "Sonido", "usb": "Dispositivos USB", "pci": "Dispositivos PCI",
          "sensores": "Sensores y ventiladores", "monitor": "Monitor en vivo",
          "perifericos": "Periféricos", "actualizaciones": "Actualizaciones de drivers",
          "energia": "Batería y energía", "sistema": "Sistema operativo",
          "drivers": "Drivers y módulos", "software": "Software", "seguridad": "Seguridad",
          "puesta": "Puesta a punto"}
# Orden en que se recopilan: el Diagnóstico y el Inicio usan lo que dejan los demás, y
# Seguridad usa datos de Placa base, Procesador, Almacenamiento y Software.
ORDER = ["placa", "cpu", "memoria", "grafica", "discos", "red", "audio", "usb", "pci", "perifericos",
         "sensores", "energia", "sistema", "drivers", "actualizaciones", "software", "seguridad", "puesta",
         "monitor"]


def safe(sid, fn, ctx):
    """Un recopilador que falla no debe tumbar el resto del informe."""
    try:
        return fn(ctx)
    except Exception as e:   # hardware raro, formatos inesperados...
        return section(sid, TITLES.get(sid, sid), [note(
            _("No se ha podido leer esta sección ({__name__}: {e}). Si abres una incidencia, incluye este mensaje.").format(__name__=type(e).__name__, e=e))])


def collect_all():
    clear_cache()
    _MISSING.clear()
    try:
        if getpass.getuser() != "root":
            secret(getpass.getuser())
    except Exception:
        pass
    home = os.path.expanduser("~")
    if home not in ("/", "/root"):
        secret(home)
    Sens(socket.gethostname())
    ctx = Ctx()
    done = {sid: safe(sid, COLLECTORS[sid], ctx) for sid in ORDER}
    diag = safe("diagnostico", sec_diagnosis, ctx)
    return [safe("resumen", sec_summary, ctx), diag] + [done[sid] for sid in COLLECTORS]


# ─────────────────────────────── exportadores ───────────────────────────────

def header_line(anon):
    return (_("{app} {version}: informe del {fecha}").format(app=APP, version=VERSION, fecha=when())
            + (" " + _("(datos personales ocultos)") if anon else ""))


def dispw(t):
    """Ancho en pantalla: los caracteres chinos y japoneses ocupan dos columnas."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in t)


def pad(t, w):
    return t + " " * max(0, w - dispw(t))


def to_text(sections, anon=False, header=True, brief=False):
    """brief=True: los avisos sin «qué hacer» (para foros, donde lo leen personas con experiencia)."""
    out = [header_line(anon), ""] if header else []
    sh = lambda v: show(v, anon)      # noqa: E731
    for s in sections:
        out += ["=" * 72, s["title"].upper(), "=" * 72]
        for b in s["blocks"]:
            if b["title"]:
                out += ["", f"[{b['title']}]"]
            if b["type"] == "kv":
                w = max(dispw(k) for k, _v in b["rows"])
                out += [f"  {pad(k, w)}  {sh(v)}" for k, v in b["rows"]]
            elif b["type"] == "bars":
                out += [f"  {l}: {sh(t)}" for l, _f, t in b["rows"]]
            elif b["type"] == "status":
                out += ["", "  " + _("Estado general: {estado}").format(estado=b["text"])]
            elif b["type"] == "findings":
                for f in b["rows"]:
                    out += [f"  [{_(LEVELS[f['level']][1])}] {f['area']}: {sh(f['text'])}"]
                    if f.get("todo") and not brief:
                        out += ["      " + _("Qué hacer:") + " " + sh(f["todo"])]
                    if f.get("action_label") and not brief:
                        out += ["      " + _("Herramienta:") + " " + f["action_label"]]
            elif b["type"] == "chart":
                out += ["  " + _("{serie}: ahora {ahora}, media {media}, máximo {maximo} (últimos {n} s)").format(
                    serie=l, ahora=fmt_unit(v[-1], b["unit"]), media=fmt_unit(sum(v) / len(v), b["unit"]),
                    maximo=fmt_unit(max(v), b["unit"]), n=len(v)) for l, v in b["rows"]]
            elif b["type"] == "cores":
                out += ["  " + ", ".join(_("hilo {n}: {uso} %").format(n=n, uso=f"{v:.0f}") for n, v in b["rows"])]
            elif b["type"] == "table":
                rows = [[sh(c) for c in r] for r in b["rows"]]
                w = [max([dispw(h)] + [dispw(r[i]) for r in rows]) for i, h in enumerate(b["headers"])]

                def line(r):
                    return ("  " + "  ".join(pad(c, w[i]) for i, c in enumerate(r))).rstrip()
                out += [line(b["headers"]), "  " + "  ".join("-" * x for x in w)] + [line(r) for r in rows]
            else:
                out += ["", "  " + b["text"]]
        out.append("")
    return "\n".join(out)


# Lo que va en el informe para foros: lo que suelen pedir en el foro de Linux Mint, sin el
# detalle técnico largo, para que quepa en un mensaje.
FORUM_SECTIONS = ["resumen", "diagnostico", "cpu", "memoria", "grafica", "discos", "red", "audio",
                  "energia", "sistema", "actualizaciones"]


# Para pedir ayuda con un problema concreto: la ficha del equipo y solo las secciones que un
# voluntario del foro necesita ver, con sus detalles técnicos.
FORUM_TOPICS = collections.OrderedDict([
    ("general", ("Resumen general", None)),
    ("red", ("Wi-Fi y red", ["red", "actualizaciones"])),
    ("sonido", ("Sonido", ["audio", "perifericos"])),
    ("grafica", ("Gráfica y pantallas", ["grafica", "actualizaciones"])),
    ("energia", ("Batería, suspensión y temperatura", ["energia", "sensores", "cpu"])),
    ("lentitud", ("Lentitud y arranque", ["diagnostico", "monitor", "memoria", "discos", "sistema"])),
])


def to_forum(sections, anon=True, topic="general"):
    """Texto compacto entre [code] y [/code], listo para pegar en un foro (phpBB, como el de Linux Mint)."""
    keep = []
    ids = {s["id"] for s in sections}
    name, wanted = FORUM_TOPICS.get(topic) or FORUM_TOPICS["general"]
    focused = bool(wanted) and len(ids) > 1
    for s in sections:
        if len(ids) > 1 and s["id"] not in ((["resumen"] + wanted) if focused else FORUM_SECTIONS):
            continue
        detail = focused and s["id"] != "resumen"          # en la sección del problema, también lo técnico
        blocks = [b for b in s["blocks"] if (detail or not b.get("adv")) and b["type"] not in ("note", "chart", "cores")]
        if s["id"] == "resumen":
            blocks = [b for b in blocks if b["type"] not in ("findings", "bars")]
        elif s["id"] == "red" and not focused:
            blocks = [b for b in blocks if b["type"] != "table"]       # interfaces: demasiado ancho
        elif s["id"] in ("diagnostico",):
            blocks = [b for b in blocks if b["type"] != "status"]
        keep.append(dict(s, blocks=blocks))
    if focused:
        keep.sort(key=lambda s: (["resumen"] + wanted).index(s["id"]))
    body = to_text(keep, anon, header=False, brief=True)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    head = header_line(anon) + ("\n" + _("Problema: {tema}").format(tema=_(name)) if focused else "")
    return f"[code]\n{head}\n\n{body}\n[/code]\n"


def to_csv(_sections=None, anon=False):
    """Histórico del Monitor en vivo: una fila por segundo, la más reciente al final."""
    cols = [("cpu", "procesador_%"), ("ram", "ram_%"), ("swap", "swap_%"), ("rx", "red_bajada_B_s"),
            ("tx", "red_subida_B_s"), ("dread", "disco_lectura_B_s"), ("dwrite", "disco_escritura_B_s"),
            ("temp", "temperatura_cpu_C"), ("gpu", "grafica_%"), ("igpu", "grafica_intel_%")]
    with SAMPLER.lock:
        data = {k: list(SAMPLER.h[k]) for k, _n in cols}
    n = max((len(v) for v in data.values()), default=0)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")          # punto y coma y coma decimal: lo que espera una hoja en español
    w.writerow(["segundos_antes_de_ahora"] + [name for _k, name in cols])
    for i in range(n):
        back = n - 1 - i
        row = [back]
        for k, _name in cols:
            v = data[k]
            j = len(v) - 1 - back
            row.append(num(v[j], 2) if 0 <= j < len(v) else "")
        w.writerow(row)
    return buf.getvalue()


def to_json(sections, anon=False):
    data = []
    for s in sections:
        blocks = []
        for b in s["blocks"]:
            nb = dict(b)
            if b["type"] == "kv":
                nb["rows"] = [[k, show(v, anon)] for k, v in b["rows"]]
            elif b["type"] == "table":
                nb["rows"] = [[show(c, anon) for c in r] for r in b["rows"]]
            elif b["type"] == "bars":
                nb["rows"] = [[l, round(f, 4), show(t, anon)] for l, f, t in b["rows"]]
            elif b["type"] == "findings":
                nb["rows"] = [{"nivel": f["level"], "area": f["area"], "texto": show(f["text"], anon),
                               "que_hacer": show(f.get("todo", ""), anon), "herramienta": f.get("action_label", "")}
                              for f in b["rows"]]
            elif b["type"] == "status":
                nb.pop("rows", None)
            nb = {k: v for k, v in nb.items() if v not in ("", None) or k in ("title", "type")}
            blocks.append(nb)
        data.append({"id": s["id"], "title": s["title"], "blocks": blocks})
    return json.dumps({"programa": APP, "version": VERSION, "esquema": JSON_SCHEMA, "autor": AUTHOR_FULL,
                       "fecha": datetime.datetime.now().isoformat(timespec="seconds"),
                       "datos_ocultos": bool(anon), "secciones": data}, ensure_ascii=False, indent=2)


HTML_CSS = """
:root{--bg:#f6f7f8;--card:#fff;--fg:#1d2327;--dim:#5f6b73;--line:#dfe3e6;--acc:#2f7d5b}
@media (prefers-color-scheme:dark){:root{--bg:#1b1e20;--card:#25292c;--fg:#e8eaeb;--dim:#9aa5ac;--line:#363c40;--acc:#6cc39a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,"Noto Sans","DejaVu Sans",sans-serif}
nav{position:fixed;top:0;bottom:0;left:0;width:210px;overflow:auto;padding:20px 0;border-right:1px solid var(--line);background:var(--card)}
nav b{display:block;padding:0 20px 12px;font-size:17px}nav a{display:block;padding:6px 20px;color:var(--fg);text-decoration:none}
nav a:hover{color:var(--acc)}main{margin-left:210px;padding:28px 36px;max-width:1150px}
h2{margin:36px 0 6px;font-size:22px;border-bottom:2px solid var(--acc);padding-bottom:6px}h2:first-child{margin-top:0}
h3{margin:22px 0 8px;font-size:15px;color:var(--dim);font-weight:600}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:6px}
table{border-collapse:collapse;width:100%}td,th{padding:6px 12px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:0}th{font-weight:600;color:var(--dim);white-space:nowrap}td.k{color:var(--dim);width:32%}
.bar{height:9px;border-radius:5px;background:var(--line);min-width:160px}.bar i{display:block;height:100%;border-radius:5px;background:var(--acc)}
p.note{color:var(--dim);max-width:75ch}footer{margin:40px 0 10px;color:var(--dim);font-size:13px}
.st{padding:14px 18px;border-radius:6px;font-size:17px;font-weight:600;border:1px solid var(--line);background:var(--card)}
.st.bad{border-left:6px solid #c0392b}.st.warn{border-left:6px solid #d68910}.st.ok,.st.info{border-left:6px solid var(--acc)}
.f{padding:10px 14px;border-bottom:1px solid var(--line)}.f:last-child{border-bottom:0}.f p{margin:4px 0 0;color:var(--dim)}
.b{display:inline-block;font-size:12px;font-weight:700;padding:1px 8px;border-radius:9px;margin-right:6px;color:#fff;background:#5f6b73}
.b.bad{background:#c0392b}.b.warn{background:#b9770e}.b.info{background:#2e6da4}.b.ok{background:#2e8b57}
details{margin-top:18px}summary{cursor:pointer;color:var(--dim);font-weight:600}
@media (max-width:760px){nav{display:none}main{margin:0;padding:18px}}
"""


def to_html(sections, anon=False):
    e = html.escape
    nav = "".join(f'<a href="#{s["id"]}">{e(s["title"])}</a>' for s in sections)
    body = []
    for s in sections:
        body.append(f'<h2 id="{s["id"]}">{e(s["title"])}</h2>')
        adv_open = False
        for b in s["blocks"]:
            if b.get("adv") and not adv_open:
                body.append(f"<details><summary>{e(_('Detalles técnicos'))}</summary>")
                adv_open = True
            if b["title"]:
                body.append(f"<h3>{e(b['title'])}</h3>")
            if b.get("help"):
                body.append(f'<p class="note">{e(b["help"])}</p>')
            if b["type"] == "status":
                body.append(f'<div class="st {b["level"]}">{e(b["text"])}</div>')
            elif b["type"] == "findings":
                items = "".join(
                    f'<div class="f"><span class="b {f["level"]}">{e(_(LEVELS[f["level"]][1]))}</span>'
                    f'<b>{e(f["area"])}:</b> {e(show(f["text"], anon))}'
                    + (f'<p>{e(_("Qué hacer:"))} {e(show(f["todo"], anon))}</p>' if f.get("todo") else "")
                    + (f'<p>{e(_("Herramienta:"))} {e(f["action_label"])}</p>' if f.get("action_label") else "")
                    + "</div>"
                    for f in b["rows"])
                body.append(f'<div class="wrap">{items}</div>')
            elif b["type"] == "kv":
                rows = "".join(f'<tr><td class="k">{e(k)}</td><td>{e(show(v, anon))}</td></tr>' for k, v in b["rows"])
                body.append(f'<div class="wrap"><table>{rows}</table></div>')
            elif b["type"] == "bars":
                rows = "".join(f'<tr><td class="k">{e(l)}</td><td><div class="bar"><i style="width:{f * 100:.0f}%"></i></div></td>'
                               f"<td>{e(show(t, anon))}</td></tr>" for l, f, t in b["rows"])
                body.append(f'<div class="wrap"><table>{rows}</table></div>')
            elif b["type"] == "chart":
                rows = ""
                for l, v in b["rows"]:
                    top = 100.0 if b["unit"] == "%" else max(max(v), 1e-9)
                    pts = " ".join(f"{i * 240 / max(len(v) - 1, 1):.1f},{38 - min(x / top, 1) * 36:.1f}"
                                   for i, x in enumerate(v))
                    rows += (f'<tr><td class="k">{e(l)}</td><td><svg width="240" height="40" viewBox="0 0 240 40">'
                             f'<polyline points="{pts}" fill="none" stroke="var(--acc)" stroke-width="1.6"/></svg></td>'
                             "<td>" + e(_("ahora {ahora}, media {media}, máximo {maximo}").format(
                                 ahora=fmt_unit(v[-1], b["unit"]), media=fmt_unit(sum(v) / len(v), b["unit"]),
                                 maximo=fmt_unit(max(v), b["unit"]))) + "</td></tr>")
                body.append(f'<div class="wrap"><table>{rows}</table></div>')
            elif b["type"] == "cores":
                rows = "".join(f'<tr><td class="k">{e(_("Hilo {n}").format(n=n))}</td><td><div class="bar"><i style="width:{v:.0f}%"></i></div></td>'
                               f"<td>{v:.0f} %</td></tr>" for n, v in b["rows"])
                body.append(f'<div class="wrap"><table>{rows}</table></div>')
            elif b["type"] == "table":
                head = "".join(f"<th>{e(h)}</th>" for h in b["headers"])
                rows = "".join("<tr>" + "".join(f"<td>{e(show(c, anon))}</td>" for c in r) + "</tr>" for r in b["rows"])
                body.append(f'<div class="wrap"><table><tr>{head}</tr>{rows}</table></div>')
            else:
                body.append(f'<p class="note">{e(b["text"])}</p>')
        if adv_open:
            body.append("</details>")
    foot = _("Informe generado con {app} {version} el {fecha}.").format(app=APP, version=VERSION, fecha=when())
    if anon:
        foot += " " + _("Los datos personales se han ocultado.")
    return (f'<!doctype html><html lang="{_LANG[0]}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{e(_('{app}: informe del sistema').format(app=APP))}</title><style>{HTML_CSS}</style></head><body>"
            f"<nav><b>{APP}</b>{nav}</nav><main>{''.join(body)}"
            f"<footer>{e(foot)}<br>{e(_(DISCLAIMER))}</footer></main></body></html>")


# formato: (exportador, extensión, nombre para el usuario, explicación)
EXPORTERS = collections.OrderedDict([
    ("txt", (to_text, "txt", "Texto", "Para leerlo o adjuntarlo a un correo")),
    ("html", (to_html, "html", "Página web", "Se abre en el navegador; cómoda para enviar a un técnico")),
    ("foro", (to_forum, "txt", "Para un foro", "Resumen listo para pegar en el foro de Linux Mint")),
    ("json", (to_json, "json", "JSON", "Datos estructurados para otros programas")),
    ("csv", (to_csv, "csv", "Histórico del monitor (CSV)", "Gráficas de los últimos 2 minutos, para una hoja de cálculo")),
])


def export(fmt, sections, anon, topic=None):
    if fmt == "foro" and topic:
        return to_forum(sections, anon, topic)
    return EXPORTERS[fmt][0](sections, anon)


# ─────────────────────────────── interfaz GTK ───────────────────────────────

LEVEL_ICONS = {"bad": "dialog-error-symbolic", "warn": "dialog-warning-symbolic",
               "info": "dialog-information-symbolic", "ok": "emblem-ok-symbolic"}

SECTION_ICONS = {
    "resumen": ["go-home-symbolic", "user-home-symbolic"],
    "diagnostico": ["emblem-ok-symbolic", "object-select-symbolic", "dialog-information-symbolic"],
    "monitor": ["utilities-system-monitor-symbolic", "org.gnome.SystemMonitor-symbolic", "view-statistics-symbolic"],
    "cpu": ["cpu-symbolic", "computer-chip-symbolic", "processor-symbolic", "system-run-symbolic"],
    "memoria": ["memory-symbolic", "media-flash-symbolic", "drive-removable-media-symbolic"],
    "grafica": ["video-display-symbolic", "display-symbolic"],
    "discos": ["drive-harddisk-symbolic", "drive-harddisk"],
    "placa": ["computer-symbolic"],
    "energia": ["battery-full-symbolic", "battery-symbolic", "ac-adapter-symbolic"],
    "sensores": ["temperature-symbolic", "sensors-temperature-symbolic", "weather-clear-symbolic"],
    "red": ["network-wired-symbolic", "network-wireless-symbolic", "network-workgroup-symbolic"],
    "audio": ["audio-speakers-symbolic", "audio-volume-high-symbolic"],
    "perifericos": ["input-keyboard-symbolic", "input-mouse-symbolic"],
    "usb": ["media-removable-symbolic", "drive-removable-media-symbolic"],
    "pci": ["application-x-firmware-symbolic", "preferences-system-symbolic", "emblem-system-symbolic"],
    "sistema": ["emblem-system-symbolic", "preferences-system-symbolic"],
    "actualizaciones": ["software-update-available-symbolic", "view-refresh-symbolic"],
    "drivers": ["system-run-symbolic", "application-x-executable-symbolic"],
    "software": ["system-software-install-symbolic", "application-x-addon-symbolic", "view-app-grid-symbolic"],
    "seguridad": ["security-high-symbolic", "channel-secure-symbolic", "changes-prevent-symbolic"],
    "puesta": ["emblem-default-symbolic", "object-select-symbolic", "emblem-ok-symbolic"],
}

PALETTES = {
    "oscuro": dict(bg="#0b0e14", side="#0e121a", card="#131824", card2="#171d2b", fg="#e7eaf2", dim="#8a93a8",
                   line="rgba(255,255,255,0.07)", a1="#22d3ee", a2="#8b5cf6", ok="#34d399", warn="#fbbf24",
                   bad="#f87171", info="#60a5fa"),
    "claro": dict(bg="#dde1e8", side="#d4d9e1", card="#e8ebf0", card2="#e2e6ec", fg="#111827", dim="#4a5366",
                  line="rgba(15,23,42,0.12)", a1="#0891b2", a2="#7c3aed", ok="#059669", warn="#d97706",
                  bad="#dc2626", info="#2563eb"),
}

CSS = """
@define-color mm_bg {bg}; @define-color mm_side {side}; @define-color mm_card {card}; @define-color mm_card2 {card2};
@define-color mm_fg {fg}; @define-color mm_dim {dim}; @define-color mm_line {line};
@define-color mm_a1 {a1}; @define-color mm_a2 {a2}; @define-color mm_ok {ok}; @define-color mm_warn {warn};
@define-color mm_bad {bad}; @define-color mm_info {info};

.mm-win {{ background-color: @mm_bg; color: @mm_fg; }}
.mm-win headerbar {{ background-color: @mm_bg; background-image: none; background-clip: border-box; border: none;
    border-bottom: 1px solid mix(@mm_bg, @mm_fg, 0.08); box-shadow: none; color: @mm_fg; padding: 6px 10px;
    min-height: 44px; }}
.mm-win headerbar .title {{ font-weight: 700; color: @mm_fg; }}
.mm-win headerbar .subtitle {{ color: @mm_dim; }}
.mm-win headerbar button, .mm-win button.mm-ghost {{ background-color: alpha(@mm_fg, 0.06); background-image: none;
    border: 1px solid @mm_line; border-radius: 10px; color: @mm_fg; box-shadow: none; text-shadow: none;
    -gtk-icon-shadow: none; padding: 5px 12px; }}
.mm-win headerbar button:hover, .mm-win button.mm-ghost:hover {{ background-color: alpha(@mm_fg, 0.12); }}
.mm-win headerbar button.titlebutton {{ background: none; border: none; padding: 4px; }}
.mm-win headerbar button.titlebutton:hover {{ background-color: alpha(@mm_fg, 0.10); border-radius: 99px; }}
.mm-win button.mm-accent, .mm-win headerbar button.mm-accent {{
    background-image: linear-gradient(110deg, @mm_a1, @mm_a2); background-color: @mm_a2; color: #ffffff;
    border: none; font-weight: 700; border-radius: 10px; padding: 5px 16px; }}
.mm-win button.mm-accent:hover {{ background-image: linear-gradient(110deg, shade(@mm_a1, 1.12), shade(@mm_a2, 1.12)); }}
.mm-win button.mm-accent:checked {{ background-image: linear-gradient(110deg, shade(@mm_a1, 0.9), shade(@mm_a2, 0.9)); }}
.mm-side {{ background-color: @mm_side; border-right: 1px solid @mm_line; }}
.mm-brand {{ font-size: 17px; font-weight: 800; color: @mm_fg; }}
.mm-by {{ font-size: 11px; font-weight: 400; color: @mm_dim; }}
.mm-nav, .mm-nav row {{ background-color: transparent; }}
.mm-nav row {{ border-radius: 10px; margin: 1px 10px; padding: 6px 10px; color: @mm_dim; }}
.mm-nav row:hover {{ background-color: alpha(@mm_fg, 0.05); color: @mm_fg; }}
.mm-nav row:selected {{ background-image: linear-gradient(90deg, alpha(@mm_a1, 0.22), alpha(@mm_a2, 0.16));
    color: @mm_fg; }}
.mm-nav row:selected image {{ color: @mm_a1; }}
.mm-badge {{ background-image: linear-gradient(110deg, @mm_warn, shade(@mm_warn, 0.85)); color: #1a1205;
    border-radius: 99px; padding: 0 7px; font-size: 11px; font-weight: 800; }}
.mm-badge-bad {{ background-image: linear-gradient(110deg, @mm_bad, shade(@mm_bad, 0.85)); color: #ffffff; }}
.mm-group {{ font-size: 10px; font-weight: 800; color: alpha(@mm_dim, 0.8); padding: 16px 22px 6px 22px;
    letter-spacing: 1.5px; }}
.mm-win entry {{ background-color: alpha(@mm_fg, 0.05); background-image: none; border: 1px solid @mm_line;
    border-radius: 10px; color: @mm_fg; box-shadow: none; caret-color: @mm_a1; min-height: 32px; }}
.mm-win entry:focus {{ border-color: alpha(@mm_a1, 0.7); box-shadow: 0 0 0 3px alpha(@mm_a1, 0.15); }}
.mm-win entry image {{ color: @mm_dim; }}
.mm-win scrolledwindow, .mm-win viewport, .mm-win stack {{ background-color: transparent; }}
.mm-win scrollbar {{ background-color: transparent; border: none; }}
.mm-win scrolledwindow undershoot.top, .mm-win scrolledwindow undershoot.bottom,
.mm-win scrolledwindow undershoot.left, .mm-win scrolledwindow undershoot.right,
.mm-win scrolledwindow overshoot.top, .mm-win scrolledwindow overshoot.bottom,
.mm-win scrolledwindow overshoot.left, .mm-win scrolledwindow overshoot.right {{
    background: none; background-image: none; background-color: transparent; border: none; box-shadow: none; }}
.mm-win scrollbar slider {{ background-color: alpha(@mm_fg, 0.18); border-radius: 99px; min-width: 6px;
    min-height: 6px; border: none; }}
.mm-win scrollbar slider:hover {{ background-color: alpha(@mm_fg, 0.32); }}
.mm-win separator {{ background-color: @mm_line; min-height: 1px; min-width: 1px; }}
.mm-heading {{ font-size: 28px; font-weight: 300; color: @mm_fg; }}
.mm-kicker {{ font-size: 11px; font-weight: 800; letter-spacing: 1.5px; color: @mm_a1; }}
.mm-title {{ font-size: 11px; font-weight: 800; letter-spacing: 1.3px; color: @mm_dim; }}
.mm-dim {{ color: @mm_dim; }}
.mm-key {{ color: @mm_dim; }}
.mm-val {{ color: @mm_fg; }}
.mm-card {{ background-color: @mm_card; border: 1px solid @mm_line; border-radius: 16px; }}
.mm-hero {{ border-radius: 18px; border: 1px solid @mm_line; background-color: @mm_card;
    background-image: linear-gradient(115deg, alpha(@mm_ok, 0.18), alpha(@mm_a1, 0.06) 55%, alpha(@mm_a2, 0.10)); }}
.mm-hero.warn {{ background-image: linear-gradient(115deg, alpha(@mm_warn, 0.20), alpha(@mm_a2, 0.06) 60%, alpha(@mm_a2, 0.10)); }}
.mm-hero.bad {{ background-image: linear-gradient(115deg, alpha(@mm_bad, 0.22), alpha(@mm_a2, 0.06) 60%, alpha(@mm_a2, 0.10)); }}
.mm-hero-title {{ font-size: 20px; font-weight: 700; color: @mm_fg; }}
.mm-ring {{ border-radius: 99px; min-width: 52px; min-height: 52px; background-color: alpha(@mm_ok, 0.16); color: @mm_ok; }}
.mm-ring.warn {{ background-color: alpha(@mm_warn, 0.16); color: @mm_warn; }}
.mm-ring.bad {{ background-color: alpha(@mm_bad, 0.16); color: @mm_bad; }}
.mm-ring.info {{ background-color: alpha(@mm_info, 0.16); color: @mm_info; }}
.mm-ic-bad {{ color: @mm_bad; }} .mm-ic-warn {{ color: @mm_warn; }} .mm-ic-info {{ color: @mm_info; }} .mm-ic-ok {{ color: @mm_ok; }}
.mm-finding {{ padding: 14px 16px; }}
.mm-finding-area {{ font-weight: 700; color: @mm_fg; }}
.mm-win treeview.view {{ background-color: @mm_card; color: @mm_fg; border-color: @mm_line; }}
.mm-win treeview.view:hover {{ background-color: alpha(@mm_fg, 0.03); }}
.mm-win treeview.view header button {{ background-color: @mm_card; background-image: none; color: @mm_dim;
    border: none; border-bottom: 1px solid @mm_line; box-shadow: none; font-weight: 700; padding: 8px 8px; }}
.mm-win progressbar trough {{ background-color: alpha(@mm_fg, 0.08); background-image: none; border: none;
    min-height: 6px; border-radius: 99px; }}
.mm-win progressbar progress {{ background-image: linear-gradient(90deg, @mm_a1, @mm_a2); border: none;
    border-radius: 99px; min-height: 6px; }}
.mm-win expander title {{ color: @mm_dim; font-weight: 700; }}
.mm-win expander title:hover {{ color: @mm_fg; }}
.mm-toast {{ background-color: @mm_card2; border: 1px solid @mm_line; border-radius: 14px; padding: 10px 14px;
    color: @mm_fg; box-shadow: 0 8px 30px alpha(black, 0.35); margin: 18px; }}
popover.mm-pop {{ background-color: @mm_card; border: 1px solid @mm_line; border-radius: 16px; color: @mm_fg;
    box-shadow: 0 12px 40px alpha(black, 0.35); }}
popover.mm-pop label {{ color: @mm_fg; }}
popover.mm-pop .mm-dim {{ color: @mm_dim; }}
popover.mm-pop button.flat, popover.mm-pop modelbutton {{ color: @mm_fg; border-radius: 8px; }}
popover.mm-pop combobox button {{ background-color: alpha(@mm_fg, 0.06); background-image: none; color: @mm_fg;
    border: 1px solid @mm_line; border-radius: 8px; box-shadow: none; }}
popover.mm-pop button.mm-ghost {{ background-color: alpha(@mm_fg, 0.06); background-image: none;
    border: 1px solid @mm_line; border-radius: 10px; color: @mm_fg; box-shadow: none; }}
popover.mm-pop button.mm-accent {{ background-image: linear-gradient(110deg, @mm_a1, @mm_a2); color: #ffffff;
    border: none; font-weight: 700; border-radius: 10px; }}
popover.mm-pop button.mm-danger {{ color: @mm_bad; }}
.mm-chip {{ font-size: 11px; color: @mm_dim; }}
"""


def draw_icon(cr, sid, color):
    """Iconos de línea de la barra lateral, dibujados en una rejilla de 18 × 18 con cairo."""
    import math
    cr.set_source_rgba(*color)
    cr.set_line_width(1.6)
    cr.set_line_cap(1)          # redondeado
    cr.set_line_join(1)

    def rr(x, y, w, h, r=2.5):
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
        cr.close_path()

    def line(*pts):
        cr.move_to(*pts[0])
        for p in pts[1:]:
            cr.line_to(*p)

    def dot(x, y, r=1.2):
        cr.new_sub_path()
        cr.arc(x, y, r, 0, 2 * math.pi)
        cr.fill()
    if sid == "resumen":
        line((2.5, 8.5), (9, 3), (15.5, 8.5))
        line((4.5, 7.5), (4.5, 15), (13.5, 15), (13.5, 7.5))
        line((7.5, 15), (7.5, 11), (10.5, 11), (10.5, 15))
    elif sid == "diagnostico":
        line((9, 2.5), (15, 4.8), (15, 9), (9, 15.5), (3, 9), (3, 4.8), (9, 2.5))
        cr.close_path()
        cr.stroke()
        line((6, 9), (8.3, 11.2), (12.2, 7))
    elif sid == "monitor":
        rr(2, 3, 14, 12)
        cr.stroke()
        line((4.5, 10), (6.8, 10), (8.2, 6.5), (10, 12.5), (11.4, 9), (13.5, 9))
    elif sid == "cpu":
        rr(5, 5, 8, 8, 1.5)
        cr.stroke()
        for k in (7, 9, 11):
            line((k, 2.5), (k, 4.5))
            line((k, 13.5), (k, 15.5))
            line((2.5, k), (4.5, k))
            line((13.5, k), (15.5, k))
        cr.stroke()
        rr(7.5, 7.5, 3, 3, 0.8)
        cr.fill()
        return
    elif sid == "memoria":
        rr(2, 5, 14, 7, 1.5)
        cr.stroke()
        for k in (4.5, 7.5, 10.5):
            cr.rectangle(k, 7, 2, 3)
        cr.fill()
        for k in (4, 7, 10, 13):
            line((k, 12), (k, 14))
    elif sid == "grafica":
        rr(2, 3, 14, 9.5)
        cr.stroke()
        line((9, 12.5), (9, 15))
        line((6, 15.2), (12, 15.2))
    elif sid == "discos":
        rr(2.5, 4, 13, 10)
        cr.stroke()
        line((5, 11), (9, 11))
        cr.stroke()
        dot(12.5, 11)
        return
    elif sid == "placa":
        rr(2.5, 2.5, 13, 13)
        cr.stroke()
        rr(5.5, 5.5, 4, 4, 1)
        cr.stroke()
        line((9.5, 7.5), (12.5, 7.5), (12.5, 12.5))
        line((5.5, 12.5), (9.5, 12.5))
    elif sid == "energia":
        rr(2, 5.5, 12.5, 7.5, 1.8)
        cr.stroke()
        line((16, 8), (16, 10.5))
        cr.stroke()
        line((8.8, 6.8), (6.6, 9.6), (9.6, 9.6), (7.6, 11.9))
    elif sid == "sensores":
        cr.arc(9, 13, 2.8, -1.1, math.pi + 1.1)
        line((7.6, 10.6), (7.6, 4))
        cr.arc(9, 4, 1.4, math.pi, 0)
        line((10.4, 4), (10.4, 10.6))
        cr.stroke()
        dot(9, 13, 1.3)
        line((9, 12), (9, 7))
    elif sid == "red":
        for r_ in (3.2, 6.4, 9.6):
            cr.new_sub_path()
            cr.arc(9, 15, r_, math.pi * 1.25, math.pi * 1.75)
        cr.stroke()
        dot(9, 15, 1.3)
        return
    elif sid == "audio":
        line((3, 7), (6, 7), (9.5, 4), (9.5, 14), (6, 11), (3, 11))
        cr.close_path()
        cr.stroke()
        cr.arc(10, 9, 3, -0.7, 0.7)
        cr.stroke()
        cr.arc(10, 9, 5.6, -0.8, 0.8)
    elif sid == "perifericos":
        rr(1.5, 5, 15, 8.5, 2)
        cr.stroke()
        for x in (4.5, 7.5, 10.5, 13.5):
            dot(x, 7.8, 0.9)
        line((5.5, 10.8), (12.5, 10.8))
    elif sid == "usb":
        line((9, 15.5), (9, 3.5))
        line((7, 5.5), (9, 3.2), (11, 5.5))
        line((9, 11), (5, 8.5), (5, 7))
        line((9, 9.5), (13, 7.5), (13, 6.5))
        cr.stroke()
        dot(9, 15.5, 1.4)
        dot(5, 6.5, 1.2)
        cr.rectangle(12, 5, 2, 2)
        cr.fill()
        return
    elif sid == "pci":
        rr(2, 4, 14, 8, 1.5)
        cr.stroke()
        rr(4.5, 6, 5, 4, 0.8)
        cr.stroke()
        for x in (5, 7, 9, 11, 13):
            line((x, 12), (x, 14.5))
    elif sid == "sistema":
        cr.arc(9, 9, 3, 0, 2 * math.pi)
        cr.stroke()
        for k in range(8):
            a = k * math.pi / 4
            line((9 + 5 * math.cos(a), 9 + 5 * math.sin(a)), (9 + 7 * math.cos(a), 9 + 7 * math.sin(a)))
    elif sid == "actualizaciones":
        cr.arc(9, 9, 6, -math.pi * 0.35, math.pi * 1.25)
        cr.stroke()
        line((13.5, 2.5), (13.9, 5.7), (10.7, 5.9))
        cr.stroke()
        line((9, 6), (9, 11))
        line((6.8, 9), (9, 11.2), (11.2, 9))
    elif sid == "drivers":
        line((9, 2.5), (15.5, 6), (9, 9.5), (2.5, 6), (9, 2.5))
        cr.close_path()
        cr.stroke()
        line((2.5, 9), (9, 12.5), (15.5, 9))
        line((2.5, 12), (9, 15.5), (15.5, 12))
    elif sid == "software":
        for x, y in ((2.5, 2.5), (10, 2.5), (2.5, 10), (10, 10)):
            rr(x, y, 5.5, 5.5, 1.5)
    elif sid == "seguridad":
        rr(3.5, 8, 11, 8, 2)
        cr.stroke()
        cr.arc(9, 8, 3.5, math.pi, 0)
        cr.stroke()
        dot(9, 12, 1.3)
        return
    elif sid == "puesta":
        for y in (4.5, 9, 13.5):
            line((2.5, y), (3.8, y + 1.3), (6, y - 1.5))
            line((8.5, y), (15.5, y))
    else:
        dot(9, 9, 2)
        return
    cr.stroke()


def draw_logo(cr, size, c1, c2):
    """Marca de MintMachine: chip con un pulso, en degradado."""
    import math
    import cairo
    s = size / 28.0
    cr.scale(s, s)
    g = cairo.LinearGradient(0, 0, 28, 28)
    g.add_color_stop_rgb(0, *c1)
    g.add_color_stop_rgb(1, *c2)
    r = 7
    cr.new_sub_path()
    cr.arc(28 - r, r, r, -math.pi / 2, 0)
    cr.arc(28 - r, 28 - r, r, 0, math.pi / 2)
    cr.arc(r, 28 - r, r, math.pi / 2, math.pi)
    cr.arc(r, r, r, math.pi, 1.5 * math.pi)
    cr.close_path()
    cr.set_source(g)
    cr.fill()
    cr.set_source_rgb(1, 1, 1)
    cr.set_line_width(2.2)
    cr.set_line_cap(1)
    cr.set_line_join(1)
    for x, y in ((6, 15), (10, 15), (12, 9), (15.5, 20), (18, 13), (19.5, 15), (22, 15)):
        cr.line_to(x, y)
    cr.stroke()


def uninstall_cmd():
    """Orden para quitar el paquete, o None si MintMachine no está instalado con apt/dpkg."""
    if "install ok installed" not in run(["dpkg-query", "-W", "-f", "${Status}", "mintmachine"], timeout=5):
        return None
    return ["pkexec", "apt-get", "purge", "-y", "mintmachine"]


def remove_user_data():
    """Lo único que MintMachine guarda en la carpeta personal: su configuración."""
    shutil.rmtree(os.path.dirname(CONFIG), ignore_errors=True)


def run_gui(anon=False, screenshot=None, start=None, delay=3500):
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gdk, GLib, Pango
    try:                       # dibujar con cairo necesita el paquete python3-gi-cairo
        gi.require_foreign("cairo")
        import cairo
        can_draw = True
    except Exception:
        can_draw = False

    screen = Gdk.Screen.get_default()
    theme = Gtk.IconTheme.get_default()
    css_provider = Gtk.CssProvider()
    Gtk.StyleContext.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    state = {"tema": load_config().get("tema", "oscuro")}

    def apply_theme():
        pal = PALETTES.get(state["tema"], PALETTES["oscuro"])
        css_provider.load_from_data(CSS.format(**pal).encode())
        Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", state["tema"] == "oscuro")
    apply_theme()

    def rgb(name):
        h = PALETTES.get(state["tema"], PALETTES["oscuro"])[name].lstrip("#")
        return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def icon(names, size=Gtk.IconSize.BUTTON):
        names = [names] if isinstance(names, str) else names
        fallback = {"emblem-ok-symbolic": "object-select-symbolic"}
        for n in list(names) + [fallback.get(names[0], "")]:
            if n and theme.has_icon(n):
                return Gtk.Image.new_from_icon_name(n, size)
        img = Gtk.Image()
        img.set_size_request(16, 16)
        return img

    def label(text, cls=None, wrap=False, markup=False, xalign=0, selectable=False):
        lab = Gtk.Label(xalign=xalign)
        lab.set_markup(text) if markup else lab.set_text(text)
        if cls:
            for c in cls.split():
                lab.get_style_context().add_class(c)
        if wrap:
            lab.set_line_wrap(True)
            lab.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            lab.set_max_width_chars(95)
        if selectable:
            lab.set_selectable(True)
        return lab

    def styled(widget, *classes):
        for c in classes:
            widget.get_style_context().add_class(c)
        return widget

    class Window(Gtk.Window):
        def __init__(self):
            super().__init__(title=APP)
            styled(self, "mm-win")
            self.set_default_size(1180, 760)
            self.set_icon_name("mintmachine" if theme.has_icon("mintmachine") else "computer")
            self.anon, self.sections, self.refs, self.busy = anon, [], {}, False
            self.index, self.first, self._building = {}, True, None

            hb = Gtk.HeaderBar(show_close_button=True, title=APP)
            self.set_titlebar(hb)
            self.hb = hb
            self.btn_refresh = styled(Gtk.Button(), "mm-ghost")
            self.btn_refresh.add(icon("view-refresh-symbolic"))
            hb.pack_start(self.btn_refresh)
            self.btn_refresh.connect("clicked", lambda *_a: self.reload())
            self.spinner = Gtk.Spinner()
            hb.pack_start(self.spinner)
            self.menu_btn = Gtk.MenuButton()
            self.menu_btn.add(icon("open-menu-symbolic"))
            self.menu_pop = styled(Gtk.Popover(), "mm-pop")
            self.menu_pop.connect("show", self.fill_menu)
            self.menu_btn.set_popover(self.menu_pop)
            hb.pack_end(self.menu_btn)
            self.export_btn = styled(Gtk.MenuButton(), "mm-accent")
            self.export_btn.set_sensitive(False)
            self.export_pop = styled(Gtk.Popover(), "mm-pop")
            self.export_pop.connect("show", self.fill_export)
            self.export_btn.set_popover(self.export_pop)
            hb.pack_end(self.export_btn)

            # barra lateral
            side = styled(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), "mm-side")
            side.set_size_request(250, -1)
            brand = Gtk.Box(spacing=10, margin_start=20, margin_end=16, margin_top=18, margin_bottom=14)
            if can_draw:
                logo = Gtk.DrawingArea()
                logo.set_size_request(28, 28)
                logo.set_valign(Gtk.Align.CENTER)
                logo.connect("draw", lambda _w, cr: draw_logo(cr, 28, rgb("a1"), rgb("a2")))
                brand.pack_start(logo, False, False, 0)
            name = label(f'{APP}  <span size="small" weight="normal" alpha="70%">by {AUTHOR}</span>', "mm-brand",
                         markup=True)
            name.set_tooltip_text(f"{AUTHOR_FULL} <{EMAIL}>")
            brand.pack_start(name, False, False, 0)
            self.search = Gtk.SearchEntry()
            self.search.set_margin_start(16)
            self.search.set_margin_end(16)
            self.search.set_margin_bottom(8)
            self.search.connect("search-changed", self.on_search)
            self.search.connect("stop-search", lambda *_a: self.search.set_text(""))
            self.nav = styled(Gtk.ListBox(), "mm-nav")
            self.nav.set_selection_mode(Gtk.SelectionMode.BROWSE)
            self.nav.connect("row-selected", self.on_row)
            self.nav.set_header_func(self.nav_header)
            self.nav.set_filter_func(self.nav_filter)
            self.no_match = label("", "mm-dim")
            self.no_match.set_margin_start(22)
            self.no_match.set_no_show_all(True)
            sw = Gtk.ScrolledWindow()
            sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            sw.add(self.nav)
            for w in (brand, self.search, self.no_match):
                side.pack_start(w, False, False, 0)
            side.pack_start(sw, True, True, 0)

            # contenido con aviso flotante
            self.stack = Gtk.Stack()
            self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
            self.stack.set_transition_duration(140)
            self.stack.add_named(self.loading_page(), "_cargando")
            overlay = Gtk.Overlay()
            overlay.add(self.stack)
            self.toast_rev = Gtk.Revealer(halign=Gtk.Align.CENTER, valign=Gtk.Align.END)
            self.toast_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
            toast = styled(Gtk.Box(spacing=12), "mm-toast")
            self.toast_label = label("", wrap=True)
            self.toast_label.set_max_width_chars(70)
            self.toast_open = styled(Gtk.Button(), "mm-ghost")
            self.toast_open.connect("clicked", self.on_toast_open)
            close = styled(Gtk.Button(), "mm-ghost")
            close.add(icon("window-close-symbolic"))
            close.connect("clicked", lambda *_a: self.toast_rev.set_reveal_child(False))
            toast.pack_start(self.toast_label, True, True, 0)
            toast.pack_start(self.toast_open, False, False, 0)
            toast.pack_start(close, False, False, 0)
            self.toast_rev.add(toast)
            overlay.add_overlay(self.toast_rev)
            self.toast_path, self.toast_timer = None, None

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            box.pack_start(side, False, False, 0)
            box.pack_start(overlay, True, True, 0)
            self.add(box)
            self.connect("destroy", Gtk.main_quit)
            self.setup_keys()
            self.translate_chrome()
            self.ticks = 0
            SAMPLER.tick()
            self.reload()
            GLib.timeout_add_seconds(1, self.on_tick)

        def translate_chrome(self):
            """Textos fijos de la ventana; se repiten al cambiar de idioma."""
            self.btn_refresh.set_tooltip_text(_("Volver a leer todo el equipo (F5)"))
            self.menu_btn.set_tooltip_text(_("Menú"))
            self.export_btn.set_label(_("Exportar"))
            self.export_btn.set_tooltip_text(_("Guardar o copiar el informe: texto, página web, foro, JSON o CSV (Ctrl+E)"))
            self.search.set_placeholder_text(_("Buscar en el informe"))
            self.search.set_tooltip_text(_("Escribe, por ejemplo, «temperatura», «NVIDIA» o «batería» (Ctrl+F)"))
            self.no_match.set_text(_("Sin resultados."))
            self.toast_open.set_label(_("Abrir"))
            self.hb.set_subtitle(_(READONLY))

        # ── menú: idioma, tema, privacidad, ayuda y desinstalar ──
        def fill_menu(self, pop):
            for c in pop.get_children():
                pop.remove(c)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            box.set_border_width(14)
            grid = Gtk.Grid(column_spacing=12, row_spacing=8)
            lang = Gtk.ComboBoxText()
            for code, name in LANGS.items():
                lang.append(code, name)
            lang.set_active_id(_LANG[0])
            tema = Gtk.ComboBoxText()
            tema.append("oscuro", _("Oscuro"))
            tema.append("claro", _("Claro"))
            tema.set_active_id(state["tema"])
            grid.attach(label(_("Idioma"), "mm-dim"), 0, 0, 1, 1)
            grid.attach(lang, 1, 0, 1, 1)
            grid.attach(label(_("Aspecto"), "mm-dim"), 0, 1, 1, 1)
            grid.attach(tema, 1, 1, 1, 1)
            box.pack_start(grid, False, False, 2)
            anon_cb = Gtk.CheckButton(label=_("Ocultar datos personales en pantalla"))
            anon_cb.set_tooltip_text(_("Tapa números de serie, MAC, IP, nombre del equipo, red Wi-Fi y usuario. "
                                       "Útil para hacer capturas de pantalla."))
            anon_cb.set_active(self.anon)
            box.pack_start(anon_cb, False, False, 6)
            box.pack_start(Gtk.Separator(), False, False, 2)
            items = [(_("Atajos de teclado"), self.on_shortcuts, ""), (_("Acerca de MintMachine"), self.on_about, ""),
                     (_("Desinstalar MintMachine…"), self.on_uninstall, "mm-danger")]
            for text, cb, cls in items:
                b = Gtk.ModelButton(text=text)
                if cls:
                    b.get_style_context().add_class(cls)
                b.connect("clicked", lambda _b, f=cb: (pop.popdown(), f()))
                box.pack_start(b, False, False, 0)

            def on_lang(cb):
                code = cb.get_active_id()
                if code and code != _LANG[0]:
                    save_config(idioma=code)
                    set_language(code)
                    pop.popdown()
                    self.translate_chrome()
                    self.reload(force=True)

            def on_tema(cb):
                t = cb.get_active_id()
                if t and t != state["tema"]:
                    state["tema"] = t
                    save_config(tema=t)
                    apply_theme()
                    self.queue_draw()
            lang.connect("changed", on_lang)
            tema.connect("changed", on_tema)
            anon_cb.connect("toggled", self.on_anon)
            box.show_all()
            pop.add(box)

        def setup_keys(self):
            acc = Gtk.AccelGroup()
            self.add_accel_group(acc)

            def bind(key, fn):
                k, m = Gtk.accelerator_parse(key)
                acc.connect(k, m, Gtk.AccelFlags.VISIBLE, lambda *_a: fn() or True)
            bind("<Control>f", lambda: self.search.grab_focus())
            bind("F5", self.reload)
            bind("<Control>r", self.reload)
            bind("<Control>e", lambda: self.export_btn.get_sensitive() and self.export_btn.set_active(True))
            bind("<Control>q", self.destroy)
            bind("F1", self.on_about)
            for i in range(1, 10):
                bind(f"<Alt>{i}", lambda i=i: self.goto_index(i - 1))

        def goto_index(self, i):
            rows = [r for r in self.nav.get_children() if r.get_mapped()]
            if i < len(rows):
                self.nav.select_row(rows[i])

        def on_shortcuts(self, *_a):
            items = [(_("Buscar en el informe"), "<Control>f"), (_("Volver a leer el equipo"), "F5"),
                     (_("Exportar"), "<Control>e"), (_("Ir a la sección 1 a 9 de la lista"), "<Alt>1"),
                     (_("Acerca de"), "F1"), (_("Salir"), "<Control>q")]
            xml = ('<interface><object class="GtkShortcutsWindow" id="w"><property name="modal">1</property>'
                   '<child><object class="GtkShortcutsSection"><property name="visible">1</property>'
                   '<child><object class="GtkShortcutsGroup"><property name="visible">1</property>'
                   '<property name="title">MintMachine</property>')
            for title, accel in items:
                xml += ('<child><object class="GtkShortcutsShortcut"><property name="visible">1</property>'
                        f'<property name="title">{html.escape(title)}</property>'
                        f'<property name="accelerator">{html.escape(accel)}</property></object></child>')
            xml += "</object></child></object></child></object></interface>"
            w = Gtk.Builder.new_from_string(xml, -1).get_object("w")
            w.set_transient_for(self)
            w.show_all()

        def on_about(self, *_a):
            d = Gtk.AboutDialog(transient_for=self, modal=True)
            d.set_program_name(APP)
            d.set_version(VERSION)
            d.set_logo_icon_name("mintmachine" if theme.has_icon("mintmachine") else "computer")
            d.set_comments(_("Hardware, drivers y software de tu equipo en una sola ventana.") + "\n\n" + _(DISCLAIMER))
            d.set_authors([f"{AUTHOR_FULL} <{EMAIL}>"])
            d.set_copyright(f"© 2026 {AUTHOR_FULL}")
            d.set_license_type(Gtk.License.MIT_X11)
            d.run()
            d.destroy()

        def message(self, kind, title, text, buttons=Gtk.ButtonsType.CLOSE):
            d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=kind, buttons=buttons, text=title)
            d.format_secondary_text(text)
            r = d.run()
            d.destroy()
            return r

        def on_uninstall(self, *_a):
            cmd = uninstall_cmd()
            d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                                  buttons=Gtk.ButtonsType.NONE, text=_("¿Desinstalar MintMachine?"))
            d.format_secondary_text(
                _("Se quitarán el programa, su icono del menú y su configuración, sin dejar rastro en el equipo. "
                  "Los informes que hayas guardado son tuyos y no se tocan.")
                + ("\n\n" + _("El sistema te pedirá tu contraseña para quitar el programa.") if cmd else ""))
            d.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
            ok = d.add_button(_("Desinstalar"), Gtk.ResponseType.OK)
            ok.get_style_context().add_class("destructive-action")
            r = d.run()
            d.destroy()
            if r != Gtk.ResponseType.OK:
                return
            if not cmd:
                remove_user_data()
                self.message(Gtk.MessageType.INFO, _("Configuración borrada"),
                             _("MintMachine no está instalado como paquete: lo estás ejecutando desde su carpeta. "
                               "Se ha borrado su configuración; para terminar, borra esa carpeta."))
                return
            self.spinner.start()
            self.set_sensitive(False)

            def work():
                try:
                    p = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, errors="replace")
                    res = (p.returncode, p.stdout)
                except OSError as e:
                    res = (-1, str(e))
                GLib.idle_add(done, res)

            def done(res):
                self.spinner.stop()
                self.set_sensitive(True)
                code, out = res
                if code == 0:
                    remove_user_data()
                    self.message(Gtk.MessageType.INFO, _("MintMachine se ha desinstalado"),
                                 _("Gracias por usarlo. La ventana se cerrará ahora."))
                    self.destroy()
                elif code in (126, 127):
                    self.message(Gtk.MessageType.INFO, _("No se ha desinstalado"),
                                 _("Se ha cancelado la contraseña. No se ha cambiado nada."))
                else:
                    tail = "\n".join(out.strip().splitlines()[-4:])
                    self.message(Gtk.MessageType.ERROR, _("No se ha podido desinstalar"),
                                 _("Si el Gestor de actualizaciones u otro instalador está abierto, ciérralo y vuelve "
                                   "a intentarlo.") + ("\n\n" + tail if tail else ""))
                return False
            threading.Thread(target=work, daemon=True).start()

        def notify(self, text, path=None):
            self.toast_label.set_text(text)
            self.toast_path = path
            self.toast_open.set_visible(bool(path))
            self.toast_rev.show_all()
            self.toast_open.set_visible(bool(path))
            self.toast_rev.set_reveal_child(True)
            if self.toast_timer:
                GLib.source_remove(self.toast_timer)
            self.toast_timer = GLib.timeout_add_seconds(9, self.hide_toast)

        def hide_toast(self):
            self.toast_rev.set_reveal_child(False)
            self.toast_timer = None
            return False

        def on_toast_open(self, *_a):
            if self.toast_path:
                self.launch(["xdg-open", self.toast_path])
            self.hide_toast()

        def launch(self, cmd):
            try:
                subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError as e:
                self.notify(_("No se ha podido abrir «{prog}»: {err}").format(prog=cmd[0], err=e.strerror))

        # ── carga de datos (en un hilo, para no congelar la ventana) ──
        def loading_page(self):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, valign=Gtk.Align.CENTER)
            sp = Gtk.Spinner(width_request=36, height_request=36)
            sp.start()
            box.pack_start(sp, False, False, 0)
            self.loading_label = label(_("Leyendo el equipo…"), "mm-hero-title", xalign=0.5)
            box.pack_start(self.loading_label, False, False, 0)
            box.pack_start(label(_("Tarda unos segundos. MintMachine solo lee: no cambia nada."), "mm-dim", xalign=0.5),
                           False, False, 0)
            return box

        def reload(self, force=False):
            if self.busy:
                return
            self.busy = True
            self.btn_refresh.set_sensitive(False)
            self.spinner.start()

            def work():
                secs = collect_all()
                GLib.idle_add(self.populate, secs)
            threading.Thread(target=work, daemon=True).start()

        def current(self):
            row = self.nav.get_selected_row()
            return row.sid if row else None

        def populate(self, secs):
            keep = self.current() or (start or "").split("+")[0]
            self.sections = secs
            for child in self.nav.get_children():
                child.destroy()
            for child in self.stack.get_children():
                if self.stack.child_get_property(child, "name") != "_cargando":
                    child.destroy()
            self.refs, self.index = {}, {}
            select = None
            for s in secs:
                row = Gtk.ListBoxRow()
                row.sid = s["id"]
                hbox = Gtk.Box(spacing=12)
                hbox.pack_start(self.nav_icon(row), False, False, 0)
                hbox.pack_start(Gtk.Label(label=s["title"], xalign=0), True, True, 0)
                if s["id"] == "diagnostico":
                    rows = [f for b in s["blocks"] if b["type"] == "findings" for f in b["rows"]]
                    n = sum(1 for f in rows if f["level"] in ("bad", "warn"))
                    if n:
                        badge = styled(Gtk.Label(label=str(n)), "mm-badge")
                        if any(f["level"] == "bad" for f in rows):
                            badge.get_style_context().add_class("mm-badge-bad")
                        hbox.pack_end(badge, False, False, 0)
                row.add(hbox)
                self.nav.add(row)
                self.stack.add_named(self.build_page(s), s["id"])
                self.index[s["id"]] = fold(to_text([s], self.anon, header=False))
                if s["id"] == keep or select is None:
                    select = row
            self.nav.show_all()
            self.stack.show_all()
            self.on_search(self.search)
            if select:
                self.nav.select_row(select)
            self.spinner.stop()
            self.btn_refresh.set_sensitive(True)
            self.export_btn.set_sensitive(True)
            self.busy = False
            if self.first:
                self.first = False
                if select:
                    select.grab_focus()
            return False

        def nav_icon(self, row):
            if not can_draw:
                return icon(SECTION_ICONS.get(row.sid, []))
            area = Gtk.DrawingArea()
            area.set_size_request(18, 18)
            area.set_valign(Gtk.Align.CENTER)

            def draw(w, cr):
                if row.is_selected():
                    color = rgb("a1") + (1.0,)
                else:
                    c = w.get_style_context().get_color(w.get_state_flags())
                    color = (c.red, c.green, c.blue, c.alpha)
                draw_icon(cr, row.sid, color)
                return False
            area.connect("draw", draw)
            return area

        # ── barra lateral: grupos y búsqueda ──
        def nav_header(self, row, before):
            group = GROUPS.get(row.sid)
            row.set_header(label(_(group).upper(), "mm-group") if group else None)

        def nav_filter(self, row):
            q = fold(self.search.get_text().strip())
            return not q or q in self.index.get(row.sid, "") or q in fold(_(TITLES.get(row.sid, "")))

        def on_search(self, entry):
            self.nav.invalidate_filter()
            q = entry.get_text().strip()
            visible = [r for r in self.nav.get_children() if self.nav_filter(r)]
            self.no_match.set_visible(bool(q) and not visible)
            cur = self.nav.get_selected_row()
            if q and visible and (cur is None or cur not in visible):
                self.nav.select_row(visible[0])

        # ── construcción de una página ──
        def build_page(self, s):
            self._building = s["id"]
            page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            page.set_border_width(32)
            page.set_margin_top(22)
            group = None
            for sid in COLLECTORS:
                group = GROUPS.get(sid, group)
                if sid == s["id"]:
                    break
            kicker = _(group).upper() if s["id"] in COLLECTORS and group else APP.upper()
            page.pack_start(label(kicker, "mm-kicker"), False, False, 0)
            page.pack_start(label(s["title"], "mm-heading"), False, False, 0)
            adv_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            refs, grid, n = [], None, 0
            for b in s["blocks"]:
                target = adv_box if b.get("adv") else page
                if b["type"] == "chart":
                    if grid is None:
                        grid = Gtk.Grid(column_spacing=16, row_spacing=16, column_homogeneous=True, margin_top=10)
                        page.pack_start(grid, False, False, 0)
                    widget, ref = self.w_chart(b)
                    grid.attach(widget, n % 2, n // 2, 1, 1)
                    n += 1
                    refs.append(("chart", ref))
                    continue
                if b["title"]:
                    t = label(b["title"].upper(), "mm-title")
                    t.set_margin_top(18)
                    target.pack_start(t, False, False, 0)
                if b.get("help"):
                    target.pack_start(label(b["help"], "mm-dim", wrap=True), False, False, 0)
                kind = "gauges" if b["type"] == "bars" and b.get("gauge") else b["type"]
                widget, ref = getattr(self, "w_" + kind)(b)
                target.pack_start(widget, False, False, 0)
                refs.append((kind, ref))
            if adv_box.get_children():
                exp = Gtk.Expander(label=_("Detalles técnicos"), margin_top=22)
                exp.set_tooltip_text(_("Información para usuarios avanzados o para pedir ayuda en un foro"))
                exp.add(adv_box)
                page.pack_start(exp, False, False, 0)
            self.refs[s["id"]] = refs
            sw = Gtk.ScrolledWindow()
            sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            sw.add(page)
            return sw

        def card(self, child, *classes):
            frame = styled(Gtk.Box(), "mm-card", *classes)
            frame.pack_start(child, True, True, 0)
            return frame

        def level_ring(self, level, size=Gtk.IconSize.DIALOG):
            ring = styled(Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER), "mm-ring", level)
            img = icon(LEVEL_ICONS.get(level, "dialog-information-symbolic"), size)
            img.set_margin_start(10)
            img.set_margin_end(10)
            img.set_margin_top(10)
            img.set_margin_bottom(10)
            ring.pack_start(img, True, True, 0)
            return ring

        def w_status(self, b):
            box = styled(Gtk.Box(spacing=20), "mm-hero", b["level"])
            box.set_border_width(0)
            inner = Gtk.Box(spacing=20, margin_start=22, margin_end=22, margin_top=20, margin_bottom=20)
            inner.pack_start(self.level_ring(b["level"]), False, False, 0)
            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER)
            texts.pack_start(label(b["text"], "mm-hero-title", wrap=True), False, False, 0)
            sub = _("No se ha detectado ningún problema en la revisión automática.") if b["level"] == "ok" \
                else _("Abajo tienes qué pasa y qué puedes hacer.")
            texts.pack_start(label(sub, "mm-dim", wrap=True), False, False, 0)
            inner.pack_start(texts, True, True, 0)
            if self._building != "diagnostico":
                btn = styled(Gtk.Button(label=_("Ver diagnóstico completo"), valign=Gtk.Align.CENTER), "mm-ghost")
                btn.connect("clicked", lambda *_a: self.goto("diagnostico"))
                inner.pack_end(btn, False, False, 0)
            box.pack_start(inner, True, True, 0)
            return box, None

        def goto(self, sid):
            for r in self.nav.get_children():
                if r.sid == sid:
                    if not r.get_mapped():
                        self.search.set_text("")
                    self.nav.select_row(r)

        def w_findings(self, b):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            esc = GLib.markup_escape_text
            for i, f in enumerate(b["rows"]):
                if i:
                    box.pack_start(Gtk.Separator(), False, False, 0)
                row = styled(Gtk.Box(spacing=14), "mm-finding")
                img = icon(LEVEL_ICONS.get(f["level"], "dialog-information-symbolic"), Gtk.IconSize.LARGE_TOOLBAR)
                img.get_style_context().add_class("mm-ic-" + f["level"])
                img.set_valign(Gtk.Align.START)
                img.set_tooltip_text(_(LEVELS[f["level"]][1]))
                row.pack_start(img, False, False, 0)
                col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                head = label(f'<span weight="bold">{esc(f["area"])}</span>   {esc(show(f["text"], self.anon))}',
                             wrap=True, markup=True, selectable=True)
                col.pack_start(head, False, False, 0)
                if f.get("todo") and not b.get("compact"):
                    col.pack_start(label(f'<b>{esc(_("Qué hacer:"))}</b> {esc(show(f["todo"], self.anon))}', "mm-dim",
                                         wrap=True, markup=True), False, False, 0)
                cmd = action_cmd(f.get("action")) if f.get("action") and not b.get("compact") else None
                if cmd:
                    btn = styled(Gtk.Button(label=_(ACTIONS[f["action"]][0]), halign=Gtk.Align.START, margin_top=6),
                                 "mm-ghost")
                    btn.connect("clicked", lambda _b, c=cmd: self.launch(c))
                    col.pack_start(btn, False, False, 0)
                row.pack_start(col, True, True, 0)
                box.pack_start(row, False, False, 0)
            return self.card(box), len(b["rows"])

        def w_kv(self, b):
            grid = Gtk.Grid(column_spacing=28, row_spacing=10)
            grid.set_border_width(18)
            labels = []
            for i, (k, v) in enumerate(b["rows"]):
                kbox = Gtk.Box(spacing=6, valign=Gtk.Align.START)
                kl = label(k, "mm-key")
                kl.set_line_wrap(True)
                kl.set_max_width_chars(30)
                kbox.pack_start(kl, False, False, 0)
                kbox.set_size_request(240, -1)
                vl = label(show(v, self.anon), "mm-val", wrap=True, selectable=True)
                vl.set_max_width_chars(80)
                vl.set_hexpand(True)
                vl.set_yalign(0)
                grid.attach(kbox, 0, i, 1, 1)
                grid.attach(vl, 1, i, 1, 1)
                labels.append(vl)
            return self.card(grid), labels

        def w_bars(self, b):
            grid = Gtk.Grid(column_spacing=18, row_spacing=12)
            grid.set_border_width(18)
            widgets = []
            for i, (lab, frac, text) in enumerate(b["rows"]):
                kl = label(lab, "mm-key")
                kl.set_size_request(160, -1)
                bar = Gtk.ProgressBar(fraction=frac, valign=Gtk.Align.CENTER)
                bar.set_size_request(260, -1)
                tl = label(show(text, self.anon), "mm-dim")
                tl.set_hexpand(True)
                tl.set_ellipsize(Pango.EllipsizeMode.END)
                for col, w in enumerate((kl, bar, tl)):
                    grid.attach(w, col, i, 1, 1)
                widgets.append((bar, tl))
            return self.card(grid), widgets

        # ── indicadores circulares de «Ahora mismo» ──
        def w_gauges(self, b):
            flow = Gtk.Box(spacing=14, homogeneous=True)
            refs = []
            for lab, frac, text in b["rows"]:
                col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                col.set_border_width(16)
                area = Gtk.DrawingArea()
                area.set_size_request(118, 118)
                st = {"frac": frac, "center": self.gauge_center(frac, text)}
                if can_draw:
                    area.connect("draw", self.draw_gauge, st)
                col.pack_start(area, False, False, 0)
                col.pack_start(label(lab, "mm-val", xalign=0.5), False, False, 4)
                sub = label(show(text, self.anon), "mm-dim mm-chip", xalign=0.5)
                sub.set_line_wrap(True)
                sub.set_justify(Gtk.Justification.CENTER)
                sub.set_max_width_chars(22)
                col.pack_start(sub, False, False, 0)
                flow.pack_start(self.card(col), True, True, 0)
                refs.append((area, st, sub))
            return flow, refs

        @staticmethod
        def gauge_center(frac, text):
            m = re.search(r"(-?[\d.,]+)\s*(°C|%|MHz)", text)
            if m and m.group(2) == "MHz":
                return num(float(m.group(1).replace(",", ".")) / 1000) + " GHz"
            return f"{m.group(1)}{' °C' if m.group(2) == '°C' else '%'}" if m else f"{frac * 100:.0f}%"

        def draw_gauge(self, area, cr, st):
            w, h = area.get_allocated_width(), area.get_allocated_height()
            r = min(w, h) / 2 - 8
            cx, cy = w / 2, h / 2
            import math
            fg = rgb("fg")
            cr.set_line_width(9)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            start, sweep = math.pi * 0.75, math.pi * 1.5
            cr.set_source_rgba(*fg, 0.08)
            cr.arc(cx, cy, r, start, start + sweep)
            cr.stroke()
            frac = st["frac"]
            if frac > 0.002:
                if frac >= 0.9:
                    c1, c2 = rgb("bad"), rgb("warn")
                elif frac >= 0.75:
                    c1, c2 = rgb("warn"), rgb("a2")
                else:
                    c1, c2 = rgb("a1"), rgb("a2")
                g = cairo.LinearGradient(cx - r, cy + r, cx + r, cy - r)
                g.add_color_stop_rgb(0, *c1)
                g.add_color_stop_rgb(1, *c2)
                cr.set_source(g)
                cr.arc(cx, cy, r, start, start + sweep * frac)
                cr.stroke()
            cr.set_source_rgb(*fg)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(22)
            t = st["center"]
            ext = cr.text_extents(t)
            cr.move_to(cx - ext.width / 2 - ext.x_bearing, cy - ext.height / 2 - ext.y_bearing)
            cr.show_text(t)
            return False

        def w_table(self, b):
            n = len(b["headers"])
            store = Gtk.ListStore(*([str] * n))
            for r in b["rows"]:
                store.append([show(c, self.anon) for c in r])
            tv = Gtk.TreeView(model=store)
            tv.set_enable_search(False)
            tv.set_grid_lines(Gtk.TreeViewGridLines.NONE)
            tv.get_selection().set_mode(Gtk.SelectionMode.NONE)
            for i, h in enumerate(b["headers"]):
                longest = max([len(r[i]) for r in b["rows"]] or [0])
                cell = Gtk.CellRendererText(xpad=10, ypad=7)
                col = Gtk.TreeViewColumn(h, cell, text=i)
                col.set_resizable(True)
                if longest > 34 and n <= 3:   # texto para leer entero: varias líneas
                    cell.set_property("wrap-mode", Pango.WrapMode.WORD_CHAR)
                    cell.set_property("wrap-width", 560)
                    col.set_expand(True)
                elif longest > 34:            # tabla ancha: se recorta y se reparte el ancho
                    cell.set_property("ellipsize", Pango.EllipsizeMode.END)
                    col.set_expand(True)
                    col.set_min_width(220)
                tv.append_column(col)
            sw = Gtk.ScrolledWindow()
            sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
            sw.add(tv)
            sw.set_margin_top(4)
            sw.set_margin_bottom(6)
            return self.card(sw), store

        def legend(self, b):
            esc = GLib.markup_escape_text
            parts = []
            cols = [PALETTES[state["tema"]]["a1"], PALETTES[state["tema"]]["a2"]]
            for i, (lab, v) in enumerate(b["rows"]):
                parts.append(f'<span foreground="{cols[i % 2]}">●</span> {esc(lab)} '
                             f'<b>{esc(fmt_unit(v[-1], b["unit"]))}</b> '
                             f'<small>({esc(_("máx."))} {esc(fmt_unit(max(v), b["unit"]))})</small>')
            return "     ".join(parts)

        def w_chart(self, b):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_border_width(18)
            box.pack_start(label(b["title"].upper(), "mm-title"), False, False, 0)
            legend = label("")
            legend.set_ellipsize(Pango.EllipsizeMode.END)
            legend.set_markup(self.legend(b))
            area = Gtk.DrawingArea()
            area.set_size_request(-1, 120)
            area.set_tooltip_text(_("Últimos 2 minutos, una muestra por segundo"))
            st = {"b": b}
            if can_draw:
                area.connect("draw", self.draw_chart, st)
            else:
                area = label(_("Instala python3-gi-cairo para ver la gráfica"), "mm-dim")
            box.pack_start(legend, False, False, 0)
            box.pack_start(area, False, False, 0)
            card = self.card(box)
            card.set_hexpand(True)
            return card, (st, area, legend, len(b["rows"]))

        def draw_chart(self, area, cr, st):
            b = st["b"]
            w, h = area.get_allocated_width(), area.get_allocated_height()
            fg = rgb("fg")
            allv = [x for _l, v in b["rows"] for x in v] or [0]
            if b["unit"] == "%":
                top = 100.0
            elif b["unit"] == "°C":
                top = max(100.0, max(allv))
            else:
                top = max(max(allv) * 1.2, 64 * 1024)
            cr.set_line_width(1)
            cr.set_source_rgba(*fg, 0.06)
            for f in (0.25, 0.5, 0.75, 1):
                y = 0.5 + round((h - 1) * f)
                cr.move_to(0, y)
                cr.line_to(w, y)
            cr.stroke()
            step = w / (HIST - 1)
            colors = [(rgb("a1"), rgb("a2")), (rgb("a2"), rgb("warn"))]
            for i, (_lab, v) in enumerate(b["rows"]):
                pts = [(w - (len(v) - 1 - k) * step, h - 2 - min(x / top, 1) * (h - 6)) for k, x in enumerate(v)]
                if len(pts) < 2:
                    continue
                c1, c2 = colors[i % 2]

                def path():
                    cr.move_to(*pts[0])
                    for k in range(1, len(pts)):        # curva suave entre muestras
                        x0, y0 = pts[k - 1]
                        x1, y1 = pts[k]
                        mx = (x0 + x1) / 2
                        cr.curve_to(mx, y0, mx, y1, x1, y1)
                if i == 0:
                    path()
                    cr.line_to(pts[-1][0], h)
                    cr.line_to(pts[0][0], h)
                    cr.close_path()
                    g = cairo.LinearGradient(0, 0, 0, h)
                    g.add_color_stop_rgba(0, *c1, 0.32)
                    g.add_color_stop_rgba(1, *c2, 0.0)
                    cr.set_source(g)
                    cr.fill()
                path()
                g = cairo.LinearGradient(pts[0][0], 0, w, 0)
                g.add_color_stop_rgb(0, *c1)
                g.add_color_stop_rgb(1, *c2)
                cr.set_source(g)
                cr.set_line_width(2.2)
                cr.stroke()
                x, y = pts[-1]
                cr.set_source_rgb(*c2)
                cr.arc(x - 3, y, 3.5, 0, 6.283)
                cr.fill()
            cr.set_source_rgba(*fg, 0.45)
            cr.set_font_size(10)
            cr.move_to(4, 12)
            cr.show_text(fmt_unit(top, b["unit"]))
            return False

        def w_cores(self, b):
            area = Gtk.DrawingArea()
            area.set_size_request(-1, 92)
            for m in ("top", "bottom", "start", "end"):
                getattr(area, "set_margin_" + m)(16)
            st = {"b": b}
            if can_draw:
                area.connect("draw", self.draw_cores, st)
            return self.card(area), (st, area)

        def draw_cores(self, area, cr, st):
            rows = st["b"]["rows"]
            w, h = area.get_allocated_width(), area.get_allocated_height()
            fg = rgb("fg")
            n = max(len(rows), 1)
            gap = 6 if n <= 32 else 2
            bw = max(2.0, min(56.0, (w - gap * (n - 1)) / n))
            bh = h - 16
            c1, c2 = rgb("a1"), rgb("a2")
            cr.set_font_size(9)
            for i, (num_, v) in enumerate(rows):
                x = i * (bw + gap)
                cr.set_source_rgba(*fg, 0.07)
                cr.rectangle(x, 0, bw, bh)
                cr.fill()
                fill = bh * min(max(v, 0), 100) / 100
                g = cairo.LinearGradient(0, bh, 0, 0)
                g.add_color_stop_rgb(0, *c1)
                g.add_color_stop_rgb(1, *c2)
                cr.set_source(g)
                cr.rectangle(x, bh - fill, bw, fill)
                cr.fill()
                if n <= 32:
                    cr.set_source_rgba(*fg, 0.5)
                    cr.move_to(x + 1, h - 3)
                    cr.show_text(str(num_))
                if bw >= 26:             # con sitio, el porcentaje de cada hilo sobre su barra
                    t = f"{v:.0f}%"
                    ext = cr.text_extents(t)
                    cr.set_source_rgba(*fg, 0.85)
                    cr.move_to(x + (bw - ext.width) / 2 - ext.x_bearing, 12)
                    cr.show_text(t)
            return False

        def w_note(self, b):
            lab = label(b["text"], "mm-dim", wrap=True)
            lab.set_margin_top(8)
            return lab, None

        # ── refresco en vivo de la sección visible ──
        def on_tick(self):
            SAMPLER.tick()
            self.ticks += 1
            sid = self.current()
            fast = sid == "cpu" and self.ticks % 2
            if self.busy or sid not in LIVE or (sid not in ("monitor", "cpu") and self.ticks % 2):
                return True
            idx = next((i for i, s in enumerate(self.sections) if s["id"] == sid), None)
            if idx is None:
                return True
            if sid == "resumen":       # en el Inicio solo cambia «Ahora mismo»
                old = self.sections[idx]
                live = live_now()
                new = dict(old, blocks=[live if b["type"] == "bars" and b.get("gauge") else b for b in old["blocks"]])
            elif fast:                 # en Procesador, entre dos lecturas completas, solo lo que va en vivo
                old = self.sections[idx]
                live = {b["type"]: b for b in cpu_live()}
                new = dict(old, blocks=[live.get("bars", b) if b["type"] == "bars" and b.get("gauge")
                                        else live.get("cores", b) if b["type"] == "cores" else b
                                        for b in old["blocks"]])
            else:
                new = safe(sid, COLLECTORS[sid], Ctx())
            self.sections[idx] = new
            refs = self.refs.get(sid, [])

            def fits(t, r, b):
                kind = "gauges" if b["type"] == "bars" and b.get("gauge") else b["type"]
                if t != kind:
                    return False
                if t in ("kv", "bars", "gauges"):
                    return len(r) == len(b["rows"])
                if t == "table":
                    return r.get_n_columns() == len(b["headers"])
                if t == "chart":
                    return r[3] == len(b["rows"])
                if t == "findings":
                    return r == len(b["rows"])
                return True
            same = len(refs) == len(new["blocks"]) and all(fits(t, r, b) for (t, r), b in zip(refs, new["blocks"]))
            if not same:         # ha cambiado la estructura: se reconstruye la página
                old = self.stack.get_child_by_name(sid)
                expanded = [e.get_expanded() for e in self.expanders(old)]
                page = self.build_page(new)
                for e, x in zip(self.expanders(page), expanded):
                    e.set_expanded(x)
                self.stack.remove(old)
                old.destroy()
                self.stack.add_named(page, sid)
                page.show_all()
                self.stack.set_visible_child_name(sid)
                return True
            for (t, r), b in zip(refs, new["blocks"]):
                if t == "kv":
                    for lab, (_k, v) in zip(r, b["rows"]):
                        txt = show(v, self.anon)
                        if lab.get_text() != txt:
                            lab.set_text(txt)
                elif t == "bars":
                    for (bar, tl), (_l, frac, text) in zip(r, b["rows"]):
                        bar.set_fraction(frac)
                        tl.set_text(show(text, self.anon))
                elif t == "gauges":
                    for (area, st, sub), (_l, frac, text) in zip(r, b["rows"]):
                        st["frac"], st["center"] = frac, self.gauge_center(frac, text)
                        sub.set_text(show(text, self.anon))
                        area.queue_draw()
                elif t == "chart":
                    r[0]["b"] = b
                    r[2].set_markup(self.legend(b))
                    r[1].queue_draw()
                elif t == "cores":
                    r[0]["b"] = b
                    r[1].queue_draw()
                elif t == "table":
                    rows = [[show(c, self.anon) for c in row] for row in b["rows"]]
                    if len(r) == len(rows):
                        for it, row in zip(r, rows):
                            for c, val in enumerate(row):
                                if it[c] != val:
                                    it[c] = val
                    else:
                        r.clear()
                        for row in rows:
                            r.append(row)
            return True

        def expanders(self, widget):
            out = []

            def walk(w):
                if isinstance(w, Gtk.Expander):
                    out.append(w)
                if isinstance(w, Gtk.Container):
                    for c in w.get_children():
                        walk(c)
            walk(widget)
            return out

        # ── acciones ──
        def on_row(self, _lb, row):
            if row:
                self.stack.set_visible_child_name(row.sid)
            self.nav.queue_draw()

        def on_anon(self, btn):
            self.anon = btn.get_active()
            if self.sections and not self.busy:
                self.populate(self.sections)

        # ── exportar ──
        def fill_export(self, pop):
            for c in pop.get_children():
                pop.remove(c)
            sid = self.current()
            title = next((s["title"] for s in self.sections if s["id"] == sid), "")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            box.set_border_width(18)
            box.pack_start(label(_("Exportar informe"), "mm-hero-title"), False, False, 0)
            box.pack_start(label(_("Qué incluir").upper(), "mm-title"), False, False, 8)
            r_all = Gtk.RadioButton.new_with_label(None, _("Todo el informe"))
            r_one = Gtk.RadioButton.new_with_label_from_widget(r_all, _("Solo «{seccion}»").format(seccion=title))
            for r in (r_all, r_one):
                box.pack_start(r, False, False, 0)
            box.pack_start(label(_("Formato").upper(), "mm-title"), False, False, 8)
            radios, first = {}, None
            for key, (_fn, _ext, name, desc) in EXPORTERS.items():
                rb = Gtk.RadioButton.new_from_widget(first)
                rb.add(label(f"{GLib.markup_escape_text(_(name))}\n<small>{GLib.markup_escape_text(_(desc))}</small>",
                             markup=True))
                first = first or rb
                radios[key] = rb
                box.pack_start(rb, False, False, 0)
                if key == "foro":           # para pedir ayuda: solo lo que hace falta para ese problema
                    topic_box = Gtk.Box(spacing=8, margin_start=28, margin_bottom=4)
                    topic_box.pack_start(label(_("Pedir ayuda con:"), "mm-dim"), False, False, 0)
                    topic_cb = Gtk.ComboBoxText()
                    for tkey, (tname, _secs) in FORUM_TOPICS.items():
                        topic_cb.append(tkey, _(tname))
                    topic_cb.set_active_id("general")
                    topic_cb.set_tooltip_text(_("Elige el problema y el resumen llevará la ficha del equipo y solo "
                                                "las secciones que hacen falta para ayudarte con él."))
                    topic_box.pack_start(topic_cb, False, False, 0)
                    box.pack_start(topic_box, False, False, 0)
            anon_cb = Gtk.CheckButton(label=_("Ocultar datos personales"))
            anon_cb.set_tooltip_text(_("Tapa números de serie, MAC, IP, nombre del equipo, red Wi-Fi, usuario y otros "
                                       "datos que te identifican. Recomendado si lo vas a publicar o enviar."))
            anon_cb.set_active(True)
            box.pack_start(anon_cb, False, False, 10)

            def chosen():
                return next(k for k, rb in radios.items() if rb.get_active())

            def sync(*_a):
                fmt = chosen()
                r_all.set_sensitive(fmt != "csv")
                r_one.set_sensitive(fmt != "csv" and bool(sid))
                anon_cb.set_sensitive(fmt != "csv")
                topic_box.set_sensitive(fmt == "foro" and r_all.get_active())
            for rb in list(radios.values()) + [r_all]:
                rb.connect("toggled", sync)
            sync()

            def payload():
                fmt = chosen()
                secs = self.sections if r_all.get_active() else [s for s in self.sections if s["id"] == sid]
                return (fmt, export(fmt, secs, anon_cb.get_active() and fmt != "csv",
                                    topic_cb.get_active_id() if r_all.get_active() else None), r_all.get_active())

            btns = Gtk.Box(spacing=8, margin_top=4)
            copy = styled(Gtk.Button(label=_("Copiar")), "mm-ghost")
            copy.set_tooltip_text(_("Copia el informe al portapapeles para pegarlo donde quieras"))
            save = styled(Gtk.Button(label=_("Guardar…")), "mm-accent")

            def on_copy(_b):
                fmt, text, _whole = payload()
                Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)
                pop.popdown()
                msg = _("Copiado al portapapeles en formato «{fmt}».").format(fmt=_(EXPORTERS[fmt][2]))
                if anon_cb.get_active() and fmt != "csv":
                    msg += " " + _("Los datos personales están ocultos.")
                msg += " " + _("Pégalo con Ctrl+V.")
                if fmt == "foro":
                    msg += " " + _("En el foro, pégalo tal cual: ya va entre [code] y [/code].")
                self.notify(msg)

            def on_save(_b):
                fmt, text, whole = payload()
                pop.popdown()
                self.save_dialog(fmt, text, "" if whole else sid)
            copy.connect("clicked", on_copy)
            save.connect("clicked", on_save)
            btns.pack_end(save, False, False, 0)
            btns.pack_end(copy, False, False, 0)
            box.pack_start(btns, False, False, 0)
            box.show_all()
            pop.add(box)

        def save_dialog(self, fmt, text, sid):
            ext = EXPORTERS[fmt][1]
            dlg = Gtk.FileChooserDialog(title=_("Guardar informe"), transient_for=self,
                                        action=Gtk.FileChooserAction.SAVE)
            dlg.add_buttons(_("Cancelar"), Gtk.ResponseType.CANCEL, _("Guardar"), Gtk.ResponseType.OK)
            dlg.set_default_response(Gtk.ResponseType.OK)
            dlg.set_do_overwrite_confirmation(True)
            folder = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS) or os.path.expanduser("~")
            if os.path.isdir(folder):
                dlg.set_current_folder(folder)
            parts = ["mintmachine", {"foro": "foro", "csv": "monitor"}.get(fmt, ""), sid,
                     f"{datetime.datetime.now():%Y%m%d-%H%M}"]
            dlg.set_current_name("-".join(p for p in parts if p) + "." + ext)
            if dlg.run() == Gtk.ResponseType.OK:
                path = dlg.get_filename()
                if not path.lower().endswith("." + ext):
                    path += "." + ext
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(text)
                    self.notify(_("Informe guardado en {ruta}").format(ruta=path), path)
                except OSError as e:
                    self.message(Gtk.MessageType.ERROR, _("No se ha podido guardar el informe"), e.strerror or str(e))
            dlg.destroy()

    win = Window()
    win.show_all()
    win.toast_open.set_visible(False)
    if screenshot:   # solo para pruebas automáticas: captura la ventana y sale
        def prepare():
            if start and "+exportar" in start:
                win.export_btn.set_active(True)
            if start and "+alto" in start:
                win.resize(1180, 1450)
            if start and "+claro" in start:
                state["tema"] = "claro"
                apply_theme()
            if start and "+menu" in start:
                win.menu_btn.set_active(True)
            m = re.search(r"\+buscar=([^+]+)", start or "")
            if m:
                win.search.set_text(m.group(1))
            if start and "+detalles" in start:
                for e in win.expanders(win.stack.get_visible_child()):
                    e.set_expanded(True)
            if start and "+bajar" in start:
                adj = win.stack.get_visible_child().get_vadjustment()
                adj.set_value(adj.get_upper())
            if start and "+aviso" in start:
                win.notify(_("Informe guardado en {ruta}").format(ruta="/home/neo/Documentos/mintmachine.txt"), "/tmp")
            return False

        def shot():
            ext = win.get_window().get_frame_extents()     # desde la raíz, para que salgan los menús
            pb = Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), ext.x, ext.y, ext.width, ext.height)
            pb.savev(screenshot, "png", [], [])
            Gtk.main_quit()
            return False
        GLib.timeout_add(max(500, delay - 1200), prepare)
        GLib.timeout_add(delay, shot)
    Gtk.main()


# ───────────────────────────────── entrada ─────────────────────────────────

def main():
    set_language(next((sys.argv[i + 1] for i, x in enumerate(sys.argv[:-1]) if x in ("--idioma", "--lang")), None))
    ap = argparse.ArgumentParser(description=_("{app}: información de hardware y software del equipo. "
                                               "Solo lee: no cambia nada y no envía datos a internet.").format(app=APP))
    ap.add_argument("--texto", "--text", action="store_true", help=_("muestra el informe completo por terminal"))
    ap.add_argument("--foro", "--forum", action="store_true",
                    help=_("resumen listo para pegar en un foro (oculta los datos personales)"))
    ap.add_argument("--problema", "--problem", choices=[k for k in FORUM_TOPICS if k != "general"],
                    help=_("con --foro: resumen centrado en un problema (red, sonido, grafica, energia, lentitud)"))
    ap.add_argument("--json", action="store_true", help=_("vuelca el informe en JSON"))
    ap.add_argument("--txt", metavar=_("ARCHIVO"), help=_("guarda el informe completo en un archivo de texto"))
    ap.add_argument("--html", metavar=_("ARCHIVO"), help=_("guarda el informe en un archivo HTML"))
    ap.add_argument("--csv", metavar=_("ARCHIVO"),
                    help=_("mide durante 2 minutos y guarda el histórico del monitor en CSV"))
    ap.add_argument("--anon", action="store_true", help=_("oculta números de serie, MAC, IP, nombres y usuario"))
    ap.add_argument("--idioma", "--lang", choices=list(LANGS), help=_("idioma: es, en, fr, ja, zh"))
    ap.add_argument("--debug", action="store_true",
                    help=_("muestra qué utilidades se ejecutan y cuánto tardan (no guarda nada)"))
    ap.add_argument("--version", action="version", version=f"{APP} {VERSION}, {AUTHOR_FULL}")
    ap.add_argument("--captura", metavar="PNG", help=argparse.SUPPRESS)
    ap.add_argument("--seccion", help=argparse.SUPPRESS)
    a = ap.parse_args()
    _DEBUG[0] = a.debug

    def measured():          # tres muestras para tener uso de CPU, red y procesos reales
        for i in range(3):
            SAMPLER.tick()
            if i < 2:
                time.sleep(0.5)
        return collect_all()

    def save(path, text):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            sys.exit(_("No se ha podido guardar {ruta}: {error}").format(ruta=path, error=e.strerror))
        print(_("Informe guardado en {ruta}").format(ruta=path))

    if a.csv:
        print(_("Midiendo durante 2 minutos (Ctrl+C para guardar antes)..."), file=sys.stderr)
        try:
            for _i in range(HIST):
                SAMPLER.tick()
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        save(a.csv, to_csv())
        return
    if a.txt or a.html:
        secs = measured()
        if a.txt:
            save(a.txt, to_text(secs, a.anon))
        if a.html:
            save(a.html, to_html(secs, a.anon))
        return
    if a.json:
        print(to_json(measured(), a.anon))
        return
    if a.foro or a.problema:
        print(to_forum(measured(), True, a.problema or "general"))
        return
    if not a.texto and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        try:
            run_gui(a.anon, a.captura, a.seccion)
            return
        except (ImportError, ValueError) as e:
            print(_("No se puede abrir la interfaz gráfica ({error}). Falta el paquete python3-gi o gir1.2-gtk-3.0. "
                    "Se muestra el informe en texto.").format(error=e) + "\n", file=sys.stderr)
    print(to_text(measured(), a.anon))


if __name__ == "__main__":
    main()
