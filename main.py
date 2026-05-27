#!/usr/bin/env python3
"""
Lantan GUI Application
Controls an external USB device via CDC serial port with live data visualization.
"""

import sys
import threading
import queue
import serial
import serial.tools.list_ports
from datetime import datetime

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

import tkinter as tk
from tkinter import ttk, messagebox


class SerialManager:
    """Manages serial communication with the device."""
    
    def __init__(self):
        self.serial_conn = None
        self.is_connected = False
        self.message_queue = queue.Queue()
        self.running = False
        self.reader_thread = None
        
    def list_ports(self):
        """Return list of available serial ports."""
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
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
                    buffer += data
                    
                    # Parse complete messages (end with \r\n)
                    while '\r\n' in buffer:
                        msg, buffer = buffer.split('\r\n', 1)
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
            }
        except (ValueError, IndexError) as e:
            print(f"Failed to parse UPDATE message: {e}")
            return None


class LantanGUI:
    """Main GUI application for Lantan device control."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Lantan GUI")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Data storage
        self.serial_manager = SerialManager()
        self.max_samples = 200
        self.sample_count = 0
        self.time_data = []
        self.dut_a_data = []
        self.dut_b_data = []
        self.dut_c_data = []
        self.dut_d_data = []
        
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
            'A': tk.DoubleVar(value=50.0),
            'B': tk.DoubleVar(value=50.0),
            'C': tk.DoubleVar(value=50.0),
            'D': tk.DoubleVar(value=50.0)
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
    
    def _create_ui(self):
        """Create all UI components."""
        # Top menu ribbon frame
        self.menu_frame = ttk.Frame(self.root)
        self.menu_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # Left panel for numerical displays and configuration
        self.left_panel = ttk.Frame(self.root)
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)
        
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
            state="readonly"
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
        
        # Connection status label
        self.status_label = ttk.Label(self.menu_frame, text="Disconnected")
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Refresh ports on startup
        self._refresh_ports()
    
    def _create_graph_area(self):
        """Create graphing area with matplotlib."""
        # Graph frame
        graph_frame = ttk.Frame(self.root)
        graph_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create matplotlib figure
        self.fig, self.ax = plt.subplots(figsize=(10, 6), dpi=100)
        self.fig.tight_layout()
        
        # Initialize data
        self.time_data = list(range(self.max_samples))
        self.dut_a_data = [0.0] * self.max_samples
        self.dut_b_data = [0.0] * self.max_samples
        self.dut_c_data = [0.0] * self.max_samples
        self.dut_d_data = [0.0] * self.max_samples
        
        # Plot lines
        self.line_a, = self.ax.plot([], [], 'r-', label='DUT Response A')
        self.line_b, = self.ax.plot([], [], 'g-', label='DUT Response B')
        self.line_c, = self.ax.plot([], [], 'b-', label='DUT Response C')
        self.line_d, = self.ax.plot([], [], 'm-', label='DUT Response D')
        
        self.ax.set_xlabel('Sample')
        self.ax.set_ylabel('Intensity (a.u.)')
        self.ax.set_title('DUT Responses')
        self.ax.legend()
        self.ax.grid(True)
        
        # Embed in Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Optional toolbar
        self.toolbar = NavigationToolbar2Tk(self.canvas, graph_frame)
        self.toolbar.update()
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    
    def _create_numerical_displays(self):
        """Create numerical displays section."""
        num_frame = ttk.LabelFrame(
            self.left_panel,
            text="Numerical Displays",
            labelanchor=tk.N
        )
        num_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        # Field names and values for display
        self.display_labels = {}
        display_fields = [
            ('Power Good', 'power_good'),
            ('Channel A Active', 'channel_a_active'),
            ('Channel B Active', 'channel_b_active'),
            ('Channel C Active', 'channel_c_active'),
            ('Channel D Active', 'channel_d_active'),
            ('Voltage A (uV)', 'voltage_a'),
            ('Voltage B (uV)', 'voltage_b'),
            ('Voltage C (uV)', 'voltage_c'),
            ('Voltage D (uV)', 'voltage_d'),
            ('Current A (uA)', 'current_a'),
            ('Current B (uA)', 'current_b'),
            ('Current C (uA)', 'current_c'),
            ('Current D (uA)', 'current_d'),
            ('Mod Amp A (uA)', 'mod_amp_a'),
            ('Mod Amp B (uA)', 'mod_amp_b'),
            ('Mod Amp C (uA)', 'mod_amp_c'),
            ('Mod Amp D (uA)', 'mod_amp_d'),
            ('DUT Resp A', 'dut_response_a'),
            ('DUT Resp B', 'dut_response_b'),
            ('DUT Resp C', 'dut_response_c'),
            ('DUT Resp D', 'dut_response_d'),
            ('Det. Sensitivity', 'detector_sensitivity'),
            ('Det. Gain', 'detector_gain'),
        ]
        
        # Create 2-column layout
        for i, (label_text, field_key) in enumerate(display_fields):
            row = i // 2
            col = i % 2
            
            # Label
            label = ttk.Label(num_frame, text=label_text + ":")
            label.grid(row=row, column=col*2, sticky=tk.W, padx=5, pady=2)
            
            # Value display
            value_var = tk.StringVar(value="N/A")
            value_label = ttk.Label(num_frame, textvariable=value_var)
            value_label.grid(row=row, column=col*2+1, sticky=tk.E, padx=5, pady=2)
            
            self.display_labels[field_key] = value_var
    
    def _create_configuration_panel(self):
        """Create configuration panel."""
        config_frame = ttk.LabelFrame(
            self.left_panel,
            text="Configuration",
            labelanchor=tk.N
        )
        config_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        # Channel enable checkboxes
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
            cb.grid(row=1, column=i, sticky=tk.W, padx=5, pady=2)
        
        # Detector sensitivity
        ttk.Label(config_frame, text="Detector Sensitivity:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=2
        )
        sens_combo = ttk.Combobox(
            config_frame,
            textvariable=self.detector_sensitivity,
            values=[1, 2, 3, 4],
            state="readonly",
            width=5
        )
        sens_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Detector gain
        ttk.Label(config_frame, text="Detector Gain:").grid(
            row=3, column=0, sticky=tk.W, padx=5, pady=2
        )
        gain_combo = ttk.Combobox(
            config_frame,
            textvariable=self.detector_gain,
            values=[1, 2, 3, 4],
            state="readonly",
            width=5
        )
        gain_combo.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        
        # Modulation intensity sliders
        ttk.Label(config_frame, text="Modulation Intensity:").grid(
            row=4, column=0, columnspan=2, sticky=tk.W, padx=5, pady=2
        )
        
        for i, ch in enumerate(['A', 'B', 'C', 'D']):
            ttk.Label(config_frame, text=f"{ch}:").grid(
                row=5, column=i, sticky=tk.W, padx=5, pady=2
            )
            slider = ttk.Scale(
                config_frame,
                from_=0,
                to=100,
                variable=self.mod_intensity[ch],
                orient=tk.HORIZONTAL,
                length=100
            )
            slider.grid(row=6, column=i, sticky=tk.W, padx=5, pady=2)
            
            value_label = ttk.Label(
                config_frame,
                textvariable=self.mod_intensity[ch]
            )
            value_label.grid(row=7, column=i, sticky=tk.W, padx=5, pady=2)
        
        # Update configuration button
        update_btn = ttk.Button(
            config_frame,
            text="Update Configuration",
            command=self._update_configuration
        )
        update_btn.grid(
            row=8, column=0, columnspan=4, pady=10
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
            self.serial_manager.disconnect()
            self.connect_btn.config(text="Connect")
            self.status_label.config(text="Disconnected")
        else:
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "No port selected!")
                return
            
            if self.serial_manager.connect(port):
                self.connect_btn.config(text="Disconnect")
                self.status_label.config(text=f"Connected to {port}")
            else:
                messagebox.showerror("Error", f"Failed to connect to {port}")
    
    def _update_configuration(self):
        """Send configuration to device."""
        if not self.serial_manager.is_connected:
            messagebox.showwarning("Warning", "Not connected to device!")
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
        
        messagebox.showinfo("Info", "Configuration updated!")
    
    def _process_messages(self):
        """Process incoming messages from serial port."""
        while self.running:
            try:
                msg = self.serial_manager.message_queue.get(timeout=0.1)
                parsed = self.serial_manager.parse_update_message(msg)
                if parsed and hasattr(self, 'root') and self.root.winfo_exists():
                    self.last_update = parsed
                    # Trigger UI update on main thread
                    self.root.after(0, self._update_display)
                    self.root.after(0, self._update_plot)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Message processing error: {e}")
                break
    
    def _update_display(self):
        """Update numerical displays with last received data."""
        if not self.last_update:
            return
        
        data = self.last_update
        
        # Update all display fields
        for key, var in self.display_labels.items():
            value = data.get(key, "N/A")
            if isinstance(value, float):
                var.set(f"{value:.4f}")
            else:
                var.set(str(value))
    
    def _update_plot(self):
        """Update plot with new data."""
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
        
        # Trim to max_samples
        if len(self.dut_a_data) > self.max_samples:
            self.dut_a_data = self.dut_a_data[-self.max_samples:]
            self.dut_b_data = self.dut_b_data[-self.max_samples:]
            self.dut_c_data = self.dut_c_data[-self.max_samples:]
            self.dut_d_data = self.dut_d_data[-self.max_samples:]
            self.sample_count = self.max_samples
        
        # Update plot data
        x_data = list(range(len(self.dut_a_data)))
        
        self.line_a.set_data(x_data, self.dut_a_data)
        self.line_b.set_data(x_data, self.dut_b_data)
        self.line_c.set_data(x_data, self.dut_c_data)
        self.line_d.set_data(x_data, self.dut_d_data)
        
        # Adjust view
        self.ax.relim()
        self.ax.autoscale_view(scaley=True)
        
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
