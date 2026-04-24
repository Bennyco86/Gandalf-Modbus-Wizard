# Gandalf Modbus Wizard v1.12 Release Notes

Excited to share Gandalf Modbus Wizard is now officially supported on Linux.

## v1.12 — RTU over TCP (RTU Tunnel) + TCP Scanner Update

This release adds RTU over TCP (RTU Tunnel / Transparent Mode) support — ideal for users running Modbus RTU devices through gateways (e.g. Waveshare "transparent transmit" setups).

### Highlights

- RTU over TCP (RTU Tunnel) added to the TCP Scanner
  Full scan + write support using RTU framing carried over a TCP socket (no MBAP).

- Transport / Framing selector in the TCP Scanner UI
  Quickly switch between:
  - Modbus TCP (MBAP)
  - RTU over TCP (RTU Tunnel)

- Local testing made easy
  Includes an RTU-over-TCP proxy helper so you can test against the built-in simulator without any extra hardware.

### Testing / How to Verify

- RTU_OVER_TCP_TESTING.md included with step-by-step instructions
- rtu_over_tcp_proxy.exe ships with the release for quick local testing
  (Proxy bridges RTU-over-TCP ? Modbus TCP simulator)

### Downloads

- Gandalf_Wizard_Setup_v1.12.exe
- rtu_over_tcp_proxy.exe
- gandalf-modbus-wizard_1.12_amd64.deb