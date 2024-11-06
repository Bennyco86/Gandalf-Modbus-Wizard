# Gandalf Modbus Wizard - Version 1.3

Gandalf Modbus Wizard is a powerful tool for scanning and interacting with Modbus devices, supporting both Modbus TCP and Modbus RTU protocols. This release (v1.3) includes several key fixes and enhancements to improve user experience and functionality.

## Key Fixes and Enhancements in Version 1.3

1. **Automatic Register Combination**  
   - Registers now automatically combine based on the display format selected. For example:
     - **Float**: Combines two registers
     - **Double**: Combines four registers

2. **Streamlined Interface**  
   - Removed the "Combine Registers" checkbox and the combination order dropdown. Register combinations now adjust automatically, simplifying the interface.

3. **Corrected Coil Status and Input Status Functionality**  
   - Fixed issues with Coil Status and Input Status (function codes 1 and 2), ensuring correct operation during scans.

4. **Enhanced Address Display Options**  
   - Added a toggle for displaying addresses in either hexadecimal or decimal format.
   - Removed prefixes from hexadecimal and binary representations, providing cleaner output.

5. **Accurate Combined Address Display**  
   - Combined register addresses are displayed correctly according to the chosen format, with accurate ordering when using reversed combinations.

## Features

- Supports both Modbus TCP and Modbus RTU protocols.
- Scans for Coil Status, Input Status, Holding Registers, and Input Registers.
- Allows real-time register value display in Decimal, Binary, Hexadecimal, Float, and Double formats.
- Provides an option to download scan logs for analysis and troubleshooting.

## Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/yourusername/GandalfModbusWizard.git
