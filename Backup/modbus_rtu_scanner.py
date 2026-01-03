import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from threading import Thread, Event, Lock
import time
import csv
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
    """Helper to share one Serial port among multiple tabs."""
    def __init__(self):
        self.lock = Lock()
        self.client = None
        self.connected = False
        self.params = None
        self._active_scans = 0

    def is_port_in_use(self, port: str) -> bool:
        if not self.connected or not self.params:
            return False
        current = str(self.params.get("port", "")).strip().upper()
        target = str(port).strip().upper()
        return current == target

    def matches(self, params: dict) -> bool:
        if not self.connected or not self.params:
            return False
        keys = ("port", "baudrate", "parity", "bytesize", "stopbits")
        for k in keys:
            v1 = str(self.params.get(k, "")).upper()
            v2 = str(params.get(k, "")).upper()
            if v1 != v2:
                return False
        return True

    def connect(self, params):
        if self.connected and self.matches(params):
            return True, "Connected (Shared)"

        if self._active_scans > 0:
            return False, "RTU is scanning. Stop all scans before changing port settings."
        
        if self.client:
            try: self.client.close()
            except: pass
        self.client = None
        self.connected = False
        
        try:
            self.client = ModbusClient(method="rtu", **params)
            if self.client.connect():
                self.connected = True
                self.params = dict(params)
                return True, "Connected"
            return False, f"Failed to open {params.get('port')}"
        except Exception as e:
            return False, str(e)

    def disconnect(self):
        if self.client:
            try: self.client.close()
            except: pass
        self.client = None
        self.connected = False
        self.params = None

    def scan_started(self):
        self._active_scans += 1

    def scan_stopped(self):
        self._active_scans = max(0, self._active_scans - 1)

class ModbusRTUScanner(ModbusScannerBase):
    def __init__(self, frame, simulation_instance=None, shared_connection=None):
        self.shared = shared_connection
        super().__init__(frame)
        self.client = None
        
        self.point_type_var.set("03: Holding Registers")
        menu = self.pt_menu["menu"]
        menu.delete(0, "end")
        for l in ["01: Coils", "02: Discrete Inputs", "03: Holding Registers", "04: Input Registers"]:
            menu.add_command(label=l, command=lambda v=l: self.point_type_var.set(v))

    def _build_connection_settings(self, parent):
        self.port_var = tk.StringVar(value="Select Port")
        self.baud_var = tk.StringVar(value="115200")
        self.parity_var = tk.StringVar(value="E")
        self.stop_var = tk.StringVar(value="1")
        self.bytes_var = tk.StringVar(value="8")
        self.timeout_var = tk.StringVar(value="1") # UPDATED: Default Timeout = 1
        
        tk.Label(parent, text="Port:").pack(side="left")
        self.port_menu = tk.OptionMenu(parent, self.port_var, "")
        self.port_menu.pack(side="left")
        self.port_menu.bind("<Button-1>", self._refresh_ports)
        
        tk.Label(parent, text="Baud:").pack(side="left")
        ttk.Combobox(parent, textvariable=self.baud_var, values=["9600","19200","38400","115200"], width=7).pack(side="left")
        
        tk.Label(parent, text="Parity:").pack(side="left")
        tk.OptionMenu(parent, self.parity_var, "N", "E", "O").pack(side="left")
        
        tk.Label(parent, text="Data:").pack(side="left")
        tk.OptionMenu(parent, self.bytes_var, "7", "8").pack(side="left")
        
        tk.Label(parent, text="Stop:").pack(side="left")
        tk.OptionMenu(parent, self.stop_var, "1", "1.5", "2").pack(side="left")

        tk.Label(parent, text="T/O:").pack(side="left")
        tk.Entry(parent, textvariable=self.timeout_var, width=4).pack(side="left")

    def _refresh_ports(self, _):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        menu = self.port_menu["menu"]
        menu.delete(0, "end")
        if not ports:
            menu.add_command(label="No ports", command=lambda: self.port_var.set("Select Port"))
        for p in ports: 
            menu.add_command(label=p, command=lambda v=p: self.port_var.set(v))

    def connect_modbus(self):
        try:
            params = {
                "port": self.port_var.get(),
                "baudrate": int(self.baud_var.get()),
                "parity": self.parity_var.get(),
                "stopbits": float(self.stop_var.get()),
                "bytesize": int(self.bytes_var.get()),
                "timeout": float(self.timeout_var.get())
            }
        except Exception:
            messagebox.showerror("Error", "Invalid Serial Settings")
            return
        
        if self.shared:
            ok, msg = self.shared.connect(params)
            if ok:
                self.client = self.shared.client
                self.connected = True
                self.connect_btn.config(text="Connected", state="disabled", bg="#4caf50")
            else:
                messagebox.showerror("Connection Error", msg)
        else:
            try:
                self.client = ModbusClient(method="rtu", **params)
                if self.client.connect():
                    self.connected = True
                    self.connect_btn.config(text="Connected", state="disabled", bg="#4caf50")
                else:
                    messagebox.showerror("Error", "Failed to connect")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def disconnect_modbus(self):
        self.stop_scan()
        if self.shared: 
            self.shared.disconnect()
            self.client = None
        elif self.client: 
            self.client.close()
            self.client = None
            
        self.connected = False
        self.connect_btn.config(text="Connect", state="normal", bg="#2e7d32")

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
        lock = self.shared.lock if self.shared else Lock()
        
        offset = 1 if self.one_based.get() else 0
        pt_label = self.point_type_var.get()[:2]
        
        pos = max(0, start - offset)
        zend = max(0, end - offset)
        
        while pos <= zend and self.scanning and gen == self.generation:
            count = min(batch, zend - pos + 1)
            vals = None
            err = None
            
            try:
                with lock:
                    if pt_label == "03": rsp = self.client.read_holding_registers(pos, count, unit=unit)
                    elif pt_label == "04": rsp = self.client.read_input_registers(pos, count, unit=unit)
                    elif pt_label == "01": rsp = self.client.read_coils(pos, count, unit=unit)
                    elif pt_label == "02": rsp = self.client.read_discrete_inputs(pos, count, unit=unit)
                    else: rsp = None

                if rsp and not rsp.isError():
                    vals = getattr(rsp, "registers", getattr(rsp, "bits", []))
                else:
                    err = parse_exception_from_response(rsp, "Error")
            except Exception as e:
                err = ExceptionInfo(None, None, str(e))
                
            if vals:
                for i, v in enumerate(vals[:count]):
                    addr = pos + i + offset
                    self._raw_values[addr] = int(v)
                    self._error_by_addr.pop(addr, None)
            elif err:
                for i in range(count):
                    addr = pos + i + offset
                    if addr >= start:
                        self._error_by_addr[addr] = err
                        
            pos += count

    def _perform_write(self, wire_addr, val, unit):
        lock = self.shared.lock if self.shared else Lock()
        try:
            with lock:
                rsp = self.client.write_register(wire_addr, val, unit=unit)
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