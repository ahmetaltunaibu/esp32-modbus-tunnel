import asyncio
import websockets
import os

connected_esp32 = None
connected_clients = set()

async def handle_connection(websocket, path):
    global connected_esp32
    
    print(f"Client connected: {websocket.remote_address}")
    
    try:
        # İlk mesajı al
        message = await websocket.recv()
        print(f"İlk mesaj: {message}")
        
        if message == "esp32_register":
            connected_esp32 = websocket
            await websocket.send("esp32_confirmed")
            print("✅ ESP32 registered")
            
            # ESP32'den gelen mesajları client'lara ilet
            async for message in websocket:
                for client in connected_clients.copy():
                    try:
                        await client.send(message)
                    except:
                        connected_clients.remove(client)
                        
        elif message == "client_register":
            connected_clients.add(websocket)
            await websocket.send("client_confirmed")
            print("✅ Client registered")
            
            # Client'tan gelen mesajları ESP32'ye ilet
            async for message in websocket:
                if connected_esp32:
                    try:
                        await connected_esp32.send(message)
                    except:
                        connected_esp32 = None
        else:
            print(f"❌ Bilinmeyen mesaj: {message}")
            await websocket.close()
            
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")
        if websocket == connected_esp32:
            connected_esp32 = None
            print("ESP32 disconnected")

async def main():
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 WebSocket sunucusu başlatılıyor... Port: {port}")
    
    server = await websockets.serve(handle_connection, "0.0.0.0", port)
    print(f"✅ Sunucu başlatıldı: 0.0.0.0:{port}")
    print("⏳ ESP32 bağlantısını bekliyor...")
    
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
