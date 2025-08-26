# Render app.py - Simplinx tarzı reverse tunnel

import socket
import threading
import time
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# Global connections
esp32_connection = None
virtual_connections = {}
next_virtual_port = 5000

class TunnelHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        
        status = f"""
        <h1>Simplinx Tunnel Server</h1>
        <p>Time: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>ESP32 Status: {'Connected' if esp32_connection else 'Disconnected'}</p>
        <p>Active Virtual Connections: {len(virtual_connections)}</p>
        <hr>
        <h3>Virtual IP Usage:</h3>
        <p>WPLSoft IP: <strong>esp32-modbus-tunnel.onrender.com:502</strong></p>
        <p>Protocol: Modbus TCP</p>
        """
        self.wfile.write(status.encode())
        
    def log_message(self, format, *args):
        return  # Disable HTTP logging

class ModbusTCPHandler:
    def __init__(self, client_socket, client_addr):
        self.client_socket = client_socket
        self.client_addr = client_addr
        
    def handle(self):
        global esp32_connection
        
        print(f"WPLSoft connected from: {self.client_addr}")
        
        try:
            while True:
                # WPLSoft'tan Modbus TCP al
                data = self.client_socket.recv(1024)
                if not data:
                    break
                
                print(f"WPLSoft → ESP32 ({len(data)} bytes): {data.hex()}")
                
                if esp32_connection:
                    # ESP32'ye ilet
                    esp32_connection.send(data)
                    
                    # ESP32'den yanıt bekle
                    try:
                        response = esp32_connection.recv(1024)
                        if response:
                            print(f"ESP32 → WPLSoft ({len(response)} bytes): {response.hex()}")
                            self.client_socket.send(response)
                    except:
                        break
                else:
                    # ESP32 bağlı değil, error response
                    error_response = bytes([
                        data[0], data[1],  # Transaction ID
                        0x00, 0x00,        # Protocol ID
                        0x00, 0x03,        # Length
                        0x01, 0x8B, 0x0A   # Unit ID, Error FC, Gateway error
                    ])
                    self.client_socket.send(error_response)
                    
        except Exception as e:
            print(f"WPLSoft connection error: {e}")
        finally:
            self.client_socket.close()

def handle_esp32_connection(esp32_sock, addr):
    global esp32_connection
    
    print(f"ESP32 reverse connection from: {addr}")
    esp32_connection = esp32_sock
    
    try:
        # ESP32'den keep-alive bekle
        while True:
            data = esp32_sock.recv(1024)
            if not data:
                break
                
            # ESP32'den gelen veriyi işle (heartbeat, response vs)
            if data == b'HEARTBEAT':
                esp32_sock.send(b'HEARTBEAT_OK')
                print("ESP32 heartbeat received")
            else:
                print(f"ESP32 data: {data.hex()}")
                
    except Exception as e:
        print(f"ESP32 connection error: {e}")
    finally:
        esp32_connection = None
        esp32_sock.close()
        print("ESP32 disconnected")

def start_modbus_server():
    """Modbus TCP server (port 502 emulation)"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Render PORT kullan
    port = int(os.environ.get('PORT', 5000))
    server.bind(('0.0.0.0', port))
    server.listen(5)
    
    print(f"Simplinx Virtual Modbus TCP server on port {port}")
    print("WPLSoft can connect to this server as if it's direct PLC connection")
    
    while True:
        try:
            client_socket, client_addr = server.accept()
            
            # Her WPLSoft bağlantısı için thread
            handler = ModbusTCPHandler(client_socket, client_addr)
            threading.Thread(target=handler.handle, daemon=True).start()
            
        except Exception as e:
            print(f"Server error: {e}")

def start_esp32_listener():
    """ESP32 reverse connection listener"""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    esp32_port = int(os.environ.get('PORT', 5000)) + 100
    listener.bind(('0.0.0.0', esp32_port))
    listener.listen(1)
    
    print(f"ESP32 reverse connection listener on port {esp32_port}")
    
    while True:
        try:
            esp32_sock, addr = listener.accept()
            threading.Thread(target=handle_esp32_connection, 
                           args=(esp32_sock, addr), daemon=True).start()
        except Exception as e:
            print(f"ESP32 listener error: {e}")

def start_http_status():
    """HTTP status server for Render health check"""
    status_port = int(os.environ.get('PORT', 5000)) + 200
    
    def run_server():
        httpd = HTTPServer(('0.0.0.0', status_port), TunnelHTTPHandler)
        httpd.serve_forever()
    
    threading.Thread(target=run_server, daemon=True).start()
    print(f"HTTP status server on port {status_port}")

if __name__ == "__main__":
    print("Starting Simplinx-style Reverse Tunnel Server")
    
    # Start all services
    threading.Thread(target=start_esp32_listener, daemon=True).start()
    threading.Thread(target=start_http_status, daemon=True).start()
    
    # Main Modbus TCP server
    start_modbus_server()
