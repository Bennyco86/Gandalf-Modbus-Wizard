import os
import logging
from logging.handlers import RotatingFileHandler
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
from threading import Thread, Event
import minimalmodbus
import serial.tools.list_ports
import time
from statistics import pstdev

# --- logging (Updated to use AppData to fix Permission Error) ---
app_name = "Gandalf Modbus Wizard"
# Use LOCALAPPDATA (e.g., C:\Users\Name\AppData\Local)
user_data_dir = os.path.join(os.getenv('LOCALAPPDATA'), app_name)

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
CONFIRM_READS = 3                  # identical reads per block
SECOND_BLOCK_OFFSET = 8            # second block start = first + this (if possible)
EARLY_TUPLE_FAILS = 8              # contiguous ID failures to skip a serial tuple
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

        # run-state for timers/ETA
        self.scanning = False
        self.total_trials = 0
        self.done_trials = 0

        self.create_widgets()

    # ---------------- UI ----------------
    def create_widgets(self):
        self.top_frame_wizard = tk.Frame(self.frame)
        self.top_frame_wizard.grid(row=0, column=0, columnspan=6, sticky='nw')

        tk.Label(self.top_frame_wizard, text="COM Port:").grid(row=0, column=0, sticky='w')
        self.port_var_wizard = tk.StringVar()
        self.port_menu_wizard = tk.OptionMenu(self.top_frame_wizard, self.port_var_wizard, "Select COM Port")
        self.port_menu_wizard.grid(row=0, column=1, columnspan=5, sticky='w')
        self.port_menu_wizard.bind("<Button-1>", self.refresh_ports)

        tk.Label(self.top_frame_wizard, text="Start Device ID:").grid(row=1, column=0, sticky='w')
        self.start_id_entry = tk.Entry(self.top_frame_wizard); self.start_id_entry.grid(row=1, column=1, sticky='w')

        tk.Label(self.top_frame_wizard, text="End Device ID:").grid(row=1, column=2, sticky='w')
        self.end_id_entry = tk.Entry(self.top_frame_wizard); self.end_id_entry.grid(row=1, column=3, sticky='w')

        # Quick Sample Mode
        self.quick_sample_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self.top_frame_wizard, text="Quick Sample Mode", variable=self.quick_sample_var).grid(row=1, column=4, sticky='w')
        tk.Label(self.top_frame_wizard, text="Sample Size:").grid(row=1, column=5, sticky='e')
        self.sample_size_var = tk.IntVar(value=3)
        self.sample_size_spin = tk.Spinbox(self.top_frame_wizard, from_=3, to=15, width=4, textvariable=self.sample_size_var)
        self.sample_size_spin.grid(row=1, column=6, sticky='w')

        # Baud / Parity / Data / Stop
        tk.Label(self.top_frame_wizard, text="Baudrates:").grid(row=2, column=0, sticky='w')
        self.baudrate_vars = {str(b): tk.BooleanVar(value=True) for b in default_baudrates}
        for i, (b, var) in enumerate(self.baudrate_vars.items()):
            tk.Checkbutton(self.top_frame_wizard, text=b, variable=var).grid(row=2, column=1+i, sticky='w')

        self.custom_baudrate_var = tk.BooleanVar()
        tk.Checkbutton(self.top_frame_wizard, text="Custom", variable=self.custom_baudrate_var,
                       command=self.toggle_custom_baudrate).grid(row=2, column=1+len(self.baudrate_vars), sticky='w')
        self.custom_baudrate_entry = tk.Entry(self.top_frame_wizard, state=tk.DISABLED, width=8)
        self.custom_baudrate_entry.grid(row=2, column=2+len(self.baudrate_vars), sticky='w')

        tk.Label(self.top_frame_wizard, text="Parities:").grid(row=3, column=0, sticky='w')
        self.parity_vars = {p: tk.BooleanVar(value=True) for p in default_parities}
        for i, (p, var) in enumerate(self.parity_vars.items()):
            tk.Checkbutton(self.top_frame_wizard, text=p, variable=var).grid(row=3, column=1+i, sticky='w')

        self.custom_parity_var = tk.BooleanVar()
        tk.Checkbutton(self.top_frame_wizard, text="Custom", variable=self.custom_parity_var,
                       command=self.toggle_custom_parity).grid(row=3, column=1+len(self.parity_vars), sticky='w')
        self.custom_parity_entry = tk.Entry(self.top_frame_wizard, state=tk.DISABLED, width=4)
        self.custom_parity_entry.grid(row=3, column=2+len(self.parity_vars), sticky='w')

        tk.Label(self.top_frame_wizard, text="Databits:").grid(row=4, column=0, sticky='w')
        self.databits_vars = {str(d): tk.BooleanVar(value=True) for d in default_databits}
        for i, (d, var) in enumerate(self.databits_vars.items()):
            tk.Checkbutton(self.top_frame_wizard, text=d, variable=var).grid(row=4, column=1+i, sticky='w')

        tk.Label(self.top_frame_wizard, text="Stopbits:").grid(row=4, column=3, sticky='e')
        self.stopbits_vars = {str(s): tk.BooleanVar(value=True) for s in default_stopbits}
        for i, (s, var) in enumerate(self.stopbits_vars.items()):
            tk.Checkbutton(self.top_frame_wizard, text=s, variable=var).grid(row=4, column=4+i, sticky='w')

        tk.Label(self.top_frame_wizard, text="Register Type:").grid(row=5, column=0, sticky='w')
        self.point_type_var = tk.StringVar(self.top_frame_wizard); self.point_type_var.set("03: Holding Registers")
        self.point_type_menu = tk.OptionMenu(self.top_frame_wizard, self.point_type_var, *MODBUS_POINT_TYPES.keys())
        self.point_type_menu.grid(row=5, column=1, sticky='w')

        tk.Label(self.top_frame_wizard, text="Register Read Range:").grid(row=5, column=2, sticky='e')
        self.register_start_entry = tk.Entry(self.top_frame_wizard, width=6); self.register_start_entry.grid(row=5, column=3, sticky='w'); self.register_start_entry.insert(0, '0')
        self.register_end_entry   = tk.Entry(self.top_frame_wizard, width=6); self.register_end_entry.grid(row=5, column=4, sticky='w'); self.register_end_entry.insert(0, '1')

        # buttons
        self.start_detection_button = tk.Button(self.top_frame_wizard, text="Start Detection", command=self.start_detection, bg='green', fg='white', width=18)
        self.stop_detection_button  = tk.Button(self.top_frame_wizard, text="Stop Detection",  command=self.stop_detection,  bg='red',   fg='white', width=18)
        self.clear_results_button   = tk.Button(self.top_frame_wizard, text="Clear Results",  command=self.clear_results_wizard, bg="blue", fg="white", width=18)
        self.download_log_button    = tk.Button(self.top_frame_wizard, text="Download Log",   command=self.download_log, bg='blue', fg='white', width=18)

        self.start_detection_button.grid(row=6, column=0, columnspan=2, sticky='w')
        self.stop_detection_button.grid(row=6, column=2, columnspan=2, sticky='w')
        self.clear_results_button.grid(row=6, column=4, columnspan=1, sticky='w')
        self.download_log_button.grid(row=6, column=5, columnspan=2, sticky='w', padx=(8,0))

        self.progress_label = tk.Label(self.top_frame_wizard, text="Progress: Not Started")
        self.progress_label.grid(row=7, column=0, columnspan=6, sticky='w')
        self.settings_label = tk.Label(self.top_frame_wizard, text="Current Settings: N/A")
        self.settings_label.grid(row=8, column=0, columnspan=6, sticky='w')

        self.progress_bar = ttk.Progressbar(self.top_frame_wizard, orient="horizontal", length=420, mode="determinate")
        self.progress_bar.grid(row=9, column=0, columnspan=6, sticky='w')

        self.elapsed_time_label = tk.Label(self.top_frame_wizard, text="Elapsed Time: 00:00:00, Estimated Time Remaining: 00:00:00")
        self.elapsed_time_label.grid(row=10, column=0, columnspan=6, sticky='w')

    # -------------- helpers --------------
    def refresh_ports(self, _=None):
        ports = serial.tools.list_ports.comports()
        menu = self.port_menu_wizard["menu"]; menu.delete(0, "end")
        for p in ports:
            menu.add_command(label=f"{p.device} - {p.description}",
                             command=tk._setit(self.port_var_wizard, f"{p.device} - {p.description}"))

    def toggle_custom_parity(self):
        self.custom_parity_entry.config(state=tk.NORMAL if self.custom_parity_var.get() else tk.DISABLED)

    def toggle_custom_baudrate(self):
        self.custom_baudrate_entry.config(state=tk.NORMAL if self.custom_baudrate_var.get() else tk.DISABLED)

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
        self.elapsed_time_label.config(
            text=f"Elapsed Time: {self.format_time(elapsed)}, Estimated Time Remaining: 00:00:00"
        )
        self.start_detection_button.config(state=tk.NORMAL)

    # -------------- lifecycle --------------
    def start_detection(self):
        if not self.port_var_wizard.get() or not self.start_id_entry.get() or not self.end_id_entry.get():
            messagebox.showwarning("Input Error", "Please select a port and enter start and end device IDs before starting detection.")
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

        if not the_port or the_port == "Select COM Port":
            self.refresh_ports()
        self.start_time = time.time()
        self.done_trials = 0
        self.total_trials = 0
        self.start_detection_button.config(state=tk.DISABLED)
        self.update_elapsed_time()  # start timer
        Thread(target=self.auto_detect_modbus, daemon=True).start()

    def stop_detection(self):
        self.stop_event.set()

    def clear_results_wizard(self):
        self.progress_label.config(text="Progress: Not Started")
        self.settings_label.config(text="Current Settings: N/A")
        self.progress_bar['value'] = 0
        self.elapsed_time_label.config(text="Elapsed Time: 00:00:00, Estimated Time Remaining: 00:00:00")

    # -------------- fast scanner --------------
    def auto_detect_modbus(self):
        port = self.port_var_wizard.get().split(' - ')[0]
        try:
            start_id  = int(self.start_id_entry.get())
            end_id    = int(self.end_id_entry.get())
            reg_start = int(self.register_start_entry.get())
            reg_end   = int(self.register_end_entry.get())
        except ValueError:
            messagebox.showerror("Input Error", "Invalid device ID(s) or register range. Please enter valid numbers.")
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

        global instrument
        instrument = minimalmodbus.Instrument(port, 1)  # temp address, changed per ID
        instrument.close_port_after_each_call = False
        instrument.clear_buffers_before_each_transaction = True

        last_serial_tuple = None
        best = None  # (score, info_dict)

        try:
            for baud in sel_baud:
                for parity in sel_par:
                    for databits in sel_data:
                        for stopbits in sel_stop:
                            if self.stop_event.is_set():
                                log.info("Scan stopped by user.")
                                messagebox.showinfo("Scan Stopped", "Modbus scan was stopped by the user.")
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

                            # choose ID list based on sampling
                            id_list = sample_ids if quick_sample else ids
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
                                else:
                                    contig_fail += 1
                                    if contig_fail >= min(EARLY_TUPLE_FAILS, len(id_list)):
                                        log.debug(f"Early-abort tuple {ser_tuple} after {contig_fail} contiguous fails")
                                        break

                            # If sampling mode and this tuple had any hit, do a full sweep for this tuple only
                            if quick_sample and tuple_hit:
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
        self.progress_bar['value'] = 100
        self.progress_label.config(text="Progress: 100%")
        self._finalize_scan(False)
        messagebox.showerror("Connection Error", "Failed to connect to any device with the tested settings.")

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
        for to in (0.15, 0.5, 1.5):
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

        pct = (self.done_trials / max(1, self.total_trials)) * 100.0
        self.progress_bar['value'] = pct
        self.progress_label.config(text=f"Progress: {pct:.1f}%")
        self.settings_label.config(
            text=f"Testing ID={device_id}, {baud} {parity} {databits}/{stopbits} "
                 f"({self.done_trials}/{self.total_trials})"
        )

        elapsed = time.time() - self.start_time
        remaining_steps = max(0, self.total_trials - self.done_trials)
        avg_per_step = (elapsed / self.done_trials) if self.done_trials else 0
        eta = avg_per_step * remaining_steps
        self.elapsed_time_label.config(
            text=f"Elapsed Time: {self.format_time(elapsed)}, "
                 f"Estimated Time Remaining: {self.format_time(eta)}"
        )
        self.frame.update_idletasks()

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
        current = self.elapsed_time_label.cget("text")
        try:
            tail = current.split(", Estimated Time Remaining: ")[1]
            self.elapsed_time_label.config(
                text=f"Elapsed Time: {self.format_time(elapsed)}, Estimated Time Remaining: {tail}"
            )
        except Exception:
            self.elapsed_time_label.config(
                text=f"Elapsed Time: {self.format_time(elapsed)}, Estimated Time Remaining: 00:00:00"
            )
        self.frame.after(1000, self.update_elapsed_time)

    @staticmethod
    def format_time(seconds):
        hrs, secs = divmod(int(seconds), 3600)
        mins, secs = divmod(secs, 60)
        return f"{hrs:02}:{mins:02}:{secs:02}"