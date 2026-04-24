import os
import logging
from logging.handlers import RotatingFileHandler
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import customtkinter as ctk
from threading import Thread, Event
from queue import SimpleQueue
import minimalmodbus
import serial
import serial.tools.list_ports
import time
import glob
import sys
from statistics import pstdev

# --- logging (Updated to use AppData to fix Permission Error) ---
app_name = "Gandalf Modbus Wizard"
# Use LOCALAPPDATA on Windows, otherwise fall back to XDG or ~/.local/share
local_appdata = os.getenv('LOCALAPPDATA')
xdg_data_home = os.getenv('XDG_DATA_HOME')
if local_appdata:
    user_data_dir = os.path.join(local_appdata, app_name)
elif xdg_data_home:
    user_data_dir = os.path.join(xdg_data_home, app_name)
else:
    user_data_dir = os.path.join(os.path.expanduser("~/.local/share"), app_name)

# Create the directory if it doesn't exist
if not os.path.exists(user_data_dir):
    try:
        os.makedirs(user_data_dir)
    except OSError:
        # If we can't create the folder, we will fallback later
        user_data_dir = None

# Set the log file path
if user_data_dir:
    log_file = os.path.join(user_data_dir, "modbus_scan.log")
else:
    # Fallback to current directory if AppData fails (unlikely)
    log_file = "modbus_scan.log"

# Configure logging
try:
    handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
    logging.basicConfig(
        handlers=[handler],
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
except Exception as e:
    # If file logging fails entirely, just log to console to prevent crash
    logging.basicConfig(level=logging.DEBUG)
    print(f"File logging failed: {e}")

log = logging.getLogger()

# --- defaults ---
default_baudrates = [9600, 115200, 19200, 38400, 57600]
default_parities  = ['N', 'E', 'O']
default_databits  = [8]
default_stopbits  = [1, 1.5, 2]
MODBUS_POINT_TYPES = {
    '03: Holding Registers': '03',
    '04: Input Registers': '04'
}

# verification & scoring knobs
CONFIRM_READS = 2                  # identical reads per block (Reduced from 3 for speed)
SECOND_BLOCK_OFFSET = 8            # second block start = first + this (if possible)
EARLY_TUPLE_FAILS = 15             # contiguous ID failures to skip a serial tuple (Increased for safety)
PARITY_TIE_PREFERENCE = ['N','E','O']  # prefer N > E > O on exact score ties
SCORE_DEVICE_ID_BONUS_11 = 100.0   # bonus if FC 0x11 (Report Slave ID) parses
SCORE_DEVICE_ID_BONUS_2B = 140.0   # bonus if 0x2B/0x0E (MEI) parses

# one global Instrument reused per file
instrument = None


class AutoDetectionWizard:
    """
    RTU autodetector with:
      - Quick Sample Mode (fast reject of bad tuples)
      - Device-ID probe (FC 0x11 and 0x2B/0x0E) for high-confidence tuple selection
      - Multi-block, multi-repeat verification and stability scoring
      - Early-abort for hopeless tuples; stable ETA; timer stop

    transfer_callback: a callable that receives a dict:
      {
        'port': 'COM3',
        'device_id': 1,
        'baudrate': 115200,
        'parity': 'E',
        'databits': 8,
        'stopbits': 2.0,
        'point_type': '03: Holding Registers'
      }
    """
    def __init__(self, frame, transfer_callback, port_in_use_callback=None):
        self.frame = frame
        self.transfer_callback = transfer_callback

        self.port_in_use_callback = port_in_use_callback
        self.stop_event = Event()
        self.connection_params = None
        self.start_time = 0
        self._last_ui_update = 0
        self._ui_queue = SimpleQueue()
        self.frame.after(100, self._drain_ui_queue)

        # run-state for timers/ETA
        self.scanning = False
        self.total_trials = 0
        self.done_trials = 0

        self.create_widgets()

    # ---------------- UI ----------------
    def create_widgets(self):
        # Use CTkFrame for better dark mode support
        self.top_frame_wizard = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.top_frame_wizard.grid(row=0, column=0, columnspan=6, sticky='nw')

        ctk.CTkLabel(self.top_frame_wizard, text="COM Port:").grid(row=0, column=0, sticky='w', padx=2)
        self.port_var_wizard = tk.StringVar()
        self.port_menu_wizard = ctk.CTkOptionMenu(self.top_frame_wizard, variable=self.port_var_wizard, values=["Select COM Port"], width=200)
        self.port_menu_wizard.grid(row=0, column=1, columnspan=5, sticky='w', padx=2, pady=2)
        # Add refresh button next to it? 
        ctk.CTkButton(self.top_frame_wizard, text="Refresh", width=80, command=self.refresh_ports).grid(row=0, column=5, sticky='w', padx=2)

        ctk.CTkLabel(self.top_frame_wizard, text="Start Device ID:").grid(row=1, column=0, sticky='w', padx=2)
        self.start_id_entry = ctk.CTkEntry(self.top_frame_wizard, width=60); self.start_id_entry.grid(row=1, column=1, sticky='w', padx=2, pady=2)

        ctk.CTkLabel(self.top_frame_wizard, text="End Device ID:").grid(row=1, column=2, sticky='w', padx=2)
        self.end_id_entry = ctk.CTkEntry(self.top_frame_wizard, width=60); self.end_id_entry.grid(row=1, column=3, sticky='w', padx=2, pady=2)

        # Quick Sample Mode
        self.quick_sample_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.top_frame_wizard, text="Quick Sample Mode", variable=self.quick_sample_var).grid(row=1, column=4, sticky='w', padx=2)
        ctk.CTkLabel(self.top_frame_wizard, text="Sample Size:").grid(row=1, column=5, sticky='e', padx=2)
        self.sample_size_var = tk.IntVar(value=3)
        # CTk doesn't have Spinbox. Use Entry.
        self.sample_size_spin = ctk.CTkEntry(self.top_frame_wizard, width=40, textvariable=self.sample_size_var)
        self.sample_size_spin.grid(row=1, column=6, sticky='w', padx=2)

        # Baud / Parity / Data / Stop
        ctk.CTkLabel(self.top_frame_wizard, text="Baudrates:").grid(row=2, column=0, sticky='w', padx=2)
        self.baudrate_vars = {str(b): tk.BooleanVar(value=True) for b in default_baudrates}
        for i, (b, var) in enumerate(self.baudrate_vars.items()):
            ctk.CTkCheckBox(self.top_frame_wizard, text=b, variable=var, width=70).grid(row=2, column=1+i, sticky='w', padx=2)

        self.custom_baudrate_var = tk.BooleanVar()
        ctk.CTkCheckBox(self.top_frame_wizard, text="Custom", variable=self.custom_baudrate_var,
                       command=self.toggle_custom_baudrate, width=70).grid(row=2, column=1+len(self.baudrate_vars), sticky='w', padx=2)
        self.custom_baudrate_entry = ctk.CTkEntry(self.top_frame_wizard, state="disabled", width=80)
        self.custom_baudrate_entry.grid(row=2, column=2+len(self.baudrate_vars), sticky='w', padx=2)

        ctk.CTkLabel(self.top_frame_wizard, text="Parities:").grid(row=3, column=0, sticky='w', padx=2)
        self.parity_vars = {p: tk.BooleanVar(value=True) for p in default_parities}
        for i, (p, var) in enumerate(self.parity_vars.items()):
            ctk.CTkCheckBox(self.top_frame_wizard, text=p, variable=var, width=50).grid(row=3, column=1+i, sticky='w', padx=2)

        self.custom_parity_var = tk.BooleanVar()
        ctk.CTkCheckBox(self.top_frame_wizard, text="Custom", variable=self.custom_parity_var,
                       command=self.toggle_custom_parity, width=70).grid(row=3, column=1+len(self.parity_vars), sticky='w', padx=2)
        self.custom_parity_entry = ctk.CTkEntry(self.top_frame_wizard, state="disabled", width=40)
        self.custom_parity_entry.grid(row=3, column=2+len(self.parity_vars), sticky='w', padx=2)

        ctk.CTkLabel(self.top_frame_wizard, text="Databits:").grid(row=4, column=0, sticky='w', padx=2)
        self.databits_vars = {str(d): tk.BooleanVar(value=True) for d in default_databits}
        for i, (d, var) in enumerate(self.databits_vars.items()):
            ctk.CTkCheckBox(self.top_frame_wizard, text=d, variable=var, width=50).grid(row=4, column=1+i, sticky='w', padx=2)

        ctk.CTkLabel(self.top_frame_wizard, text="Stopbits:").grid(row=4, column=3, sticky='e', padx=2)
        self.stopbits_vars = {str(s): tk.BooleanVar(value=True) for s in default_stopbits}
        for i, (s, var) in enumerate(self.stopbits_vars.items()):
            ctk.CTkCheckBox(self.top_frame_wizard, text=s, variable=var, width=50).grid(row=4, column=4+i, sticky='w', padx=2)

        ctk.CTkLabel(self.top_frame_wizard, text="Register Type:").grid(row=5, column=0, sticky='w', padx=2)
        self.point_type_var = tk.StringVar(value="03: Holding Registers")
        self.point_type_menu = ctk.CTkOptionMenu(self.top_frame_wizard, variable=self.point_type_var, values=list(MODBUS_POINT_TYPES.keys()))
        self.point_type_menu.grid(row=5, column=1, sticky='w', padx=2, pady=2)

        ctk.CTkLabel(self.top_frame_wizard, text="Register Read Range:").grid(row=5, column=2, sticky='e', padx=2)
        self.register_start_entry = ctk.CTkEntry(self.top_frame_wizard, width=60); self.register_start_entry.grid(row=5, column=3, sticky='w', padx=2); self.register_start_entry.insert(0, '0')
        self.register_end_entry   = ctk.CTkEntry(self.top_frame_wizard, width=60); self.register_end_entry.grid(row=5, column=4, sticky='w', padx=2); self.register_end_entry.insert(0, '1')

        # buttons
        self.start_detection_button = ctk.CTkButton(self.top_frame_wizard, text="Start Detection", command=self.start_detection, fg_color='green', text_color='white', width=140)
        self.stop_detection_button  = ctk.CTkButton(self.top_frame_wizard, text="Stop Detection",  command=self.stop_detection,  fg_color='red',   text_color='white', width=140, hover_color="#8B0000")
        self.clear_results_button   = ctk.CTkButton(self.top_frame_wizard, text="Clear Results",  command=self.clear_results_wizard, fg_color="blue", text_color="white", width=140)
        self.download_log_button    = ctk.CTkButton(self.top_frame_wizard, text="Download Log",   command=self.download_log, fg_color='#1f6aa5', text_color='white', width=140)

        self.start_detection_button.grid(row=6, column=0, columnspan=2, sticky='w', padx=2, pady=5)
        self.stop_detection_button.grid(row=6, column=2, columnspan=2, sticky='w', padx=2, pady=5)
        self.clear_results_button.grid(row=6, column=4, columnspan=1, sticky='w', padx=2, pady=5)
        self.download_log_button.grid(row=6, column=5, columnspan=2, sticky='w', padx=(8,0), pady=5)

        self.progress_label = ctk.CTkLabel(self.top_frame_wizard, text="Progress: Not Started")
        self.progress_label.grid(row=7, column=0, columnspan=6, sticky='w', padx=2)
        self.settings_label = ctk.CTkLabel(self.top_frame_wizard, text="Current Settings: N/A")
        self.settings_label.grid(row=8, column=0, columnspan=6, sticky='w', padx=2)

        self.progress_bar = ctk.CTkProgressBar(self.top_frame_wizard, orientation="horizontal", width=420, mode="determinate")
        self.progress_bar.grid(row=9, column=0, columnspan=6, sticky='w', padx=2, pady=5)
        self.progress_bar.set(0)

        self.elapsed_time_label = ctk.CTkLabel(self.top_frame_wizard, text="Elapsed Time: 00:00:00, Estimated Time Remaining: 00:00:00")
        self.elapsed_time_label.grid(row=10, column=0, columnspan=6, sticky='w', padx=2)

        # Initialize ports immediately
        self.refresh_ports()

    def _enqueue_ui(self, fn):
        self._ui_queue.put(fn)

    def _drain_ui_queue(self):
        while True:
            try:
                fn = self._ui_queue.get_nowait()
            except Exception:
                break
            try:
                fn()
            except Exception:
                pass
        self.frame.after(100, self._drain_ui_queue)

    def _ui_messagebox(self, kind, title, message):
        def _show():
            if kind == "warning":
                messagebox.showwarning(title, message)
            elif kind == "info":
                messagebox.showinfo(title, message)
            else:
                messagebox.showerror(title, message)
        self._enqueue_ui(_show)

    # -------------- helpers --------------
    def refresh_ports(self, _=None):
        ports = [p.device + " - " + p.description for p in serial.tools.list_ports.comports(include_links=True)]
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
            # Fallback: manually check for common serial devices
            manual_ports = []
            if is_wsl:
                patterns = ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/serial/by-id/*")
            else:
                patterns = ("/dev/ttyUSB*", "/dev/ttyACM*", "/dev/ttyS*", "/dev/ttyAMA*", "/dev/ttySC*", "/dev/serial/by-id/*")
            for pattern in patterns:
                manual_ports.extend(glob.glob(pattern))
            manual_ports = sorted(set(manual_ports))
            if manual_ports:
                ports = []
                for p in manual_ports:
                    if os.access(p, os.R_OK | os.W_OK):
                        ports.append(p + " - Manual Detect")
                    else:
                        ports.append(p + " - No permission")

        if not ports:
            if os.name == "nt":
                ports = ["No serial ports detected"]
            else:
                if is_wsl:
                    ports = ["No serial ports detected in WSL (use Windows app or attach USB serial to WSL)"]
                else:
                    ports = ["No serial ports detected (check /dev/ttyUSB* or /dev/ttyACM*)"]
        self.port_menu_wizard.configure(values=ports)
        self.port_var_wizard.set(ports[0])

    def toggle_custom_parity(self):
        self.custom_parity_entry.configure(state="normal" if self.custom_parity_var.get() else "disabled")

    def toggle_custom_baudrate(self):
        self.custom_baudrate_entry.configure(state="normal" if self.custom_baudrate_var.get() else "disabled")

    def download_log(self):
        path = filedialog.asksaveasfilename(defaultextension=".log",
                                            filetypes=[("Log files", "*.log"), ("All files", "*.*")])
        if path:
            try:
                with open(log_file, 'r') as src, open(path, 'w') as dst:
                    dst.write(src.read())
                messagebox.showinfo("Log Downloaded", f"Log file saved to {path}")
            except Exception as e:
                 messagebox.showerror("Error", f"Could not save log file: {e}")

    # ---------- serial constants / finalize ----------
    def _serial_consts(self, databits, stopbits, parity):
        """Map numeric settings to pySerial constants to ensure the driver really applies them."""
        S = minimalmodbus.serial
        bytesize = S.EIGHTBITS  # Modbus RTU is 8-bit; 7-bit is Modbus ASCII
        stopbits = {1.0: S.STOPBITS_ONE, 2.0: S.STOPBITS_TWO, 1.5: S.STOPBITS_ONE_POINT_FIVE}[float(stopbits)]
        parity   = {'N': S.PARITY_NONE, 'E': S.PARITY_EVEN, 'O': S.PARITY_ODD}[parity]
        return bytesize, stopbits, parity

    def _finalize_scan(self, ok: bool):
        """Stop timers, freeze ETA, and re-enable UI after a run."""
        self.scanning = False
        self.stop_event.set()
        elapsed = time.time() - self.start_time
        def _apply():
            self.elapsed_time_label.configure(
                text=f"Elapsed Time: {self.format_time(elapsed)}, Estimated Time Remaining: 00:00:00"
            )
            self.start_detection_button.configure(state=tk.NORMAL)
        self._enqueue_ui(_apply)

    # -------------- lifecycle --------------
    def start_detection(self):
        if not self.port_var_wizard.get() or not self.start_id_entry.get() or not self.end_id_entry.get():
            messagebox.showwarning("Input Error", "Please select a port and enter start and end device IDs before starting detection.")
            return
        if self.port_var_wizard.get().startswith("/dev/ttyS"):
            messagebox.showwarning("Serial Port", "WSL pseudo-serial ports (/dev/ttyS*) are not usable for Modbus. Use a USB serial device attached to WSL.")
            return
        self.stop_event.clear()
        self.scanning = True
        the_port = self.port_var_wizard.get()

        # Prevent running detection on a COM port already in use by the RTU scanner
        try:
            if callable(self.port_in_use_callback):
                p = the_port.split(' - ')[0].strip()
                if p and self.port_in_use_callback(p):
                    messagebox.showwarning("Auto Detect", f"{p} is already in use. Disconnect RTU first.")
                    return
        except Exception:
            pass

        if not the_port or the_port.startswith("No serial ports detected") or the_port == "Select COM Port":
            self.refresh_ports()
        self.start_time = time.time()
        self.done_trials = 0
        self.total_trials = 0
        self.start_detection_button.configure(state=tk.DISABLED)
        self.update_elapsed_time()  # start timer
        Thread(target=self.auto_detect_modbus, daemon=True).start()

    def stop_detection(self):
        self.stop_event.set()
        if self.scanning:
            self._finalize_scan(False)
            self.disconnect_modbus()

    def clear_results_wizard(self):
        self.progress_label.configure(text="Progress: Not Started")
        self.settings_label.configure(text="Current Settings: N/A")
        self.progress_bar.set(0)
        self.elapsed_time_label.configure(text="Elapsed Time: 00:00:00, Estimated Time Remaining: 00:00:00")

    # -------------- fast scanner --------------
    def auto_detect_modbus(self):
        port_choice = self.port_var_wizard.get()
        port = port_choice.split(' - ')[0]
        if "No permission" in port_choice:
            self._ui_messagebox("error", "Serial Port", f"Permission denied for {port}. Add your user to the 'dialout' group or run with elevated permissions.")
            self._finalize_scan(False)
            return
        try:
            start_id  = int(self.start_id_entry.get())
            end_id    = int(self.end_id_entry.get())
            reg_start = int(self.register_start_entry.get())
            reg_end   = int(self.register_end_entry.get())
        except ValueError:
            self._ui_messagebox("error", "Input Error", "Invalid device ID(s) or register range. Please enter valid numbers.")
            self._finalize_scan(False)
            return

        # Collect choices
        sel_baud = [int(b) for b, var in self.baudrate_vars.items() if var.get()]
        if self.custom_baudrate_var.get():
            try: sel_baud.append(int(self.custom_baudrate_entry.get()))
            except: pass

        sel_par  = [p for p, var in self.parity_vars.items() if var.get()]
        if self.custom_parity_var.get():
            v = self.custom_parity_entry.get().strip().upper()
            if v in {'N','E','O'}: sel_par.append(v)

        sel_data = [int(d) for d, var in self.databits_vars.items() if var.get()]
        sel_stop = [float(s) for s, var in self.stopbits_vars.items() if var.get()]

        # Prioritize common combos; try 8E2/8N2 early for your devices
        def prioritized(seq, pref):
            return sorted(seq, key=lambda x: (pref.index(x) if x in pref else 99, seq.index(x)))
        sel_baud = prioritized(sel_baud, [9600, 19200, 38400, 57600, 115200])
        sel_par  = prioritized(sel_par,  ['E','N','O'])
        sel_data = prioritized(sel_data, [8,7])
        sel_stop = prioritized(sel_stop, [2,1,1.5])

        ids = list(range(start_id, end_id + 1))
        self.total_trials = len(sel_baud)*len(sel_par)*len(sel_data)*len(sel_stop)*len(ids)

        # Sampling set
        quick_sample = self.quick_sample_var.get()
        sample_size  = max(3, int(self.sample_size_var.get()))
        sample_ids   = self._build_sample_ids(ids, sample_size) if quick_sample else ids
        needs_full_retry = quick_sample and len(sample_ids) < len(ids)

        global instrument
        try:
            instrument = minimalmodbus.Instrument(port, 1)  # temp address, changed per ID
        except (serial.SerialException, PermissionError) as e:
            self._ui_messagebox("error", "Serial Port", f"Could not open {port}: {e}")
            self._finalize_scan(False)
            return
        instrument.close_port_after_each_call = False
        instrument.clear_buffers_before_each_transaction = True

        last_serial_tuple = None
        best = None  # (score, info_dict)

        try:
            scan_passes = 2 if needs_full_retry else 1
            for pass_idx in range(scan_passes):
                sample_mode = quick_sample if pass_idx == 0 else False
                id_list = sample_ids if sample_mode else ids
                if pass_idx == 1:
                    log.info("Quick sample found no hits; retrying full ID sweep.")
                    self.done_trials = 0
                    self._last_ui_update = 0
                    def _reset_progress():
                        self.progress_bar.set(0)
                        self.progress_label.configure(text="Progress: 0%")
                        self.settings_label.configure(text="Quick sample found no hits. Retrying full ID sweep...")
                    self._enqueue_ui(_reset_progress)
                last_serial_tuple = None

                for baud in sel_baud:
                    for parity in sel_par:
                        for databits in sel_data:
                            for stopbits in sel_stop:
                                if self.stop_event.is_set():
                                    log.info("Scan stopped by user.")
                                    self._ui_messagebox("info", "Scan Stopped", "Modbus scan was stopped by the user.")
                                    self._finalize_scan(False)
                                    return

                                ser_tuple = (baud, parity, databits, stopbits)
                                if ser_tuple != last_serial_tuple:
                                    try:
                                        if instrument.serial.is_open:
                                            instrument.serial.close()
                                    except Exception:
                                        pass
                                    bs, sb, pr = self._serial_consts(databits, stopbits, parity)
                                    instrument.serial.baudrate = baud
                                    instrument.serial.timeout  = 0.15  # small; adaptive inside
                                    instrument.serial.bytesize = bs
                                    instrument.serial.stopbits = sb
                                    instrument.serial.parity   = pr
                                    try:
                                        instrument.serial.open()
                                        # ARDUINO FIX: Opening port resets the board (DTR). 
                                        # Wait for bootloader (approx 1.5-2.0s)
                                        time.sleep(2.0) 
                                    except Exception as e:
                                        log.debug(f"Open failed for {ser_tuple}: {e}")
                                        last_serial_tuple = None
                                        continue
                                    try:
                                        instrument.serial.reset_input_buffer()
                                        instrument.serial.reset_output_buffer()
                                    except Exception:
                                        pass
                                    last_serial_tuple = ser_tuple

                                contig_fail = 0
                                tuple_hit = False

                                for device_id in id_list:
                                    if self.stop_event.is_set():
                                        self._finalize_scan(False)
                                        return

                                    self.done_trials += 1
                                    self._update_progress(device_id, baud, parity, databits, stopbits)

                                    instrument.address = device_id

                                    ok, score, sample = self._verify_candidate(
                                        instrument,
                                        MODBUS_POINT_TYPES[self.point_type_var.get()],
                                        reg_start, reg_end
                                    )

                                    if ok:
                                        tuple_hit = True
                                        # Device-ID probe bonus
                                        bonus = 0.0
                                        try:
                                            # Try FC 0x2B/0x0E first (modern)
                                            ok2b, _ = self._probe_device_id_mei(instrument)
                                            if ok2b:
                                                bonus += SCORE_DEVICE_ID_BONUS_2B
                                            else:
                                                # Fall back to FC 0x11 if 2B not supported
                                                ok11, _ = self._probe_device_id_report_slave_id(instrument)
                                                if ok11:
                                                    bonus += SCORE_DEVICE_ID_BONUS_11
                                        except Exception as e:
                                            log.debug(f"Device-ID probe error: {e}")

                                        final_score = score + bonus
                                        info = {
                                            'port': port, 'device_id': device_id, 'baudrate': baud,
                                            'parity': parity, 'databits': databits, 'stopbits': stopbits,
                                            'score': final_score, 'sample': sample
                                        }
                                        if (best is None) or (final_score > best[0]) or \
                                           (final_score == best[0] and PARITY_TIE_PREFERENCE.index(parity) < \
                                            PARITY_TIE_PREFERENCE.index(best[1]['parity'])):
                                            best = (final_score, info)
                                        contig_fail = 0
                                        break
                                    else:
                                        contig_fail += 1
                                        if contig_fail >= min(EARLY_TUPLE_FAILS, len(id_list)):
                                            log.debug(f"Early-abort tuple {ser_tuple} after {contig_fail} contiguous fails")
                                            break

                                # If sampling mode and this tuple had any hit, do a full sweep for this tuple only
                                if sample_mode and tuple_hit:
                                    for device_id in ids:
                                        if self.stop_event.is_set():
                                            self._finalize_scan(False)
                                            return
                                        self.done_trials += 1
                                        self._update_progress(device_id, baud, parity, databits, stopbits)
                                        instrument.address = device_id
                                        ok, score, sample = self._verify_candidate(
                                            instrument,
                                            MODBUS_POINT_TYPES[self.point_type_var.get()],
                                            reg_start, reg_end
                                        )
                                        if ok:
                                            bonus = 0.0
                                            try:
                                                ok2b, _ = self._probe_device_id_mei(instrument)
                                                if ok2b:
                                                    bonus += SCORE_DEVICE_ID_BONUS_2B
                                                else:
                                                    ok11, _ = self._probe_device_id_report_slave_id(instrument)
                                                    if ok11:
                                                        bonus += SCORE_DEVICE_ID_BONUS_11
                                            except Exception as e:
                                                log.debug(f"Device-ID probe error: {e}")
                                            final_score = score + bonus
                                            info = {
                                                'port': port, 'device_id': device_id, 'baudrate': baud,
                                                'parity': parity, 'databits': databits, 'stopbits': stopbits,
                                                'score': final_score, 'sample': sample
                                            }
                                            if (best is None) or (final_score > best[0]) or \
                                               (final_score == best[0] and PARITY_TIE_PREFERENCE.index(parity) < \
                                                PARITY_TIE_PREFERENCE.index(best[1]['parity'])):
                                                best = (final_score, info)
                                            break

                                if best: break
                            if best: break
                        if best: break
                    if best: break

                if best or not sample_mode:
                    break

        finally:
            try:
                if instrument and instrument.serial.is_open:
                    instrument.serial.close()
            except Exception:
                pass

        # Choose best candidate
        if best:
            chosen = best[1]
            elapsed = time.time() - self.start_time

            params = {
                'port': chosen['port'],
                'device_id': int(chosen['device_id']),
                'baudrate': int(chosen['baudrate']),
                'parity': str(chosen['parity']).upper(),
                'databits': int(chosen['databits']),
                'stopbits': float(chosen['stopbits']),
                'point_type': self.point_type_var.get(),
            }

            self.disconnect_modbus()

            # Hand off to the RTU Scanner on the UI thread, then show success dialog
            def _handoff():
                try:
                    if callable(self.transfer_callback):
                        self.transfer_callback(params)
                except Exception as e:
                    log.error(f"Transfer callback failed: {e}")
                messagebox.showinfo(
                    "Connection Success",
                    (f"Connected to {params['port']}\n"
                     f"ID={params['device_id']}, {params['baudrate']} "
                     f"{params['parity']} {params['databits']}{int(params['stopbits'])}\n"
                     f"Stability Score: {chosen['score']:.2f}\n"
                     f"Total Scan Time: {self.format_time(elapsed)}")
                )

            self.frame.after(0, _handoff)
            self._finalize_scan(True)
            return

        # No candidate
        self.progress_bar.set(1.0) # CTkProgressBar uses 0.0 to 1.0
        self._enqueue_ui(lambda: self.progress_label.configure(text="Progress: 100%"))
        self._finalize_scan(False)
        self._ui_messagebox("error", "Connection Error", "Failed to connect to any device with the tested settings.")

    # ----- tuple sampling helper -----
    def _build_sample_ids(self, ids, n):
        if len(ids) <= n:
            return ids[:]
        # pick start, end, and evenly spaced mids
        idxs = [0, len(ids)-1]
        if n > 2:
            step = (len(ids)-1) / (n-1)
            idxs = [round(i*step) for i in range(n)]
        dedup = sorted(set(max(0, min(len(ids)-1, i)) for i in idxs))
        return [ids[i] for i in dedup]

    # ----- tuple scoring helpers -----
    def _score_specific_tuple(self, port, device_id, baud, parity, databits, stopbits,
                              point_type, reg_start, reg_end):
        """Re-run verification for one specific tuple, return info dict or None."""
        global instrument
        try:
            instrument = minimalmodbus.Instrument(port, device_id)
            instrument.close_port_after_each_call = False
            instrument.clear_buffers_before_each_transaction = True

            bs, sb, pr = self._serial_consts(databits, stopbits, parity)
            instrument.serial.baudrate = baud
            instrument.serial.timeout  = 0.15
            instrument.serial.bytesize = bs
            instrument.serial.stopbits = sb
            instrument.serial.parity   = pr

            instrument.serial.open()
            ok, score, sample = self._verify_candidate(instrument, point_type, reg_start, reg_end)
            # device-id bonus pass
            if ok:
                try:
                    ok2b, _ = self._probe_device_id_mei(instrument)
                    if ok2b:
                        score += SCORE_DEVICE_ID_BONUS_2B
                    else:
                        ok11, _ = self._probe_device_id_report_slave_id(instrument)
                        if ok11:
                            score += SCORE_DEVICE_ID_BONUS_11
                except Exception as e:
                    log.debug(f"Device-ID cross-check error: {e}")
            instrument.serial.close()
            if ok:
                return {
                    'port': port, 'device_id': device_id, 'baudrate': baud,
                    'parity': parity, 'databits': databits, 'stopbits': stopbits,
                    'score': score, 'sample': sample
                }
        except Exception as e:
            log.debug(f"Cross-check open failed ({baud}/{parity}/{databits}/{stopbits}): {e}")
        finally:
            try:
                if instrument and instrument.serial.is_open:
                    instrument.serial.close()
            except Exception:
                pass
        return None

    def _verify_candidate(self, inst, point_type, start, end):
        """
        Strong verification:
        - Read two blocks (A and B) at different addresses
        - Each block must read identically CONFIRM_READS times
        - Score = success + non-trivial data + low jitter
        """
        count = max(1, end - start + 1)
        a_start = start
        b_start = max(0, start + SECOND_BLOCK_OFFSET)
        if b_start == a_start:
            b_start = a_start + 1

        # cap each block to ~10 regs for speed
        a_count = min(count, 10)
        b_count = min(count, 10)

        timings = []
        try:
            a_ok, a_vals = self._stable_block(inst, point_type, a_start, a_count, timings)
            if not a_ok:
                return False, 0.0, None
            b_ok, b_vals = self._stable_block(inst, point_type, b_start, b_count, timings)
            if not b_ok:
                return False, 0.0, None

            all_vals = a_vals + b_vals
            nonzero = any(v not in (0, 0xFFFF) for v in all_vals)  # simple entropy guard
            jitter = pstdev(timings) if len(timings) > 1 else 0.0

            success_ratio = 1.0  # both blocks passed with repeats
            score = success_ratio * 100.0 - (jitter * 10.0) + (10.0 if nonzero else 0.0)
            return True, score, {'A': a_vals, 'B': b_vals}
        except Exception as e:
            log.debug(f"verify_candidate exception: {e}")
            return False, 0.0, None

    def _stable_block(self, inst, point_type, start, count, timings):
        """
        Read [start..start+count-1] CONFIRM_READS times.
        All reads must succeed and be identical. Return (ok, values).
        """
        last = None
        for to in (0.15, 0.8):
            inst.serial.timeout = to
            reads = []
            ok = True
            for _ in range(CONFIRM_READS):
                t0 = time.time()
                try:
                    inst.serial.reset_input_buffer()
                    inst.serial.reset_output_buffer()
                except Exception:
                    pass
                try:
                    if point_type == '03':
                        vals = inst.read_registers(start, count, functioncode=3)
                    else:
                        vals = inst.read_registers(start, count, functioncode=4)
                except Exception as e:
                    ok = False
                    log.debug(f"Block read fail (timeout={to}): {e}")
                    break
                timings.append(time.time() - t0)
                reads.append(vals)
            if ok and all(r == reads[0] for r in reads):
                last = reads[0]
                break
        return (last is not None), (last if last is not None else [])

    # -------- Device-ID probes (minimalmodbus 2.5.3) --------
    def _probe_device_id_report_slave_id(self, inst):
        """FC 0x11 Report Slave ID: light structural sanity checks only."""
        try:
            payload = inst._perform_command(0x11, b"")
            if not payload or len(payload) < 2:
                return False, None
            bytecount = payload[0]
            if bytecount != len(payload) - 1:
                return False, None
            return True, payload
        except Exception as e:
            log.debug(f"FC0x11 probe failed: {e}")
            return False, None

    def _probe_device_id_mei(self, inst):
        """FC 0x2B/0x0E Read Device Identification (Basic)."""
        try:
            req = bytes([0x0E, 0x01, 0x00])  # MEI=0x0E, Basic=0x01, ObjectID=0x00
            payload = inst._perform_command(0x2B, req)
            if not payload or payload[0] != 0x0E:
                return False, None
            if len(payload) < 5:
                return False, None
            return True, payload
        except Exception as e:
            log.debug(f"MEI 0x0E probe failed: {e}")
            return False, None

    # Throttled progress + stable ETA
    def _update_progress(self, device_id, baud, parity, databits, stopbits):
        now = time.time()
        if now - self._last_ui_update < 0.1:
            return
        self._last_ui_update = now

        # CTkProgressBar is 0.0-1.0
        pct = (self.done_trials / max(1, self.total_trials)) 
        progress_text = f"Progress: {pct*100.0:.1f}%"
        settings_text = (
            f"Testing ID={device_id}, {baud} {parity} {databits}/{stopbits} "
            f"({self.done_trials}/{self.total_trials})"
        )

        elapsed = time.time() - self.start_time
        remaining_steps = max(0, self.total_trials - self.done_trials)
        avg_per_step = (elapsed / self.done_trials) if self.done_trials else 0
        eta = avg_per_step * remaining_steps
        elapsed_text = (
            f"Elapsed Time: {self.format_time(elapsed)}, "
            f"Estimated Time Remaining: {self.format_time(eta)}"
        )

        def _apply():
            self.progress_bar.set(pct)
            self.progress_label.configure(text=progress_text)
            self.settings_label.configure(text=settings_text)
            self.elapsed_time_label.configure(text=elapsed_text)
            self.frame.update_idletasks()

        self._enqueue_ui(_apply)

    # -------------- teardown --------------
    def disconnect_modbus(self):
        global instrument
        try:
            if instrument and instrument.serial and instrument.serial.is_open:
                instrument.serial.close()
            log.info("Disconnected from Modbus")
        except Exception as e:
            log.error(f"Error disconnecting from Modbus: {e}")
        finally:
            instrument = None

    # -------------- timers/formatters --------------
    def update_elapsed_time(self):
        if not self.scanning or self.stop_event.is_set():
            return
        elapsed = time.time() - self.start_time
        # CTkLabel uses cget("text") works, but sometimes .configure is preferred. 
        # But 'cget' exists on CTkBaseClass. 
        # Let's trust it, but wrap in try/except for text manipulation
        try:
            current = self.elapsed_time_label.cget("text")
            tail = current.split(", Estimated Time Remaining: ")[1]
            self.elapsed_time_label.configure(
                text=f"Elapsed Time: {self.format_time(elapsed)}, Estimated Time Remaining: {tail}"
            )
        except Exception:
            self.elapsed_time_label.configure(
                text=f"Elapsed Time: {self.format_time(elapsed)}, Estimated Time Remaining: 00:00:00"
            )
        self.frame.after(1000, self.update_elapsed_time)

    @staticmethod
    def format_time(seconds):
        hrs, secs = divmod(int(seconds), 3600)
        mins, secs = divmod(secs, 60)
        return f"{hrs:02}:{mins:02}:{secs:02}"
