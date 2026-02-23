"""
zeka_motoru.py
Cano'nun bulut beyni — Google Gemini API + Cascade Fallback.
- Birden fazla modeli sırayla dener (şelale yedekleme).
- Bir model hata verirse sonrakine otomatik geçer.
- Tüm modeller başarısız olursa güvenli mesaj döner.
"""

import os

from google import genai

# ---------------------------------------------------------------------------
# Yapılandırma
# ---------------------------------------------------------------------------

# API anahtarı: ortam değişkeninden çek (güvenlik için koda ASLA yazılmaz!)
# Ayarlama: $env:GEMINI_API_KEY = "key-buraya"  (PowerShell)
API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Şelale model hiyerarşisi — sırayla denenir
# İlk model başarısız olursa ikinciye, o da olmazsa üçüncüye geçer
MODELLER = [
    "gemini-2.0-flash",     # 1. tercih: en hızlı
    "gemini-1.5-flash",     # 2. yedek: hafif ve stabil
    "gemini-1.5-pro",       # 3. yedek: en yetenekli
]

# Cano'nun kişiliğini tanımlayan sistem talimatı
SISTEM_TALIMATI = (
    "Senin adın Cano. Onurcan'ın kişisel asistanısın. "
    "Kısa, samimi, net ve tek cümlelik Türkçe cevaplar ver. "
    "Asla uzun paragraflar yazma çünkü cevapların sesli okunacak. "
    "Emojileri az ve yerinde kullan. "
    "ÖNEMLİ KURAL: Eğer kullanıcının cümlesi anlamsızsa, yarım kesilmişse "
    "veya bağlamı yoksa KESİNLİKLE cevap veya hikaye uydurma. "
    'Sadece şu cevabı ver: "Tam anlayamadım, cümlen yarım kalmış olabilir. '
    'Tekrar söyler misin?"'
)

# Ortak üretim ayarları
_URETIM_AYARLARI = genai.types.GenerateContentConfig(
    system_instruction=SISTEM_TALIMATI,
    temperature=0.7,
    max_output_tokens=120,
)

# ---------------------------------------------------------------------------
# Gemini istemcisi (lazy-init — key yoksa import'ta çökmez)
# ---------------------------------------------------------------------------

_client = None


def _get_client():
    """İlk kullanımda client oluşturur. Key yoksa None döner."""
    global _client
    if _client is None and API_KEY:
        _client = genai.Client(api_key=API_KEY)
    return _client


# ---------------------------------------------------------------------------
# Ana fonksiyon — Cascade Fallback
# ---------------------------------------------------------------------------

def gemini_sor(metin: str) -> str:
    """
    Kullanıcının metnini Gemini'ye gönderir ve yanıtı döner.

    Şelale (Cascade) mantığı:
      1. MODELLER listesindeki ilk modeli dener.
      2. Hata alırsa (429, 503, vb.) sonraki modele geçer.
      3. Tüm modeller başarısız olursa güvenli mesaj döner.
    """
    for i, model in enumerate(MODELLER):
        try:
            client = _get_client()
            if client is None:
                return "API anahtari ayarlanmamis. $env:GEMINI_API_KEY ayarla."
            yanit = client.models.generate_content(
                model=model,
                contents=metin,
                config=_URETIM_AYARLARI,
            )
            cevap = yanit.text.strip()

            if not cevap:
                continue  # boş yanıt → sonraki modeli dene

            return cevap

        except Exception as e:
            # Sonraki model var mı?
            if i < len(MODELLER) - 1:
                sonraki = MODELLER[i + 1]
                print(f"[!] Model {model} yanit vermedi, {sonraki} modeline geciliyor...")
            else:
                print(f"[!] Model {model} de yanit vermedi. Tum modeller denendi.")

    # Hiçbir model yanıt veremediyse
    return "Su an bulut beynim cok yogun, lutfen bir dakika sonra tekrar dene."


# ---------------------------------------------------------------------------
# Sesden Metne Çevirme (STT) — Gemini ile  (YENİ)
# ---------------------------------------------------------------------------

# STT için özel sistem talimatı
_STT_TALIMATI = (
    "Bu bir ses kaydından metin çıkarma görevi. "
    "Ses kaydındaki Türkçe konuşmayı, olduğu gibi düz metin olarak yaz. "
    "Ekstra açıklama, yorum veya format ekleme. "
    "Eğer ses anlaşılmıyorsa veya boşsa sadece 'ANLASILMADI' yaz."
)

_STT_AYARLARI = genai.types.GenerateContentConfig(
    system_instruction=_STT_TALIMATI,
    temperature=0.1,       # yaratıcılık düşük — sadık çeviri
    max_output_tokens=200,
)


def sesi_metne_cevir(ses_dosyasi_yolu: str) -> str | None:
    """
    Ses dosyasını (.wav, .m4a, .mp3) Gemini'ye gönderip
    içindeki konuşmayı metin olarak döner.

    - PyAudio/SpeechRecognition yerine bulut STT.
    - Anlaşılamazsa veya hata olursa None döner.
    """
    try:
        # Dosyayı Gemini'ye yükle
        with open(ses_dosyasi_yolu, "rb") as f:
            ses_verisi = f.read()

        # MIME tipini belirle
        uzanti = ses_dosyasi_yolu.lower().rsplit(".", 1)[-1]
        mime_tipleri = {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "m4a": "audio/mp4",
            "ogg": "audio/ogg",
            "webm": "audio/webm",
        }
        mime = mime_tipleri.get(uzanti, "audio/wav")

        # Cascade fallback ile STT dene
        for i, model in enumerate(MODELLER):
            try:
                client = _get_client()
                if client is None:
                    return None
                yanit = client.models.generate_content(
                    model=model,
                    contents=[
                        genai.types.Part.from_bytes(
                            data=ses_verisi,
                            mime_type=mime,
                        ),
                        "Bu ses kaydındaki konuşmayı Türkçe metin olarak yaz.",
                    ],
                    config=_STT_AYARLARI,
                )
                metin = yanit.text.strip()

                if not metin or metin == "ANLASILMADI":
                    return None

                return metin

            except Exception:
                if i < len(MODELLER) - 1:
                    print(f"[!] STT: Model {model} basarisiz, sonraki deneniyor...")
                continue

        return None

    except Exception as e:
        print(f"[!] STT hatasi: {e}")
        return None

