"""Simula un portátil real (sysfs + utilidades falsas) para probar los analizadores."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BIN = tempfile.mkdtemp(prefix="syscheckup-bin-")

# Uso (como root, porque monta un /sys falso en un espacio de montajes privado):
#   sudo tests/run.sh texto [--anon]
#   sudo tests/run.sh html /tmp/informe.html [--anon]       (también json, foro y csv)
#   sudo -E tests/run.sh gui /tmp/captura.png [sección]   (hace una captura y sale)

def w(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w") as f: f.write(data if isinstance(data, bytes) else str(data) + "\n")

def tree(base, d):
    for k, v in d.items(): w(f"{base}/{k}", v)

def link_driver(devpath, name):
    os.makedirs(f"/sys/bus/fake/drivers/{name}", exist_ok=True)
    os.makedirs(devpath, exist_ok=True)
    os.symlink(f"/sys/bus/fake/drivers/{name}", devpath + "/driver")

def cmd(name, body):
    p = f"{BIN}/{name}"
    with open(p, "w") as f: f.write("#!/bin/sh\n" + body)
    os.chmod(p, 0o755)

def build():
    tree("/sys/class/dmi/id", dict(sys_vendor="LENOVO", product_name="21C1S0AB00", product_version="ThinkPad L14 Gen 3",
         product_family="ThinkPad L14 Gen 3", board_vendor="LENOVO", board_name="21C1S0AB00", board_version="SDK0T76530 WIN",
         bios_vendor="LENOVO", bios_version="R1XET54W (1.36 )", bios_date="03/14/2025", bios_release="1.36",
         chassis_type="10", product_serial="PF3ABC12"))
    w("/sys/class/tpm/tpm0/tpm_version_major", "2")
    # SPD del módulo (driver ee1004), legible sin root como en un kernel real: DDR4-3200 de 8 GiB, Samsung
    spd = bytearray(512)
    head = bytes.fromhex("2311 0c03 4521 0008 0000 0000 0103 0000 0000 0500 0000 0000 6e6e 6e11 006e".replace(" ", ""))
    spd[0:len(head)] = head
    spd[320:322], spd[350:352], spd[323:325] = b"\x80\xce", b"\x80\xce", b"\x22\x10"
    spd[329:349] = b"M471A1K43EB1-CWE    "
    crc = 0
    for x in spd[:126]:
        crc ^= x << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
    spd[126], spd[127] = crc & 0xFF, (crc >> 8) & 0xFF
    w("/sys/bus/i2c/drivers/ee1004/0-0050/eeprom", bytes(spd))
    w("/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c", bytes([6,0,0,0,1]))
    tree("/sys/class/hwmon/hwmon0", dict(name="acpitz", temp1_input=45000))
    tree("/sys/class/hwmon/hwmon1", dict(name="nvme", temp1_input=38850, temp1_label="Composite", temp1_max=81850, temp1_crit=84850))
    tree("/sys/class/hwmon/hwmon2", dict(name="coretemp", temp1_input=88000, temp1_label="Package id 0", temp1_max=100000, temp1_crit=100000,
         temp2_input=86000, temp2_label="Core 0", temp2_max=100000, temp2_crit=100000, temp6_input=71000, temp6_label="Core 4"))
    tree("/sys/class/hwmon/hwmon3", dict(name="thinkpad", fan1_input=2890, temp1_input=47000, pwm1=128, pwm1_enable=2))
    nct = dict(name="nct6798", fan1_input=1180, fan1_min=300, pwm1=96, pwm1_enable=5,
               fan2_input=0, pwm2=0, pwm2_enable=5, in0_input=1008)
    for i, (t, pw) in enumerate([(30, 60), (45, 90), (60, 140), (70, 200), (80, 255)], 1):
        nct[f"pwm1_auto_point{i}_temp"] = t * 1000
        nct[f"pwm1_auto_point{i}_pwm"] = pw
    tree("/sys/class/hwmon/hwmon4", nct)
    tree("/sys/class/thermal/thermal_zone0", dict(type="acpitz", temp=45000, trip_point_0_temp=105000,
         trip_point_0_type="critical", trip_point_1_temp=95000, trip_point_1_type="passive",
         trip_point_2_temp=60000, trip_point_2_type="active"))
    tree("/sys/class/thermal/cooling_device0", dict(type="Fan", cur_state=1, max_state=1))
    for i in range(1, 5):
        tree(f"/sys/class/thermal/cooling_device{i}", dict(type="Processor", cur_state=0, max_state=10))
    tree("/sys/class/video4linux/video0", dict(name="Integrated Camera: Integrated C"))
    tree("/sys/class/video4linux/video1", dict(name="Integrated Camera: Integrated C"))
    tree("/sys/class/net/wlp0s20f3/statistics", dict(rx_bytes=0, tx_bytes=0))
    tree("/sys/class/hwmon/hwmon10", dict(name="BAT0", in0_input=11800, power1_input=8500000))
    tree("/sys/class/power_supply/BAT0", dict(type="Battery", status="Discharging", capacity=67, energy_full=38000000,
         energy_full_design=52500000, energy_now=25460000, cycle_count=412, technology="Li-poly", manufacturer="SMP",
         model_name="5B10W13973", power_now=8500000, voltage_now=11800000,
         charge_control_start_threshold=75, charge_control_end_threshold=80))
    tree("/sys/class/power_supply/AC", dict(type="Mains", online=0))
    tree("/sys/class/power_supply/hidpp_battery_0", dict(type="Battery", scope="Device", model_name="MX Master 3", capacity=80, status="Discharging"))
    edid = bytearray(128); edid[:8] = b"\x00\xff\xff\xff\xff\xff\xff\x00"; edid[8:10] = b"\x09\xe5"; edid[17] = 31; edid[21], edid[22] = 31, 17
    edid[54:62] = bytes([0x2e, 0x36, 0x80, 0xa0, 0x70, 0x38, 0x1f, 0x40])
    edid[72:90] = b"\x00\x00\x00\xfc\x00" + b"NV140FHM-N4V\n"
    tree("/sys/class/drm/card1-eDP-1", dict(status="connected", modes="1920x1080\n1680x1050", edid=bytes(edid)))
    tree("/sys/class/drm/card1-HDMI-A-1", dict(status="disconnected"))
    tree("/sys/class/net/lo", dict(operstate="unknown", address="00:00:00:00:00:00"))
    tree("/sys/class/net/enp2s0", dict(operstate="down", address="8c:8c:aa:11:22:33", speed="-1"))
    link_driver("/sys/class/net/enp2s0/device", "r8169")
    tree("/sys/class/net/wlp0s20f3", dict(operstate="up", address="f4:7b:09:aa:bb:cc"))
    os.makedirs("/sys/class/net/wlp0s20f3/wireless"); link_driver("/sys/class/net/wlp0s20f3/device", "iwlwifi")
    tree("/sys/class/net/docker0", dict(operstate="down", address="02:42:11:22:33:44"))
    os.makedirs("/sys/class/bluetooth/hci0")
    tree("/sys/bus/usb/devices/usb1", dict(idVendor="1d6b", idProduct="0002"))
    tree("/sys/bus/usb/devices/1-3", dict(idVendor="046d", idProduct="c52b", manufacturer="Logitech", product="USB Receiver",
         version=" 2.00", speed=12, bMaxPower="98mA"))
    link_driver("/sys/bus/usb/devices/1-3/1-3:1.0", "usbhid")
    tree("/sys/bus/usb/devices/1-4", dict(idVendor="04f2", idProduct="b74f", manufacturer="Chicony Electronics Co.,Ltd.",
         product="Integrated Camera", version=" 2.01", speed=480, bMaxPower="500mA"))
    link_driver("/sys/bus/usb/devices/1-4/1-4:1.0", "uvcvideo")
    tree("/sys/module/nvidia", dict(taint="POE", version="550.163.01"))
    tree("/sys/module/i915", dict(taint=""))
    tree("/sys/module/iwlwifi", dict(taint=""))
    os.makedirs("/sys/bus/pci/devices/0000:00:02.0")
    if os.environ.get("MM_FUENTE"):          # MM_FUENTE=1: fuente Corsair con USB (driver corsair-psu)
        tree("/sys/bus/usb/devices/1-9", dict(manufacturer="Corsair", product="RM850i"))
        tree("/sys/bus/usb/devices/1-9/1-9:1.0/hid", dict(x=""))
        tree("/sys/class/hwmon/hwmon11", dict(name="corsairpsu", power1_input=142000000, power1_label="power total",
             temp1_input=38250, temp1_label="vrm temp", fan1_input=0))
        os.symlink("/sys/bus/usb/devices/1-9/1-9:1.0/hid", "/sys/class/hwmon/hwmon11/device")
    tree("/sys/bus/pci/devices/0000:03:00.0", dict(current_link_speed="8.0 GT/s PCIe", current_link_width=4,
         max_link_speed="16.0 GT/s PCIe", max_link_width=4))
    tree("/sys/class/drm/card1", dict(gt_act_freq_mhz=650, gt_max_freq_mhz=1450))
    os.symlink("/sys/bus/pci/devices/0000:00:02.0", "/sys/class/drm/card1/device")

    cmd("systemd-detect-virt", "echo none\n")
    cmd("lspci", r"""printf 'Slot:\t0000:00:00.0\nClass:\tHost bridge [0600]\nVendor:\tIntel Corporation [8086]\nDevice:\tDevice [4601]\nSVendor:\tLenovo [17aa]\nSDevice:\tDevice [50a0]\nRev:\t04\nDriver:\tigen6_edac\nModule:\tigen6_edac\n\nSlot:\t0000:00:02.0\nClass:\tVGA compatible controller [0300]\nVendor:\tIntel Corporation [8086]\nDevice:\tAlder Lake-UP3 GT2 [Iris Xe Graphics] [46a8]\nSVendor:\tLenovo [17aa]\nSDevice:\tDevice [50a0]\nRev:\t0c\nProgIf:\t00\nDriver:\ti915\nModule:\ti915\nModule:\txe\n\nSlot:\t0000:00:14.3\nClass:\tNetwork controller [0280]\nVendor:\tIntel Corporation [8086]\nDevice:\tAlder Lake-P PCH CNVi WiFi [51f0]\nSVendor:\tIntel Corporation [8086]\nSDevice:\tWi-Fi 6 AX201 160MHz [0074]\nRev:\t01\nDriver:\tiwlwifi\nModule:\tiwlwifi\n\nSlot:\t0000:02:00.0\nClass:\tEthernet controller [0200]\nVendor:\tRealtek Semiconductor Co., Ltd. [10ec]\nDevice:\tRTL8111/8168/8211/8411 PCI Express Gigabit Ethernet Controller [8168]\nSVendor:\tLenovo [17aa]\nSDevice:\tDevice [50a0]\nRev:\t15\nDriver:\tr8169\nModule:\tr8169\n\nSlot:\t0000:03:00.0\nClass:\tNon-Volatile memory controller [0108]\nVendor:\tSamsung Electronics Co Ltd [144d]\nDevice:\tNVMe SSD Controller PM9A1/PM9A3/980PRO [a80a]\nSVendor:\tSamsung Electronics Co Ltd [144d]\nSDevice:\tDevice [a801]\nProgIf:\t02\nDriver:\tnvme\nModule:\tnvme\n'
""")
    cmd("udevadm", """cat <<'X'
DEVPATH=/devices/virtual/dmi/id
MEMORY_ARRAY_LOCATION=System Board Or Motherboard
MEMORY_ARRAY_MAX_CAPACITY=68719476736
MEMORY_ARRAY_NUM_DEVICES=2
MEMORY_DEVICE_0_TOTAL_WIDTH=64
MEMORY_DEVICE_0_DATA_WIDTH=64
MEMORY_DEVICE_0_SIZE=8589934592
MEMORY_DEVICE_0_FORM_FACTOR=SODIMM
MEMORY_DEVICE_0_LOCATOR=DIMM 0
MEMORY_DEVICE_0_BANK_LOCATOR=BANK 0
MEMORY_DEVICE_0_TYPE=DDR4
MEMORY_DEVICE_0_TYPE_DETAIL=Synchronous
MEMORY_DEVICE_0_SPEED_MTS=3200
MEMORY_DEVICE_0_MANUFACTURER=Samsung
MEMORY_DEVICE_0_PART_NUMBER=M471A1K43EB1-CWE    
MEMORY_DEVICE_0_CONFIGURED_SPEED_MTS=3200
MEMORY_DEVICE_1_PRESENT=0
MEMORY_DEVICE_1_LOCATOR=DIMM 1
SUBSYSTEM=dmi
X
""")
    cmd("lsblk", """cat <<'X'
{"blockdevices":[
 {"name":"nvme0n1","model":"SAMSUNG MZVL2512HCJQ-00BL7","serial":"S64KNX0T123456","size":512110190592,"type":"disk","tran":"nvme","rota":false,"fstype":null,"mountpoint":null,"rev":"GXA7801Q","rm":false,"pkname":null,"children":[
   {"name":"nvme0n1p1","model":null,"serial":null,"size":536870912,"type":"part","tran":"nvme","rota":false,"fstype":"vfat","mountpoint":"/boot/efi","rev":null,"rm":false,"pkname":"nvme0n1"},
   {"name":"nvme0n1p2","model":null,"serial":null,"size":511572246528,"type":"part","tran":"nvme","rota":false,"fstype":"crypto_LUKS","mountpoint":null,"rev":null,"rm":false,"pkname":"nvme0n1","children":[
      {"name":"luks-2b1f","model":null,"serial":null,"size":511555469312,"type":"crypt","tran":null,"rota":false,"fstype":"ext4","mountpoint":"/","rev":null,"rm":false,"pkname":"nvme0n1p2"}]}]},
 {"name":"sda","model":"ST1000LM035-1RK172","serial":"WL1ABCDE","size":1000204886016,"type":"disk","tran":"sata","rota":true,"fstype":null,"mountpoint":null,"rev":"LCM2","rm":false,"pkname":null,"children":[
   {"name":"sda1","model":null,"serial":null,"size":1000203091968,"type":"part","tran":null,"rota":true,"fstype":"ext4","mountpoint":"/tmp","rev":null,"rm":false,"pkname":"sda"}]},
 {"name":"zram0","model":null,"serial":null,"size":4294967296,"type":"disk","tran":null,"rota":false,"fstype":null,"mountpoint":"[SWAP]","rev":null,"rm":false,"pkname":null}
]}
X
""")
    cmd("glxinfo", """cat <<'X'
name of display: :0
display: :0  screen: 0
direct rendering: Yes
Extended renderer info (GLX_MESA_query_renderer):
    Vendor: Intel (0x8086)
    Device: Mesa Intel(R) Iris(R) Xe Graphics (ADL GT2) (0x46a8)
    Version: 25.0.7
    Accelerated: yes
    Video memory: 15718MB
    Unified memory: yes
OpenGL vendor string: Intel
OpenGL renderer string: Mesa Intel(R) Iris(R) Xe Graphics (ADL GT2)
OpenGL core profile version string: 4.6 (Core Profile) Mesa 25.0.7-2
OpenGL version string: 4.6 (Compatibility Profile) Mesa 25.0.7-2
X
""")
    # Segundo monitor por HDMI cuyo EDID solo se ve con «xrandr --verbose», como con el driver de NVIDIA
    e2 = bytearray(128); e2[:8] = b"\x00\xff\xff\xff\xff\xff\xff\x00"; e2[8:10] = b"\x1e\x6d"; e2[16] = 12; e2[17] = 33
    e2[20] = 0x80; e2[21], e2[22] = 60, 34
    e2[54:72] = bytes([0x90, 0xe2, 0x00, 0xa0, 0xa0, 0xa0, 0x29, 0x50, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    e2[72:90] = b"\x00\x00\x00\xfc\x00" + b"LG ULTRAGEAR\n"
    e2[90:108] = b"\x00\x00\x00\xff\x00" + b"205NTKF4A123\n"
    hexed = "\n".join("\t\t" + e2[i:i + 16].hex() for i in range(0, 128, 16))
    cmd("xrandr", """case "$*" in *verbose*) cat <<'X'
Screen 0: minimum 8 x 8, current 4480 x 1440, maximum 32767 x 32767
eDP-1 connected primary 1920x1080+0+0 (0x46) normal (normal left inverted right x axis y axis) 309mm x 174mm
	Identifier: 0x42
  1920x1080 (0x46) 141.000MHz -HSync -VSync *current +preferred
        h: width  1920 start 1936 end 1952 total 2104 skew    0 clock  67.02KHz
        v: height 1080 start 1083 end 1097 total 1116           clock  60.05Hz
HDMI-0 connected 2560x1440+1920+0 (0x1c8) normal (normal left inverted right x axis y axis) 597mm x 336mm
	Identifier: 0x1c7
	EDID:
""" + hexed + """
  2560x1440 (0x1c8) 241.500MHz +HSync -VSync *current +preferred
        h: width  2560 start 2608 end 2640 total 2720 skew    0 clock  88.79KHz
        v: height 1440 start 1443 end 1448 total 1481           clock 143.97Hz
  1920x1080 (0x1c9) 148.500MHz +HSync +VSync
        h: width  1920 start 2008 end 2052 total 2200 skew    0 clock  67.50KHz
        v: height 1080 start 1084 end 1089 total 1125           clock  60.00Hz
X
exit 0;; esac
cat <<'X'
Screen 0: minimum 320 x 200, current 1920 x 1080, maximum 16384 x 16384
eDP-1 connected primary 1920x1080+0+0 (normal left inverted right x axis y axis) 309mm x 174mm
   1920x1080     60.01*+  59.97    59.96    59.93  
   1680x1050     59.95    59.88  
HDMI-1 disconnected (normal left inverted right x axis y axis)
X
""")
    cmd("iw", r"""printf 'Connected to a0:b1:c2:d3:e4:f5 (on wlp0s20f3)\n\tSSID: MiCasa_5G\n\tfreq: 5180.0\n\tRX: 483920 bytes (3211 packets)\n\tTX: 99120 bytes (812 packets)\n\tsignal: -52 dBm\n\trx bitrate: 866.7 MBit/s VHT-MCS 9 80MHz short GI VHT-NSS 2\n\ttx bitrate: 780.0 MBit/s VHT-MCS 8 80MHz short GI VHT-NSS 2\n'
""")
    cmd("ip", """case "$*" in
*route*) echo '[{"dst":"default","gateway":"192.168.1.1","dev":"wlp0s20f3","protocol":"dhcp","metric":600,"flags":[]}]';;
*) echo '[{"ifindex":1,"ifname":"lo","addr_info":[{"family":"inet","local":"127.0.0.1","prefixlen":8},{"family":"inet6","local":"::1","prefixlen":128}]},{"ifindex":2,"ifname":"enp2s0","addr_info":[]},{"ifindex":3,"ifname":"wlp0s20f3","addr_info":[{"family":"inet","local":"192.168.1.37","prefixlen":24},{"family":"inet6","local":"fe80::f67b:9ff:feaa:bbcc","prefixlen":64}]}]';;
esac
""")
    cmd("systemctl", """case "$*" in
*failed*) echo 'fwupd-refresh.service loaded failed failed Refresh fwupd metadata and update motd';;
*running*) printf 'cron.service loaded active running Regular background program processing daemon\\nNetworkManager.service loaded active running Network Manager\\nlightdm.service loaded active running Light Display Manager\\n';;
*is-enabled*fstrim*) echo enabled;;
*) echo inactive;;
esac
""")
    cmd("journalctl", """case "$*" in *-k*) cat <<'K'
iwlwifi 0000:00:14.3: firmware: failed to load iwlwifi-so-a0-gf-a0-89.ucode (-2)
iwlwifi 0000:00:14.3: Direct firmware load for iwlwifi-so-a0-gf-a0-88.ucode failed with error -2
iwlwifi 0000:00:14.3: Direct firmware load for iwl-debug-yoyo.bin failed with error -2
Out of memory: Killed process 4123 (firefox-esr) total-vm:9123456kB, anon-rss:3123456kB
K
exit 0;; esac
cat <<'X'
Nov 13 08:01:02 portatil kernel: ACPI BIOS Error (bug): Could not resolve symbol [\\_SB.PC00.LPCB.HEC.CHRG], AE_NOT_FOUND
Nov 13 08:01:02 portatil kernel: ACPI Error: Aborting method \\_SB.PC00.LPCB.EC0._QA3 due to previous error (AE_NOT_FOUND)
Nov 13 08:01:09 portatil bluetoothd[812]: Failed to set mode: Failed (0x03)
Nov 13 08:14:41 portatil kernel: ACPI BIOS Error (bug): Could not resolve symbol [\\_SB.PC00.LPCB.HEC.CHRG], AE_NOT_FOUND
Nov 13 09:30:12 portatil bluetoothd[812]: Failed to set mode: Failed (0x03)
Nov 13 09:31:00 portatil bluetoothd[2231]: Failed to set mode: Failed (0x03)
X
""")
    cmd("udisksctl", """cat <<'X'
/org/freedesktop/UDisks2/Manager:
  org.freedesktop.UDisks2.Manager:
    Version:                    2.10.1
/org/freedesktop/UDisks2/block_devices/sda:
  org.freedesktop.UDisks2.Block:
    Device:                     /dev/sda
    Drive:                      '/org/freedesktop/UDisks2/drives/ST1000LM035_1RK172_WL1ABCDE'
/org/freedesktop/UDisks2/drives/ST1000LM035_1RK172_WL1ABCDE:
  org.freedesktop.UDisks2.Drive:
    CanPowerOff:                false
    Configuration:              {}
    Id:                         ST1000LM035-1RK172-WL1ABCDE
    Model:                      ST1000LM035-1RK172
    RotationRate:               5400
    Serial:                     WL1ABCDE
  org.freedesktop.UDisks2.Drive.Ata:
    SmartEnabled:               true
    SmartFailing:               false
    SmartNumAttributesFailedInThePast: 0
    SmartNumAttributesFailing:  0
    SmartNumBadSectors:         16
    SmartPowerOnSeconds:        61344000
    SmartSelftestPercentRemaining: 0
    SmartSelftestStatus:        success
    SmartSupported:             true
    SmartTemperature:           309.15
    SmartUpdated:               1794500000
/org/freedesktop/UDisks2/drives/SAMSUNG_MZVL2512HCJQ_00BL7_S64KNX0T123456:
  org.freedesktop.UDisks2.Drive:
    Id:                         SAMSUNG-MZVL2512HCJQ-00BL7-S64KNX0T123456
    Model:                      SAMSUNG MZVL2512HCJQ-00BL7
  org.freedesktop.UDisks2.NVMe.Controller:
    ControllerID:               6
    NVMeRevision:               1.3
    SmartCriticalWarning:       
    SmartPowerOnHours:          4210
    SmartSelftestStatus:        success
    SmartTemperature:           312
    SmartUpdated:               1794500000
    State:                      live
X
""")
    # Respuestas de UDisks a SmartGetAttributes, con el formato de texto de GVariant que imprime gdbus
    cmd("gdbus", """case "$*" in
*NVMe.Controller.SmartGetAttributes*) echo "({'avail_spare': <byte 0x64>, 'spare_thresh': <byte 0x0a>, 'percent_used': <byte 0x07>, 'total_data_read': <uint64 21474836480000>, 'total_data_written': <uint64 32212254720000>, 'ctrl_busy_time': <uint64 412>, 'power_cycles': <uint64 1873>, 'unsafe_shutdowns': <uint64 61>, 'media_errors': <uint64 0>, 'num_err_log_entries': <uint64 0>, 'temp_sensors': <[uint16 312, 318]>, 'wctemp': <uint16 355>, 'cctemp': <uint16 358>},)";;
*Drive.Ata.SmartGetAttributes*) echo "([(byte 0x01, 'raw-read-error-rate', uint16 15, 78, 64, 6, int64 70013420, 0, @a{sv} {}), (0x05, 'reallocated-sector-count', 51, 100, 100, 10, 16, 1, {}), (0x09, 'power-on-hours', 50, 81, 81, 0, 61344000000, 2, {})],)";;
*) exit 1;;
esac
""")
    cmd("fwupdmgr", """case "$*" in
*get-updates*) echo '{"Devices":[{"Name":"System Firmware","DeviceId":"a45df35ac0e948ee180fe216a5f703f32dda163f","Version":"1.36","Releases":[{"Version":"1.40","Summary":"Lenovo ThinkPad L14 Gen 3 BIOS"}]}]}';;
*) echo '{"Devices":[{"Name":"System Firmware","DeviceId":"a45df35ac0e948ee180fe216a5f703f32dda163f","Vendor":"LENOVO","Version":"1.36","Flags":["internal","updatable","require-ac"]},{"Name":"SAMSUNG MZVL2512HCJQ-00BL7","DeviceId":"71b677ca0f1bc2c5b804fa1d59e52064ce589293","Vendor":"Samsung","Version":"GXA7801Q","Flags":["internal","updatable"]},{"Name":"UEFI dbx","DeviceId":"362301da643102b9f38477387e2193e57abaa590","Vendor":"UEFI:Linux Foundation","Version":"20241101","Flags":["internal","updatable"]},{"Name":"Integrated Camera","DeviceId":"2292ae5236790b47884e37cf162dcf23bfcd1c60","Vendor":"Chicony","Version":"0.27","Flags":[]}]}';;
esac
""")
    pkgs = [("linux-image-amd64", "6.12.48-1"), ("linux-image-6.12.48+deb13-amd64", "6.12.48-1"),
            ("linux-image-6.12.57+deb13-amd64", "6.12.57-1"), ("linux-image-6.12.38+deb13-amd64", "6.12.38-1"),
            ("nvidia-driver", "550.163.01-2"), ("nvidia-kernel-dkms", "550.163.01-2"),
            ("firmware-iwlwifi", "20250410-2"), ("firmware-misc-nonfree", "20250410-2"),
            ("intel-microcode", "3.20250512.1"), ("libgl1-mesa-dri", "25.0.7-2"), ("bluez", "5.82-1.1"),
            ("fwupd", "2.0.8-3"), ("libc6", "2.41-12"), ("systemd", "257.8-1~deb13u2"),
            ("cinnamon", "6.4.12+gigi"), ("python3", "3.13.5-1"), ("firefox", "144.0+linuxmint1+gigi"),
            ("pipewire", "1.4.2-1"), ("cups", "2.4.10-3")]
    cmd("dpkg-query", "cat <<'X'\n" + "\n".join(f"{n}\t{v}\tii " for n, v in pkgs) + "\nX\n")
    cmd("apt-cache", """for p in "$@"; do [ "$p" = policy ] && continue
case "$p" in
 nvidia-driver|nvidia-kernel-dkms) i=550.163.01-2; c=550.163.01-4;;
 intel-microcode) i=3.20250512.1; c=3.20250812.1~deb13u1;;
 linux-image-amd64) i=6.12.48-1; c=6.12.57-1;;
 *) i=1.0; c=1.0;;
esac
printf '%s:\n  Installed: %s\n  Candidate: %s\n  Version table:\n *** %s 500\n        500 http://deb.debian.org/debian trixie/main amd64 Packages\n' "$p" "$i" "$c" "$c"
done
""")
    cmd("vainfo", """cat <<'X'
libva info: VA-API version 1.22.0
vainfo: Driver version: Intel iHD driver for Intel(R) Gen Graphics - 25.2.3 ()
vainfo: Supported profile and entrypoints
      VAProfileMPEG2Main              :	VAEntrypointVLD
      VAProfileH264Main               :	VAEntrypointVLD
      VAProfileH264Main               :	VAEntrypointEncSliceLP
      VAProfileH264High               :	VAEntrypointVLD
      VAProfileHEVCMain10             :	VAEntrypointVLD
      VAProfileVP9Profile0            :	VAEntrypointVLD
      VAProfileAV1Profile0            :	VAEntrypointEncSliceLP
X
""")
    cmd("vulkaninfo", """cat <<'X'
Devices:
========
GPU0:
	apiVersion         = 1.4.305
	driverVersion      = 25.0.7
	vendorID           = 0x8086
	deviceID           = 0x46a8
	deviceType         = PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU
	deviceName         = Intel(R) Iris(R) Xe Graphics (ADL GT2)
	driverName         = Intel open-source Mesa driver
	driverInfo         = Mesa 25.0.7-2
X
""")
    cmd("lpstat", "echo HP_LaserJet_M110w\n")
    cmd("bluetoothctl", "echo 'Device D4:57:63:AA:BB:CC MX Master 3'\n")
    cmd("dkms", "echo 'nvidia-current/550.163.01, 6.12.48+deb13-amd64, x86_64: installed'\n")
    cmd("powerprofilesctl", "echo balanced\n")
    cmd("cinnamon", "echo 'Cinnamon 6.4.12'\n")
    cmd("flatpak", "printf 'Spotify\\tcom.spotify.Client\\t1.2.50.335\\tflathub\\nObsidian\\tmd.obsidian.Obsidian\\t1.8.10\\tflathub\\n'\n")
    cmd("pactl", """cat <<'X'
Server String: /run/user/1000/pulse/native
Server Name: PulseAudio (on PipeWire 1.4.2)
Server Version: 15.0.0
Default Sample Specification: float32le 2ch 48000Hz
Default Sink: alsa_output.pci-0000_00_1f.3.analog-stereo
Default Source: alsa_input.pci-0000_00_1f.3.analog-stereo
X
""")
    cmd("ufw", "exit 0\n")
    cmd("timeshift", "exit 0\n")
    cmd("systemd-analyze", """case "$*" in *blame*) printf '6.012s NetworkManager-wait-online.service\n2.314s plymouth-quit-wait.service\n1.120s fwupd.service\n 834ms dev-nvme0n1p2.device\n';;
*) echo 'Startup finished in 6.412s (firmware) + 2.105s (loader) + 3.870s (kernel) + 11.224s (userspace) = 23.612s';; esac
""")

FAKE = {
 "/proc/modules": "nvidia 54018048 412 nvidia_modeset,nvidia_uvm, Live 0x0000000000000000 (POE)\ni915 4300800 38 - Live 0x0000000000000000\niwlwifi 544768 1 iwlmvm, Live 0x0000000000000000\nr8169 126976 0 - Live 0x0000000000000000\nuvcvideo 139264 0 - Live 0x0000000000000000\n",
 "/proc/asound/cards": " 0 [PCH            ]: HDA-Intel - HDA Intel PCH\n                      HDA Intel PCH at 0x603d1a8000 irq 162\n 1 [NVidia         ]: HDA-Intel - HDA NVidia\n                      HDA NVidia at 0xb3080000 irq 17",
 "/proc/sys/kernel/tainted": "12801",   # P + W + O + E
 "/etc/linuxmint/info": 'RELEASE=7\nCODENAME=gigi\nEDITION="Cinnamon"\nDESCRIPTION="LMDE 7 Gigi"\nDESKTOP=Gnome\nGRUB_TITLE=LMDE 7 Cinnamon',
 "/etc/os-release": 'PRETTY_NAME="LMDE 7 (gigi)"\nNAME="LMDE"\nVERSION_ID="7"\nID=linuxmint\nID_LIKE=debian\nVERSION_CODENAME=gigi\nDEBIAN_CODENAME=trixie',
 "/etc/debian_version": "13.1",
 "/proc/acpi/ibm/fan": "status:\t\tenabled\nspeed:\t\t2890\nlevel:\t\tauto",
 "/sys/power/state": "freeze mem disk",
 "/sys/power/mem_sleep": "s2idle [deep]",
 "/sys/devices/system/cpu/cpu0/thermal_throttle/package_throttle_count": "37",
 "/sys/devices/system/cpu/cpu0/cpufreq/base_frequency": "1300000",
 "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq": "4400000",
 "/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq": "400000",
 "/proc/bus/input/devices": 'I: Bus=0011 Vendor=0001 Product=0001 Version=ab54\nN: Name="AT Translated Set 2 keyboard"\nH: Handlers=sysrq kbd leds event3\n\nI: Bus=0018\nN: Name="ELAN0676:00 04F3:3195 Touchpad"\nH: Handlers=mouse1 event7\n\nI: Bus=0003\nN: Name="Logitech MX Master 3"\nH: Handlers=sysrq kbd leds event9 mouse2\n\nI: Bus=0019\nN: Name="Power Button"\nH: Handlers=kbd event1\n',
 "/etc/ufw/ufw.conf": "ENABLED=no\nLOGLEVEL=low",
 "/etc/timeshift/timeshift.json": '{"backup_device_uuid": "9f0c2b6e-1d5a-4c7b-8e21-aa00bb11cc22", "schedule_monthly": "false", "schedule_weekly": "false", "schedule_daily": "false", "do_first_run": "true"}',
 "/proc/swaps": "Filename\t\t\t\tType\t\tSize\t\tUsed\t\tPriority\n/dev/zram0                              partition\t4194300\t\t0\t\t100",
}

def patch(rx):
    real = rx.read
    rx.read = lambda p, default="": FAKE[p] if p in FAKE else real(p, default)
    os.environ.update(XDG_CURRENT_DESKTOP="X-Cinnamon", XDG_SESSION_TYPE="x11", LANG="es_ES.UTF-8", SHELL="/bin/bash")
    rx._PATH = BIN + ":" + rx._PATH
    rx._ENV["PATH"] = rx._PATH
    rx.platform.release = lambda: "6.12.48+deb13-amd64"

if __name__ == "__main__":
    build()
    import syscheckup as rx
    patch(rx)
    rx.set_language(os.environ.get("MM_IDIOMA", "es"))      # MM_IDIOMA=en|fr|ja|zh para probar traducciones
    mode = sys.argv[1] if len(sys.argv) > 1 else "texto"
    if mode == "texto":
        for _ in range(3):
            rx.SAMPLER.tick(); __import__("time").sleep(0.4)
        print(rx.to_text(rx.collect_all(), "--anon" in sys.argv))
    elif mode in ("html", "json", "foro", "csv"):
        for _ in range(3):
            rx.SAMPLER.tick(); __import__("time").sleep(0.4)
        out = rx.export({"html": "html", "json": "json", "foro": "foro", "csv": "csv"}[mode],
                        rx.collect_all(), "--anon" in sys.argv)
        open(sys.argv[2], "w").write(out) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else print(out)
    else:
        rx.run_gui(False, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None,
                   int(sys.argv[4]) if len(sys.argv) > 4 else 3500)
