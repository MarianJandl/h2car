import serial
import sys
import os
import datetime


print("info:Starting serial communication...")
print("info:port: ", sys.agrv[1], "baudrate: ",sys.argv[2])

ser = serial.Serial(str(sys.argv[1]), int(sys.argv[2]), timeout=1)

print(f"info:Connected to: {ser.name}")

if not os.path.exists("logs"):
    os.mkdir("logs")

x = datetime.datetime.now().strftime("%Y%m%d")
k = 0


while os.path.exists(f"logs/rawdatalog{x}_{k}.txt"):
    k += 1
with open(f"logs/rawdatalog{x}_{k}.txt", "a") as f:
    f.write(f"--- New session started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
try:
    while True:
        if ser.in_waiting > 0:
            data = ser.readline().decode('utf-8', errors='ignore').strip()
            if data:
                print("data:",data)
                f.write(data + "\n")
                sys.stdout.flush()
except KeyboardInterrupt:   
    print("info:Exiting...")
finally:
    ser.close()