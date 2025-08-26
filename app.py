# Render app.py - Port Ayırımlı Modbus TCP Server

import socket
import threading
import time
import json
import os

# Global connections
esp32_connection = None
esp32_lock = threading.Lock()

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
    
    print(f"ESP32 WebSocket connection from: {addr}")
    
    with esp32_lock:
        # Eski bağlantıyı kapat
        if esp32_connection:
            try:
                esp32_connection.close()
            except:
                pass
        esp32_connection = esp32_sock
    
    try:
        # ESP32 WebSocket registration'ı oku
        registration = ""
        while "\r\n\r\n" not in registration:
            chunk = esp32_sock.recv(1024)
            if not chunk:
                break
            registration += chunk.decode('utf-8', errors='ignore')
            
        print(f"ESP32 WebSocket handshake: {registration[:200]}...")
        
        # WebSocket/HTTP response gönder
        response = "HTTP/1.1 200 OK\r\n"
        response += "Content-Type: text/plain\r\n"
        response += "Connection: keep-alive\r\n\r\n"
        response += "ESP32_REGISTERED"
        
        esp32_sock.send(response.encode())
        esp32_sock.settimeout(60.0)
        
        print("ESP32 WebSocket registered successfully")
        
        # ESP32'den gelen verileri işle
        while True:
            try:
                data = esp32_sock.recv(1024)
                if not data:
                    print("ESP32 connection closed")
                    break
                    
                # Heartbeat kontrolü
                if b'HEARTBEAT' in data:
                    esp32_sock.send(b"HTTP/1.1 200 OK\r\n\r\nOK")
                    print("ESP32 heartbeat received")
                else:
                    # Normal Modbus TCP yanıtı
                    hex_data = data.hex()
                    print(f"ESP32 response data: {hex_data}")
                    
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

def start_modbus_tcp_server():
    """Sadece Modbus TCP Server - Port 502"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind(('0.0.0.0', 502))
        print("Modbus TCP Server started on port 502")
    except Exception as e:
        print(f"Port 502 bind error: {e}")
        return
    
    server.listen(10)
    
    while True:
        try:
            client_socket, client_addr = server.accept()
            
            # Direkt ModbusTCPHandler - detection yok
            handler = ModbusTCPHandler(client_socket, client_addr)
            threading.Thread(target=handler.handle, daemon=True).start()
                
        except Exception as e:
            print(f"Modbus server accept error: {e}")
            time.sleep(1)

def start_http_websocket_server():
    """HTTP/WebSocket Server - Render PORT"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    port = int(os.environ.get('PORT', 10000))
    server.bind(('0.0.0.0', port))
    server.listen(10)
    
    print(f"HTTP/WebSocket server started on port {port}")
    
    while True:
        try:
            client_socket, client_addr = server.accept()
            
            # HTTP/WebSocket detection
            client_socket.settimeout(2.0)
            try:
                first_bytes = client_socket.recv(20, socket.MSG_PEEK)
                client_socket.settimeout(None)
                
                if first_bytes.startswith(b'GET ') or first_bytes.startswith(b'POST'):
                    # HTTP request - status handler
                    threading.Thread(target=handle_http_request, 
                                   args=(client_socket, client_addr), daemon=True).start()
                else:
                    # ESP32 WebSocket/registration
                    threading.Thread(target=handle_esp32_connection, 
                                   args=(client_socket, client_addr), daemon=True).start()
                                   
            except socket.timeout:
                # Timeout - ESP32 olarak kabul et
                client_socket.settimeout(None)
                threading.Thread(target=handle_esp32_connection, 
                               args=(client_socket, client_addr), daemon=True).start()
                
        except Exception as e:
            print(f"HTTP server accept error: {e}")
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
        <hr>
        <h3>WPLSoft Bağlantı Bilgileri:</h3>
        <p><strong>IP:</strong> 216.24.57.7 (veya güncel server IP)</p>
        <p><strong>Port:</strong> 502</p>
        <p><strong>Protocol:</strong> Modbus TCP</p>
        <p><strong>Unit ID:</strong> 1</p>
        <hr>
        <p>Bu server ESP32 cihazınız üzerinden PLC bağlantısı sağlıyor.</p>
        <p>Modbus TCP: Port 502 | HTTP Status: Port {os.environ.get('PORT', '10000')}</p>
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

if __name__ == "__main__":
    print("Starting Port-Separated Modbus TCP Tunnel Server")
    print(f"Render PORT environment: {os.environ.get('PORT', 'Not set')}")
    
    # Modbus TCP server'ı ayrı thread'de başlat
    threading.Thread(target=start_modbus_tcp_server, daemon=True).start()
    
    # Ana thread HTTP/WebSocket server'ı çalıştır
    start_http_websocket_server()
