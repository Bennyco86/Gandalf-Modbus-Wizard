import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import customtkinter as ctk
from threading import Thread, Event
import time
import csv
import datetime
from abc import ABC, abstractmethod

# Try to import xlsxwriter for charting; handle gracefully if missing
try:
    import xlsxwriter
    HAS_XLSXWRITER = True
except ImportError:
    HAS_XLSXWRITER = False

# Try to import the new Live Trend Popup
try:
    from live_trend_popup import LiveTrendPopup
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from modbus_common import (
    SwapMode,
    TYPE_REGISTER_WIDTH,
    TYPE_BIT_WIDTH,
    ExceptionInfo,
    parse_exception_from_response,
    exception_status_text,
    decode_register_words,
    encode_value_to_words,
)

# --- UPDATED: Added Strings to this Dictionary ---
DATA_TYPE_LABEL_TO_NAME = {
    "Int16": "int16", "UInt16": "uint16", 
    "Int32": "int32", "UInt32": "uint32",
    "Int64": "int64", "UInt64": "uint64", 
    "Float32": "float32", "Float64": "float64",
    # Strings
    "String (10 char)": "string10",
    "String (20 char)": "string20",
    "String (32 char)": "string32",
    "String (64 char)": "string64",
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
        self.one_based = tk.BooleanVar(value=True)
        
        self.poll_var = tk.StringVar(value="50")
        self.batch_var = tk.StringVar(value="1")
        
        self.data_type_var = tk.StringVar(value="Int16")
        self.swap_mode_var = tk.StringVar(value="None")
        
        self.address_format = "decimal"
        self.value_format = tk.StringVar(value="decimal")
        
        self.write_enabled = tk.BooleanVar(value=False)
        self.record_enabled = tk.BooleanVar(value=False)

        self._raw_values = {}
        self._raw_range = (0, -1)
        self._raw_ptype = None
        self._error_by_addr = {}

        # History: list of (timestamp_str, { "Label": numeric_value })
        self._history_data = []
        
        # Trend Popup Reference
        self.trend_popup = None

        self._row_order = []
        self._row_map = {}
        self._prev_vals = {}
        self._prev_status = {}

        # Default color for CTkButton is usually a blue, store it if needed
        self._addr_btns = {}
        self._val_btns = {}
        
        self._build_base_ui()

    def _build_base_ui(self):
        # Row 0: Connection
        self.conn_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.conn_frame.grid(row=0, column=0, columnspan=4, sticky="nw", pady=(2, 2))
        self._build_connection_settings(self.conn_frame)

        # Row 1-2: Controls
        ctrl = ctk.CTkFrame(self.frame, fg_color="transparent")
        ctrl.grid(row=1, column=0, columnspan=4, sticky="nw", pady=(2, 2))
        
        ctk.CTkLabel(ctrl, text="Start Addr:").grid(row=0, column=0, sticky="w", padx=2)
        ctk.CTkEntry(ctrl, width=80, textvariable=self.start_var).grid(row=0, column=1, sticky="w", padx=2)
        ctk.CTkLabel(ctrl, text="End Addr:").grid(row=0, column=2, sticky="w", padx=2)
        ctk.CTkEntry(ctrl, width=80, textvariable=self.end_var).grid(row=0, column=3, sticky="w", padx=2)
        ctk.CTkLabel(ctrl, text="Unit ID:").grid(row=0, column=4, sticky="w", padx=2)
        ctk.CTkEntry(ctrl, width=60, textvariable=self.unit_var).grid(row=0, column=5, sticky="w", padx=2)

        ctk.CTkLabel(ctrl, text="Point Type:").grid(row=1, column=0, sticky="w", padx=2)
        # Point Type Menu
        self.pt_menu = ctk.CTkOptionMenu(ctrl, variable=self.point_type_var, values=["03: Holding Registers"], width=180) 
        self.pt_menu.grid(row=1, column=1, columnspan=2, sticky="w", padx=2, pady=5)
        
        ctk.CTkCheckBox(ctrl, text="Use 1-based addresses (40001)", variable=self.one_based, command=self._render_from_cache, width=200).grid(row=1, column=3, columnspan=3, sticky="w", padx=5)

        ctk.CTkLabel(ctrl, text="Polling (ms):").grid(row=2, column=0, sticky="w", padx=2)
        ctk.CTkEntry(ctrl, width=80, textvariable=self.poll_var).grid(row=2, column=1, sticky="w", padx=2)
        ctk.CTkLabel(ctrl, text="Batch Size:").grid(row=2, column=2, sticky="w", padx=2)
        ctk.CTkEntry(ctrl, width=80, textvariable=self.batch_var).grid(row=2, column=3, sticky="w", padx=2)
        
        # Modern Buttons
        self.connect_btn = ctk.CTkButton(ctrl, text="Connect", fg_color="#2e7d32", text_color="white", width=100, command=self.connect_modbus)
        self.connect_btn.grid(row=2, column=4, padx=4, sticky="w")
        
        ctk.CTkButton(ctrl, text="Disconnect", fg_color="red", hover_color="#8B0000", text_color="white", width=100, command=self.disconnect_modbus).grid(row=2, column=5, padx=4, sticky="w")

        # Row 2 (Format) & Row 3 (Buttons)
        fmt = ctk.CTkFrame(self.frame, fg_color="transparent")
        fmt.grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 2))
        ctk.CTkLabel(fmt, text="Data Type:").grid(row=0, column=0, sticky="w", padx=2)
        ctk.CTkComboBox(fmt, variable=self.data_type_var, values=list(DATA_TYPE_LABEL_TO_NAME.keys()), width=160, state="readonly").grid(row=0, column=1, sticky="w", padx=5)
        ctk.CTkLabel(fmt, text="Swap:").grid(row=0, column=2, sticky="w", padx=2)
        ctk.CTkComboBox(fmt, variable=self.swap_mode_var, values=list(SWAP_LABEL_TO_MODE.keys()), width=140, state="readonly").grid(row=0, column=3, sticky="w", padx=5)
        
        ctk.CTkButton(fmt, text="Apply Format", width=100, command=self._render_from_cache).grid(row=0, column=4, sticky="w")

        # --- Single Row, Full Labels ---
        btns = ctk.CTkFrame(self.frame, fg_color="transparent")
        btns.grid(row=3, column=0, columnspan=4, sticky="w", pady=2)
        
        def mk_btn(parent, txt, key, store, is_val=True):
            # Using Small, discrete buttons for format toggles
            b = ctk.CTkButton(parent, text=txt, command=lambda: self._set_fmt(key, is_val), height=24, width=120, fg_color="transparent", border_width=1, text_color=("black", "white"))
            b.pack(side="left", padx=1)
            store[key] = b
            
        mk_btn(btns, "Values: Dec", "decimal", self._val_btns, True)
        mk_btn(btns, "Values: Bool", "binary", self._val_btns, True)
        mk_btn(btns, "Values: Hex", "hex", self._val_btns, True)
        ctk.CTkLabel(btns, text="|").pack(side="left", padx=4)
        mk_btn(btns, "Addr: Dec", "decimal", self._addr_btns, False)
        mk_btn(btns, "Addr: Hex", "hex", self._addr_btns, False)
        
        self._update_fmt_buttons()

        # Results Table
        res = ctk.CTkFrame(self.frame, corner_radius=0)
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

        # Bottom Bar (Row 5)
        bot = ctk.CTkFrame(self.frame, fg_color="transparent")
        bot.grid(row=5, column=0, columnspan=4, sticky="w", pady=4)
        
        ctk.CTkButton(bot, text="Start Scan", fg_color="green", text_color="white", width=100, command=self.start_scan).pack(side="left", padx=2)
        ctk.CTkButton(bot, text="Stop Scan", fg_color="red", hover_color="#8B0000", text_color="white", width=100, command=self.stop_scan).pack(side="left", padx=2)
        ctk.CTkButton(bot, text="Clear", fg_color="gray", text_color="white", width=80, command=self._clear_table).pack(side="left", padx=2)
        ctk.CTkButton(bot, text="Export Results / Log", fg_color="#1f6aa5", text_color="white", width=140, command=self._export_data).pack(side="left", padx=2)
        ctk.CTkButton(bot, text="Trend Selected", fg_color="purple", hover_color="#6a0dad", text_color="white", width=120, command=self._launch_trend).pack(side="left", padx=2)

        # Write Controls (Row 6) - Moved to new row to prevent cropping
        wf = ctk.CTkFrame(self.frame, fg_color="transparent")
        wf.grid(row=6, column=0, columnspan=4, sticky="w", pady=(0, 5))
        
        self.chk_record = ctk.CTkCheckBox(wf, text="Record Data", variable=self.record_enabled, command=self._toggle_record)
        self.chk_record.pack(side="left", padx=5)
        
        self.chk_write = ctk.CTkCheckBox(wf, text="Enable Writing", variable=self.write_enabled, command=self._toggle_write_mode)
        self.chk_write.pack(side="left", padx=5)
        
        ctk.CTkLabel(wf, text="Addr:").pack(side="left", padx=(10, 2))
        self.write_addr_entry = ctk.CTkEntry(wf, width=60, state="disabled")
        self.write_addr_entry.pack(side="left", padx=2)
        ctk.CTkLabel(wf, text="Val:").pack(side="left", padx=2)
        self.write_val_entry = ctk.CTkEntry(wf, width=60, state="disabled")
        self.write_val_entry.pack(side="left", padx=2)
        
        # Fixed contrast: White text on Dark Orange button
        self.btn_write = ctk.CTkButton(wf, text="Write", state="disabled", fg_color="#e65100", text_color="white", width=80, command=self._manual_write)
        self.btn_write.pack(side="left", padx=10)

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
        
        if not self.record_enabled.get():
            self._history_data = []
            
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

        is_visible = False
        try:
            is_visible = bool(self.frame.winfo_exists() and self.frame.winfo_ismapped())
        except Exception:
            is_visible = False

        # Skip heavy table redraw when this session tab is not visible.
        if is_visible:
            self._render_from_cache()

        # Trend popup is a separate window; keep it live when open.
        if self.trend_popup and self.trend_popup.is_open:
            snapshot = self._capture_decoded_snapshot()
            if snapshot:
                self.trend_popup.update(snapshot)

        if self.record_enabled.get():
            snapshot = self._capture_decoded_snapshot()
            if snapshot:
                ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self._history_data.append((ts, snapshot))

        self.frame.after(120 if is_visible else 300, self._ui_tick)

    def _launch_trend(self):
        if not HAS_MATPLOTLIB:
            messagebox.showerror("Error", "Matplotlib is not installed.\nPlease run: pip install matplotlib")
            return

        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showinfo("Trend", "Please select one or more rows in the table to trend.")
            return

        selected_regs = []
        for iid in selected_items:
            vals = self.tree.item(iid, "values")
            if vals:
                selected_regs.append(vals[0])

        if len(selected_regs) > 8:
            if not messagebox.askyesno("Warning", f"You selected {len(selected_regs)} registers.\nGraphing this many lines can be hard to read.\nContinue?"):
                return

        if self.trend_popup and self.trend_popup.is_open:
            self.trend_popup.on_close()

        # Improved Dark Mode Detection for CustomTkinter
        is_dark_mode = False
        try:
            import customtkinter as ctk
            if ctk.get_appearance_mode() == "Dark":
                is_dark_mode = True
        except ImportError:
            # Fallback for standard Tkinter
            try:
                current_bg = self.frame.cget("bg")
                is_dark_mode = (current_bg == "#333333")
            except: 
                pass

        self.trend_popup = LiveTrendPopup(self.frame, selected_regs, is_dark=is_dark_mode, max_points=3000)

    def _capture_decoded_snapshot(self):
        if not self._raw_values: return None
        start, end = self._raw_range
        type_name = DATA_TYPE_LABEL_TO_NAME.get(self.data_type_var.get(), "int16")
        swap_mode = SWAP_LABEL_TO_MODE.get(self.swap_mode_var.get(), SwapMode.NONE)
        regs_per = TYPE_REGISTER_WIDTH.get(type_name, 1)
        
        snapshot = {}
        a = start
        while a <= end:
            chunk = []
            valid = True
            for i in range(regs_per):
                val = self._raw_values.get(a+i)
                if val is None: 
                    valid = False; break
                chunk.append(val)
            
            if valid:
                val_num, _ = decode_register_words(chunk, type_name, swap_mode)
                if self.one_based.get():
                    lbl = f"{a}" if regs_per==1 else f"{a}-{a+regs_per-1}"
                else:
                    lbl = f"{a-1}" if regs_per==1 else f"{a-1}-{a+regs_per-2}"
                snapshot[lbl] = val_num
            
            a += regs_per
        return snapshot

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
        # Return string/float directly
        if type_name.startswith("string") or type_name.startswith("float"):
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
            self.write_addr_entry.config(state="normal"); self.write_val_entry.config(state="normal"); self.btn_write.configure(state="normal")
        else:
            self.write_addr_entry.config(state="disabled"); self.write_val_entry.config(state="disabled"); self.btn_write.configure(state="disabled")
    
    def _toggle_record(self): pass 

    def _manual_write(self):
        if not self.connected: return
        try:
            a_str = self.write_addr_entry.get()
            v_str = self.write_val_entry.get()
            
            addr = int(a_str, 16) if "x" in a_str.lower() else int(a_str)
            wire_addr = max(0, addr - 1) if self.one_based.get() else addr
            
            type_name = DATA_TYPE_LABEL_TO_NAME.get(self.data_type_var.get(), "int16")
            swap_mode = SWAP_LABEL_TO_MODE.get(self.swap_mode_var.get(), SwapMode.NONE)
            
            # Encode Value (handles floats, strings, etc)
            words = encode_value_to_words(v_str, type_name, swap_mode)
            if not words:
                messagebox.showerror("Write Error", f"Could not encode '{v_str}' as {type_name}")
                return

            try: unit = int(self.unit_var.get())
            except: unit = 1

            success, msg = self._perform_write(wire_addr, words, unit)
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

        type_name = DATA_TYPE_LABEL_TO_NAME.get(self.data_type_var.get(), "int16")
        is_float = "float" in type_name.lower()
        is_string = "string" in type_name.lower()
        
        prompt = f"Enter value for {addr_disp} ({self.data_type_var.get()}):"
        
        if is_float:
            new_val = simpledialog.askfloat("Write Float", prompt, parent=self.frame)
        else:
            new_val = simpledialog.askstring("Write Value", prompt, parent=self.frame)

        if new_val is not None:
            swap_mode = SWAP_LABEL_TO_MODE.get(self.swap_mode_var.get(), SwapMode.NONE)
            words = encode_value_to_words(new_val, type_name, swap_mode)
            
            if not words:
                messagebox.showerror("Write Error", "Invalid format or value.")
                return

            wire_addr = max(0, addr_disp - 1) if self.one_based.get() else addr_disp
            try: unit = int(self.unit_var.get())
            except: unit = 1
            
            success, msg = self._perform_write(wire_addr, words, unit)
            if not success: messagebox.showerror("Write Error", msg)

    def _set_fmt(self, key, is_val):
        if is_val: self.value_format.set(key)
        else: self.address_format = key
        self._update_fmt_buttons()
        self._render_from_cache()

    def _update_fmt_buttons(self):
        # Update colors to show active state
        for k, b in self._val_btns.items(): 
            if k == self.value_format.get():
                b.configure(fg_color="#1f6aa5", text_color="white")
            else:
                b.configure(fg_color="transparent", text_color=("black", "white"))
                
        for k, b in self._addr_btns.items(): 
            if k == self.address_format:
                b.configure(fg_color="#1f6aa5", text_color="white")
            else:
                b.configure(fg_color="transparent", text_color=("black", "white"))

    def _clear_table(self):
        self._row_order.clear(); self._row_map.clear(); self._prev_vals.clear(); self._prev_status.clear()
        self._history_data = [] 
        for c in self.tree.get_children(): self.tree.delete(c)

    def _clear_table_keep_view(self):
        y = self.tree.yview(); self._clear_table()
        try: self.tree.yview_moveto(y[0])
        except: pass

    def _export_data(self):
        has_log = len(self._history_data) > 1
        export_mode = "snapshot"
        if has_log and HAS_XLSXWRITER:
            ans = messagebox.askyesno("Export", f"You have {len(self._history_data)} recorded samples.\n\nYes = Export Trend Log (Excel)\nNo  = Export Snapshot (CSV)")
            if ans: export_mode = "log"
        elif has_log and not HAS_XLSXWRITER:
             messagebox.showinfo("Info", "Log data exists, but 'xlsxwriter' is not installed.\nExporting snapshot.")

        if export_mode == "snapshot": self._download_results_csv()
        else: self._download_results_excel_trend()

    def _download_results_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path: return
        try:
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Address", "Value", "Status"])
                for k in self._row_order: item = self.tree.item(self._row_map[k], "values"); w.writerow(item)
            messagebox.showinfo("Export", f"Saved to {path}")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _download_results_excel_trend(self):
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path: return
        try:
            # Float64 scans can produce NaN/Inf; allow xlsxwriter to export those
            # cells as Excel errors instead of throwing write_number() exceptions.
            workbook = xlsxwriter.Workbook(path, {'nan_inf_to_errors': True})
            sheet = workbook.add_worksheet("Trend Data")
            all_labels = set()
            for ts, snap in self._history_data: all_labels.update(snap.keys())
            
            def sort_key(s):
                try: return int(s.split('-')[0])
                except: return s
            sorted_labels = sorted(list(all_labels), key=sort_key)
            
            headers = ["Time"] + [f"Reg {lbl}" for lbl in sorted_labels]
            sheet.write_row(0, 0, headers)
            
            row = 1
            for ts, snap in self._history_data:
                row_data = [ts]
                for lbl in sorted_labels: row_data.append(snap.get(lbl, ""))
                sheet.write_row(row, 0, row_data)
                row += 1
            
            chart = workbook.add_chart({'type': 'line'})
            count_graphed = 0
            for i, lbl in enumerate(sorted_labels):
                if count_graphed >= 15: break
                col_idx = i + 1 
                has_data = any(h[1].get(lbl) is not None for h in self._history_data)
                if has_data:
                    chart.add_series({
                        'name': f'Reg {lbl}',
                        'categories': ['Trend Data', 1, 0, row-1, 0],
                        'values': ['Trend Data', 1, col_idx, row-1, col_idx],
                    })
                    count_graphed += 1
            
            sheet.insert_chart('E2', chart)
            workbook.close()
            messagebox.showinfo("Export", f"Saved to {path}")
        except Exception as e: messagebox.showerror("Export Error", str(e))
