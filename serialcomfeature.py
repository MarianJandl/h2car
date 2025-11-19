import serial
import sys
import os
import datetime
import time
from serial.serialutil import SerialException

RECONNECT_DELAY = 3  # seconds


def ensure_log_dir():
    if not os.path.exists("./logs"):
        os.makedirs("./logs")


def create_log_file():
    """Create a unique log file for each session."""
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    k = 0

    while True:
        path = f"./logs/rawdatalog{date_str}_{k}.txt"
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(f"--- New session started at {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
            print("info:Created log file:", os.path.basename(path))
            return path
        k += 1


def connect(port, baudrate):
    """Try to open serial port. Return None if failed."""
    try:
        ser = serial.Serial(port, baudrate, timeout=1)
        print(f"info:Connected to: {ser.name}")
        return ser
    except SerialException as e:
        print(f"info: Connection failed: {e}")
        return None


def main():
    if len(sys.argv) < 3:
        print("Usage: python logger.py <PORT> <BAUDRATE>")
        sys.exit(1)

    port = sys.argv[1]
    baudrate = int(sys.argv[2])

    print("info:Starting serial communication...")
    print(f"info:port={port} baudrate={baudrate}")

    ensure_log_dir()
    logfile = create_log_file()

    ser = None

    try:
        while True:
            # Connect if not connected
            if ser is None:
                ser = connect(port, baudrate)
                if ser is None:
                    print(f"info:Retrying in {RECONNECT_DELAY} seconds...")
                    time.sleep(RECONNECT_DELAY)
                    continue  # try again

            try:
                # Read incoming data
                if ser.in_waiting > 0:
                    raw = ser.readline().decode("utf-8", errors="ignore").strip()
                    if raw:
                        print("data:", raw)
                        with open(logfile, "a") as f:
                            f.write(raw + "\n")
                        sys.stdout.flush()

            except SerialException:
                print("info:Lost connection! Attempting to reconnect...")
                try:
                    ser.close()
                except:
                    pass
                ser = None
                time.sleep(RECONNECT_DELAY)

    except KeyboardInterrupt:
        print("\ninfo:Exiting...")

    finally:
        if ser:
            ser.close()


if __name__ == "__main__":
    main()