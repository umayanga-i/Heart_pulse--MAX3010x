# ESP32 + MAX30102 PPG Research Logger

Records raw red/IR PPG data from a MAX30102 sensor using an ESP32, then analyzes it offline in Python (heart rate, SDNN, RMSSD, waveform plot).

## Files

| File | Purpose |
|---|---|
| `esp32_max30102_logger.ino` | ESP32 firmware, streams raw samples at 200 Hz over serial |
| `logger.py` | Saves the serial stream to a CSV file |
| `analyze.py` | Filters the signal, detects beats, computes metrics, plots the waveform |

## Wiring

| MAX30102 | ESP32 |
|---|---|
| VIN | 3V3 |
| GND | GND |
| SDA | GPIO21 |
| SCL | GPIO22 |
| INT | GPIO19 (optional, not used by the current firmware) |

## 1. Upload the firmware

1. In Arduino IDE, install the library **SparkFun MAX3010x Pulse and Proximity Sensor Library**.
2. Select your ESP32 board and port.
3. Upload `esp32_max30102_logger.ino`.
4. Check the signal in Serial Plotter (921600 baud). IR should be about 50,000-200,000 with a visible pulse. If it reaches 262143, lower `ledBrightness`. If it is below about 20,000, raise it or check finger placement.
5. **Close the Serial Monitor/Plotter** before running the logger (only one program can use the port).

## 2. Python setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install pyserial numpy scipy pandas matplotlib
```

On Windows, activate with `venv\Scripts\activate` instead.

## 3. Record data

```bash
python3 logger.py /dev/ttyUSB0 subject01 60
```

Arguments: `<serial port> <output name> <seconds>`. This saves `subject01.csv`.

- Linux port names: `/dev/ttyUSB0` or `/dev/ttyACM0`. Windows: `COM5`.
- If you get a permission error on Linux: `sudo usermod -a -G dialout $USER`, then log out and back in.

## 4. Analyze

```bash
python analyze.py subject01.csv
```

Output:

- Dropped-sample check (index gaps, sensor time vs host time)
- Signal quality warnings (saturation, no finger)
- Mean HR, SDNN, RMSSD
- Plot of the filtered PPG waveform with detected peaks

## Recording tips

- Seated, still, finger relaxed with light, steady pressure.
- Avoid bright ambient light on the sensor.
- Record at least a few minutes per subject for stable HRV estimates.
- Keep the setup battery-powered or use a USB isolator when connected to a person.

## Research notes

- The MAX30102 is a breakout module, not a medical device.
- PPG gives pulse rate variability (PRV), which is not identical to ECG-based HRV.
- SpO2 from this module is uncalibrated and not suitable for clinical claims.
- Validate against a reference (ECG or certified pulse oximeter) and report error, for example with Bland-Altman analysis.
- Obtain ethics/IRB approval and informed consent before recording real subjects.
