"""
butce_motoru.py
Cano'nun cüzdanı — sesli harcama takibi.
- Kullanıcının söylediği cümleden tutarı ve açıklamayı ayıklar.
- Harcamaları butce.json dosyasına kaydeder.
- Toplam harcama özetini sesli okumak için metin döner.
"""

import json
import re
from datetime import datetime
from pathlib import Path

BUTCE_DOSYASI = Path("butce.json")

# ---------------------------------------------------------------------------
# Bilinen kategoriler — cümleden kategori tahmini için
# ---------------------------------------------------------------------------

_KATEGORI_ANAHTAR = {
    "market":   ["market", "migros", "bim", "a101", "şok", "carrefour", "manav"],
    "fatura":   ["fatura", "elektrik", "su", "doğalgaz", "internet", "telefon"],
    "ulaşım":   ["taksi", "benzin", "otobüs", "metro", "ulaşım", "otopark", "köprü"],
    "yemek":    ["yemek", "restoran", "kafe", "kahve", "döner", "pizza", "burger"],
    "giyim":    ["giyim", "kıyafet", "ayakkabı", "mont", "pantolon", "gömlek"],
    "sağlık":   ["eczane", "ilaç", "doktor", "hastane", "sağlık", "muayene"],
    "eğlence":  ["sinema", "konser", "maç", "oyun", "netflix", "spotify"],
    "eğitim":   ["kitap", "kurs", "eğitim", "okul", "kırtasiye"],
}


def _kategori_tahmin_et(metin: str) -> str:
    """Cümleden anahtar kelimelere bakarak kategori tahmin eder."""
    m = metin.lower()
    for kategori, kelimeler in _KATEGORI_ANAHTAR.items():
        if any(k in m for k in kelimeler):
            return kategori
    return "diğer"


# ---------------------------------------------------------------------------
# Tutar ayıklama
# ---------------------------------------------------------------------------

def harcama_ayikla(metin: str) -> tuple[float, str, str] | None:
    """
    Cümleden tutarı (float), açıklamayı (str) ve kategoriyi (str) çeker.

    Desteklenen formatlar:
      "450 lira",  "100 TL",  "25,50 lira",  "1.200 tl",
      "75.5 liraya", "200 liralık"

    Tutar bulunamazsa None döner.
    """
    metin_kucuk = metin.lower()

    # Regex: binlik nokta (isteğe bağlı) + ondalık virgül/nokta (isteğe bağlı) + lira/tl
    eslesme = re.search(
        r'(\d{1,3}(?:\.\d{3})*(?:[,\.]\d{1,2})?)\s*(?:lira|tl)\w*',
        metin_kucuk
    )
    if not eslesme:
        return None

    tutar_str = eslesme.group(1)
    # Binlik noktaları kaldır, ondalık virgülü noktaya çevir
    tutar_str = tutar_str.replace(".", "").replace(",", ".")
    # Eğer ondalık yoksa float'a çevir; doğal olarak çalışır
    # Ama binlik noktayı kaldırdığımızda "25.50" → "2550" olabilir,
    # bunu düzeltelim: orijinaldeki . veya , sonrası 1-2 haneyse ondalıktır.
    ham = eslesme.group(1)
    if re.search(r'[,\.]\d{1,2}$', ham) and not re.search(r'\.\d{3}', ham):
        # Ondalık var ve binlik nokta yok → sadece virgülü noktaya çevir
        tutar_str = ham.replace(",", ".")
    else:
        # Binlik noktalı sayı veya tam sayı
        tutar_str = ham.replace(".", "").replace(",", ".")

    tutar = float(tutar_str)

    # Tutarı ve para birimini cümleden çıkararak açıklama oluştur
    aciklama = re.sub(
        r'\d{1,3}(?:\.\d{3})*(?:[,\.]\d{1,2})?\s*(?:lira|tl)\w*',
        '', metin_kucuk
    ).strip()
    # Gereksiz kelimeleri temizle
    for soz in ["harcadım", "aldım", "verdim", "ödedim", "cano", "canım",
                "can o", "canı", "kano", "bugün", "dün", "şimdi"]:
        aciklama = aciklama.replace(soz, "")
    aciklama = " ".join(aciklama.split()).strip(" .,;:")  # çoklu boşlukları temizle
    if not aciklama:
        aciklama = "genel harcama"

    kategori = _kategori_tahmin_et(metin)

    return (tutar, aciklama, kategori)


# ---------------------------------------------------------------------------
# JSON veri katmanı
# ---------------------------------------------------------------------------

def _yukle() -> list[dict]:
    """butce.json'dan harcama listesini yükler."""
    if BUTCE_DOSYASI.exists():
        with open(BUTCE_DOSYASI, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _kaydet(liste: list[dict]) -> None:
    """Harcama listesini butce.json'a yazar."""
    with open(BUTCE_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(liste, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Harcama ekleme
# ---------------------------------------------------------------------------

def harcama_ekle(metin: str) -> str:
    """
    Kullanıcının söylediği cümleden tutar ayıklar, butce.json'a kaydeder.
    Geri bildirim metni döner.
    """
    sonuc = harcama_ayikla(metin)
    if sonuc is None:
        return "Bir tutar bulamadım. Lütfen '450 lira market' gibi söyler misin?"

    tutar, aciklama, kategori = sonuc

    liste = _yukle()
    liste.append({
        "tutar": tutar,
        "aciklama": aciklama,
        "kategori": kategori,
        "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    _kaydet(liste)

    return f"Kaydettim! {tutar:.0f} lira, {kategori} kategorisinde."


# ---------------------------------------------------------------------------
# Harcama özeti
# ---------------------------------------------------------------------------

def harcama_ozeti() -> str:
    """
    Toplam harcamayı ve kategori dağılımını okunabilir metin olarak döner.
    """
    liste = _yukle()

    if not liste:
        return "Henüz kayıtlı harcaman yok."

    toplam = sum(h["tutar"] for h in liste)

    # Kategori bazında toplam
    kategoriler: dict[str, float] = {}
    for h in liste:
        kat = h.get("kategori", "diğer")
        kategoriler[kat] = kategoriler.get(kat, 0) + h["tutar"]

    # En yüksekten düşüğe sırala
    sirali = sorted(kategoriler.items(), key=lambda x: x[1], reverse=True)

    parcalar = [f"Şu ana kadar toplam {toplam:.0f} lira harcadın."]
    for kat, miktar in sirali[:5]:  # en fazla 5 kategori
        parcalar.append(f"{kat}: {miktar:.0f} lira")

    return " ".join(parcalar)
