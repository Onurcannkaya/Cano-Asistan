"""
app.py
Cano Sesli Asistan — Flet GUI (Mobil Uyumlu v3.0)
- ft.Audio ile ses çalma (pygame yok)
- ft.AudioRecorder ile ses kayıt (PyAudio yok)
- TextField ile metin girişi (klavye desteği)
- Gemini STT ile ses → metin çevirme
- edge-tts ile metin → ses çevirme

Başlatma:
  pip install -r requirements.txt
  python app.py
"""

import os
import threading
import time
import tempfile
from datetime import datetime

import flet as ft
import schedule

import ses_motoru as ses
import hatirlatici_motoru as hat
import butce_motoru as butce
import zeka_motoru as zeka


# ---------------------------------------------------------------------------
# Anahtar kelime listeleri  (KATI NİYET FİLTRESİ)
# ---------------------------------------------------------------------------

_HATIRLATICI_CAPA = ["hatırlat", "uyar"]
_HATIRLATICI_ZAMAN = ["dakika sonra", "saat sonra", "yarım saat"]
_HATIRLATICI_GEO = ["gidince", "varınca", "yaklaşınca", "ulaşınca", "gelince"]

SORGULAMA_ANAHTAR = [
    "hatırlatıcılarımı oku", "hatırlatıcılarım", "hatırlatıcılar",
    "neler var", "ne var", "bekleyen", "bekleyenler",
    "okur musun", "listele",
]
HARCAMA_ANAHTAR = ["harcadım", "aldım", "verdim", "ödedim", "lira", "tl"]
BUTCE_OZET_ANAHTAR = [
    "ne kadar harcadım", "bütçe özeti", "harcamalarım",
    "toplam harcama", "bütçem", "harcama özeti",
]
CIKIS_ANAHTAR = ["çıkış", "kapat", "görüşürüz", "hoşça kal", "bay bay"]


def _komut_icerir(metin: str, anahtar_liste: list[str]) -> bool:
    m = metin.lower()
    return any(k in m for k in anahtar_liste)


def _hatirlatici_niyeti_var(metin: str) -> bool:
    m = metin.lower()
    if any(k in m for k in _HATIRLATICI_GEO):
        return True
    if any(k in m for k in _HATIRLATICI_ZAMAN):
        return True
    return any(k in m for k in _HATIRLATICI_CAPA)


# ---------------------------------------------------------------------------
# Sohbet balonu widget'ı
# ---------------------------------------------------------------------------

def _balon_olustur(mesaj: str, kullanici_mi: bool) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    "Sen" if kullanici_mi else "🤖 Cano",
                    size=11,
                    weight=ft.FontWeight.BOLD,
                    color="#90CAF9" if kullanici_mi else "#CE93D8",
                ),
                ft.Text(mesaj, size=14, color="#E0E0E0", selectable=True),
                ft.Text(
                    datetime.now().strftime("%H:%M"),
                    size=9, color="#757575",
                ),
            ],
            spacing=2, tight=True,
        ),
        bgcolor="#1E2A3A" if kullanici_mi else "#2A1E3A",
        border_radius=ft.BorderRadius.only(
            top_left=16, top_right=16,
            bottom_right=4 if kullanici_mi else 16,
            bottom_left=16 if kullanici_mi else 4,
        ),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        margin=ft.Margin.only(
            left=80 if kullanici_mi else 8,
            right=8 if kullanici_mi else 80,
            bottom=6,
        ),
        alignment=ft.Alignment(1, 0) if kullanici_mi else ft.Alignment(-1, 0),
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
    )


# ---------------------------------------------------------------------------
# Ana uygulama
# ---------------------------------------------------------------------------

def main(page: ft.Page):
    # --- Tema ---
    page.title = "Cano — Kişisel Asistan"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0D1117"
    page.padding = 0
    page.window.width = 420
    page.window.height = 720
    page.fonts = {
        "Inter": "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap"
    }
    page.theme = ft.Theme(font_family="Inter")

    # --- Durum ---
    dinliyor_mu = False
    _son_tts_yol = [None]  # mutable container — closure'da kullanmak için

    # --- ft.Audio bileşeni (TTS ses çalma) ---
    ses_oynatici = ft.Audio(
        src="",
        autoplay=False,
        volume=1.0,
    )
    page.overlay.append(ses_oynatici)

    # --- ft.AudioRecorder bileşeni (mikrofon kayıt) ---
    kayit_dosya_yolu = os.path.join(tempfile.gettempdir(), "cano_kayit.wav")

    ses_kaydedici = ft.AudioRecorder(
        audio_encoder=ft.AudioEncoder.WAV,
    )
    page.overlay.append(ses_kaydedici)

    # --- UI bileşenleri ---
    durum_metni = ft.Text(
        "Hazırım! 🎙️",
        size=12,
        color="#90CAF9",
        text_align=ft.TextAlign.CENTER,
        animate_opacity=ft.Animation(300),
    )

    sohbet_listesi = ft.ListView(
        expand=True, spacing=0,
        padding=ft.Padding.symmetric(vertical=12),
        auto_scroll=True,
    )

    def _mesaj_ekle(mesaj: str, kullanici_mi: bool):
        sohbet_listesi.controls.append(_balon_olustur(mesaj, kullanici_mi))
        page.update()

    def _durumu_guncelle(metin: str, renk: str = "#90CAF9"):
        durum_metni.value = metin
        durum_metni.color = renk
        page.update()

    # --- TTS + ft.Audio ile sesli yanıt ---
    def _cano_konus(metin: str):
        """Cano konuşurken balonu ekler ve ft.Audio ile sesi çalar."""
        _mesaj_ekle(metin, kullanici_mi=False)
        _durumu_guncelle("🔊  Cano konuşuyor...", "#CE93D8")
        try:
            mp3_yol = ses.konuş(metin)
            _son_tts_yol[0] = mp3_yol
            ses_oynatici.src = mp3_yol
            ses_oynatici.play()
            # Ses dosyasının çalmasını bekle (basit yaklaşım)
            time.sleep(max(1.0, len(metin) * 0.08))
        except Exception as e:
            print(f"[TTS] Hata: {e}")
        _durumu_guncelle("Hazırım! 🎙️")

    # --- Komut yönlendiricisi (Router) ---
    def _komutu_isle(metin: str):
        if _komut_icerir(metin, CIKIS_ANAHTAR):
            _cano_konus("Görüşürüz! İyi günler dilerim.")
            return
        if _komut_icerir(metin, BUTCE_OZET_ANAHTAR):
            _cano_konus(butce.harcama_ozeti())
            return
        if _komut_icerir(metin, SORGULAMA_ANAHTAR):
            _cano_konus(hat.bekleyenleri_oku())
            return
        if _komut_icerir(metin, HARCAMA_ANAHTAR):
            _cano_konus(butce.harcama_ekle(metin))
            return
        if _hatirlatici_niyeti_var(metin):
            _cano_konus(hat.hatirlatici_ekle(metin))
            return
        # Sohbet → Gemini LLM
        _durumu_guncelle("🧠  Düşünüyorum...", "#FFD54F")
        yanit = zeka.gemini_sor(metin)
        _cano_konus(yanit)

    # --- Mikrofon butonu (push-to-talk → AudioRecorder) ---
    def _mikrofon_tiklandi(e):
        nonlocal dinliyor_mu
        if dinliyor_mu:
            # İkinci tıklama — kaydı bitir ve işle
            dinliyor_mu = False
            mik_buton.icon = ft.Icons.MIC
            mik_buton.icon_color = "#FFFFFF"
            pulse_ring.opacity = 0
            _durumu_guncelle("⏳  Ses işleniyor...", "#FFD54F")
            page.update()

            def _kaydi_isle():
                nonlocal dinliyor_mu
                try:
                    ses_kaydedici.stop_recording()
                    time.sleep(0.5)  # dosyanın yazılmasını bekle

                    if os.path.exists(kayit_dosya_yolu):
                        metin = zeka.sesi_metne_cevir(kayit_dosya_yolu)
                        if metin:
                            _mesaj_ekle(metin, kullanici_mi=True)
                            _komutu_isle(metin)
                        else:
                            _durumu_guncelle("⚠️  Anlayamadım, tekrar dene", "#FF9800")
                            time.sleep(1.5)
                            _durumu_guncelle("Hazırım! 🎙️")
                    else:
                        _durumu_guncelle("⚠️  Kayıt dosyası bulunamadı", "#F44336")
                except Exception as ex:
                    _durumu_guncelle(f"Hata: {ex}", "#F44336")

            threading.Thread(target=_kaydi_isle, daemon=True).start()
            return

        # İlk tıklama — kaydı başlat
        dinliyor_mu = True
        mik_buton.icon = ft.Icons.STOP
        mik_buton.icon_color = "#F44336"
        pulse_ring.opacity = 1
        _durumu_guncelle("🎙️  Dinliyorum... (durdurmak için tekrar bas)", "#4FC3F7")
        page.update()

        ses_kaydedici.start_recording(output_path=kayit_dosya_yolu)

    # --- TextField ile metin girişi ---
    metin_kutusu = ft.TextField(
        hint_text="Cano'ya bir şeyler yaz...",
        hint_style=ft.TextStyle(color="#5C6370"),
        bgcolor="#161B22",
        border_color="#21262D",
        focused_border_color="#1565C0",
        color="#E0E0E0",
        border_radius=24,
        content_padding=ft.Padding.only(left=16, right=8, top=8, bottom=8),
        expand=True,
        text_size=14,
        on_submit=lambda e: _metin_gonder(e),
    )

    def _metin_gonder(e):
        metin = metin_kutusu.value.strip()
        if not metin:
            return
        metin_kutusu.value = ""
        page.update()
        _mesaj_ekle(metin, kullanici_mi=True)
        threading.Thread(
            target=_komutu_isle, args=(metin,), daemon=True
        ).start()

    gonder_buton = ft.IconButton(
        icon=ft.Icons.SEND,
        icon_color="#1565C0",
        icon_size=24,
        tooltip="Gönder",
        on_click=_metin_gonder,
    )

    # --- Konum Simülatörü Dropdown ---
    konum_dropdown = ft.Dropdown(
        label="📍 Konum",
        value="bilinmiyor",
        options=[
            ft.dropdown.Option(key="bilinmiyor", text="📍 Bilinmiyor"),
            ft.dropdown.Option(key="ev",         text="🏠 Ev"),
            ft.dropdown.Option(key="belediye",   text="🏛️ Belediye"),
            ft.dropdown.Option(key="market",     text="🛒 Market"),
            ft.dropdown.Option(key="okul",       text="🏫 Okul"),
            ft.dropdown.Option(key="hastane",    text="🏥 Hastane"),
        ],
        width=148,
        height=45,
        text_size=12,
        color="#90CAF9",
        bgcolor="#1E2A3A",
        border_color="#21262D",
        border_radius=8,
        content_padding=ft.Padding.only(left=10, right=4, top=2, bottom=2),
    )

    def _mevcut_konum() -> str | None:
        v = konum_dropdown.value
        return None if v == "bilinmiyor" else v

    # --- Arka plan zamanlayıcısı ---
    def _zamanlayici():
        schedule.every(1).minutes.do(
            lambda: hat.kontrol_et(_cano_konus, _mevcut_konum())
        )
        while True:
            schedule.run_pending()
            hat.kontrol_et(_cano_konus, _mevcut_konum())
            time.sleep(10)

    threading.Thread(target=_zamanlayici, daemon=True).start()

    # --- Mikrofon butonu ve nabız animasyonu ---
    pulse_ring = ft.Container(
        width=64, height=64, border_radius=32,
        bgcolor=ft.Colors.with_opacity(0.15, "#4FC3F7"),
        animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
        opacity=0,
    )

    mik_buton = ft.IconButton(
        icon=ft.Icons.MIC,
        icon_size=28,
        icon_color="#FFFFFF",
        bgcolor="#1565C0",
        width=52,
        height=52,
        style=ft.ButtonStyle(shape=ft.CircleBorder(), elevation=6),
        tooltip="Bas ve konuş",
        on_click=_mikrofon_tiklandi,
    )

    mikrofon_alani = ft.Container(
        content=ft.Stack(
            controls=[pulse_ring, mik_buton],
            alignment=ft.Alignment(0, 0),
        ),
        alignment=ft.Alignment(0, 0),
        height=64, width=64,
    )

    # --- Üst başlık ---
    baslik = ft.Container(
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Text("🤖", size=28),
                    width=44, height=44, border_radius=22,
                    bgcolor="#1E2A3A",
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Column(
                    controls=[
                        ft.Text("Cano", size=20, weight=ft.FontWeight.BOLD, color="#E0E0E0"),
                        ft.Text("Kişisel Asistan • v3.0", size=11, color="#4FC3F7"),
                    ],
                    spacing=0, expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                konum_dropdown,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        bgcolor="#161B22",
        border=ft.Border.only(bottom=ft.BorderSide(1, "#21262D")),
    )

    # --- Alt giriş alanı: TextField + Mikrofon + Durum + İmza ---
    giris_satiri = ft.Row(
        controls=[metin_kutusu, mikrofon_alani, gonder_buton],
        spacing=6,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    imza = ft.Text(
        "Developed by Onurcan KAYA",
        size=9, color="#3D4450",
        text_align=ft.TextAlign.CENTER,
        italic=True,
    )

    alt_alan = ft.Container(
        content=ft.Column(
            controls=[durum_metni, giris_satiri, imza],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        ),
        padding=ft.Padding.only(left=12, right=12, top=6, bottom=10),
        bgcolor="#161B22",
        border=ft.Border.only(top=ft.BorderSide(1, "#21262D")),
    )

    # --- Sayfa düzeni ---
    page.add(
        ft.Column(
            controls=[
                baslik,
                ft.Container(content=sohbet_listesi, expand=True, bgcolor="#0D1117"),
                alt_alan,
            ],
            expand=True, spacing=0,
        )
    )

    # Hoşgeldin mesajı
    def _hosgeldin():
        _cano_konus("Merhaba! Ben Cano. Mikrofona basarak konuş veya yazarak sor!")

    threading.Thread(target=_hosgeldin, daemon=True).start()


# ---------------------------------------------------------------------------
# Uygulama başlatma
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ft.run(main)
