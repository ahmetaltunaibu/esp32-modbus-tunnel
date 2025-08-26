# Render app.py - Port 502 Modbus TCP Server

import socket
import threading
import time
import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import struct

# Global connections
esp32_connection = None
esp32_lock = threading.Lock()
virtual_connections = {}

class TunnelHTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        
        status = f"""
        <h1>Modbus TCP Tunnel Server</h1>
        <p>Time: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>ESP32 Status: {'Connected' if esp32_connection else 'Disconnected'}</p>
        <p>Active Virtual Connections: {len(virtual_connections)}</p>
        <hr>
        <h3>WPLSoft Bağlantı Bilgileri:</h3>
        <p><strong>Host:</strong> esp32-modbus-tunnel.onrender.com</p>
        <p><strong>Port:</strong> 502</p>
        <p><strong>Protocol:</strong> Modbus TCP</p>
        <p><strong>Unit ID:</strong> 1</p>
        <hr>
        <p>Bu server Render.com üzerinde çalışıyor ve ESP32 cihazınız üzerinden PLC bağlantısı sağlıyor.</p>
        """
        self.wfile.write(status.encode())
        
    def log_message(self, format, *args):
        return  # HTTP logging'i kapat

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
                
                # HTTP request kontrolü - eğer HTTP ise kapat
                if data.startswith(b'GET') or data.startswith(b'HEAD') or data.startswith(b'POST'):
                    # HTTP response gönder ve bağlantıyı kapat
                    http_response = b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
                    self.client_socket.send(http_response)
                    break
                
                # Modbus TCP minimum uzunluk kontrolü
                if len(data) < 8:
                    print(f"Invalid Modbus TCP frame length: {len(data)}")
                    continue
                    
                print(f"WPLSoft → ESP32 ({len(data)} bytes): {data.hex()}")
                
                with esp32_lock:
                    if esp32_connection and esp32_connection.fileno() != -1:
                        try:
                            # ESP32'ye ilet
                            esp32_connection.send(data)
                            
                            # ESP32'den yanıt bekle (timeout ile)
                            esp32_connection.settimeout(5.0)  # 5 saniye timeout
                            response = esp32_connection.recv(1024)
                            
                            if response:
                                print(f"ESP32 → WPLSoft ({len(response)} bytes): {response.hex()}")
                                self.client_socket.send(response)
                            else:
                                print("ESP32'den boş yanıt")
                                break
                                
                        except socket.timeout:
                            print("ESP32 response timeout")
                            self.send_error_response(data, 0x0B)  # Gateway timeout
                        except Exception as e:
                            print(f"ESP32 communication error: {e}")
                            self.send_error_response(data, 0x0A)  # Gateway unavailable
                    else:
                        print("ESP32 bağlı değil, error response gönderiliyor")
                        self.send_error_response(data, 0x0A)  # Gateway unavailable
                    
        except Exception as e:
            print(f"WPLSoft connection error: {e}")
        finally:
            self.client_socket.close()
            print(f"WPLSoft disconnected: {self.client_addr}")

    def send_error_response(self, request_data, error_code):
        """Modbus TCP error response gönder"""
        try:
            if len(request_data) < 8:
                return
                
            # Transaction ID'yi koruyalım
            transaction_id = request_data[:2]
            unit_id = request_data[6] if len(request_data) > 6 else 0x01
            function_code = request_data[7] if len(request_data) > 7 else 0x03
            
            error_response = bytearray([
                transaction_id[0], transaction_id[1],  # Transaction ID
                0x00, 0x00,        # Protocol ID
                0x00, 0x03,        # Length
                unit_id,           # Unit ID
                function_code | 0x80,  # Error function code
                error_code         # Exception code
            ])
            
            self.client_socket.send(error_response)
            print(f"Error response sent: {error_response.hex()}")
        except Exception as e:
            print(f"Error sending error response: {e}")

def handle_esp32_connection(esp32_sock, addr):
    global esp32_connection
    
    print(f"ESP32 reverse connection from: {addr}")
    
    with esp32_lock:
        # Eski bağlantıyı kapat
        if esp32_connection:
            try:
                esp32_connection.close()
            except:
                pass
        esp32_connection = esp32_sock
    
    try:
        esp32_sock.settimeout(60.0)  # 60 saniye timeout
        
        # ESP32 registration'ı oku
        registration = ""
        while "\r\n\r\n" not in registration:
            chunk = esp32_sock.recv(1024)
            if not chunk:
                break
            registration += chunk.decode('utf-8', errors='ignore')
            
        print(f"ESP32 registration received: {registration[:100]}...")
        
        # Registration başarılı response
        esp32_sock.send(b"REGISTRATION_OK\r\n")
        
        # ESP32'den gelen verileri işle
        while True:
            try:
                data = esp32_sock.recv(1024)
                if not data:
                    print("ESP32 connection closed")
                    break
                    
                # Heartbeat kontrolü
                if b'HEARTBEAT' in data:
                    esp32_sock.send(b"HEARTBEAT_OK\n")
                    print("ESP32 heartbeat received")
                else:
                    # Normal Modbus TCP yanıtı
                    hex_data = data.hex()
                    print(f"ESP32 data: {hex_data}")
                    
            except socket.timeout:
                print("ESP32 heartbeat timeout")
                break
            except Exception as e:
                print(f"ESP32 data receive error: {e}")
                break
                
    except Exception as e:
        print(f"ESP32 connection error: {e}")
    finally:
        with esp32_lock:
            if esp32_connection == esp32_sock:
                esp32_connection = None
        try:
            esp32_sock.close()
        except:
            pass
        print("ESP32 disconnected")

def start_port_502_server():
    """Port 502'de Modbus TCP server başlat"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        # Önce 502 portunu dene
        server.bind(('0.0.0.0', 502))
        print("Modbus TCP Server started on port 502 (Standard Modbus port)")
        
    except PermissionError:
        # Root yetkisi yoksa Render'ın verdiği portu kullan
        render_port = int(os.environ.get('PORT', 10000))
        server.bind(('0.0.0.0', render_port))
        print(f"Port 502 için yetki yok, port {render_port} kullanılıyor")
        print("NOT: WPLSoft'ta port 502 yerine port {} kullanın".format(render_port))
        
    except Exception as e:
        # Port 502 kullanılamıyorsa Render'ın verdiği portu kullan
        render_port = int(os.environ.get('PORT', 10000))
        server.bind(('0.0.0.0', render_port))
        print(f"Port 502 kullanılamadı ({e}), port {render_port} kullanılıyor")
        print("NOT: WPLSoft'ta port 502 yerine port {} kullanın".format(render_port))
    
    server.listen(10)
    
    while True:
        try:
            client_socket, client_addr = server.accept()
            
            # İlk birkaç byte'a bakarak HTTP mi TCP mi karar ver
            client_socket.settimeout(2.0)
            try:
                first_bytes = client_socket.recv(12, socket.MSG_PEEK)
                client_socket.settimeout(None)
                
                if first_bytes.startswith(b'GET ') or first_bytes.startswith(b'POST'):
                    # HTTP request - status handler
                    threading.Thread(target=handle_http_request, 
                                   args=(client_socket, client_addr), daemon=True).start()
                elif first_bytes.startswith(b'ESP32_REGISTER'):
                    # ESP32 registration request
                    threading.Thread(target=handle_esp32_connection, 
                                   args=(client_socket, client_addr), daemon=True).start()
                else:
                    # Modbus TCP request
                    handler = ModbusTCPHandler(client_socket, client_addr)
                    threading.Thread(target=handler.handle, daemon=True).start()
            except socket.timeout:
                # Timeout olursa Modbus TCP olarak kabul et
                client_socket.settimeout(None)
                handler = ModbusTCPHandler(client_socket, client_addr)
                threading.Thread(target=handler.handle, daemon=True).start()
                
        except Exception as e:
            print(f"Server accept error: {e}")
            time.sleep(1)

def handle_http_request(client_socket, client_addr):
    """HTTP status requestlerini işle"""
    try:
        # HTTP request'i oku
        request = b""
        while b"\r\n\r\n" not in request:
            chunk = client_socket.recv(1024)
            if not chunk:
                break
            request += chunk
            if len(request) > 4096:  # Büyük request'leri engelle
                break
            
        # Status HTML'i gönder
        status = f"""HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n
<!DOCTYPE html>
<html>
<head><title>Modbus TCP Tunnel</title></head>
<body>
        <h1>Modbus TCP Tunnel Server</h1>
        <p>Time: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>ESP32 Status: {'Connected' if esp32_connection else 'Disconnected'}</p>
        <p>Active Connections: {len(virtual_connections)}</p>
        <hr>
        <h3>WPLSoft Bağlantı Bilgileri:</h3>
        <p><strong>Host:</strong> esp32-modbus-tunnel.onrender.com</p>
        <p><strong>Port:</strong> 502 (veya {os.environ.get('PORT', '10000')})</p>
        <p><strong>Protocol:</strong> Modbus TCP</p>
        <p><strong>Unit ID:</strong> 1</p>
        <hr>
        <p>Bu server ESP32 cihazınız üzerinden PLC bağlantısı sağlıyor.</p>
</body>
</html>"""
        
        client_socket.send(status.encode())
        
    except Exception as e:
        print(f"HTTP request error: {e}")
    finally:
        try:
            client_socket.close()
        except:
            pass

def start_health_check_server():
    """Render.com için health check server (farklı port)"""
    health_port = int(os.environ.get('PORT', 10000))
    
    def health_server():
        health_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        health_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            health_sock.bind(('0.0.0.0', health_port))
            health_sock.listen(5)
            print(f"Health check server started on port {health_port}")
            
            while True:
                client, addr = health_sock.accept()
                try:
                    # Basit HTTP response
                    response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"
                    client.send(response)
                except:
                    pass
                finally:
                    client.close()
                    
        except Exception as e:
            print(f"Health server error: {e}")
    
    threading.Thread(target=health_server, daemon=True).start()

if __name__ == "__main__":
    print("Starting Modbus TCP Tunnel Server for Port 502")
    print(f"Render PORT environment: {os.environ.get('PORT', 'Not set')}")
    
    # Health check server'ı başlat (Render.com için gerekli)
    start_health_check_server()
    
    # Ana Modbus TCP server'ı başlat (port 502'yi dene)
    start_port_502_server()
