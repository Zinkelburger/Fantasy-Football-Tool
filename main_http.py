import os
import logging
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import shutil

# Set up logging directory
log_dir = "log"
os.makedirs(log_dir, exist_ok=True)

# Delete all existing .txt files initially
for file_name in os.listdir(log_dir):
    if file_name.endswith(".txt"):
        try:
            os.remove(os.path.join(log_dir, file_name))
        except Exception as e:
            print(f"Error deleting file {file_name}: {e}")

# Delete the existing draft_script.log file if it exists
log_file = os.path.join(log_dir, "draft_script.log")
if os.path.exists(log_file):
    try:
        os.remove(log_file)
    except Exception as e:
        print(f"Error deleting log file {log_file}: {e}")

# Initialize pick.txt with 0
pick_file = os.path.join(log_dir, "pick.txt")
with open(pick_file, "w") as pick:
    pick.write("0")
logging.info("Initialized pick.txt with value 0")

# Set up logging
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Initialize variables
latest_file = None
player_names = set()

# Function to save a new player file with a timestamp and append new players
def save_new_player_file(new_names):
    global latest_file
    if new_names:
        # Generate a new filename with the current timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        new_file = os.path.join(log_dir, f"players_{timestamp}.txt")
        
        # Copy the latest file to the new file, if it exists
        if latest_file and os.path.exists(latest_file):
            shutil.copy(latest_file, new_file)

        # Append new player names to the new file
        with open(new_file, "a") as file:
            for name in new_names:
                file.write(f"{name}\n")
        logging.info(f"Appended new player names to {new_file}")

        # Update pick.txt with the length of the new file
        with open(new_file, "r") as file:
            lines = file.readlines()
            player_count = len(lines)
        
        pick_file = os.path.join(log_dir, "pick.txt")
        with open(pick_file, "w") as pick:
            pick.write(str(player_count))
        logging.info(f"Updated pick.txt with player count: {player_count}")

        # Update latest_file reference
        latest_file = new_file

# HTTP request handler class
class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        # Extract player names from POST data
        new_player_names = data.get('playerNames', [])
        new_entries = []

        if new_player_names:
            for player_name in new_player_names:
                if player_name not in player_names:
                    player_names.add(player_name)
                    new_entries.append(player_name)
                    logging.info(f"Added player: {player_name}")

            if new_entries:  # Only save if there are new players
                save_new_player_file(new_entries)

        # Send a response back to the client
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {'status': 'success'}
        self.wfile.write(json.dumps(response).encode('utf-8'))

# Function to run the server
def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    logging.info(f'Starting server on port {port}...')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info('Server stopped by user.')
    finally:
        httpd.server_close()
        logging.info('Server closed.')

if __name__ == '__main__':
    run()
