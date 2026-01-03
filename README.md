# Gandalf Modbus Wizard 🧙‍♂️

[![Download](https://img.shields.io/badge/Download-v1.9-blue?style=for-the-badge&logo=github)](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/releases/tag/v1.9)
[![Buy Me A Coffee](https://img.shields.io/badge/Support-Buy%20Me%20A%20Coffee-orange?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/bennycohen)

**Gandalf Modbus Wizard** is a comprehensive, free utility designed to facilitate the scanning, troubleshooting, and simulation of Modbus TCP and Modbus RTU devices.

*Designed by an engineer, for engineers—to take the guesswork out of serial communications.*

---

## ☕ Support the Project
This tool is completely free to use. However, it takes significant personal time to develop and maintain. If this wizard helps you solve a tricky connection issue or saves you time in the field, please consider supporting the project!

[**☕ Buy Me a Coffee**](https://buymeacoffee.com/bennycohen)

---

## 📺 Video Tutorial
Watch the full guide on how to use the Auto Detection Wizard, Scanners, and Simulator:

[![Gandalf Modbus Wizard Tutorial](https://img.youtube.com/vi/Xit_uzv_hek/0.jpg)](https://www.youtube.com/watch?v=Xit_uzv_hek)

---

## ✨ Features

### 🔍 Auto Detection Wizard
Stop guessing your connection settings. This feature brute-forces combinations to automatically detect the correct parameters for your Modbus RTU device.

* **COM Port:** Select your target port  
* **Scan Range:** Define the Device ID range to probe  
* **Parameters:** Automatically cycles through Baud Rates, Parities, Data Bits, and Stop Bits  

![Auto Detection Wizard](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/Gandalf.PNG)

---

### 🔌 Modbus RTU Scanner
Once your connection is established, use the RTU Scanner to visualize data.

* **Configuration:** Parameters are pre-loaded from the Auto Detection Wizard  
* **Data Types:** Coil Status, Input Status, Holding Registers, Input Registers  
* **Visuals:** Combine consecutive registers (Normal / Reverse) for 32-bit values  
* **Control:** Write directly to registers from the interface  

![Modbus RTU Scanner](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/Modbus%20RTU%20scanner.PNG)  
![Modbus RTU Combined](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/combined%20rtu.png)

---

### 🌐 Modbus TCP Scanner
Connect to and diagnose Modbus TCP devices over a network.

* **Connection:** Localhost or target IP (Default Port 502)  
* **Flexibility:** Custom polling rates and Start / End address ranges  
* **Data Formatting:** Combined registers in Normal or Reverse order  

![Modbus TCP Scanner](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/Modbus%20TCP%20scanner.PNG)  
![Combined Normal TCP](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/combined%20normal.PNG)

---

### 🎮 Modbus Simulation
Need to test a SCADA or HMI client? Spin up a virtual device instantly.

* **Modes:** Modbus TCP and Modbus RTU simulation  
* **Customization:** Function Codes, Address Ranges, Device IDs  
* **Simulation:** Generates valid Modbus responses for client testing  

![Modbus Simulation](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/Simulation.PNG)

---

## 🚀 What's New in Version 1.9

### Major Features

📦 **Official Windows Installer**  
Gandalf Modbus Wizard is now available as a professional **Windows installer (Setup.exe)**, automatically creating Start Menu and Desktop shortcuts.

📈 **Excel Trend Logs**  
Export scan history directly to **Excel (.xlsx)** with **auto-generated charts** for visualizing register value trends over time.  
*(Note: Requires `XlsxWriter` if running from source.)*

🌙 **Dark Mode**  
Added a native **Dark Mode toggle** for improved usability in low-light environments.

---

### Critical Fixes & Improvements

🛡️ **Crash Prevention (Permissions)**  
Fixed a critical crash affecting restricted user accounts by moving log generation to the Windows **AppData** directory.  
This prevents *“Permission Denied”* errors when running from read-only locations such as `Program Files`.

🔌 **COM Port Sharing Improvements**  
Improved serial connection handling between the **Auto Detection Wizard** and **RTU Scanner**, preventing *Access Denied* conflicts when switching tabs.

🐍 **Stability & Compatibility**  
Dependencies are now locked to **pymodbus 2.5.3** to ensure consistent behavior and prevent breaking API changes.

---

## 🚀 Getting Started

### Option 1: Windows Installer (Recommended)

1. **Download:**  
   Get the latest installer from the official release page:  
   👉 https://github.com/Bennyco86/Gandalf-Modbus-Wizard/releases/tag/v1.9

2. **Install:**  
   Run `Gandalf_Setup_v1.9.exe` and follow the setup wizard.

3. **Launch:**  
   Start Gandalf Modbus Wizard from the Desktop or Start Menu.

---

### Option 2: Portable / Source Version

1. Download the ZIP from the release page  
2. Extract and run `modbuswizard.exe`

---

> ⚠️ **Important Notice**  
> This software is not currently code-signed by Microsoft. Windows SmartScreen or antivirus software may flag it as unrecognized.  
> This is normal for open-source Python applications compiled with PyInstaller.  
> You may need to select **“Run Anyway”** or whitelist the application.

---

## 🤝 Support & Contribution

If you find value in Gandalf Modbus Wizard, your support is greatly appreciated. It helps drive continued development and feature improvements.

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-%23FFDD00.svg?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/bennycohen)

---

### Contributing
Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on the code of conduct and how to submit pull requests.

---

### Credits & License
If you share this software, please credit **Benny Cohen**.  
This project is licensed under the **Gandalf Modbus Wizard License** – see [LICENSE.md](LICENSE.md) for details.
