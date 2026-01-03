# ModbusSimulation.py
import os
import re
import time
import math
import random
import struct
import subprocess
import tkinter as tk
from tkinter import messagebox, simpledialog

from threading import Thread
from pymodbus.server.sync import ModbusTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext,
)

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

SWAP_MODES = ("none", "word", "byte", "word+byte")


class RangeValidatedDataBlock(ModbusSequentialDataBlock):
    def __init__(self, address, values, is_allowed_fn):
        super().__init__(address, values)
        self._is_allowed_fn = is_allowed_fn

    def validate(self, address, count=1):
        try:
            for a in range(int(address), int(address) + int(count)):
                if not self._is_allowed_fn(a):
                    return False
        except Exception:
            return False
        return super().validate(address, count)


class ModbusSimulation:
    def __init__(self, frame):
        self.frame = frame
        self.simulating = False
        self.server = None
        self.server_thread = None
        self.start_address = 0
        self.end_address = 103
        self.allowed_ranges = []
        self.written_values = {}
        self.manual_mode = False
        self.block = None
        self._ctx_menu = None
        self._build_ui()

    def _build_ui(self):
        top = tk.Frame(self.frame)
        top.grid(row=0, column=0, sticky="nw")
        for r in range(9): top.grid_rowconfigure(r, pad=1)

        c0 = 0; c1 = 1; c2 = 2
        tk.Label(top, text="Host:").grid(row=0, column=c0, sticky="w")
        self.host_entry = tk.Entry(top, width=16)
        self.host_entry.grid(row=0, column=c1, sticky="w", columnspan=2)
        self.host_entry.insert(0, "localhost")

        tk.Label(top, text="Port:").grid(row=1, column=c0, sticky="w")
        self.port_entry = tk.Entry(top, width=8)
        self.port_entry.grid(row=1, column=c1, sticky="w")
        self.port_entry.insert(0, "502")

        tk.Label(top, text="Function Code:").grid(row=2, column=c0, sticky="w")
        self.function_code_var = tk.StringVar(value="03: Holding Registers")
        self.function_code_var.trace_add("write", self._restart_if_running)
        tk.OptionMenu(top, self.function_code_var, *MODBUS_FUNCTION_CODES.keys()).grid(row=2, column=c1, columnspan=2, sticky="w")

        tk.Label(top, text="Value Type:").grid(row=3, column=c0, sticky="w")
        self.value_type_var = tk.StringVar(value="Auto 103-Reg Demo")
        self.value_type_var.trace_add("write", self._restart_if_running)
        tk.OptionMenu(top, self.value_type_var, *VALUE_TYPES).grid(row=3, column=c1, columnspan=2, sticky="w")

        tk.Label(top, text="Address Start:").grid(row=4, column=c0, sticky="w")
        self.address_start_entry = tk.Entry(top, width=8)
        self.address_start_entry.grid(row=4, column=c1, sticky="w")
        self.address_start_entry.insert(0, "0")

        tk.Label(top, text="Address End:").grid(row=5, column=c0, sticky="w")
        self.address_end_entry = tk.Entry(top, width=8)
        self.address_end_entry.grid(row=5, column=c1, sticky="w")
        self.address_end_entry.insert(0, "103")

        tk.Label(top, text="Address Ranges (optional):").grid(row=6, column=c0, sticky="w")
        self.address_ranges_entry = tk.Entry(top, width=28)
        self.address_ranges_entry.grid(row=6, column=c1, sticky="w", columnspan=2)
        self.address_ranges_entry.insert(0, "")

        tk.Label(top, text="Device ID:").grid(row=7, column=c0, sticky="w")
        self.device_id_entry = tk.Entry(top, width=8)
        self.device_id_entry.grid(row=7, column=c1, sticky="w")
        self.device_id_entry.insert(0, "1")

        tk.Button(top, text="Start Simulation", bg="green", fg="white", command=self.start_simulation).grid(row=8, column=c0, sticky="w")
        tk.Button(top, text="Stop Simulation", bg="red", fg="white", command=self.stop_simulation).grid(row=8, column=c1, sticky="w")
        tk.Button(top, text="Open IPv4 Settings (ncpa.cpl)", command=self.open_ipv4_settings).grid(row=8, column=c2, sticky="w")

        holder = tk.Frame(self.frame)
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
        self._ctx_menu.add_command(label="Edit Value…", command=self._edit_current_selection)

    # --- THEME APPLICATION ---
    def apply_theme(self, dark_mode: bool):
        bg = "#333333" if dark_mode else "SystemButtonFace"
        fg = "#ffffff" if dark_mode else "black"
        ent_bg = "#444444" if dark_mode else "white"
        ent_fg = "#ffffff" if dark_mode else "black"

        def rec(w):
            try:
                # Skip buttons (keep red/green/default)
                if isinstance(w, tk.Button): return
                
                # Entries/Listboxes
                if isinstance(w, (tk.Entry, tk.Listbox)):
                    w.config(bg=ent_bg, fg=ent_fg, insertbackground=fg)
                # Menus
                elif isinstance(w, tk.Menu):
                    w.config(bg=ent_bg, fg=ent_fg)
                # Others
                else:
                    try: w.config(bg=bg)
                    except: pass
                    try: w.config(fg=fg)
                    except: pass
            except: pass
            for c in w.winfo_children(): rec(c)

        rec(self.frame)
        # FORCE Listbox update
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
        self.block = RangeValidatedDataBlock(start_addr, [0] * count, is_allowed_fn=self._is_allowed_abs)

        host = (self.host_entry.get() or "").strip() or "localhost"
        self.host_entry.delete(0, tk.END); self.host_entry.insert(0, host)
        try: port = int(self.port_entry.get() or "502")
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
            self.frame.after(0, lambda: messagebox.showerror("Simulation Error", f"Error starting TCP simulation:\n{e}"))
        finally: self.simulating = False

    def _tick(self):
        if not self.simulating: return
        try:
            fn = self.function_code_var.get().split(": ")[0]
            vtype = self.value_type_var.get()
            vals = self.block.values
            if not self.manual_mode:
                if vtype == "Auto 103-Reg Demo": self._fill_auto_demo(vals) # FIXED
                elif fn in ["01", "02"]: self._fill_bits(vals)
                elif fn in ["03", "04"]: self._fill_by_type(vals, vtype)
                else: self._fill_integers(vals)
            for idx, word in self.written_values.items():
                if 0 <= idx < len(vals): vals[idx] = word
            self._render_list()
        except Exception as e:
            self.frame.after(0, lambda: messagebox.showerror("Simulation", f"Update error:\n{e}"))
        finally: self.frame.after(150, self._tick)

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
            high_first = (vtype == "Float")
            for i in range(0, n, 2):
                if not (self._is_allowed_rel(i) and self._is_allowed_rel(i+1)): continue
                if i in self.written_values or (i+1) in self.written_values: continue
                f = 20.0 + 10.0 * math.sin(2 * math.pi * (t / (6.0 + (i // 2))))
                w0, w1 = self._split_f32_words(f)
                w0, w1 = (w0, w1) if high_first else (w1, w0)
                if i < n: values[i] = w0
                if i+1 < n: values[i+1] = w1
            return
        if vtype in ["Double", "Swapped Double"]:
            high_first = (vtype == "Double")
            for i in range(0, n, 4):
                if not all(self._is_allowed_rel(i+k) for k in range(4)): continue
                if any((i+k) in self.written_values for k in range(4)): continue
                d = 1000.0 + 100.0 * math.sin(2 * math.pi * (t / (10.0 + (i // 4))))
                ws = list(self._split_f64_words(d))
                ws = ws if high_first else list(reversed(ws))
                for k in range(4):
                    if i+k < n: values[i+k] = ws[k]
            return
        self._fill_integers(values)

    def _fill_auto_demo(self, values):
        """
        Aligned Demo Map (Indices 0-103)
        0-19: Ints/Bools
        20-59: Floats (aligned to even addresses)
        60-99: Doubles (aligned to 4-byte addresses)
        101-103: Clock
        """
        n = len(values); t = time.time()
        def put(i_rel, word):
            if 0 <= i_rel < n and self._is_allowed_rel(i_rel) and i_rel not in self.written_values:
                values[i_rel] = int(word) & 0xFFFF
        
        # 0-10 bools
        for i in range(11):
            if not self._is_allowed_rel(i): continue
            if i < 4: put(i, int(((t * 4) + i) % 2))
            else: put(i, 1 - (int(values[i]) & 1) if random.random() < 0.03 else int(values[i]))
        
        # 11-19 integers
        for i in range(11, 20):
            if not self._is_allowed_rel(i): continue
            put(i, (int(values[i]) + ((i - 11) % 7) + 1) & 0xFFFF)

        def write_float_pair(base, fval, mode):
            w0, w1 = self._encode_f32_for_mode(fval, mode)
            put(base, w0); put(base+1, w1)

        # Floats 20-59 (Aligned 2)
        # 20-29: None, 30-39: Word, 40-49: Byte, 50-59: Word+Byte
        float_blocks = [
            (20, "none", 25.0), (30, "word", 45.0),
            (40, "byte", 65.0), (50, "word+byte", 85.0)
        ]
        for base, mode, offset in float_blocks:
            for k in range(5):
                f = offset + k + 5.0*math.sin(2*math.pi*(t/(7.0+k)))
                write_float_pair(base + 2*k, f, mode)

        def write_double_quad(base, dval, mode):
            ws = self._encode_f64_for_mode(dval, mode)
            for k in range(4): put(base+k, ws[k])

        # Doubles 60-99 (Aligned 4)
        # 60-69: None, 70-79: Word, 80-89: Byte, 90-99: Word+Byte
        double_blocks = [
            (60, "none", 900.0), (70, "word", 2900.0),
            (80, "byte", 4900.0), (90, "word+byte", 6900.0)
        ]
        for base, mode, offset in double_blocks:
            # 2 doubles per block (indices +0, +4) + 2 pad regs (+8, +9)
            d1 = offset + 150.0*math.sin(2*math.pi*(t/10.0))
            d2 = offset + 1000.0 + 150.0*math.sin(2*math.pi*(t/12.0))
            write_double_quad(base, d1, mode)
            write_double_quad(base+4, d2, mode)
            put(base+8, 0); put(base+9, 0)

        # Clock 101-103
        lt = time.localtime()
        put(101, lt.tm_hour); put(102, lt.tm_min); put(103, lt.tm_sec)

    @staticmethod
    def _swap_bytes_in_word(word): return ((word & 0x00FF) << 8) | ((word & 0xFF00) >> 8)

    @classmethod
    def _apply_swap_mode(cls, words, mode):
        out = [int(w) & 0xFFFF for w in words]
        if mode in ("byte", "word+byte"): out = [cls._swap_bytes_in_word(w) for w in out]
        if mode in ("word", "word+byte"): out = list(reversed(out))
        return out

    @staticmethod
    def _split_f32_words(fval):
        b = struct.pack(">f", float(fval))
        return int.from_bytes(b[0:2], "big"), int.from_bytes(b[2:4], "big")

    @staticmethod
    def _split_f64_words(dval):
        b = struct.pack(">d", float(dval))
        return tuple(int.from_bytes(b[i:i+2], "big") for i in range(0, 8, 2))

    @classmethod
    def _encode_f32_for_mode(cls, fval, mode):
        w0, w1 = cls._split_f32_words(fval)
        out = cls._apply_swap_mode([w0, w1], mode)
        return out[0], out[1]

    @classmethod
    def _encode_f64_for_mode(cls, dval, mode):
        ws = list(cls._split_f64_words(dval))
        out = cls._apply_swap_mode(ws, mode)
        return tuple(out)

    @classmethod
    def _decode_f32_mode(cls, w0, w1, mode):
        ws = cls._apply_swap_mode([w0, w1], mode)
        try: return struct.unpack(">f", ws[0].to_bytes(2,"big")+ws[1].to_bytes(2,"big"))[0]
        except: return float("nan")

    @classmethod
    def _decode_f64_mode(cls, words4, mode):
        ws = cls._apply_swap_mode(list(words4), mode)
        try: return struct.unpack(">d", b"".join(int(w).to_bytes(2,"big") for w in ws))[0]
        except: return float("nan")

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

        def add(s): self.register_listbox.insert(tk.END, s)
        def allowed(a): return self._is_allowed_abs(a)

        if fn in ["01", "02"] or vtype == "Integer":
            for i in range(n):
                addr = base + i
                add(f"Address: {addr}, Value: {values[i]}" if allowed(addr) else f"Address: {addr}, Value: <undefined>")
        elif vtype in ["Float", "Swapped Float"]:
            mode = "none" if vtype == "Float" else "word"
            for i in range(0, n, 2):
                a0 = base + i
                if i+1 < n and allowed(a0) and allowed(a0+1):
                    v = self._decode_f32_mode(values[i], values[i+1], mode)
                    add(f"Addresses: {a0}-{a0+1}, Value: {self._fmt_sci(v)}")
                else: add(f"Addresses: {a0}-{a0+1}, Value: <undefined>")
        elif vtype in ["Double", "Swapped Double"]:
            mode = "none" if vtype == "Double" else "word"
            for i in range(0, n, 4):
                a0 = base + i
                if i+3 < n and all(allowed(a0+k) for k in range(4)):
                    v = self._decode_f64_mode(values[i:i+4], mode)
                    add(f"Addresses: {a0}-{a0+3}, Value: {self._fmt_sci(v)}")
                else: add(f"Addresses: {a0}-{a0+3}, Value: <undefined>")
        elif vtype == "Auto 103-Reg Demo":
            # 0-19 Ints
            for i in range(min(20, n)):
                addr = base + i
                add(f"Address: {addr}, Value: {values[i]}" if allowed(addr) else f"Address: {addr}, Value: <undefined>")
            
            # Floats 20-59 (Aligned 2)
            # 20-29: None, 30-39: Word, 40-49: Byte, 50-59: Word+Byte
            for j in range(20, 60, 2):
                if j+1 >= n: break
                mode = "none"
                if 30 <= j <= 39: mode = "word"
                elif 40 <= j <= 49: mode = "byte"
                elif 50 <= j <= 59: mode = "word+byte"
                a0 = base + j
                if allowed(a0) and allowed(a0+1):
                    v = self._decode_f32_mode(values[j], values[j+1], mode)
                    add(f"Addresses: {a0}-{a0+1}, Value: {self._fmt_sci(v)}")
                else: add(f"Addresses: {a0}-{a0+1}, Value: <undefined>")

            # Doubles 60-99 (Aligned 4)
            # 60-69: None, 70-79: Word, 80-89: Byte, 90-99: Word+Byte
            for j in range(60, 100, 4):
                if j+3 >= n: break
                mode = "none"
                if 70 <= j <= 79: mode = "word"
                elif 80 <= j <= 89: mode = "byte"
                elif 90 <= j <= 99: mode = "word+byte"
                a0 = base + j
                if all(allowed(a0+k) for k in range(4)):
                    v = self._decode_f64_mode(values[j:j+4], mode)
                    add(f"Addresses: {a0}-{a0+3}, Value: {self._fmt_sci(v)}")
                else: add(f"Addresses: {a0}-{a0+3}, Value: <undefined>")

            # Clock 101-103
            for j in range(101, 104):
                if j >= n: break
                addr = base + j
                lbl = {101:"HH", 102:"MM", 103:"SS"}.get(addr, "")
                add(f"Address: {addr}, Value: {values[j]} ({lbl})" if allowed(addr) else f"Address: {addr}, Value: <undefined>")

        self.register_listbox.yview_moveto(cur[0])

    def write_register(self, address, value):
        if not self.block or not self._is_allowed_abs(address): return
        rel = address - self.start_address
        if 0 <= rel < len(self.block.values):
            vv = int(value) & 0xFFFF
            self.written_values[rel] = vv
            self.block.values[rel] = vv
            self.block.setValues(address, [vv])
            self._render_list()

    def set_register_values(self, relative_address, values):
        if not self.block: return
        base_abs = self.start_address + relative_address
        out = []
        for off, v in enumerate(values):
            if not self._is_allowed_abs(base_abs+off): return
            idx = relative_address + off
            if 0 <= idx < len(self.block.values):
                vv = int(v) & 0xFFFF
                self.block.values[idx] = vv
                self.written_values[idx] = vv
                out.append(vv)
        if out:
            self.block.setValues(base_abs, out)
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
        if m:
            addr = int(m.group(1))
            cur = int(m.group(2))
            val = simpledialog.askinteger("Edit", f"Value for {addr}:", initialvalue=cur, parent=self.frame)
            if val is not None: self.write_register(addr, val)

    def open_ipv4_settings(self):
        try: subprocess.Popen(["control", "ncpa.cpl"])
        except: pass