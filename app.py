import asyncio
import websockets
import json
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

esp32_socket = None
client_sockets = set()

class HTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(f"Modbus Tunnel Server - {datetime.now()}".encode())

async def handle_websocket(websocket, path):
    global esp32_socket
    
    print(f"WebSocket connection: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            if message == "esp32_register":
                esp32_socket = websocket
                await websocket.send("esp32_confirmed")
                print("ESP32 registered")
            elif message == "client_register":
                client_sockets.add(websocket)
                await websocket.send("client_confirmed")
                print("Client registered")
            else:
                if websocket == esp32_socket:
                    for client in client_sockets.copy():
                        try:
                            await client.send(message)
                        except:
                            client_sockets.discard(client)
                else:
                    if esp32_socket:
                        try:
                            await esp32_socket.send(message)
                        except:
                            esp32_socket = None
    except:
        if websocket == esp32_socket:
            esp32_socket = None
        else:
            client_sockets.discard(websocket)

def start_http_server():
    port = int(os.environ.get("PORT", 8000))
    httpd = HTTPServer(("0.0.0.0", port), HTTPHandler)
    print(f"HTTP server starting on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    
    # HTTP server thread
    http_thread = threading.Thread(target=start_http_server)
    http_thread.daemon = True
    http_thread.start()
    
    # WebSocket server
    ws_port = port + 1000  # Farklı port
    start_server = websockets.serve(handle_websocket, "0.0.0.0", ws_port)
    
    print(f"WebSocket server starting on port {ws_port}")
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
