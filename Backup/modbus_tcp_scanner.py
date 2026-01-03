import tkinter as tk
from tkinter import messagebox
import os
import subprocess
from pymodbus.client.sync import ModbusTcpClient
from modbus_common import ExceptionInfo, parse_exception_from_response
from modbus_scanner_base import ModbusScannerBase

class ModbusTCPScanner(ModbusScannerBase):
    def __init__(self, frame, simulation_instance=None):
        super().__init__(frame)
        self.client = None

        # Populate Option Menu specific to TCP
        self.point_type_var.set("03: Holding Registers")
        menu = self.pt_menu["menu"]
        menu.delete(0, "end")
        for l in ["01: Coil Status", "02: Input Status", "03: Holding Registers", "04: Input Registers"]:
            menu.add_command(label=l, command=lambda v=l: self.point_type_var.set(v))

    def _build_connection_settings(self, parent):
        tk.Label(parent, text="Host:").grid(row=0, column=0)
        self.host_entry = tk.Entry(parent, width=15)
        self.host_entry.grid(row=0, column=1)
        self.host_entry.insert(0, "127.0.0.1")
        
        tk.Label(parent, text="Port:").grid(row=0, column=2)
        self.port_entry = tk.Entry(parent, width=6)
        self.port_entry.grid(row=0, column=3)
        self.port_entry.insert(0, "502")

        # Ping Button (Restored)
        tk.Button(parent, text="Ping", command=self.ping_host).grid(row=0, column=4, padx=5)

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
        subprocess.Popen(["ping", "-c", "4", host])

    def connect_modbus(self):
        host = self.host_entry.get().strip()
        try: port = int(self.port_entry.get())
        except: return
        
        self.client = ModbusTcpClient(host=host, port=port)
        if self.client.connect():
            self.connected = True
            self.connect_btn.config(text="Connected", state="disabled", bg="#4caf50")
        else:
            messagebox.showerror("Error", "Connection failed")

    def disconnect_modbus(self):
        self.stop_scan()
        if self.client: self.client.close()
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
            rsp = self.client.write_register(wire_addr, val, unit=unit)
            if rsp.isError(): return False, str(rsp)
            return True, "OK"
        except Exception as e: return False, str(e)