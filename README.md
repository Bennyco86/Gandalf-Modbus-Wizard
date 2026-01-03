Gandalf Modbus Wizard 🧙‍♂️ (Internal Dev Build)
Gandalf Modbus Wizard is a comprehensive, free utility designed to facilitate the scanning, troubleshooting, and simulation of Modbus TCP and Modbus RTU devices.

Designed by an engineer, for engineers—to take the guesswork out of serial communications.

📝 Changelog: v1.9 (Developer Update)
Reflects changes made during the source code backup session.

📦 Source Code Backup: Full Python source code committed to the repository (no longer just the compiled .exe).

📄 Dependency Tracking: Added requirements.txt to allow for single-command environment setup (pip install -r requirements.txt).

🧹 Repository Hygiene: Added a standard Python .gitignore to exclude __pycache__, virtual environments, and system files.

🎨 Assets: Integrated GandalfModbusWizard_BMP.ico for application branding.

🔧 Git Configuration: Fixed branch pointers and established main as the primary development branch.

☕ Support the Project
This tool is completely free to use. However, it takes significant personal time to develop and maintain. If this wizard helps you solve a tricky connection issue or saves you time in the field, please consider supporting the project!

☕ Buy Me a Coffee

📺 Video Tutorial
Watch the full guide on how to use the Auto Detection Wizard, Scanners, and Simulator:

✨ Features
🔍 Auto Detection Wizard
Stop guessing your connection settings. This feature brute-forces combinations to automatically detect the correct parameters for your Modbus RTU device.

COM Port: Select your target port.

Scan Range: Define the Device ID range to probe.

Parameters: Automatically cycles through Baud Rates, Parities, Data Bits, and Stop Bits.

🔌 Modbus RTU Scanner
Once your connection is established, use the RTU Scanner to visualize data.

Configuration: Parameters are pre-loaded from the Auto Detection Wizard.

Data Types: Supports Coil Status, Input Status, Holding Registers, and Input Registers.

Visuals: Combine consecutive registers (Normal/Reverse) for 32-bit values.

Control: Write directly to registers from the interface.

🌐 Modbus TCP Scanner
Connect to and diagnose Modbus TCP devices over a network.

Connection: Support for Localhost or target IP addresses (Default Port 502).

Flexibility: Custom polling rates and Start/End address ranges.

Data Formatting: View combined registers in Normal or Reverse order.

🎮 Modbus Simulation
Need to test a SCADA or HMI client? Spin up a virtual device instantly.

Modes: Supports both TCP and RTU simulation.

Customization: Define Function Codes, Address Ranges, and Device IDs.

Simulation: Generates valid Modbus responses for testing client applications.

🚀 Getting Started (Dev Mode)
Clone: git clone https://github.com/Bennyco86/Gandalf-Private-Backup.git

Install Dependencies:

Bash

pip install -r requirements.txt
Run Source: Execute the main Python script (e.g., python main.py or similar).

⚠️ Important Notice: This software is not currently code-signed by Microsoft. Your antivirus or Windows SmartScreen may flag compiled versions as unrecognized. This is normal for open-source Python tools compiled with PyInstaller.

🤝 Support & Contribution
If you find value in Gandalf Modbus Wizard, your support is greatly appreciated. It motivates me to keep adding features and fixing bugs!

Contributing
Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests.

Credits & License
If you share this software, please credit Benny Cohen. This project is licensed under the Gandalf Modbus Wizard License - see LICENSE.md for details.
