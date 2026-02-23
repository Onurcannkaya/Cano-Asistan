"""
zeka_motoru.py
Cano'nun bulut beyni — Google Gemini API + Cascade Fallback + Multi-Turn.
- Sohbet geçmişi tutarak bağlamlı yanıtlar verir.
- Birden fazla modeli sırayla dener (şelale yedekleme).
- Streaming desteği ile hızlı yanıt başlangıcı.
- Tüm modeller başarısız olursa güvenli mesaj döner.
"""

import os
from collections import deque

from google import genai

# ---------------------------------------------------------------------------
# Yapılandırma
# ---------------------------------------------------------------------------

# API anahtarı: ortam değişkeninden çek (güvenlik için koda ASLA yazılmaz!)
API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Şelale model hiyerarşisi — sırayla denenir
MODELLER = [
    "gemini-2.5-flash",       # 1. tercih: en hızlı ve güncel
    "gemini-2.5-pro",         # 2. yedek: en yetenekli
    "gemini-2.0-flash-001",   # 3. yedek: stabil eski versiyon
]

# Cano'nun kişiliğini tanımlayan sistem talimatı — Samimi & Canlı
SISTEM_TALIMATI = (
    "Sen Cano'sun! Onurcan'ın en yakın arkadaşı ve kişisel asistanısın. "
    "Konuşma tarzın samimi, sıcak, enerji dolu ve esprilik. "
    "Cevapların kısa ve öz olsun — 1-2 cümle yeter, çünkü sesli okunacak. "
    "Kalıplaşmış değil, doğal konuş. 'Şey', 'haa', 'yahu', 'bak' gibi günlük ifadeler kullan. "
    "Onurcan'ı tanıyorsun — onu motive et, şakalaş, ilgilen. "
    "Emojileri seviyorsun ama abartmıyorsun — her mesajda 1 tane yeter. "
    "Önceki mesajları hatırla ve sohbetin akışına uy. "
    "Eğer cümle anlaşılmadıysa samimi şekilde tekrar sor, robot gibi konuşma."
)

# Üretim ayarları — biraz daha yaratıcı ve canlı
_URETIM_AYARLARI = genai.types.GenerateContentConfig(
    system_instruction=SISTEM_TALIMATI,
    temperature=0.85,
    max_output_tokens=300,
)

# ---------------------------------------------------------------------------
# Sohbet geçmişi — Multi-Turn Conversation (YENİ)
# ---------------------------------------------------------------------------

# Son N mesajı tut (kullanıcı + asistan çiftleri)
_MAX_GECMIS = 10
_gecmis: deque[dict] = deque(maxlen=_MAX_GECMIS)


def gecmis_temizle():
    """Sohbet geçmişini sıfırlar."""
    _gecmis.clear()


def _gecmis_contents(yeni_mesaj: str) -> list:
    """Geçmişi + yeni mesajı Gemini contents formatında döner."""
    contents = []
    for msg in _gecmis:
        contents.append(genai.types.Content(
            role=msg["role"],
            parts=[genai.types.Part.from_text(text=msg["text"])]
        ))
    # Yeni kullanıcı mesajını ekle
    contents.append(genai.types.Content(
        role="user",
        parts=[genai.types.Part.from_text(text=yeni_mesaj)]
    ))
    return contents


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
# Ana fonksiyon — Cascade Fallback + Multi-Turn
# ---------------------------------------------------------------------------

def gemini_sor(metin: str) -> str:
    """
    Kullanıcının metnini sohbet geçmişiyle birlikte Gemini'ye gönderir.

    Şelale (Cascade) mantığı:
      1. MODELLER listesindeki ilk modeli dener.
      2. Hata alırsa sonraki modele geçer.
      3. Tüm modeller başarısız olursa güvenli mesaj döner.
    """
    for i, model in enumerate(MODELLER):
        try:
            client = _get_client()
            if client is None:
                return "API anahtarı ayarlanmamış. Ayarlar'dan kontrol et."

            # Multi-turn: geçmişi içeriklerle gönder
            contents = _gecmis_contents(metin)

            yanit = client.models.generate_content(
                model=model,
                contents=contents,
                config=_URETIM_AYARLARI,
            )
            cevap = yanit.text.strip()

            if not cevap:
                continue

            # Başarılıysa geçmişe ekle
            _gecmis.append({"role": "user", "text": metin})
            _gecmis.append({"role": "model", "text": cevap})

            return cevap

        except Exception as e:
            if i < len(MODELLER) - 1:
                sonraki = MODELLER[i + 1]
                print(f"[!] Model {model} yanıt vermedi, {sonraki}'e geçiliyor...")
            else:
                print(f"[!] Model {model} de yanıt vermedi. Tüm modeller denendi.")
                print(f"    Hata: {e}")

    return "Şu an bulut beynim çok yoğun, lütfen bir dakika sonra tekrar dene."


# ---------------------------------------------------------------------------
# Sesden Metne Çevirme (STT) — Gemini ile
# ---------------------------------------------------------------------------

_STT_TALIMATI = (
    "Bu bir ses kaydından metin çıkarma görevi. "
    "Ses kaydındaki Türkçe konuşmayı, olduğu gibi düz metin olarak yaz. "
    "Ekstra açıklama, yorum veya format ekleme. "
    "Eğer ses anlaşılmıyorsa veya boşsa sadece 'ANLASILMADI' yaz."
)

_STT_AYARLARI = genai.types.GenerateContentConfig(
    system_instruction=_STT_TALIMATI,
    temperature=0.1,
    max_output_tokens=200,
)


def sesi_metne_cevir(ses_dosyasi_yolu: str) -> str | None:
    """
    Ses dosyasını Gemini'ye gönderip konuşmayı metin olarak döner.
    Anlaşılamazsa veya hata olursa None döner.
    """
    try:
        with open(ses_dosyasi_yolu, "rb") as f:
            ses_verisi = f.read()

        uzanti = ses_dosyasi_yolu.lower().rsplit(".", 1)[-1]
        mime_tipleri = {
            "wav": "audio/wav", "mp3": "audio/mpeg",
            "m4a": "audio/mp4", "ogg": "audio/ogg", "webm": "audio/webm",
        }
        mime = mime_tipleri.get(uzanti, "audio/wav")

        for i, model in enumerate(MODELLER):
            try:
                client = _get_client()
                if client is None:
                    return None
                yanit = client.models.generate_content(
                    model=model,
                    contents=[
                        genai.types.Part.from_bytes(data=ses_verisi, mime_type=mime),
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
                    print(f"[!] STT: Model {model} başarısız, sonraki deneniyor...")
                continue

        return None

    except Exception as e:
        print(f"[!] STT hatası: {e}")
        return None


# ---------------------------------------------------------------------------
# Akıllı Hatırlatıcı Ayrıştırma — Gemini ile (YENİ)
# ---------------------------------------------------------------------------

_HATIRLATICI_TALIMATI = (
    "Kullanıcı bir hatırlatıcı kurmak istiyor. Cümleden şu bilgileri çıkar:\n"
    "1. gorev: Hatırlatılacak görev (kısa ve net)\n"
    "2. zaman_tipi: 'goreceli' | 'mutlak' | 'konum' | 'yok'\n"
    "3. dakika: Göreceli ise kaç dk sonra (int). '1 saat'→60, 'yarım saat'→30\n"
    "4. saat: Mutlak ise saat (24h format, int)\n"
    "5. dakika_mutlak: Mutlak ise dakika (int)\n"
    "6. konum: Konum bazlı ise konum adı\n"
    "\nSADECE JSON yaz, başka bir şey yazma.\n"
    'Örnek: {"gorev":"ilacı iç","zaman_tipi":"goreceli","dakika":30}\n'
    'Örnek: {"gorev":"toplantı","zaman_tipi":"mutlak","saat":14,"dakika_mutlak":30}\n'
    'Örnek: {"gorev":"dosya imzalat","zaman_tipi":"konum","konum":"belediye"}\n'
    'Örnek: {"gorev":"araba yıka","zaman_tipi":"yok"}\n'
    "Şu anki tarih/saat: " + __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
)

_HATIRLATICI_AYARLARI = genai.types.GenerateContentConfig(
    system_instruction=_HATIRLATICI_TALIMATI,
    temperature=0.1,
    max_output_tokens=150,
)


def hatirlatici_ayikla(metin: str) -> dict | None:
    """
    Gemini ile doğal dildeki hatırlatıcı cümlesini ayrıştırır.
    Döner: {"gorev", "zaman_tipi", "dakika"?, "saat"?, "dakika_mutlak"?, "konum"?}
    """
    import json as _json

    try:
        client = _get_client()
        if client is None:
            return None

        yanit = client.models.generate_content(
            model=MODELLER[0],
            contents=metin,
            config=_HATIRLATICI_AYARLARI,
        )
        ham = yanit.text.strip()

        # ```json ... ``` sarmalayıcısını kaldır
        if ham.startswith("```"):
            ham = ham.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        return _json.loads(ham)

    except Exception as e:
        print(f"[!] Akıllı hatırlatıcı ayrıştırma hatası: {e}")
        return None
