# Gandalf Modbus Wizard 

![Gandalf Modbus Wizard Banner](Images/Banner.jpg)

[![Download](https://img.shields.io/badge/Download-v1.12-blue?style=for-the-badge&logo=github)](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/releases/tag/v1.12)
[![Buy Me A Coffee](https://img.shields.io/badge/Support-Buy%20Me%20A%20Coffee-orange?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/bennycohen)

**Gandalf Modbus Wizard** is a comprehensive, free utility designed to facilitate the scanning, troubleshooting, and simulation of Modbus TCP and Modbus RTU devices.

*Designed by an engineer, for engineersto take the guesswork out of serial communications.*

---

##  Support the Project
This tool is completely free to use. However, it takes significant personal time to develop and maintain. If this wizard helps you solve a tricky connection issue or saves you time in the field, please consider supporting the project!

[** Buy Me a Coffee**](https://buymeacoffee.com/bennycohen)

---

##  Video Tutorial
** NOTE: New video tutorial featuring the latest UI + diagnostics (v1.12) is coming soon!**

In the meantime, the core concepts from the previous version's guide still apply:

[![Gandalf Modbus Wizard Tutorial](https://img.youtube.com/vi/Xit_uzv_hek/0.jpg)](https://www.youtube.com/watch?v=Xit_uzv_hek)

---

##  Features

###  Live Trend Analysis (New!)
Visualize your data in real-time to diagnose stability issues or tune loops.
* **Real-time Graphing:** Select specific registers to plot values instantly.
* **PID Tuning Helper:** Perfect for visualizing PV (Process Variable), SP (Setpoint), and OP (Output) simultaneously.
* **Dynamic Theme:** Charts automatically adapt to Dark Mode.

![Live Trend Analysis](Images/LiveTrend.jpg)

---

###  Auto Detection Wizard
Stop guessing your connection settings. This feature brute-forces combinations to automatically detect the correct parameters for your Modbus RTU device.
* **COM Port:** Select your target port.
* **Scan Range:** Define the Device ID range to probe.
* **Parameters:** Automatically cycles through Baud Rates, Parities, Data Bits, and Stop Bits.

![Auto Detection Wizard](Images/AutoDetect.jpg)

---

###  Modbus RTU Scanner
Once your connection is established, use the RTU Scanner to visualize data.
* **Relaxed Timing:** Now supports **1.5 Stop Bits** for improved stability with Arduino/Embedded devices.
* **Control:** Write directly to registers from the interface.
* **Visuals:** Combine consecutive registers (Normal / Reverse) for 32-bit values.

![Modbus RTU Scanner](Images/RTUScanner.jpg)

*Connection Success details are now clearly visible:*
![RTU Connection Success](Images/RTUConnect.jpg)

---

###  Modbus TCP Scanner
Connect to and diagnose Modbus TCP devices over a network.
* **Connection:** Localhost or target IP (Default Port 502).
* **Flexibility:** Custom polling rates and Start / End address ranges.
* **Data Formatting:** Combined registers in Normal or Reverse order.

---

###  Modbus Simulation
Need to test a SCADA or HMI client? Spin up a virtual device instantly.
* **Robust Engine:** Completely rewritten threaded engine to prevent stalls.
* **Manual Overrides:** Writing to a register now "Locks" the value (indicated by `[LOCKED]`), preventing the auto-generator from overwriting your test data.
* **Simulation:** Generates valid Modbus responses for client testing.

![Modbus Simulation Locked](Images/Simulation.jpg)

---

##  What's New in Version 1.12

 **Release link (v1.12):**
 https://github.com/Bennyco86/Gandalf-Modbus-Wizard/releases/tag/v1.12

### Major Features

 **RTU over TCP (RTU Tunnel)**
Added a Transport / Framing selector to the TCP Scanner to support RTU frames over TCP sockets (no MBAP header). This matches Waveshare-style gateways and Modscanstyle RTU tunneling.

 **Proxy Helper for Local Testing**
Included a standalone RTU-over-TCP proxy tool to test against the built-in Modbus TCP simulator without hardware.

---

##  What's New in Version 1.11

 **Release link (v1.11):**
 https://github.com/Bennyco86/Gandalf-Modbus-Wizard/releases/tag/v1.11

### Major Features

 **Futuristic UI Overhaul**
Migrated to a modern flat UI with a cleaner layout, smoother scaling, and a seamless **Dark/Light** theme.
Also includes **DPI-aware** behavior for sharp rendering on high-DPI displays.

 **New Network Diagnostics Tab**
Built-in tools to help when youre chasing comms issues:
- **Traffic Monitor (Packet Sniffer):** view raw Modbus hex traffic in real-time with a high-performance rolling log
- **CRC16 Calculator:** manually verify checksums for firmware/debugging work

 **Enhanced Auto-Detection**
Improved algorithms for Arduino and embedded device boot timing quirks  faster and more reliable when trying to find that lost baud rate.

 **Save Your Config**
Save and load RTU connection settings to **JSON**, making it easy to swap between multiple field devices without re-entering parameters.

---

##  What's New in Version 1.10

### Major Features

 **Live Trend Graphing**
Added a popup real-time chart. Select any rows in the scanner grid and click **"Trend Selected"** to visualize data over time. Essential for diagnosing intermittent sensor issues or PID loop behavior.

 **Excel Export with Charts**
Export your scan history directly to an Excel file. The wizard now automatically generates a line chart for the first 15 registers in your log!

![Excel Export Chart](Images/ExcelExport.jpg)

 **Full Windows Application**
Gandalf has graduated to a standalone Windows Application. The installer handles all dependenciesno Python knowledge required.

### Critical Fixes & Improvements

 **Simulation Race Condition Fix**
Rewrote the Simulation Server to use **Thread Locking**. This eliminates the "Input/Output" error and application stall that occurred when writing values to the simulator during a scan.

 **RTU Stability Update**
Added support for **1.5 Stop Bits** logic. This fixes framing errors and connection drops commonly seen with Arduino, ESP32, and other embedded Modbus slaves that have slight timing jitters.

 **Float Value Support**
Fixed an issue where writing Float values to registers was not parsing correctly. You can now write 32-bit floating point numbers to supported devices seamlessly.

 **Dynamic Dark Mode**
The Live Trend charts now respect the global Dark Mode setting, switching to a dark background and white axis text automatically.

---

##  Getting Started

### Option 1: Windows Installer (Recommended)

1. **Download:**
   Get the latest installer from the official release page:
    https://github.com/Bennyco86/Gandalf-Modbus-Wizard/releases/tag/v1.12

2. **Install:**
   Run `Gandalf_Wizard_Setup.exe` and follow the setup wizard.
   
   ![Setup Preview](Images/Setup_Screenshot.jpg)

3. **Launch:**
   Start Gandalf Modbus Wizard from the Desktop or Start Menu.

---

##  Support & Contribution

If you find value in Gandalf Modbus Wizard, your support is greatly appreciated. It helps drive continued development and feature improvements.

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-%23FFDD00.svg?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/bennycohen)

---

### Contributing
Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on the code of conduct and how to submit pull requests.

---

### Credits & License
If you share this software, please credit **Benny Cohen**.
This project is licensed under the **Gandalf Modbus Wizard License**  see [LICENSE.md](LICENSE.md) for details.
