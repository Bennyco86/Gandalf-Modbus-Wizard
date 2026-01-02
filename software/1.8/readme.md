
# Gandalf Modbus Wizard 🧙‍♂️

**Gandalf Modbus Wizard** is a comprehensive, open-source tool designed to simplify the scanning, troubleshooting, and simulation of Modbus TCP and Modbus RTU devices. 

Designed for engineers and automation professionals, it removes the guesswork from serial communications by automatically detecting connection parameters.

## 🚀 Download & Support

| **Latest Version** | **Support the Developer** |
|:---:|:---:|
| [**⬇️ Download v1.8 Here**](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/tree/main/software/1.8) | [**☕ Buy Me a Coffee**](https://buymeacoffee.com/bennycohen) |

---

## ✨ Key Features

### 🔍 Auto Detection Wizard
Stop guessing your serial settings. The wizard bruteforces combinations of **Baud Rate**, **Parity**, **Data Bits**, and **Stop Bits** to identify the correct configuration for your slave device automatically.

### 🔌 Modbus RTU & TCP Scanners
Once connected, visualize your data in real-time.
* **Flexible Addressing:** Scan specific ranges or widely dispersed registers.
* **Data Types:** Decode registers as `Int16`, `UInt16`, `Int32`, `Float32`, `Float64`, and more.
* **Data Formatting:** View raw values in **Decimal**, **Hex**, or **Binary**.
* **Swap Modes:** Handle endianness issues with Byte Swap, Word Swap, or Both.

### 🎮 Modbus Simulation
Need to test a client application (SCADA/HMI) but don't have the hardware? 
* Spin up a **Modbus TCP Server** instantly.
* Define valid address ranges (Sparse Mode).
* Auto-generate dynamic data (Sine waves, counters) to verify your client is reading correctly.

### 💾 Export Results
Export your scanned register data directly to **CSV** for reporting or further analysis.

---

## 📦 Installation

1.  **Download** the latest version from the link above.
2.  **Extract** the `.zip` file to a folder on your computer.
3.  Run the **GandalfModbusWizard.exe**.
    * *Note: Because this software is not signed by Microsoft, your antivirus (or Windows SmartScreen) may flag it. This is normal for open-source Python tools compiled with PyInstaller. You may need to "Run Anyway" or whitelist the file.*

## 🛠️ Built With
* **Python**
* **Tkinter** (UI)
* **Pymodbus** (Protocol handling)

## 📄 License
This project is open-source. Feel free to contribute or fork the repository!

---
*Created by [Bennyco86](https://github.com/Bennyco86)*
