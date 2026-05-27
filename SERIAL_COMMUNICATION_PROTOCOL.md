# Serial Communication Protocol Documentation

**Application:** Lantan GUI  
**Interface:** Serial Port (RS-232/RS-485/USB)  
**Document Version:** 1.0  

---

## 📋 Overview

### Purpose
This document defines the command and response protocol between the [Python GUI Application] and the [DEVICE_NAME] device over serial communication.

### Scope
- Command message formats
- Response message formats
- Error handling
- Communication parameters
- Data encoding and framing

---

## 🔌 Serial Connection Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Baud Rate** | [115200] | |
| **Data Bits** | [8] | |
| **Parity** | [None] | |
| **Stop Bits** | [1] | |


Note that this is a USB CDC device, so these parameters will work but they won't have any effect.

---


## Message Structure
All messages are ASCII encoded. The start with CMD ID and end with '\r\n'. Separator sign is '|'.

### direction: serial device -> PC
There is only one message in this direction. Device constantly sends update frames in the following format (dut means 'device under test', ABCD indicates channel):
UPDATE|<power good flag>|<channel A active>|<channel B active>|<channel C active>|<channel D active>|<dut voltage A>|<dut voltage B>|<dut voltage C>|<dut voltage D>|<dut current A>|<dut current B>|<dut current C>|<dut current D>|<dut modulation amplitude A>|<dut modulation amplitude B>|<dut modulation amplitude C>|<dut modulation amplitude D>|<dut response A>|<dut response B>|<dut response C>|<dut response D>|<detector sensitivity>|<detector gain>\r\n

### direction: PC -> serial device
Commands start with an ID made of letters and then is followed by numerical arguments. The number and meaning of arguements depends on the ID.
<CMD ID>|<arg1>|<arg2>|...|<argN>\r\n

---

## 📚 Command Catalog

### direction: serial device -> PC

#### 1. Update message from the device
CMD ID: UPDATE 
power good flag: '0' - bad, '1' - good
channel A active: '0' - off, '1' - on
channel B active: '0' - off, '1' - on
channel C active: '0' - off, '1' - on
channel D active: '0' - off, '1' - on
dut voltage A: voltage in uV
dut voltage B: voltage in uV
dut voltage C: voltage in uV
dut voltage D: voltage in uV
dut current A: current in uA
dut current B: current in uA
dut current C: current in uA
dut current D: current in uA
dut modulation amplitude A: current in uA
dut modulation amplitude B: current in uA
dut modulation amplitude C: current in uA
dut modulation amplitude D: current in uA
dut response A: intensity in arbitrary unit
dut response B: intensity in arbitrary unit
dut response C: intensity in arbitrary unit
dut response D: intensity in arbitrary unit
detector sensitivity: integer value (1,2,3 or 4)
detector gain: integer value (1,2,3 or 4)

### direction: PC -> serial device

#### 1. Modulator configuration command
CMD ID: MODULATOR
channel A active: '0' - off, '1' - on
channel B active: '0' - off, '1' - on
channel C active: '0' - off, '1' - on
channel D active: '0' - off, '1' - on
dut modulation amplitude A: in %, 0-100%
dut modulation amplitude B: in %, 0-100%
dut modulation amplitude C: in %, 0-100%
dut modulation amplitude D: in %, 0-100%

#### 2. Detector configuration command
CMD ID: DETECTOR
detector sensitivity: integer value (1,2,3 or 4)
detector gain: integer value (1,2,3 or 4)

---

## Timing Requirements
The protocol is asynchronous. There are no "challange reponse" transactions, therefore no timing requirements.

---

### Message Parsing Tips
- Always validate CMD ID before parsing
- Silently ignore messages with broken ID
- Silently ignore messages if arguments don't parse correctly or throw exceptions

---

