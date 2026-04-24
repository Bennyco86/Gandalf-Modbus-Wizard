import tkinter as tk
from tkinter import ttk
import time
from collections import deque
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

# Use the TkAgg backend for tkinter integration
matplotlib.use("TkAgg")

class LiveTrendPopup:
    def __init__(self, parent, registers, is_dark=False, max_points=20000):
        self.window = tk.Toplevel(parent)
        self.window.title("Live Trend Analysis")
        self.window.geometry("900x700")
        
        self.registers = registers
        # Internal buffer is huge (20k) to support long history if needed.
        # We control what is SHOWN via the Time Window.
        self.max_points = max_points 
        self.is_open = True
        
        # Default Time Window in Seconds (e.g., Show last 60 seconds)
        self.time_window = 60.0 
        
        # Throttling: 40ms = ~25 FPS (Smoother than 100ms)
        self.last_draw_time = 0
        self.draw_interval = 0.04 
        
        # Data storage
        self.timestamps = deque(maxlen=max_points)
        self.data_history = {reg: deque(maxlen=max_points) for reg in registers}
        
        # --- 1. Top Control Frame ---
        ctrl_frame = tk.Frame(self.window)
        ctrl_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        tk.Label(ctrl_frame, text="Time Window (seconds):").pack(side=tk.LEFT)
        self.window_var = tk.StringVar(value="60")
        self.window_entry = tk.Entry(ctrl_frame, textvariable=self.window_var, width=8)
        self.window_entry.pack(side=tk.LEFT, padx=5)
        self.window_entry.bind("<Return>", self.update_time_window)
        tk.Button(ctrl_frame, text="Update", command=self.update_time_window).pack(side=tk.LEFT)

        # --- 2. Setup Figure ---
        self.fig, self.ax = plt.subplots(figsize=(8, 6), dpi=100)
        
        self.lines = {}
        for reg in registers:
            line, = self.ax.plot([], [], label=f"Reg {reg}", linewidth=2)
            self.lines[reg] = line
            
        # --- 3. Pack Canvas (Middle - Expands) ---
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.window)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- 4. Pack Toolbar (Bottom - Fixed) ---
        # Packing at bottom ensures it is never cropped by the canvas
        self.toolbar_frame = tk.Frame(self.window)
        self.toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame)
        self.toolbar.update()
        
        # Apply Initial Theme
        self.set_theme(is_dark)
        
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        self.start_time = time.time()

    def update_time_window(self, _=None):
        """Updates how many seconds of data are visible on the X-Axis."""
        try:
            val = float(self.window_var.get())
            if val < 1: val = 1
            self.time_window = val
            # Force immediate redraw to apply scale
            self.last_draw_time = 0 
        except ValueError:
            pass

    def set_theme(self, is_dark):
        """Updates the chart colors dynamically."""
        if is_dark:
            bg_color = "#333333"
            fig_color = "#2b2b2b"
            text_color = "white"
            grid_color = "#555555"
        else:
            bg_color = "#f0f0f0"
            fig_color = "white"
            text_color = "black"
            grid_color = "#d9d9d9"
            
        self.window.configure(bg=bg_color)
        self.canvas_widget.configure(bg=bg_color)
        self.toolbar_frame.configure(bg=bg_color) # Toolbar bg
        
        self.fig.patch.set_facecolor(bg_color)
        self.ax.set_facecolor(fig_color)
        
        self.ax.set_title("Real-Time Data Trend", color=text_color)
        self.ax.set_xlabel("Time (seconds)", color=text_color)
        self.ax.set_ylabel("Value", color=text_color)
        self.ax.grid(True, linestyle='--', color=grid_color, alpha=0.7)
        
        self.ax.tick_params(axis='x', colors=text_color)
        self.ax.tick_params(axis='y', colors=text_color)
        for spine in self.ax.spines.values():
            spine.set_color(text_color)
            
        legend = self.ax.legend(loc='upper left')
        if legend:
            legend.get_frame().set_facecolor(fig_color)
            legend.get_frame().set_edgecolor(grid_color)
            for text in legend.get_texts():
                text.set_color(text_color)
                
        self.canvas.draw_idle()

    def update(self, snapshot_data):
        if not self.is_open: return
        
        # 1. Update Data (Immediate)
        t_now = time.time() - self.start_time
        self.timestamps.append(t_now)
        
        for reg in self.registers:
            val = snapshot_data.get(reg)
            if isinstance(val, (int, float)):
                self.data_history[reg].append(val)
            else:
                # Fallback for errors
                if len(self.data_history[reg]) > 0:
                    self.data_history[reg].append(self.data_history[reg][-1])
                else:
                    self.data_history[reg].append(0)

        # 2. Throttle Rendering (40ms = 25 FPS)
        current_time = time.time()
        if current_time - self.last_draw_time > self.draw_interval:
            
            # Update Lines
            for reg in self.registers:
                self.lines[reg].set_data(self.timestamps, self.data_history[reg])
            
            # Handle Scrolling X-Axis based on Time Window
            if t_now > self.time_window:
                self.ax.set_xlim(t_now - self.time_window, t_now)
            else:
                self.ax.set_xlim(0, max(self.time_window, t_now))
            
            self.ax.relim()
            self.ax.autoscale_view(scalex=False, scaley=True) # Only autoscale Y
            
            self.canvas.draw_idle()
            self.last_draw_time = current_time

    def on_close(self):
        self.is_open = False
        plt.close(self.fig)
        self.window.destroy()