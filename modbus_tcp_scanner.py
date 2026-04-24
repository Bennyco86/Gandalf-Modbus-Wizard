import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import os
import subprocess
import socket
import struct
import sys
import platform
from threading import Lock

try:
    from pymodbus.client.sync import ModbusTcpClient
except Exception:
    try:
        from pymodbus.client import ModbusTcpClient
    except Exception:
        ModbusTcpClient = None

try:
    from pymodbus.framer.rtu_framer import ModbusRtuFramer
except Exception:
    ModbusRtuFramer = None

from modbus_common import ExceptionInfo, parse_exception_from_response
from modbus_scanner_base import ModbusScannerBase

TRANSPORT_MBAP = "Modbus TCP (MBAP)"
TRANSPORT_RTU = "RTU over TCP (RTU tunnel)"


def _is_wsl() -> bool:
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in platform.release().lower()
    except Exception:
        return False


class RtuOverTcpResponse:
    def __init__(self, registers=None, bits=None, error=False, exception_code=None, message=""):
        self.registers = registers or []
        self.bits = bits or []
        self._error = bool(error)
        self.exception_code = exception_code
        self._message = message

    def isError(self):
        return self._error

    def __str__(self):
        if self._error:
            if self.exception_code is not None:
                return f"Modbus exception {self.exception_code}"
            if self._message:
                return self._message
            return "RTU error"
        return "OK"


class RTUOverTCPClient:
    def __init__(self, host, port, timeout=3.0):
        self.host = host
        self.port = port
        self.timeout = float(timeout)
        self.socket = None
        self._lock = Lock()

    def connect(self):
        try:
            self.socket = socket.create_connection((self.host, self.port), timeout=self.timeout)
            self.socket.settimeout(self.timeout)
            return True
        except Exception:
            self.socket = None
            return False

    def close(self):
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        self.socket = None

    def _crc16(self, data):
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc & 0xFFFF

    def _validate_crc(self, frame):
        if len(frame) < 4:
            return False
        crc_calc = self._crc16(frame[:-2])
        crc_recv = frame[-2] | (frame[-1] << 8)
        return crc_calc == crc_recv

    def _recv_exact(self, n):
        data = bytearray()
        while len(data) < n:
            chunk = self.socket.recv(n - len(data))
            if not chunk:
                raise IOError("Connection closed")
            data.extend(chunk)
        return bytes(data)

    def _recv_response(self, expected_bits=None, expected_regs=None):
        header = self._recv_exact(2)
        func = header[1]

        if func & 0x80:
            rest = self._recv_exact(3)
            frame = header + rest
            if not self._validate_crc(frame):
                return RtuOverTcpResponse(error=True, message="CRC check failed")
            return RtuOverTcpResponse(error=True, exception_code=rest[0], message="Modbus exception")

        if func in (1, 2, 3, 4):
            bc = self._recv_exact(1)
            byte_count = bc[0]
            data_crc = self._recv_exact(byte_count + 2)
            frame = header + bc + data_crc
        elif func in (5, 6, 15, 16):
            rest = self._recv_exact(6)
            frame = header + rest
        else:
            bc = self._recv_exact(1)
            byte_count = bc[0]
            data_crc = self._recv_exact(byte_count + 2)
            frame = header + bc + data_crc

        if not self._validate_crc(frame):
            return RtuOverTcpResponse(error=True, message="CRC check failed")

        return self._parse_response(frame, expected_bits, expected_regs)

    def _parse_response(self, frame, expected_bits=None, expected_regs=None):
        func = frame[1]
        if func & 0x80:
            return RtuOverTcpResponse(error=True, exception_code=frame[2], message="Modbus exception")

        if func in (1, 2):
            if len(frame) < 5:
                return RtuOverTcpResponse(error=True, message="Short response")
            byte_count = frame[2]
            data = frame[3:3 + byte_count]
            bit_count = expected_bits if expected_bits is not None else byte_count * 8
            bits = []
            for i in range(bit_count):
                b = data[i // 8]
                bits.append((b >> (i % 8)) & 1)
            return RtuOverTcpResponse(bits=bits)

        if func in (3, 4):
            if len(frame) < 5:
                return RtuOverTcpResponse(error=True, message="Short response")
            byte_count = frame[2]
            data = frame[3:3 + byte_count]
            if byte_count % 2 != 0:
                return RtuOverTcpResponse(error=True, message="Odd byte count")
            regs = []
            for i in range(0, len(data), 2):
                regs.append(int.from_bytes(data[i:i + 2], byteorder="big"))
            if expected_regs is not None:
                regs = regs[:expected_regs]
            return RtuOverTcpResponse(registers=regs)

        if func in (5, 6, 15, 16):
            return RtuOverTcpResponse()

        return RtuOverTcpResponse()

    def _send_request(self, unit, func, payload, expected_bits=None, expected_regs=None):
        if not self.socket:
            raise IOError("Not connected")
        frame = bytes([unit, func]) + payload
        crc = self._crc16(frame)
        frame += struct.pack("<H", crc)
        with self._lock:
            self.socket.sendall(frame)
            return self._recv_response(expected_bits=expected_bits, expected_regs=expected_regs)

    def read_holding_registers(self, address, count, unit=1):
        payload = struct.pack(">HH", address, count)
        return self._send_request(unit, 3, payload, expected_regs=count)

    def read_input_registers(self, address, count, unit=1):
        payload = struct.pack(">HH", address, count)
        return self._send_request(unit, 4, payload, expected_regs=count)

    def read_coils(self, address, count, unit=1):
        payload = struct.pack(">HH", address, count)
        return self._send_request(unit, 1, payload, expected_bits=count)

    def read_discrete_inputs(self, address, count, unit=1):
        payload = struct.pack(">HH", address, count)
        return self._send_request(unit, 2, payload, expected_bits=count)

    def write_register(self, address, value, unit=1):
        payload = struct.pack(">HH", address, int(value) & 0xFFFF)
        return self._send_request(unit, 6, payload)

    def write_registers(self, address, values, unit=1):
        vals = [int(v) & 0xFFFF for v in values]
        byte_count = len(vals) * 2
        payload = struct.pack(">HHB", address, len(vals), byte_count)
        data = bytearray()
        for v in vals:
            data.extend(struct.pack(">H", v))
        return self._send_request(unit, 16, payload + bytes(data))


class ModbusTCPScanner(ModbusScannerBase):
    def __init__(self, frame, simulation_instance=None):
        self.client = None
        self.transport_var = tk.StringVar(value=TRANSPORT_MBAP)
        super().__init__(frame)

        # Populate Option Menu specific to TCP
        self.point_type_var.set("03: Holding Registers")
        # CTkOptionMenu uses configure(values=...)
        self.pt_menu.configure(values=["01: Coil Status", "02: Input Status", "03: Holding Registers", "04: Input Registers"])

    def _build_connection_settings(self, parent):
        # 'parent' is likely a CTkFrame from ModbusScannerBase._build_base_ui's self.conn_frame
        ctk.CTkLabel(parent, text="Host:").grid(row=0, column=0, padx=2)
        self.host_entry = ctk.CTkEntry(parent, width=150)
        self.host_entry.grid(row=0, column=1, padx=2)
        self.host_entry.insert(0, "127.0.0.1")
        
        ctk.CTkLabel(parent, text="Port:").grid(row=0, column=2, padx=2)
        self.port_entry = ctk.CTkEntry(parent, width=60)
        self.port_entry.grid(row=0, column=3, padx=2)
        default_port = "1502" if sys.platform.startswith("linux") else "502"
        self.port_entry.insert(0, default_port)

        # Ping Button (Restored)
        ctk.CTkButton(parent, text="Ping", width=60, command=self.ping_host).grid(row=0, column=4, padx=5)

        ctk.CTkLabel(parent, text="Transport / Framing:").grid(row=1, column=0, padx=2, pady=(4, 0), sticky="w")
        self.transport_menu = ctk.CTkOptionMenu(
            parent,
            variable=self.transport_var,
            values=[TRANSPORT_MBAP, TRANSPORT_RTU],
            command=self._on_transport_changed,
            width=200
        )
        self.transport_menu.grid(row=1, column=1, columnspan=3, padx=2, pady=(4, 0), sticky="w")

    def _on_transport_changed(self, _=None):
        if self.connected:
            messagebox.showinfo("Transport", "Transport changed. Please reconnect.")
            self.disconnect_modbus()

    def _build_client(self, host, port):
        transport = self.transport_var.get()
        if transport == TRANSPORT_RTU:
            if ModbusTcpClient and ModbusRtuFramer:
                try:
                    return ModbusTcpClient(host=host, port=port, framer=ModbusRtuFramer)
                except TypeError:
                    pass
            return RTUOverTCPClient(host=host, port=port, timeout=3.0)
        if ModbusTcpClient:
            return ModbusTcpClient(host=host, port=port)
        return None

    def ping_host(self):
        try: 
            host = self.host_entry.get().strip()
        except: 
            host = ""
            
        if not host:
            messagebox.showwarning("Ping", "Please enter a Host / IP address first.")
            return

        if os.name == "nt":
            try:
                # Opens a new command prompt window to show the ping
                subprocess.Popen(["cmd.exe", "/k", f"ping {host}"], creationflags=subprocess.CREATE_NEW_CONSOLE)
            except Exception as e:
                messagebox.showerror("Ping", f"Failed: {e}")
            return
        
        # Fallback for Linux/Mac (run in background)
        # subprocess.Popen(["ping", "-c", "4", host])
        if sys.platform.startswith("linux"):
            if _is_wsl():
                ping_cmd = f"ping -c 4 {host}; echo; read -n 1 -s -r -p 'Press any key to close...'"
                distro = os.environ.get("WSL_DISTRO_NAME")
                wsl_cmd = ["wsl.exe"]
                if distro:
                    wsl_cmd += ["-d", distro]
                wsl_cmd += ["-e", "bash", "-lc", ping_cmd]
                try:
                    subprocess.Popen(["cmd.exe", "/c", "start", "cmd.exe", "/k"] + wsl_cmd)
                    return
                except Exception as e:
                    messagebox.showerror("Ping", f"Failed to open terminal: {e}")
                    return
            cmd = f"ping -c 4 {host}; echo; echo Press Enter to close...; read"
            terminals = ["gnome-terminal", "x-terminal-emulator", "konsole", "xfce4-terminal", "lxterminal"]
            started = False
            for term in terminals:
                try:
                    # gnome-terminal and others often take -- bash -c "..." or -e "..."
                    # We try common args: -- bash -c
                    if term == "gnome-terminal":
                        subprocess.Popen([term, "--", "bash", "-c", cmd])
                    else:
                        subprocess.Popen([term, "-e", f"bash -c '{cmd}'"])
                    started = True
                    break
                except FileNotFoundError:
                    continue
            if not started:
                # If no GUI terminal found, try just running it (might be in terminal already if started from CLI)
                subprocess.Popen(["ping", "-c", "4", host])
        else:
            # Mac or other
            subprocess.Popen(["ping", "-c", "4", host])

    def connect_modbus(self):
        host = self.host_entry.get().strip()
        try: 
            port = int(self.port_entry.get())
        except: 
            return

        self.client = self._build_client(host, port)
        if not self.client:
            messagebox.showerror("Error", "Modbus TCP client is unavailable.")
            return

        try:
            if self.client.connect():
                self.connected = True
                # FIX: Use Dark Green for high contrast
                self.connect_btn.configure(text="Connected", state="disabled", fg_color="#1b5e20", text_color="white")
            else:
                messagebox.showerror("Error", "Connection failed")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def disconnect_modbus(self):
        self.stop_scan()
        if self.client: 
            try:
                self.client.close()
            except Exception:
                pass
        self.connected = False
        # FIX: Use configure for CTkButton, map bg -> fg_color
        self.connect_btn.configure(text="Connect", state="normal", fg_color="#2e7d32", text_color="white")

    def _scan_once(self, gen):
        if not self.client: return
        try:
            start = int(self.start_var.get())
            end = int(self.end_var.get())
            unit = int(self.unit_var.get())
            batch = int(self.batch_var.get())
        except: return
        if end < start: start, end = end, start

        pt_label = self.point_type_var.get()[:2]
        offset = 1 if self.one_based.get() else 0
        raw = {}
        err = {}

        pos = max(0, start - offset)
        zend = max(0, end - offset)

        while pos <= zend and self.scanning and gen == self.generation:
            count = min(batch, zend - pos + 1)
            try:
                if pt_label == "03": rsp = self.client.read_holding_registers(pos, count, unit=unit)
                elif pt_label == "04": rsp = self.client.read_input_registers(pos, count, unit=unit)
                elif pt_label == "01": rsp = self.client.read_coils(pos, count, unit=unit)
                elif pt_label == "02": rsp = self.client.read_discrete_inputs(pos, count, unit=unit)
                else: rsp = None

                if rsp and not rsp.isError():
                    vals = getattr(rsp, "registers", getattr(rsp, "bits", []))
                    for i, v in enumerate(vals[:count]):
                        raw[pos + i + offset] = int(v)
                else:
                    exc = parse_exception_from_response(rsp, "Error")
                    for i in range(count):
                        if (pos+i+offset) >= start: err[pos + i + offset] = exc
            except Exception as e:
                ex = ExceptionInfo(None, None, str(e))
                for i in range(count): err[pos + i + offset] = ex
            
            pos += count

        # Atomic update
        self._raw_values = raw
        self._raw_range = (start, end)
        self._error_by_addr = err

    def _perform_write(self, wire_addr, val, unit):
        try:
            # 'val' is now a LIST of integers (from encode_value_to_words)
            if isinstance(val, list):
                if len(val) == 1:
                    rsp = self.client.write_register(wire_addr, val[0], unit=unit)
                else:
                    rsp = self.client.write_registers(wire_addr, val, unit=unit)
            else:
                # Fallback for old calls (shouldn't happen)
                rsp = self.client.write_register(wire_addr, int(val), unit=unit)
                
            if rsp.isError(): return False, str(rsp)
            return True, "OK"
        except Exception as e: return False, str(e)
