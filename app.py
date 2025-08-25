from flask import Flask, request
from flask_socketio import SocketIO, emit
import time
import threading
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'modbus-tunnel-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

esp32_socket = None
client_sockets = set()


@app.route('/')
def index():
    return f"Modbus Tunnel Server - {time.strftime('%Y-%m-%d %H:%M:%S')}"


@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')


@socketio.on('disconnect')
def handle_disconnect():
    global esp32_socket
    print(f'Client disconnected: {request.sid}')

    if request.sid == esp32_socket:
        esp32_socket = None
        print('ESP32 disconnected')
    else:
        client_sockets.discard(request.sid)


@socketio.on('esp32_register')
def handle_esp32_register():
    global esp32_socket
    esp32_socket = request.sid
    print('ESP32 registered')
    emit('esp32_confirmed')


@socketio.on('client_register')
def handle_client_register():
    client_sockets.add(request.sid)
    print('WPLSoft client registered')
    emit('client_confirmed')


@socketio.on('modbus_data')
def handle_modbus_data(data):
    if request.sid == esp32_socket:
        # ESP32'den gelen veriyi WPLSoft'a ilet
        for client_sid in client_sockets:
            socketio.emit('modbus_data', data, room=client_sid)
    else:
        # WPLSoft'tan gelen veriyi ESP32'ye ilet
        if esp32_socket:
            socketio.emit('modbus_data', data, room=esp32_socket)


def keep_alive():
    while True:
        time.sleep(300)  # 5 dakikada bir
        print(f"Keep-alive ping - {time.strftime('%H:%M:%S')}")
        socketio.emit('ping', {'timestamp': time.time()})


# Background thread
threading.Thread(target=keep_alive, daemon=True).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)