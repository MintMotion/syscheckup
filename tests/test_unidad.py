"""Pruebas unitarias de MintMachine. No necesitan root ni tocan el sistema.

    python3 -m pytest tests/test_unidad.py        (o, sin pytest:  python3 tests/test_unidad.py)

Comprueban las funciones que interpretan datos (EDID, pantallas en Wayland, aplicaciones,
gráfica Intel), la ocultación de datos personales y las traducciones. El banco de pruebas
del portátil simulado (tests/run.sh) sigue siendo la prueba de conjunto.
"""
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import mintmachine as mm  # noqa: E402

mm.set_language("es")
SRC = open(os.path.join(ROOT, "mintmachine.py"), encoding="utf-8").read()


# ───────────────────────────── privacidad ─────────────────────────────

def test_no_hay_codigo_de_red():
    """El programa no abre conexiones: no importa ningún módulo de red."""
    for mod in ("urllib", "requests", "http.client", "ftplib", "smtplib", "telnetlib", "xmlrpc", "asyncio"):
        assert not re.search(r"^\s*(import|from)\s+" + re.escape(mod) + r"\b", SRC, re.M), mod
    usos = set(re.findall(r"\bsocket\.(\w+)", SRC))
    assert usos <= {"gethostname"}, usos           # socket solo se usa para saber el nombre del equipo


def test_no_se_ejecuta_nada_como_root_salvo_desinstalar():
    assert SRC.count('"pkexec"') == 1              # solo en uninstall_cmd, que el usuario pide a mano
    assert '"sudo"' not in SRC


def test_scrub_tapa_mac_ip_uuid():
    t = mm.scrub("eth0 f4:7b:09:aa:bb:cc 192.168.1.37 fe80::f67b:9ff:feaa:bbcc "
                 "9f0c2b6e-1d5a-4c7b-8e21-aa00bb11cc22 127.0.0.1")
    for dato in ("f4:7b:09:aa:bb:cc", "192.168.1.37", "fe80::f67b:9ff:feaa:bbcc", "9f0c2b6e"):
        assert dato not in t
    assert "127.0.0.1" in t


def test_valor_sensible_se_oculta_y_se_busca_en_otros_textos():
    serie = mm.Sens("ZX81SERIE77")
    assert mm.show(serie, anon=True) == "(oculto)"
    assert mm.show(serie, anon=False) == "ZX81SERIE77"
    assert "ZX81SERIE77" not in mm.show("disco ZX81SERIE77 montado", anon=True)


def test_secret_tapa_usuario_y_carpeta():
    mm.secret("/home/pruebas_usuario")
    assert "pruebas_usuario" not in mm.show("ruta /home/pruebas_usuario/Documentos", anon=True)


def test_la_traza_de_debug_no_muestra_argumentos():
    viejo, mm._DEBUG[0], sys.stderr = sys.stderr, True, io.StringIO()
    try:
        mm._trace(["gdbus", "call", "--system", "/org/UDisks2/drives/SERIE_SECRETA_123"], 0.0, "bien")
        salida = sys.stderr.getvalue()
    finally:
        mm._DEBUG[0], sys.stderr = False, viejo
    assert "gdbus" in salida and "--system" in salida
    assert "SERIE_SECRETA_123" not in salida


def test_resumen_para_foro_por_problema():
    secs = [{"id": i, "title": i.upper(), "blocks": [mm.kv("Datos", [("Clave", mm.Sens("SECRETO-1234"))]),
                                                    mm.kv("Técnico", [("Detalle", "valor")], adv=True)]}
            for i in ("resumen", "red", "audio", "discos", "actualizaciones")]
    out = mm.to_forum(secs, True, "red")
    assert out.startswith("[code]\n") and out.rstrip().endswith("[/code]")
    assert "Problema: Wi-Fi y red" in out
    assert "AUDIO" not in out and "DISCOS" not in out and "ACTUALIZACIONES" in out
    assert "Detalle" in out                        # en la sección del problema van también los detalles técnicos
    assert "SECRETO-1234" not in out
    general = mm.to_forum(secs, True)
    assert "Problema:" not in general and "Detalle" not in general


# ───────────────────────────── pantallas ─────────────────────────────

def _edid():
    b = bytearray(128)
    b[:8] = b"\x00\xff\xff\xff\xff\xff\xff\x00"
    b[8], b[9] = 0x09, 0xE5                         # «BOE»
    b[16], b[17], b[20], b[21], b[22] = 12, 32, 0x80, 31, 17
    b[54:72] = bytes([0x38, 0x36, 0x80, 0xA0, 0x70, 0x38, 0x20, 0x40, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    b[72:77] = bytes([0, 0, 0, 0xFC, 0])
    b[77:90] = b"PANEL-14\n    "
    b[90:95] = bytes([0, 0, 0, 0xFF, 0])
    b[95:108] = b"SN12345\n     "
    return bytes(b)


def test_parse_edid():
    e = mm.parse_edid(_edid())
    assert e["code"] == "BOE" and e["mfg"] == "BOE" and e["year"] == 2022
    assert e["name"] == "PANEL-14" and e["serial"] == "SN12345"
    assert e["res"] == "1920 × 1080" and (e["w"], e["h"]) == (31, 17)
    assert mm.parse_edid(b"basura") == {}


def test_numero_de_serie_del_monitor_es_sensible():
    e = dict(mm.parse_edid(_edid()), port="eDP-1")
    fila = mm.monitor_rows([e])[0]
    assert isinstance(fila[-1], mm.Sens) and mm.show(fila[-1], True) == "(oculto)"


def test_wlr_randr():
    txt = json.dumps([{"name": "eDP-1", "enabled": True, "scale": 1.5, "serial": "NO-USAR",
                       "modes": [{"width": 1920, "height": 1080, "refresh": 59.999, "current": True},
                                 {"width": 1280, "height": 720, "refresh": 60.0, "current": False}]},
                      {"name": "HDMI-A-1", "enabled": False, "modes": []}])
    out = mm.parse_wlr_randr(txt)
    assert out == {"eDP-1": {"mode": "1920 × 1080", "hz": "60 Hz", "primary": False, "scale": "1,5"}}
    assert mm.parse_wlr_randr("no es json") == {}


def test_kscreen_doctor():
    txt = json.dumps({"outputs": [{"name": "DP-1", "enabled": True, "connected": True, "currentModeId": "7",
                                   "priority": 1, "scale": 1,
                                   "modes": [{"id": "3", "size": {"width": 1280, "height": 720}, "refreshRate": 60},
                                             {"id": "7", "size": {"width": 2560, "height": 1440},
                                              "refreshRate": 143.97}]}]})
    assert mm.parse_kscreen(txt) == {"DP-1": {"mode": "2560 × 1440", "hz": "144 Hz", "primary": True}}


def test_display_config_de_mutter_y_muffin():
    spec = ("eDP-1", "BOE", "0x0931", "SERIE-QUE-NO-SE-USA")
    modos = [("1920x1080@60", 1920, 1080, 60.0, 1.0, [1.0, 2.0], {"is-current": True, "is-preferred": True}),
             ("1280x720@60", 1280, 720, 60.0, 1.0, [1.0], {})]
    state = (5, [(spec, modos, {"is-builtin": True})], [(0, 0, 2.0, 0, True, [spec], {})], {})
    out = mm.parse_display_config(state)
    assert out == {"eDP-1": {"mode": "1920 × 1080", "hz": "60 Hz", "primary": True, "scale": "2"}}
    assert "SERIE" not in json.dumps(out)
    assert mm.parse_display_config(None) == {}


# ───────────────────────── aplicaciones y gráfica ─────────────────────────

def test_app_name():
    base = "0::/user.slice/user-1000.slice/user@1000.service/app.slice/"
    assert mm.app_name(base + "app-gnome-firefox-4321.scope", "x") == "firefox"
    assert mm.app_name(base + "app-org.gnome.Terminal-9f3a.scope", "x") == "org.gnome.Terminal"
    assert mm.app_name(base + "app-flatpak-com.spotify.Client-1234.scope", "x") == "com.spotify.Client"
    assert mm.app_name(base + r"app-gnome-code\x2doss-777.scope", "x") == "code-oss"
    assert mm.app_name(base + "snap.firefox.firefox-0a1b2c3d.scope", "x") == "firefox"
    assert mm.app_name("0::/system.slice/NetworkManager.service", "x") == "NetworkManager"
    # ni el número de usuario ni el nombre de una instancia (una VPN, por ejemplo) deben salir
    assert mm.app_name("0::/system.slice/system-openvpn.slice/openvpn@oficina_de_ana.service", "x") == "openvpn"
    assert mm.app_name("0::/user.slice/user-1000.slice/session-2.scope", "firefox") == "firefox"
    assert mm.app_name("0::/user.slice/user-1000.slice/user@1000.service", "systemd") == "systemd"
    assert mm.app_name("", "bash") == "bash"


def test_uso_de_la_grafica_intel():
    s = mm.Sampler()
    s._rc6 = "/falso/rc6_residency_ms"
    reloj, lecturas = [100.0], [5000]
    real_int, real_mono = mm.read_int, mm.time.monotonic
    mm.read_int = lambda p, default=None: lecturas[0]
    mm.time.monotonic = lambda: reloj[0]
    try:
        s._gpu_intel()                              # primera lectura: solo guarda la referencia
        assert not s.h["igpu"]
        reloj[0], lecturas[0] = 101.0, 5750         # 750 ms dormida de 1000: 25 % de uso
        s._gpu_intel()
        assert abs(s.h["igpu"][-1] - 25.0) < 0.01
        reloj[0], lecturas[0] = 102.0, 10           # el contador ha dado la vuelta: se descarta
        s._gpu_intel()
        assert len(s.h["igpu"]) == 1
    finally:
        mm.read_int, mm.time.monotonic = real_int, real_mono


def test_timeshift():
    real = mm.read
    try:
        mm.read = lambda p, default="": '{"backup_device_uuid": "abc", "schedule_daily": "true"}'
        assert mm.timeshift_scheduled() is True
        mm.read = lambda p, default="": '{"backup_device_uuid": "", "schedule_daily": "true"}'
        assert mm.timeshift_scheduled() is False
        mm.read = lambda p, default="": ""
        assert mm.timeshift_scheduled() is None
    finally:
        mm.read = real


def test_un_recopilador_que_falla_no_tumba_el_informe():
    def roto(_ctx):
        raise RuntimeError("hardware raro")
    sec = mm.safe("cpu", roto, mm.Ctx())
    assert sec["id"] == "cpu" and sec["blocks"][0]["type"] == "note"


def test_fabricante_de_la_memoria():
    assert mm.ram_vendor("G Skill Intl", "F4-3200C16-16GVK") == "G Skill Intl"
    assert mm.ram_vendor("04CD", "") == "G.Skill"
    assert mm.ram_vendor("CD04", "") == "G.Skill"
    assert mm.ram_vendor("Bank 5, Hex 0xCD", "") == "G.Skill"
    assert mm.ram_vendor("859B00000000", "") == "Crucial"
    assert mm.ram_vendor("Unknown", "F4-3600C16D-32GTZNC") == "G.Skill (según la referencia)"
    assert mm.ram_vendor("Unknown", "CMK32GX4M2E3200C16") == "Corsair (según la referencia)"
    assert mm.ram_vendor("Unknown", "KF432C16BB/8") == "Kingston (según la referencia)"
    assert mm.ram_vendor("0000", "ABC123") == "La placa no lo indica"
    assert mm.ram_vendor("Undefined", "") == "La placa no lo indica"


def test_firmware_que_falta():
    lineas = ["iwlwifi 0000:04:00.0: Direct firmware load for iwl-debug-yoyo.bin failed with error -2",
              "Bluetooth: hci0: Direct firmware load for intel/ibt-0040-0041.sfi failed with error -2",
              "amdgpu 0000:0b:00.0: firmware: failed to load amdgpu/green_sardine_ta.bin (-2)"]
    viejo = mm.run
    mm.run = lambda *a, **k: "\n".join(lineas)
    mm.clear_cache()
    try:
        log = mm.kernel_log()
    finally:
        mm.run = viejo
        mm.clear_cache()
    filas = {f: r for f, *r in mm.firmware_rows(log, {})}
    assert filas["iwl-debug-yoyo.bin"] == ["iwlwifi", "Wi-Fi Intel", "", True]
    assert filas["intel/ibt-0040-0041.sfi"] == ["Bluetooth", "Bluetooth", "firmware-iwlwifi", False]
    assert filas["amdgpu/green_sardine_ta.bin"] == ["amdgpu", "Gráfica AMD", "firmware-amd-graphics", False]
    assert mm.firmware_rows(log, {"linux-firmware": "x"})[2][3] == "linux-firmware"


def test_registro_de_secciones_coherente():
    assert set(mm.COLLECTORS) == set(mm.ORDER)
    assert set(mm.COLLECTORS) | {"resumen", "diagnostico"} == set(mm.TITLES)
    for tema, (_nombre, secs) in mm.FORUM_TOPICS.items():
        assert not secs or set(secs) <= set(mm.TITLES), tema


# ───────────────────────────── traducciones ─────────────────────────────

def _po(lang):
    return mm.parse_po(os.path.join(ROOT, "po", lang + ".po"))


def test_todos_los_idiomas_traducen_lo_mismo():
    cats = {os.path.basename(p)[:-3]: _po(os.path.basename(p)[:-3]) for p in glob.glob(os.path.join(ROOT, "po", "*.po"))}
    assert set(cats) == set(mm.LANGS) - {"es"}
    claves = set(cats["en"])
    for lang, cat in cats.items():
        assert set(cat) == claves, (lang, sorted(set(cat) ^ claves)[:5])


def test_las_plantillas_conservan_sus_huecos():
    hueco = re.compile(r"\{(\w*)[^}]*\}")
    for lang in mm.LANGS:
        if lang == "es":
            continue
        for k, v in _po(lang).items():
            assert sorted(hueco.findall(k)) == sorted(hueco.findall(v)), (lang, k)


def test_textos_nuevos_traducidos():
    """Los textos fijos de las funciones añadidas en la 0.5.0 existen en todos los idiomas."""
    nuevos = ["Puesta a punto", "Lista de comprobación", "Aplicaciones que más consumen", "Memoria comprimida",
              "Seguridad del firmware (HSI)", "Pedir ayuda con:", "Problema: {tema}", "Wi-Fi y red",
              "Utilidades opcionales que no están instaladas", "{n} de {m} puntos en orden",
              mm.READONLY, "Frecuencia media", "{marca} (según la referencia)", "Código JEDEC {codigo}",
              "La placa no lo indica", "Falta firmware que pidió un driver: {lista}.", "Paquete que lo trae",
              "Wi-Fi Intel", "Red por cable Realtek", mm.FW_OPTIONAL["iwl-debug-yoyo.bin"]]
    for lang in mm.LANGS:
        if lang != "es":
            cat = _po(lang)
            for t in nuevos:
                assert cat.get(t), (lang, t)


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_") and callable(fn):
            try:
                fn()
                print("bien  ", nombre)
            except Exception as e:       # AssertionError incluido
                fallos += 1
                print("FALLO ", nombre, "→", type(e).__name__, e)
    sys.exit(1 if fallos else 0)
