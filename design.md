1. Chrome extension
- monitors for player name changes
- sends the entire player name list to the python webserver on port 8000

2. Python webserver (or change to Go)
- listens for player names on port 8000
- writes its changes to a csv file
- notifies the main program when the changes are written
