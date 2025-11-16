import serial
import sys
import os
import datetime

print("info:Starting serial communication...")
print("info:port: ", sys.argv[1], "baudrate: ",sys.argv[2])
try:
    ser = serial.Serial(str(sys.argv[1]), int(sys.argv[2]), timeout=1)
except Exception as e:
    print(f"info:{e}")
    sys.exit(1)
    

print(f"info:Connected to: {ser.name}")

try:
    if not os.path.exists("./logs/"):
        os.mkdir("logs")
except Exception as e:
    print(f"info: {e}")
x = datetime.datetime.now().strftime("%Y%m%d")
k = 0

print("info:logging test")

while os.path.exists(f"./logs/rawdatalog{x}_{k}.txt"):
    k += 1

with open(f"./logs/rawdatalog{x}_{k}.txt", "a") as f:
    f.write(f"--- New session started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")

print("info:Created log file:", f"rawdatalog{x}_{k}.txt")

try:
    while True:
        if ser.in_waiting > 0:
            data = ser.readline().decode('utf-8', errors='ignore').strip()
            if data:
                print("data:",data)
                with open(f"./logs/rawdatalog{x}_{k}.txt", "a") as f:
                    f.write(data + "\n")
                sys.stdout.flush()
except KeyboardInterrupt:   
    print("info:Exiting...")
finally:
    ser.close()