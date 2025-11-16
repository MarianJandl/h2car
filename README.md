# Telemetry app 
## To do: 

- Log 
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

### Current newest feature:
- Docs tab to view documentation files from docs/ directory

### Key bindings
- To connect to a device press `c` and choose between simulation data for debugging or serial option where you specify the port and baudrate of the device.
- To disconnect from data stream press `ctrl+d`.
- To quit the app press `ctrl+q` and confirm in dialog window.
- To open textual palette press `ctrl+p`.


## Features

- Real-time dashboard with all important data
- Statistics dashboard with min/max/avg measured values
- Real-time log
- Saving the log to the file in logs/ folder
- Error status with suggested solution
- Variety of color themes

