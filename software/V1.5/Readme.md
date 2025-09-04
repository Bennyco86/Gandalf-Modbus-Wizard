Gandalf Modbus Wizard — v1.5 (Windows)

This folder contains the v1.5 Windows build of Gandalf Modbus Wizard.

⬇️ Download

ZIP: Gandalf_Rev1.5.zip

Extract the ZIP and run GandalfModbusWizard.exe.
If SmartScreen warns about an unsigned app: More info → Run anyway.

✨ What’s new in v1.5

Treeview UI for TCP & RTU

Left-aligned columns, resizable area

Minimal flicker (in-place updates; scroll position preserved)

Undefined handling

Value shows undefined

Undefined rows sorted after defined rows

Consistent address ordering by numeric start address (works with 2-word floats & 4-word doubles)

Float / Double views with 3-decimal formatting

Includes Swapped Float and Swapped Double (word-order aware)

Large number display

Scientific notation for magnitudes ≥ 10,000 (e.g., 1.23*10^5)

Export results to Excel (.xlsx) or CSV (TCP & RTU)

RTU quality of life

Custom baud: choose Custom to reveal an input box and type any value

COM refresh, parity/stop/data bits

Polling rate polish

Slider ↔ entry stay in sync

Optional write

“Enable Write” guarded by confirmation (Holding Registers)

🚀 Quick start

Open Modbus TCP Scanner or Modbus RTU Scanner.

Set address range and point type (e.g., 03: Holding Registers).

Set Device ID (unit), host/port (TCP) or COM/baud/serial settings (RTU).

Click Start Scan.

Use the bottom buttons to view as Decimal / Binary / Hex / Float / Swapped Float / Double / Swapped Double.

Click Download Results to export the current grid.

🏗️ Build a Windows .exe (from source)

We ship a helper script:

Double-click build_exe.bat

It will:

create a venv

install requirements (including pyinstaller)

build a single, GUI-only exe in dist/GandalfModbusWizard.exe

Optional:

Add an icon: edit the batch and append --icon wizard.ico to the pyinstaller line.

Need a console window? remove --windowed.

🔧 Configuration notes

Floats/Doubles: “Swapped” buttons interpret 16-bit Modbus words in reverse order. Use the swapped variants when your device stores low-order words first.

Undefined means a read failed or there weren’t enough trailing registers to assemble a float/double group.

Scientific notation appears in decimal/float/double modes for values ≥ 10,000.

🗒️ Changelog (v1.5 highlights)

Rewrote results UI using Treeview (left-aligned, resizable).

Flicker-free updates with preserved scroll position.

Undefined → at bottom + labeled as undefined (not just red).

Added 3-decimal rounding for float/double.

Clarified Swapped Float/Double decoding paths.

Added Export to Excel/CSV for TCP & RTU.

Added Custom baud for RTU + serial settings polish.

Added Write Register section (guarded by confirmation).

Integrated Auto Detection Wizard → RTU parameter transfer.
