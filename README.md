# Ptasi Alert – aplikacja o chorobach drobiu w Polsce

Aplikacja na Androida (oraz strona internetowa) z mapą ognisk grypy ptaków (HPAI/LPAI) i rzekomego pomoru drobiu (ND) w całej Polsce, z powiadomieniami na telefon. Działa na darmowym GitHubie, bez Claude i bez własnego komputera.

- **Aplikacja na Androida** (8.0 lub nowszy) z własną ikoną i powiadomieniami. Sprawdza nowe zdarzenia w tle co około 15 minut, także gdy jest zamknięta. Dotknięcie powiadomienia otwiera ognisko na mapie.
- **Mapa OpenStreetMap** z drogami i miejscowościami, granicami województw oraz strefami 3 km (zapowietrzona) i 10 km (zagrożona) wokół ognisk.
- **Wybór obszaru**: cała Polska albo wybrane województwa. Ten sam wybór decyduje o powiadomieniach w aplikacji.
- **Automatyczna aktualizacja danych co 15 minut** z trzech rodzajów źródeł:
  - **GIW**: komunikaty Głównego Inspektoratu Weterynarii, oznaczone jako potwierdzone;
  - **regionalne**: strony **wszystkich 16 wojewódzkich inspektoratów weterynarii** (sprawdzane co 15 minut), **wszystkich powiatowych inspektoratów weterynarii** (każdy mniej więcej co godzinę) i urzędów wojewódzkich, w tym rozporządzenia w PDF z listami miejscowości w strefach. Adresy inspektoratów powiatowych program znajduje sam i odświeża tę listę raz w tygodniu (plik `data/inspektoraty.json`);
  - **niepotwierdzone**: wiadomości lokalne i komunikaty powiatowe znalezione w Google News.
- To samo ognisko z kilku źródeł łączy się w jeden wpis z listą wszystkich źródeł.

---

## Konfiguracja (jednorazowo, ok. 25 minut)

### 1. Konto i repozytorium
1. Załóż darmowe konto na https://github.com/signup.
2. Kliknij **+**, a potem **New repository**. Nazwa: `ptasi-alert`. Wybierz **Public**, bo darmowa strona i darmowe budowanie wymagają repozytorium publicznego. Na koniec kliknij **Create repository**.

### 2. Wgraj pliki
1. Rozpakuj paczkę `ptasi-alert.zip` na komputerze.
2. W repozytorium kliknij **uploading an existing file**. Przeciągnij plik `index.html`, plik `README.md`, folder `skrypt` i folder `android`, a potem kliknij **Commit changes**. Przeciąganie folderów działa w Chrome, Edge i Firefoxie.
3. Kliknij **Add file**, a potem **Create new file**. Jako nazwę wpisz dokładnie `.github/workflows/aktualizacja.yml`, wklej zawartość pliku `aktualizacja.yml` i kliknij **Commit changes**.
4. Powtórz to samo dla drugiego pliku: nazwa `.github/workflows/android.yml`, zawartość pliku `android.yml`.

### 3. Włącz stronę
Wejdź w **Settings**, potem **Pages**. W sekcji **Source** wybierz **GitHub Actions**.

### 4. Ustawienia w GitHubie
Wejdź w **Settings**, potem **Secrets and variables**, potem **Actions**.

Zakładka **Variables**, przycisk **New repository variable**:

| Name | Wartość |
|---|---|
| `STRONA_URL` | adres Twojej strony: `https://TWOJ-LOGIN.github.io/ptasi-alert/` (**wymagane**: z tego adresu aplikacja pobiera dane) |
| `DNI_AKTYWNE` | *(opcjonalnie)* ile dni od ogniska pokazywać strefy jako aktywne. Domyślnie 45. |

Zakładka **Secrets**, przycisk **New repository secret**. Dodaj dwa sekrety z pliku **KLUCZ-PODPISU-aplikacji-PRYWATNE.txt**, który dostałaś osobno:

| Name | Wartość |
|---|---|
| `KEYSTORE_PASSWORD` | hasło z pliku |
| `KEYSTORE_B64` | długi ciąg znaków z pliku, wklejony w całości |

Klucz podpisu potwierdza, że kolejne wersje aplikacji pochodzą od Ciebie, i pozwala instalować aktualizacje bez odinstalowywania. Zachowaj ten plik w bezpiecznym miejscu i nikomu go nie wysyłaj.

### 5. Pierwsze uruchomienie
1. Wejdź w zakładkę **Actions** i potwierdź włączenie, jeśli GitHub o to zapyta.
2. Kliknij **Ptasi Alert - aktualizacja**, potem **Run workflow**. Pierwsze uruchomienie trwa kilka minut. Gdy pojawi się zielony ✓, strona `https://TWOJ-LOGIN.github.io/ptasi-alert/` działa.
3. Kliknij **Aplikacja Android**, potem **Run workflow**. Budowanie trwa ok. 5–10 minut.

### 6. Instalacja aplikacji na telefonie
1. Na telefonie otwórz `https://github.com/TWOJ-LOGIN/ptasi-alert/releases/latest/download/ptasi-alert.apk` albo na stronie z mapą dotknij przycisku **Aplikacja na Androida**.
2. Otwórz pobrany plik. Telefon zapyta o zgodę na instalację z tego źródła (np. „Zezwól z tego źródła”). Zgódź się i zainstaluj. Google Play Protect może pokazać ostrzeżenie o nieznanej aplikacji. Wybierz **Zainstaluj mimo to**.
3. Uruchom **Ptasi Alert** i zezwól na powiadomienia.
4. Dotknij przycisku z obszarem (np. „Cała Polska”), wybierz województwa i sprawdź **Wyślij powiadomienie testowe**.
5. **Ważne na telefonach Xiaomi, Huawei, Oppo i Samsung**: wyłącz oszczędzanie baterii dla Ptasi Alert (Ustawienia → Aplikacje → Ptasi Alert → Bateria → **Bez ograniczeń**). W przeciwnym razie telefon może blokować sprawdzanie w tle.

Pierwsze sprawdzenie w aplikacji tylko zapamiętuje obecne zdarzenia. Powiadomienia przychodzą o kolejnych, nowych zdarzeniach.

### Aktualizacje aplikacji i udostępnianie innym hodowcom
- Nowa wersja aplikacji buduje się sama po każdej zmianie w folderze `android`. Instalujesz ją tak samo, z tego samego linku, a ustawienia zostają.
- **Innym hodowcom** wystarczy wysłać link `https://github.com/TWOJ-LOGIN/ptasi-alert/releases/latest/download/ptasi-alert.apk`. Każdy sam wybiera swoje województwa. Dane i powiadomienia działają dla wszystkich bez dodatkowych kosztów.
- **Sklep Google Play** (opcjonalnie, później): wymaga konta dewelopera Google (jednorazowo ok. 25 USD), opisu aplikacji, polityki prywatności i testów zamkniętych przed publikacją. Aplikacja jest do tego przygotowana. Do sklepu trzeba wysłać plik w formacie AAB, który GitHub może zbudować po drobnej zmianie.

### Powiadomienia bez aplikacji (opcjonalnie)
Zamiast aplikacji albo dodatkowo możesz dostawać powiadomienia przez darmową aplikację **ntfy**. Dodaj sekret `NTFY_TEMAT` (wymyślona nazwa tematu, ta sama co w ntfy) i zmienną `WOJEWODZTWA` (np. `wielkopolskie,łódzkie`). Możesz też dostawać powiadomienia e-mailem. Wtedy dodaj sekrety `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` i `MAIL_TO` (dla poczty o2: `poczta.o2.pl`, port `465`).

---

## Jak to działa
1. Program (`skrypt/aktualizuj.py`) czyta listę komunikatów GIW i wybiera te o chorobach ptaków.
2. Z treści komunikatu wyciąga chorobę, datę, województwo, powiat, gminę, miejscowość, gatunek i liczbę ptaków.
3. Miejscowość wyszukuje w OpenStreetMap. Jeśli jej nie znajdzie, stawia punkt w gminie, powiecie albo stolicy województwa i oznacza położenie jako „przybliżone”.
4. Zapisuje dane w folderze `data/`, publikuje stronę i wysyła powiadomienia o nowych ogniskach.
5. Za pierwszym razem pobiera też granice województw (`data/wojewodztwa.geojson`).

## Dodawanie źródeł
Inspektoraty wojewódzkie i powiatowe program znajduje sam. W pliku `data/inspektoraty.json` zobaczysz, które znalazł. Jeśli brakuje któregoś województwa (lista błędów: „nie znaleziono strony WIW”) albo Twojego powiatu, dopisz jego stronę ręcznie:
Otwórz plik `skrypt/zrodla.json` w GitHubie (ikona ołówka) i dopisz linijkę w tym samym formacie:
```
{"nazwa": "PIW Szamotuły", "woj": "wielkopolskie", "url": "https://adres-strony-z-komunikatami"},
```
Najlepiej podać stronę, na której są wypisane komunikaty lub rozporządzenia. Program sam znajdzie na niej linki o grypie ptaków i ND. Źródło, które sprawia kłopoty, wyłączysz, dopisując `"wylaczone": true`. Adresy oznaczone `"zweryfikowane": false` dobrałam bez sprawdzenia. Jeśli któryś nie działa, w pliku `data/zdarzenia.json` (pole `bledy`) pojawi się jego nazwa.

## Ograniczenia
- **Strefy:** gdy program znajdzie rozporządzenie wojewody, pokazuje listę miejscowości w strefach. W pozostałych przypadkach rysuje koła 3/10 km, czyli minimalny zasięg według przepisów UE, i to tylko wtedy, gdy zna dokładną miejscowość. Wiążące jest rozporządzenie wojewody.
- **Wiadomości z mediów** są oznaczone jako niepotwierdzone i mogą zawierać błędy, np. starą sprawę opisaną na nowo. Na stronie można je ukryć.
- **Odczyt PDF** działa dla plików tekstowych. Zeskanowane dokumenty (obraz bez tekstu) zostaną pominięte.
- **Status „aktywne” jest szacunkowy**, liczony od daty ogniska (domyślnie 45 dni).
- **GIW może zmienić wygląd swojej strony.** Wtedy program przestanie rozpoznawać część informacji i trzeba go poprawić.

## Gdy coś nie działa
- **Czerwony ✗ w Actions**: kliknij go i przeczytaj komunikat w kroku „Pobierz komunikaty GIW”.
- **Brak granic województw na mapie**: pobierz plik `wojewodztwa-min.geojson` z https://github.com/ppatrzyk/polska-geojson (folder `wojewodztwa`), zmień jego nazwę na `wojewodztwa.geojson` i wgraj do folderu `data`.
- **Nie przychodzą powiadomienia w aplikacji**: wyślij powiadomienie testowe. Jeśli nie przyjdzie, włącz powiadomienia dla Ptasi Alert w ustawieniach telefonu i wyłącz dla niej oszczędzanie baterii. Pamiętaj, że pierwsze sprawdzenie niczego nie wysyła.
- **Aplikacja się nie zbudowała (czerwony ✗ przy „Aplikacja Android”)**: sprawdź, czy ustawiona jest zmienna `STRONA_URL`. Jeśli błąd jest inny, skopiuj jego treść z logu.
- **Telefon nie chce zainstalować aktualizacji („konflikt z istniejącym pakietem”)**: poprzednia wersja była podpisana innym kluczem. Odinstaluj ją i zainstaluj nową. To zdarza się tylko wtedy, gdy na początku nie było sekretu `KEYSTORE_B64`.
- **Zmiana częstotliwości**: w pliku `.github/workflows/aktualizacja.yml` zmień linię `cron`. `*/15 * * * *` oznacza co 15 minut, a `*/30 * * * *` co 30 minut. Częściej niż co 5 minut GitHub nie pozwala.
- **Wyłączenie**: w zakładce **Actions** wybierz **Ptasi Alert - aktualizacja**, kliknij **⋯**, a potem **Disable workflow**.

Test programu bez internetu: `python skrypt/test_aktualizuj.py`
