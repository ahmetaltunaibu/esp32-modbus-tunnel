# ESP32 Modbus Tunnel Server

WebSocket tabanlı tunnel server ESP32 Modbus gateway için.

## Özellikler

- ESP32 ile WebSocket bağlantısı
- Modbus TCP veri aktarımı
- Render.com ücretsiz hosting
- Keep-alive anti-sleep

## Kurulum

1. Bu repository'yi Render.com'a deploy edin
2. ESP32'nizi tunnel server'a bağlayın
3. WPLSoft'u tunnel üzerinden kullanın

## Teknik Detaylar

- Python Flask + SocketIO
- WebSocket protokolü
- Render.com free tier uyumlu

## Kullanım

ESP32 → WebSocket → Render Server → WebSocket → WPLSoft
