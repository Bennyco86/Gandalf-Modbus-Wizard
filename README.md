# Gandalf Modbus Wizard 🧙‍♂️

[![Download](https://img.shields.io/badge/Download-v1.9-blue?style=for-the-badge&logo=github)](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/tree/main/software/1.9)
[![Buy Me A Coffee](https://img.shields.io/badge/Support-Buy%20Me%20A%20Coffee-orange?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/bennycohen)

**Gandalf Modbus Wizard** is a comprehensive, free utility designed to facilitate the scanning, troubleshooting, and simulation of Modbus TCP and Modbus RTU devices. 

*Designed by an engineer, for engineers—to take the guesswork out of serial communications.*

---

### ☕ Support the Project
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
* **COM Port:** Select your target port.
* **Scan Range:** Define the Device ID range to probe.
* **Parameters:** Automatically cycles through Baud Rates, Parities, Data Bits, and Stop Bits.

![Auto Detection Wizard](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/Gandalf.PNG)

### 🔌 Modbus RTU Scanner
Once your connection is established, use the RTU Scanner to visualize data.
* **Configuration:** Parameters are pre-loaded from the Auto Detection Wizard.
* **Data Types:** Supports Coil Status, Input Status, Holding Registers, and Input Registers.
* **Visuals:** Combine consecutive registers (Normal/Reverse) for 32-bit values.
* **Control:** Write directly to registers from the interface.

![Modbus RTU Scanner](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/Modbus%20RTU%20scanner.PNG)
![Modbus RTU Combined](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/combined%20rtu.png)

### 🌐 Modbus TCP Scanner
Connect to and diagnose Modbus TCP devices over a network.
* **Connection:** Support for Localhost or target IP addresses (Default Port 502).
* **Flexibility:** Custom polling rates and Start/End address ranges.
* **Data Formatting:** View combined registers in Normal or Reverse order.

![Modbus TCP Scanner](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/Modbus%20TCP%20scanner.PNG)
![Combined Normal TCP](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/combined%20normal.PNG)

### 🎮 Modbus Simulation
Need to test a SCADA or HMI client? Spin up a virtual device instantly.
* **Modes:** Supports both TCP and RTU simulation.
* **Customization:** Define Function Codes, Address Ranges, and Device IDs.
* **Simulation:** Generates valid Modbus responses for testing client applications.

![Modbus Simulation](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/Simulation.PNG)

---

## 🚀 Getting Started

1.  **Download:** Get the latest version (v1.8) from the [**software folder**](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/tree/main/software/1.8).
2.  **Run:** Extract the `.zip` file and launch `modbuswizard.exe`.
3.  **Connect:** Use the Auto Detection tab to find your device, or jump straight to the Scanners if you know your settings.

> **⚠️ Important Notice:** > This software is not currently code-signed by Microsoft. Your antivirus or Windows SmartScreen may flag it as unrecognized. This is normal for open-source Python tools compiled with PyInstaller. You may need to select "Run Anyway" or whitelist the application.

---

## 🤝 Support & Contribution

If you find value in Gandalf Modbus Wizard, your support is greatly appreciated. It motivates me to keep adding features and fixing bugs!

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-%23FFDD00.svg?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/bennycohen)

### Contributing
Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

### Credits & License
If you share this software, please credit **Benny Cohen**.  
This project is licensed under the Gandalf Modbus Wizard License - see [LICENSE.md](LICENSE.md) for details.
