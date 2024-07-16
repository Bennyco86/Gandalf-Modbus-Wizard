# Gandalf Modbus Wizard

## Introduction
The Gandalf Modbus Wizard is a comprehensive tool designed to facilitate working with Modbus devices. It integrates three main functionalities into a single tool: Modbus TCP Register Scan, Brute Force Connection for Modbus RTU Devices, and Modbus RTU Scanner.

## Libraries and Versions
| Library       | Version | Purpose                                                                  |
|---------------|---------|--------------------------------------------------------------------------|
| Tkinter       | Built-in| Provides the GUI framework for creating windows, dialogs, buttons, etc.  |
| Pymodbus      | 2.5.3   | Enables communication with Modbus devices. Specific version for RTU.     |
| MinimalModbus | 2.1.1   | Simple Modbus RTU/ASCII implementation for Python.                       |
| PySerial      | 3.5     | Provides serial port communication capabilities for RTU connection.      |
| Logging       | Built-in| Provides logging capabilities to track and debug program execution.      |
| Threading     | Built-in| Handles concurrent execution for background scans.                       |
| Struct        | Built-in| Converts between Python values and C structs as Python bytes objects.     |
| Time          | Built-in| Handles timing functions such as delays.                                 |
| FileDialog    | Built-in| Provides file dialog interfaces to save and load files.                  |

## Explanation of the Program
### Modbus TCP Register Scan
- **Objective:** Scan all available registers on a Modbus TCP device.
- **Implementation:** Scans from start to end address, marking undefined registers, and displays results in the GUI.

### Brute Force Connection for Modbus RTU Devices
- **Objective:** Establish connection with unknown communication parameters.
- **Implementation:** Tries all possible communication settings until successful connection and displays the settings used.

### Modbus RTU Scanner
- **Objective:** Scan RTU devices using known parameters.
- **Implementation:** Connects to the device, scans specified registers, and displays results in multiple formats.

## User Guides

### Modbus TCP Scanner
![Modbus TCP Scanner](https://github.com/username/repository/blob/main/images/modbus_tcp_scanner.png)

1. **Host Selection:**
   - *Localhost*: For simulated values from Modsim.
   - *Other*: Input device's IP address for real devices.
2. **Target IP Address:** Enter IP when "Other" is selected.
3. **Service Port:** Default is 502, change if necessary.
4. **Start and End Address:** Define register range.
5. **Device ID:** Default is 1, change if necessary.
6. **Modbus Point Type:** Select from Coil Status, Input Status, Holding Registers, or Input Registers.
7. **Polling Rate:** Set scanning rate in milliseconds.
8. **Buttons:**
   - *Start Scan*: Begin scanning.
   - *Stop Scan*: Halt scanning.
   - *Clear Results*: Clear displayed results.
   - *Download Log*: Save log file.
9. **Result Display:** Shows scan results. Errors in red.
10. **Format Buttons:** Toggle display format.

### Auto Detection Wizard
![Auto Detection Wizard](https://github.com/username/repository/blob/main/images/auto_detection_wizard.png)

1. **COM Port:** Select from dropdown.
2. **Start Device ID / End Device ID:** Define slave ID range.
3. **Baudrates:** Select common or custom baud rates.
4. **Parities:** Choose None, Even, Odd, or custom.
5. **Databits:** Typically 8.
6. **Stopbits:** Choose 1, 1.5, or 2.
7. **Register Type:** Select Holding Registers or Input Registers.
8. **Register Read Range:** Define range to scan.
9. **Buttons:**
   - *Start Detection*: Begin detection.
   - *Stop Detection*: Halt detection.
   - *Clear Results*: Clear displayed results.
   - *Download Log*: Save log file.
10. **Progress & Current Settings:** Display during scan.

### Modbus RTU Scanner
![Modbus RTU Scanner](https://github.com/username/repository/blob/main/images/modbus_rtu_scanner.png)

1. **COM Port:** Select from dropdown.
2. **Baud Rate:** Choose from predefined or custom.
3. **Parity:** Choose None, Even, Odd, or custom.
4. **Data Bits:** Typically 8.
5. **Stop Bits:** Typically 1.
6. **Timeout (s):** Enter timeout duration.
7. **Start Address / End Address:** Define register range.
8. **Device ID:** Enter slave ID.
9. **Modbus Point Type:** Select type to scan.
10. **Polling Rate (ms):** Set rate.
11. **Batch Size:** Number of registers to read in one batch.
12. **Buttons:**
    - *Connect*: Establish connection.
    - *Disconnect*: Terminate connection.
    - *Start Scan*: Begin scanning.
    - *Stop Scan*: Halt scanning.
    - *Clear Results*: Clear displayed results.
    - *Download Log*: Save log file.
13. **Results Display:** Shows scan results in chosen format.

## Drive to Make the Program
The Gandalf Modbus Wizard was created to provide a user-friendly and robust tool for working with Modbus devices. It ensures comprehensive scans, facilitates brute force connections, and offers ease of use, addressing limitations of existing tools that rely on potentially inaccurate manufacturer-provided registers and known communication parameters.

## How to Include Images in README
To include images in your README, upload the images to your GitHub repository and link them using the following format:

```markdown
![Image Description](https://github.com/username/repository/blob/main/path_to_image.png)
