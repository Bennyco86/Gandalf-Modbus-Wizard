# RTU over TCP Testing Guide (Local)

This guide shows how to test **RTU over TCP (RTU Tunnel / Transparent Mode)** in Gandalf using:
- the built-in **Modbus TCP Simulator** (MBAP), and
- the included **RTU-over-TCP proxy** (bridges RTU⇄TCP)

The goal is to prove that **RTU-over-TCP returns the same values** as a normal Modbus TCP scan.

---

## ✅ Prerequisites

- **Gandalf Modbus Wizard v1.12+** installed (or running from source)
- **rtu_over_tcp_proxy.exe** (included in the GitHub release assets)
- *(Optional)* Python 3.8+ if running the proxy from source instead of the .exe

---

## 1) Start the Modbus TCP Simulator (MBAP)

1. Open **Gandalf Modbus Wizard**
2. Go to **Modbus Simulation**
3. Start the simulator with:
   - **Host:** `127.0.0.1`
   - **Port:** `1502`

✅ Leave it running.

---

## 2) Start the RTU-over-TCP Proxy

The proxy listens for **RTU frames over TCP** and forwards them to the simulator as **Modbus TCP (MBAP)**.

### Quick start (recommended)
Double-click:
- `rtu_over_tcp_proxy.exe`

By default it will:
- **Listen:** `127.0.0.1:15020`
- **Forward to:** `127.0.0.1:1502`

### Start from terminal (optional: verbose / custom ports)
Open a terminal in the folder containing the exe and run:

```bash
rtu_over_tcp_proxy.exe --verbose

