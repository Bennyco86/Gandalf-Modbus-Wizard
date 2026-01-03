import tkinter as tk
from tkinter import ttk
import os
import sys
import ctypes

from auto_detection_wizard import AutoDetectionWizard
from modbus_rtu_scanner import ModbusRTUScanner, RTUSharedConnection
from modbus_tcp_scanner import ModbusTCPScanner
from ModbusSimulation import ModbusSimulation


def _resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base, rel_path)


def _set_windows_app_user_model_id(app_id: str) -> None:
    if os.name != "nt": return
    try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except: pass


class GandalfModbusWizard:
    ICON_FILENAME = "GandalfModbusWizard_BMP.ico"
    APP_ID = "BennyCohen.GandalfModbusWizard"
    VERSION = "1.9"

    def __init__(self, root: tk.Tk):
        self.root = root
        
        # Initialize state
        self.dark_mode = False 
        
        _set_windows_app_user_model_id(self.APP_ID)

        self.root.title(f"Gandalf Modbus Wizard v{self.VERSION} - Created by Benny Cohen")
        self.root.geometry("900x820")
        self.root.minsize(900, 820)
        self._apply_app_icon(self.ICON_FILENAME)

        # --- Menu Bar ---
        self.menubar = tk.Menu(root)
        self.menubar.add_command(label="Switch to Dark Mode", command=self.toggle_theme)
        root.config(menu=self.menubar)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=1, fill="both")

        # --- Shared Resources ---
        self._rtu_shared = RTUSharedConnection()

        # --- Tabs ---
        self.simulation_frame = tk.Frame(self.notebook)
        self.notebook.add(self.simulation_frame, text="Modbus Simulation")
        self.simulation = ModbusSimulation(self.simulation_frame)

        self.tcp_scanner_frame = tk.Frame(self.notebook)
        self.notebook.insert(0, self.tcp_scanner_frame, text="Modbus TCP Scanner")
        tcp_toolbar = tk.Frame(self.tcp_scanner_frame)
        tcp_toolbar.pack(side="top", fill="x", padx=6, pady=4)
        tk.Button(tcp_toolbar, text="New TCP Session", command=self._new_tcp_session).pack(side="left")
        tk.Button(tcp_toolbar, text="Close TCP Session", command=self._close_tcp_session).pack(side="left", padx=(6, 0))
        
        self.tcp_sessions_nb = ttk.Notebook(self.tcp_scanner_frame)
        self.tcp_sessions_nb.pack(expand=1, fill="both")
        self.tcp_sessions = []
        self._tcp_session_counter = 0
        self._tcp_free_ids = set()
        self._last_tcp_snapshot = None 
        
        self._new_tcp_session()

        # Auto Detect
        self.auto_wizard_frame = tk.Frame(self.notebook)
        self.notebook.insert(1, self.auto_wizard_frame, text="Auto Detection Wizard")
        
        self.auto_wizard = AutoDetectionWizard(
            self.auto_wizard_frame, 
            self.transfer_connection_params,
            port_in_use_callback=self._rtu_shared.is_port_in_use
        )

        self.rtu_scanner_frame = tk.Frame(self.notebook)
        self.notebook.insert(2, self.rtu_scanner_frame, text="Modbus RTU Scanner")
        rtu_toolbar = tk.Frame(self.rtu_scanner_frame)
        rtu_toolbar.pack(side="top", fill="x", padx=6, pady=4)
        tk.Button(rtu_toolbar, text="New RTU Session", command=self._new_rtu_session).pack(side="left")
        tk.Button(rtu_toolbar, text="Close RTU Session", command=self._close_rtu_session).pack(side="left", padx=(6, 0))
        
        self.rtu_sessions_nb = ttk.Notebook(self.rtu_scanner_frame)
        self.rtu_sessions_nb.pack(expand=1, fill="both")
        self.rtu_sessions = []
        self._rtu_session_counter = 0
        self._last_rtu_snapshot = None

        self._new_rtu_session()

        try: self.notebook.select(self.simulation_frame)
        except: pass

        root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _apply_app_icon(self, ico_filename: str):
        ico_path = _resource_path(ico_filename)
        try:
            if os.path.exists(ico_path): self.root.iconbitmap(ico_path)
        except: pass
        try:
            from PIL import Image, ImageTk
            if os.path.exists(ico_path):
                img = Image.open(ico_path)
                try: img = img.convert("RGBA")
                except: pass
                try: img = img.resize((64, 64))
                except: pass
                self._app_icon_photo = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, self._app_icon_photo)
        except: pass

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        
        # 1. Update Label
        new_label = "Switch to Light Mode" if self.dark_mode else "Switch to Dark Mode"
        try: self.menubar.entryconfigure(1, label=new_label) # try index 1
        except: 
            try: self.menubar.entryconfigure(0, label=new_label) # fallback index 0
            except: pass

        # 2. Palette
        bg = "#333333" if self.dark_mode else "SystemButtonFace"
        fg = "#ffffff" if self.dark_mode else "black"
        ent_bg = "#444444" if self.dark_mode else "white"
        ent_fg = "#ffffff" if self.dark_mode else "black"
        
        # 3. Configure Style
        style = ttk.Style()
        
        if self.dark_mode:
            # 'clam' theme is required for dark Treeviews on Windows
            try: style.theme_use('clam')
            except: pass
            
            style.configure(".", background=bg, foreground=fg, fieldbackground=ent_bg)
            style.configure("Treeview", background=ent_bg, fieldbackground=ent_bg, foreground=fg)
            style.map("Treeview", background=[("selected", "#0078d7")], foreground=[("selected", "white")])
            style.configure("TNotebook", background=bg)
            style.configure("TNotebook.Tab", background=bg, foreground=fg)
            style.map("TNotebook.Tab", background=[("selected", "#505050")], foreground=[("selected", "white")])
        else:
            if os.name == 'nt':
                try: style.theme_use('vista')
                except: style.theme_use('default')
            else:
                style.theme_use('default')
                
            style.configure(".", background=bg, foreground=fg, fieldbackground=ent_bg)
            style.configure("Treeview", background="white", fieldbackground="white", foreground="black")
            style.configure("TNotebook", background=bg)

        # 4. Recursive Color Applicator
        def rec(w):
            try:
                # SKIP BUTTONS (Keep them native/colored)
                if isinstance(w, tk.Button):
                    return

                # Entries/Listboxes
                if isinstance(w, (tk.Entry, tk.Listbox)):
                    w.config(bg=ent_bg, fg=ent_fg, insertbackground=fg)
                
                # Containers
                elif isinstance(w, (tk.Frame, tk.Label, tk.LabelFrame)):
                    w.config(bg=bg)
                    if hasattr(w, "config") and "fg" in w.keys():
                        w.config(fg=fg)
                
                # Toplevel
                elif isinstance(w, (tk.Toplevel, tk.Tk)):
                    w.config(bg=bg)

            except Exception:
                pass
            
            for c in w.winfo_children():
                rec(c)
        
        rec(self.root)
        
        # 5. Force update on Simulation tab
        if self.simulation:
            self.simulation.apply_theme(self.dark_mode)

    # --- TCP Logic ---
    def _next_tcp_id(self) -> int:
        if getattr(self, "_tcp_free_ids", None):
            sid = min(self._tcp_free_ids); self._tcp_free_ids.remove(sid)
            return sid
        self._tcp_session_counter += 1
        return self._tcp_session_counter

    def _new_tcp_session(self):
        try:
            curr_idx = self.tcp_sessions_nb.index("current")
            if 0 <= curr_idx < len(self.tcp_sessions):
                sc = self.tcp_sessions[curr_idx]["scanner"]
                self._last_tcp_snapshot = {
                    "host": sc.host_entry.get(), "port": sc.port_entry.get(),
                    "unit": sc.unit_var.get(), "connected": sc.connected
                }
        except: pass

        sid = self._next_tcp_id()
        tab = tk.Frame(self.tcp_sessions_nb)
        tab.pack(expand=1, fill="both")
        scanner = ModbusTCPScanner(tab, self.simulation)
        
        if self._last_tcp_snapshot:
            try:
                scanner.host_entry.delete(0, tk.END); scanner.host_entry.insert(0, self._last_tcp_snapshot["host"])
                scanner.port_entry.delete(0, tk.END); scanner.port_entry.insert(0, self._last_tcp_snapshot["port"])
                scanner.unit_var.set(self._last_tcp_snapshot["unit"])
                if self._last_tcp_snapshot["connected"]:
                    tab.after(100, scanner.connect_modbus)
            except: pass

        self.tcp_sessions.append({"id": sid, "tab": tab, "scanner": scanner})
        self.tcp_sessions_nb.add(tab, text=f"TCP {sid}")
        self.tcp_sessions_nb.select(tab)
        # Apply theme if needed
        if self.dark_mode: 
            self.dark_mode = not self.dark_mode # Toggle back to re-trigger
            self.toggle_theme() 

    def _close_tcp_session(self):
        try: idx = self.tcp_sessions_nb.index("current")
        except: return
        if idx < 0 or idx >= len(self.tcp_sessions): return
        
        item = self.tcp_sessions.pop(idx)
        try: item["scanner"].disconnect_modbus()
        except: pass
        self.tcp_sessions_nb.forget(idx)
        
        if not self.tcp_sessions:
            self._tcp_session_counter = 0; self._tcp_free_ids = set()
            self._new_tcp_session()
        else:
            self._tcp_free_ids.add(item["id"])

    # --- RTU Logic ---
    def _get_active_rtu_scanner(self):
        try:
            idx = self.rtu_sessions_nb.index("current")
            if 0 <= idx < len(self.rtu_sessions): return self.rtu_sessions[idx]
        except: pass
        return self.rtu_sessions[0] if self.rtu_sessions else None

    def _new_rtu_session(self):
        snapshot = None
        active = self._get_active_rtu_scanner()
        if active and hasattr(active, "export_ui_params"):
            try: snapshot = active.export_ui_params()
            except: pass
        
        if not snapshot and self._last_rtu_snapshot: snapshot = self._last_rtu_snapshot
        
        if not snapshot and self._rtu_shared and self._rtu_shared.connected and self._rtu_shared.params:
             p = self._rtu_shared.params
             snapshot = {
                 "port": p.get("port",""), "baudrate": str(p.get("baudrate","")),
                 "parity": str(p.get("parity","")), "stopbits": str(p.get("stopbits","")),
                 "bytesize": str(p.get("bytesize","")), "timeout": str(p.get("timeout",""))
             }

        self._rtu_session_counter += 1
        tab = ttk.Frame(self.rtu_sessions_nb)
        tab.pack(fill="both", expand=True)
        self.rtu_sessions_nb.add(tab, text=f"RTU {self._rtu_session_counter}")
        self.rtu_sessions_nb.select(tab)

        scanner = ModbusRTUScanner(tab, simulation_instance=None, shared_connection=self._rtu_shared)
        self.rtu_sessions.append(scanner)
        
        if snapshot:
            try: scanner.import_ui_params(snapshot)
            except: pass
        
        if self._rtu_shared.connected:
            tab.after(100, scanner.connect_modbus)
            
        if self.dark_mode: 
            self.dark_mode = not self.dark_mode
            self.toggle_theme()
            
        return scanner

    def _close_rtu_session(self):
        try: idx = self.rtu_sessions_nb.index("current")
        except: return
        if idx < 0 or idx >= len(self.rtu_sessions): return
        
        scanner = self.rtu_sessions.pop(idx)
        try: self._last_rtu_snapshot = scanner.export_ui_params()
        except: pass
        try: scanner.stop_scan()
        except: pass
        
        self.rtu_sessions_nb.forget(idx)
        
        if not self.rtu_sessions:
            if self._rtu_shared: self._rtu_shared.disconnect()
            self._rtu_session_counter = 0
            self._new_rtu_session()

    def transfer_connection_params(self, params: dict):
        rtu = self._get_active_rtu_scanner()
        if not rtu: return
        try: self.notebook.select(2)
        except: pass
        try: rtu.set_connection_params(params); rtu.connect_modbus()
        except: pass

    def on_closing(self):
        try:
            if self.simulation: self.simulation.stop_simulation()
        except: pass
        try:
            if self._rtu_shared: self._rtu_shared.disconnect()
        except: pass
        os._exit(0)

if __name__ == "__main__":
    _set_windows_app_user_model_id(GandalfModbusWizard.APP_ID)
    root = tk.Tk()
    GandalfModbusWizard(root)
    root.mainloop()