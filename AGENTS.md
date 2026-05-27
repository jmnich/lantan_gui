# General information
This is a 'Lantan GUI' application. It controls an external USB device that communicates via a CDC class (Serial port).
Device sends regular updates with data that is then presented to the user in the application.
The application can send multiple control commands when user modifies settings. 

# Communication with the device
Communication protocol is described in file: SERIAL_COMMUNICATION_PROTOCOL.md. 
Follow it exactly. 

# GUI Description
GUI is split into 4 sections: 
1) top menu ribbon
2) graphing area
3) numerical displays
4) configuration panel

## 1. Top menu ribbon
The menu ribbon has the following options:
1) Droplist of connected serial devices: allows to select a serial port to connect to.
2) Refresh button: populates the droplist of connected devices.
3) Connect/Disconnect button: It either connects or disconnects the device. Button text changes accordingly.
4) Clear button: clears all data currently in the buffer

## 2. Graphing area
This is the largest area in the app. Located to the right of Numerical displays and Configuration panel and below the Top menu ribbon. It contains a single plot with 4 data series, which show the following 4 fields
1) dut response A: intensity in arbitrary unit
2) dut response B: intensity in arbitrary unit
3) dut response C: intensity in arbitrary unit
4) dut response D: intensity in arbitrary unit
as documented in SERIAL_COMMUNICATION_PROTOCOL.md.

The plot live updates and scrolls as new data comes in with UPDATE messages. 
It contains last 200 samples. 
Y-axis autoranges to fit all data.
X-axis has constant scale that fits last 200 samples. 

## 3. Numerical displays
This is a stack of labels and fields, looking like a 2-column table, showing data sent from the device in the last update message.
It contains all data fields from UPDATE messages.

## 4. Configuration panel
A panel located below "Numerical displays", matching its witdh. It contains:
- 4 check boxes to enable/disable channels A-D
- droplist with detector sensitivity (1 - 4)
- droplist with detector gain (1 - 4)
- 4 sliders for modulation intensity for channels A-D (scaled from 0 to 100%)
- Button 'Update configuration' that sends Modulator and Detector configuration commands based on current settings in the panel. Commands are described in SERIAL_COMMUNICATION_PROTOCOL.md. 
