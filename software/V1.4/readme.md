# Modbus TCP Scanner

## Recent Changes

This update introduces several new features and enhancements to improve the usability, performance, and responsiveness of the Modbus TCP Scanner.

### Key Changes:

1. **Auto Detection of Format**
   - Added an auto-detect button that determines the most suitable format for displaying register values. The tool now tries different formats, such as Decimal, Float, Double, and selects the one that best fits the scanned data.

2. **UI Enhancements**
   - Improved button alignments for a cleaner look and better user experience.
   - Display formats now use 3 decimal points before the exponent for float and double values, enhancing the readability of data.

3. **Responsive Scanning and Improved Efficiency**
   - Scanning is now performed in batches of up to 10 registers at a time, improving responsiveness for larger scans.
   - Removed logging, which was initially used for debugging but added lag to the system. The tool now runs faster without this unnecessary overhead.

4. **Start/Stop Scan Improvements**
   - Enhanced the responsiveness of starting and stopping scans, reducing delays when interacting with the scanner controls.

### Removed Features:

- **Logging**: Removed the logging feature as it added lag to the system. It was initially used to diagnose issues but is no longer needed, leading to a cleaner and more efficient codebase.

### How to Use

- Clone or download the repository.
- Download the Zip file with the .exe in it (program is still unsigned)
- Use the provided buttons to configure the target IP, start/end addresses, and other parameters.
- Start scanning to view the defined and undefined registers, with options to auto-detect formats or manually set display preferences.


### Future Improvements
- Implementing flicker-free updates using double buffering to further enhance the UI experience.
- Explore more dynamic data visualization features.
