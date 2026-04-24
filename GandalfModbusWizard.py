import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import os
import sys
import ctypes
import json
import glob
import shutil
import subprocess

from auto_detection_wizard import AutoDetectionWizard
from modbus_rtu_scanner import ModbusRTUScanner, RTUSharedConnection
from modbus_tcp_scanner import ModbusTCPScanner
from ModbusSimulation import ModbusSimulation
from diagnostics_tab import DiagnosticsTab


def _resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base, rel_path)


def _set_windows_app_user_model_id(app_id: str) -> None:
    if os.name != "nt": return
    try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except: pass


class GandalfModbusWizard(ctk.CTk):
    ICON_FILENAME = "GandalfModbusWizard_BMP.ico"
    ICON_PNG_FILENAME = "gandalf-modbus-wizard-256.png"
    APP_ID = "BennyCohen.GandalfModbusWizard"
    VERSION = "1.13"

    def __init__(self):
        super().__init__()
        
        # Initialize state
        self.dark_mode = False 
        
        # CTk Setup
        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("dark-blue")
        
        _set_windows_app_user_model_id(self.APP_ID)

        self.title(f"Gandalf Modbus Wizard v{self.VERSION} - Created by Benny Cohen")
        self.geometry("1000x850")
        self.minsize(1000, 850)
        try:
            if sys.platform.startswith("linux"):
                # Align WM_CLASS with desktop file for taskbar icon matching.
                self.wm_class("GandalfModbusWizard", "GandalfModbusWizard")
        except Exception:
            pass
        self._ensure_linux_desktop_integration()
        self._apply_app_icon(self.ICON_FILENAME, self.ICON_PNG_FILENAME)
        if sys.platform.startswith("linux"):
            self.after(250, self._apply_linux_icon_late)
            self.after(1000, self._apply_linux_icon_late)
            self.after(2000, self._apply_linux_icon_late)

        # --- Menu Bar ---
        self.menubar = tk.Menu(self)
        self.menubar.add_command(label="Toggle Appearance (Light/Dark)", command=self.toggle_theme)
        self.config(menu=self.menubar)

        # Sync TTK styles with the current appearance.
        self._apply_ttk_theme()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=1, fill="both")

        # --- Shared Resources ---
        self._rtu_shared = RTUSharedConnection()

        # --- Tabs ---
        # USE CTkFrame so they auto-update theme!
        self.simulation_frame = ctk.CTkFrame(self.notebook, corner_radius=0) 
        self.notebook.add(self.simulation_frame, text="Modbus Simulation")
        self.simulation = ModbusSimulation(self.simulation_frame)

        self.tcp_scanner_frame = ctk.CTkFrame(self.notebook, corner_radius=0)
        self.notebook.insert(0, self.tcp_scanner_frame, text="Modbus TCP Scanner")
        
        tcp_toolbar = ctk.CTkFrame(self.tcp_scanner_frame, fg_color="transparent")
        tcp_toolbar.pack(side="top", fill="x", padx=6, pady=4)
        ctk.CTkButton(tcp_toolbar, text="New TCP Session", command=self._new_tcp_session).pack(side="left", padx=2)
        ctk.CTkButton(tcp_toolbar, text="Close TCP Session", command=self._close_tcp_session, fg_color="red", hover_color="#8B0000").pack(side="left", padx=(6, 0))
        
        self.tcp_sessions_nb = ttk.Notebook(self.tcp_scanner_frame)
        self.tcp_sessions_nb.pack(expand=1, fill="both")
        self.tcp_sessions = []
        self._tcp_session_counter = 0
        self._tcp_free_ids = set()
        self._last_tcp_snapshot = None 
        
        self._new_tcp_session()

        # Auto Detect
        self.auto_wizard_frame = ctk.CTkFrame(self.notebook, corner_radius=0)
        self.notebook.insert(1, self.auto_wizard_frame, text="Auto Detection Wizard")
        
        self.auto_wizard = AutoDetectionWizard(
            self.auto_wizard_frame, 
            self.transfer_connection_params,
            port_in_use_callback=self._rtu_shared.is_port_in_use
        )

        self.rtu_scanner_frame = ctk.CTkFrame(self.notebook, corner_radius=0)
        self.notebook.insert(2, self.rtu_scanner_frame, text="Modbus RTU Scanner")
        
        rtu_toolbar = ctk.CTkFrame(self.rtu_scanner_frame, fg_color="transparent")
        rtu_toolbar.pack(side="top", fill="x", padx=6, pady=4)
        ctk.CTkButton(rtu_toolbar, text="New RTU Session", command=self._new_rtu_session).pack(side="left", padx=2)
        ctk.CTkButton(rtu_toolbar, text="Close RTU Session", command=self._close_rtu_session, fg_color="red", hover_color="#8B0000").pack(side="left", padx=(6, 0))
        
        self.rtu_sessions_nb = ttk.Notebook(self.rtu_scanner_frame)
        self.rtu_sessions_nb.pack(expand=1, fill="both")
        self.rtu_sessions = []
        self._rtu_session_counter = 0
        self._last_rtu_snapshot = None

        self._new_rtu_session()

        # Network Diagnostics
        self.diagnostics_frame = DiagnosticsTab(self.notebook)
        self.notebook.add(self.diagnostics_frame, text="Network Diagnostics")

        try: self.notebook.select(self.simulation_frame)
        except: pass

        self.load_config()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _apply_app_icon(self, ico_filename: str, png_filename: str):
        ico_path = _resource_path(ico_filename)
        png_path = _resource_path(png_filename)
        system_png_path = "/usr/share/icons/hicolor/256x256/apps/gandalf-modbus-wizard.png"
        linux_opt_icon_paths = [
            "/opt/gandalf-modbus-wizard/_internal/gandalf-modbus-wizard-256.png",
            "/opt/gandalf-modbus-wizard/gandalf-modbus-wizard-256.png",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "gandalf-modbus-wizard-256.png"),
        ]
        try:
            if os.name == "nt" and os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except: pass
        try:
            # Prefer Tk's native PNG loader to avoid PIL dependency issues.
            icon_candidates = [png_path, system_png_path]
            if sys.platform.startswith("linux"):
                icon_candidates += linux_opt_icon_paths
            icon_path = next((p for p in icon_candidates if p and os.path.exists(p)), None)
            if icon_path:
                self._set_icon_photo(icon_path)
                return
        except Exception:
            pass
        try:
            from PIL import Image, ImageTk
            icon_candidates = [png_path, system_png_path, ico_path]
            icon_path = next((p for p in icon_candidates if p and os.path.exists(p)), None)
            if icon_path:
                img = Image.open(icon_path)
                try: img = img.convert("RGBA")
                except: pass
                photos = []
                for size in (16, 32, 48, 64, 128, 256):
                    try:
                        resized = img.resize((size, size))
                        photos.append(ImageTk.PhotoImage(resized))
                    except Exception:
                        pass
                if photos:
                    self._app_icon_photos = photos
                    try:
                        self.iconphoto(True, *photos)
                        self.tk.call("wm", "iconphoto", self._w, *photos)
                    except Exception:
                        pass
        except: pass

    def _ensure_linux_desktop_integration(self) -> None:
        if not sys.platform.startswith("linux"):
            return
        try:
            icon_src = _resource_path(self.ICON_PNG_FILENAME)
            if not os.path.exists(icon_src):
                return
            home = os.path.expanduser("~")
            icon_name = "gandalf-modbus-wizard.png"
            sizes = (16, 32, 48, 64, 128, 256)
            updated = False
            img = None
            try:
                from PIL import Image
                img = Image.open(icon_src).convert("RGBA")
            except Exception:
                img = None
            for size in sizes:
                icon_dir = os.path.join(home, ".local", "share", "icons", "hicolor", f"{size}x{size}", "apps")
                os.makedirs(icon_dir, exist_ok=True)
                icon_dst = os.path.join(icon_dir, icon_name)
                if os.path.exists(icon_dst):
                    continue
                try:
                    if img:
                        resized = img.resize((size, size))
                        resized.save(icon_dst)
                    else:
                        shutil.copyfile(icon_src, icon_dst)
                    updated = True
                except Exception:
                    pass

            desktop_dir = os.path.join(home, ".local", "share", "applications")
            os.makedirs(desktop_dir, exist_ok=True)
            desktop_path = os.path.join(desktop_dir, "gandalf-modbus-wizard.desktop")
            if not os.path.exists(desktop_path):
                exec_cmd = shutil.which("gandalf-modbus-wizard")
                if exec_cmd:
                    exec_line = exec_cmd
                else:
                    exec_line = f"python3 {os.path.abspath(__file__)}"
                desktop_entry = (
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=Gandalf Modbus Wizard\n"
                    f"Exec={exec_line}\n"
                    "Icon=gandalf-modbus-wizard\n"
                    "StartupWMClass=GandalfModbusWizard\n"
                    "Terminal=false\n"
                    "Categories=Utility;\n"
                )
                with open(desktop_path, "w", encoding="utf-8") as f:
                    f.write(desktop_entry)
                updated = True
            if updated:
                try:
                    if shutil.which("update-desktop-database"):
                        subprocess.run(
                            ["update-desktop-database", desktop_dir],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                except Exception:
                    pass
                try:
                    if shutil.which("gtk-update-icon-cache"):
                        icon_theme_dir = os.path.join(home, ".local", "share", "icons", "hicolor")
                        subprocess.run(
                            ["gtk-update-icon-cache", "-f", icon_theme_dir],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                except Exception:
                    pass
        except Exception:
            pass

    def _set_icon_photo(self, icon_path: str) -> None:
        try:
            base = tk.PhotoImage(file=icon_path)
            photos = [base]
            for factor in (2, 4, 8, 16):
                try:
                    photos.append(base.subsample(factor, factor))
                except Exception:
                    pass
            self._app_icon_photos = photos
            self.iconphoto(True, *photos)
            try:
                self.tk.call("wm", "iconphoto", self._w, *photos)
            except Exception:
                pass
        except Exception:
            pass

    def _apply_linux_icon_late(self) -> None:
        icon_paths = [
            _resource_path(self.ICON_PNG_FILENAME),
            "/opt/gandalf-modbus-wizard/_internal/gandalf-modbus-wizard-256.png",
            "/opt/gandalf-modbus-wizard/gandalf-modbus-wizard-256.png",
            "/usr/share/icons/hicolor/256x256/apps/gandalf-modbus-wizard.png",
            "/usr/share/pixmaps/gandalf-modbus-wizard.png",
            os.path.expanduser("~/.local/share/icons/hicolor/256x256/apps/gandalf-modbus-wizard.png"),
        ]
        xdg_dirs = os.getenv("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
        for base in xdg_dirs:
            icon_paths.extend(glob.glob(os.path.join(base, "icons", "hicolor", "*", "apps", "gandalf-modbus-wizard.png")))
        for path in icon_paths:
            if os.path.exists(path):
                self._set_icon_photo(path)
                break

    def _apply_ttk_theme(self):
        style = ttk.Style()
        # Keep tab text/padding explicit so OS theme changes do not shrink labels.
        tab_font = ("Segoe UI", 11, "bold")
        tab_padding = (12, 6)
        if self.dark_mode:
            style.theme_use('clam')
            style.configure("TNotebook", background="#2b2b2b", borderwidth=0)
            style.configure(
                "TNotebook.Tab",
                background="#2b2b2b",
                foreground="white",
                borderwidth=0,
                font=tab_font,
                padding=tab_padding,
            )
            style.map("TNotebook.Tab", background=[("selected", "#1f6aa5")], foreground=[("selected", "white")])
            style.configure("Treeview", background="#2b2b2b", fieldbackground="#2b2b2b", foreground="white")
            style.map("Treeview", background=[("selected", "#1f6aa5")], foreground=[("selected", "white")])
        else:
            style.theme_use('default')
            style.configure("TNotebook", background="#f0f0f0", borderwidth=0)
            style.configure(
                "TNotebook.Tab",
                background="#e0e0e0",
                foreground="black",
                borderwidth=0,
                font=tab_font,
                padding=tab_padding,
            )
            style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", "black")])
            style.configure("Treeview", background="white", fieldbackground="white", foreground="black")
            style.map("Treeview", background=[("selected", "#1f6aa5")], foreground=[("selected", "white")])

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        mode = "Dark" if self.dark_mode else "Light"
        ctk.set_appearance_mode(mode)
        self._apply_ttk_theme()

        # Force update on Simulation tab (if it has custom logic)
        if self.simulation:
            self.simulation.apply_theme(self.dark_mode)

        # DYNAMIC TREND UPDATE
        for session in self.tcp_sessions:
            scanner = session.get("scanner")
            if scanner and scanner.trend_popup and scanner.trend_popup.is_open:
                scanner.trend_popup.set_theme(self.dark_mode)
        for scanner in self.rtu_sessions:
            if scanner and scanner.trend_popup and scanner.trend_popup.is_open:
                scanner.trend_popup.set_theme(self.dark_mode)

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
        # USE CTkFrame
        tab = ctk.CTkFrame(self.tcp_sessions_nb, corner_radius=0)
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
        # USE CTkFrame
        tab = ctk.CTkFrame(self.rtu_sessions_nb, corner_radius=0)
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

    def load_config(self):
        config_path = "gandalf_config.json"
        if not os.path.exists(config_path): return

        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            if "geometry" in config:
                self.geometry(config["geometry"])
            
            desired_dark = bool(config.get("dark_mode", False))
            if desired_dark != self.dark_mode:
                self.toggle_theme()

            # 3. Restore TCP Settings (for the first tab)
            if "tcp_last" in config and self.tcp_sessions:
                try:
                    sc = self.tcp_sessions[0]["scanner"]
                    p = config["tcp_last"]
                    default_port = "1502" if sys.platform.startswith("linux") else "502"
                    saved_port = p.get("port")
                    saved_port_str = str(saved_port) if saved_port is not None else ""
                    saved_platform = config.get("platform")
                    if (not saved_platform) and saved_port_str in ("502", "1502"):
                        saved_port_str = default_port
                    if saved_platform and saved_platform != sys.platform and saved_port_str in ("502", "1502"):
                        saved_port_str = default_port
                    sc.host_entry.delete(0, tk.END); sc.host_entry.insert(0, p.get("host", "127.0.0.1"))
                    sc.port_entry.delete(0, tk.END); sc.port_entry.insert(0, saved_port_str or default_port)
                    sc.unit_var.set(p.get("unit", "1"))
                except: pass

            # 4. Restore RTU Settings (for the first tab)
            if "rtu_last" in config and self.rtu_sessions:
                try:
                    sc = self.rtu_sessions[0]
                    sc.import_ui_params(config["rtu_last"])
                except: pass

        except Exception as e:
            print(f"Failed to load config: {e}")

    def save_config(self):
        config = {}
        config["platform"] = sys.platform
        
        # 1. Window Geometry
        config["geometry"] = self.geometry()
        
        # 2. Dark Mode
        config["dark_mode"] = self.dark_mode

        # 3. TCP Snapshot (First Session)
        if self.tcp_sessions:
            try:
                sc = self.tcp_sessions[0]["scanner"]
                config["tcp_last"] = {
                    "host": sc.host_entry.get(),
                    "port": sc.port_entry.get(),
                    "unit": sc.unit_var.get()
                }
            except: pass

        # 4. RTU Snapshot (First Session)
        if self.rtu_sessions:
            try:
                sc = self.rtu_sessions[0]
                config["rtu_last"] = sc.export_ui_params()
            except: pass

        try:
            with open("gandalf_config.json", "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def on_closing(self):
        self.save_config()
        try:
            if self.simulation: self.simulation.stop_simulation()
        except: pass
        try:
            if self._rtu_shared: self._rtu_shared.disconnect()
        except: pass
        os._exit(0)

if __name__ == "__main__":
    _set_windows_app_user_model_id(GandalfModbusWizard.APP_ID)
    app = GandalfModbusWizard()
    app.mainloop()
