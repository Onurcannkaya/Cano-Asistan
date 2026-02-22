"""
ses_motoru.py
Cano'nun sesi — Mobil uyumlu TTS motoru.
- edge-tts ile metni Neural ses ile MP3'e çevirir.
- Ses dosyasının YOLUNU döner (çalmaz) — çalma işi ft.Audio'nun.
- pygame bağımlılığı KALDIRILDI — mobil uyumlu.
"""

import asyncio
import os
import tempfile
import edge_tts

# Türkçe erkek sesi — doğal ve profesyonel Neural ses
# Alternatif kadın sesi: "tr-TR-EmelNeural"
TURKCE_SES = "tr-TR-AhmetNeural"

# Geçici ses dosyalarının tutulacağı klasör
_TEMP_DIR = tempfile.gettempdir()


def konuş(metin: str) -> str:
    """
    Verilen metni edge-tts ile Türkçe seslendirir.
    Oluşturulan MP3 dosyasının YOLUNU (string) döner.
    Çalma işlemi app.py'deki ft.Audio tarafından yapılır.
    """
    print(f"[TTS] Cano: {metin}")

    # Her seferinde benzersiz dosya adı
    tmp = tempfile.NamedTemporaryFile(
        suffix=".mp3", delete=False, dir=_TEMP_DIR
    )
    tmp_yol = tmp.name
    tmp.close()

    # Asenkron TTS oluşturma
    async def _tts_olustur():
        tts = edge_tts.Communicate(metin, TURKCE_SES)
        await tts.save(tmp_yol)

    # Senkron bağlamdan async çalıştır
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Zaten bir event loop çalışıyorsa (Flet ortamı)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pool.submit(asyncio.run, _tts_olustur()).result()
    else:
        asyncio.run(_tts_olustur())

    return tmp_yol


def temizle(dosya_yolu: str) -> None:
    """
    Çalınması biten geçici ses dosyasını güvenle siler.
    Silinemezse bile Cano çökmez.
    """
    try:
        if dosya_yolu and os.path.exists(dosya_yolu):
            os.unlink(dosya_yolu)
    except Exception:
        pass
