"""
hatirlatici_motoru.py
Cano'nun hafızası ve zamanlama beyni.
- Kullanıcının sesli komutundan saat bilgisini ayıklar.
- Göreceli zaman ifadelerini destekler ("5 dakika sonra", "yarım saat sonra").
- Coğrafi (konum bazlı) hatırlatıcıları destekler.
- Hatırlatıcıları veri.json dosyasına kaydeder / yükler.
- Her dakika kontrol ederek zamanı gelen hatırlatıcıları tetikler.
- Bekleyen hatırlatıcıları sesli okur.
"""

import json
import math
import re
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Callable

VERI_DOSYASI = Path("veri.json")


# ---------------------------------------------------------------------------
# Saklı konumlar ve Haversine  (YENİ — Geofencing)
# ---------------------------------------------------------------------------

# Bilinen konumlar: isim → [enlem, boylam]  (Sivas civarı temsili koordinatlar)
SAKLI_KONUMLAR: dict[str, list[float]] = {
    "belediye":  [39.7500, 37.0150],
    "ev":        [39.7450, 37.0100],
    "market":    [39.7550, 37.0200],
    "okul":      [39.7480, 37.0180],
    "hastane":   [39.7520, 37.0120],
}

# Konum ipucu kelimeleri — bu kelimeler geçiyorsa zamanlı değil konumlu hatırlatıcı
_KONUM_IPUCU = ["gidince", "varınca", "yaklaşınca", "ulaşınca", "gelince"]

# Tetikleme yarıçapı (metre) — simülatörde isim eşleşmesi kullanılır
GEOFENCE_YARICAP_M = 200


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    İki koordinat arasındaki mesafeyi metre cinsinden hesaplar.
    Basit Haversine formülü.
    """
    R = 6_371_000  # Dünya yarıçapı (metre)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def konum_ayikla(metin: str) -> str | None:
    """
    Cümlede konum ipucu kelimesi ('gidince', 'varınca' vb.) varsa,
    SAKLI_KONUMLAR'daki eşleşen konumu döner.
    Bulamazsa None döner.
    """
    m = metin.lower()

    # Konum ipucu var mı?
    if not any(ip in m for ip in _KONUM_IPUCU):
        return None

    # Hangi konum geçiyor?
    for konum_adi in SAKLI_KONUMLAR:
        if konum_adi in m:
            return konum_adi

    return None


# ---------------------------------------------------------------------------
# Göreceli zaman ayıklama  (YENİ)
# ---------------------------------------------------------------------------

# Türkçe yazılı sayılar → karşılık gelen rakam değeri
_YAZI_SAYI = {
    "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5,
    "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10,
    "onbir": 11, "on bir": 11, "oniki": 12, "on iki": 12,
    "onüç": 13, "on üç": 13, "ondört": 14, "on dört": 14,
    "onbeş": 15, "on beş": 15, "yirmi": 20, "otuz": 30,
    "kırk": 40, "elli": 50, "altmış": 60,
}


def goreceli_zaman_ayikla(metin: str) -> datetime | None:
    """
    'X dakika sonra', 'yarım saat sonra', 'bir buçuk saat sonra'
    gibi göreceli ifadelerden hedef datetime üretir.
    Bulamazsa None döner.
    """
    m = metin.lower()
    simdi = datetime.now()

    # --- "yarım saat sonra" ---
    if re.search(r'yarım\s+saat\s+sonra', m):
        return simdi + timedelta(minutes=30)

    # --- "bir buçuk saat sonra" ---
    if re.search(r'bir?\s+buçuk\s+saat\s+sonra', m):
        return simdi + timedelta(minutes=90)

    # --- "X dakika sonra"  (rakam veya yazı ile) ---
    es = re.search(r'(\d+)\s+dakika\s+sonra', m)
    if es:
        return simdi + timedelta(minutes=int(es.group(1)))

    for yazi, deger in _YAZI_SAYI.items():
        if re.search(yazi + r'\s+dakika\s+sonra', m):
            return simdi + timedelta(minutes=deger)

    # --- "X saat sonra"  (rakam veya yazı ile) ---
    es = re.search(r'(\d+)\s+saat\s+sonra', m)
    if es:
        return simdi + timedelta(hours=int(es.group(1)))

    for yazi, deger in _YAZI_SAYI.items():
        if re.search(yazi + r'\s+saat\s+sonra', m):
            return simdi + timedelta(hours=deger)

    return None


# ---------------------------------------------------------------------------
# Mutlak saat ayıklama  (GÜNCELLENDİ)
# ---------------------------------------------------------------------------

def saati_ayikla(metin: str) -> tuple[int, int] | None:
    """
    Verilen Türkçe metinden saat ve dakika bilgisini çekmeye çalışır.

    Desteklenen örüntüler (Google STT'nin esnek çıktıları dahil):
      "20:30"          → (20, 30)     klasik
      "12.25"          → (12, 25)     noktalı
      "0025"           → (0, 25)      bitişik
      "00 25"          → (0, 25)      boşluklu
      "20:30'da"       → (20, 30)     Türkçe ek
      "0025de"         → (0, 25)      Türkçe ek
      "akşam sekizde"  → (20, 0)      yazılı saat + dönem ipucu
      "sabah dokuzda"  → (9, 0)       yazılı saat + dönem ipucu
    """
    metin_kucuk = metin.lower()

    # --- Sayısal biçim (GÜNCELLENDİ) ---
    # Ayırıcı olarak ':', '.', boşluk veya hiçbiri kabul edilir.
    # Sondaki Türkçe hal ekleri ('da, 'de, te, ta) yoksayılır.
    eslesme = re.search(
        r'(\d{1,2})[\s:.]?(\d{2})(?:[\'`\u2019]?(?:da|de|te|ta))?(?:\s|$|[^0-9])',
        metin_kucuk
    )
    if eslesme:
        saat = int(eslesme.group(1))
        dakika = int(eslesme.group(2))
        if 0 <= saat <= 23 and 0 <= dakika <= 59:
            return (saat, dakika)

    # --- Türkçe yazılı sayılar ---
    saatler = {
        "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5,
        "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10,
        "onbir": 11, "on bir": 11, "onikide": 12, "on iki": 12,
    }

    # Sabah / öğleden sonra / akşam / gece ipuçları
    sabah_ipucu    = any(w in metin_kucuk for w in ["sabah", "öğleden önce"])
    aksam_ipucu    = any(w in metin_kucuk for w in ["akşam", "akşamüstü"])
    ogleden_sonra  = "öğleden sonra" in metin_kucuk
    gece_ipucu     = "gece" in metin_kucuk

    for kelime, deger in saatler.items():
        # "sekizde", "sekize", "sekiz" gibi ekleri de yakala
        if re.search(r'\b' + kelime + r'[a-zçğışöü]*\b', metin_kucuk):
            saat = deger
            if aksam_ipucu or ogleden_sonra or gece_ipucu:
                if saat < 12:
                    saat += 12
            elif not sabah_ipucu and saat <= 7:
                # Belirsizse küçük saatleri akşam say (örn. "saat üçte" → 15:00)
                saat += 12
            return (saat % 24, 0)

    return None


# ---------------------------------------------------------------------------
# JSON veri katmanı
# ---------------------------------------------------------------------------

def _yukle() -> list[dict]:
    """veri.json'dan hatırlatıcı listesini yükler."""
    if VERI_DOSYASI.exists():
        with open(VERI_DOSYASI, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _kaydet(liste: list[dict]) -> None:
    """Hatırlatıcı listesini veri.json'a yazar."""
    with open(VERI_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(liste, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Hatırlatıcı işlemleri  (GÜNCELLENDİ)
# ---------------------------------------------------------------------------

def hatirlatici_ekle(metin: str) -> str:
    """
    Kullanıcının söylediği metinden zaman veya konum ayıklar ve hatırlatıcı kaydeder.
    Öncelik sırası: konum → göreceli zaman → mutlak saat.
    Geri bildirim olarak Cano'nun söyleyeceği cümleyi döner.
    """

    # --- 0) Konum bazlı hatırlatıcı kontrolü (YENİ — Geofencing) ---
    konum = konum_ayikla(metin)
    if konum is not None:
        liste = _yukle()
        liste.append({
            "metin": metin,
            "zaman": None,          # zamana bağlı değil
            "konum": konum,         # konuma bağlı
            "tetiklendi": False
        })
        _kaydet(liste)
        return f"Tamam! {konum.capitalize()}'e varınca sana hatırlatacağım."

    # --- 1) Göreceli zaman kontrolü ---
    hedef_zaman = goreceli_zaman_ayikla(metin)
    if hedef_zaman is not None:
        hatirlatici_zamani = hedef_zaman.strftime("%Y-%m-%d %H:%M")
        saat_str = hedef_zaman.strftime("%H:%M")

        liste = _yukle()
        liste.append({
            "metin": metin,
            "zaman": hatirlatici_zamani,
            "tetiklendi": False
        })
        _kaydet(liste)
        return f"Tamam! {saat_str} için hatırlatıcı kurdum."

    # --- 2) Mutlak saat kontrolü ---
    sonuc = saati_ayikla(metin)
    if sonuc is None:
        return "Üzgünüm, bir saat bilgisi bulamadım. Lütfen tekrar söyler misin?"

    saat, dakika = sonuc
    simdi = datetime.now()

    # Bugün için hedef zamanı oluştur
    hedef = simdi.replace(hour=saat, minute=dakika, second=0, microsecond=0)

    # Eğer bu saat bugün zaten geçtiyse → yarına kur  (YENİ)
    if hedef <= simdi:
        hedef += timedelta(days=1)

    hatirlatici_zamani = hedef.strftime("%Y-%m-%d %H:%M")

    liste = _yukle()
    liste.append({
        "metin": metin,
        "zaman": hatirlatici_zamani,
        "tetiklendi": False
    })
    _kaydet(liste)

    # Kullanıcıya geri bildirim
    gun_bilgisi = "yarın" if hedef.date() > simdi.date() else "bugün"
    return f"Tamam! {gun_bilgisi} {saat:02d}:{dakika:02d} için hatırlatıcı kurdum."


# ---------------------------------------------------------------------------
# Hatırlatıcı sorgulama  (YENİ)
# ---------------------------------------------------------------------------

def bekleyenleri_oku() -> str:
    """
    Henüz tetiklenmemiş hatırlatıcıları sesli okumak için
    düzenli bir metin olarak döner.
    """
    liste = _yukle()
    bekleyenler = [h for h in liste if not h["tetiklendi"]]

    if not bekleyenler:
        return "Şu an bekleyen hatırlatıcın yok."

    satirlar = []
    for i, h in enumerate(bekleyenler, 1):
        if h.get("konum"):
            # Konum bazlı hatırlatıcı
            satirlar.append(f"{i}. 📍 {h['konum']}'e varınca, {h['metin']}")
        else:
            # Zaman bazlı hatırlatıcı
            zaman = h["zaman"].split(" ")[1] if " " in str(h.get("zaman", "")) else h.get("zaman", "?")
            satirlar.append(f"{i}. saat {zaman}, {h['metin']}")

    baslik = f"Toplam {len(bekleyenler)} bekleyen hatırlatıcın var: "
    return baslik + ". ".join(satirlar)


# ---------------------------------------------------------------------------
# Arka plan kontrol
# ---------------------------------------------------------------------------

def kontrol_et(bildirim_fonksiyonu: Callable[[str], None],
               mevcut_konum: str | None = None) -> None:
    """
    Bu fonksiyon her dakika çağrılır.
    - Zamanı gelen hatırlatıcıları tetikler.
    - Konum eşleşen hatırlatıcıları tetikler (mevcut_konum verilmişse).
    bildirim_fonksiyonu: ses_motoru.konuş gibi bir çağrılabilir nesne.
    mevcut_konum: kullanıcının şu an bulunduğu konum adı (simülatörden).
    """
    simdi = datetime.now()
    simdi_str = simdi.strftime("%Y-%m-%d %H:%M")

    liste = _yukle()
    degisti = False

    for hatirlatici in liste:
        if hatirlatici["tetiklendi"]:
            continue

        # --- Zaman bazlı kontrol ---
        if hatirlatici.get("zaman") and hatirlatici["zaman"] == simdi_str:
            mesaj = f"Hatırlatma zamanı! {hatirlatici['metin']}"
            bildirim_fonksiyonu(mesaj)
            hatirlatici["tetiklendi"] = True
            degisti = True

        # --- Konum bazlı kontrol (YENİ — Geofencing) ---
        elif (hatirlatici.get("konum")
              and mevcut_konum
              and hatirlatici["konum"].lower() == mevcut_konum.lower()):
            mesaj = f"📍 Konum hatırlatması! {hatirlatici['metin']}"
            bildirim_fonksiyonu(mesaj)
            hatirlatici["tetiklendi"] = True
            degisti = True

    if degisti:
        _kaydet(liste)
