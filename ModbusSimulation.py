import os
import re
import time
import math
import random
import struct
import subprocess
import tkinter as tk
import sys
import logging
from tkinter import messagebox, simpledialog
import customtkinter as ctk

from threading import Thread, Lock  # <--- IMPORT LOCK
from pymodbus.server.sync import ModbusTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)

# --- NEW IMPORTS FOR STRING ENCODING ---
from modbus_common import encode_value_to_words, decode_register_words, SwapMode

MODBUS_FUNCTION_CODES = {
    "01: Coil Status": "01",
    "02: Input Status": "02",
    "03: Holding Registers": "03",
    "04: Input Registers": "04",
}

VALUE_TYPES = [
    "Integer",
    "Float",
    "Swapped Float",
    "Double",
    "Swapped Double",
    "Auto 103-Reg Demo",
]

class RangeValidatedDataBlock(ModbusSequentialDataBlock):
    """
    A custom DataBlock that validates ranges and uses a shared Lock 
    to prevent the Server thread from crashing the Simulation thread.
    """
    def __init__(self, address, values, is_allowed_fn, lock, on_write_cb=None):
        super().__init__(address, values)
        self._is_allowed_fn = is_allowed_fn
        self._lock = lock  # <--- SHARED LOCK
        self._on_write_cb = on_write_cb

    def validate(self, address, count=1):
        try:
            for a in range(int(address), int(address) + int(count)):
                if not self._is_allowed_fn(a):
                    return False
        except Exception:
            return False
        return super().validate(address, count)

    def setValues(self, address, values):
        """Intercept writes from external clients safely."""
        # CRITICAL FIX: Lock the update so we don't collide with the simulation loop
        with self._lock:
            super().setValues(address, values)
            
            # Notify callback while locked to ensure state consistency
            if self._on_write_cb:
                try:
                    self._on_write_cb(address, values)
                except Exception as e:
                    logging.error(f"Write Callback Error: {e}")

class ModbusSimulation:
    def __init__(self, frame):
        self.frame = frame
        self.simulating = False
        self.server = None
        self.server_thread = None
        self.lock = Lock()  # <--- CREATE THE LOCK
        
        self.start_address = 0
        # UPDATED: Extended default range to 125 to fit the Easter Egg string
        self.end_address = 125 
        self.allowed_ranges = []
        self.written_values = {} 
        self.manual_mode = False
        self.block = None
        self._ctx_menu = None
        self._build_ui()

    def _build_ui(self):
        top = ctk.CTkFrame(self.frame, fg_color="transparent")
        top.grid(row=0, column=0, sticky="nw")
        for r in range(9): top.grid_rowconfigure(r, pad=1)

        c0 = 0; c1 = 1; c2 = 2
        ctk.CTkLabel(top, text="Host:").grid(row=0, column=c0, sticky="w")
        self.host_entry = ctk.CTkEntry(top, width=160)
        self.host_entry.grid(row=0, column=c1, sticky="w", columnspan=2)
        self.host_entry.insert(0, "localhost")

        ctk.CTkLabel(top, text="Port:").grid(row=1, column=c0, sticky="w")
        self.port_entry = ctk.CTkEntry(top, width=80)
        self.port_entry.grid(row=1, column=c1, sticky="w")
        default_port = "1502" if sys.platform.startswith("linux") else "502"
        self.port_entry.insert(0, default_port)

        ctk.CTkLabel(top, text="Function Code:").grid(row=2, column=c0, sticky="w")
        self.function_code_var = ctk.StringVar(value="03: Holding Registers")
        # Trace is still supported on StringVar
        self.function_code_var.trace_add("write", self._restart_if_running) 
        ctk.CTkOptionMenu(top, variable=self.function_code_var, values=list(MODBUS_FUNCTION_CODES.keys())).grid(row=2, column=c1, columnspan=2, sticky="w")

        ctk.CTkLabel(top, text="Value Type:").grid(row=3, column=c0, sticky="w")
        self.value_type_var = ctk.StringVar(value="Auto 103-Reg Demo")
        self.value_type_var.trace_add("write", self._restart_if_running)
        ctk.CTkOptionMenu(top, variable=self.value_type_var, values=VALUE_TYPES).grid(row=3, column=c1, columnspan=2, sticky="w")

        ctk.CTkLabel(top, text="Address Start:").grid(row=4, column=c0, sticky="w")
        self.address_start_entry = ctk.CTkEntry(top, width=80)
        self.address_start_entry.grid(row=4, column=c1, sticky="w")
        self.address_start_entry.insert(0, "0")

        ctk.CTkLabel(top, text="Address End:").grid(row=5, column=c0, sticky="w")
        self.address_end_entry = ctk.CTkEntry(top, width=80)
        self.address_end_entry.grid(row=5, column=c1, sticky="w")
        # UPDATED: Default to 125 to show the Easter Egg registers
        self.address_end_entry.insert(0, "125")

        ctk.CTkLabel(top, text="Address Ranges (optional):").grid(row=6, column=c0, sticky="w")
        self.address_ranges_entry = ctk.CTkEntry(top, width=280)
        self.address_ranges_entry.grid(row=6, column=c1, sticky="w", columnspan=2)
        self.address_ranges_entry.insert(0, "")

        ctk.CTkLabel(top, text="Device ID:").grid(row=7, column=c0, sticky="w")
        self.device_id_entry = ctk.CTkEntry(top, width=80)
        self.device_id_entry.grid(row=7, column=c1, sticky="w")
        self.device_id_entry.insert(0, "1")

        ctk.CTkButton(top, text="Start Simulation", fg_color="green", text_color="white", command=self.start_simulation).grid(row=8, column=c0, sticky="w", pady=5, padx=2)
        ctk.CTkButton(top, text="Stop Simulation", fg_color="red", hover_color="#8B0000", text_color="white", command=self.stop_simulation).grid(row=8, column=c1, sticky="w", pady=5, padx=2)
        ctk.CTkButton(top, text="Open IPv4 Settings (ncpa.cpl)", command=self.open_ipv4_settings).grid(row=8, column=c2, sticky="w", pady=5, padx=2)

        holder = ctk.CTkFrame(self.frame, corner_radius=0)
        holder.grid(row=1, column=0, sticky="nsew")
        holder.grid_rowconfigure(0, weight=1)
        holder.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self.register_listbox = tk.Listbox(holder, height=26, width=82)
        self.register_listbox.grid(row=0, column=0, sticky="nsew")
        sb = tk.Scrollbar(holder, orient="vertical", command=self.register_listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.register_listbox.configure(yscrollcommand=sb.set)

        self.register_listbox.bind("<Double-Button-1>", self._on_list_double_click)
        self.register_listbox.bind("<Return>", self._on_list_activate)
        self.register_listbox.bind("<KP_Enter>", self._on_list_activate)
        self.register_listbox.bind("<Button-3>", self._on_right_click)
        self.register_listbox.bind("<ButtonRelease-3>", self._on_right_click)

        self._ctx_menu = tk.Menu(self.frame, tearoff=False)
        self._ctx_menu.add_command(label="Edit Value (Lock)", command=self._edit_current_selection)
        self._ctx_menu.add_separator()
        self._ctx_menu.add_command(label="Unlock / Resume Auto", command=self._release_override)
        self._ctx_menu.add_command(label="Unlock ALL Registers", command=self._release_all_overrides)

    def apply_theme(self, dark_mode: bool):
        bg = "#333333" if dark_mode else "SystemButtonFace"
        fg = "#ffffff" if dark_mode else "black"
        ent_bg = "#444444" if dark_mode else "white"
        ent_fg = "#ffffff" if dark_mode else "black"

        def rec(w):
            try:
                # SKIP CTk widgets, they handle themselves
                if isinstance(w, (ctk.CTkButton, ctk.CTkFrame, ctk.CTkLabel, ctk.CTkEntry)):
                    return

                if isinstance(w, tk.Button): return
                if isinstance(w, (tk.Entry, tk.Listbox)):
                    w.config(bg=ent_bg, fg=ent_fg, insertbackground=fg)
                elif isinstance(w, tk.Menu):
                    w.config(bg=ent_bg, fg=ent_fg)
                else:
                    try: w.config(bg=bg)
                    except: pass
                    try: w.config(fg=fg)
                    except: pass
            except: pass
            for c in w.winfo_children(): rec(c)

        rec(self.frame)
        self.register_listbox.config(bg=ent_bg, fg=ent_fg)

    def _restart_if_running(self, *_):
        if self.simulating:
            self.stop_simulation()
            self.start_simulation()

    def _parse_ranges(self, s: str, start_addr: int, end_addr: int):
        s = (s or "").strip()
        if not s: return []
        parts = re.split(r"[;,]\s*", s)
        ranges = []
        for p in parts:
            p = (p or "").strip()
            if not p: continue
            if "-" in p:
                left, right = p.split("-", 1)
                a = int(left.strip()) if left.strip() else start_addr
                b = int(right.strip()) if right.strip() else end_addr
            else:
                a = int(p); b = a
            if b < a: a, b = b, a
            a = max(start_addr, a); b = min(end_addr, b)
            if a <= b: ranges.append((a, b))
        if not ranges: return []
        ranges.sort(key=lambda x: (x[0], x[1]))
        merged = [ranges[0]]
        for a, b in ranges[1:]:
            la, lb = merged[-1]
            if a <= lb + 1: merged[-1] = (la, max(lb, b))
            else: merged.append((a, b))
        return merged

    def _is_allowed_abs(self, address: int) -> bool:
        try: address = int(address)
        except: return False
        if address < self.start_address or address > self.end_address: return False
        if not self.allowed_ranges: return True
        for a, b in self.allowed_ranges:
            if a <= address <= b: return True
        return False

    def _is_allowed_rel(self, i_rel: int) -> bool:
        return self._is_allowed_abs(self.start_address + int(i_rel))

    def _on_external_write(self, address, values):
        """Called by DataBlock when an external client (TCP Scanner) writes data."""
        # Note: We are already inside the lock because DataBlock calls this while holding it
        for i, val in enumerate(values):
            abs_addr = address + i
            rel = abs_addr - self.start_address
            if 0 <= rel < len(self.block.values):
                self.written_values[rel] = int(val) & 0xFFFF
        # No UI refresh needed; _tick will handle it.

    def start_simulation(self):
        if self.simulating:
            messagebox.showinfo("Simulation", "Simulation already running.")
            return
        choice = messagebox.askyesnocancel("Simulation Mode", "Generate random values automatically?\nYes = Random values\nNo  = Manual values")
        if choice is None: return
        self.manual_mode = not choice

        try:
            start_addr = int(self.address_start_entry.get() or "0")
            end_addr = int(self.address_end_entry.get() or str(start_addr))
        except ValueError:
            messagebox.showwarning("Addresses", "Start/End must be integers.")
            return
        if end_addr < start_addr: end_addr = start_addr
        self.start_address, self.end_address = start_addr, end_addr

        try:
            self.allowed_ranges = self._parse_ranges(self.address_ranges_entry.get(), start_addr, end_addr)
        except Exception as e:
            messagebox.showwarning("Address Ranges", f"Invalid ranges format:\n{e}")
            return

        count = end_addr - start_addr + 1
        self.written_values.clear()
        
        # PASS THE LOCK HERE
        self.block = RangeValidatedDataBlock(
            start_addr, 
            [0] * count, 
            is_allowed_fn=self._is_allowed_abs,
            lock=self.lock,
            on_write_cb=self._on_external_write
        )

        host = (self.host_entry.get() or "").strip() or "localhost"
        self.host_entry.delete(0, tk.END); self.host_entry.insert(0, host)
        try: port = int(self.port_entry.get() or ("1502" if sys.platform.startswith("linux") else "502"))
        except: return

        self.simulating = True
        self.server_thread = Thread(target=self._run_tcp, args=(host, port), daemon=True)
        self.server_thread.start()
        self._tick()

    def stop_simulation(self):
        if not self.simulating: return
        self.simulating = False
        try:
            if self.server:
                try: self.server.shutdown()
                except: pass
                try: self.server.server_close()
                except: pass
        finally: self.server = None
        messagebox.showinfo("Simulation", "Simulation stopped.")

    def _run_tcp(self, host, port):
        try: ModbusTcpServer.allow_reuse_address = True
        except: pass
        store = ModbusSlaveContext(hr=self.block, ir=self.block, di=self.block, co=self.block)
        context = ModbusServerContext(slaves=store, single=True)
        ident = ModbusDeviceIdentification()
        ident.VendorName = "Pymodbus"; ident.ProductName = "Pymodbus Server"
        try:
            self.server = ModbusTcpServer(context, identity=ident, address=(host, port))
            self.server.serve_forever()
        except Exception as e:
            self.frame.after(0, lambda err=e: messagebox.showerror("Simulation Error", f"Error starting TCP simulation:\n{err}"))
        finally: self.simulating = False

    def _tick(self):
        if not self.simulating: return
        visible = False
        try:
            visible = bool(self.frame.winfo_exists() and self.frame.winfo_ismapped())
        except Exception:
            visible = False
        try:
            # LOCK THE SIMULATION LOOP
            with self.lock:
                fn = self.function_code_var.get().split(": ")[0]
                vtype = self.value_type_var.get()
                vals = self.block.values
                if not self.manual_mode:
                    if vtype == "Auto 103-Reg Demo": self._fill_auto_demo(vals) 
                    elif fn in ["01", "02"]: self._fill_bits(vals)
                    elif fn in ["03", "04"]: self._fill_by_type(vals, vtype)
                    else: self._fill_integers(vals)
                
                # Enforce manual overrides
                for idx, word in self.written_values.items():
                    if 0 <= idx < len(vals): vals[idx] = word

            # Listbox redraw is expensive; skip while tab is hidden.
            if visible:
                self._render_list()
        except Exception as e:
            pass 
        finally: self.frame.after(150 if visible else 350, self._tick)

    def _fill_bits(self, values):
        t = time.time()
        for i in range(len(values)):
            if not self._is_allowed_rel(i): continue
            if i in self.written_values: continue
            
            if i < 4: values[i] = int(((t * 4) + i) % 2)
            else:
                if random.random() < 0.05: values[i] = 1 - (values[i] & 1)

    def _fill_integers(self, values):
        for i in range(len(values)):
            if not self._is_allowed_rel(i): continue
            if i in self.written_values: continue
            step = (i % 7) + 1
            values[i] = (int(values[i]) + step) & 0xFFFF

    def _fill_by_type(self, values, vtype):
        n = len(values); t = time.time()
        if vtype == "Integer":
            self._fill_integers(values); return
        if vtype in ["Float", "Swapped Float"]:
            swap_mode = SwapMode.NONE if vtype == "Float" else SwapMode.WORD
            for i in range(0, n, 2):
                if not (self._is_allowed_rel(i) and self._is_allowed_rel(i+1)): continue
                if i in self.written_values or (i+1) in self.written_values: continue
                
                f = 20.0 + 10.0 * math.sin(2 * math.pi * (t / (6.0 + (i // 2))))
                words = encode_value_to_words(f, "float32", swap_mode)
                
                if i < n: values[i] = words[0]
                if i+1 < n: values[i+1] = words[1]
            return
        if vtype in ["Double", "Swapped Double"]:
            swap_mode = SwapMode.NONE if vtype == "Double" else SwapMode.WORD
            for i in range(0, n, 4):
                if not all(self._is_allowed_rel(i+k) for k in range(4)): continue
                if any((i+k) in self.written_values for k in range(4)): continue
                
                d = 1000.0 + 100.0 * math.sin(2 * math.pi * (t / (10.0 + (i // 4))))
                words = encode_value_to_words(d, "float64", swap_mode)
                
                for k in range(4):
                    if i+k < n: values[i+k] = words[k]
            return
        self._fill_integers(values)

    def _fill_auto_demo(self, values):
        n = len(values); t = time.time()
        def put(i_rel, word):
            if 0 <= i_rel < n and self._is_allowed_rel(i_rel) and i_rel not in self.written_values:
                values[i_rel] = int(word) & 0xFFFF
        
        # 0-10 bools
        for i in range(11):
            if not self._is_allowed_rel(i): continue
            if i in self.written_values: continue
            if i < 4: put(i, int(((t * 4) + i) % 2))
            else: put(i, 1 - (int(values[i]) & 1) if random.random() < 0.03 else int(values[i]))
        
        # 11-19 integers
        for i in range(11, 20):
            if not self._is_allowed_rel(i): continue
            if i in self.written_values: continue
            put(i, (int(values[i]) + ((i - 11) % 7) + 1) & 0xFFFF)

        def write_float_pair(base, fval, mode_str):
            # Check overlap with written values
            if base in self.written_values or (base+1) in self.written_values: return
            
            # Map string mode to SwapMode
            mode_map = {
                "none": SwapMode.NONE, "word": SwapMode.WORD,
                "byte": SwapMode.BYTE, "word+byte": SwapMode.WORD_AND_BYTE
            }
            s_mode = mode_map.get(mode_str, SwapMode.NONE)
            
            words = encode_value_to_words(fval, "float32", s_mode)
            if len(words) >= 2:
                put(base, words[0]); put(base+1, words[1])

        float_blocks = [
            (20, "none", 25.0), (30, "word", 45.0),
            (40, "byte", 65.0), (50, "word+byte", 85.0)
        ]
        for base, mode, offset in float_blocks:
            for k in range(5):
                f = offset + k + 5.0*math.sin(2*math.pi*(t/(7.0+k)))
                write_float_pair(base + 2*k, f, mode)

        def write_double_quad(base, dval, mode_str):
            # Check overlap
            if any((base+k) in self.written_values for k in range(4)): return
            
            # Map string mode to SwapMode
            mode_map = {
                "none": SwapMode.NONE, "word": SwapMode.WORD,
                "byte": SwapMode.BYTE, "word+byte": SwapMode.WORD_AND_BYTE
            }
            s_mode = mode_map.get(mode_str, SwapMode.NONE)
            
            words = encode_value_to_words(dval, "float64", s_mode)
            for k in range(min(4, len(words))): put(base+k, words[k])

        double_blocks = [
            (60, "none", 900.0), (70, "word", 2900.0),
            (80, "byte", 4900.0), (90, "word+byte", 6900.0)
        ]
        for base, mode, offset in double_blocks:
            d1 = offset + 150.0*math.sin(2*math.pi*(t/10.0))
            d2 = offset + 1000.0 + 150.0*math.sin(2*math.pi*(t/12.0))
            write_double_quad(base, d1, mode)
            write_double_quad(base+4, d2, mode)
            if (base+8) not in self.written_values: put(base+8, 0)
            if (base+9) not in self.written_values: put(base+9, 0)

        # Clock 101-103
        lt = time.localtime()
        if 101 not in self.written_values: put(101, lt.tm_hour)
        if 102 not in self.written_values: put(102, lt.tm_min)
        if 103 not in self.written_values: put(103, lt.tm_sec)

        # --- EASTER EGG START: ASCII STRING ---
        # "Gandalf_Modbus_Wizard" at Address 105
        # If the user hasn't overwritten them (locked), write the string.
        egg_start = 105
        egg_text = "Gandalf_Modbus_Wizard"
        
        # We need roughly 11 registers for 21 chars.
        # "string32" will pad to 32 chars (16 registers), which is safe.
        if egg_start < n:
             words = encode_value_to_words(egg_text, "string32", SwapMode.NONE)
             
             for i, w in enumerate(words):
                 current_addr = egg_start + i
                 if current_addr < n and current_addr not in self.written_values:
                     values[current_addr] = w
        # --- EASTER EGG END ---

    @staticmethod
    def _fmt_sci(x):
        try: x = float(x)
        except: return "n/a"
        ax = abs(x)
        if (ax >= 1e4) or (0 < ax < 1e-3):
            e = int(math.floor(math.log10(ax))) if ax != 0 else 0
            m = x / (10 ** e) if ax != 0 else 0.0
            return f"{m:.3g}*10^{e}"
        return f"{x:.3f}"

    def _render_list(self):
        fn = self.function_code_var.get().split(": ")[0]
        vtype = self.value_type_var.get()
        values = self.block.values
        n = len(values); base = self.start_address
        cur = self.register_listbox.yview()
        self.register_listbox.delete(0, tk.END)

        def add(s, locked=False):
            if locked: s += " [LOCKED]"
            self.register_listbox.insert(tk.END, s)
        
        def is_locked(idx): return idx in self.written_values
        def allowed(a): return self._is_allowed_abs(a)

        if fn in ["01", "02"] or vtype == "Integer":
            for i in range(n):
                addr = base + i
                if allowed(addr):
                    add(f"Address: {addr}, Value: {values[i]}", is_locked(i))
                else:
                    add(f"Address: {addr}, Value: <undefined>")
        elif vtype in ["Float", "Swapped Float"]:
            s_mode = SwapMode.NONE if vtype == "Float" else SwapMode.WORD
            for i in range(0, n, 2):
                a0 = base + i
                if i+1 < n and allowed(a0) and allowed(a0+1):
                    v, _ = decode_register_words([values[i], values[i+1]], "float32", s_mode)
                    locked = is_locked(i) or is_locked(i+1)
                    add(f"Addresses: {a0}-{a0+1}, Value: {self._fmt_sci(v)}", locked)
                else: add(f"Addresses: {a0}-{a0+1}, Value: <undefined>")
        elif vtype in ["Double", "Swapped Double"]:
            s_mode = SwapMode.NONE if vtype == "Double" else SwapMode.WORD
            for i in range(0, n, 4):
                a0 = base + i
                if i+3 < n and all(allowed(a0+k) for k in range(4)):
                    v, _ = decode_register_words(values[i:i+4], "float64", s_mode)
                    locked = any(is_locked(i+k) for k in range(4))
                    add(f"Addresses: {a0}-{a0+3}, Value: {self._fmt_sci(v)}", locked)
                else: add(f"Addresses: {a0}-{a0+3}, Value: <undefined>")
        elif vtype == "Auto 103-Reg Demo":
            # 0-19 Ints
            for i in range(min(20, n)):
                addr = base + i
                if allowed(addr):
                     add(f"Address: {addr}, Value: {values[i]}", is_locked(i))
                else: add(f"Address: {addr}, Value: <undefined>")
            
            # Floats
            for j in range(20, 60, 2):
                if j+1 >= n: break
                s_mode = SwapMode.NONE
                if 30 <= j <= 39: s_mode = SwapMode.WORD
                elif 40 <= j <= 49: s_mode = SwapMode.BYTE
                elif 50 <= j <= 59: s_mode = SwapMode.WORD_AND_BYTE
                a0 = base + j
                if allowed(a0) and allowed(a0+1):
                    v, _ = decode_register_words([values[j], values[j+1]], "float32", s_mode)
                    locked = is_locked(j) or is_locked(j+1)
                    add(f"Addresses: {a0}-{a0+1}, Value: {self._fmt_sci(v)}", locked)
                else: add(f"Addresses: {a0}-{a0+1}, Value: <undefined>")

            # Doubles
            for j in range(60, 100, 4):
                if j+3 >= n: break
                s_mode = SwapMode.NONE
                if 70 <= j <= 79: s_mode = SwapMode.WORD
                elif 80 <= j <= 89: s_mode = SwapMode.BYTE
                elif 90 <= j <= 99: s_mode = SwapMode.WORD_AND_BYTE
                a0 = base + j
                if all(allowed(a0+k) for k in range(4)):
                    v, _ = decode_register_words(values[j:j+4], "float64", s_mode)
                    locked = any(is_locked(j+k) for k in range(4))
                    add(f"Addresses: {a0}-{a0+3}, Value: {self._fmt_sci(v)}", locked)
                else: add(f"Addresses: {a0}-{a0+3}, Value: <undefined>")

            # Clock
            for j in range(101, 104):
                if j >= n: break
                addr = base + j
                lbl = {101:"HH", 102:"MM", 103:"SS"}.get(addr, "")
                if allowed(addr):
                    add(f"Address: {addr}, Value: {values[j]} ({lbl})", is_locked(j))
                else: add(f"Address: {addr}, Value: <undefined>")
            
            # Easter Egg String (Optional Display in Listbox logic)
            # Since the listbox shows raw values, we don't need special rendering here.
            # The Scanner will decode it.
            # But we can show it for addresses > 104
            for j in range(105, 125):
                if j >= n: break
                addr = base + j
                if allowed(addr):
                     add(f"Address: {addr}, Value: {values[j]} (ASCII)", is_locked(j))
                else: add(f"Address: {addr}, Value: <undefined>")


        self.register_listbox.yview_moveto(cur[0])

    def write_register(self, address, value):
        if not self.block or not self._is_allowed_abs(address): return
        rel = address - self.start_address
        if 0 <= rel < len(self.block.values):
            vv = int(value) & 0xFFFF
            with self.lock:
                self.written_values[rel] = vv
                self.block.values[rel] = vv
            self._render_list()

    def _on_list_double_click(self, evt):
        idx = evt.widget.nearest(evt.y)
        if idx is not None: self._start_edit_at_index(idx)

    def _on_list_activate(self, _evt):
        sel = self.register_listbox.curselection()
        if sel: self._start_edit_at_index(sel[0])

    def _on_right_click(self, evt):
        idx = evt.widget.nearest(evt.y)
        if idx is not None:
            self.register_listbox.selection_clear(0, tk.END)
            self.register_listbox.selection_set(idx)
            self.register_listbox.activate(idx)
            self._ctx_menu.tk_popup(evt.x_root, evt.y_root)

    def _edit_current_selection(self):
        sel = self.register_listbox.curselection()
        if sel: self._start_edit_at_index(sel[0])

    def _start_edit_at_index(self, idx):
        if not self.simulating: return
        line = self.register_listbox.get(idx)
        if "<undefined>" in line: return
        m = re.search(r"Address: (\d+), Value: (\d+)", line)
        addr = 0
        if m:
            addr = int(m.group(1))
            cur = int(m.group(2))
        else:
             # Try matching range "Addresses: 20-21, Value: ..."
            m2 = re.search(r"Addresses: (\d+)-(\d+)", line)
            if m2:
                addr = int(m2.group(1))
                cur = 0 # Default for floats/doubles since editing complex types is hard via simple dialog
            else:
                return

        val = simpledialog.askinteger("Edit", f"Value for {addr} (Will Lock):", initialvalue=cur, parent=self.frame)
        if val is not None: self.write_register(addr, val)

    def _release_override(self):
        """Unlocks the currently selected register so auto-simulation resumes."""
        sel = self.register_listbox.curselection()
        if not sel: return
        line = self.register_listbox.get(sel[0])
        # Parse single address
        m = re.search(r"Address: (\d+)", line)
        if m:
            addr = int(m.group(1))
            rel = addr - self.start_address
            with self.lock:
                if rel in self.written_values:
                    del self.written_values[rel]
        else:
            # Parse range "Addresses: 20-21"
            m2 = re.search(r"Addresses: (\d+)-(\d+)", line)
            if m2:
                start, end = int(m2.group(1)), int(m2.group(2))
                with self.lock:
                    for a in range(start, end+1):
                        rel = a - self.start_address
                        if rel in self.written_values:
                            del self.written_values[rel]
        self._render_list()

    def _release_all_overrides(self):
        """Unlocks ALL registers."""
        with self.lock:
            self.written_values.clear()
        self._render_list()

    def open_ipv4_settings(self):
        if os.name == "nt":
            try: subprocess.Popen(["control", "ncpa.cpl"])
            except: pass
        elif sys.platform.startswith("linux"):
            # In WSL, open the Windows network settings UI.
            if os.getenv("WSL_DISTRO_NAME"):
                try:
                    subprocess.Popen(["cmd.exe", "/c", "start", "control", "ncpa.cpl"])
                    return
                except Exception:
                    pass
            # Try common Linux network managers
            cmds = ["nm-connection-editor", "gnome-control-center network", "kcmshell5 kcm_networkmanagement"]
            for cmd in cmds:
                try:
                    subprocess.Popen(cmd.split())
                    return
                except FileNotFoundError:
                    continue
            messagebox.showinfo("Network Settings", "Could not find a network settings manager.")
