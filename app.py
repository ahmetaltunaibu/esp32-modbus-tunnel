import socket
import threading
import time

ESP32_HOST = None
ESP32_PORT = None
esp32_socket = None

class TCPProxy:
    def __init__(self, listen_port=502):
        self.listen_port = listen_port
        self.server_socket = None
        
    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.listen_port))
        self.server_socket.listen(5)
        
        print(f"TCP Proxy listening on port {self.listen_port}")
        
        while True:
            try:
                client_socket, client_addr = self.server_socket.accept()
                print(f"WPLSoft connected: {client_addr}")
                
                # ESP32 bağlantısı kur
                esp32_conn = self.connect_to_esp32()
                
                if esp32_conn:
                    # İki yönlü proxy başlat
                    threading.Thread(target=self.proxy_data, 
                                   args=(client_socket, esp32_conn, "WPLSoft->ESP32")).start()
                    threading.Thread(target=self.proxy_data, 
                                   args=(esp32_conn, client_socket, "ESP32->WPLSoft")).start()
                else:
                    client_socket.close()
                    
            except Exception as e:
                print(f"Proxy error: {e}")
    
    def connect_to_esp32(self):
        # Bu kısım ESP32'nin sunucuya nasıl bağlanacağını belirler
        # Reverse tunnel mantığı gerekli
        return None
        
    def proxy_data(self, source, destination, direction):
        try:
            while True:
                data = source.recv(4096)
                if not data:
                    break
                destination.send(data)
                print(f"{direction}: {len(data)} bytes")
        except:
            pass
        finally:
            source.close()
            destination.close()

if __name__ == "__main__":
    proxy = TCPProxy()
    proxy.start()
