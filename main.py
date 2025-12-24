import os
import asyncio
import traceback
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google import genai

app = FastAPI()

# API Key Kontrolü
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("CRITICAL ERROR: GEMINI_API_KEY bulunamadı! Render Environment ayarlarını kontrol et.")

MODEL_ID = "gemini-2.5-flash-native-audio-dialog"

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client bağlandı!")

    if not API_KEY:
        await websocket.close(code=1008, reason="API Key Missing")
        return

    try:
        # İstemciyi başlat
        client = genai.Client(api_key=API_KEY, http_options={"api_version": "v1alpha"})
        
        # Live Session başlat
        async with client.aio.live.connect(model=MODEL_ID, config={"response_modalities": ["AUDIO"]}) as session:
            print("Gemini Live bağlantısı kuruldu!")
            
            # İlk mesaj (Sistem talimatı)
            await session.send(input="Sen Dr. Atlas'sın. Türkçe konuşan, yardımsever bir psikoloji asistanısın.", end_of_turn=True)

            async def receive_from_client():
                try:
                    while True:
                        data = await websocket.receive_bytes()
                        # Gemini'ye gönder
                        await session.send(input={"data": data, "mime_type": "audio/pcm"}, end_of_turn=False)
                except WebSocketDisconnect:
                    print("Client bağlantıyı kesti.")
                except Exception as e:
                    print(f"Veri alma hatası: {e}")

            async def send_to_client():
                try:
                    async for response in session.receive():
                        if response.data:
                            await websocket.send_bytes(response.data)
                except Exception as e:
                    print(f"Gemini yanıt hatası: {e}")

            # Döngüyü başlat
            await asyncio.gather(receive_from_client(), send_to_client())

    except Exception as e:
        # İŞTE BURASI HATAYI LOGLAYACAK
        error_msg = f"SUNUCU HATASI: {str(e)}\n{traceback.format_exc()}"
        print(error_msg) 
        await websocket.close(code=1011, reason=f"Server Error: {str(e)[:50]}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
