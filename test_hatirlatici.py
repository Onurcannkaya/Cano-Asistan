"""
test_hatirlatici.py
hatirlatici_motoru.py içindeki fonksiyonların birim testleri.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

# Test edilecek modül
import hatirlatici_motoru as hat


def test_sayisal_klasik():
    """Klasik 20:30 formatı"""
    assert hat.saati_ayikla("saat 20:30'da buluşalım") == (20, 30)


def test_sayisal_noktali():
    """Noktalı 12.25 formatı"""
    assert hat.saati_ayikla("saat 12.25'te toplanti") == (12, 25)


def test_sayisal_bitisik():
    """Bitişik 0025 formatı (Google STT)"""
    assert hat.saati_ayikla("0025 de hatırlat") == (0, 25)


def test_sayisal_bosluklu():
    """Boşluklu 00 25 formatı (Google STT)"""
    assert hat.saati_ayikla("00 25'de beni ara") == (0, 25)


def test_sayisal_2030_bitisik():
    """Bitişik 2030 formatı"""
    assert hat.saati_ayikla("2030da toplantı var") == (20, 30)


def test_yazili_aksam_sekiz():
    """Yazılı: akşam sekizde"""
    assert hat.saati_ayikla("akşam sekizde hali saha maçı var") == (20, 0)


def test_yazili_sabah_dokuz():
    """Yazılı: sabah dokuzda"""
    assert hat.saati_ayikla("sabah dokuzda toplanti") == (9, 0)


def test_yazili_belirsiz_uc():
    """Belirsiz küçük saat → akşam sayılır"""
    assert hat.saati_ayikla("saat üçte gel") == (15, 0)


def test_yazili_on():
    """Yazılı: on → sabah 10"""
    assert hat.saati_ayikla("saat onda buluşalım") == (10, 0)


def test_bulunamadi():
    """Saat bilgisi olmayan metin"""
    assert hat.saati_ayikla("bugün hava güzel") is None


# --- Göreceli zaman testleri ---

def test_goreceli_dakika():
    """5 dakika sonra"""
    oncesi = datetime.now()
    sonuc = hat.goreceli_zaman_ayikla("5 dakika sonra hatırlat")
    sonrasi = datetime.now()
    assert sonuc is not None
    # ±1 dakika tolerans
    beklenen = oncesi + timedelta(minutes=5)
    assert abs((sonuc - beklenen).total_seconds()) < 60


def test_goreceli_yarim_saat():
    """yarım saat sonra"""
    oncesi = datetime.now()
    sonuc = hat.goreceli_zaman_ayikla("yarım saat sonra toplantı")
    assert sonuc is not None
    beklenen = oncesi + timedelta(minutes=30)
    assert abs((sonuc - beklenen).total_seconds()) < 60


def test_goreceli_bir_bucuk_saat():
    """bir buçuk saat sonra"""
    oncesi = datetime.now()
    sonuc = hat.goreceli_zaman_ayikla("bir buçuk saat sonra git")
    assert sonuc is not None
    beklenen = oncesi + timedelta(minutes=90)
    assert abs((sonuc - beklenen).total_seconds()) < 60


def test_goreceli_saat():
    """2 saat sonra"""
    oncesi = datetime.now()
    sonuc = hat.goreceli_zaman_ayikla("2 saat sonra ara")
    assert sonuc is not None
    beklenen = oncesi + timedelta(hours=2)
    assert abs((sonuc - beklenen).total_seconds()) < 60


def test_goreceli_yok():
    """Göreceli ifade olmayan metin"""
    assert hat.goreceli_zaman_ayikla("akşam sekizde gel") is None


# --- Bekleyenleri oku testi ---

def test_bekleyenleri_oku_bos(tmp_path, monkeypatch):
    """Hiç bekleyen yoksa uygun mesaj gelir."""
    dosya = tmp_path / "veri.json"
    dosya.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(hat, "VERI_DOSYASI", dosya)

    sonuc = hat.bekleyenleri_oku()
    assert "yok" in sonuc.lower()


def test_bekleyenleri_oku_dolu(tmp_path, monkeypatch):
    """Bekleyen hatırlatıcılar varsa listelenir."""
    dosya = tmp_path / "veri.json"
    veri = [
        {"metin": "toplantı", "zaman": "2026-12-31 10:00", "tetiklendi": False},
        {"metin": "eski", "zaman": "2026-01-01 08:00", "tetiklendi": True},
    ]
    dosya.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(hat, "VERI_DOSYASI", dosya)

    sonuc = hat.bekleyenleri_oku()
    assert "1" in sonuc         # en az 1 bekleyen
    assert "toplantı" in sonuc  # metin geçmeli
    assert "eski" not in sonuc  # tetiklenen görünmemeli


# --- Geçmiş saat → yarına kurma testi ---

def test_gecmis_saat_yarina_kurulur(tmp_path, monkeypatch):
    """Geçmiş saat verildiğinde hatırlatıcı yarına kurulur."""
    dosya = tmp_path / "veri.json"
    dosya.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(hat, "VERI_DOSYASI", dosya)

    # Kesinlikle geçmiş bir saat: 00:01
    simdi = datetime.now()
    if simdi.hour > 0 or simdi.minute > 1:
        yanit = hat.hatirlatici_ekle("saat 00:01 de hatırlat")
        assert "yarın" in yanit.lower()

        # JSON'a yazıldığını doğrula
        with open(dosya, "r", encoding="utf-8") as f:
            kayitlar = json.load(f)
        assert len(kayitlar) == 1
        yarin = (simdi.date() + timedelta(days=1)).isoformat()
        assert kayitlar[0]["zaman"].startswith(yarin)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
