"""
test_butce.py
butce_motoru.py fonksiyonlarının birim testleri.
"""

import json
from pathlib import Path

import butce_motoru as butce


# --- Tutar ayıklama testleri ---

def test_basit_tutar():
    """'450 lira market' → 450.0"""
    sonuc = butce.harcama_ayikla("450 lira market harcadım")
    assert sonuc is not None
    tutar, aciklama, kategori = sonuc
    assert tutar == 450.0
    assert kategori == "market"


def test_tl_kisaltma():
    """'100 TL' formatı"""
    sonuc = butce.harcama_ayikla("100 tl benzin aldım")
    assert sonuc is not None
    assert sonuc[0] == 100.0
    assert sonuc[2] == "ulaşım"  # benzin → ulaşım


def test_ondalik_virgul():
    """'25,50 lira' → 25.5"""
    sonuc = butce.harcama_ayikla("25,50 lira kahve aldım")
    assert sonuc is not None
    assert sonuc[0] == 25.5
    assert sonuc[2] == "yemek"  # kahve → yemek


def test_liraya_eki():
    """'75 liraya' Türkçe ek"""
    sonuc = butce.harcama_ayikla("75 liraya taksi tuttum")
    assert sonuc is not None
    assert sonuc[0] == 75.0
    assert sonuc[2] == "ulaşım"


def test_liralık_eki():
    """'200 liralık' Türkçe ek"""
    sonuc = butce.harcama_ayikla("200 liralık ayakkabı aldım")
    assert sonuc is not None
    assert sonuc[0] == 200.0
    assert sonuc[2] == "giyim"


def test_tutar_bulunamaz():
    """Tutar olmayan cümle"""
    assert butce.harcama_ayikla("bugün hava güzel") is None


def test_kategori_diger():
    """Bilinmeyen kategori → diğer"""
    sonuc = butce.harcama_ayikla("50 lira hediye aldım")
    assert sonuc is not None
    assert sonuc[2] == "diğer"


# --- Harcama ekleme testi ---

def test_harcama_ekle(tmp_path, monkeypatch):
    """Harcama JSON'a yazılır."""
    dosya = tmp_path / "butce.json"
    monkeypatch.setattr(butce, "BUTCE_DOSYASI", dosya)

    yanit = butce.harcama_ekle("450 lira market harcadım")
    assert "450" in yanit
    assert "market" in yanit

    with open(dosya, "r", encoding="utf-8") as f:
        kayitlar = json.load(f)
    assert len(kayitlar) == 1
    assert kayitlar[0]["tutar"] == 450.0
    assert kayitlar[0]["kategori"] == "market"


def test_harcama_ekle_tutar_yok(tmp_path, monkeypatch):
    """Tutar bulunamazsa uygun mesaj döner."""
    dosya = tmp_path / "butce.json"
    monkeypatch.setattr(butce, "BUTCE_DOSYASI", dosya)

    yanit = butce.harcama_ekle("bugün yürüyüşe çıktım")
    assert "bulamadım" in yanit.lower()


# --- Özet testi ---

def test_harcama_ozeti_bos(tmp_path, monkeypatch):
    """Kayıt yoksa uygun mesaj."""
    dosya = tmp_path / "butce.json"
    dosya.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(butce, "BUTCE_DOSYASI", dosya)

    sonuc = butce.harcama_ozeti()
    assert "yok" in sonuc.lower()


def test_harcama_ozeti_dolu(tmp_path, monkeypatch):
    """Kayıtlar varsa toplam gösterilir."""
    dosya = tmp_path / "butce.json"
    veri = [
        {"tutar": 200, "aciklama": "market", "kategori": "market", "tarih": "2026-02-22"},
        {"tutar": 50,  "aciklama": "kahve",  "kategori": "yemek",  "tarih": "2026-02-22"},
    ]
    dosya.write_text(json.dumps(veri, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(butce, "BUTCE_DOSYASI", dosya)

    sonuc = butce.harcama_ozeti()
    assert "250" in sonuc
    assert "market" in sonuc


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
