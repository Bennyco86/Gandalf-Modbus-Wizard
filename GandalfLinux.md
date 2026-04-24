# Gandalf Modbus Wizard on Linux

This guide describes how to install and run the Linux package. It assumes you are using the Debian `.deb` release.

## Install

```bash
sudo dpkg -i gandalf-modbus-wizard_1.12_amd64.deb
```

If dependencies are missing, run:

```bash
sudo apt -f install
```

Example output:

```text
(.venv) benny@Benny:/mnt/d/Downloads/gandalf$ sudo dpkg -i /mnt/d/Downloads/gandalf/linux_dist/gandalf-modbus-wizard_1.12_amd64.deb
[sudo] password for benny:
Selecting previously unselected package gandalf-modbus-wizard.
(Reading database ... 48173 files and directories currently installed.)
Preparing to unpack .../gandalf-modbus-wizard_1.12_amd64.deb ...
Unpacking gandalf-modbus-wizard (1.12) ...
Setting up gandalf-modbus-wizard (1.12) ...
Processing triggers for hicolor-icon-theme (0.17-2) ...
(.venv) benny@Benny:/mnt/d/Downloads/gandalf$
```

## Run

Launch from terminal:

```bash
gandalf-modbus-wizard
```

Or open it from your desktop menu (search for "Gandalf Modbus Wizard").

## Ports and Permissions

On Linux, ports below 1024 require root. The Modbus Simulation default of `502` will fail with `Permission denied`.
Use a non-privileged port such as:

- `1502` for Modbus TCP simulator
- `15020` for RTU-over-TCP proxy

Suggested workflow:

1. Set Modbus Simulation to `127.0.0.1:1502`
2. Run RTU-over-TCP proxy on `127.0.0.1:15020`
3. Use TCP Scanner:
   - MBAP: `127.0.0.1:1502`
   - RTU over TCP: `127.0.0.1:15020`

## Icon

The Linux package installs a PNG icon at:

`/usr/share/icons/hicolor/256x256/apps/gandalf-modbus-wizard.png`

If the icon does not appear in your launcher, run:

```bash
sudo gtk-update-icon-cache -f /usr/share/icons/hicolor
```



Reinstall output:

```text
(.venv) benny@Benny:/mnt/d/Downloads/gandalf$ sudo dpkg -i /mnt/d/Downloads/gandalf/linux_dist/gandalf-modbus-wizard_1.12_amd64.deb
(Reading database ... 48932 files and directories currently installed.)
Preparing to unpack .../gandalf-modbus-wizard_1.12_amd64.deb ...
Unpacking gandalf-modbus-wizard (1.12) over (1.12) ...
Setting up gandalf-modbus-wizard (1.12) ...
Processing triggers for hicolor-icon-theme (0.17-2) ...
(.venv) benny@Benny:/mnt/d/Downloads/gandalf$
```


Reinstall output (latest):

```text
(.venv) benny@Benny:/mnt/d/Downloads/gandalf$ sudo dpkg -i /mnt/d/Downloads/gandalf/linux_dist/gandalf-modbus-wizard_1.12_amd64.deb
[sudo] password for benny:
(Reading database ... 48933 files and directories currently installed.)
Preparing to unpack .../gandalf-modbus-wizard_1.12_amd64.deb ...
Unpacking gandalf-modbus-wizard (1.12) over (1.12) ...
Setting up gandalf-modbus-wizard (1.12) ...
Processing triggers for hicolor-icon-theme (0.17-2) ...
(.venv) benny@Benny:/mnt/d/Downloads/gandalf$
```

## Handoff Summary (Linux .deb)

Current packaging
- Linux build uses PyInstaller with `GandalfModbusWizard.spec`, then copies `linux_dist/GandalfModbusWizard` into `linux_pkg/gandalf-modbus-wizard_1.12_amd64/opt/gandalf-modbus-wizard/` and repacks `linux_dist/gandalf-modbus-wizard_1.12_amd64.deb`.
- Desktop entry: `linux_pkg/.../usr/share/applications/gandalf-modbus-wizard.desktop` includes `StartupWMClass=GandalfModbusWizard` and explicit icon path `Icon=/usr/share/icons/hicolor/256x256/apps/gandalf-modbus-wizard.png`.

Serial ports in Linux (WSL)
- Auto Detection Wizard now shows: "No serial ports detected in WSL (use Windows app or attach USB serial to WSL)".
- WSL cannot see Windows COM ports unless USB is attached to WSL via USB/IP; otherwise use the Windows build.

GUI theme issue
- App opened half dark/half light. TTK styles now sync to current `dark_mode` via `_apply_ttk_theme()`.
- Tabs were black on white because dark TTK styles were applied at startup; this should now be fixed.

Icon issues
- Taskbar icon shows; window icon (top-left inside app) may still be missing.
- `_apply_app_icon()` now prefers Tk native PNG, then system PNG, then ICO; also sets WM_CLASS for taskbar icon matching.
- If still missing, next step: force `wm_iconphoto` with explicit `/opt/gandalf-modbus-wizard/_internal/gandalf-modbus-wizard-256.png`.

Default port Windows/Linux
- Intended defaults: Windows `502`, Linux `1502`.
- Config override bug: `gandalf_config.json` could carry ports across platforms.
- Fix applied: config now stores `platform`; loading `tcp_last` resets to platform default when platform differs or is missing.

Remaining known issues
- Window icon may still not show in the titlebar (top-left).
- Verify theme is fully light on startup and tabs are not black.
- WSL serial ports still unavailable without USB attached to WSL.
