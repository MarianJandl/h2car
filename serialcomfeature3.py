import serial
import sys
import os
import datetime
import time

RECONNECT_DELAY = 2  # seconds between reconnection attempts
DATA_TIMEOUT = 30    # seconds of no data before considering connection stale

def get_log_file():
    """Create logs directory and return a unique log filename."""
    try:
        os.makedirs("./logs/", exist_ok=True)
    except Exception as e:
        print(f"info: {e}")
    
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    k = 0
    while os.path.exists(f"./logs/rawdatalog{date_str}_{k}.txt"):
        k += 1
    
    log_path = f"./logs/rawdatalog{date_str}_{k}.txt"
    with open(log_path, "a") as f:
        f.write(f"--- Session started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    
    print(f"info:Created log file: rawdatalog{date_str}_{k}.txt")
    return log_path

def connect_serial(port, baudrate):
    """Attempt to connect to serial port, returns None on failure."""
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        print(f"info:Connected to: {ser.name}")
        return ser
    except Exception as e:
        print(f"info:Connection failed: {e}")
        return None

def main():
    if len(sys.argv) < 3:
        print("Usage: python serialcomfeature3.py <port> <baudrate>")
        sys.exit(1)
    
    port = str(sys.argv[1])
    baudrate = int(sys.argv[2])
    
    print("info:Starting serial communication...")
    print(f"info:port: {port}, baudrate: {baudrate}")
    
    log_path = get_log_file()
    ser = None
    last_data_time = None
    
    try:
        while True:
            # Connect if not connected
            if ser is None or not ser.is_open:
                ser = connect_serial(port, baudrate)
                if ser is None:
                    print(f"info:Retrying in {RECONNECT_DELAY}s...")
                    time.sleep(RECONNECT_DELAY)
                    continue
                last_data_time = time.time()
            
            # Try to read data
            try:
                if ser.in_waiting > 0:
                    data = ser.readline().decode('utf-8', errors='ignore').strip()
                    if data:
                        last_data_time = time.time()
                        print(f"data:{data}")
                        with open(log_path, "a") as f:
                            f.write(f"{data}\n")
                        sys.stdout.flush()
                else:
                    # Check for data timeout (optional stale connection detection)
                    if last_data_time and (time.time() - last_data_time > DATA_TIMEOUT):
                        print(f"info:No data for {DATA_TIMEOUT}s, connection may be stale")
                        last_data_time = time.time()  # Reset to avoid spamming
                    time.sleep(0.01)  # Small delay to prevent CPU spinning
                    
            except (serial.SerialException, OSError) as e:
                print(f"info:Serial error: {e}")
                print("info:Attempting to reconnect...")
                with open(log_path, "a") as f:
                    f.write(f"--- Connection lost at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                try:
                    ser.close()
                except:
                    pass
                ser = None
                time.sleep(RECONNECT_DELAY)
                
    except KeyboardInterrupt:
        print("\ninfo:Exiting...")
    finally:
        if ser and ser.is_open:
            ser.close()
        with open(log_path, "a") as f:
            f.write(f"--- Session ended at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        print("info:Cleanup complete")

if __name__ == "__main__":
    main()