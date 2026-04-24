import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import customtkinter as ctk
from threading import Thread, Event, Lock
import time
import csv
import json
import os
import sys
import glob
import serial.tools.list_ports

try:
    from pymodbus.client.sync import ModbusSerialClient as ModbusClient
except Exception:
    try:
        from pymodbus.client import ModbusSerialClient as ModbusClient
    except Exception:
        ModbusClient = None

from modbus_common import ExceptionInfo, parse_exception_from_response
from modbus_scanner_base import ModbusScannerBase

class RTUSharedConnection:
    # ... (Keep existing code for SharedConnection) ...
    def __init__(self):
        self.lock = Lock()
        self.client = None
        self.connected = False
        self.params = None
        self._active_scans = 0
    # ... (Rest of SharedConnection methods remain the same) ...
    def is_port_in_use(self, port: str) -> bool:
        if not self.connected or not self.params: return False
        return str(self.params.get("port", "")).strip().upper() == str(port).strip().upper()
    
    def matches(self, params: dict) -> bool:
        if not self.connected or not self.params: return False
        keys = ("port", "baudrate", "parity", "bytesize", "stopbits")
        for k in keys:
            if str(self.params.get(k, "")).upper() != str(params.get(k, "")).upper(): return False
        return True

    def connect(self, params):
        if self.connected and self.matches(params): return True, "Connected (Shared)"
        if self._active_scans > 0: return False, "RTU is scanning. Stop all scans first."
        if self.client: 
            try: self.client.close()
            except: pass
        self.client = None; self.connected = False
        try:
            self.client = ModbusClient(method="rtu", **params)
            if self.client.connect():
                self.connected = True; self.params = dict(params)
                return True, "Connected"
            return False, f"Failed to open {params.get('port')}"
        except Exception as e: return False, str(e)

    def disconnect(self):
        if self.client:
            try: self.client.close()
            except: pass
        self.client = None; self.connected = False; self.params = None

    def scan_started(self): self._active_scans += 1
    def scan_stopped(self): self._active_scans = max(0, self._active_scans - 1)


class ModbusRTUScanner(ModbusScannerBase):
    def __init__(self, frame, simulation_instance=None, shared_connection=None):
        self.shared = shared_connection
        # FIX: Create a local lock for when we aren't using shared connection
        self.local_lock = Lock() 
        super().__init__(frame)
        self.client = None
        
        self.point_type_var.set("03: Holding Registers")
        # CTkOptionMenu update
        self.pt_menu.configure(values=["01: Coils", "02: Discrete Inputs", "03: Holding Registers", "04: Input Registers"])

    def _build_connection_settings(self, parent):
        # Create a frame for the top row (Settings) - use CTkFrame if possible, but parent is passed in
        top_row = ctk.CTkFrame(parent, fg_color="transparent")
        top_row.pack(side="top", fill="x")

        self.port_var = tk.StringVar(value="Select Port")
        self.baud_var = tk.StringVar(value="115200")
        self.parity_var = tk.StringVar(value="E")
        self.stop_var = tk.StringVar(value="1")
        self.bytes_var = tk.StringVar(value="8")
        self.timeout_var = tk.StringVar(value="1")
        
        ctk.CTkLabel(top_row, text="Port:").pack(side="left", padx=2)
        # Port menu needs to be updated dynamically, CTkOptionMenu supports this via configure(values=...)
        self.port_menu = ctk.CTkOptionMenu(top_row, variable=self.port_var, values=["Select Port"], width=150)
        self.port_menu.pack(side="left", padx=2)
        # CTkOptionMenu doesn't support bind("<Button-1>"), so we use a "Refresh" button or similar, 
        # OR we just rely on the user clicking it if we could hooking into the click.
        # Actually, for "Auto-Refresh" behavior on click, CTkOptionMenu is harder.
        # Alternative: A small "Refresh" button next to it.
        
        ctk.CTkButton(top_row, text="Refresh", width=80, command=lambda: self._refresh_ports(None)).pack(side="left", padx=2)
        
        ctk.CTkLabel(top_row, text="Baud:").pack(side="left", padx=2)
        ctk.CTkComboBox(top_row, variable=self.baud_var, values=["9600","19200","38400","115200"], width=100).pack(side="left", padx=2)
        
        ctk.CTkLabel(top_row, text="Parity:").pack(side="left", padx=2)
        ctk.CTkOptionMenu(top_row, variable=self.parity_var, values=["N", "E", "O"], width=60).pack(side="left", padx=2)
        
        ctk.CTkLabel(top_row, text="Data:").pack(side="left", padx=2)
        ctk.CTkOptionMenu(top_row, variable=self.bytes_var, values=["7", "8"], width=60).pack(side="left", padx=2)
        
        ctk.CTkLabel(top_row, text="Stop:").pack(side="left", padx=2)
        ctk.CTkOptionMenu(top_row, variable=self.stop_var, values=["1", "1.5", "2"], width=70).pack(side="left", padx=2)
        
        ctk.CTkLabel(top_row, text="T/O:").pack(side="left", padx=2)
        ctk.CTkEntry(top_row, textvariable=self.timeout_var, width=50).pack(side="left", padx=2)

        # Create a frame for the bottom row (Buttons)
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(side="top", fill="x", pady=2)
        
        ctk.CTkButton(btn_row, text="Load Config", width=100, command=self.load_config_json).pack(side="left", padx=2)
        ctk.CTkButton(btn_row, text="Save Config", width=100, command=self.save_config_json).pack(side="left", padx=2)

    def save_config_json(self):
        params = self.export_ui_params()
        f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Config", "*.json")])
        if not f: return
        try:
            with open(f, "w") as fp:
                json.dump(params, fp, indent=4)
            messagebox.showinfo("Save Config", "Configuration saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")

    def load_config_json(self):
        f = filedialog.askopenfilename(filetypes=[("JSON Config", "*.json")])
        if not f: return
        try:
            with open(f, "r") as fp:
                params = json.load(fp)
            self.import_ui_params(params)
            messagebox.showinfo("Load Config", "Configuration loaded successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load config: {e}")

    def _refresh_ports(self, _):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        is_wsl = False
        if os.getenv("WSL_DISTRO_NAME"):
            is_wsl = True
        elif hasattr(os, "uname"):
            try:
                is_wsl = "microsoft" in os.uname().release.lower()
            except Exception:
                is_wsl = False
        if is_wsl:
            ports = [p for p in ports if not p.startswith("/dev/ttyS")]
        if not ports and sys.platform.startswith("linux"):
            manual_ports = []
            if is_wsl:
                patterns = ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/serial/by-id/*")
            else:
                patterns = ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyS*", "/dev/ttyAMA*", "/dev/ttySC*", "/dev/serial/by-id/*")
            for pattern in patterns:
                manual_ports.extend(glob.glob(pattern))
            manual_ports = sorted(set(manual_ports))
            ports = [p for p in manual_ports if os.access(p, os.R_OK | os.W_OK)]
        if not ports:
            if os.name == "nt":
                ports = ["No ports"]
            else:
                if is_wsl:
                    ports = ["No ports detected in WSL"]
                else:
                    ports = ["No ports"]
        # Update CTkOptionMenu values
        self.port_menu.configure(values=ports)
        if self.port_var.get() not in ports:
            self.port_var.set(ports[0])

    def connect_modbus(self):
        try:
            params = {
                "port": self.port_var.get(), "baudrate": int(self.baud_var.get()),
                "parity": self.parity_var.get(), "stopbits": float(self.stop_var.get()),
                "bytesize": int(self.bytes_var.get()), "timeout": float(self.timeout_var.get())
            }
        except Exception:
            messagebox.showerror("Error", "Invalid Serial Settings")
            return
        
        if self.shared:
            ok, msg = self.shared.connect(params)
            if ok:
                self.client = self.shared.client; self.connected = True
                self.connect_btn.configure(text="Connected", state="disabled", fg_color="#1b5e20", text_color="white")
            else: messagebox.showerror("Connection Error", msg)
        else:
            try:
                self.client = ModbusClient(method="rtu", **params)
                if self.client.connect():
                    self.connected = True
                    self.connect_btn.configure(text="Connected", state="disabled", fg_color="#1b5e20", text_color="white")
                else: messagebox.showerror("Error", "Failed to connect")
            except Exception as e: messagebox.showerror("Error", str(e))

    def disconnect_modbus(self):
        self.stop_scan()
        if self.shared: self.shared.disconnect(); self.client = None
        elif self.client: self.client.close(); self.client = None
        self.connected = False
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
        
        self._raw_range = (start, end)
        
        # FIX: Use correct lock
        lock = self.shared.lock if self.shared else self.local_lock
        
        offset = 1 if self.one_based.get() else 0
        pt_label = self.point_type_var.get()[:2]
        pos = max(0, start - offset); zend = max(0, end - offset)
        
        while pos <= zend and self.scanning and gen == self.generation:
            count = min(batch, zend - pos + 1)
            vals = None; err = None
            try:
                with lock:
                    if pt_label == "03": rsp = self.client.read_holding_registers(pos, count, unit=unit)
                    elif pt_label == "04": rsp = self.client.read_input_registers(pos, count, unit=unit)
                    elif pt_label == "01": rsp = self.client.read_coils(pos, count, unit=unit)
                    elif pt_label == "02": rsp = self.client.read_discrete_inputs(pos, count, unit=unit)
                    else: rsp = None
                if rsp and not rsp.isError():
                    vals = getattr(rsp, "registers", getattr(rsp, "bits", []))
                else: err = parse_exception_from_response(rsp, "Error")
            except Exception as e: err = ExceptionInfo(None, None, str(e))
                
            if vals:
                for i, v in enumerate(vals[:count]):
                    addr = pos + i + offset
                    self._raw_values[addr] = int(v)
                    self._error_by_addr.pop(addr, None)
            elif err:
                for i in range(count):
                    addr = pos + i + offset
                    if addr >= start: self._error_by_addr[addr] = err
            pos += count

    def _perform_write(self, wire_addr, val, unit):
        # FIX: Use correct lock
        lock = self.shared.lock if self.shared else self.local_lock
        try:
            with lock:
                if isinstance(val, list):
                    if len(val) == 1: rsp = self.client.write_register(wire_addr, val[0], unit=unit)
                    else: rsp = self.client.write_registers(wire_addr, val, unit=unit)
                else:
                    rsp = self.client.write_register(wire_addr, int(val), unit=unit)
            if rsp.isError(): return False, str(rsp)
            return True, "OK"
        except Exception as e: return False, str(e)

    def export_ui_params(self):
        return {
            "port": self.port_var.get(), "baudrate": self.baud_var.get(),
            "parity": self.parity_var.get(), "stopbits": self.stop_var.get(),
            "bytesize": self.bytes_var.get(), "timeout": self.timeout_var.get(),
            "start_addr": self.start_var.get(), "end_addr": self.end_var.get(),
            "unit": self.unit_var.get(), "poll": self.poll_var.get(), "batch": self.batch_var.get()
        }

    def import_ui_params(self, p):
        if "port" in p: self.port_var.set(p["port"])
        if "baudrate" in p: self.baud_var.set(p["baudrate"])
        if "parity" in p: self.parity_var.set(p["parity"])
        if "stopbits" in p: self.stop_var.set(p["stopbits"])
        if "bytesize" in p: self.bytes_var.set(p["bytesize"])
        if "timeout" in p: self.timeout_var.set(p["timeout"])
        if "start_addr" in p: self.start_var.set(p["start_addr"])
        if "end_addr" in p: self.end_var.set(p["end_addr"])
        if "unit" in p: self.unit_var.set(p["unit"])
        if "poll" in p: self.poll_var.set(p["poll"])
        if "batch" in p: self.batch_var.set(p["batch"])
        
    def set_connection_params(self, params):
        self.import_ui_params(params)
