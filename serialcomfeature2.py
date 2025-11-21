#!/usr/bin/env python3
"""
Robust serial logger with reliable auto-reconnect.

Usage:
    python logger.py <PORT> <BAUDRATE> [--timestamp-lines]

Example:
    python logger.py COM3 115200 --timestamp-lines
"""

import serial
import sys
import os
import datetime
import time
from serial.serialutil import SerialException
import serial.tools.list_ports

KEEP_ALIVE_SLEEP = 0.05       # sleep between empty reads to avoid busy-looping
BASE_RECONNECT_DELAY = 1.0    # initial reconnect delay (seconds)
MAX_RECONNECT_DELAY = 30.0    # maximum reconnect delay (seconds)


def ensure_log_dir():
    os.makedirs("./logs", exist_ok=True)


def create_log_file():
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


def port_is_available(port_name):
    """Return True if the given port name appears among system ports."""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        # Compare using device path (e.g. 'COM3' or '/dev/ttyUSB0')
        if p.device == port_name:
            return True
    return False


def try_open(port, baudrate):
    """Try to open the serial port. Return opened Serial or raise."""
    return serial.Serial(port, baudrate, timeout=1)


def log_to_file(path, line, timestamp_lines=False):
    if timestamp_lines:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {line}"
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    if len(sys.argv) < 3:
        print("Usage: python serialcomfeature2.py <PORT> <BAUDRATE> [--timestamp-lines]")
        sys.exit(1)

    port = sys.argv[1]
    baudrate = int(sys.argv[2])
    timestamp_lines = "--timestamp-lines" in sys.argv

    print("info:Starting serial communication...")
    print(f"info:port={port} baudrate={baudrate}")

    ensure_log_dir()
    logfile = create_log_file()

    ser = None
    reconnect_delay = BASE_RECONNECT_DELAY

    try:
        while True:
            # If not connected, attempt to (re)connect
            if ser is None or not getattr(ser, "is_open", False):
                if not port_is_available(port):
                    print(f"info:Port {port} not visible to OS. Retrying in {reconnect_delay:.1f}s...")
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(MAX_RECONNECT_DELAY, reconnect_delay * 1.5)
                    continue

                try:
                    ser = try_open(port, baudrate)
                    # Reset backoff on success
                    reconnect_delay = BASE_RECONNECT_DELAY
                    print(f"info:Connected to {ser.name}")
                except (SerialException, OSError) as e:
                    print(f"info:Failed to open {port}: {e!s}. Retrying in {reconnect_delay:.1f}s...")
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(MAX_RECONNECT_DELAY, reconnect_delay * 1.5)
                    ser = None
                    continue

            # Reading loop — stays here while connection is healthy
            try:
                # Use readline() which respects timeout and does not rely on in_waiting
                raw = ser.readline()
                if not raw:
                    # no data, small sleep to avoid busy loop
                    time.sleep(KEEP_ALIVE_SLEEP)
                    continue

                try:
                    decoded = raw.decode("utf-8", errors="ignore").strip()
                except Exception:
                    # fallback: show repr if decode fails entirely
                    decoded = repr(raw)

                if decoded:
                    print("data:", decoded)
                    log_to_file(logfile, decoded, timestamp_lines)
                    sys.stdout.flush()

            except (SerialException, OSError) as e:
                # Most robust way to recover: close object, mark ser=None, and loop to reconnect.
                print(f"info:Lost connection or read error: {e!s}")
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
                print(f"info:Will attempt reconnect in {reconnect_delay:.1f}s...")
                time.sleep(reconnect_delay)
                reconnect_delay = min(MAX_RECONNECT_DELAY, reconnect_delay * 1.5)
                continue

            except Exception as e:
                # Catch-all to avoid script crash; log and continue reading.
                print(f"warning:Unexpected error during read: {e!s}")
                time.sleep(0.2)
                continue

    except KeyboardInterrupt:
        print("\ninfo:Exiting (KeyboardInterrupt)...")

    finally:
        if ser:
            try:
                ser.close()
            except Exception:
                pass
        print("info:Closed serial (if it was open).")


if __name__ == "__main__":
    main()
