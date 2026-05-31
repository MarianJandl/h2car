### Changing how telemetry data is read

The serial and simulated readers run in-process (no separate Python process is
spawned). Edit `bin/datasource.py` — `SerialSource` reads the serial port,
`SimulatedSource` generates debug data. The app picks between them in
`handle_connection` in `telemetry.py`.
