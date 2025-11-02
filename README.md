## Struktura projektu

Projekt składa się z czterech plików:

| Plik | Opis |
|------|------|
| **robot.ino** | Kod programu dla mikrokontrolera (Arduino UNO). Zawiera implementację PID, obsługę komend, telemetrię i logikę trybów. |
| **cli.py** | Interfejs użytkownika w Pythonie. Pozwala wysyłać komendy do mikrokontrolera, wyświetla odpowiedzi oraz dane telemetrii. |
| **protocol.py** | Moduł obliczający i dołączający sumę kontrolną CRC (suma ASCII mod 256). |
| **transport.py** | Moduł odpowiedzialny za komunikację szeregową z Arduino (z użyciem biblioteki `pyserial`). |

---

## Komunikacja i format ramek

Komunikacja odbywa się w obie strony w formacie tekstowym: KOMENDA|XX, gdzie `XX` to suma kontrolna CRC obliczana jako: CRC = (suma kodów ASCII znaków z KOMENDA) & 0xFF

Każda ramka kończy się znakiem nowej linii `\n`.

Przykład:
PING|2E
TARGET(26.5)|7D


Po stronie Arduino komenda jest weryfikowana. W przypadku poprawnego CRC wykonywana jest odpowiednia akcja, w przeciwnym razie zwracany jest komunikat: NACK(CRC_FAIL)

---

## Obsługiwane komendy

| Komenda | Działanie | Odpowiedź |
|----------|------------|-----------|
| `PING` | Test połączenia | `PONG` |
| `ECHO(txt)` | Echo tekstu | `txt` |
| `TARGET(x)` | Ustawienie punktu zadanego (odległości od czujnika w cm) | `ACK` |
| `PID(kp,ki,kd)` | Ustawienie współczynników regulatora PID | `ACK` |
| `ZERO(x)` | Ustawienie pozycji zerowej serwa | `ACK` |
| `TEST` | Włączenie trybu testowego (telemetria) | `ACK`, następnie ciąg danych `TEL;dist=...;sp=...;err=...;out=...` |
| `STOP` / `B` | Zatrzymanie trybu TEST lub PID, przywrócenie pozycji zerowej | `ACK` |
| `START` | Tryb zaliczeniowy: 10 s regulacji + 3 s liczenia MAE | `ACK`, następnie po zakończeniu `MAE=xx.xx` |
| `S`, `I`, `M(x)`, `R(x)`, `V(x)` | Starsze komendy z Projektu 1 (pozostawione dla kompatybilności) | `ACK` |

---

## Tryby pracy systemu

| Tryb | Opis |
|------|------|
| **IDLE** | Stan początkowy – oczekiwanie na komendy. |
| **TEST** | Uruchomienie regulatora PID z ciągłą telemetrią. Działa do momentu wysłania `STOP` lub `B`. |
| **RUN (START)** | Tryb zaliczeniowy – w ciągu maks. 10 s regulator ustawia kulkę na pozycji zadanej, następnie przez 3 s mierzony jest błąd. |
| **HOLD** | Faza liczenia MAE (Mean Absolute Error). Po 3 s wynik jest wypisywany i system wraca do IDLE. |

---

## Telemetria (tryb TEST)

W trybie testowym Arduino cyklicznie (co 100 ms) wysyła dane w formacie:

TEL;dist=25.8;sp=26.5;err=0.7;out=4.2

| Pole | Znaczenie |
|------|------------|
| `dist` | Aktualny pomiar odległości (cm) |
| `sp` | Punkt zadany (setpoint) |
| `err` | Błąd regulacji |
| `out` | Wartość wyjściowa regulatora PID (sterowanie serwem) |

Dane można zapisać do pliku i wykorzystać do strojenia regulatora.

---

## Logika trybu START (zaliczeniowego)

1. Po komendzie `START` serwo ustawia się lekko w stronę czujnika (`servo_zero + 5°`), aby kulka mogła się zsunąć.  
2. Regulator PID działa przez 10 sekund.  
3. Następnie przez kolejne 3 sekundy liczony jest błąd bezwzględny (MAE).  
4. Wynik jest wypisywany w postaci:

5. System wraca do trybu IDLE.

Maksymalny czas pracy trybu START wynosi 15 sekund (bezpieczne zakończenie).

---

## Parametry PID

Domyślne wartości:
Kp = 3.0
Ki = 2.0
Kd = 1.5

Zmieniane z poziomu interfejsu PC komendą `PID(kp,ki,kd)`.

---

## Instrukcja uruchomienia

1. Wgraj plik **pro2-iss.ino** na płytkę Arduino UNO.  
2. Uruchom terminal PC:
python cli.py COMx  ,gdzie `COMx` to numer portu Arduino.  
3. Sprawdź połączenie:
PING
4. Ustaw parametry początkowe:
5. ZERO(95)
TARGET(26.5)
PID(3,2,1.5)
5.(opcjonalnie) Uruchom tryb testowy:
TEST, zatrzymaj go komendą: STOP
6. Uruchom test zaliczeniowy:
START
7. Oczytaj wyniki.


