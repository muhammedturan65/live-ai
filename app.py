import os
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google import genai

app = FastAPI()

# Render'daki ENV değişkeninden API Key'i alacak
API_KEY = os.environ.get("GEMINI_API_KEY")

# Model Ayarları (Dr. Atlas için sistem talimatı)
SYSTEM_INSTRUCTION = """
Sen Dr. Atlas'sın. Empati yeteneği çok yüksek, profesyonel bir psikoloji asistanısın. 
Kullanıcıyla sesli sohbet ediyorsun. Ses tonun sakinleştirici, güven verici ve doğal olmalı.
Kısa, öz ve karşılıklı sohbete uygun cevaplar ver. 
Eğer kullanıcı üzgünse ses tonunu yumuşat, neşeliyse enerjik ol.
"""

MODEL_ID = "gemini-2.0-flash-exp"  # En yeni Live model

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Google GenAI İstemcisini Başlat
    client = genai.Client(api_key=API_KEY, http_options={"api_version": "v1alpha"})
    
    try:
        # Gemini Live Bağlantısını Başlat
        async with client.aio.live.connect(model=MODEL_ID, config={"response_modalities": ["AUDIO"]}) as session:
            
            # İlk olarak sistem talimatını gönder
            await session.send(input=SYSTEM_INSTRUCTION, end_of_turn=True)

            # İki yönlü akışı yönetmek için görevler oluştur
            # 1. Görev: Android'den gelen sesi Gemini'ye gönder
            async def receive_from_android():
                try:
                    while True:
                        # Android'den ham ses verisi veya JSON bekle
                        data = await websocket.receive_bytes()
                        # Gemini'ye ses verisi olarak gönder
                        await session.send(input={"data": data, "mime_type": "audio/pcm"}, end_of_turn=False)
                except WebSocketDisconnect:
                    pass
                except Exception as e:
                    print(f"Android alma hatası: {e}")

            # 2. Görev: Gemini'den gelen sesi Android'e gönder
            async def send_to_android():
                try:
                    async for response in session.receive():
                        # Gemini'den gelen ses verisi var mı?
                        if response.data:
                            # Android'e bayt olarak geri gönder
                            await websocket.send_bytes(response.data)
                        
                        # Metin dökümü varsa (isteğe bağlı loglayabilirsin)
                        if response.text:
                            print(f"Dr. Atlas (Text): {response.text}")
                            
                except Exception as e:
                    print(f"Gemini alma hatası: {e}")

            # İki görevi aynı anda çalıştır
            await asyncio.gather(receive_from_android(), send_to_android())

    except Exception as e:
        print(f"Bağlantı hatası: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)