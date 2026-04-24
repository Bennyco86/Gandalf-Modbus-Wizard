# Gandalf Modbus Wizard v1.13 Release Notes

This release focuses on stability, performance, and usability improvements based on user feedback from v1.12.2.

## v1.13 - Fixes and Improvements

### 1) Float64 Excel Export Fix
- Fixed Excel export failure when `Float64` scans produced `NaN` or `Inf` values.
- Export now succeeds by mapping those values safely for Excel output.

### 2) Tab Font / Readability Fix
- Fixed notebook tab text appearing too small on some systems.
- Tab font and padding are now explicitly styled for consistent readability.

### 3) Network Diagnostics Startup Behavior
- Network diagnostics monitoring no longer starts automatically.
- Monitoring is now opt-in and starts only when the user presses **Start Monitoring**.
- This reduces idle CPU/resource usage when diagnostics are not needed.

### 4) UI Responsiveness Improvements
- Reduced page-transition lag by avoiding heavy redraw operations when tabs are hidden.
- Scanner and simulation updates are throttled when not visible, while preserving active behavior when focused.

## Summary
v1.13 keeps the existing UI layout and workflow, while fixing key issues and improving runtime responsiveness.
