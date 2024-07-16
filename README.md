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

![Modbus TCP Scanner](https://github.com/bennyco86/YourRepositoryName/raw/main/Modbus%20TCP%20scanner.PNG)

### Auto Detection Wizard
This feature helps automatically detect the correct connection settings for your Modbus RTU device.

- **COM Port**: Select the appropriate COM port.
- **Device ID Range**: Specify the range of device IDs to scan.
- **Baud Rates, Parities, Data Bits, and Stop Bits**: Adjust these settings to match your device.
- **Register Type and Range**: Choose the register type and range to scan.

![Auto Detection Wizard](https://github.com/bennyco86/YourRepositoryName/raw/main/Gandalf.PNG)

### Modbus RTU Scanner
After establishing a connection with the Auto Detection Wizard, use this tool to scan and read the registers of your Modbus RTU device.

- **COM Port**: Ensure the correct COM port is selected.
- **Baud Rate, Parity, Data Bits, and Stop Bits**: These should be pre-selected after using the Auto Detection Wizard.
- **Start and End Address**: Specify the register address range.
- **Device ID**: Enter the Modbus device ID.
- **Modbus Point Type**: Choose from Coil Status, Input Status, Holding Registers, or Input Registers.
- **Polling Rate**: Adjust the rate in milliseconds.

![Modbus RTU Scanner](https://github.com/bennyco86/YourRepositoryName/raw/main/Modbus%20RTU%20scanner.PNG)

## Getting Started

1. **Download the Tool**: Get the latest version from the [software folder](https://your-link-here).
2. **Run the Executable**: Extract the ZIP file and run `modbuswizard.exe`.
3. **Read the Documentation**: Refer to the included `README.md` for detailed usage instructions.

## Contributing

Please read the [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.