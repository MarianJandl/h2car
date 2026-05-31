"""In-process telemetry data sources.

Previously the app spawned a separate Python process (simulation_data.py /
serialcomfeature.py) and parsed its stdout. That second interpreter cost
~20-30 MB of RAM and required `python` to be on PATH. These sources do the
same work in a daemon thread inside the app instead.

Each source pushes lines onto the shared queue using the exact wire format the
UI already understands, so the consuming side (`update_data`) is unchanged:

    "data: Tim:1 Di:0x0 Vbat:7.8 ..."   # one space-separated Key:Value record
    "info: <status message>"
"""

from __future__ import annotations

import datetime
import random
import threading
from pathlib import Path
from queue import Queue


def _new_log_file(prefix: str) -> Path:
    """Create logs/<prefix><date>_<n>.txt, picking an unused n."""
    Path("logs").mkdir(exist_ok=True)
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    k = 0
    while (path := Path("logs") / f"{prefix}{date_str}_{k}.txt").exists():
        k += 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"--- New session started at {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
    return path


class DataSource:
    """Base class: a daemon thread that feeds prefixed lines to a queue."""

    raw_log_prefix = "rawdatalog"

    def __init__(self, queue: Queue):
        self.queue = queue
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._logfile: Path | None = None

    def start(self) -> None:
        self._logfile = _new_log_file(self.raw_log_prefix)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _info(self, msg: str) -> None:
        self.queue.put(f"info: {msg}")

    def _run(self) -> None:  # overridden by subclasses
        raise NotImplementedError


class SimulatedSource(DataSource):
    """Generates random but plausible telemetry once per second."""

    raw_log_prefix = "simrawdatalog"

    def _run(self) -> None:
        tim = 0
        di = 0
        with open(self._logfile, "a", encoding="utf-8") as log:
            while not self._stop.is_set():
                tim += 1
                if random.randint(0, 4) == 3:
                    a = random.randint(0, 25)
                    if 3 <= a <= 7:
                        di = 1
                    elif 7 <= a <= 10:
                        di = 3
                    elif 10 <= a <= 13:
                        di = 8
                    elif 13 <= a <= 15:
                        di = 9
                    elif 15 <= a <= 18:
                        di = 11
                    else:
                        di = 0

                iout = random.random() * 20 + 50
                vbat = random.random() * 2 + 7
                power = round(iout * vbat * 0.1, 2)
                raw = (
                    f"Tim:{tim} Di:{hex(di)} Pwm:0 "
                    f"Vbat:{round(vbat, 2)} Iout:{round(iout, 2)} Pout:{power} "
                    f"Vfc:{round(random.random() * 2 + 7, 2)} Pfc:{power} "
                    f"PfcDes:{power} Tfc:{random.randint(40, 80)}"
                )
                self.queue.put(f"data: {raw}")
                log.write(raw + "\n")
                log.flush()
                self._stop.wait(1)


class SerialSource(DataSource):
    """Reads newline-delimited records from a serial port, with auto-reconnect."""

    raw_log_prefix = "rawdatalog"
    RECONNECT_DELAY = 5  # seconds

    def __init__(self, queue: Queue, port: str, baudrate):
        super().__init__(queue)
        self.port = port
        self.baudrate = int(baudrate)

    def _run(self) -> None:
        import serial
        from serial.serialutil import SerialException

        self._info(f"Starting serial: port={self.port} baudrate={self.baudrate}")
        ser = None
        with open(self._logfile, "a", encoding="utf-8") as log:
            while not self._stop.is_set():
                if ser is None:
                    try:
                        ser = serial.Serial(self.port, self.baudrate, timeout=1)
                        self._info(f"Connected to {ser.name}")
                    except SerialException as e:
                        self._info(f"Connection failed: {e}; retrying in {self.RECONNECT_DELAY}s")
                        self._stop.wait(self.RECONNECT_DELAY)
                        continue

                try:
                    if ser.in_waiting > 0:
                        raw = ser.readline().decode("utf-8", errors="ignore").strip()
                        if raw:
                            self.queue.put(f"data: {raw}")
                            log.write(raw + "\n")
                            log.flush()
                    else:
                        # Idle wait avoids a busy loop pinning a CPU core.
                        self._stop.wait(0.02)
                except SerialException:
                    self._info("Lost connection! Reconnecting...")
                    try:
                        ser.close()
                    except Exception:
                        pass
                    ser = None
                    self._stop.wait(self.RECONNECT_DELAY)

            if ser:
                try:
                    ser.close()
                except Exception:
                    pass
