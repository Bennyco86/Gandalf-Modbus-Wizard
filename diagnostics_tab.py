import tkinter as tk
import customtkinter as ctk
import logging
import struct
import queue

class QueueHandler(logging.Handler):
    """This class sends log records to a queue, suitable for thread-safe UI updates."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        self.log_queue.put(self.format(record))

class DiagnosticsTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0, fg_color="transparent")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Performance: Queue for log messages
        self.log_queue = queue.Queue()
        self.max_lines = 10000 # Increased buffer size

        # --- Top Section: CRC Calculator ---
        self.crc_frame = ctk.CTkFrame(self)
        self.crc_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.crc_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self.crc_frame, text="CRC16 Calculator", font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 5))

        ctk.CTkLabel(self.crc_frame, text="Hex Bytes (e.g., '01 03 00 00'):").grid(row=1, column=0, padx=10, pady=5)
        
        self.hex_input = ctk.CTkEntry(self.crc_frame, placeholder_text="01 03 00 64 00 02")
        self.hex_input.grid(row=1, column=1, sticky="ew", padx=10, pady=5)
        
        self.btn_calc = ctk.CTkButton(self.crc_frame, text="Calculate CRC", command=self.calc_crc, width=120)
        self.btn_calc.grid(row=1, column=2, padx=10, pady=5)

        self.lbl_result = ctk.CTkLabel(self.crc_frame, text="Result: - ", font=ctk.CTkFont(size=14))
        self.lbl_result.grid(row=2, column=0, columnspan=3, sticky="w", padx=10, pady=(5, 10))

        # --- Bottom Section: Traffic Monitor ---
        self.log_frame = ctk.CTkFrame(self)
        self.log_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.log_frame.grid_rowconfigure(1, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.log_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        
        ctk.CTkLabel(header, text="Network Traffic Monitor", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left")
        
        self.btn_clear = ctk.CTkButton(header, text="Clear Log", width=80, fg_color="gray", command=self.clear_log)
        self.btn_clear.pack(side="right", padx=5)
        
        self.monitoring_active = False
        self.handler = None
        self._root_logger = logging.getLogger()
        self.btn_monitor = ctk.CTkButton(header, text="Start Monitoring", width=120, fg_color="#2e7d32", command=self.toggle_monitoring)
        self.btn_monitor.pack(side="right", padx=5)

        self.log_text = ctk.CTkTextbox(self.log_frame, state="disabled", font=ctk.CTkFont(family="Courier New", size=12))
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Start disabled by default to avoid background CPU overhead.
        self.after(300, self._poll_log_queue)

    def toggle_monitoring(self):
        if self.monitoring_active:
            self._stop_monitoring()
        else:
            self._start_monitoring()

    def _start_monitoring(self):
        if self.monitoring_active:
            return
        self.monitoring_active = True
        self.setup_logging()
        self.btn_monitor.configure(text="Stop Monitoring", fg_color="#d32f2f") # Red for Stop

    def _stop_monitoring(self):
        if not self.monitoring_active:
            return
        self.monitoring_active = False
        self._teardown_logging()
        self.btn_monitor.configure(text="Start Monitoring", fg_color="#2e7d32") # Green for Start

    def calc_crc(self):
        hex_str = self.hex_input.get()
        try:
            # Clean string: remove 0x, spaces, commas
            clean_str = hex_str.replace("0x", "").replace(" ", "").replace(",", "").replace("\n", "")
            data = bytes.fromhex(clean_str)
            
            crc = 0xFFFF
            for byte in data:
                crc ^= byte
                for _ in range(8):
                    if crc & 0x0001:
                        crc = (crc >> 1) ^ 0xA001
                    else:
                        crc >>= 1
            
            # Modbus sends Low Byte first, then High Byte
            low = crc & 0xFF
            high = (crc >> 8) & 0xFF
            
            res_hex = f"{low:02X} {high:02X}"
            res_int = f"0x{crc:04X}"
            
            self.lbl_result.configure(text=f"CRC16 (Modbus): {res_hex}  ({res_int})", text_color="green")
            
        except ValueError:
            self.lbl_result.configure(text="Error: Invalid Hex String", text_color="red")
        except Exception as e:
            self.lbl_result.configure(text=f"Error: {e}", text_color="red")

    def setup_logging(self):
        if self.handler:
            return
        # Create handler pointing to our queue
        self.handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        self.handler.setFormatter(formatter)
        
        self._root_logger.addHandler(self.handler)

    def _teardown_logging(self):
        if not self.handler:
            return
        try:
            self._root_logger.removeHandler(self.handler)
        except Exception:
            pass
        self.handler = None

    def _poll_log_queue(self):
        """Batched UI update to prevent freezing."""
        # 1. Drain the queue always (to prevent memory leak even if paused)
        lines = []
        try:
            for _ in range(500): # Max lines per poll
                lines.append(self.log_queue.get_nowait())
        except queue.Empty:
            pass

        # 2. Only update UI if active and there is data
        if self.monitoring_active and lines:
            self.log_text.configure(state='normal')
            self.log_text.insert(tk.END, '\n'.join(lines) + '\n')
            
            # Auto-scroll
            self.log_text.see(tk.END)
            
            # Trim history if too long (Rolling Buffer)
            try:
                # Check current line count
                count = int(float(self.log_text.index("end")))
                if count > self.max_lines:
                    # Delete the oldest 2000 lines to maintain buffer without clearing everything
                    trim_amount = 2000
                    self.log_text.delete("1.0", f"{trim_amount}.0")
                    self.log_text.insert("1.0", f"--- Log Truncated (Older than {self.max_lines} lines) ---\n")
            except:
                pass

            self.log_text.configure(state='disabled')
        
        # Use a slower poll while disabled.
        self.after(250 if self.monitoring_active else 500, self._poll_log_queue)

    def clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state='disabled')

    def destroy(self):
        self._teardown_logging()
        super().destroy()
