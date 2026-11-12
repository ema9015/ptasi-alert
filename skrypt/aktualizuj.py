#!/usr/bin/env python3
"""
Ptasi Alert – codzienna aktualizacja danych (bez Claude, tylko standardowy Python 3).

1. Czyta trzy rodzaje źródeł:
   a) komunikaty Głównego Inspektoratu Weterynarii (wetgiw.gov.pl)            → „potwierdzone (GIW)”
   b) strony wojewódzkich/powiatowych inspektoratów i urzędów wojewódzkich,
      w tym rozporządzenia w PDF – lista w pliku skrypt/zrodla.json           → „urzędowe (regionalne)”
   c) wiadomości lokalne z Google News                                        → „niepotwierdzone”
2. Wybiera teksty o chorobach ptaków (HPAI, LPAI, ND) i otwiera każdy z nich.
3. Wyciąga z treści: chorobę, datę, województwo, powiat, gminę, miejscowość, ptaki, liczbę.
4. Znajduje współrzędne miejscowości w OpenStreetMap (Nominatim) i zapamiętuje je.
5. Zapisuje data/zdarzenia.json, z którego korzysta strona z mapą.
6. Wysyła powiadomienia o nowych zdarzeniach w wybranych województwach:
   - na telefon przez ntfy.sh (zmienna NTFY_TEMAT),
   - e-mailem (zmienne SMTP_*; opcjonalnie).
7. Za pierwszym razem pobiera też granice województw (data/wojewodztwa.geojson).

Zmienne (sekrety/zmienne GitHub):
  WOJEWODZTWA     np. "wielkopolskie,łódzkie"; puste = cała Polska (dotyczy powiadomień)
  NTFY_TEMAT      nazwa tematu w aplikacji ntfy, np. "ptasi-alert-k7x2q" (puste = bez push)
  STRONA_URL      adres strony z mapą (link w powiadomieniu)
  DNI_AKTYWNE     ile dni od ogniska uznawać strefy za aktywne (domyślnie 45)
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_TO  – e-mail (opcjonalnie)

Test bez sieci i bez wysyłania:  python skrypt/aktualizuj.py --test
"""

import html as htmlmod
import json
import math
import os
import re
import smtplib
import ssl
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from email.mime.text import MIMEText

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
F_EVENTS = os.path.join(DATA, "zdarzenia.json")
F_STATE = os.path.join(DATA, "stan.json")
F_GEO = os.path.join(DATA, "geokod.json")
F_WOJ = os.path.join(DATA, "wojewodztwa.geojson")
F_OBSZARY = os.path.join(DATA, "obszary.json")

UA = "PtasiAlert/1.0 (+https://github.com; monitor chorob drobiu)"
GIW = "https://www.wetgiw.gov.pl"
LIST_URL = GIW + "/main/komunikaty"
WOJ_SOURCES = [
    "https://raw.githubusercontent.com/ppatrzyk/polska-geojson/master/wojewodztwa/wojewodztwa-min.geojson",
    "https://raw.githubusercontent.com/ppatrzyk/polska-geojson/master/wojewodztwa/wojewodztwa-medium.geojson",
]

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Warsaw")
except Exception:  # noqa: BLE001
    TZ = timezone(timedelta(hours=1))

# nazwa, rdzeń form przymiotnikowych (np. „wielkopolsk-im”), stolica (lat, lon)
WOJ = [
    ("dolnośląskie", "dolnośląsk", (51.11, 17.03)),
    ("kujawsko-pomorskie", "kujawsko-pomorsk", (53.12, 18.01)),
    ("lubelskie", "lubelsk", (51.25, 22.57)),
    ("lubuskie", "lubusk", (51.94, 15.51)),
    ("łódzkie", "łódzk", (51.76, 19.46)),
    ("małopolskie", "małopolsk", (50.06, 19.94)),
    ("mazowieckie", "mazowieck", (52.23, 21.01)),
    ("opolskie", "opolsk", (50.67, 17.93)),
    ("podkarpackie", "podkarpack", (50.04, 22.00)),
    ("podlaskie", "podlask", (53.13, 23.16)),
    ("pomorskie", "pomorsk", (54.35, 18.65)),
    ("śląskie", "śląsk", (50.26, 19.02)),
    ("świętokrzyskie", "świętokrzysk", (50.87, 20.63)),
    ("warmińsko-mazurskie", "warmińsko-mazursk", (53.78, 20.49)),
    ("wielkopolskie", "wielkopolsk", (52.41, 16.93)),
    ("zachodniopomorskie", "zachodniopomorsk", (53.43, 14.55)),
]
MIESIACE = {"stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6, "lipca": 7,
            "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12}
UPPER = "A-ZĄĆĘŁŃÓŚŹŻ"
LOWER = "a-ząćęłńóśźż"


# ---------------------------------------------------------------- narzędzia
def fold(t):
    t = t.lower().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pl"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        cs = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(cs, errors="replace")


def fetch_raw(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pl"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), (r.headers.get("Content-Type") or "").lower()


def pdf_text(data):
    try:
        import io
        from pypdf import PdfReader
        rd = PdfReader(io.BytesIO(data))
        return "\n".join((pg.extract_text() or "") for pg in rd.pages[:15])
    except Exception as e:  # noqa: BLE001
        print("Nie udało się odczytać PDF:", e)
        return ""


def doc_text(url, fetcher_raw):
    """Tekst strony HTML albo pliku PDF."""
    data, ctype = fetcher_raw(url)
    if url.lower().split("?")[0].endswith(".pdf") or "pdf" in ctype or data[:5] == b"%PDF-":
        return pdf_text(data)
    m = re.search(r"charset=([\w-]+)", ctype)
    return html_to_text(data.decode(m.group(1) if m else "utf-8", errors="replace"))


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def html_to_text(page):
    page = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", page)
    page = re.sub(r"<[^>]+>", " ", page)
    page = htmlmod.unescape(page).replace("\xa0", " ")
    page = re.sub(r"[ \t]+", " ", page)
    return re.sub(r"\n\s*\n+", "\n", page).strip()


# ---------------------------------------------------------------- lista GIW
def parse_list(page):
    """Zwraca [(idn, tytuł, url)] z listy komunikatów."""
    out, seen = [], {}
    for m in re.finditer(r'<a[^>]+href="([^"]*?/main/komunikaty/[^"]*?idn:(\d+)[^"]*)"[^>]*>(.*?)</a>', page, re.S | re.I):
        href, idn, inner = m.group(1), m.group(2), html_to_text(m.group(3))
        url = urllib.parse.urljoin(GIW, href)
        if idn in seen:
            if len(inner) > len(out[seen[idn]][1]):
                out[seen[idn]] = (idn, inner, url)
            continue
        if len(inner) < 15:  # link z obrazka – tytuł ze ścieżki
            slug = re.search(r"/main/komunikaty/([^/]+)/idn:", href)
            inner = urllib.parse.unquote(slug.group(1)).replace("-", " ") if slug else inner
        seen[idn] = len(out)
        out.append((idn, inner, url))
    return out


def is_bird_title(t):
    f = fold(t)
    if any(x in f for x in ["grypy ptak", "grypa ptak", "grype ptak", "hpai", "lpai", "pomoru drobiu",
                            "pomor drobiu", "(nd)", " nd ", "newcastle"]):
        return True
    return ("drob" in f or "ptak" in f) and not any(x in f for x in ["asf", "pomoru swin", "wscieklizn"])


def disease(t):
    f = fold(t)
    if "lpai" in f or "nisko zjadliw" in f:
        return "LPAI"
    if "grypy ptak" in f or "grypa ptak" in f or "hpai" in f:
        return "HPAI"
    if "pomor" in f and "drob" in f or re.search(r"\bnd\b", f) or "newcastle" in f:
        return "ND"
    return "inne"


GENERAL_RE = r"kampani|zapobieg|profilaktyk|chron swoje|edukacj|apel|#|rozprzestrzeniu sie|zagrozen\w* grypa|migracj|glownego lekarza"


def kind_of(t):
    f = fold(t)
    if "ptakow dzikich" in f or "ptakow dziko" in f or "dzikich ptak" in f:
        return "ptaki dzikie"
    if "w niewoli" in f:
        return "ptaki w niewoli"
    if "ognisk" in f or "stwierdz" in f:
        return "drob"
    return "komunikat"


# ---------------------------------------------------------------- treść komunikatu
def find_woj(s):
    s = s.lower()
    for m in re.finditer(r"(?:woj\.|województw\w*)\s*([" + LOWER + r"\-]+)", s):
        w = m.group(1)
        for name, stem, _ in sorted(WOJ, key=lambda x: -len(x[1])):
            if w.startswith(stem):
                return name
    for name, stem, _ in sorted(WOJ, key=lambda x: -len(x[1])):  # przymiotnik bez słowa „woj.”
        if re.search(r"(?<![" + LOWER + r"\-])" + stem + r"(?:ie|im|iego|a|iej)\b", s):
            return name
    return None


def norm_powiat(w):
    w = w.lower()
    for a, b in [("skiego", "ski"), ("skim", "ski"), ("ckiego", "cki"), ("ckim", "cki"), ("dzkiego", "dzki"), ("dzkim", "dzki")]:
        if w.endswith(a):
            return w[: -len(a)] + b
    return w


def find_powiat(s):
    m = re.search(r"(?:pow\.|powiat\w*|powiecie)\s+(m\.\s*)?([" + LOWER + r"\-]{4,})", s, re.I)
    if not m:
        return None
    return norm_powiat(m.group(2))


NAME = r"[" + UPPER + r"][\w\-" + LOWER + r"]+(?:\s+(?:[" + UPPER + r"0-9][\w\-" + LOWER + r"]*|nad|pod|w|k\.)){0,3}"


def clean_name(n):
    n = re.sub(r"\s+(w|nad|pod|k\.)$", "", n.strip())
    return n.strip(" ,.;")


def find_gmina(s):
    m = re.search(r"(?:gm\.|gmin(?:a|ie|y))\s+(" + NAME + ")", s)
    return clean_name(m.group(1)) if m else None


def find_miejscowosc(s):
    m = re.search(r"(?:w\s+)?miejscowoś\w+\s+(" + NAME + ")", s)
    return clean_name(m.group(1)) if m else None


def find_date(s):
    m = re.search(r"(\d{1,2})\s+(" + "|".join(MIESIACE) + r")\s+(\d{4})", s.lower())
    if m:
        try:
            return date(int(m.group(3)), MIESIACE[m.group(2)], int(m.group(1))).isoformat()
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def find_birds(s):
    m = re.search(r"utrzymuj\w*\s+(?:łącznie\s+)?([\d][\d\s\.]{0,12}\d|\d)\s+(?:szt\.?\s+)?([" + LOWER + r"\s]{3,40}?)(?=[,.;(]|\s+zlokaliz|\s+w\s|\s+—|\s+-\s|$)", s)
    if not m:
        m2 = re.search(r"utrzymuj\w*\s+([" + LOWER + r"\s]{3,40}?)(?=[,.;(]|\s+zlokaliz|\s+w\s)", s)
        return None, (m2.group(1).strip() if m2 else None)
    try:
        n = int(re.sub(r"[\s\.]", "", m.group(1)))
    except ValueError:
        n = None
    return n, m.group(2).strip()


def find_nr(s):
    m = re.search(r"ognisk\w*\s+(?:HPAI|ND|LPAI)?\s*(?:nr\.?\s*)?(\d{1,3}(?:/\d{4})?)\b", s, re.I)
    return m.group(1) if m else None


def _clean(t, n=700):
    t = re.sub(r"\s+", " ", t).strip(" :;,.")
    t = re.sub(r"(?:\s+\d+\.)?\s+(?:Za|W)$", "", t).strip(" :;,.")
    return (t[:n] + "…") if len(t) > n else t


def extract_zones(body):
    """Wycina z rozporządzenia opis obszaru zapowietrzonego, zagrożonego i buforowego."""
    z = {}
    pats = [
        ("zapowietrzony", r"obszar\w*\s+zapowietrzon\w*", r"obszar\w*\s+zagrożon\w*|§\s*\d|Rozdział"),
        ("zagrozony", r"obszar\w*\s+zagrożon\w*", r"obszar\w*\s+buforow\w*|§\s*\d|Rozdział|nakazuj"),
        ("buforowy", r"obszar\w*\s+buforow\w*", r"§\s*\d|Rozdział|nakazuj"),
    ]
    for key, start, stop in pats:
        m = re.search(start + r"[^:]{0,200}?(?:uznaje się|obejmuj\w*|stanowi\w*|ustanawia się|wyznacza się)[^:]{0,80}?:(.{10,3000}?)(?=" + stop + r"|$)",
                      body, re.S | re.I)
        if m:
            z[key] = _clean(m.group(1))
    return z


ZAKAZ_RE = re.compile(r"zakaz\w*|zabrania\w*|nie wolno|wstrzymu\w*", re.I)
TEMAT_ZAKAZU_RE = re.compile(r"handl\w*|sprzeda\w*|rozwo\w*|przemieszcz\w*|targ\w*|wystaw\w*|transport\w*|ubojni\w*|skup\w*|obrot\w*", re.I)


def extract_restrictions(body):
    """Zdania o zakazach dotyczących handlu, sprzedaży, rozwożenia i przemieszczania drobiu."""
    out = []
    for s in re.split(r"(?<=[.;])\s+|\n", body):
        if ZAKAZ_RE.search(s) and TEMAT_ZAKAZU_RE.search(s):
            c = _clean(s, 300)
            if c and c not in out:
                out.append(c)
        if len(out) >= 6:
            break
    return out


def parse_detail(title, text, list_url, strict=False):
    """Zwraca listę zdarzeń z jednego komunikatu (może opisywać kilka ognisk).
    strict=True (rozporządzenia): ognisko tylko ze zdań o „stwierdzeniu”, bo dalej są długie listy miejscowości w strefach."""
    i = text.find(title[:40]) if title else -1
    body = text[i:] if i >= 0 else text
    body = body[:6000]
    end = re.search(r"\n(Drukuj|Udostępnij|Powrót|Data publikacji|Wróć)", body)
    if end:
        body = body[: end.start()]
    full = title + "\n" + body
    dz = disease(full)
    kd = kind_of(title + " " + body[:400])
    # ogólne kampanie i apele nie są ogniskami, nawet gdy wspominają o ogniskach
    if re.search(GENERAL_RE, fold(title + " " + body[:400])) \
            and not re.search(r"stwierdz|wykry|potwierdz", fold(body[:1500])):
        kd = "komunikat"
    doc_woj, doc_pow = find_woj(full), find_powiat(full)
    doc_date = find_date(body) or None

    # zdania z miejscowością = osobne ogniska
    parts = [p for p in re.split(r"(?<=[" + LOWER + r"0-9]{3}[.;])\s+(?=[" + UPPER + r"])|\n", body) if re.search(r"miejscowoś", p)]
    if strict:
        parts = [p for p in parts if re.search(r"stwierdz|wykry|potwierdz", p, re.I) and not re.search(r"obszar\w*\s+(zapowietrz|zagrożon|buforow)", p, re.I)][:5]
    out = []
    for p in parts:
        mc = find_miejscowosc(p)
        if not mc:
            continue
        n, ptaki = find_birds(p)
        out.append({
            "miejscowosc": mc, "gmina": find_gmina(p), "powiat": find_powiat(p) or doc_pow,
            "woj": find_woj(p) or doc_woj, "liczba": n, "ptaki": ptaki,
            "nr": find_nr(p), "data": find_date(p) or doc_date,
        })
    if not out:
        n, ptaki = find_birds(body)
        out.append({"miejscowosc": find_miejscowosc(body), "gmina": find_gmina(body), "powiat": doc_pow,
                    "woj": doc_woj, "liczba": n, "ptaki": ptaki, "nr": find_nr(title + " " + body[:300]),
                    "data": doc_date})
    zones = extract_zones(body) if strict else {}
    restr = extract_restrictions(body)
    for o in out:
        if restr:
            o["ograniczenia"] = restr
        o.update({"choroba": dz, "typ": kd, "tytul_zrodla": title, "zrodlo": list_url,
                  "rodzaj": "ognisko" if kd != "komunikat" else "komunikat"})
        if zones:
            o["strefy"] = zones
        if o["rodzaj"] == "komunikat" and not o["woj"]:
            o["woj"] = "cała Polska"
    return out


# ---------------------------------------------------------------- obszary (jaśniejsze tło pod kropką)
def _hull(points):
    """Otoczka wypukła (łańcuch monotoniczny), punkty (lat, lon)."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def villages_in_zone(strefy):
    """Nazwy miejscowości wymienione w opisie stref z rozporządzenia."""
    names = []
    for key in ("zapowietrzony", "zagrozony"):
        m = re.search(r"miejscowo\w*:\s*(.+)", (strefy or {}).get(key, ""), re.I | re.S)
        if not m:
            continue
        for n in re.split(r",|\s+i\s+", m.group(1)):
            n = n.strip(" .;")
            if 2 <= len(n) <= 60 and n[:1].isupper() and n not in names:
                names.append(n)
    return names


def strefa_obrys(ev, geo, offline=False, limit=25, promien_m=2000):
    """Obrys strefy: otoczka wokół miejscowości z rozporządzenia (każda miejscowość rozszerzona o promień)."""
    if offline or not ev.get("strefy"):
        return None
    pts = []
    for n in villages_in_zone(ev["strefy"])[:limit]:
        lat, lon, acc = geocode({"miejscowosc": n, "gmina": ev.get("gmina"), "powiat": ev.get("powiat"),
                                 "woj": ev.get("woj")}, geo, offline=offline)
        if lat is None or acc != "miejscowosc":
            continue
        dlat = promien_m / 111320
        dlon = promien_m / (111320 * max(math.cos(math.radians(lat)), 0.2))
        for k in range(8):
            ang = math.pi * k / 4
            pts.append((lat + dlat * math.sin(ang), lon + dlon * math.cos(ang)))
    if len(pts) < 3:
        return None
    return [[round(a, 4), round(b, 4)] for a, b in _hull(pts)]


def obszar_powiatu(ev, cache, fetcher=fetch, offline=False):
    """Granica powiatu z OpenStreetMap (Nominatim). Zwraca klucz w obszary.json albo None."""
    if offline or not ev.get("powiat") or not ev.get("woj") or ev["woj"] == "cała Polska":
        return None
    key = f"powiat {ev['powiat']}, województwo {ev['woj']}"
    if key in cache:
        return key if cache[key] else None
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
        {"q": key, "format": "json", "limit": 3, "countrycodes": "pl", "polygon_geojson": 1,
         "polygon_threshold": 0.005})
    geom = None
    try:
        for r in json.loads(fetcher(url, timeout=30)):
            g = r.get("geojson") or {}
            if g.get("type") in ("Polygon", "MultiPolygon"):
                geom = g
                break
    except Exception:  # noqa: BLE001
        geom = None
    cache[key] = geom
    time.sleep(1.1)
    return key if geom else None


# ---------------------------------------------------------------- geokodowanie
def geocode(ev, cache, offline=False):
    woj = ev.get("woj")
    tries = []
    if ev.get("miejscowosc"):
        parts = [ev["miejscowosc"]]
        if ev.get("gmina") and ev["gmina"] != ev["miejscowosc"]:
            parts.append("gmina " + ev["gmina"])
        if ev.get("powiat"):
            parts.append("powiat " + ev["powiat"])
        if woj and woj != "cała Polska":
            parts.append("województwo " + woj)
        tries.append((", ".join(parts), "miejscowosc"))
        if woj and woj != "cała Polska":
            tries.append((ev["miejscowosc"] + ", województwo " + woj, "miejscowosc"))
    if ev.get("gmina"):
        tries.append(("gmina " + ev["gmina"] + (", województwo " + woj if woj and woj != "cała Polska" else ""), "gmina"))
    if ev.get("powiat"):
        tries.append(("powiat " + ev["powiat"] + (", województwo " + woj if woj and woj != "cała Polska" else ""), "powiat"))
    for q, acc in tries:
        if q in cache:
            hit = cache[q]
        elif offline:
            continue
        else:
            url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
                {"q": q, "format": "json", "limit": 1, "countrycodes": "pl", "addressdetails": 1})
            try:
                res = json.loads(fetch(url, timeout=30))
                hit = [float(res[0]["lat"]), float(res[0]["lon"]), (res[0].get("address") or {}).get("state", "")] if res else None
            except Exception:  # noqa: BLE001
                hit = None
            cache[q] = hit
            time.sleep(1.1)  # zasady Nominatim: maks. 1 zapytanie na sekundę
        if hit:
            if not ev.get("woj") and len(hit) > 2 and hit[2]:
                ev["woj"] = find_woj(hit[2])
            return hit[0], hit[1], acc
    for name, _, cap in WOJ:
        if name == woj:
            return cap[0], cap[1], "województwo"
    return None, None, None


# ---------------------------------------------------------------- granice województw
def ensure_boundaries(offline=False):
    if os.path.exists(F_WOJ) or offline:
        return
    for u in WOJ_SOURCES:
        try:
            g = json.loads(fetch(u, timeout=60))
            if g.get("type") == "FeatureCollection" and len(g.get("features", [])) >= 16:
                save(F_WOJ, g)
                print("Pobrano granice województw:", u)
                return
        except Exception as e:  # noqa: BLE001
            print("Nie udało się pobrać granic z", u, e)


# ---------------------------------------------------------------- powiadomienia
def wanted(ev, woj_filter):
    if not woj_filter:
        return True
    return ev.get("woj") in woj_filter or ev.get("woj") == "cała Polska"


def short(ev):
    where = ev.get("miejscowosc") or (("pow. " + ev["powiat"]) if ev.get("powiat") else "")
    w = ev.get("woj") or ""
    kind = {"ptaki dzikie": "u dzikich ptaków", "ptaki w niewoli": "u ptaków w niewoli"}.get(ev.get("typ"), "")
    head = f"{ev['choroba']}{(' ' + kind) if kind else ''}"
    tag = {"media": " [niepotwierdzone]", "urzędowe": " [źródło regionalne]"}.get(ev.get("potwierdzenie"), "")
    if ev["rodzaj"] == "komunikat":
        return f"Komunikat: {ev.get('tytul_zrodla', '')[:120]}{tag}"
    return f"Nowe ognisko {head}: {where} ({w}){tag}".replace(" ()", "")


def notify(new_events, page_url):
    topic = os.environ.get("NTFY_TEMAT", "").strip()
    if topic and new_events:
        title = short(new_events[0]) if len(new_events) == 1 else f"{len(new_events)} nowe zdarzenia – choroby drobiu"
        body = "\n".join("• " + short(e) + (f", {e['liczba']:,} szt.".replace(",", " ") if e.get("liczba") else "") for e in new_events[:8])
        req = urllib.request.Request(
            "https://ntfy.sh/" + urllib.parse.quote(topic), data=body.encode("utf-8"), method="POST",
            headers={"Title": _hdr(title),
                     "Tags": "warning,chicken", "Priority": "high", **({"Click": page_url} if page_url else {})})
        try:
            urllib.request.urlopen(req, timeout=30).read()
            print("Wysłano powiadomienie ntfy.")
        except Exception as e:  # noqa: BLE001
            print("Błąd ntfy:", e)
    if os.environ.get("SMTP_HOST") and os.environ.get("MAIL_TO") and new_events:
        lines = [short(e) + "\n  " + (e.get("zrodla") or [{"u": ""}])[0]["u"] for e in new_events]
        text = "Nowe zdarzenia:\n\n" + "\n\n".join(lines) + (f"\n\nMapa: {page_url}" if page_url else "")
        msg = MIMEText(text, "plain", "utf-8")
        msg["Subject"] = f"Ptasi Alert – {len(new_events)} nowe zdarzenia"
        msg["From"] = os.environ["SMTP_USER"]
        to = [a.strip() for a in os.environ["MAIL_TO"].split(",") if a.strip()]
        msg["To"] = ", ".join(to)
        port = int(os.environ.get("SMTP_PORT") or 465)
        try:
            ctx = ssl.create_default_context()
            if port == 465:
                s = smtplib.SMTP_SSL(os.environ["SMTP_HOST"], port, context=ctx, timeout=60)
            else:
                s = smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=60)
                s.starttls(context=ctx)
            s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            s.sendmail(os.environ["SMTP_USER"], to, msg.as_string())
            s.quit()
            print("Wysłano e-mail.")
        except Exception as e:  # noqa: BLE001
            print("Błąd e-mail:", e)


def _hdr(s):
    """Nagłówki HTTP muszą być w ASCII – ntfy przyjmuje UTF-8 zakodowane wg RFC 2047."""
    try:
        s.encode("ascii")
        return s
    except UnicodeEncodeError:
        import base64
        return "=?UTF-8?B?" + base64.b64encode(s.encode("utf-8")).decode() + "?="


# ---------------------------------------------------------------- źródła regionalne
F_SOURCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "zrodla.json")
BIRD_URL_HINTS = ["grypa", "grypy", "hpai", "lpai", "pomor", "pomoru", "drob", "ptak", "-nd-", "_nd", ".nd", "newcastle"]


def links_on_page(page, base):
    out = []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', page, re.S | re.I):
        href, text = m.group(1).strip(), html_to_text(m.group(2))
        if href.startswith(("mailto:", "javascript:", "tel:")):
            continue
        url = urllib.parse.urljoin(base, href)
        out.append((url, text))
    return out


def bird_link(url, text):
    if text and len(text) > 8 and is_bird_title(text):
        return True
    u = fold(urllib.parse.unquote(url))
    return any(h in u for h in BIRD_URL_HINTS) and not any(x in u for x in ["asf", "swin", "wscieklizn"])


def regional_items(sources, fetcher, fetcher_raw, done_urls, first_run, errors):
    """Zwraca zdarzenia z nowych dokumentów na stronach regionalnych."""
    found = []
    from concurrent.futures import ThreadPoolExecutor

    def get(src):
        try:
            return src, fetcher(src["url"]), None
        except Exception as e:  # noqa: BLE001
            return src, None, e
    with ThreadPoolExecutor(max_workers=12) as ex:
        pages = list(ex.map(get, sources))
    for src, page, err in pages:
        if err is not None:
            if not src.get("cicho"):
                errors.append(f"{src.get('nazwa', src['url'])}: {err}")
            continue
        cand, seen = [], set()
        for url, text in links_on_page(page, src["url"]):
            if url in seen or url == src["url"] or not bird_link(url, text):
                continue
            seen.add(url)
            cand.append((url, text))
        cand = cand[:15] if first_run else cand[:40]
        for url, text in cand:
            if url in done_urls:
                continue
            done_urls.add(url)
            try:
                body = doc_text(url, fetcher_raw)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{url}: {e}")
                continue
            if not body or not is_bird_title(text + " " + body[:3000]):
                continue
            title = text if len(text) > 15 else (body.strip().split("\n")[0][:160])
            f = fold(title + " " + body[:600])
            if "uchyl" in f or "zniesieni" in f:
                found.append({"_uchylenie": True, "choroba": disease(title + " " + body[:2000]),
                              "powiaty": sorted({norm_powiat(m.group(1)) for m in re.finditer(r"(?:pow\.|powiat\w*|powiecie)\s+(?:m\.\s*)?([" + LOWER + r"\-]{4,})", body, re.I)}),
                              "woj": find_woj(title + " " + body[:1500]) or src.get("woj")})
                continue
            evs = parse_detail(title, body, url, strict=True)
            for k, ev in enumerate(evs):
                if not ev.get("miejscowosc") and not ev.get("powiat") and ev["rodzaj"] == "ognisko":
                    # brak miejsca – traktujemy jako komunikat regionalny tylko, gdy to nakaz/zakaz
                    if not re.search(r"nakaz|zakaz|obowiąz|rozporządzeni", title, re.I):
                        continue
                    ev["rodzaj"] = "komunikat"
                ev["woj"] = ev.get("woj") or src.get("woj")
                ev["potwierdzenie"] = "urzędowe"
                ev["zrodlo_rodzaj"] = src.get("rodzaj", "regionalne")
                ev["zrodla"] = [{"t": title[:200], "u": url, "typ": src.get("nazwa", "")}]
                ev["id"] = "reg-" + _h(url) + f"-{k + 1}"
                found.append(ev)
    return found



# ---------------------------------------------------------------- odkrywanie inspektoratów (WIW + PIW)
F_INSP = os.path.join(DATA, "inspektoraty.json")
# znane adresy wojewódzkich inspektoratów + warianty do sprawdzenia (pierwszy działający wygrywa)
WIW_KANDYDACI = {
    "dolnośląskie": ["https://wroc.wiw.gov.pl/"],
    "kujawsko-pomorskie": ["https://bydgoszcz.wiw.gov.pl/", "https://www.wiw.bydgoszcz.pl/", "https://wiw.bydgoszcz.pl/"],
    "lubelskie": ["https://lublin.wiw.gov.pl/", "https://www.wiw.lublin.pl/", "https://wiw.lublin.pl/"],
    "lubuskie": ["https://zgora.wiw.gov.pl/", "https://gorzow.wiw.gov.pl/", "https://www.wiw.gorzow.pl/", "https://wiw.gorzow.pl/"],
    "łódzkie": ["https://lodz.wiw.gov.pl/", "https://www.wiw.lodz.pl/", "https://wiw.lodz.pl/"],
    "małopolskie": ["https://www.wiw.krakow.pl/"],
    "mazowieckie": ["https://mazowsze.wiw.gov.pl/"],
    "opolskie": ["https://opole.wiw.gov.pl/", "https://www.wiw.opole.pl/", "https://wiw.opole.pl/"],
    "podkarpackie": ["https://krosno.wiw.gov.pl/", "https://www.wiw.krosno.pl/", "https://wiw.krosno.pl/"],
    "podlaskie": ["https://bialystok.wiw.gov.pl/"],
    "pomorskie": ["https://gdansk.wiw.gov.pl/", "https://bip.gdansk.wiw.gov.pl/", "https://www.wiw.gdansk.pl/"],
    "śląskie": ["https://katowice.wiw.gov.pl/"],
    "świętokrzyskie": ["https://kielce.wiw.gov.pl/", "https://www.wiw.kielce.pl/", "https://wiw.kielce.pl/"],
    "warmińsko-mazurskie": ["https://olsztyn.wiw.gov.pl/", "https://www.wiw.olsztyn.pl/", "https://wiw.olsztyn.pl/"],
    "wielkopolskie": ["https://wiw.poznan.pl/"],
    "zachodniopomorskie": ["https://szczecin.wiw.gov.pl/", "https://www.wiw.szczecin.pl/", "https://wiw.szczecin.pl/"],
}
# strony z listą powiatowych inspektoratów (znalezione; reszta wyszukiwana automatycznie)
PIW_LISTY = {
    "małopolskie": ["https://www.wiw.krakow.pl/powiatowe-inspektoraty-weterynarii/"],
    "mazowieckie": ["https://mazowsze.wiw.gov.pl/wiw/informacje-podstawowe/organizacja/powiatowe-inspektoraty-weteryn/20938,Powiatowe-Inspektoraty-Weterynarii.html"],
    "śląskie": ["https://katowice.wiw.gov.pl/wk/kontakt/powiatowe-inspektoraty/3318,Powiatowe-Inspektoraty-Weterynarii.html"],
    "dolnośląskie": ["https://wroc.wiw.gov.pl/?cat=23"],
}
SKIP_HOSTS = ["facebook.", "twitter.", "x.com", "youtube.", "instagram.", "linkedin.", "google.", "gov.pl/web/", "epuap", "bip.gov.pl",
              "wetgiw.gov.pl", "uw.gov.pl", "gios.", "arimr", "mapy.", "obywatel", "pzlow", "wikipedia"]


def _host(u):
    return urllib.parse.urlparse(u).netloc.lower().removeprefix("www.")


def _looks_like_inspectorate(page):
    return bool(re.search(r"[Ii]nspektorat\w*\s+[Ww]eterynar|[Ll]ekarz\w*\s+[Ww]eterynar", page[:200000]))


def discover_inspectorates(fetcher, errors):
    out = {"wiw": [], "piw": [], "odkryto": datetime.now(TZ).isoformat(timespec="minutes")}
    seen_piw = set()
    for woj, cands in WIW_KANDYDACI.items():
        wiw_url, wiw_page = None, None
        for u in cands:
            try:
                pg = fetcher(u)
                if _looks_like_inspectorate(pg):
                    wiw_url, wiw_page = u, pg
                    break
            except Exception:  # noqa: BLE001
                continue
        if not wiw_url:
            errors.append(f"nie znaleziono strony WIW: {woj}")
            continue
        out["wiw"].append({"woj": woj, "url": wiw_url, "nazwa": f"WIW ({woj})"})
        # strony z listą PIW: znane + linki „powiatowe inspektoraty” ze strony głównej
        lists = list(PIW_LISTY.get(woj, []))
        for url, text in links_on_page(wiw_page, wiw_url):
            f = fold(text + " " + url)
            if ("powiatow" in f and ("inspektor" in f or "piw" in f)) or "/piw" in f:
                if _host(url) == _host(wiw_url) and url not in lists:
                    lists.append(url)
        pages = [wiw_page]
        for lu in lists[:4]:
            try:
                pages.append(fetcher(lu))
            except Exception:  # noqa: BLE001
                pass
        for pg in pages:
            for url, text in links_on_page(pg, wiw_url):
                h = _host(url)
                if not h or h == _host(wiw_url) or any(x in url.lower() for x in SKIP_HOSTS):
                    continue
                f = fold(text + " " + h)
                if not re.search(r"piw|weteryn|inspektorat|plw|wet\.", f):
                    continue
                home = urllib.parse.urlparse(url)._replace(path="/", query="", fragment="").geturl()
                if home in seen_piw:
                    continue
                seen_piw.add(home)
                name = text if 4 < len(text) < 120 else h
                out["piw"].append({"woj": woj, "url": home, "nazwa": name})
    print(f"Odkryto: {len(out['wiw'])} inspektoratów wojewódzkich, {len(out['piw'])} powiatowych")
    return out


def inspectorate_sources(fetcher, errors, today, force=False):
    d = load(F_INSP, None)
    stale = True
    if d and d.get("odkryto"):
        try:
            stale = (today - date.fromisoformat(d["odkryto"][:10])).days >= 7
        except ValueError:
            stale = True
    if force or not d or stale:
        try:
            d = discover_inspectorates(fetcher, errors)
            save(F_INSP, d)
        except Exception as e:  # noqa: BLE001
            errors.append(f"odkrywanie inspektoratów: {e}")
            d = d or {"wiw": [], "piw": []}
    return d.get("wiw", []), d.get("piw", [])

# ---------------------------------------------------------------- wiadomości (niepotwierdzone)
NEWS_QUERIES = [
    '"grypa ptaków" OR "ptasia grypa" OR "grypy ptaków" ognisko',
    '"rzekomy pomór drobiu" OR "rzekomego pomoru drobiu" ognisko',
    '"obszar zapowietrzony" drób OR ptaków OR drobiu',
    '"lekarz weterynarii" komunikat "grypy ptaków" OR "pomoru drobiu"',
]
FOREIGN = ["niemcz", "czech", "dani", "usa", "stanach", "wegrz", "ukrain", "litw", "slowac", "holandi", "franc", "wlosz", "japoni", "chin", "kanad", "brytani", "anglii", "belgi", "hiszpan"]


def _h(s):
    import hashlib
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]


def news_items(fetcher, done_guids, today, errors):
    from email.utils import parsedate_to_datetime
    from xml.etree import ElementTree
    out = []
    for q in NEWS_QUERIES:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:3d", "hl": "pl", "gl": "PL", "ceid": "PL:pl"})
        try:
            root = ElementTree.fromstring(fetcher(url))
        except Exception as e:  # noqa: BLE001
            errors.append(f"wiadomości: {e}")
            continue
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            guid = (it.findtext("guid") or it.findtext("link") or title).strip()
            if guid in done_guids:
                continue
            done_guids.add(guid)
            desc = html_to_text(it.findtext("description") or "")
            text = re.sub(r"\s+-\s+[^-]+$", "", title) + ". " + desc
            f = fold(text)
            if not is_bird_title(text) or not re.search(r"ognisk|stwierdz|wykryt|potwierdz|przypad|zapowietrz|strefy|wybi|utyliz", f):
                continue
            ev = {"choroba": disease(text), "typ": "ptaki dzikie" if re.search(r"dzik\w* ptak|łabędź|łabędzi|mewa|mew\b", text, re.I) else "drob",
                  "rodzaj": "ognisko", "woj": find_woj(text), "powiat": find_powiat(text), "gmina": find_gmina(text),
                  "miejscowosc": find_miejscowosc(text), "potwierdzenie": "media", "tytul_zrodla": title}
            if not (ev["woj"] or ev["powiat"] or ev["gmina"] or ev["miejscowosc"]):
                continue
            if not ev["woj"] and any(x in f for x in FOREIGN):
                continue
            n, ptaki = find_birds(text)
            ev.update({"liczba": n, "ptaki": ptaki})
            try:
                ev["data"] = parsedate_to_datetime(it.findtext("pubDate")).astimezone(TZ).date().isoformat()
            except Exception:  # noqa: BLE001
                ev["data"] = today.isoformat()
            if (today - date.fromisoformat(ev["data"])).days > 7:
                continue
            src = (it.findtext("source") or "").strip() or "wiadomości"
            ev["zrodla"] = [{"t": title[:200], "u": (it.findtext("link") or "").strip(), "typ": src}]
            ev["id"] = "news-" + _h(guid)
            out.append(ev)
    return out


# ---------------------------------------------------------------- łączenie tych samych ognisk
RANK = {"GIW": 3, "urzędowe": 2, "media": 1}


def same_outbreak(a, b):
    if a.get("rodzaj") != "ognisko" or b.get("rodzaj") != "ognisko":
        return False
    if a.get("choroba") not in (b.get("choroba"), "inne") and b.get("choroba") != "inne":
        return False
    if a.get("woj") and b.get("woj") and a["woj"] != b["woj"]:
        return False
    try:
        if abs((date.fromisoformat(a["data"]) - date.fromisoformat(b["data"])).days) > 21:
            return False
    except (ValueError, KeyError, TypeError):
        return False
    ma, mb = fold(a.get("miejscowosc") or ""), fold(b.get("miejscowosc") or "")
    if ma and mb:
        return ma == mb
    ga, gb = fold(a.get("gmina") or ""), fold(b.get("gmina") or "")
    if ga and gb and ga != gb:
        return False
    pa, pb = a.get("powiat"), b.get("powiat")
    return bool(pa and pb and pa == pb and (ga == gb or not (ga and gb)))


def merge_into(events, ev):
    """Dodaje zdarzenie albo dokleja je do istniejącego. Zwraca True, gdy to nowe ognisko."""
    for old in events.values():
        if old["id"] != ev["id"] and same_outbreak(old, ev):
            urls = {z["u"] for z in old.get("zrodla", [])}
            old.setdefault("zrodla", []).extend(z for z in ev.get("zrodla", []) if z["u"] not in urls)
            for k in ["miejscowosc", "gmina", "powiat", "woj", "liczba", "ptaki", "nr", "strefy", "ograniczenia"]:
                if not old.get(k) and ev.get(k):
                    old[k] = ev[k]
            if RANK.get(ev.get("potwierdzenie"), 0) > RANK.get(old.get("potwierdzenie"), 0):
                old["potwierdzenie"] = ev["potwierdzenie"]
                if ev.get("data"):
                    old["data"] = ev["data"]
            if ev.get("lat") is not None and (old.get("dokladnosc") != "miejscowosc") and ev.get("dokladnosc") == "miejscowosc":
                old.update({"lat": ev["lat"], "lon": ev["lon"], "dokladnosc": ev["dokladnosc"]})
            return False
    if ev["id"] in events:
        return False
    events[ev["id"]] = ev
    return True


# ---------------------------------------------------------------- główny przebieg
def status_for(ev, today, dni_aktywne):
    if ev.get("zniesione"):
        return "zniesione"
    if ev["rodzaj"] == "komunikat" or ev.get("typ") == "ptaki dzikie":
        lim = 30
    else:
        lim = dni_aktywne
    try:
        d = date.fromisoformat(ev.get("data") or "")
    except ValueError:
        return "aktywne"
    age = (today - d).days
    if age <= lim:
        return "aktywne"
    if age <= lim + 30:
        return "wygasa"
    return "zniesione"


def run(fetcher=fetch, fetcher_raw=fetch_raw, offline=False, today=None, sources=None):
    today = today or datetime.now(TZ).date()
    dni_aktywne = int(os.environ.get("DNI_AKTYWNE") or 45)
    woj_filter = [w.strip().lower() for w in (os.environ.get("WOJEWODZTWA") or "").split(",") if w.strip()]
    page_url = os.environ.get("STRONA_URL", "").strip()
    if sources is None:
        sources = [x for x in load(F_SOURCES, {"zrodla": []}).get("zrodla", []) if x.get("url") and not x.get("wylaczone")]

    state = load(F_STATE, None)
    first_run = state is None
    state = state or {}
    done = set(state.get("przetworzone", []))
    done_urls = set(state.get("adresy", []))
    done_guids = set(state.get("wiadomosci", []))
    data = load(F_EVENTS, {"zdarzenia": []})
    events = {e["id"]: e for e in data["zdarzenia"]}
    for e in events.values():  # zgodność ze starszym formatem
        if "zrodla" not in e and e.get("zrodlo"):
            e["zrodla"] = [{"t": e.get("tytul_zrodla", "Komunikat GIW"), "u": e["zrodlo"], "typ": "GIW"}]
            e.setdefault("potwierdzenie", "GIW")
    geo = load(F_GEO, {})
    errors = []
    incoming = []

    # a) GIW
    pages = 8 if first_run else 2
    items = []
    for n in range(1, pages + 1):
        url = LIST_URL if n == 1 else f"{LIST_URL}/st:{n}"
        try:
            items += parse_list(fetcher(url))
        except Exception as e:  # noqa: BLE001
            errors.append(f"lista GIW str. {n}: {e}")
            break
    for idn, title, url in items:
        if idn in done or not is_bird_title(title):
            continue
        try:
            text = html_to_text(fetcher(url))
        except Exception as e:  # noqa: BLE001
            errors.append(f"komunikat {idn}: {e}")
            continue
        for k, ev in enumerate(parse_detail(title, text, url)):
            ev["id"] = f"giw-{idn}-{k + 1}"
            ev["potwierdzenie"] = "GIW"
            ev["zrodla"] = [{"t": title[:200], "u": url, "typ": "GIW"}]
            incoming.append(ev)
        done.add(idn)

    # b) źródła regionalne: urzędy wojewódzkie (zrodla.json) + wszystkie WIW co 15 min + PIW po kolei (każdy co ok. godzinę)
    wiw, piw = inspectorate_sources(fetcher, errors, today) if not offline else ([], [])
    all_src = list(sources)
    have = {x["url"] for x in all_src}
    all_src += [dict(w, rodzaj="WIW") for w in wiw if w["url"] not in have]
    if piw:
        n = max(1, -(-len(piw) // 4))
        off = int(state.get("piw_offset", 0)) % len(piw)
        batch = (piw + piw)[off:off + n]
        state["piw_offset"] = (off + n) % len(piw)
        all_src += [dict(p, rodzaj="PIW", cicho=True) for p in batch if p["url"] not in have]
    regional = regional_items(all_src, fetcher, fetcher_raw, done_urls, first_run, errors)
    incoming += [e for e in regional if not e.get("_uchylenie")]
    incoming += news_items(fetcher, done_guids, today, errors)

    # uchylenia rozporządzeń → strefy zniesione
    for u in [e for e in regional if e.get("_uchylenie")]:
        for ev in events.values():
            if ev.get("powiat") in u["powiaty"] and (u["choroba"] in (ev.get("choroba"), "inne")) and (not u.get("woj") or u["woj"] == ev.get("woj")):
                try:
                    if (today - date.fromisoformat(ev["data"])).days >= 14:
                        ev["zniesione"] = True
                except (ValueError, KeyError, TypeError):
                    pass

    # GIW najpierw, potem urzędowe, na końcu media – żeby łączyć do najpewniejszego wpisu
    incoming.sort(key=lambda e: -RANK.get(e.get("potwierdzenie"), 0))
    new_ids = []
    for ev in incoming:
        if not ev.get("data"):
            ev["data"] = today.isoformat()
        if ev["data"] > today.isoformat():  # data z przyszłości to błąd odczytu
            ev["data"] = today.isoformat()
        lat, lon, acc = geocode(ev, geo, offline=offline)
        if ev.get("potwierdzenie") == "media" and lat is None:
            continue
        ev.update({"lat": lat, "lon": lon, "dokladnosc": acc})
        ev["dodano"] = datetime.now(TZ).isoformat(timespec="minutes")
        ev["zrodlo"] = ev["zrodla"][0]["u"] if ev.get("zrodla") else None
        if merge_into(events, ev):
            new_ids.append(ev["id"])

    keep = {}
    obszary = load(F_OBSZARY, {})
    for ev in events.values():
        if ev.get("data") and ev["data"] > today.isoformat():  # data z przyszłości to błąd odczytu
            ev["data"] = today.isoformat()
        tyt = fold(ev.get("tytul_zrodla") or "")
        if ev.get("rodzaj") == "ognisko" and re.search(GENERAL_RE, tyt) and not re.search(r"stwierdz|wykry|potwierdz", tyt):
            ev["rodzaj"] = ev["typ"] = "komunikat"  # ogólna kampania albo apel, nie ognisko
        ev["status"] = status_for(ev, today, dni_aktywne)
        if ev.get("rodzaj") == "ognisko" and ev["status"] in ("aktywne", "wygasa") and ev.get("potwierdzenie") != "media":
            if "strefa_obrys" not in ev and ev.get("strefy") and not offline:
                ev["strefa_obrys"] = strefa_obrys(ev, geo, offline=offline)
            if "obszar" not in ev and ev.get("dokladnosc") != "miejscowosc":
                ev["obszar"] = obszar_powiatu(ev, obszary, fetcher=fetcher, offline=offline)

        try:
            if (today - date.fromisoformat(ev["data"])).days > 400:
                continue
        except (ValueError, KeyError, TypeError):
            pass
        keep[ev["id"]] = ev
    out = sorted(keep.values(), key=lambda e: e.get("data") or "", reverse=True)

    save(F_EVENTS, {"aktualizacja": datetime.now(TZ).isoformat(timespec="minutes"),
                    "dni_aktywne": dni_aktywne, "bledy": errors[:30], "zdarzenia": out})
    state.update({"przetworzone": sorted(done, key=lambda x: int(x))[-2000:],
                  "adresy": sorted(done_urls)[-5000:], "wiadomosci": sorted(done_guids)[-5000:],
                  "ostatnie_uruchomienie": datetime.now(TZ).isoformat(timespec="minutes")})
    save(F_STATE, state)
    save(F_GEO, geo)
    if not offline:
        save(F_OBSZARY, obszary)
    ensure_boundaries(offline=offline)

    fresh = [keep[i] for i in new_ids if i in keep and keep[i]["status"] == "aktywne" and wanted(keep[i], woj_filter)]
    print(f"GIW: {len(items)} na liście; źródeł regionalnych sprawdzono: {len(all_src)} (WIW: {len(wiw)}, PIW w tej turze: {len([x for x in all_src if x.get('rodzaj') == 'PIW'])} z {len(piw)}); dokumentów regionalnych: {len(regional)}; nowych zdarzeń: {len(new_ids)}; do powiadomienia: {len(fresh)}")
    for e in errors:
        print("UWAGA:", e)
    if first_run:
        print("Pierwsze uruchomienie – zapisano historię, powiadomienia od następnego razu.")
        return out, []
    if not offline:
        notify(fresh, page_url)
    return out, fresh


if __name__ == "__main__":
    run()
