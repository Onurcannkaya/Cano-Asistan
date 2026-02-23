import flet as ft
import traceback
import sys

# ---------------------------------------------------------------------------
# GÜVENLİ İMPORT: Herhangi bir kütüphane eksikse siyah ekran yerine
# kırmızı hata mesajı gösterir — "Sessiz Çökme" koruması
# ---------------------------------------------------------------------------
try:
    import asyncio
    import os
    import threading
    import time
    import tempfile
    from datetime import datetime
    import schedule

    import ses_motoru as ses
    import hatirlatici_motoru as hat
    import butce_motoru as butce
    import zeka_motoru as zeka

    # Bildirim kütüphanesini çok dikkatli çağır
    try:
        from flet_notifications import LocalNotifications
        BILDIRIM_DESTEGI = True
    except Exception as e:
        print(f"[!] Bildirim kütüphanesi yüklenemedi: {e}")
        BILDIRIM_DESTEGI = False
        LocalNotifications = None

except Exception as global_err:
    # Buraya düşerse: bir kütüphane eksik, uygulama hiç başlamadan patlamış
    def emergency_main(page: ft.Page):
        page.bgcolor = "#0D1117"
        page.add(
            ft.Text(
                f"KRİTİK BAŞLATMA HATASI (Import Error):\n\n"
                f"{traceback.format_exc()}",
                color="red",
                size=11,
                selectable=True,
            )
        )
        page.update()

    if __name__ == "__main__":
        ft.app(target=emergency_main)
    sys.exit()

# ---------------------------------------------------------------------------
# Sabitler ve Yardımcı Fonksiyonlar (Aynen Korundu)
# ---------------------------------------------------------------------------
_HATIRLATICI_CAPA = ["hatırlat", "uyar"]
_HATIRLATICI_ZAMAN = ["dakika sonra", "saat sonra", "yarım saat"]
_HATIRLATICI_GEO = ["gidince", "varınca", "yaklaşınca", "ulaşınca", "gelince"]

SORGULAMA_ANAHTAR = ["hatırlatıcılarımı oku", "hatırlatıcılarım", "hatırlatıcılar", "neler var", "ne var", "bekleyen", "okur musun", "listele"]
HARCAMA_ANAHTAR = ["harcadım", "aldım", "verdim", "ödedim", "lira", "tl"]
BUTCE_OZET_ANAHTAR = ["ne kadar harcadım", "bütçe özeti", "harcamalarım", "toplam harcama", "bütçem", "harcama özeti"]
CIKIS_ANAHTAR = ["çıkış", "kapat", "görüşürüz", "hoşça kal", "bay bay"]

def _komut_icerir(metin: str, anahtar_liste: list[str]) -> bool:
    m = metin.lower()
    return any(k in m for k in anahtar_liste)

def _hatirlatici_niyeti_var(metin: str) -> bool:
    m = metin.lower()
    if any(k in m for k in _HATIRLATICI_GEO): return True
    if any(k in m for k in _HATIRLATICI_ZAMAN): return True
    return any(k in m for k in _HATIRLATICI_CAPA)

def _balon_olustur(mesaj: str, kullanici_mi: bool) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("Sen" if kullanici_mi else "🤖 Cano", size=11, weight=ft.FontWeight.BOLD, color="#90CAF9" if kullanici_mi else "#CE93D8"),
                ft.Text(mesaj, size=14, color="#E0E0E0", selectable=True),
                ft.Text(datetime.now().strftime("%H:%M"), size=9, color="#757575"),
            ],
            spacing=2, tight=True,
        ),
        bgcolor="#1E2A3A" if kullanici_mi else "#2A1E3A",
        border_radius=ft.border_radius.only(top_left=16, top_right=16, bottom_right=4 if kullanici_mi else 16, bottom_left=16 if kullanici_mi else 4),
        padding=ft.padding.symmetric(horizontal=16, vertical=10),
        margin=ft.margin.only(left=80 if kullanici_mi else 8, right=8 if kullanici_mi else 80, bottom=6),
        alignment=ft.alignment.center_right if kullanici_mi else ft.alignment.center_left,
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
    )

# ---------------------------------------------------------------------------
# Ana Uygulama Mantığı
# ---------------------------------------------------------------------------

def main(page: ft.Page):
    try: # <--- TEŞHİS KATMANI: Siyah ekran yerine hatayı görmeni sağlar
        # --- 1. SAYFA AYARLARI ---
        page.title = "Cano — Kişisel Asistan"
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = "#0D1117"
        page.padding = 0
        page.fonts = {"Inter": "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap"}
        page.theme = ft.Theme(font_family="Inter")

        # --- 2. DURUM VE DEĞİŞKENLER ---
        dinliyor_mu = False
        _son_tts_yol = [None]
        kayit_dosya_yolu = os.path.join(tempfile.gettempdir(), "cano_kayit.wav")

        # --- 3. UI BİLEŞENLERİNİ TANIMLA (Önce İskelet) ---
        sohbet_listesi = ft.ListView(expand=True, spacing=0, padding=ft.padding.symmetric(vertical=12), auto_scroll=True)
        durum_metni = ft.Text("Hazırım! 🎙️", size=12, color="#90CAF9", animate_opacity=ft.Animation(300))
        
        def _mesaj_ekle(mesaj: str, kullanici_mi: bool):
            sohbet_listesi.controls.append(_balon_olustur(mesaj, kullanici_mi))
            page.update()

        def _durumu_guncelle(metin: str, renk: str = "#90CAF9"):
            durum_metni.value = metin
            durum_metni.color = renk
            page.update()

        # Konum Dropdown
        konum_dropdown = ft.Dropdown(
            label="📍 Konum", value="bilinmiyor",
            options=[
                ft.dropdown.Option(key="bilinmiyor", text="📍 Bilinmiyor"),
                ft.dropdown.Option(key="ev", text="🏠 Ev"),
                ft.dropdown.Option(key="belediye", text="🏛️ Belediye"),
                ft.dropdown.Option(key="market", text="🛒 Market"),
            ],
            width=140, text_size=12, color="#90CAF9", bgcolor="#1E2A3A", border_radius=8,
        )

        def _mevcut_konum() -> str | None:
            return None if konum_dropdown.value == "bilinmiyor" else konum_dropdown.value

        # Giriş Alanı
        metin_kutusu = ft.TextField(
            hint_text="Cano'ya yaz...", expand=True, border_radius=24, text_size=14,
            bgcolor="#161B22", color="#E0E0E0", on_submit=lambda e: _metin_gonder(e)
        )

        # Mikrofon ve Animasyon
        pulse_ring = ft.Container(width=64, height=64, border_radius=32, bgcolor=ft.Colors.with_opacity(0.15, "#4FC3F7"), opacity=0, animate=ft.Animation(600))
        mik_buton = ft.IconButton(icon=ft.Icons.MIC, icon_size=28, bgcolor="#1565C0", on_click=lambda e: _mikrofon_tiklandi(e))
        
        # UI Montajı
        baslik = ft.Container(
            content=ft.Row([
                ft.Text("🤖", size=24),
                ft.Column([ft.Text("Cano", weight="bold"), ft.Text("v3.8 Stabil", size=10)], spacing=0, expand=True),
                konum_dropdown
            ]), padding=15, bgcolor="#161B22"
        )
        
        alt_alan = ft.Container(
            content=ft.Column([
                durum_metni, 
                ft.Row([metin_kutusu, ft.Stack([pulse_ring, mik_buton], alignment=ft.alignment.center), ft.IconButton(ft.Icons.SEND, on_click=lambda e: _metin_gonder(e))], spacing=5),
                ft.Text("Developed by Onurcan KAYA", size=9, color="#3D4450", italic=True)
            ], horizontal_alignment="center"), padding=10, bgcolor="#161B22"
        )

        # --- 4. EKRANI HEMEN ÇİZ (Siyah Ekranı Engellemek İçin En Kritik Adım) ---
        page.add(ft.Column([baslik, ft.Container(sohbet_listesi, expand=True), alt_alan], expand=True, spacing=0))
        page.update() # Arayüz artık Android ekranında görünüyor ✅

        # --- 5. OVERLAY VE BİLEŞENLER (Ekran çizildikten sonra) ---
        ses_oynatici = ft.Audio(src="", autoplay=False)
        ses_kaydedici = ft.AudioRecorder(audio_encoder=ft.AudioEncoder.WAV)
        page.overlay.extend([ses_oynatici, ses_kaydedici])
        
        bildirimler = None
        if BILDIRIM_DESTEGI:
            bildirimler = LocalNotifications()
            page.overlay.append(bildirimler)
            page.run_task(bildirimler.request_permissions)

        # --- 6. FONKSİYONLAR (Closure'lar) ---
        def _cano_konus(metin: str):
            _mesaj_ekle(metin, False)
            _durumu_guncelle("🔊 Cano konuşuyor...", "#CE93D8")
            try:
                mp3_yol = ses.konuş(metin)
                ses_oynatici.src = mp3_yol
                ses_oynatici.play()
            except: pass
            _durumu_guncelle("Hazırım! 🎙️")

        def _komutu_isle(metin: str):
            if _komut_icerir(metin, CIKIS_ANAHTAR): _cano_konus("Görüşürüz Onurcan!"); return
            if _komut_icerir(metin, BUTCE_OZET_ANAHTAR): _cano_konus(butce.harcama_ozeti()); return
            if _komut_icerir(metin, SORGULAMA_ANAHTAR): _cano_konus(hat.bekleyenleri_oku()); return
            if _komut_icerir(metin, HARCAMA_ANAHTAR): _cano_konus(butce.harcama_ekle(metin)); return
            if _hatirlatici_niyeti_var(metin):
                geri_bildirim, hedef_zaman = hat.hatirlatici_ekle(metin)
                _cano_konus(geri_bildirim)
                if hedef_zaman and bildirimler:
                    page.run_task(lambda: bildirimler.schedule_notification(id=hat.yeni_bildirim_id(), title="⏰ Cano Hatırlatma", body=metin, scheduled_date=hedef_zaman))
                return
            _cano_konus(zeka.gemini_sor(metin))

        def _mikrofon_tiklandi(e):
            nonlocal dinliyor_mu
            if dinliyor_mu:
                dinliyor_mu = False
                mik_buton.icon = ft.Icons.MIC; pulse_ring.opacity = 0; _durumu_guncelle("⏳ İşleniyor...")
                ses_kaydedici.stop_recording()
                time.sleep(0.5)
                metin = zeka.sesi_metne_cevir(kayit_dosya_yolu)
                if metin: _mesaj_ekle(metin, True); _komutu_isle(metin)
                else: _durumu_guncelle("Anlayamadım 🎙️")
            else:
                dinliyor_mu = True
                mik_buton.icon = ft.Icons.STOP; pulse_ring.opacity = 1; _durumu_guncelle("🎙️ Dinliyorum...")
                ses_kaydedici.start_recording(kayit_dosya_yolu)
            page.update()

        def _metin_gonder(e):
            val = metin_kutusu.value.strip()
            if not val: return
            metin_kutusu.value = ""; _mesaj_ekle(val, True)
            threading.Thread(target=_komutu_isle, args=(val,), daemon=True).start()

        # --- 7. ARKA PLAN GÖREVLERİ (En Son Başlat) ---
        def _arka_plan_dongusu():
            time.sleep(2) # Uygulama iyice otursun
            _cano_konus("Merhaba Onurcan! Cano v3.8 cebinde, seni dinliyorum.")
            while True:
                schedule.run_pending()
                hat.kontrol_et(_cano_konus, _mevcut_konum())
                time.sleep(10)

        threading.Thread(target=_arka_plan_dongusu, daemon=True).start()

    except Exception:
        # Hata detaylarını siyah ekran yerine kırmızı yazıyla göster
        err = traceback.format_exc()
        page.add(ft.Text(f"Başlatma Hatası:\n{err}", color="red", size=10))
        page.update()

if __name__ == "__main__":
    ft.app(target=main) # ft.run yerine ft.app (Mobil Standartı)