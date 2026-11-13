# MintMachine

Hardware, drivers y software de tu equipo Linux en una sola ventana, con gráficas de uso en vivo, revisión de drivers y firmware, y un diagnóstico que te señala lo que conviene mirar.

Está pensado para Linux Mint y LMDE. Funciona también en Debian, Ubuntu y derivadas. Disponible en español, inglés, francés, japonés y chino.

Autor: José Antonio Ramos Miralles «Sombra» <hola@joseantonioramos.es>. Licencia MIT.

![Pantalla de inicio](docs/captura-inicio.png)

Las capturas de `docs/` salen del banco de pruebas, que simula un portátil. Los datos que aparecen en ellas son inventados.

## Pensado para cualquiera

- **La primera pantalla enseña lo importante:** si el equipo está bien o hay algo que revisar, indicadores de uso en vivo, la ficha del equipo (con placa base y BIOS) y el estado del sistema.
- **El detalle va en la barra lateral**, agrupado en Hardware y Sistema y software. Lo que solo interesa a expertos está plegado en **Detalles técnicos** dentro de cada sección.
- **Explicaciones en lenguaje llano** bajo los apartados técnicos.
- **Buscador** (Ctrl+F): escribe «temperatura», «NVIDIA» o «batería» y la lista se queda con las secciones que lo mencionan.

## Idioma y aspecto

![Menú con idioma y aspecto](docs/captura-menu.png)

![Aspecto claro](docs/captura-claro.png)

El programa detecta el idioma del sistema y se abre en él. Se fija solo en el idioma, no en el país: `es_ES`, `es_MX` o `es_AR` → español; `en_US` o `en_GB` → inglés; `fr_FR` o `fr_CA` → francés; `ja_JP` → japonés; `zh_CN` o `zh_TW` → chino (simplificado). Si el sistema está en un idioma que MintMachine aún no tiene, sale en inglés.

En el menú (☰) se puede elegir otro idioma y el aspecto, oscuro (el de serie) o claro. La elección se guarda en `~/.config/mintmachine/config.json`, el único archivo que el programa crea en tu carpeta personal. Desde la terminal: `mintmachine --idioma en`.

Las traducciones son archivos `.po` normales en la carpeta `po/`; se pueden revisar con Poedit o Weblate. Las ha hecho una IA: conviene que las revise alguien nativo, sobre todo las de japonés y chino. Para ver bien el japonés y el chino hacen falta fuentes con esos caracteres (paquete `fonts-noto-cjk`, que Linux Mint instala al añadir esos idiomas).

## Recomendaciones seguras

MintMachine solo lee información: no cambia nada en el equipo. El diagnóstico explica qué pasa y qué hacer, y solo propone acciones seguras desde el propio sistema: instalar actualizaciones, abrir el Gestor de controladores, hacer una copia de seguridad, liberar espacio… Cuando un aviso tiene una herramienta del sistema asociada, aparece un botón para abrirla.

Nunca pide abrir el equipo ni tocar componentes. Si algo requiere una revisión física (limpieza interna, cambiar un disco, la memoria o la batería), la recomendación es acudir a un servicio técnico o al fabricante. Este aviso aparece también en el Diagnóstico, en «Acerca de» y en los informes exportados.

![Diagnóstico](docs/captura-diagnostico.png)

## Qué muestra

Veintiuna secciones en la barra lateral:

| Sección | Contenido |
|---|---|
| Inicio | Estado general, indicadores en vivo (procesador, memoria, disco, temperatura, batería), lo más importante del diagnóstico, ficha del equipo con placa base y BIOS, y sistema |
| Diagnóstico | Revisión automática: qué conviene revisar, sugerencias opcionales, qué hacer en cada caso y errores más repetidos del registro del sistema |
| Monitor en vivo | Gráficas de los últimos dos minutos de procesador, RAM y swap, red, disco, temperatura y gráfica; uso de cada hilo; procesos que más consumen |
| Procesador | Indicadores en vivo de uso total, frecuencia media y temperatura, con una barra por hilo que se actualiza cada segundo; modelo, familia y stepping, microcódigo, núcleos e hilos, núcleos P y E, cachés, juegos de instrucciones, frecuencia y uso de cada hilo, frenazos por temperatura, vulnerabilidades y mitigaciones |
| Placa base y BIOS | Fabricante y modelo del equipo y de la placa, versión y fecha de la BIOS, UEFI o legacy, Secure Boot, TPM |
| Memoria | Uso de RAM y swap, módulos instalados ranura a ranura con su fabricante (si la placa no lo da, se deduce del código JEDEC o de la referencia del módulo), ranuras libres, máximo que admite la placa, errores de memoria corregidos |
| Gráfica y pantallas | Tarjetas, driver en uso, frecuencia, enlace PCIe, OpenGL y Vulkan, formatos de vídeo que decodifica por hardware, monitores y modo en uso |
| Almacenamiento | Espacio ocupado; salud SMART, desgaste de los SSD, temperatura y horas de uso; unidades con modelo, tipo, interfaz, enlace PCIe y firmware; particiones y cifrado; TRIM |
| Red | Interfaces con driver, MAC, IP y velocidad; Wi-Fi con calidad de la señal y banda; puerta de enlace, DNS, Bluetooth |
| Sonido | Tarjetas de sonido y servidor de audio |
| Dispositivos USB | Lo que hay conectado, con velocidad, consumo y driver |
| Dispositivos PCI | Todos los dispositivos y el driver que usa cada uno |
| Periféricos | Monitores (marca, modelo, tamaño, resolución y refresco nativos, modo en uso, año de fabricación y número de serie, leídos del EDID del propio monitor), teclados, ratones, paneles táctiles, mandos, cámaras, impresoras y dispositivos Bluetooth emparejados |
| Sensores y ventiladores | Temperaturas, ventiladores en RPM y en porcentaje, quién los controla, curvas programadas, umbrales térmicos del firmware, voltajes y potencia |
| Batería y energía | Carga, salud frente a la capacidad de fábrica, ciclos, consumo, límite de carga, tipo de suspensión, hibernación; batería de ratones y teclados inalámbricos; fuentes de alimentación con USB (Corsair HXi, RMi, AXi) |
| Sistema operativo | Distribución y base, fecha de instalación, kernel, escritorio, duración del arranque y qué lo retrasa |
| Drivers y módulos | Módulos del kernel cargados, cuáles son privativos o externos, DKMS, marcas del kernel |
| Actualizaciones de drivers | Versión instalada y disponible de kernel, driver NVIDIA, Mesa, firmware, microcódigo y DKMS; firmware de BIOS, SSD y periféricos; dispositivos sin driver; firmware que falta |
| Software | Paquetes instalados, versiones de los componentes clave, actualizaciones pendientes, últimos cambios, Flatpak, programas de inicio, repositorios |
| Seguridad | Secure Boot, TPM, nivel de seguridad del firmware (HSI), cifrado de disco, cortafuegos, AppArmor, puertos abiertos, SSH |
| Puesta a punto | Lista de comprobación de lo que conviene dejar hecho tras instalar el sistema: actualizaciones, drivers y firmware, cortafuegos, instantáneas de Timeshift, TRIM de los SSD y códecs multimedia. Cada punto lleva a la herramienta del sistema que lo hace |

![Puesta a punto](docs/captura-puesta.png)

## Exportar

Un solo botón, **Exportar**, con todas las opciones:

![Exportar](docs/captura-exportar.png)

- **Qué incluir:** todo el informe o solo la sección que estás viendo.
- **Formato:**
  - **Texto**, para leerlo o adjuntarlo a un correo.
  - **Página web**, que se abre en el navegador y es cómoda para enviar a un técnico.
  - **Para un foro**, un resumen entre `[code]` y `[/code]` listo para pegar en el foro de Linux Mint. En «Pedir ayuda con» puedes elegir el problema (Wi-Fi y red, sonido, gráfica y pantallas, batería y temperatura, lentitud y arranque): el resumen lleva entonces la ficha del equipo y solo las secciones que hacen falta para ese problema, con sus detalles técnicos.
  - **JSON**, para procesar los datos con otro programa.
  - **Histórico del monitor (CSV)**, las gráficas de los últimos dos minutos para abrirlas en una hoja de cálculo.
- **Ocultar datos personales**, marcado por defecto: tapa números de serie, MAC, IP, UUID de los discos, nombre del equipo, red Wi-Fi, usuario y nombres de dispositivos Bluetooth, también cuando aparecen dentro de otros textos, como el registro del sistema.
- **Copiar** al portapapeles o **Guardar** en un archivo. Después de guardar sale un botón para abrirlo.

Los informes incluyen siempre todo, también lo que en la ventana está plegado en «Detalles técnicos».

## Botones y atajos

| | |
|---|---|
| Flecha circular, F5 o Ctrl+R | Volver a leer todo el equipo |
| Ctrl+F | Buscar en todo el informe |
| Ctrl+E | Exportar |
| Alt+1 … Alt+9 | Ir a una de las primeras nueve secciones de la lista |
| Menú (☰) | Idioma, aspecto (oscuro o claro), ocultar datos personales en pantalla (para hacer capturas), atajos de teclado, Acerca de y Desinstalar |
| F1 | Acerca de |
| Ctrl+Q | Salir |

## Monitor en vivo

![Monitor en vivo](docs/captura-monitor.png)

MintMachine toma una muestra por segundo desde que arranca y guarda los últimos dos minutos. Las gráficas se dibujan con datos reales del kernel:

- **Procesador:** uso total y una barra por hilo, calculados con `/proc/stat`.
- **Memoria:** RAM ocupada de verdad (total menos disponible) y swap.
- **Red:** bajada y subida sumando las interfaces físicas.
- **Disco:** lectura y escritura de todas las unidades, con `/proc/diskstats`.
- **Temperatura del procesador:** el sensor más caliente de la CPU.
- **Gráfica:** uso de la GPU en tarjetas AMD, NVIDIA e Intel. Intel no publica un porcentaje, así que se calcula con el tiempo que la gráfica pasa dormida (RC6); en los portátiles con dos gráficas salen las dos líneas.

Cada gráfica muestra el valor actual y el máximo de los dos últimos minutos. Debajo van dos tablas con los procesos que más procesador y más memoria gastan, y la presión del sistema (PSI): el porcentaje de tiempo que los programas pasan esperando CPU, memoria o disco.

## Monitores y fuente de alimentación

![Periféricos con los monitores](docs/captura-perifericos.png)

Los datos del monitor salen de su EDID, la ficha que el propio monitor envía por el cable. El kernel la publica en `/sys/class/drm`; con el driver privativo de NVIDIA no siempre lo hace, y entonces MintMachine la lee de `xrandr --verbose`.

La fuente de alimentación de un sobremesa no comunica al equipo su marca, modelo ni potencia, así que ningún programa puede leerlos. Las únicas que lo hacen son las fuentes «inteligentes» con cable USB interno; de ellas, Linux tiene driver para las Corsair HXi, RMi y AXi (`corsair-psu`), y MintMachine muestra su modelo, la potencia que entregan, la temperatura y el ventilador. Para saber cuál es la tuya, mira la factura o la caja; no abras el equipo para leer la etiqueta.

## Ventiladores y curvas

Esto es lo que Linux permite saber de un ventilador, y MintMachine lo enseña todo:

| Dato | De dónde sale | Disponibilidad |
|---|---|---|
| Velocidad en RPM | `fanN_input` | Casi siempre, si el kernel tiene driver para el chip |
| Potencia en % | `pwmN`, de 0 a 255 | Placas de sobremesa y bastantes portátiles |
| Quién lo controla | `pwmN_enable`: 0 al máximo, 1 manual, 2 o más automático | Donde haya `pwmN` |
| Curva temperatura → potencia | `pwmN_auto_pointM_temp` y `_pwm` | Solo si el chip la publica |
| Umbrales del firmware | Zonas térmicas ACPI | Casi todos los portátiles |

La curva que configuras en la BIOS se guarda en el chip controlador de la placa y la mayoría de drivers no deja leerla. MintMachine la muestra cuando existe: algunas placas con chips Nuvoton o ITE, los portátiles ASUS ROG con curvas personalizadas y las gráficas AMD. En el resto de equipos verás los umbrales ACPI, que dicen a qué temperatura el firmware acelera el ventilador, frena el procesador o apaga el equipo.

MintMachine solo lee. Para cambiar curvas desde Linux están CoolerControl, con interfaz gráfica, y `fancontrol`, del paquete `lm-sensors`.

## Cómo se comprueba si los drivers están al día

En Windows cada driver se instala y se actualiza por separado. En Linux casi todos viajan dentro del kernel, así que la pregunta útil es otra: si tienes el kernel más reciente que ofrece tu distribución. MintMachine revisa cuatro cosas.

1. **Paquetes.** Compara la versión instalada con la que ofrecen tus repositorios para el kernel, el driver de NVIDIA, Mesa, los paquetes de firmware, el microcódigo del procesador y los módulos DKMS.
2. **Firmware de dispositivos.** Si está `fwupd`, lista BIOS, SSD, docks y periféricos con su versión y avisa cuando el fabricante ha publicado una nueva.
3. **Dispositivos sin driver.** Señala el hardware PCI que no tiene ningún módulo cargado.
4. **Firmware que falta.** Busca en el registro del kernel los archivos que un driver pidió y no encontró.

También avisa si ya tienes un kernel más nuevo instalado y falta reiniciar, y si la lista de paquetes lleva más de diez días sin refrescarse.

La comparación se hace con los repositorios de tu sistema y sin conectar a internet. Si NVIDIA publica hoy un driver que Debian aún no ha empaquetado, MintMachine no lo sabrá.

## Diagnóstico

Además de leer, interpreta. Avisa de:

- Discos por encima del 90 % de ocupación, con sectores dañados, con fallo SMART inminente o con la vida útil estimada casi agotada.
- Errores de disco, errores de hardware del procesador y cierres por falta de memoria en el registro del kernel.
- Temperaturas altas y frenazos del procesador por calor.
- Batería desgastada.
- Servicios de systemd que no arrancaron bien.
- Un solo módulo de RAM en una placa con dos ranuras, y errores de memoria.
- Gráfica sin driver o 3D dibujado por software.
- Vulnerabilidades de CPU sin mitigar.
- Señal Wi-Fi débil.
- Versiones nuevas de drivers y firmware, actualizaciones pendientes y reinicios sin hacer.

Cada aviso dice qué hacer y, si existe, ofrece un botón para abrir la herramienta del sistema: Gestor de actualizaciones, Gestor de controladores, Copias de seguridad, Timeshift, Analizador de uso de disco, Discos, Cortafuegos, Firmware, Monitor del sistema o Informes del sistema. El botón solo aparece si la herramienta está instalada. MintMachine nunca ejecuta nada como administrador: si la herramienta necesita permisos, es ella la que pide la contraseña.

## Desinstalar

Menú (☰) → **Desinstalar MintMachine…**. Quita el programa, su icono del menú y su configuración, sin dejar rastro. El sistema pide tu contraseña, como en cualquier desinstalación; es la única vez que MintMachine hace algo con permisos de administrador, y solo si lo pides. Los informes que hayas guardado son tuyos y no se tocan.

Desde la terminal hace lo mismo: `sudo apt purge mintmachine` y después `rm -rf ~/.config/mintmachine`.

## Instalación

Descarga el `.deb` y, desde la carpeta donde lo hayas guardado:

```
sudo apt install ./mintmachine_0.5.1_all.deb
```

`apt` instala las dependencias que falten. Después lo tienes en el menú con el nombre MintMachine. Si tenías una versión anterior, este paquete la actualiza; si tenías la primera, que se llamaba Radiografía, la sustituye.

Para quitarlo, mira la sección «Desinstalar».

### Sin instalar

El programa es un único archivo de Python:

```
python3 mintmachine.py
```

Necesita `python3-gi`, `python3-gi-cairo` y `gir1.2-gtk-3.0`, que Mint y LMDE traen de serie.

## Uso desde la terminal

```
mintmachine                       abre la ventana
mintmachine --texto               informe completo por terminal
mintmachine --foro                resumen para pegar en un foro, con los datos personales ocultos
mintmachine --foro --problema red resumen centrado en un problema: red, sonido, grafica, energia o lentitud
mintmachine --txt informe.txt     guarda el informe completo en texto
mintmachine --html informe.html   guarda el informe en HTML
mintmachine --json                vuelca los datos en JSON
mintmachine --csv monitor.csv     mide dos minutos y guarda el histórico del monitor
mintmachine --texto --anon        cualquiera de las anteriores con --anon oculta los datos personales
mintmachine --idioma en           cualquiera de las anteriores en otro idioma (es, en, fr, ja, zh)
mintmachine --texto --debug       muestra además qué utilidades se ejecutan y cuánto tarda cada una
```

Sin entorno gráfico, por ejemplo por SSH, el programa pasa solo al modo texto.

## Privacidad

MintMachine no pide contraseña de administrador y no abre ninguna conexión a internet. Lee archivos de `/proc` y `/sys` y ejecuta utilidades que ya están en tu sistema. Los informes se quedan donde tú los guardes.

Al exportar, «Ocultar datos personales» viene marcado. Revisa igualmente el informe antes de publicarlo: la ocultación busca los datos que el programa conoce y los formatos habituales (MAC, IP, UUID), pero no puede adivinar cualquier dato personal que aparezca en un nombre de archivo o de dispositivo.

Lo que garantiza el código, y comprueban las pruebas automáticas en cada cambio:

- No importa ningún módulo de red. La única función de red que usa es la que devuelve el nombre del equipo.
- Lo único que escribe en tu carpeta personal es `~/.config/mintmachine/config.json`, con el idioma y el tema. No guarda históricos ni informes por su cuenta.
- Solo pide la contraseña si tú eliges «Desinstalar» en el menú.
- `--debug` escribe en la terminal el nombre de cada utilidad y sus opciones, nunca sus argumentos ni su salida, y no crea ningún archivo.
- De la configuración de Timeshift solo mira si hay instantáneas programadas; del escritorio en Wayland, solo el conector y el modo de cada pantalla.
- Con «Ocultar datos personales» se tapan también los nombres de las impresoras y los de los teclados y ratones Bluetooth, que pueden llevar el nombre de una persona.

## De dónde sale cada dato

| Dato | Fuente |
|---|---|
| Procesador | `/proc/cpuinfo`, `/proc/stat`, `/sys/devices/system/cpu` |
| Placa y BIOS | `/sys/class/dmi/id` |
| Secure Boot, TPM | `/sys/firmware/efi/efivars`, `/sys/class/tpm` |
| Módulos de RAM | `udevadm info` sobre el nodo DMI, sin root |
| Gráfica y vídeo | `lspci`, `glxinfo`, `vainfo`, `vulkaninfo`, `nvidia-smi` |
| Monitores | EDID en `/sys/class/drm` o, con NVIDIA, `xrandr --verbose` |
| Modo de pantalla en uso | X11: `xrandr`. Wayland: D-Bus del escritorio (GNOME, Cinnamon), `kscreen-doctor -j` (KDE), `wlr-randr --json` (wlroots) |
| Uso de la gráfica Intel | `/sys/class/drm/card*/gt/gt0/rc6_residency_ms` (i915) o `…/gtidle/idle_residency_ms` (xe) |
| Aplicación de cada proceso | `/proc/<pid>/cgroup` y el nombre del ejecutable |
| Perfil y gobernador de energía | `powerprofilesctl`, `/sys/firmware/acpi/platform_profile`, `/sys/devices/system/cpu/*/cpufreq` |
| Memoria comprimida | `/sys/block/zram*`, `/sys/module/zswap` |
| Seguridad del firmware (HSI) | Propiedad `HostSecurityId` del servicio fwupd, con `gdbus` |
| Puesta a punto | Datos de las demás secciones y `/etc/timeshift/timeshift.json` |
| Fuente de alimentación | `/sys/class/hwmon` (driver `corsair-psu`) |
| Discos | `lsblk`, `statvfs`, `/proc/diskstats` |
| SMART | `udisksctl dump`: el servicio UDisks ya tiene los datos leídos y los ofrece sin root |
| Desgaste de los SSD | `gdbus call` a `SmartGetAttributes` de UDisks (NVMe y SATA) |
| Enlace PCIe, frecuencia de la gráfica | `/sys/bus/pci/devices/*/current_link_*`, `/sys/class/drm/card*` |
| Red | `/sys/class/net`, `ip`, `iw` |
| Sensores y ventiladores | `/sys/class/hwmon`, `/sys/class/thermal`, `/proc/acpi/ibm/fan` |
| Batería y suspensión | `/sys/class/power_supply`, `/sys/power` |
| Procesos | `/proc/<pid>/stat` |
| Módulos del kernel | `/proc/modules`, `/sys/module`, `dkms` |
| Versiones de drivers | `dpkg-query`, `apt-cache policy` |
| Firmware | `fwupdmgr get-devices` y `get-updates` |
| Software | `apt`, `flatpak`, `/var/log/dpkg.log` |
| Servicios y registro | `systemctl`, `systemd-analyze`, `journalctl` |

Si falta alguna utilidad, la sección correspondiente sale más corta y el resto sigue funcionando. Un fallo al leer una sección tampoco tumba las demás.

## Estado del proyecto

Versión 0.5.1. Conviene saber cómo se ha probado.

El código se ha ejecutado en una máquina virtual con Ubuntu 24.04, en un contenedor con los paquetes de LMDE 7 y contra un portátil simulado: un `/sys` falso con placa, batería, sensores, ventiladores con PWM y curva, monitor, Wi-Fi y USB, más versiones de pega de `lspci`, `lsblk`, `udisksctl`, `gdbus`, `fwupdmgr`, `apt-cache` y compañía. Con eso se han comprobado todos los analizadores, las gráficas con carga real de CPU y disco, el refresco en vivo, la búsqueda, los botones, la ocultación de datos personales y los cinco formatos de exportación.

Lo que falta es rodaje en hardware real. Los formatos del banco de pruebas están escritos a mano a partir de la documentación de cada herramienta, y un equipo de verdad siempre trae alguna rareza. Si una sección sale vacía o con datos raros en tu máquina, abre una incidencia y pega el resultado de `mintmachine --texto --anon`.

### Límites conocidos

- **Curvas de la BIOS.** Solo se ven cuando el driver del chip las publica. Está explicado más arriba.
- **Drivers más nuevos que los del repositorio.** La comparación no sale de tu sistema.
- **SMART y desgaste de los NVMe.** Necesita UDisks 2.10 o posterior. Linux Mint 22 y LMDE 7 lo traen; LMDE 6 trae la 2.9 y solo dará SMART de discos SATA.
- **Traducciones hechas por IA.** Inglés y francés deberían ser correctos; japonés y chino conviene que los revise alguien nativo.
- **Desgaste de los SSD sin probar en hardware real.** La respuesta de UDisks está escrita a partir de su documentación. Si en tu SSD la columna «Vida útil» sale vacía, abre una incidencia.
- **Detalle de SMART.** Se muestra estado, temperatura, horas y sectores dañados. La tabla completa de atributos sigue pidiendo `sudo smartctl -a`.
- **Registro del kernel.** Para leerlo, tu usuario debe pertenecer al grupo `adm`. El primer usuario de Mint suele estar.
- **Uso de la GPU en Intel.** Es una estimación a partir del tiempo de reposo de la gráfica, sin probar todavía en hardware real. El uso por programa sigue sin mostrarse.
- **Latencias de la RAM.** Los tiempos del SPD necesitan acceso al bus I2C con root.
- **Wayland.** El modo de pantalla en uso se pide al escritorio: GNOME y Cinnamon por D-Bus, KDE Plasma con `kscreen-doctor` y Sway, Hyprland y similares con `wlr-randr`. Está comprobado con respuestas de ejemplo, no en cada escritorio real; en otros compositores sale la ficha del monitor sin el modo en uso.
- **Aplicaciones del Monitor.** GNOME, KDE, Flatpak y Snap dan el nombre exacto de cada aplicación; en Cinnamon se agrupa por ejecutable, así que varios programas hechos en Python salen juntos como `python3`.
- **Distribuciones sin `.deb`.** El programa funciona, pero el inventario de paquetes y la revisión de drivers salen vacíos.

## Cómo está hecho

Un archivo, `mintmachine.py`, con cinco partes:

1. **Utilidades.** `read()` lee un archivo y devuelve cadena vacía si falla. `run()` ejecuta una orden con tiempo límite e idioma fijo, y también devuelve cadena vacía si la orden no existe.
2. **Muestreador.** La clase `Sampler` toma una muestra por segundo y guarda el histórico que pintan las gráficas.
3. **Recopiladores.** Una función `sec_*` por sección. Cada una devuelve bloques de ocho tipos: `kv` (pares clave y valor), `table`, `bars`, `chart`, `cores`, `note`, `status` y `findings`. Con `adv=True`, un bloque es detalle técnico y la ventana lo pliega; con `help="..."`, lleva una explicación en lenguaje llano.
4. **Exportadores.** `to_text`, `to_html`, `to_json`, `to_forum` y `to_csv`, registrados en `EXPORTERS`.
5. **Interfaz GTK 3.** Pinta los mismos bloques; las gráficas se dibujan con cairo. La lectura inicial va en un hilo aparte para que la ventana no se congele.

Los textos se escriben en español dentro de `_()`; los que llevan datos, como plantilla: `_("Quedan {n} libres").format(n=...)`. Los títulos, claves, cabeceras, notas y valores fijos que se pasan a `kv`, `table`, `bars`, `note` y `section` se traducen solos. Para añadir o cambiar textos: se edita el código, se regenera `po/mintmachine.pot` y se completan los `.po` (`msgmerge` sirve para eso).

Los recopiladores comparten un objeto `Ctx`. Con `ctx.flag(nivel, área, texto, qué_hacer, acción)` cualquiera de ellos deja un aviso que después recoge el Diagnóstico. `acción` es una clave de `ACTIONS`, la lista de herramientas del sistema que se pueden abrir. **Norma para los avisos:** «qué hacer» solo puede proponer acciones seguras desde el sistema; cualquier revisión física se deriva a un servicio técnico o al fabricante.

Los valores envueltos en `Sens(...)` se tapan al ocultar los datos personales, y también se buscan dentro del resto de textos del informe.

### Añadir una sección

```python
def sec_ejemplo(ctx):
    filas = []
    for p in sorted(glob.glob("/sys/class/leds/*")):
        filas.append((os.path.basename(p), read(p + "/brightness")))
    return section("leds", "Luces", [
        table("LED del equipo", ["Nombre", "Brillo"], filas),
    ])
```

Después se registra en `COLLECTORS`, `ORDER` y `TITLES`. Con eso aparece en la ventana, en el modo texto y en todos los formatos de exportación. Si quieres que se refresque sola, añade su identificador a `LIVE`.

## Construir el paquete .deb

```
packaging/build-deb.sh
```

El paquete queda en `dist/`. Solo hace falta `dpkg-deb`. La versión se toma de la variable `VERSION` de `mintmachine.py`. El campo «Maintainer» del paquete lleva solo «MintMachine», sin datos personales: dpkg lo exige y, si falta, apt muestra un aviso cada vez que se usa.

En GitHub, la acción `.github/workflows/ci.yml` prueba el programa y construye el `.deb` en cada cambio. Al publicar una etiqueta `v0.5.1`, adjunta el `.deb` a esa versión.

## Pruebas

El banco de pruebas monta un `/sys` simulado dentro de un espacio de montajes privado, así que el `/sys` real de tu equipo no se toca. Necesita root por el montaje:

```
sudo tests/run.sh texto
sudo tests/run.sh texto --anon
sudo tests/run.sh html /tmp/informe.html
sudo tests/run.sh foro /tmp/foro.txt --anon        (también json y csv)
sudo -E tests/run.sh gui /tmp/captura.png resumen   (captura de la ventana y sale)
```

Además hay pruebas unitarias, que no necesitan root: comprueban los analizadores (EDID, pantallas en Wayland, aplicaciones, gráfica Intel), la ocultación de datos personales, que el código no use la red y que las traducciones estén completas.

```
python3 -m pytest tests/test_unidad.py      (sin pytest: python3 tests/test_unidad.py)
```

Para probar un caso nuevo, por ejemplo un ventilador parado o un disco con fallo SMART, cambia los valores en `tests/simular_portatil.py` y mira qué dice el Diagnóstico. Con `MM_IDIOMA=en` (o `fr`, `ja`, `zh`) delante, el banco de pruebas sale en ese idioma; con `MM_FUENTE=1`, simula una fuente Corsair con USB.

## Publicarlo en GitHub

1. Crea un repositorio vacío en GitHub, sin README ni licencia: ya van incluidos.
2. Desde la carpeta del proyecto:

```
git init
git add .
git commit -m "MintMachine 0.5.1"
git branch -M main
git remote add origin https://github.com/TU-USUARIO/mintmachine.git
git push -u origin main
git tag v0.5.1
git push origin v0.5.1
```

3. La acción de GitHub construye el `.deb` y lo adjunta a la versión `v0.5.1`. Si prefieres hacerlo a mano, en Releases crea la versión `v0.5.1` y adjunta `mintmachine_0.5.1_all.deb`.
4. Cuando tengas la dirección del repositorio, añádela a `data/mintmachine.metainfo.xml` con `<url type="homepage">…</url>`.

Las incidencias usan las plantillas de `.github/ISSUE_TEMPLATE`, que piden el informe para foros con los datos personales ocultos.

Las carpetas `build/` y `dist/` están en `.gitignore`. El `.deb` se sube como archivo de la versión publicada y se queda fuera del historial.

Un aviso sobre el nombre: «Linux Mint» es una marca de su proyecto. Deja claro en la descripción del repositorio que MintMachine es un programa independiente.

## Ideas para las siguientes versiones

- Uso de la gráfica por proceso (fdinfo de DRM, sin root para tus propios procesos).
- Dibujar la curva del ventilador como gráfica, con un punto que marque dónde está ahora.
- Comprobación opcional contra internet: último kernel estable y último driver de NVIDIA publicados.
- Alertas de escritorio cuando una temperatura o un disco cruzan un umbral.
- Guardar el histórico de las gráficas entre sesiones.
- Comparar dos informes JSON para ver qué ha cambiado en el equipo.
- Uso de GPU por proceso y consumo eléctrico del procesador (RAPL), que hoy piden root.
- Icono en la bandeja con temperatura y uso.
- Repartir el código en módulos y cargar cada sección al abrirla, para que arranque más rápido.
- Asistente «¿por qué va lento mi equipo?», puntuación de salud por áreas e informe para vender o comprar un equipo de segunda mano.
- Paquete Flatpak.

## Licencia

MIT, © 2026 José Antonio Ramos Miralles «Sombra». Puedes usarlo, modificarlo y redistribuirlo, también en proyectos comerciales, manteniendo el aviso de copyright. El texto completo está en `LICENSE`.

Como dice la licencia, el programa se ofrece tal cual, sin garantías. Sus recomendaciones son orientativas: ante cualquier duda sobre el hardware, consulta con un servicio técnico o con el fabricante.
