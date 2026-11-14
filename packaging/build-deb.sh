#!/bin/sh
# Construye dist/syscheckup_<versión>_all.deb. Solo necesita dpkg-deb.
#   packaging/build-deb.sh            (MAINTAINER="Nombre <correo>" para cambiar el mantenedor)
set -e
cd "$(dirname "$0")/.."

VERSION=$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' syscheckup.py)
# dpkg exige el campo Maintainer: sin él, apt mostraría un aviso en cada instalación.
MAINTAINER=${MAINTAINER:-"SysCheckup"}
PKG="build/syscheckup_${VERSION}_all"

rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" dist
install -Dm755 syscheckup.py           "$PKG/usr/bin/syscheckup"
# El paquete usa el Python del sistema, que es el que tiene python3-gi; con «env» podría
# arrancar un Python de conda o pyenv sin GTK.
sed -i '1s|^#!/usr/bin/env python3$|#!/usr/bin/python3|' "$PKG/usr/bin/syscheckup"
install -Dm644 data/syscheckup.desktop "$PKG/usr/share/applications/syscheckup.desktop"
install -Dm644 data/syscheckup.svg     "$PKG/usr/share/icons/hicolor/scalable/apps/syscheckup.svg"
# Iconos en mapa de bits: algunos menús y paneles solo buscan en las carpetas de tamaño fijo.
for n in 16 22 24 32 48 64 128 256; do
  install -Dm644 "data/icons/syscheckup-$n.png" "$PKG/usr/share/icons/hicolor/${n}x${n}/apps/syscheckup.png"
done
install -Dm644 data/syscheckup.svg     "$PKG/usr/share/pixmaps/syscheckup.svg"
# Ayudante de solo lectura para los datos internos (SPD de la memoria, registros del procesador) y su
# regla de polkit: solo se ejecuta si el usuario lo pide y escribe su contraseña.
install -Dm755 data/syscheckup-probe   "$PKG/usr/libexec/syscheckup/syscheckup-probe"
sed -i '1s|.*|#!/usr/bin/python3|' "$PKG/usr/libexec/syscheckup/syscheckup-probe"
install -Dm644 data/org.syscheckup.probe.policy "$PKG/usr/share/polkit-1/actions/org.syscheckup.probe.policy"
install -Dm644 data/syscheckup.metainfo.xml "$PKG/usr/share/metainfo/syscheckup.metainfo.xml"
for po in po/*.po; do                    # traducciones: el programa lee los .po directamente
  install -Dm644 "$po" "$PKG/usr/share/syscheckup/po/$(basename "$po")"
done
install -Dm644 README.md                "$PKG/usr/share/doc/syscheckup/README.md"
install -Dm644 README.es.md             "$PKG/usr/share/doc/syscheckup/README.es.md"
install -Dm644 LICENSE                  "$PKG/usr/share/doc/syscheckup/copyright"
gzip -9n -c CHANGELOG.md > "$PKG/usr/share/doc/syscheckup/changelog.gz"
chmod 644 "$PKG/usr/share/doc/syscheckup/changelog.gz"

cat > "$PKG/DEBIAN/control" <<CONTROL
Package: syscheckup
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-gi, python3-gi-cairo, gir1.2-gtk-3.0
Recommends: pciutils, iproute2, udisks2, libglib2.0-bin, fwupd, mesa-utils, x11-xserver-utils, iw, pkexec | policykit-1, stress-ng, 7zip | p7zip-full, glmark2-x11 | glmark2 | glmark2-wayland
Suggests: vainfo, vulkan-tools, lm-sensors, fonts-noto-cjk, memtest86+, earlyoom
Conflicts: radiografia, mintmachine
Replaces: radiografia, mintmachine
Installed-Size: $(du -sk "$PKG/usr" | cut -f1)
Maintainer: $MAINTAINER
Description: Información y diagnóstico del equipo
 SysCheckup muestra procesador, placa base, memoria, gráfica, discos, red,
 sensores, ventiladores, batería y software en una sola ventana, con gráficas
 de uso en vivo. Revisa la salud y el desgaste de los discos, comprueba si hay
 versiones nuevas de drivers y firmware y hace un diagnóstico automático con
 recomendaciones seguras. Exporta el informe a texto, HTML, JSON, CSV o a un
 formato listo para pegar en un foro, con los datos personales ocultos.
 Incluye pruebas voluntarias de estabilidad y rendimiento del procesador, la
 memoria, la gráfica y el disco.
 .
 Solo lee: no cambia nada y no envía datos a internet. Solo pide la contraseña
 si eliges leer datos internos que el sistema reserva al administrador.
CONTROL

# Al instalar y al quitar: el menú tiene que ver el icono nuevo sin esperar a reiniciar la sesión.
for script in postinst postrm; do
  cat > "$PKG/DEBIAN/$script" <<'SCRIPT'
#!/bin/sh
set -e
if command -v gtk-update-icon-cache >/dev/null 2>&1 && [ -f /usr/share/icons/hicolor/index.theme ]; then
  gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database -q /usr/share/applications || true
fi
exit 0
SCRIPT
  chmod 755 "$PKG/DEBIAN/$script"
done

# -Zxz: compatible con cualquier dpkg (Ubuntu usa zstd por defecto)
dpkg-deb --build --root-owner-group -Zxz "$PKG" "dist/syscheckup_${VERSION}_all.deb"
echo "Paquete listo: dist/syscheckup_${VERSION}_all.deb"
