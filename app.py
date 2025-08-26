import asyncio
import websockets
import json
import os
from datetime import datetime

esp32_socket = None
client_sockets = set()

async def handle_client(websocket, path):
    global esp32_socket
    
    print(f"New connection: {websocket.remote_address}")
    
    try:
        async for message in websocket:
            print(f"Message: {message}")
            
            if message == "esp32_register":
                esp32_socket = websocket
                await websocket.send("esp32_confirmed")
                print("ESP32 registered successfully")
                
            elif message == "client_register":
                client_sockets.add(websocket)
                await websocket.send("client_confirmed")
                print("WPLSoft client registered")
                
            else:
                # Modbus data forwarding
                if websocket == esp32_socket:
                    # ESP32 -> WPLSoft clients
                    for client in client_sockets.copy():
                        try:
                            await client.send(message)
                        except:
                            client_sockets.discard(client)
                            
                else:
                    # WPLSoft -> ESP32
                    if esp32_socket:
                        try:
                            await esp32_socket.send(message)
                        except:
                            esp32_socket = None
                            
    except websockets.exceptions.ConnectionClosed:
        if websocket == esp32_socket:
            esp32_socket = None
            print("ESP32 disconnected")
        else:
            client_sockets.discard(websocket)
            print("Client disconnected")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting WebSocket server on port {port}")
    
    start_server = websockets.serve(handle_client, "0.0.0.0", port)
    
    asyncio.get_event_loop().run_until_complete(start_server)
    print("WebSocket server running...")
    asyncio.get_event_loop().run_forever()
