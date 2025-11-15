import serial

# Open serial port (adjust baudrate to match your device)
ser = serial.Serial('COM6', 115200, timeout=1)

print(f"Connected to: {ser.name}")

try:
    while True:
        if ser.in_waiting > 0:
            data = ser.readline().decode('utf-8', errors='ignore').strip()
            if data:
                print(data)
except KeyboardInterrupt:
    print("Exiting...")
finally:
    ser.close()