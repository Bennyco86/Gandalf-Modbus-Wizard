import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from threading import Thread, Event
import time
import csv
from abc import ABC, abstractmethod

from modbus_common import (
    SwapMode,
    TYPE_REGISTER_WIDTH,
    TYPE_BIT_WIDTH,
    ExceptionInfo,
    parse_exception_from_response,
    exception_status_text,
    decode_register_words,
)

DATA_TYPE_LABEL_TO_NAME = {
    "Int16": "int16", "UInt16": "uint16", "Int32": "int32", "UInt32": "uint32",
    "Int64": "int64", "UInt64": "uint64", "Float32": "float32", "Float64": "float64",
}

SWAP_LABEL_TO_MODE = {
    "None": SwapMode.NONE, "Word Swap": SwapMode.WORD,
    "Byte Swap": SwapMode.BYTE, "Word + Byte Swap": SwapMode.WORD_AND_BYTE,
}

class ModbusScannerBase(ABC):
    def __init__(self, frame):
        self.frame = frame
        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(4, weight=1)
        self.connected = False
        self.scanning = False
        self.stop_evt = Event()
        self.scan_thread = None
        self.generation = 0
        self.start_var = tk.StringVar(value="1")
        self.end_var = tk.StringVar(value="110")
        self.unit_var = tk.StringVar(value="1")
        self.point_type_var = tk.StringVar(value="03: Holding Registers")
        self.one_based = tk.BooleanVar(value=False)
        self.poll_var = tk.StringVar(value="50")
        self.batch_var = tk.StringVar(value="1")
        self.data_type_var = tk.StringVar(value="Int16")
        self.swap_mode_var = tk.StringVar(value="None")
        self.address_format = "decimal"
        self.value_format = tk.StringVar(value="decimal")
        self.write_enabled = tk.BooleanVar(value=False)
        self._raw_values = {}
        self._raw_range = (0, -1)
        self._raw_ptype = None
        self._error_by_addr = {}
        self._row_order = []
        self._row_map = {}
        self._prev_vals = {}
        self._prev_status = {}
        tmp = tk.Button(self.frame)
        self._btn_default_bg = tmp.cget("bg")
        tmp.destroy()
        self._addr_btns = {}
        self._val_btns = {}
        self._build_base_ui()

    def _build_base_ui(self):
        self.conn_frame = tk.Frame(self.frame)
        self.conn_frame.grid(row=0, column=0, columnspan=4, sticky="nw", pady=(2, 2))
        self._build_connection_settings(self.conn_frame)
        ctrl = tk.Frame(self.frame)
        ctrl.grid(row=1, column=0, columnspan=4, sticky="nw", pady=(2, 2))
        tk.Label(ctrl, text="Start Addr:").grid(row=0, column=0, sticky="w")
        tk.Entry(ctrl, width=10, textvariable=self.start_var).grid(row=0, column=1, sticky="w")
        tk.Label(ctrl, text="End Addr:").grid(row=0, column=2, sticky="w")
        tk.Entry(ctrl, width=10, textvariable=self.end_var).grid(row=0, column=3, sticky="w")
        tk.Label(ctrl, text="Unit ID:").grid(row=0, column=4, sticky="w")
        tk.Entry(ctrl, width=6, textvariable=self.unit_var).grid(row=0, column=5, sticky="w")
        tk.Label(ctrl, text="Point Type:").grid(row=1, column=0, sticky="w")
        self.pt_menu = tk.OptionMenu(ctrl, self.point_type_var, "03: Holding Registers") 
        self.pt_menu.grid(row=1, column=1, columnspan=2, sticky="w")
        tk.Checkbutton(ctrl, text="Use 1-based addresses (40001)", variable=self.one_based, command=self._render_from_cache).grid(row=1, column=3, columnspan=3, sticky="w")
        tk.Label(ctrl, text="Polling (ms):").grid(row=2, column=0, sticky="w")
        tk.Entry(ctrl, width=8, textvariable=self.poll_var).grid(row=2, column=1, sticky="w")
        tk.Label(ctrl, text="Batch Size:").grid(row=2, column=2, sticky="w")
        tk.Entry(ctrl, width=8, textvariable=self.batch_var).grid(row=2, column=3, sticky="w")
        self.connect_btn = tk.Button(ctrl, text="Connect", bg="#2e7d32", fg="white", command=self.connect_modbus)
        self.connect_btn.grid(row=2, column=4, padx=4, sticky="w")
        tk.Button(ctrl, text="Disconnect", bg="red", fg="white", command=self.disconnect_modbus).grid(row=2, column=5, padx=4, sticky="w")
        fmt = tk.Frame(self.frame)
        fmt.grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 2))
        tk.Label(fmt, text="Data Type:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(fmt, textvariable=self.data_type_var, values=list(DATA_TYPE_LABEL_TO_NAME.keys()), width=10, state="readonly").grid(row=0, column=1, sticky="w", padx=5)
        tk.Label(fmt, text="Swap:").grid(row=0, column=2, sticky="w")
        ttk.Combobox(fmt, textvariable=self.swap_mode_var, values=list(SWAP_LABEL_TO_MODE.keys()), width=14, state="readonly").grid(row=0, column=3, sticky="w", padx=5)
        tk.Button(fmt, text="Apply Format", command=self._render_from_cache).grid(row=0, column=4, sticky="w")
        btns = tk.Frame(self.frame)
        btns.grid(row=3, column=0, columnspan=4, sticky="w", pady=2)
        def mk_btn(parent, txt, key, store, is_val=True):
            b = tk.Button(parent, text=txt, command=lambda: self._set_fmt(key, is_val))
            b.pack(side="left", padx=1)
            store[key] = b
        mk_btn(btns, "Show Values as Decimal", "decimal", self._val_btns, True)
        mk_btn(btns, "Show Values as Binary", "binary", self._val_btns, True)
        mk_btn(btns, "Show Values as Hex", "hex", self._val_btns, True)
        tk.Label(btns, text="|").pack(side="left", padx=4)
        mk_btn(btns, "Show Addresses as Decimal", "decimal", self._addr_btns, False)
        mk_btn(btns, "Show Addresses as Hex", "hex", self._addr_btns, False)
        self._update_fmt_buttons()
        res = tk.Frame(self.frame)
        res.grid(row=4, column=0, columnspan=4, sticky="nsew")
        res.grid_rowconfigure(0, weight=1)
        res.grid_columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(res, columns=("Address", "Value", "Status"), show="headings")
        self.tree.heading("Address", text="Address"); self.tree.column("Address", width=110)
        self.tree.heading("Value", text="Value"); self.tree.column("Value", width=200)
        self.tree.heading("Status", text="Status"); self.tree.column("Status", width=180)
        self.tree.tag_configure("error", foreground="red")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        sb = tk.Scrollbar(res, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        bot = tk.Frame(self.frame)
        bot.grid(row=5, column=0, columnspan=4, sticky="w", pady=4)
        tk.Button(bot, text="Start Scan", bg="green", fg="white", command=self.start_scan).pack(side="left", padx=2)
        tk.Button(bot, text="Stop Scan", bg="red", fg="white", command=self.stop_scan).pack(side="left", padx=2)
        tk.Button(bot, text="Clear", command=self._clear_table).pack(side="left", padx=2)
        tk.Button(bot, text="Export CSV", bg="blue", fg="white", command=self._download_results).pack(side="left", padx=2)
        wf = tk.Frame(bot, bd=1, relief=tk.GROOVE)
        wf.pack(side="left", padx=10, fill="y")
        self.chk_write = tk.Checkbutton(wf, text="Enable Writing", variable=self.write_enabled, command=self._toggle_write_mode)
        self.chk_write.pack(side="left", padx=5)
        tk.Label(wf, text="Addr:").pack(side="left")
        self.write_addr_entry = tk.Entry(wf, width=6, state="disabled")
        self.write_addr_entry.pack(side="left", padx=2)
        tk.Label(wf, text="Val:").pack(side="left")
        self.write_val_entry = tk.Entry(wf, width=6, state="disabled")
        self.write_val_entry.pack(side="left", padx=2)
        self.btn_write = tk.Button(wf, text="Write", state="disabled", bg="#f0ad4e", command=self._manual_write)
        self.btn_write.pack(side="left", padx=5)

    @abstractmethod
    def _build_connection_settings(self, parent): pass
    @abstractmethod
    def connect_modbus(self): pass
    @abstractmethod
    def disconnect_modbus(self): pass
    @abstractmethod
    def _scan_once(self, gen): pass
    @abstractmethod
    def _perform_write(self, wire_addr, val, unit): pass

    def start_scan(self):
        if not self.connected: messagebox.showerror("Scan", "Not connected."); return
        if self.scanning: return
        self.scanning = True
        self.stop_evt.clear()
        self.generation += 1
        self.scan_thread = Thread(target=self._scan_loop, args=(self.generation,), daemon=True)
        self.scan_thread.start()
        self._ui_tick()

    def stop_scan(self): self.scanning = False; self.stop_evt.set()

    def _scan_loop(self, gen):
        while self.scanning and not self.stop_evt.is_set() and gen == self.generation:
            try: poll = max(10, int(self.poll_var.get())); self._scan_once(gen); time.sleep(poll / 1000.0)
            except: time.sleep(1.0)

    def _ui_tick(self):
        if not self.scanning: return
        self._render_from_cache()
        self.frame.after(100, self._ui_tick)

    def _render_from_cache(self):
        rows = self._build_rows()
        keys = [r[0] for r in rows]
        if keys != self._row_order:
            self._clear_table_keep_view()
            for k, v, status, is_err in rows:
                tags = ("error",) if is_err else ()
                iid = self.tree.insert("", "end", values=(k, v, status), tags=tags)
                self._row_map[k] = iid
                self._prev_vals[k] = v
                self._prev_status[k] = status
                self._row_order.append(k)
            return
        for k, v, status, is_err in rows:
            iid = self._row_map.get(k)
            if not iid: continue
            if self._prev_vals.get(k) != v or self._prev_status.get(k) != status:
                tags = ("error",) if is_err else ()
                self.tree.item(iid, values=(k, v, status), tags=tags)
                self._prev_vals[k] = v
                self._prev_status[k] = status

    def _build_rows(self):
        if not self._raw_values and not self._error_by_addr: return []
        start, end = self._raw_range
        type_name = DATA_TYPE_LABEL_TO_NAME.get(self.data_type_var.get(), "int16")
        swap_mode = SWAP_LABEL_TO_MODE.get(self.swap_mode_var.get(), SwapMode.NONE)
        regs_per = TYPE_REGISTER_WIDTH.get(type_name, 1)
        rows = []
        def fmt_addr(a):
            disp = a if self.one_based.get() else (a - 1)
            if self.address_format == "hex": return f"{int(disp):X}"
            return str(disp)

        a = start
        while a <= end:
            err_in_range = None
            chunk_vals = []
            for i in range(regs_per):
                addr = a + i
                if addr in self._error_by_addr: err_in_range = self._error_by_addr[addr]
                chunk_vals.append(self._raw_values.get(addr))
            
            if regs_per == 1: key = fmt_addr(a)
            else: key = f"{fmt_addr(a)}-{fmt_addr(a+regs_per-1)}"
            
            if err_in_range:
                status = exception_status_text(err_in_range, undefined=False)
                rows.append((key, "n/a", status, True))
            elif any(x is None for x in chunk_vals):
                rows.append((key, "undefined", "Waiting...", True))
            else:
                val, default_text = decode_register_words(chunk_vals, type_name, swap_mode)
                val_str = self._fmt_val(val, type_name, default_text)
                rows.append((key, val_str, "OK", False))
            a += regs_per
        return rows

    def _fmt_val(self, val, type_name, default_text=None):
        if val is None: return "Error"
        if type_name in ("float32", "float64"):
            return default_text if default_text else str(val)
        bits = TYPE_BIT_WIDTH.get(type_name, 16)
        mask = (1 << bits) - 1
        v_int = int(val) & mask
        fmt = self.value_format.get()
        if fmt == "hex": return f"{v_int:X}"
        if fmt == "binary": return f"{v_int:0{bits}b}"
        return str(val)

    def _toggle_write_mode(self):
        if self.write_enabled.get():
            if not messagebox.askyesno("Enable Writing", "Warning: Writing to field devices can be dangerous.\nProceed?", icon='warning'):
                self.write_enabled.set(False); return
            self.write_addr_entry.config(state="normal"); self.write_val_entry.config(state="normal"); self.btn_write.config(state="normal")
        else:
            self.write_addr_entry.config(state="disabled"); self.write_val_entry.config(state="disabled"); self.btn_write.config(state="disabled")

    def _manual_write(self):
        if not self.connected: return
        try:
            a_str = self.write_addr_entry.get(); v_str = self.write_val_entry.get()
            addr = int(a_str, 16) if "x" in a_str.lower() else int(a_str)
            val = int(v_str, 16) if "x" in v_str.lower() else int(v_str)
            wire_addr = max(0, addr - 1) if self.one_based.get() else addr
            unit = int(self.unit_var.get())
            success, msg = self._perform_write(wire_addr, val, unit)
            if not success: messagebox.showerror("Write Error", msg)
            else: messagebox.showinfo("Write", "Success")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _on_tree_double_click(self, event):
        if not self.write_enabled.get(): return
        item = self.tree.identify_row(event.y)
        if not item: return
        vals = self.tree.item(item, "values")
        lbl = vals[0].split("-")[0]
        try: addr_disp = int(lbl, 16) if self.address_format == "hex" else int(lbl)
        except: return
        new_val = simpledialog.askinteger("Write", f"Enter value for {addr_disp}:", parent=self.frame)
        if new_val is not None:
            wire_addr = max(0, addr_disp - 1) if self.one_based.get() else addr_disp
            try: unit = int(self.unit_var.get())
            except: unit = 1
            success, msg = self._perform_write(wire_addr, new_val, unit)
            if not success: messagebox.showerror("Write Error", msg)

    def _set_fmt(self, key, is_val):
        if is_val: self.value_format.set(key)
        else: self.address_format = key
        self._update_fmt_buttons()
        self._render_from_cache()

    def _update_fmt_buttons(self):
        for k, b in self._val_btns.items(): b.config(bg=self._btn_default_bg if k != self.value_format.get() else "#bdbdbd")
        for k, b in self._addr_btns.items(): b.config(bg=self._btn_default_bg if k != self.address_format else "#bdbdbd")

    def _clear_table(self):
        self._row_order.clear(); self._row_map.clear(); self._prev_vals.clear(); self._prev_status.clear()
        for c in self.tree.get_children(): self.tree.delete(c)

    def _clear_table_keep_view(self):
        y = self.tree.yview(); self._clear_table()
        try: self.tree.yview_moveto(y[0])
        except: pass

    def _download_results(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path: return
        try:
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Address", "Value", "Status"])
                for k in self._row_order: item = self.tree.item(self._row_map[k], "values"); w.writerow(item)
            messagebox.showinfo("Export", f"Saved to {path}")
        except Exception as e: messagebox.showerror("Error", str(e))