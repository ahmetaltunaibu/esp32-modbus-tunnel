import asyncio
import websockets
from websockets import WebSocketServerProtocol
import json
import os
from http import HTTPStatus
import asyncio

connected_esp32 = None
connected_clients = set()

async def health_check(path, request_headers):
    """Render health check için HEAD request'leri handle et"""
    if path == "/health":
        return HTTPStatus.OK, [], b"OK\n"
    return None

async def handle_connection(websocket: WebSocketServerProtocol, path: str):
    global connected_esp32
    
    # Health check endpoint'i
    if path == "/health":
        await websocket.close()
        return
        
    print(f"Client connected: {websocket.remote_address}, path: {path}")
    
    try:
        # İlk mesajı al (kayıt)
        message = await websocket.recv()
        print(f"İlk mesaj: {message}")
        
        if message == "esp32_register":
            connected_esp32 = websocket
            await websocket.send("esp32_confirmed")
            print("ESP32 registered")
            
            # ESP32'den gelen mesajları dinle
            async for message in websocket:
                print(f"ESP32'den: {message}")
                # Tüm client'lara gönder
                for client in connected_clients.copy():
                    try:
                        await client.send(message)
                    except:
                        connected_clients.remove(client)
                        
        elif message == "client_register":
            connected_clients.add(websocket)
            await websocket.send("client_confirmed")
            print("WPLSoft client registered")
            
            # Client'tan gelen mesajları dinle
            async for message in websocket:
                print(f"Client'tan: {message}")
                # ESP32'ye gönder
                if connected_esp32:
                    try:
                        await connected_esp32.send(message)
                    except:
                        connected_esp32 = None
        else:
            print(f"Bilinmeyen mesaj: {message}")
            await websocket.close()
            
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")
        if websocket == connected_esp32:
            connected_esp32 = None
            print("ESP32 disconnected")
        connected_clients.discard(websocket)

async def main():
    port = int(os.environ.get("PORT", 5000))
    print(f"WebSocket sunucusu başlatılıyor... Port: {port}")
    
    # Health check handler ile server oluştur
    server = await websockets.serve(
        handle_connection, 
        "0.0.0.0", 
        port,
        process_request=health_check
    )
    
    print(f"Sunucu başlatıldı: 0.0.0.0:{port}")
    print("ESP32 bağlantısını bekliyor...")
    
    # Health check endpoint için basit HTTP server
    async def http_handler(reader, writer):
        data = await reader.read(100)
        message = data.decode()
        if message.startswith('HEAD /health') or message.startswith('GET /health'):
            writer.write(b'HTTP/1.1 200 OK\r\n\r\n')
            await writer.drain()
        writer.close()
    
    # HTTP health check server
    http_server = await asyncio.start_server(http_handler, '0.0.0.0', port)
    
    await asyncio.gather(
        server.wait_closed(),
        http_server.wait_closed()
    )

if __name__ == "__main__":
    asyncio.run(main())
