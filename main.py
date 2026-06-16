#!/usr/bin/env python3
"""
Lantan GUI Application
Controls an external USB device via CDC serial port with live data visualization.
"""

import sys
import threading
import queue
import csv
import serial
import serial.tools.list_ports
from datetime import datetime

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# Configure matplotlib with Nord dark theme
plt.style.use('dark_background')
# Nord color palette
nord_bg = '#2e3440'
nord_fg = '#d8dee9'
nord_blue = '#88c0d0'
nord_green = '#a3be8c'
nord_red = '#bf616a'
nord_purple = '#b48ead'
nord_orange = '#d08770'
plt.rcParams['figure.facecolor'] = nord_bg
plt.rcParams['axes.facecolor'] = nord_bg
plt.rcParams['axes.edgecolor'] = '#3b4252'
plt.rcParams['axes.labelcolor'] = nord_fg
plt.rcParams['axes.titlecolor'] = nord_fg
plt.rcParams['xtick.color'] = nord_fg
plt.rcParams['ytick.color'] = nord_fg
plt.rcParams['legend.facecolor'] = nord_bg
plt.rcParams['legend.labelcolor'] = nord_fg
plt.rcParams['legend.edgecolor'] = '#3b4252'
plt.rcParams['grid.color'] = '#3b4252'
plt.rcParams['text.color'] = nord_fg


class SerialManager:
    """Manages serial communication with the device."""
    
    def __init__(self):
        self.serial_conn = None
        self.is_connected = False
        self.message_queue = queue.Queue()
        self.running = False
        self.reader_thread = None
        
    def list_ports(self):
        """Return list of available serial ports with manufacturer/product info.
        
        Returns formatted strings like: "device (Manufacturer - Product)"
        Filtered to active USB/CDC devices only.
        """
        all_ports = serial.tools.list_ports.comports()
        port_display_list = []
        for port in all_ports:
            # Skip non-USB devices
            if not (hasattr(port, 'pid') and port.pid and hasattr(port, 'vid') and port.vid):
                if not (port.device and ('/dev/ttyACM' in port.device or '/dev/ttyUSB' in port.device)):
                    continue
            
            # Build compact display string
            info_parts = []
            if hasattr(port, 'manufacturer') and port.manufacturer:
                info_parts.append(port.manufacturer)
            if hasattr(port, 'product') and port.product:
                info_parts.append(port.product)
            
            if info_parts:
                display_str = f"{port.device} ({' - '.join(info_parts)})"
            else:
                display_str = port.device
            
            port_display_list.append(display_str)
        
        return port_display_list
    
    def connect(self, port_name, baudrate=115200, timeout=1):
        """Connect to a serial port."""
        if self.is_connected:
            self.disconnect()
        
        try:
            self.serial_conn = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                bytesize=8,
                parity=serial.PARITY_NONE,
                stopbits=1,
                timeout=timeout
            )
            self.is_connected = True
            self.start_reader()
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from serial port."""
        self.running = False
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1)
        
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
        self.serial_conn = None
        self.is_connected = False
    
    def start_reader(self):
        """Start thread to read from serial port."""
        if self.reader_thread and self.reader_thread.is_alive():
            return
        
        self.running = True
        self.reader_thread = threading.Thread(
            target=self._read_serial, daemon=True
        )
        self.reader_thread.start()
    
    def _read_serial(self):
        """Read from serial port and parse messages."""
        buffer = ""
        while self.running and self.serial_conn:
            try:
                if self.serial_conn.in_waiting:
                    data = self.serial_conn.read_all().decode('ascii', errors='ignore')
                    # Normalize line endings: handle \r\n, \n, or \r
                    data = data.replace('\r\n', '\n').replace('\r', '\n')
                    buffer += data
                    
                    # Parse complete messages (end with \n)
                    while '\n' in buffer:
                        msg, buffer = buffer.split('\n', 1)
                        msg = msg.strip()
                        if msg:
                            self.message_queue.put(msg)
            except Exception as e:
                print(f"Serial read error: {e}")
                break
    
    def send_command(self, cmd_id, *args):
        """Send a command to the device."""
        if not self.is_connected or not self.serial_conn:
            return False
        
        try:
            msg = f"{cmd_id}|{'|'.join(str(arg) for arg in args)}\r\n"
            self.serial_conn.write(msg.encode('ascii'))
            return True
        except Exception as e:
            print(f"Failed to send command: {e}")
            return False
    
    def parse_update_message(self, message):
        """Parse UPDATE message from device."""
        try:
            parts = message.split('|')
            if parts[0] != 'UPDATE':
                return None
            
            # Power good flag
            power_good = parts[1] if len(parts) > 1 else '0'
            
            # Channel active flags (4 channels)
            channel_a_active = parts[2] if len(parts) > 2 else '0'
            channel_b_active = parts[3] if len(parts) > 3 else '0'
            channel_c_active = parts[4] if len(parts) > 4 else '0'
            channel_d_active = parts[5] if len(parts) > 5 else '0'
            
            # Voltages (uV)
            voltage_a = float(parts[6]) if len(parts) > 6 else 0.0
            voltage_b = float(parts[7]) if len(parts) > 7 else 0.0
            voltage_c = float(parts[8]) if len(parts) > 8 else 0.0
            voltage_d = float(parts[9]) if len(parts) > 9 else 0.0
            
            # Currents (uA)
            current_a = float(parts[10]) if len(parts) > 10 else 0.0
            current_b = float(parts[11]) if len(parts) > 11 else 0.0
            current_c = float(parts[12]) if len(parts) > 12 else 0.0
            current_d = float(parts[13]) if len(parts) > 13 else 0.0
            
            # Modulation amplitudes (uA)
            mod_amp_a = float(parts[14]) if len(parts) > 14 else 0.0
            mod_amp_b = float(parts[15]) if len(parts) > 15 else 0.0
            mod_amp_c = float(parts[16]) if len(parts) > 16 else 0.0
            mod_amp_d = float(parts[17]) if len(parts) > 17 else 0.0
            
            # DUT responses (arbitrary units)
            dut_response_a = float(parts[18]) if len(parts) > 18 else 0.0
            dut_response_b = float(parts[19]) if len(parts) > 19 else 0.0
            dut_response_c = float(parts[20]) if len(parts) > 20 else 0.0
            dut_response_d = float(parts[21]) if len(parts) > 21 else 0.0
            
            # Detector config
            detector_sensitivity = int(parts[22]) if len(parts) > 22 else 1
            detector_gain = int(parts[23]) if len(parts) > 23 else 1
            detector_out_of_range = int(parts[24]) if len(parts) > 24 else 0
            
            return {
                'power_good': power_good,
                'channel_a_active': channel_a_active,
                'channel_b_active': channel_b_active,
                'channel_c_active': channel_c_active,
                'channel_d_active': channel_d_active,
                'voltage_a': voltage_a,
                'voltage_b': voltage_b,
                'voltage_c': voltage_c,
                'voltage_d': voltage_d,
                'current_a': current_a,
                'current_b': current_b,
                'current_c': current_c,
                'current_d': current_d,
                'mod_amp_a': mod_amp_a,
                'mod_amp_b': mod_amp_b,
                'mod_amp_c': mod_amp_c,
                'mod_amp_d': mod_amp_d,
                'dut_response_a': dut_response_a,
                'dut_response_b': dut_response_b,
                'dut_response_c': dut_response_c,
                'dut_response_d': dut_response_d,
                'detector_sensitivity': detector_sensitivity,
                'detector_gain': detector_gain,
                'detector_out_of_range': detector_out_of_range,
            }
        except (ValueError, IndexError) as e:
            print(f"Failed to parse UPDATE message: {e}")
            return None


class LantanGUI:
    """Main GUI application for Lantan device control."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Lantan GUI")
        self.root.geometry("2000x1200")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Enable DPI awareness for high-DPI displays
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass  # Only works on Windows, ignore on other platforms
        
        # Launch in maximized window mode
        self.root.update()
        self.root.attributes('-zoomed', True)
        
        # Apply dark theme
        self._apply_dark_theme()
        
        # Data storage
        self.serial_manager = SerialManager()
        self.max_samples = 10000  # Always store up to 10000 samples in buffer
        self.display_samples = tk.IntVar(value=200)  # Number of samples to display (10-10000)
        self.sample_count = 0
        self.time_data = []
        self.dut_a_data = []
        self.dut_b_data = []
        self.dut_c_data = []
        self.dut_d_data = []
        
        # Y-axis scale mode: 'linear' or 'log'
        self.y_scale_mode = tk.StringVar(value='linear')
        
        # Configuration state
        self.channels_enabled = {
            'A': tk.BooleanVar(value=True),
            'B': tk.BooleanVar(value=True),
            'C': tk.BooleanVar(value=True),
            'D': tk.BooleanVar(value=True)
        }
        self.detector_sensitivity = tk.IntVar(value=1)
        self.detector_gain = tk.IntVar(value=1)
        self.mod_intensity = {
            'A': tk.IntVar(value=50),
            'B': tk.IntVar(value=50),
            'C': tk.IntVar(value=50),
            'D': tk.IntVar(value=50)
        }
        
        # Last update data for numerical displays
        self.last_update = None
        self.running = True
        
        # Create UI
        self._create_ui()
        
        # Start message processing thread
        self.processing_thread = threading.Thread(
            target=self._process_messages, daemon=True
        )
        self.processing_thread.start()
        
        # Start update timer
        self._start_update_timer()
    
    def _apply_dark_theme(self):
        """Apply Nord dark theme to Tkinter and matplotlib."""
        # Nord color palette
        nord_bg = '#2e3440'
        nord_bg2 = '#3b4252'
        nord_bg3 = '#434c5e'
        nord_fg = '#d8dee9'
        nord_fg2 = '#e5e9f0'
        nord_blue = '#88c0d0'
        nord_green = '#a3be8c'
        nord_red = '#bf616a'
        nord_purple = '#b48ead'
        nord_orange = '#d08770'
        nord_yellow = '#ebcb8b'
        
        # Configure root window
        self.root.configure(bg=nord_bg)
        
        # Configure ttk style
        style = ttk.Style()
        style.theme_use('clam')  # Use clam as base theme (most customizable)
        
        # Configure colors for all widget types
        style.configure('.', 
            background=nord_bg,
            foreground=nord_fg,
            bordercolor=nord_bg,
            darkcolor=nord_bg,
            lightcolor=nord_bg2)
        
        # Frame
        style.configure('TFrame', background=nord_bg)
        style.configure('TLabelFrame', background=nord_bg, foreground=nord_fg)
        style.configure('TLabelFrame.Label', background=nord_bg, foreground=nord_fg)
        
        # Labels
        style.configure('TLabel', background=nord_bg, foreground=nord_fg)
        
        # Buttons
        style.configure('TButton', 
            background=nord_bg3,
            foreground=nord_fg,
            bordercolor=nord_bg3,
            darkcolor=nord_bg3,
            lightcolor=nord_bg3)
        style.map('TButton', 
            background=[('active', nord_bg2), ('pressed', nord_bg)],
            foreground=[('active', nord_fg), ('pressed', nord_fg)])
        
        # Combobox
        style.configure('TCombobox', 
            background=nord_bg3,
            foreground=nord_fg,
            fieldbackground=nord_bg2,
            selectbackground=nord_blue,
            selectforeground=nord_fg)
        style.map('TCombobox', 
            fieldbackground=[('readonly', nord_bg2)],
            background=[('readonly', nord_bg3)],
            foreground=[('readonly', nord_fg)])
        
        # Checkbuttons
        style.configure('TCheckbutton', 
            background=nord_bg,
            foreground=nord_fg)
        style.map('TCheckbutton',
            background=[('active', nord_bg2), ('pressed', nord_bg)],
            foreground=[('active', nord_fg), ('pressed', nord_fg)])
        
        # Scale
        style.configure('Horizontal.TScale', 
            background=nord_bg,
            troughcolor=nord_bg2,
            foreground=nord_fg)
        
        # Scrollbar - match Nord dark theme
        style.configure('Vertical.TScrollbar',
            background=nord_bg2,
            troughcolor=nord_bg2,
            bordercolor=nord_bg2,
            arrowcolor=nord_fg)
        style.map('Vertical.TScrollbar',
            background=[('active', nord_bg3), ('pressed', nord_bg2)],
            troughcolor=[('active', nord_bg3), ('pressed', nord_bg2)])
        
        # Notebook (if used)
        style.configure('TNotebook', background=nord_bg)
        style.configure('TNotebook.Tab', background=nord_bg2, foreground=nord_fg)
        style.map('TNotebook.Tab', 
            background=[('selected', nord_bg3)],
            foreground=[('selected', nord_fg)])
        
        # Configure matplotlib figure background
        self.root.option_add('*background', nord_bg)
        self.root.option_add('*foreground', nord_fg)
    
    def _create_ui(self):
        """Create all UI components."""
        # Top menu ribbon frame
        self.menu_frame = ttk.Frame(self.root)
        self.menu_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Create a container frame for left and right panels
        # This allows us to use grid layout for fixed/expandable sizing
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Configure grid: left expands to fit content, right expands to fill remaining space
        self.main_container.grid_columnconfigure(0, weight=0, minsize=300)  # Left panel - don't expand beyond content, but has minimum width
        self.main_container.grid_columnconfigure(1, weight=1)  # Right panel expands
        self.main_container.grid_rowconfigure(0, weight=1)
        
        # Left panel for numerical displays and configuration
        # Create a scrollable frame for the left panel
        self.left_panel_frame = ttk.Frame(self.main_container)
        self.left_panel_frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(5, 0), pady=5)
        self.left_panel_frame.grid_columnconfigure(0, weight=1)
        
        # Create canvas for scrolling
        self.left_canvas = tk.Canvas(self.left_panel_frame, bg=nord_bg, highlightthickness=0)
        self.left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add scrollbar
        self.left_scrollbar = ttk.Scrollbar(self.left_panel_frame, orient=tk.VERTICAL, command=self.left_canvas.yview)
        self.left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.left_canvas.configure(yscrollcommand=self.left_scrollbar.set)
        
        # Frame inside canvas to hold the actual content
        self.left_panel = ttk.Frame(self.left_canvas)
        self.left_panel.grid_columnconfigure(0, weight=1)
        self.left_canvas.create_window((0, 0), window=self.left_panel, anchor=tk.NW)
        
        # Bind scroll wheel to canvas and left panel frame for smoother scrolling
        self.left_canvas.bind("<MouseWheel>", self._on_left_panel_scroll)
        self.left_panel.bind("<MouseWheel>", self._on_left_panel_scroll)
        self.left_panel_frame.bind("<MouseWheel>", self._on_left_panel_scroll)
        self.left_scrollbar.bind("<MouseWheel>", self._on_left_panel_scroll)
        
        # Bind configure event to update scroll region and window size
        self.left_panel.bind("<Configure>", self._update_left_panel_scrollregion)
        self.left_canvas.bind("<Configure>", self._update_left_panel_scrollregion)
        self.left_panel_frame.bind("<Configure>", self._update_left_panel_scrollregion)
        
        # Create menu ribbon
        self._create_menu_ribbon()
        
        # Create graphing area
        self._create_graph_area()
        
        # Create numerical displays
        self._create_numerical_displays()
        
        # Create configuration panel
        self._create_configuration_panel()
    
    def _create_menu_ribbon(self):
        """Create top menu ribbon with port selection, refresh, and connect."""
        # Port selection
        self.port_label = ttk.Label(self.menu_frame, text="Port:")
        self.port_label.pack(side=tk.LEFT, padx=5)
        
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(
            self.menu_frame,
            textvariable=self.port_var,
            state="readonly",
            width=50
        )
        self.port_combo.pack(side=tk.LEFT, padx=5)
        
        # Refresh button
        self.refresh_btn = ttk.Button(
            self.menu_frame,
            text="Refresh",
            command=self._refresh_ports
        )
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # Connect/Disconnect button
        self.connect_status = tk.BooleanVar(value=False)
        self.connect_btn = ttk.Button(
            self.menu_frame,
            text="Connect",
            command=self._toggle_connect
        )
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        # Clear button
        self.clear_btn = ttk.Button(
            self.menu_frame,
            text="Clear",
            command=self._clear_data
        )
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        # Save Data button
        self.save_btn = ttk.Button(
            self.menu_frame,
            text="Save Data",
            command=self._save_data
        )
        self.save_btn.pack(side=tk.LEFT, padx=5)
        
        # Connection status label
        self.status_label = ttk.Label(self.menu_frame, text="Disconnected")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Refresh ports on startup
        self._refresh_ports()
    
    def _create_graph_area(self):
        """Create graphing area with matplotlib."""
        # Graph frame - use main_container grid
        graph_frame = ttk.Frame(self.main_container)
        graph_frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(0, 5), pady=5)
        graph_frame.grid_columnconfigure(0, weight=1)
        graph_frame.grid_rowconfigure(0, weight=1)
        
        # Configure graph_frame to use grid layout for better control
        graph_frame.grid_columnconfigure(0, weight=1)
        graph_frame.grid_rowconfigure(0, weight=1)
        graph_frame.grid_rowconfigure(1, weight=0)  # Slider row doesn't expand
        
        # Create matplotlib figure
        self.fig, self.ax = plt.subplots(figsize=(10, 6), dpi=100)
        
        # Initialize data
        self.time_data = list(range(self.max_samples))
        self.dut_a_data = [0.0] * self.max_samples
        self.dut_b_data = [0.0] * self.max_samples
        self.dut_c_data = [0.0] * self.max_samples
        self.dut_d_data = [0.0] * self.max_samples
        
        # Plot lines with Nord palette colors for dark background
        self.line_a, = self.ax.plot([], [], color=nord_blue, linewidth=2, label='DUT Response A')
        self.line_b, = self.ax.plot([], [], color=nord_green, linewidth=2, label='DUT Response B')
        self.line_c, = self.ax.plot([], [], color=nord_orange, linewidth=2, label='DUT Response C')
        self.line_d, = self.ax.plot([], [], color=nord_purple, linewidth=2, label='DUT Response D')
        
        self.ax.set_xlabel('Sample number', color=nord_fg)
        self.ax.set_ylabel('Intensity (a.u.)', color=nord_fg)
        # self.ax.set_title('DUT Responses', color=nord_fg, pad=20)
        
        # Configure legend for Nord theme
        legend = self.ax.legend(facecolor=nord_bg, edgecolor='#3b4252', labelcolor=nord_fg)
        legend.get_frame().set_alpha(0.8)
        
        # Configure grid and ticks for Nord theme
        self.ax.grid(True, color='#3b4252', alpha=0.5, linestyle='--')
        self.ax.tick_params(colors=nord_fg)
        
        # Set axis colors for Nord theme
        self.ax.spines['bottom'].set_color('#3b4252')
        self.ax.spines['top'].set_color('#3b4252')
        self.ax.spines['left'].set_color('#3b4252')
        self.ax.spines['right'].set_color('#3b4252')
        
        # Embed in Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky=tk.NSEW)
        
        # Samples to display slider (below the graph)
        slider_frame = ttk.Frame(graph_frame)
        slider_frame.grid(row=1, column=0, sticky=tk.EW, padx=5, pady=5)
        
        ttk.Label(slider_frame, text="Samples to display:").pack(side=tk.LEFT, padx=5)
        
        def update_samples_display(val):
            self.display_samples.set(int(float(val)))
            self._update_plot(from_new_data=False)
        
        samples_slider = ttk.Scale(
            slider_frame,
            from_=10,
            to=10000,
            variable=self.display_samples,
            orient=tk.HORIZONTAL,
            length=200,
            command=update_samples_display
        )
        samples_slider.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        samples_value_label = ttk.Label(
            slider_frame,
            textvariable=self.display_samples
        )
        samples_value_label.pack(side=tk.LEFT, padx=5)
        
        # Y-axis scale toggle button
        self.scale_btn = ttk.Button(
            slider_frame,
            textvariable=self.y_scale_mode,
            command=self._toggle_y_scale
        )
        self.scale_btn.pack(side=tk.LEFT, padx=5)
    
    def _create_numerical_displays(self):
        """Create numerical displays section with 2 columns.
        
        Left column: Power Good, Channel states, Mod Amp, DUT Resp, Detector
        Right column: Voltage A-D, Current A-D
        """
        num_frame = ttk.LabelFrame(
            self.left_panel,
            text="Numerical Displays",
            labelanchor=tk.N
        )
        num_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)
        num_frame.grid_columnconfigure(0, weight=1, minsize=150)
        num_frame.grid_columnconfigure(1, weight=1, minsize=80)
        num_frame.grid_columnconfigure(2, weight=1, minsize=150)
        num_frame.grid_columnconfigure(3, weight=1, minsize=80)
        
        # Field names and values for display
        self.display_labels = {}
        self.display_label_widgets = {}
        
        # Left column fields (all except Voltage, Current, and DUT Resp)
        left_column_fields = [
            ('Power Good', 'power_good'),
            ('Channel A Active', 'channel_a_active'),
            ('Channel B Active', 'channel_b_active'),
            ('Channel C Active', 'channel_c_active'),
            ('Channel D Active', 'channel_d_active'),
            ('Mod Amp A (mA)', 'mod_amp_a'),
            ('Mod Amp B (mA)', 'mod_amp_b'),
            ('Mod Amp C (mA)', 'mod_amp_c'),
            ('Mod Amp D (mA)', 'mod_amp_d'),
            ('Det. Sensitivity', 'detector_sensitivity'),
            ('Det. Gain', 'detector_gain'),
            ('Det. Out of Range', 'detector_out_of_range'),
        ]
        
        # Right column fields: Voltage, Current, and DUT Resp
        right_column_fields = [
            ('Voltage A (mV)', 'voltage_a'),
            ('Voltage B (mV)', 'voltage_b'),
            ('Voltage C (mV)', 'voltage_c'),
            ('Voltage D (mV)', 'voltage_d'),
            ('Current A (mA)', 'current_a'),
            ('Current B (mA)', 'current_b'),
            ('Current C (mA)', 'current_c'),
            ('Current D (mA)', 'current_d'),
            ('DUT Resp A', 'dut_response_a'),
            ('DUT Resp B', 'dut_response_b'),
            ('DUT Resp C', 'dut_response_c'),
            ('DUT Resp D', 'dut_response_d'),
        ]
        
        # Create 2-column layout
        # Left column (grid columns 0-1)
        for row, (label_text, field_key) in enumerate(left_column_fields):
            label = ttk.Label(num_frame, text=label_text + ":")
            label.grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
            
            value_var = tk.StringVar(value="N/A")
            value_label = ttk.Label(num_frame, textvariable=value_var)
            value_label.grid(row=row, column=1, sticky=tk.E, padx=5, pady=2)
            
            self.display_labels[field_key] = value_var
            self.display_label_widgets[field_key] = value_label
        
        # Right column (grid columns 2-3)
        for row, (label_text, field_key) in enumerate(right_column_fields):
            label = ttk.Label(num_frame, text=label_text + ":")
            label.grid(row=row, column=2, sticky=tk.W, padx=5, pady=2)
            
            value_var = tk.StringVar(value="N/A")
            value_label = ttk.Label(num_frame, textvariable=value_var)
            value_label.grid(row=row, column=3, sticky=tk.E, padx=5, pady=2)
            
            self.display_labels[field_key] = value_var
            self.display_label_widgets[field_key] = value_label
    
    def _create_configuration_panel(self):
        """Create configuration panel."""
        config_frame = ttk.LabelFrame(
            self.left_panel,
            text="Configuration",
            labelanchor=tk.N
        )
        config_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=5)
        config_frame.grid_columnconfigure(0, weight=1)
        config_frame.grid_columnconfigure(1, weight=1)
        config_frame.grid_columnconfigure(2, weight=1)
        config_frame.grid_columnconfigure(3, weight=1)
        
        # Channel enable checkboxes - arranged vertically to fit better
        ttk.Label(config_frame, text="Channels:").grid(
            row=0, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2
        )
        
        for i, ch in enumerate(['A', 'B', 'C', 'D']):
            cb = ttk.Checkbutton(
                config_frame,
                text=f"Channel {ch}",
                variable=self.channels_enabled[ch],
                onvalue=True,
                offvalue=False
            )
            cb.grid(row=1+i, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2)
        
        # Detector sensitivity
        ttk.Label(config_frame, text="Detector Sensitivity:").grid(
            row=5, column=0, sticky=tk.W, padx=5, pady=2
        )
        sens_combo = ttk.Combobox(
            config_frame,
            textvariable=self.detector_sensitivity,
            values=[1, 2, 3, 4],
            state="readonly",
            width=5
        )
        sens_combo.grid(row=5, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Detector gain
        ttk.Label(config_frame, text="Detector Gain:").grid(
            row=6, column=0, sticky=tk.W, padx=5, pady=2
        )
        gain_combo = ttk.Combobox(
            config_frame,
            textvariable=self.detector_gain,
            values=[1, 2, 3, 4],
            state="readonly",
            width=5
        )
        gain_combo.grid(row=6, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Modulation intensity sliders - stacked vertically
        ttk.Label(config_frame, text="Modulation Intensity:").grid(
            row=7, column=0, columnspan=4, sticky=tk.W, padx=5, pady=2
        )
        
        row_offset = 8
        for ch in ['A', 'B', 'C', 'D']:
            # Channel label
            ttk.Label(config_frame, text=f"Channel {ch}:").grid(
                row=row_offset, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2
            )
            # Slider with integer-only values
            def make_int_cmd(var):
                def cmd(val):
                    var.set(int(float(val)))
                return cmd
            
            slider = ttk.Scale(
                config_frame,
                from_=0,
                to=100,
                variable=self.mod_intensity[ch],
                orient=tk.HORIZONTAL,
                length=200,
                command=make_int_cmd(self.mod_intensity[ch])
            )
            slider.grid(row=row_offset+1, column=0, columnspan=4, sticky=tk.EW, padx=5, pady=2)
            
            # Value label
            value_label = ttk.Label(
                config_frame,
                textvariable=self.mod_intensity[ch]
            )
            value_label.grid(row=row_offset+2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(0, 10))
            
            row_offset += 3
        
        # Update configuration button
        update_btn = ttk.Button(
            config_frame,
            text="Update Configuration",
            command=self._update_configuration
        )
        update_btn.grid(
            row=row_offset, column=0, columnspan=4, pady=10
        )
    
    def _refresh_ports(self):
        """Refresh list of available serial ports."""
        ports = self.serial_manager.list_ports()
        self.port_combo['values'] = ports
        if ports:
            self.port_var.set(ports[0])
    
    def _toggle_connect(self):
        """Toggle connection to serial port."""
        if self.serial_manager.is_connected:
            # Send command to disable all channels before disconnecting
            mod_cmd = ['0', '0', '0', '0', 0, 0, 0, 0]
            self.serial_manager.send_command('MODULATOR', *mod_cmd)
            
            self.serial_manager.disconnect()
            self.connect_btn.config(text="Connect")
            self.status_label.config(text="Disconnected")
        else:
            port_display = self.port_var.get()
            if not port_display:
                messagebox.showerror("Error", "No port selected!")
                return
            
            # Extract device path by removing everything in parentheses
            # e.g., "/dev/ttyACM0 (Manufacturer - Product)" -> "/dev/ttyACM0"
            port = port_display.split(" (")[0] if " (" in port_display else port_display
            
            if self.serial_manager.connect(port):
                self.connect_btn.config(text="Disconnect")
                self.status_label.config(text=f"Connected to {port}")
                # Send configuration automatically twice with 100ms delay
                self._send_configuration_commands()
                self.root.after(100, self._send_configuration_commands)
            else:
                messagebox.showerror("Error", f"Failed to connect to {port}")
    
    def _toggle_y_scale(self):
        """Toggle Y-axis scale between linear and log."""
        current = self.y_scale_mode.get()
        new_mode = 'log' if current == 'linear' else 'linear'
        self.y_scale_mode.set(new_mode)
        # Force a plot update to apply the new scale
        self._update_plot(from_new_data=False)
    
    def _on_left_panel_scroll(self, event):
        """Handle scroll wheel for left panel."""
        # Only scroll if mouse is over the left panel area
        if self.left_canvas.winfo_containing(event.x_root, event.y_root) == self.left_canvas:
            self.left_canvas.yview_scroll(-1 * (event.delta // 120), tk.UNITS)
        return "break"
    
    def _update_left_panel_scrollregion(self, event):
        """Update scroll region when left panel content size changes."""
        # Update scroll region to fit all content
        self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
        # Update the window width to match the canvas width
        self.left_canvas.itemconfig(1, width=self.left_canvas.winfo_width())
    
    def _clear_data(self):
        """Clear all data buffers."""
        # Reset data lists
        self.sample_count = 0
        self.time_data = list(range(self.max_samples))
        self.dut_a_data = [0.0] * self.max_samples
        self.dut_b_data = [0.0] * self.max_samples
        self.dut_c_data = [0.0] * self.max_samples
        self.dut_d_data = [0.0] * self.max_samples
        
        # Reset all display values to N/A and reset detector out of range color
        for key, var in self.display_labels.items():
            var.set("N/A")
            if key in self.display_label_widgets and key == 'detector_out_of_range':
                self.display_label_widgets[key].config(foreground=nord_fg)
        
        # Update plot to show cleared data (no new data to add)
        self._update_plot(from_new_data=False)
    
    def _save_data(self):
        """Save all stored data to a CSV file."""
        if not self.dut_a_data:
            messagebox.showinfo("Info", "No data to save.")
            return
        
        # Get file path from save dialog
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Data"
        )
        
        if not file_path:
            return  # User cancelled
        
        try:
            with open(file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header
                writer.writerow(['Sample', 'DUT Response A', 'DUT Response B', 'DUT Response C', 'DUT Response D'])
                
                # Write data rows (newest first, so reverse order)
                # Use min length to handle case where data lists might have different lengths
                min_length = min(len(self.dut_a_data), len(self.dut_b_data), 
                                  len(self.dut_c_data), len(self.dut_d_data))
                
                # Start from the end and go backwards to get newest first
                for i in range(min_length - 1, -1, -1):
                    # Calculate sample number from the original position
                    sample_num = min_length - i
                    writer.writerow([
                        sample_num,
                        self.dut_a_data[i],
                        self.dut_b_data[i],
                        self.dut_c_data[i],
                        self.dut_d_data[i]
                    ])
            
            messagebox.showinfo("Success", f"Data saved to {file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save data: {e}")
    
    def _send_configuration_commands(self):
        """Send configuration commands to device without UI feedback."""
        if not self.serial_manager.is_connected:
            return
        
        # Send MODULATOR command
        mod_cmd = [
            '1' if self.channels_enabled['A'].get() else '0',
            '1' if self.channels_enabled['B'].get() else '0',
            '1' if self.channels_enabled['C'].get() else '0',
            '1' if self.channels_enabled['D'].get() else '0',
            int(self.mod_intensity['A'].get()),
            int(self.mod_intensity['B'].get()),
            int(self.mod_intensity['C'].get()),
            int(self.mod_intensity['D'].get()),
        ]
        self.serial_manager.send_command('MODULATOR', *mod_cmd)
        
        # Send DETECTOR command
        det_cmd = [
            self.detector_sensitivity.get(),
            self.detector_gain.get()
        ]
        self.serial_manager.send_command('DETECTOR', *det_cmd)
    
    def _update_configuration(self):
        """Send configuration to device."""
        if not self.serial_manager.is_connected:
            messagebox.showwarning("Warning", "Not connected to device!")
            return
        
        self._send_configuration_commands()
    
    def _process_messages(self):
        """Process incoming messages from serial port."""
        while self.running:
            try:
                msg = self.serial_manager.message_queue.get(timeout=0.1)
                parsed = self.serial_manager.parse_update_message(msg)
                if parsed:
                    self.last_update = parsed
                    # Trigger UI update on main thread
                    self.root.after(0, self._update_display)
                    self.root.after(0, lambda: self._update_plot(from_new_data=True))
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Message processing error: {e}")
                break
    
    def _update_display(self):
        """Update numerical displays with last received data.
        
        Converts uV to mV and uA to mA, formats to 1 decimal place.
        Converts detector_out_of_range flag to 'In range' or 'OUT OF RANGE' with red color.
        """
        if not self.last_update:
            return
        
        data = self.last_update
        
        # Unit conversion factors
        uV_to_mV = 1000.0
        uA_to_mA = 1000.0
        
        # Fields to convert
        voltage_fields = ['voltage_a', 'voltage_b', 'voltage_c', 'voltage_d']
        current_fields = ['current_a', 'current_b', 'current_c', 'current_d']
        mod_amp_fields = ['mod_amp_a', 'mod_amp_b', 'mod_amp_c', 'mod_amp_d']
        
        # Update all display fields
        for key, var in self.display_labels.items():
            value = data.get(key, "N/A")
            
            # Special handling for detector out of range flag
            if key == 'detector_out_of_range':
                if isinstance(value, (int, float)):
                    if value == 1:
                        display_text = "OUT OF RANGE"
                        color = nord_red
                    else:
                        display_text = "In range"
                        color = nord_fg
                    var.set(display_text)
                    # Update the label widget color
                    if key in self.display_label_widgets:
                        self.display_label_widgets[key].config(foreground=color)
                else:
                    var.set(str(value))
            elif isinstance(value, (int, float)):
                # Apply unit conversions
                if key in voltage_fields:
                    value = value / uV_to_mV
                elif key in current_fields or key in mod_amp_fields:
                    value = value / uA_to_mA
                # Format to 1 decimal place
                var.set(f"{value:.1f}")
            else:
                var.set(str(value))
    
    def _add_new_data(self):
        """Add new data from last update to buffer."""
        if not self.last_update:
            return
        
        data = self.last_update
        
        # Add new data points
        self.sample_count += 1
        
        # Get DUT response values
        dut_a = data.get('dut_response_a', 0.0)
        dut_b = data.get('dut_response_b', 0.0)
        dut_c = data.get('dut_response_c', 0.0)
        dut_d = data.get('dut_response_d', 0.0)
        
        # Add to data lists
        self.dut_a_data.append(dut_a)
        self.dut_b_data.append(dut_b)
        self.dut_c_data.append(dut_c)
        self.dut_d_data.append(dut_d)
        
        # Trim to max_samples (always keep 10000 in buffer)
        if len(self.dut_a_data) > self.max_samples:
            self.dut_a_data = self.dut_a_data[-self.max_samples:]
            self.dut_b_data = self.dut_b_data[-self.max_samples:]
            self.dut_c_data = self.dut_c_data[-self.max_samples:]
            self.dut_d_data = self.dut_d_data[-self.max_samples:]
            self.sample_count = self.max_samples
    
    def _update_plot(self, from_new_data=False):
        """Update plot with current buffer data.
        
        Args:
            from_new_data: If True, also add new data to buffer before plotting
        """
        if from_new_data:
            self._add_new_data()
        
        if not self.dut_a_data:
            return
        
        # Get number of samples to display from slider
        num_display = self.display_samples.get()
        
        # Use only the last num_display samples for plotting
        start_idx = max(0, len(self.dut_a_data) - num_display)
        
        plot_a = self.dut_a_data[start_idx:]
        plot_b = self.dut_b_data[start_idx:]
        plot_c = self.dut_c_data[start_idx:]
        plot_d = self.dut_d_data[start_idx:]
        
        # Use relative x-axis matching actual data length to prevent replication
        actual_display = len(plot_a)
        x_data = list(range(actual_display))
        
        self.line_a.set_data(x_data, plot_a)
        self.line_b.set_data(x_data, plot_b)
        self.line_c.set_data(x_data, plot_c)
        self.line_d.set_data(x_data, plot_d)
        
        # Set Y-axis scale based on mode
        scale_mode = self.y_scale_mode.get()
        self.ax.set_yscale(scale_mode)
        
        # Adjust view
        self.ax.relim()
        self.ax.autoscale_view(scaley=True)
        
        # Apply tight layout with padding to prevent label clipping on resize
        self.fig.tight_layout(pad=3.0)
        
        # Redraw canvas
        self.canvas.draw()
    
    def _start_update_timer(self):
        """Start timer for periodic UI updates."""
        # Update displays periodically even if no new data
        self.root.after(100, self._periodic_update)
    
    def _periodic_update(self):
        """Periodic update check."""
        # This allows UI to update even without serial data
        self.root.after(100, self._periodic_update)
    
    def _on_close(self):
        """Handle window close."""
        self.running = False
        self.serial_manager.disconnect()
        self.root.quit()
        self.root.destroy()


def main():
    """Main entry point."""
    root = tk.Tk()
    app = LantanGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
