import serial
import sys

print("info:Starting serial communication...")
print("info:port: ", sys.agrv[1], "baudrate: ",sys.argv[2])

ser = serial.Serial(str(sys.argv[1]), int(sys.argv[2]), timeout=1)

print(f"info:Connected to: {ser.name}")

try:
    while True:
        if ser.in_waiting > 0:
            data = ser.readline().decode('utf-8', errors='ignore').strip()
            if data:
                print("data:",data)
except KeyboardInterrupt:
    print("info:Exiting...")
finally:
    ser.close()