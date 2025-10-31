#!/usr/bin/env python3

import http.server
import socketserver
import os
import webbrowser
import socket

def find_free_port():
    """Find a free port to use for the server"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def serve_directory(port=None, directory=None):
    """Serve the current directory over HTTP"""

    if directory is None:
        directory = os.getcwd()

    if port is None:
        port = find_free_port()

    # Change to the specified directory
    os.chdir(directory)

    # Create HTTP request handler
    Handler = http.server.SimpleHTTPRequestHandler

    try:
        with socketserver.TCPServer(("", port), Handler) as httpd:
            server_url = f"http://localhost:{port}"
            print(f"Serving directory: {directory}")
            print(f"Server running at: {server_url}")
            print(f"Access your HTML files at:")
            print(f"  - {server_url}/rb_efficiency_vs_oline_interactive.html")
            print(f"  - {server_url}/rb_volume_vs_oline_interactive.html")
            print(f"  - {server_url}/rb_volume_vs_oline_interactive_with_search.html")
            print()
            print("Press Ctrl+C to stop the server")

            # Note: Browser opening disabled for compatibility

            # Start serving
            httpd.serve_forever()

    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except OSError as e:
        if e.errno == 98:  # Address already in use
            print(f"Port {port} is already in use. Trying a different port...")
            serve_directory(find_free_port(), directory)
        else:
            print(f"Error starting server: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Serve directory over HTTP for viewing HTML files')
    parser.add_argument('--port', '-p', type=int, help='Port to serve on (default: find free port)')
    parser.add_argument('--directory', '-d', type=str, help='Directory to serve (default: current directory)')

    args = parser.parse_args()

    serve_directory(args.port, args.directory)