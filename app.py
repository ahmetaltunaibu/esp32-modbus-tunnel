import asyncio
import websockets
import json

connected_esp32 = None
connected_clients = set()

async def handle_connection(websocket, path):
    global connected_esp32
    
    print(f"Client connected: {websocket.remote_address}")
    
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
                for client in connected_clients:
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
            
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")
        if websocket == connected_esp32:
            connected_esp32 = None
            print("ESP32 disconnected")
        connected_clients.discard(websocket)

async def main():
    print("WebSocket sunucusu başlatılıyor...")
    server = await websockets.serve(handle_connection, "0.0.0.0", 5000)
    print("Sunucu başlatıldı: 0.0.0.0:5000")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
