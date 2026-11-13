# Cambios

## 0.5.3 (13/11/2026)

- El menú de Linux Mint mostraba el icono genérico de programa en lugar del de MintMachine. El paquete instala ahora el icono también en mapa de bits (de 16 a 256 píxeles) y en `/usr/share/pixmaps`, y al instalar y al quitar actualiza la caché de iconos y la base de datos de aplicaciones.

## 0.5.2 (13/11/2026)

- Corregida la raya de colores entre la barra superior y el contenido. Con el compositor del escritorio activo (Cinnamon), la fila de píxeles del borde de la barra quedaba transparente y dejaba ver lo que había detrás de la ventana. Ahora el borde es opaco.

## 0.5.1 (13/11/2026)

- **Procesador:** indicadores en vivo de uso total, frecuencia media y temperatura, y una barra por hilo; se actualizan cada segundo.
- **Memoria:** el fabricante de cada módulo ya no sale como «Unknown». Si la placa no lo da por su nombre, se lee su código JEDEC o se deduce de la referencia del módulo (G.Skill, Corsair, Kingston, Crucial, Samsung, SK hynix, Micron, ADATA, TeamGroup, Patriot), y se indica que es una deducción.
- **Barra superior:** bajo el nombre del programa se lee «MintMachine solo lee información. No cambia nada en tu equipo y no envía datos a internet». Esa nota sale del final del Inicio.
- Fuera la línea discontinua que el tema Mint-Y dibuja en el borde del contenido al desplazarse.
- Fuera los botones «i» de los campos.
- **Tema claro** más apagado, para que no deslumbre.

## 0.5.0 (13/11/2026)

**Datos nuevos**
- **Pantallas en Wayland:** el modo en uso (resolución, refresco y escala) se pide al escritorio: GNOME y Cinnamon por D-Bus, KDE Plasma con `kscreen-doctor`, y Sway, Hyprland y similares con `wlr-randr`. En X11 se sigue usando `xrandr`.
- **Uso de la gráfica Intel** en el Monitor en vivo y en el CSV, calculado con el tiempo de reposo (RC6) que publica el kernel, sin permisos de administrador.
- **Aplicaciones que más consumen:** el Monitor suma los procesos de cada aplicación (un navegador abre decenas).
- **Energía:** perfil del fabricante, gobernador del procesador y preferencia entre ahorro y rendimiento; sugerencia si el equipo está enchufado con el perfil de ahorro.
- **Memoria comprimida:** zram y zswap.
- **Seguridad del firmware (HSI)**, leída del servicio fwupd del propio equipo.

**Más fácil de usar**
- Nueva sección **Puesta a punto:** lista de comprobación tras instalar el sistema (actualizaciones, drivers y firmware, cortafuegos, instantáneas de Timeshift, TRIM y códecs), con botón a la herramienta de cada punto.
- **Pedir ayuda con un problema:** el formato «Para un foro» puede centrarse en Wi-Fi y red, sonido, gráfica, batería y temperatura o lentitud. En la terminal, `--foro --problema red`.
- El Diagnóstico lista las **utilidades opcionales que faltan**, con el paquete que las trae y qué se deja de ver sin ellas.
- `--debug`: muestra en la terminal qué utilidades se ejecutan y cuánto tardan.

**Privacidad**
- Al ocultar datos personales se tapan también los nombres de las impresoras y los de los periféricos Bluetooth allí donde antes se veían: en la lista de teclados y ratones y en el título de su batería.
- Ninguna de las funciones nuevas usa internet, pide contraseña ni guarda nada en disco. `--debug` no muestra argumentos ni salidas de las utilidades.
- Pruebas automáticas que vigilan que el código no importe módulos de red y que los datos marcados como sensibles no salgan en los informes anónimos.

**Proyecto**
- Pruebas unitarias en `tests/test_unidad.py` (20 pruebas), añadidas a la acción de GitHub.
- Traducciones de todo lo nuevo en inglés, francés, japonés y chino.

## 0.4.0 (13/11/2026)

- **Idiomas:** español, inglés, francés, japonés y chino. Se elige solo según el idioma del sistema (cualquier variante de país) y se puede cambiar en el menú; si el idioma del sistema no está disponible, sale en inglés. Traducciones en `po/*.po`.
- **Diseño nuevo:** tema oscuro por defecto y tema claro, tarjetas, degradados, iconos propios en la barra lateral, indicadores circulares en el Inicio, gráficas suaves con degradado y avisos flotantes.
- **Inicio:** «Equipo» en lugar de «Tu equipo», con la placa base y la BIOS incluidas.
- **Monitores:** nueva tabla en Periféricos (y en Gráfica y pantallas) con marca, modelo, tamaño, resolución y refresco nativos, modo en uso, año y número de serie. Con el driver de NVIDIA el EDID se lee de `xrandr`.
- **Fuente de alimentación:** modelo, potencia, temperatura y ventilador de las fuentes Corsair con USB. En el resto de sobremesas, una nota explica por qué no se puede leer.
- **Batería de periféricos:** el nivel («Full», «Low»…) sale traducido.
- **Información (i):** ahora es un botón que muestra la explicación al pulsarlo, además de al pasar el ratón.
- **«by Sombra»** junto al nombre del programa, arriba en la barra lateral.
- **Desinstalar** desde el menú: quita el programa, su icono y su configuración, sin dejar rastro. Pide la contraseña del sistema.
- **Paquete:** la descripción ya no menciona otros programas y el campo «Maintainer» no lleva datos personales.

## 0.3.0 (13/11/2026)

Autor: José Antonio Ramos Miralles «Sombra» <hola@joseantonioramos.es>.

**Más fácil de usar**
- Nueva pantalla de **Inicio**: estado general del equipo, lo más importante del diagnóstico, ficha del equipo, uso en vivo (procesador, memoria, disco, temperatura y batería) y sistema.
- Barra lateral agrupada en Hardware y Sistema y software.
- Los datos para expertos van plegados en **Detalles técnicos** en cada sección. Las exportaciones los incluyen siempre.
- Explicaciones en lenguaje llano bajo los apartados técnicos y al pasar el ratón por los campos marcados con ⓘ.
- **Búsqueda** en todo el informe (Ctrl+F), atajos de teclado (F5, Ctrl+E, Ctrl+Q, Alt+1…9, F1) y ventana Acerca de.
- Un solo botón **Exportar** con todas las opciones: todo el informe o solo la sección visible; texto, página web, resumen para foros, JSON o histórico del monitor en CSV; ocultar datos personales (marcado por defecto); copiar o guardar. Tras guardar, botón para abrir el archivo.

**Diagnóstico**
- Cada aviso explica qué pasa y qué hacer, y separa lo que conviene revisar de las sugerencias opcionales.
- Las recomendaciones se limitan a acciones seguras desde el sistema. Nunca se pide abrir el equipo: las revisiones físicas se derivan a un servicio técnico o al fabricante. Aviso legal en el Diagnóstico, en Acerca de y en los informes.
- Botones que abren la herramienta adecuada del sistema: Gestor de actualizaciones, Gestor de controladores, Copias de seguridad, Analizador de uso de disco, Cortafuegos, Monitor del sistema…
- Ya no se recomienda `sudo sensors-detect`, revisar cables o pasta térmica, ni cambiar piezas.

**Datos nuevos**
- Desgaste de los SSD NVMe (vida útil usada, bloques de reserva, errores de datos) y vida restante de los SSD SATA que la publican, pedidos a UDisks sin permisos de administrador.
- Enlace PCIe actual y máximo de la gráfica y de los SSD NVMe.
- Frecuencia actual y máxima de la gráfica en Intel y AMD.
- Calidad de la señal Wi-Fi y aviso si es débil.
- Memoria: módulos y tipo en la ficha del equipo; tamaño de la swap.

**Correcciones**
- Ocultar datos personales tapaba solo los campos marcados: ahora también los busca dentro de cualquier texto (registro del sistema, parámetros de arranque, rutas con el nombre de usuario) y tapa MAC, IP, UUID, nombre del equipo, usuario y nombres de dispositivos Bluetooth.
- El porcentaje de disco ocupado se calcula como `df` (antes no contaba el espacio reservado de ext4 y salía más bajo).
- Los números llevan coma decimal.
- Los nombres de procesos ya no salen recortados a 15 letras.
- La comparación de versiones de kernel ya no puede fallar al mezclar números y texto.
- El aviso de llvmpipe ya no salta en máquinas virtuales; un servicio caído es una sugerencia, no un aviso.
- Si no se puede guardar un informe desde la terminal, el mensaje es claro y no un error de Python.

**Proyecto**
- Licencia y paquete a nombre de José Antonio Ramos Miralles «Sombra».
- Metadatos AppStream, plantillas de incidencias de GitHub y una acción de GitHub que prueba el programa y construye el `.deb`.
- Nuevas opciones de terminal: `--foro` y `--csv`. El JSON lleva un número de esquema (`"esquema": 2`).

## 0.2.0 (13/11/2026)

El programa pasa a llamarse MintMachine. Autor: Sombra.

- Monitor en vivo: gráficas de procesador, RAM y swap, red, disco, temperatura y gráfica, uso por hilo y procesos que más consumen.
- Ventiladores: porcentaje de potencia, modo de control, curvas programadas cuando el chip las publica, umbrales térmicos ACPI y mecanismos de refrigeración.
- Actualizaciones de drivers: versión instalada y disponible de kernel, NVIDIA, Mesa, firmware, microcódigo y DKMS; firmware de dispositivos con fwupd; dispositivos sin driver; firmware que falta.
- Salud SMART de los discos sin root, a través de UDisks.
- Botón Exportar: toda la información del panel a un archivo de texto, HTML o JSON. Opción `--txt` en la terminal.
- Nueva sección Periféricos: teclados, ratones, cámaras, impresoras y Bluetooth.
- Decodificación de vídeo por hardware y Vulkan; suspensión, hibernación y límite de carga; servicios que retrasan el arranque; errores de memoria; frenazos del procesador por calor.
- El diagnóstico lee el registro del kernel: errores de disco, errores de hardware y cierres por falta de memoria.
- El informe de texto ya no recorta columnas largas.

## 0.1.0 (13/11/2026)

Primera versión, con el nombre Radiografía.

- Interfaz GTK 3 con 17 secciones y refresco en vivo de procesador, memoria y sensores.
- Diagnóstico automático, informes en HTML, texto y JSON, opción de ocultar datos sensibles.
- Modo terminal y paquete .deb.
