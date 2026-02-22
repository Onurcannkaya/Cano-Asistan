"""
main.py
Cano'nun kalbi — tüm modülleri bir araya getirir.

Çalışma akışı:
  1. Arka planda her dakika hatırlatıcıları kontrol eden bir thread başlar.
  2. Ana döngü kullanıcıyı dinler.
  3. Uyanma kelimesi: "cano" veya STT alternatifleri geçen komutlar işlenir.
  4. Çıkış → Bütçe özeti → Hatırlatıcı sorgulama → Harcama ekleme
     → Hatırlatıcı ekleme sırası ile kontrol edilir.
  5. "çıkış" / "görüşürüz" duyulursa program nazikçe sonlanır.
"""

import threading
import time

import schedule

import ses_motoru as ses
import hatirlatici_motoru as hat
import butce_motoru as butce                 # YENİ

# ---------------------------------------------------------------------------
# Wake word alternatifleri  (STT TOLERANSLI)
# ---------------------------------------------------------------------------
# Google STT "cano" yerine bazen bunları döküyor
WAKE_WORDS = ["cano", "canım", "can o", "canı", "kano"]

# ---------------------------------------------------------------------------
# Anahtar kelime tanımlama
# ---------------------------------------------------------------------------

# Hatırlatıcı ekleme komutları
HATIRLATICI_ANAHTAR = [
    "hatırlatıcı", "hatırlat", "ayarla", "kur",
    "dakika sonra", "saat sonra", "yarım saat",
]

# Hatırlatıcı sorgulama komutları
# Bu liste ekleme listesinden ÖNCE kontrol ediliyor.
SORGULAMA_ANAHTAR = [
    "hatırlatıcılarımı oku", "hatırlatıcılarım", "hatırlatıcılar",
    "neler var", "ne var", "bekleyen", "bekleyenler",
    "okur musun", "listele",
]

# Bütçe / harcama ekleme komutları  (YENİ)
HARCAMA_ANAHTAR = ["harcadım", "aldım", "verdim", "ödedim", "lira", "tl"]

# Bütçe özeti sorgulama komutları  (YENİ)
BUTCE_OZET_ANAHTAR = [
    "ne kadar harcadım", "bütçe özeti", "harcamalarım",
    "toplam harcama", "bütçem", "harcama özeti",
]

# Çıkış komutları
CIKIS_ANAHTAR = ["çıkış", "kapat", "görüşürüz", "hoşça kal", "bay bay"]


def _komut_icerir(metin: str, anahtar_liste: list[str]) -> bool:
    """Metinde anahtar kelimelerden biri geçiyor mu?"""
    m = metin.lower()
    return any(k in m for k in anahtar_liste)


# ---------------------------------------------------------------------------
# Arka plan zamanlayıcısı
# ---------------------------------------------------------------------------

def _zamanlayici_baslat() -> None:
    """
    Her dakika hatirlatici_motoru.kontrol_et'i çağıran
    schedule döngüsünü arka plan thread'inde çalıştırır.
    """
    schedule.every(1).minutes.do(hat.kontrol_et, ses.konuş)

    def _calistir():
        while True:
            schedule.run_pending()
            time.sleep(10)

    thread = threading.Thread(target=_calistir, daemon=True)
    thread.start()


# ---------------------------------------------------------------------------
# Ana döngü
# ---------------------------------------------------------------------------

def main():
    print("=" * 50)
    print("  🎙️  Cano Kişisel Asistan — başlatılıyor...")
    print("=" * 50)

    _zamanlayici_baslat()
    ses.konuş("Merhaba! Ben Cano. Sana nasıl yardımcı olabilirim?")

    while True:
        metin = ses.dinle()

        if metin is None:
            continue

        # --- Wake Word (STT toleranslı) ---
        if not any(w in metin.lower() for w in WAKE_WORDS):
            print("💤  (Wake word algılanmadı, yoksayılıyor)")
            continue

        # --- Çıkış ---
        if _komut_icerir(metin, CIKIS_ANAHTAR):
            ses.konuş("Görüşürüz! İyi günler dilerim.")
            break

        # --- Bütçe özeti sorgulama (YENİ) ---
        if _komut_icerir(metin, BUTCE_OZET_ANAHTAR):
            yanit = butce.harcama_ozeti()
            ses.konuş(yanit)
            continue

        # --- Hatırlatıcı sorgulama ---
        if _komut_icerir(metin, SORGULAMA_ANAHTAR):
            yanit = hat.bekleyenleri_oku()
            ses.konuş(yanit)
            continue

        # --- Harcama ekleme (YENİ) ---
        if _komut_icerir(metin, HARCAMA_ANAHTAR):
            yanit = butce.harcama_ekle(metin)
            ses.konuş(yanit)
            continue

        # --- Hatırlatıcı ekleme ---
        if _komut_icerir(metin, HATIRLATICI_ANAHTAR):
            yanit = hat.hatirlatici_ekle(metin)
            ses.konuş(yanit)
            continue

        # --- Tanımlanamayan komut ---
        ses.konuş("Anlayamadım, tekrar söyler misin?")


if __name__ == "__main__":
    main()
