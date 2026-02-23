"""
ses_motoru.py
Cano'nun sesi — Mobil uyumlu TTS motoru (v4.0 Pro).
- edge-tts ile metni Neural ses ile MP3'e çevirir.
- Ses dosyasının YOLUNU döner — çalma işi ft.Audio'nun.
- Eski geçici dosyaları otomatik temizler.
- Hız ve ses tonu ayarlanabilir.
"""

import asyncio
import os
import tempfile
import time
import edge_tts

# Türkçe erkek sesi — doğal ve profesyonel Neural ses
# Alternatif kadın sesi: "tr-TR-EmelNeural"
TURKCE_SES = "tr-TR-AhmetNeural"

# Ses ayarları
SES_HIZI = "+0%"      # "+10%" hızlandırır, "-10%" yavaşlatır
SES_TONU = "+0Hz"     # "+2Hz" tonu yükseltir

# Geçici ses dosyalarının tutulacağı klasör
_TEMP_DIR = tempfile.gettempdir()
_TEMP_PREFIX = "cano_tts_"

# Eski dosya temizleme eşiği (saniye) — 5 dakikadan eski dosyaları sil
_TEMIZLIK_ESIK_SN = 300


def _eski_dosyalari_temizle():
    """5 dakikadan eski Cano TTS dosyalarını siler."""
    try:
        simdi = time.time()
        for dosya in os.listdir(_TEMP_DIR):
            if dosya.startswith(_TEMP_PREFIX) and dosya.endswith(".mp3"):
                tam_yol = os.path.join(_TEMP_DIR, dosya)
                if simdi - os.path.getmtime(tam_yol) > _TEMIZLIK_ESIK_SN:
                    os.unlink(tam_yol)
    except Exception:
        pass  # Temizlik başarısız olursa uygulama devam eder


def konuş(metin: str) -> str:
    """
    Verilen metni edge-tts ile Türkçe seslendirir.
    Oluşturulan MP3 dosyasının YOLUNU döner.
    """
    print(f"[TTS] Cano: {metin}")

    # Eski dosyaları temizle
    _eski_dosyalari_temizle()

    # Benzersiz dosya adı
    tmp = tempfile.NamedTemporaryFile(
        prefix=_TEMP_PREFIX, suffix=".mp3", delete=False, dir=_TEMP_DIR
    )
    tmp_yol = tmp.name
    tmp.close()

    # Asenkron TTS oluşturma
    async def _tts_olustur():
        tts = edge_tts.Communicate(
            metin, TURKCE_SES,
            rate=SES_HIZI,
            pitch=SES_TONU,
        )
        await tts.save(tmp_yol)

    # Senkron bağlamdan async çalıştır
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pool.submit(asyncio.run, _tts_olustur()).result()
    else:
        asyncio.run(_tts_olustur())

    return tmp_yol


def tahmini_sure(metin: str) -> float:
    """Metnin sesli okunma süresini saniye olarak tahmin eder."""
    # Ortalama: 14 karakter/saniye (Türkçe Neural TTS)
    return max(2.0, len(metin) / 14.0 + 0.5)


def temizle(dosya_yolu: str) -> None:
    """Tek bir geçici ses dosyasını güvenle siler."""
    try:
        if dosya_yolu and os.path.exists(dosya_yolu):
            os.unlink(dosya_yolu)
    except Exception:
        pass
