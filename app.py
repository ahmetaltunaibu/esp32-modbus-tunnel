import asyncio
import websockets
import os
from aiohttp import web

connected_esp32 = None
connected_clients = set()

async def websocket_handler(websocket, path):
    global connected_esp32
    
    print(f"WebSocket client connected: {websocket.remote_address}")
    
    try:
        message = await websocket.recv()
        print(f"İlk mesaj: {message}")
        
        if message == "esp32_register":
            connected_esp32 = websocket
            await websocket.send("esp32_confirmed")
            print("ESP32 registered")
            
            async for message in websocket:
                for client in connected_clients.copy():
                    try:
                        await client.send(message)
                    except:
                        connected_clients.remove(client)
                        
        elif message == "client_register":
            connected_clients.add(websocket)
            await websocket.send("client_confirmed")
            print("Client registered")
            
            async for message in websocket:
                if connected_esp32:
                    try:
                        await connected_esp32.send(message)
                    except:
                        connected_esp32 = None
        else:
            await websocket.close()
            
    except websockets.exceptions.ConnectionClosed:
        print("WebSocket client disconnected")
        if websocket == connected_esp32:
            connected_esp32 = None

async def health_check(request):
    return web.Response(text="OK")

async def start_websocket_server():
    port = int(os.environ.get("PORT", 5000))
    print(f"WebSocket server starting on port {port}")
    
    # WebSocket server
    ws_server = await websockets.serve(websocket_handler, "0.0.0.0", port)
    print(f"WebSocket server started on port {port}")
    return ws_server

async def start_http_server():
    # HTTP server for health checks
    app = web.Application()
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # HTTP server farklı bir portta çalışsın
    site = web.TCPSite(runner, '0.0.0.0', 5001)
    await site.start()
    print("HTTP health check server started on port 5001")

async def main():
    # Hem HTTP hem WebSocket serverları başlat
    await asyncio.gather(
        start_websocket_server(),
        start_http_server()
    )
    
    # Sonsuz döngü
    await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
