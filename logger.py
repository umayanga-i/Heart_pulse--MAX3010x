# Usage: python logger.py /dev/ttyUSB0 subject01 60     (port, name, seconds)
import sys, time, serial

port, name, secs = sys.argv[1], sys.argv[2], float(sys.argv[3])
ser = serial.Serial(port, 921600, timeout=1)
time.sleep(2); ser.reset_input_buffer()

t0, n, other = time.time(), 0, []
with open(f"{name}.csv", "w") as f:
    f.write("host_time,idx,red,ir\n")
    while time.time() - t0 < secs:
        line = ser.readline().decode(errors="ignore").strip()
        parts = line.split(",")
        if len(parts) == 3 and parts[0].isdigit():
            f.write(f"{time.time():.4f},{line}\n"); n += 1
            if n % 200 == 0:
                print(f"\r{time.time()-t0:5.1f}s  {n} samples", end="", flush=True)
        elif line:
            other.append(line)
            if len(other) <= 5: print("Device says:", line)

print(f"\nsaved {name}.csv with {n} samples")
if n == 0:
    print("NO DATA captured. Check: firmware uploaded? 'ERROR: MAX30102 not found' above? "
          "wiring SDA/SCL? baud 921600 in the .ino?")
