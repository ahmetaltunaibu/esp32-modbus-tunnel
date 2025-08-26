import asyncio
import websockets
import json
import os
from datetime import datetime
from aiohttp import web, WSMsgType
import aiohttp_cors

esp32_socket = None
client_sockets = set()

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
                # Data forwarding
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

async def http_handler(request):
    return web.Response(text=f"Modbus Tunnel Server - {datetime.now()}")

async def init_app():
    app = web.Application()
    app.router.add_get('/', http_handler)
    
    return app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    
    # HTTP server
    app = asyncio.get_event_loop().run_until_complete(init_app())
    
    # WebSocket server
    start_server = websockets.serve(handle_websocket, "0.0.0.0", port + 1)
    
    # HTTP server start
    runner = web.AppRunner(app)
    asyncio.get_event_loop().run_until_complete(runner.setup())
    site = web.TCPSite(runner, '0.0.0.0', port)
    asyncio.get_event_loop().run_until_complete(site.start())
    
    print(f"HTTP server: {port}, WebSocket: {port + 1}")
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
