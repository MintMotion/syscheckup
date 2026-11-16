# Changelog

[Versión en español](CHANGELOG.es.md)

## 0.8.0 (2026-11-16)

Changes based on user feedback on the Linux Mint forum:

- **Copy data from the window:** any text can be selected with the mouse (or a double click) and copied with Ctrl+C, and the selection is now clearly visible with any appearance. In tables you select whole rows (several with Shift or Ctrl) and Ctrl+C copies them tab-separated. Export still hides personal data by default.
- **Hide Diagnosis warnings:** each warning has "Hide this warning". It stops showing in Diagnosis, on Home and in the sidebar badge; it comes back if the problem changes; a button shows them again. Exported reports still include them.
- **UPS:** "Battery and power" shows UPS units connected over USB (status, charge, runtime and model), read from the system's power service (UPower) without a password. It no longer says the computer has no battery when there is a UPS, and it warns if the computer is running on the UPS battery.
- **Phased updates (Ubuntu and Linux Mint 22):** the ones the system doesn't offer this computer yet are shown separately and don't count as pending, in Software or in Driver updates.
- **Window buttons with the Breeze theme (KDE):** minimize, maximize and close were invisible; they now show with any theme.
- **Window icon:** it is the menu launcher's icon, so if you change it, the window follows. A monochrome icon (`syscheckup-symbolic`) is installed too. The window always identifies itself as "syscheckup", also when opened with `python3 syscheckup.py`.

## 0.7.2 (2026-11-14)

- **New "System" appearance** (menu ☰ → Appearance), besides Dark (the default) and Light. It takes the theme's background and text, the light or dark preference and the accent color from the desktop, and updates right away if you change the theme or switch between light and dark. Only those colors change: the design and the status colors stay the same, and they are adjusted where needed so text is readable. Tested with Mint-Y (light, dark and its color variants), Adwaita, Yaru, Breeze, Greybird and HighContrast, simulating Linux Mint, Ubuntu and Debian with GNOME, KDE Plasma and Xfce.

## 0.7.1 (2026-11-14)

- **"Hide personal data on screen"** no longer unticks itself. Ticking or unticking it now closes the menu and the window updates right away; before, a double click or a second click made while the window was redrawing could remove the tick again.

## 0.7.0 (2026-11-14)

- **New name: SysCheckup** (formerly MintMachine), because it works on any Debian-based distribution, not just Linux Mint. Package and command `syscheckup`. The package replaces `mintmachine` if it was installed, and the settings and history in `~/.config/mintmachine` move to `~/.config/syscheckup` automatically.

Up to 0.6.2 the program was called MintMachine; the entries below already use the new name.

## 0.6.2 (2026-11-14)

- The internal-data button no longer says "asks for your password": if needed, the system asks for it when you press it.

## 0.6.1 (2026-11-14)

- **Fewer passwords:** the processor's base, maximum and minimum frequency with their multipliers, the memory module data (if the kernel already publishes it) and the processor's power draw (if the system lets it be read) are read without a password. The button that asks for it only appears when there is something left that only the administrator can read, and it only asks for what belongs to its tab.
- **"i" button next to each test** and next to the internal-data one: what it does, how long it takes, which tool it uses, whether it asks for a password and when it stops on its own.
- **Any Debian-based distribution and any desktop:** buttons open whichever tool is installed (Linux Mint, Ubuntu, GNOME, KDE Plasma, Xfce, MATE, LXQt…) and the advice names it; Linux Mint-specific advice only appears on Linux Mint; the tests suggest the package that exists in your repositories.
- Live processor power draw in the Processor tab and in the Monitor's peaks, when the system lets it be read.
- If the desktop has no polkit agent, it explains so instead of saying the password wasn't given.

## 0.6.0 (2026-11-14)

- **Voluntary tests**, with a button in their tab and always with a warning and confirmation: processor stability and performance, memory, graphics performance and sustained load, and disk speed. Live window with temperature, frequency and a Stop button; automatic cut-off on temperature or if the laptop is unplugged; results saved and compared with your previous measurements.
- **Internal data with your password**, only if you ask for it: timings, XMP profiles, chip manufacturer and manufacturing date of each memory module (DDR4 and DDR5), and the processor's base frequency, multipliers and power draw in watts. Read by a separate read-only helper.
- **Disk health history:** one measurement a day; warns if new bad sectors or errors appear and estimates how long an SSD has left at its wear rate.
- **Graphics:** temperature, power draw and its limit, what is limiting it, card BIOS, video memory manufacturer and Resizable BAR (AMD and NVIDIA).
- **Live monitor:** programs using the graphics card and peaks reached since you opened the program.
- **Memory:** whether there is a service protecting the computer when memory runs out; if there isn't and programs have been killed for lack of memory, it suggests earlyoom.
- Fixed: the Monitor's system pressure showed "memoria" and "disco" in Spanish in the other languages.

## 0.5.4 (2026-11-14)

- **Missing firmware:** the diagnosis warning now says which file is missing, which device it belongs to and which package provides it (on LMDE and Debian, the matching `firmware-*` package; on Linux Mint and Ubuntu, `linux-firmware`). In "Driver updates", the details table adds the driver, the device, the package and a note.
- No more warning about `iwl-debug-yoyo.bin`: the Intel Wi-Fi driver asks for it at every boot, but it's an optional debugging configuration that no package ships. It still appears in the details table, marked as optional.
- That warning no longer points to Driver Manager, which doesn't exist on LMDE: it leads to Update Manager.

## 0.5.3 (2026-11-13)

- The Linux Mint menu showed the generic program icon instead of SysCheckup's. The package now also installs the icon as bitmaps (16 to 256 pixels) and in `/usr/share/pixmaps`, and updates the icon cache and the application database on install and removal.

## 0.5.2 (2026-11-13)

- Fixed the coloured line between the top bar and the content. With the desktop compositor active (Cinnamon), the row of pixels at the bar's border was transparent and showed what was behind the window. The border is now opaque.

## 0.5.1 (2026-11-13)

- **Processor:** live gauges for total usage, average frequency and temperature, and one bar per thread; updated every second.
- **Memory:** each module's manufacturer no longer shows as "Unknown". If the board doesn't report it by name, its JEDEC code is read or it is worked out from the module part number (G.Skill, Corsair, Kingston, Crucial, Samsung, SK hynix, Micron, ADATA, TeamGroup, Patriot), and it is marked as inferred.
- **Top bar:** under the program's name it reads "SysCheckup only reads information. It changes nothing on your computer and sends no data to the internet". That note is removed from the bottom of Home.
- Removed the dashed line the Mint-Y theme draws at the content's edge when scrolling.
- Removed the "i" buttons from the fields.
- **Light theme** toned down so it doesn't dazzle.

## 0.5.0 (2026-11-13)

**New data**
- **Displays on Wayland:** the current mode (resolution, refresh rate and scale) is requested from the desktop: GNOME and Cinnamon via D-Bus, KDE Plasma with `kscreen-doctor`, and Sway, Hyprland and similar with `wlr-randr`. X11 still uses `xrandr`.
- **Intel GPU usage** in the Live monitor and the CSV, computed from the idle time (RC6) the kernel publishes, without administrator privileges.
- **Applications using the most:** the Monitor adds up the processes of each application (a browser opens dozens).
- **Power:** manufacturer profile, processor governor and power/performance preference; a suggestion if the computer is plugged in with the power-saving profile.
- **Compressed memory:** zram and zswap.
- **Firmware security (HSI)**, read from the computer's own fwupd service.

**Easier to use**
- New **Setup checklist** section: what to check after installing the system (updates, drivers and firmware, firewall, Timeshift snapshots, TRIM and codecs), with a button to the tool for each item.
- **Ask for help with a problem:** the "For a forum" format can focus on Wi-Fi and network, sound, graphics, battery and temperature, or slowness. In the terminal, `--foro --problema red`.
- The Diagnosis lists the **missing optional tools**, with the package that provides them and what you can't see without them.
- `--debug`: shows in the terminal which tools are run and how long they take.

**Privacy**
- Hiding personal data now also masks printer names and Bluetooth peripheral names where they used to show: in the keyboard and mouse list and in their battery title.
- None of the new features uses the internet, asks for a password or saves anything to disk. `--debug` doesn't show the tools' arguments or output.
- Automated tests that make sure the code doesn't import network modules and that data marked as sensitive doesn't appear in anonymous reports.

**Project**
- Unit tests in `tests/test_unidad.py` (20 tests), added to the GitHub action.
- Translations of everything new into English, French, Japanese and Chinese.

## 0.4.0 (2026-11-13)

- **Languages:** Spanish, English, French, Japanese and Chinese. Chosen automatically from the system language (any country variant) and changeable in the menu; if the system language isn't available, it opens in English. Translations in `po/*.po`.
- **New design:** dark theme by default and a light theme, cards, gradients, custom sidebar icons, circular gauges on Home, smooth gradient graphs and floating notifications.
- **Home:** "Computer" instead of "Your computer", with the motherboard and BIOS included.
- **Monitors:** new table in Peripherals (and in Graphics and displays) with brand, model, size, native resolution and refresh rate, current mode, year and serial number. With the NVIDIA driver the EDID is read from `xrandr`.
- **Power supply:** model, power, temperature and fan of Corsair power supplies with USB. On other desktops, a note explains why it can't be read.
- **Peripheral battery:** the level ("Full", "Low"…) is translated.
- **Information (i):** now a button that shows the explanation when pressed, as well as on hover.
- **"by Sombra"** next to the program's name, at the top of the sidebar.
- **Uninstall** from the menu: removes the program, its icon and its settings, leaving no trace. Asks for the system password.
- **Package:** the description no longer mentions other programs and the "Maintainer" field carries no personal data.

## 0.3.0 (2026-11-13)

Author: José Antonio Ramos Miralles «Sombra» <hola@joseantonioramos.es>.

**Easier to use**
- New **Home** screen: overall status of the computer, the most important diagnosis items, computer summary, live usage (processor, memory, disk, temperature and battery) and system.
- Sidebar grouped into Hardware and System and software.
- Expert data is folded under **Technical details** in each section. Exports always include it.
- Plain-language explanations under technical items and on hover over fields marked with ⓘ.
- **Search** across the whole report (Ctrl+F), keyboard shortcuts (F5, Ctrl+E, Ctrl+Q, Alt+1…9, F1) and an About window.
- A single **Export** button with every option: the whole report or only the visible section; text, web page, forum summary, JSON or monitor history as CSV; hide personal data (ticked by default); copy or save. After saving, a button to open the file.

**Diagnosis**
- Each warning explains what is going on and what to do, and separates what should be checked from optional suggestions.
- Recommendations are limited to safe actions from the system. It never asks you to open the computer: physical checks are referred to a repair service or the manufacturer. Legal notice in the Diagnosis, in About and in reports.
- Buttons that open the right system tool: Update Manager, Driver Manager, Backups, Disk Usage Analyzer, Firewall, System Monitor…
- No longer recommends `sudo sensors-detect`, checking cables or thermal paste, or replacing parts.

**New data**
- NVMe SSD wear (life used, spare blocks, data errors) and remaining life of SATA SSDs that publish it, requested from UDisks without administrator privileges.
- Current and maximum PCIe link of the graphics card and NVMe SSDs.
- Current and maximum graphics clock on Intel and AMD.
- Wi-Fi signal quality and a warning if it is weak.
- Memory: modules and type in the computer summary; swap size.

**Fixes**
- Hiding personal data only masked the marked fields: it now also searches for them inside any text (system log, boot parameters, paths with the user name) and masks MAC, IP, UUID, computer name, user name and Bluetooth device names.
- The used-disk percentage is computed like `df` (it used to ignore ext4's reserved space and came out lower).
- Numbers use a decimal comma (in Spanish).
- Process names are no longer cut at 15 letters.
- Kernel version comparison can no longer fail when mixing numbers and text.
- The llvmpipe warning no longer fires in virtual machines; a failed service is a suggestion, not a warning.
- If a report can't be saved from the terminal, the message is clear rather than a Python error.

**Project**
- License and package in the name of José Antonio Ramos Miralles «Sombra».
- AppStream metadata, GitHub issue templates and a GitHub action that tests the program and builds the `.deb`.
- New terminal options: `--foro` and `--csv`. The JSON carries a schema number (`"esquema": 2`).

## 0.2.0 (2026-11-13)

The program is renamed SysCheckup. Author: Sombra.

- Live monitor: graphs of processor, RAM and swap, network, disk, temperature and graphics, per-thread usage and processes using the most.
- Fans: power percentage, control mode, programmed curves when the chip publishes them, ACPI thermal thresholds and cooling devices.
- Driver updates: installed and available version of kernel, NVIDIA, Mesa, firmware, microcode and DKMS; device firmware with fwupd; devices without a driver; missing firmware.
- SMART disk health without root, through UDisks.
- Export button: all the panel's information to a text, HTML or JSON file. `--txt` option in the terminal.
- New Peripherals section: keyboards, mice, cameras, printers and Bluetooth.
- Hardware video decoding and Vulkan; suspend, hibernation and charge limit; services delaying boot; memory errors; thermal throttling of the processor.
- The diagnosis reads the kernel log: disk errors, hardware errors and out-of-memory kills.
- The text report no longer cuts long columns.

## 0.1.0 (2026-11-13)

First version, under the name Radiografía.

- GTK 3 interface with 17 sections and live refresh of processor, memory and sensors.
- Automatic diagnosis, HTML, text and JSON reports, option to hide sensitive data.
- Terminal mode and .deb package.
