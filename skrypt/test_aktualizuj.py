"""Test na przykładowych danych, bez internetu: python skrypt/test_aktualizuj.py"""
import os, sys, json, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aktualizuj as A
from datetime import date

LIST = """<html><body>
<a href="/main/komunikaty/Komunikat-ND-w-woj.-wielkopolskim/idn:3251"><img src="x"></a>
<h3><a href="/main/komunikaty/Komunikat-ND-w-woj.-wielkopolskim/idn:3251">Komunikat dotyczący stwierdzenia ogniska rzekomego pomoru drobiu (ND) w woj. wielkopolskim</a></h3>
<a href="/main/komunikaty/Komunikat-HPAI/idn:3260">Komunikat Głównego Lekarza Weterynarii dotyczący stwierdzenia ognisk wysoce zjadliwej grypy ptaków (HPAI) u drobiu nr 67 i 68</a>
<a href="/main/komunikaty/ASF/idn:3240">Komunikat dotyczący stwierdzenia 9 ogniska afrykańskiego pomoru świń (ASF)</a>
</body></html>"""
D3251 = """<h1>Komunikat dotyczący stwierdzenia ogniska rzekomego pomoru drobiu (ND) w woj. wielkopolskim</h1>
<p>W dniu 9 października 2026 r. stwierdzono ognisko rzekomego pomoru drobiu (ND) w zakładzie utrzymującym 473 170 kur nioski, zlokalizowanym w miejscowości Duszniki, gm. Duszniki, w powiecie szamotulskim, w woj. wielkopolskim.</p><p>Drukuj</p>"""
D3260 = """<h1>Komunikat Głównego Lekarza Weterynarii dotyczący stwierdzenia ognisk wysoce zjadliwej grypy ptaków (HPAI) u drobiu nr 67 i 68</h1>
<p>Ognisko HPAI nr 67 zostało stwierdzone 1 listopada 2026 r. w gospodarstwie komercyjnym, utrzymującym 48482 kur nosek, zlokalizowanym w miejscowości Będlewo, gmina Stęszew, powiat poznański, woj. wielkopolskie.</p>"""
# strona urzędu wojewódzkiego z rozporządzeniami
UW = """<ul><li><a href="/system/files/rozporzadzenia/rozp_hpai_02.11.2026.html">Rozporządzenie Wojewody Wielkopolskiego z dnia 2 listopada 2026 r. w sprawie zwalczania wysoce zjadliwej grypy ptaków (HPAI) na terenie powiatów poznańskiego i grodziskiego</a></li>
<li><a href="/system/files/rozporzadzenia/uchylenie_nd.html">Rozporządzenie uchylające rozporządzenie w sprawie zwalczania rzekomego pomoru drobiu na terenie powiatu szamotulskiego</a></li>
<li><a href="/kontakt">Kontakt</a></li></ul>"""
ROZP = """ROZPORZĄDZENIE WOJEWODY WIELKOPOLSKIEGO z dnia 2 listopada 2026 r. w sprawie zwalczania wysoce zjadliwej grypy ptaków (HPAI)
W związku ze stwierdzeniem ogniska wysoce zjadliwej grypy ptaków w gospodarstwie zlokalizowanym w miejscowości Będlewo, gmina Stęszew, powiat poznański, zarządza się, co następuje:
§ 1. 1. Za obszar zapowietrzony wystąpieniem wysoce zjadliwej grypy ptaków (HPAI), zwany dalej „obszarem zapowietrzonym”, uznaje się: w gminie Stęszew miejscowości: Będlewo, Krąplewo, Wronczyn, Zaparcin.
2. Za obszar zagrożony wystąpieniem wysoce zjadliwej grypy ptaków (HPAI), zwany dalej „obszarem zagrożonym”, uznaje się: gminy Stęszew, Buk, Grodzisk Wielkopolski, w miejscowości Dopiewiec.
§ 2. Na obszarze zapowietrzonym nakazuje się..."""
UCHYL = """ROZPORZĄDZENIE uchylające rozporządzenie w sprawie zwalczania rzekomego pomoru drobiu (ND) na terenie powiatu szamotulskiego. Uchyla się rozporządzenie ... powiat szamotulski."""
RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Ptasia grypa w gminie Kobierzyce. Ognisko u drobiu w powiecie wrocławskim - Gazeta Wrocławska</title><link>https://news.google.com/a1</link><guid>a1</guid><pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate><source>Gazeta Wrocławska</source><description>Powiatowy lekarz weterynarii potwierdził ognisko grypy ptaków</description></item>
<item><title>Ptasia grypa w Danii. Wybito 20 tys. indyków - Interia</title><link>https://news.google.com/a2</link><guid>a2</guid><pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Ognisko HPAI w Będlewie potwierdzone, gmina Stęszew - Głos Wlkp</title><link>https://news.google.com/a3</link><guid>a3</guid><pubDate>Mon, 02 Nov 2026 11:00:00 GMT</pubDate><description>w miejscowości Będlewo, powiat poznański</description></item>
</channel></rss>"""

PAGES = {A.LIST_URL: LIST, "https://uw.test/rozporzadzenia": UW}
for idn, d in [("3251", D3251), ("3260", D3260)]:
    PAGES[[u for i, t, u in A.parse_list(LIST) if i == idn][0]] = d
RAW = {"https://uw.test/system/files/rozporzadzenia/rozp_hpai_02.11.2026.html": ROZP,
       "https://uw.test/system/files/rozporzadzenia/uchylenie_nd.html": UCHYL}
def fake(url, timeout=0):
    if url in PAGES: return PAGES[url]
    if "news.google.com" in url: return RSS
    if "/st:" in url: return "<html></html>"
    raise RuntimeError("brak " + url)
def fake_raw(url, timeout=0):
    if url in RAW: return RAW[url].encode("utf-8"), "text/plain; charset=utf-8"
    raise RuntimeError("brak " + url)

tmp = tempfile.mkdtemp()
for n in ["F_EVENTS", "F_STATE", "F_GEO", "F_WOJ"]:
    setattr(A, n, os.path.join(tmp, os.path.basename(getattr(A, n))))
A.DATA = tmp
# wcześniejszy stan: ognisko ND w Dusznikach sprzed 30 dni było już znane
json.dump({"przetworzone": ["3251"]}, open(A.F_STATE, "w"))
json.dump({"zdarzenia": [{"id": "giw-3251-1", "rodzaj": "ognisko", "choroba": "ND", "typ": "drob", "data": "2026-10-09", "woj": "wielkopolskie",
           "powiat": "szamotulski", "gmina": "Duszniki", "miejscowosc": "Duszniki", "potwierdzenie": "GIW", "zrodlo": "https://giw/3251"}]}, open(A.F_EVENTS, "w"))
os.environ["WOJEWODZTWA"] = ""
src = [{"nazwa": "UW test", "woj": "wielkopolskie", "url": "https://uw.test/rozporzadzenia"}]
out, fresh = A.run(fetcher=fake, fetcher_raw=fake_raw, offline=True, today=date(2026, 11, 3), sources=src)
for e in out:
    print(json.dumps({k: e.get(k) for k in ["id", "choroba", "data", "woj", "powiat", "gmina", "miejscowosc", "potwierdzenie", "status"]}, ensure_ascii=False))
    print("   źródła:", [z["typ"] for z in e.get("zrodla", [])], "| strefy:", list((e.get("strefy") or {}).keys()))
b = [e for e in out if e.get("miejscowosc") == "Będlewo"][0]
print("   strefa zapowietrzona Będlewo:", b.get("strefy", {}).get("zapowietrzony"))
print("do powiadomienia:", [A.short(e) for e in fresh])
assert len([e for e in out if e.get("miejscowosc") == "Będlewo"]) == 1, "Będlewo powinno być połączone w jeden wpis"
assert not any("Danii" in (e.get("tytul_zrodla") or "") for e in out), "wiadomość zagraniczna nie powinna wejść"
assert [e for e in out if e["id"] == "giw-3251-1"][0]["status"] == "zniesione", "uchylenie powinno znieść strefy"
print("TESTY OK")
shutil.rmtree(tmp)
