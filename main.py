import flet as ft
import traceback
import sys

# ---------------------------------------------------------------------------
# GÜVENLİ İMPORT: Eksik kütüphane → kırmızı hata ekranı
# ---------------------------------------------------------------------------
try:
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

    try:
        from flet_notifications import LocalNotifications
        BILDIRIM_DESTEGI = True
    except Exception as e:
        print(f"[!] Bildirim kütüphanesi yüklenemedi: {e}")
        BILDIRIM_DESTEGI = False
        LocalNotifications = None

except Exception as global_err:
    def emergency_main(page: ft.Page):
        page.bgcolor = "#0D1117"
        page.add(ft.Text(f"KRİTİK HATA:\n\n{traceback.format_exc()}", color="red", size=11, selectable=True))
        page.update()
    if __name__ == "__main__":
        ft.app(target=emergency_main)
    sys.exit()

# ---------------------------------------------------------------------------
# Renk Paleti & Sabitler
# ---------------------------------------------------------------------------
class Renk:
    """Cano v4.0 Pro — Glassmorphism tema renkleri."""
    BG_PRIMARY = "#0D1117"          # Ana arka plan
    BG_CARD = "#161B22"             # Kart arka plan
    BG_USER_MSG = "#1A2332"         # Kullanıcı mesaj balonu
    BG_CANO_MSG = "#1E1A2E"         # Cano mesaj balonu
    ACCENT_BLUE = "#58A6FF"         # Ana vurgu mavi
    ACCENT_PURPLE = "#BC8CFF"       # Cano vurgu mor
    ACCENT_ORANGE = "#F0883E"       # Düşünme göstergesi
    ACCENT_GREEN = "#3FB950"        # Başarı
    TEXT_PRIMARY = "#E6EDF3"        # Ana metin
    TEXT_SECONDARY = "#8B949E"      # İkincil metin
    TEXT_DIM = "#484F58"            # Soluk metin
    GRADIENT_START = "#1565C0"      # Buton gradient başlangıç
    GRADIENT_END = "#7C3AED"        # Buton gradient bitiş

# Komut tanıma anahtar kelimeleri
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
    return any(k in m for k in _HATIRLATICI_GEO) or \
           any(k in m for k in _HATIRLATICI_ZAMAN) or \
           any(k in m for k in _HATIRLATICI_CAPA)

# ---------------------------------------------------------------------------
# UI Bileşen Fabrikaları
# ---------------------------------------------------------------------------

def _mesaj_balonu(mesaj: str, kullanici_mi: bool) -> ft.Container:
    """Gemini Live tarzı gradient mesaj balonu oluşturur."""
    zaman = datetime.now().strftime("%H:%M")
    
    if kullanici_mi:
        isim, renk_isim, bg = "Sen", Renk.ACCENT_BLUE, Renk.BG_USER_MSG
        border_radius = ft.border_radius.only(top_left=18, top_right=18, bottom_right=4, bottom_left=18)
        margin = ft.margin.only(left=60, right=10, bottom=4)
        alignment = ft.alignment.center_right
    else:
        isim, renk_isim, bg = "✨ Cano", Renk.ACCENT_PURPLE, Renk.BG_CANO_MSG
        border_radius = ft.border_radius.only(top_left=18, top_right=18, bottom_right=18, bottom_left=4)
        margin = ft.margin.only(left=10, right=60, bottom=4)
        alignment = ft.alignment.center_left

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text(isim, size=11, weight=ft.FontWeight.W_600, color=renk_isim),
                ft.Text(zaman, size=9, color=Renk.TEXT_DIM),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text(mesaj, size=14, color=Renk.TEXT_PRIMARY, selectable=True),
        ], spacing=4, tight=True),
        bgcolor=bg,
        border=ft.border.all(1, ft.Colors.with_opacity(0.08, "#FFFFFF")),
        border_radius=border_radius,
        padding=ft.padding.symmetric(horizontal=16, vertical=12),
        margin=margin,
        alignment=alignment,
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        shadow=ft.BoxShadow(
            spread_radius=0, blur_radius=8,
            color=ft.Colors.with_opacity(0.15, "#000000"),
            offset=ft.Offset(0, 2),
        ),
    )

def _hizli_eylem_butonu(icon: str, label: str, on_click) -> ft.Container:
    """Hızlı eylem chip butonu."""
    return ft.Container(
        content=ft.Row([
            ft.Icon(icon, size=14, color=Renk.ACCENT_BLUE),
            ft.Text(label, size=11, color=Renk.TEXT_SECONDARY),
        ], spacing=4, tight=True),
        bgcolor=ft.Colors.with_opacity(0.06, "#FFFFFF"),
        border=ft.border.all(1, ft.Colors.with_opacity(0.1, "#FFFFFF")),
        border_radius=20,
        padding=ft.padding.symmetric(horizontal=12, vertical=6),
        on_click=on_click,
        animate=ft.Animation(200),
    )


# ---------------------------------------------------------------------------
# Ana Uygulama
# ---------------------------------------------------------------------------

def main(page: ft.Page):
    try:
        # --- 1. SAYFA AYARLARI ---
        page.title = "Cano — Kişisel Asistan"
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = Renk.BG_PRIMARY
        page.padding = 0
        page.fonts = {"Inter": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"}
        page.theme = ft.Theme(font_family="Inter")

        # --- 2. DURUM ---
        dinliyor_mu = False
        _update_lock = threading.Lock()
        kayit_dosya_yolu = os.path.join(tempfile.gettempdir(), "cano_kayit.wav")

        def _safe_update():
            """Thread-safe page update."""
            with _update_lock:
                try:
                    page.update()
                except Exception:
                    pass

        # --- 3. UI BİLEŞENLERİ ---
        sohbet_listesi = ft.ListView(
            expand=True, spacing=0,
            padding=ft.padding.symmetric(vertical=8, horizontal=4),
            auto_scroll=True,
        )

        # Durum göstergesi — spinner + metin
        durum_spinner = ft.ProgressRing(width=14, height=14, stroke_width=2, color=Renk.ACCENT_BLUE, visible=False)
        durum_metni = ft.Text("Hazırım! ✨", size=12, color=Renk.ACCENT_BLUE, animate_opacity=ft.Animation(300))
        durum_satiri = ft.Row([durum_spinner, durum_metni], spacing=6, alignment=ft.MainAxisAlignment.CENTER)

        def _mesaj_ekle(mesaj: str, kullanici_mi: bool):
            sohbet_listesi.controls.append(_mesaj_balonu(mesaj, kullanici_mi))
            _safe_update()

        def _durumu_guncelle(metin: str, renk: str = Renk.ACCENT_BLUE, spinner: bool = False):
            durum_metni.value = metin
            durum_metni.color = renk
            durum_spinner.visible = spinner
            durum_spinner.color = renk
            _safe_update()

        # Konum Dropdown
        konum_dropdown = ft.Dropdown(
            label="📍 Konum", value="bilinmiyor",
            options=[
                ft.dropdown.Option(key="bilinmiyor", text="📍 Bilinmiyor"),
                ft.dropdown.Option(key="ev", text="🏠 Ev"),
                ft.dropdown.Option(key="belediye", text="🏛️ Belediye"),
                ft.dropdown.Option(key="market", text="🛒 Market"),
            ],
            width=130, text_size=11, color=Renk.TEXT_SECONDARY,
            bgcolor=Renk.BG_CARD, border_radius=10,
            content_padding=ft.padding.symmetric(horizontal=8, vertical=4),
        )

        def _mevcut_konum() -> str | None:
            return None if konum_dropdown.value == "bilinmiyor" else konum_dropdown.value

        # Giriş Alanı
        metin_kutusu = ft.TextField(
            hint_text="Cano'ya yaz...", expand=True, border_radius=24, text_size=14,
            bgcolor=ft.Colors.with_opacity(0.04, "#FFFFFF"),
            color=Renk.TEXT_PRIMARY,
            hint_style=ft.TextStyle(color=Renk.TEXT_DIM),
            border_color=ft.Colors.with_opacity(0.1, "#FFFFFF"),
            focused_border_color=Renk.ACCENT_BLUE,
            on_submit=lambda e: _metin_gonder(e),
            cursor_color=Renk.ACCENT_BLUE,
        )

        # Mikrofon — pulse animasyonlu
        pulse_ring = ft.Container(
            width=52, height=52, border_radius=26,
            bgcolor=ft.Colors.with_opacity(0.12, Renk.ACCENT_BLUE),
            opacity=0, animate=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
        )
        mik_buton = ft.IconButton(
            icon=ft.Icons.MIC_ROUNDED, icon_size=24,
            icon_color="#FFFFFF",
            bgcolor=Renk.GRADIENT_START,
            on_click=lambda e: _mikrofon_tiklandi(e),
            style=ft.ButtonStyle(shape=ft.CircleBorder()),
        )
        gonder_buton = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED, icon_size=20,
            icon_color=Renk.ACCENT_BLUE,
            on_click=lambda e: _metin_gonder(e),
        )

        # Hızlı Eylemler
        def _hizli_hatirlatici(e):
            _mesaj_ekle("Hatırlatıcılarımı oku", True)
            threading.Thread(target=_komutu_isle, args=("hatırlatıcılarımı oku",), daemon=True).start()

        def _hizli_butce(e):
            _mesaj_ekle("Bütçe özeti", True)
            threading.Thread(target=_komutu_isle, args=("ne kadar harcadım",), daemon=True).start()

        hizli_eylemler = ft.Row([
            _hizli_eylem_butonu(ft.Icons.ALARM_ROUNDED, "Hatırlatıcılar", _hizli_hatirlatici),
            _hizli_eylem_butonu(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, "Bütçe", _hizli_butce),
        ], spacing=8, alignment=ft.MainAxisAlignment.CENTER)

        # --- UI MONTAJI ---
        # Üst başlık
        baslik = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text("✨", size=20),
                    width=40, height=40, border_radius=20,
                    bgcolor=ft.Colors.with_opacity(0.1, Renk.ACCENT_PURPLE),
                    alignment=ft.alignment.CENTER,
                ),
                ft.Column([
                    ft.Text("Cano", size=18, weight=ft.FontWeight.W_700, color=Renk.TEXT_PRIMARY),
                    ft.Text("v4.0 Pro", size=10, color=Renk.TEXT_SECONDARY),
                ], spacing=0, expand=True),
                konum_dropdown,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=16, vertical=12),
            bgcolor=Renk.BG_CARD,
            border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.with_opacity(0.06, "#FFFFFF"))),
        )

        # Alt giriş alanı
        alt_alan = ft.Container(
            content=ft.Column([
                hizli_eylemler,
                durum_satiri,
                ft.Row([
                    metin_kutusu,
                    ft.Stack([pulse_ring, mik_buton], alignment=ft.alignment.CENTER),
                    gonder_buton,
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Text("Developed by Onurcan KAYA", size=8, color=Renk.TEXT_DIM, italic=True,
                         text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            bgcolor=Renk.BG_CARD,
            border=ft.border.only(top=ft.border.BorderSide(1, ft.Colors.with_opacity(0.06, "#FFFFFF"))),
        )

        # --- 4. EKRANI ÇİZ ---
        page.add(ft.Column([baslik, ft.Container(sohbet_listesi, expand=True), alt_alan], expand=True, spacing=0))
        _safe_update()

        # --- 5. OVERLAY ---
        ses_kaydedici = None
        if hasattr(ft, "AudioRecorder"):
            ses_kaydedici = ft.AudioRecorder(audio_encoder=ft.AudioEncoder.WAV if hasattr(ft, "AudioEncoder") else None)
            page.overlay.append(ses_kaydedici)

        bildirimler = None
        if BILDIRIM_DESTEGI:
            bildirimler = LocalNotifications()
            page.overlay.append(bildirimler)
            page.run_task(bildirimler.request_permissions)

        # --- 6. FONKSİYONLAR ---
        def _ses_cal(metin: str):
            """TTS: ses dosyası oluştur ve çal."""
            try:
                mp3_yol = ses.konuş(metin)
                oynatici = None
                
                def bitti():
                    try:
                        if oynatici and hasattr(page.overlay, "remove"):
                            page.overlay.remove(oynatici)
                    except Exception:
                        pass
                    _safe_update()
                    ses.temizle(mp3_yol)
                    _durumu_guncelle("Hazırım! ✨")

                if hasattr(ft, "Audio"):
                    oynatici = ft.Audio(src=mp3_yol, autoplay=True)
                    page.overlay.append(oynatici)
                    _safe_update()
                    if spn := durum_spinner:
                        spn.color = Renk.ACCENT_PURPLE
                    oynatici.on_state_changed = lambda e: bitti() if e.data == "completed" else None
                    # Fallback timer (in case on_state_changed doesn't fire)
                    threading.Timer(ses.tahmini_sure(metin) + 1.0, bitti).start()
                else:
                    # Flet-audio yoksa sahte bekleme
                    time.sleep(ses.tahmini_sure(metin))
                    bitti()

            except Exception as e:
                print(f"[!] TTS hatası: {e}")
                _durumu_guncelle("Hazırım! ✨")

        def _cano_konus(metin: str):
            """Metin hemen ekrana, ses arka planda."""
            _mesaj_ekle(metin, False)
            _durumu_guncelle("🔊 Konuşuyor...", Renk.ACCENT_PURPLE, spinner=True)
            threading.Thread(target=_ses_cal, args=(metin,), daemon=True).start()

        def _cano_konus_bekle(metin: str):
            """Metin + ses senkron (açılış için)."""
            _mesaj_ekle(metin, False)
            _durumu_guncelle("🔊 Konuşuyor...", Renk.ACCENT_PURPLE, spinner=True)
            _ses_cal(metin)

        def _komutu_isle(metin: str):
            if _komut_icerir(metin, CIKIS_ANAHTAR):
                _cano_konus("Görüşürüz Onurcan! 👋"); return
            if _komut_icerir(metin, BUTCE_OZET_ANAHTAR):
                _cano_konus(butce.harcama_ozeti()); return
            if _komut_icerir(metin, SORGULAMA_ANAHTAR):
                _cano_konus(hat.bekleyenleri_oku()); return
            if _komut_icerir(metin, HARCAMA_ANAHTAR):
                _cano_konus(butce.harcama_ekle(metin)); return

            # Hatırlatıcı niyeti var mı? → Gemini ile akıllı ayrıştırma
            if _hatirlatici_niyeti_var(metin):
                _durumu_guncelle("⏰ Hatırlatıcı kuruluyor...", Renk.ACCENT_ORANGE, spinner=True)
                ayik = zeka.hatirlatici_ayikla(metin)

                if ayik and ayik.get("zaman_tipi") != "yok":
                    from datetime import timedelta
                    simdi = datetime.now()
                    hedef_zaman = None
                    geri_bildirim = ""

                    tip = ayik["zaman_tipi"]
                    gorev = ayik.get("gorev", metin)

                    if tip == "goreceli" and ayik.get("dakika"):
                        dk = int(ayik["dakika"])
                        hedef_zaman = simdi + timedelta(minutes=dk)
                        saat_str = hedef_zaman.strftime("%H:%M")
                        geri_bildirim = f"Tamam! {saat_str} için hatırlatıcı kurdum — {gorev} ⏰"

                    elif tip == "mutlak" and ayik.get("saat") is not None:
                        saat = int(ayik["saat"])
                        dakika = int(ayik.get("dakika_mutlak", 0))
                        hedef_zaman = simdi.replace(hour=saat, minute=dakika, second=0, microsecond=0)
                        if hedef_zaman <= simdi:
                            hedef_zaman += timedelta(days=1)
                        gun = "yarın" if hedef_zaman.date() > simdi.date() else "bugün"
                        geri_bildirim = f"Tamam! {gun} {saat:02d}:{dakika:02d} için kurdum — {gorev} ⏰"

                    elif tip == "konum" and ayik.get("konum"):
                        konum = ayik["konum"]
                        geri_bildirim = f"Tamam! {konum.capitalize()}'e varınca hatırlatacağım — {gorev} 📍"

                    if geri_bildirim:
                        # Hatırlatıcıyı kaydet
                        hat_kayit = {"metin": metin, "tetiklendi": False}
                        if hedef_zaman:
                            hat_kayit["zaman"] = hedef_zaman.strftime("%Y-%m-%d %H:%M")
                        if tip == "konum":
                            hat_kayit["konum"] = ayik["konum"]
                            hat_kayit["zaman"] = None

                        hat._yukle  # ensure module loaded
                        liste = hat._yukle()
                        liste.append(hat_kayit)
                        hat._kaydet(liste)

                        _cano_konus(geri_bildirim)
                        if hedef_zaman and bildirimler:
                            page.run_task(lambda: bildirimler.schedule_notification(
                                id=hat.yeni_bildirim_id(), title="⏰ Cano Hatırlatma",
                                body=gorev, scheduled_date=hedef_zaman))
                        return

                # Gemini ayrıştıramadıysa eski yöntemi dene
                geri_bildirim, hedef_zaman = hat.hatirlatici_ekle(metin)
                _cano_konus(geri_bildirim)
                if hedef_zaman and bildirimler:
                    page.run_task(lambda: bildirimler.schedule_notification(
                        id=hat.yeni_bildirim_id(), title="⏰ Cano Hatırlatma",
                        body=metin, scheduled_date=hedef_zaman))
                return

            # AI yanıtı
            _durumu_guncelle("🧠 Düşünüyor...", Renk.ACCENT_ORANGE, spinner=True)
            _cano_konus(zeka.gemini_sor(metin))

        def _mikrofon_tiklandi(e):
            nonlocal dinliyor_mu
            if dinliyor_mu:
                dinliyor_mu = False
                mik_buton.icon = ft.Icons.MIC_ROUNDED
                mik_buton.bgcolor = Renk.GRADIENT_START
                pulse_ring.opacity = 0
                _durumu_guncelle("⏳ İşleniyor...", Renk.ACCENT_ORANGE, spinner=True)
                if ses_kaydedici and hasattr(ses_kaydedici, "stop_recording"):
                    ses_kaydedici.stop_recording()
                _safe_update()
                time.sleep(0.5)
                metin = zeka.sesi_metne_cevir(kayit_dosya_yolu)
                if metin:
                    _mesaj_ekle(metin, True)
                    _komutu_isle(metin)
                else:
                    _durumu_guncelle("Anlayamadım, tekrar dene 🎙️")
            else:
                dinliyor_mu = True
                mik_buton.icon = ft.Icons.STOP_ROUNDED
                mik_buton.bgcolor = "#DC2626"
                pulse_ring.opacity = 1
                _durumu_guncelle("🎙️ Dinliyorum...", Renk.ACCENT_GREEN, spinner=True)
                ses_kaydedici.start_recording(kayit_dosya_yolu)
            _safe_update()

        def _metin_gonder(e):
            val = metin_kutusu.value.strip()
            if not val:
                return
            metin_kutusu.value = ""
            _mesaj_ekle(val, True)
            _safe_update()
            threading.Thread(target=_komutu_isle, args=(val,), daemon=True).start()

        # --- 7. ARKA PLAN ---
        def _arka_plan_dongusu():
            time.sleep(2)
            _cano_konus_bekle("Merhaba Onurcan! Cano v4.0 Pro hazır, seni dinliyorum. ✨")
            while True:
                schedule.run_pending()
                hat.kontrol_et(_cano_konus, _mevcut_konum())
                time.sleep(10)

        threading.Thread(target=_arka_plan_dongusu, daemon=True).start()

    except Exception:
        err = traceback.format_exc()
        if "NoneType: None" not in err:
            page.add(ft.Text(f"Başlatma Hatası:\n{err}", color="red", size=10, selectable=True))
            page.update()


if __name__ == "__main__":
    ft.app(target=main)