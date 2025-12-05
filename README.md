# Telemetry app 
## To do: 
- Better documentation and guide
- Improve race tracker calculation and connect it to incoming data
- Pit feature in race tracker - stops battery/stick consumption
- Redflag a tak proste kdy to jezdi a kdy je pusteny zavod nezavisle na sobe
- statistics time stamps
- Racetracker resets after stop
- procenta baterek?
- graf prumernych hodnot za 10s treba: dodelat cteni nejnovejsiho logu
- MAKE IT MORE CLEAN






## How to use this app

- Clone this repository:
```
git clone https://github.com/MarianJandl/h2car
```
- Install requirments:
```
pip install -r requirments.txt
```
- Run the app:
```
python telemetry1.py
```
or
```
python telemetry1feature.py
```
to test newest features
- To update to the latest version
```
git pull upstream main
```

### Current newest feature:
- Race tracker

### Key bindings
#### Connection control
- To connect to a device press `c` and choose between simulation data for debugging or serial option where you specify the port and baudrate of the device.
- To disconnect from data stream press `ctrl+d`.

#### General app control
- To quit the app press `ctrl+q` and confirm in dialog window.
- To open textual palette press `ctrl+p`.

#### Race Tracker control
- To start/stop press `r`
- To reset press `ctrl+r`
- To log hydrostick change press `ctrl+s`
- To log battery change press `ctrl+b`
- Race tracker config `./config/race_config.json`

#### Command line
- Press `m` to open the command line
- list of commands is lower in the Guide section

### Guide / some tips
#### Commands
- `log` - writes to the log
- `napomenuti` - takes one argument F (Filip) or V (Vitek)
- `plot` - plots the data from log file, you can use these arguments:
    - `-f / --file`: to specify log file
    - `-l / --last`: number of last seconds you want to plot
    - `-v / --vars`: to specify which variales to plot

#### Pro zmenu souboru ktery cte bluetooth: spousti se z telemetry1feature.py:
radek 588: `self.data_stream = subprocess.Popen(["python", "serialcomfeature.py", conn_port, conn_baudrate], stdout=subprocess.PIPE, text=True)`
zmenit nazev souboru



## Features

- Real-time dashboard with all important data
- Statistics dashboard with min/max/avg measured values
- Race tracker with estimated times to change hydrostick/battery
- Race tracker configuration file
- Real-time log
- Saving the log to the file in logs/ folder
- Docs tab to view documentation files from docs/ directory
- Error status with suggested solution
- Variety of color themes

