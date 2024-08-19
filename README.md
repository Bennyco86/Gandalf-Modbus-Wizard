
# Gandalf Modbus Wizard

Gandalf Modbus Wizard is a comprehensive tool designed to facilitate the scanning and troubleshooting of Modbus TCP and Modbus RTU devices. It includes three main features: Modbus TCP Scanner, Auto Detection Wizard, and Modbus RTU Scanner.

## Features

### Modbus TCP Scanner
This tool allows you to connect to a Modbus TCP device, read the registers, and display the values in various formats.

- **Host**: Select between 'localhost' or input the target IP address.
- **Service Port**: Default is 502 but can be changed.
- **Start and End Address**: Specify the address range to scan.
- **Device ID**: Enter the Modbus device ID.
- **Modbus Point Type**: Choose from Coil Status, Input Status, Holding Registers, or Input Registers.
- **Polling Rate**: Adjust the rate in milliseconds.
- **Combine Registers**: Option to combine two consecutive registers in either normal or reverse order.
- **Write Registers**: Directly write to registers from the scanner interface.

![Modbus TCP Scanner](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/Modbus%20TCP%20scanner.PNG)
![Combined Normal TCP](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/combined%20normal.PNG)
![Combined Reverse TCP](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/combined%20reverse.PNG)

### Auto Detection Wizard
This feature helps automatically detect the correct connection settings for your Modbus RTU device.

- **COM Port**: Select the appropriate COM port.
- **Device ID Range**: Specify the range of device IDs to scan.
- **Baud Rates, Parities, Data Bits, and Stop Bits**: Adjust these settings to match your device.
- **Register Type and Range**: Choose the register type and range to scan.

![Auto Detection Wizard](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/Gandalf.PNG)

### Modbus RTU Scanner
After establishing a connection with the Auto Detection Wizard, use this tool to scan and read the registers of your Modbus RTU device.

- **COM Port**: Ensure the correct COM port is selected.
- **Baud Rate, Parity, Data Bits, and Stop Bits**: These should be pre-selected after using the Auto Detection Wizard.
- **Start and End Address**: Specify the register address range.
- **Device ID**: Enter the Modbus device ID.
- **Modbus Point Type**: Choose from Coil Status, Input Status, Holding Registers, or Input Registers.
- **Polling Rate**: Adjust the rate in milliseconds.
- **Combine Registers**: Option to combine two consecutive registers in either normal or reverse order.
- **Write Registers**: Directly write to registers from the scanner interface.

![Modbus RTU Scanner](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/Modbus%20RTU%20scanner.PNG)
![Combined Normal RTU](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/combined%20rtu.PNG)
![Combined Reverse RTU](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/combined%20reverse%20rtu.PNG)

### Modbus Simulation
This feature allows you to simulate Modbus TCP and RTU devices.

- **Simulation Type**: Choose between TCP or RTU.
- **Host/Port**: For TCP simulation.
- **COM Port/Baudrate/Stop Bits/Parity/Data Bits**: For RTU simulation.
- **Function Code**: Choose from Coil Status, Input Status, Holding Registers, or Input Registers.
- **Address Start/End**: Specify the address range to simulate.
- **Device ID**: Enter the Modbus device ID.

![Modbus Simulation](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/blob/main/Simulation.PNG)

## Getting Started

1. **Download the Tool**: Get the latest version from the [software folder](https://github.com/Bennyco86/Gandalf-Modbus-Wizard/tree/main/software).
2. **Run the Executable**: Extract the ZIP file and run `modbuswizard.exe`.
3. **Read the Documentation**: Refer to the included `README.md` for detailed usage instructions.

## Support

This program took me a long time to develop. If you like it, I'd appreciate your support!  
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-%23FFDD00.svg?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/bennycohen)

## Contributing

Please read the [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## License

This project is licensed under the Gandalf Modbus Wizard License - see the [LICENSE.md](LICENSE.md) file for details.

## Important Notice

Please note that this software has not been signed yet, so your antivirus or Windows might flag it. I plan to have it signed in future releases, but I'm currently not familiar with the process.

If you share this software, please credit Benny Cohen.
