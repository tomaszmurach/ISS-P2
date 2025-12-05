#!/usr/bin/env python
# coding: utf-8

"""
Interaktywny klient do komunikacji z Arduino przez port szeregowy.

Funkcje:
- wyświetlanie dostępnych portów COM,
- wypisywanie pomocy z listą komend,
- prosty REPL (pętla odczytu komend z klawiatury),
- obsługa trybu TEST (ciągła telemetria) i START (pomiar MAE).

Komunikacja:
- każda komenda jest normalizowana (obcięcie spacji),
- jeśli nie ma już dopiętego CRC (brak znaku '|'), dodajemy je przez add_crc(),
- ramka jest wysyłana przez SerialTransport.write_line(),
- odpowiedzi czytamy przez SerialTransport.read_line().
"""

from __future__ import annotations
import argparse
import time
from transport import SerialTransport, available_ports
from protocol import add_crc, normalize


def show_ports() -> None:
    """
    Wypisuje na stdout listę dostępnych portów COM.

    Używane z poziomu REPL przez wpisanie komendy:
        ports
    """
    for p in available_ports() or []:
        print(p)


def show_help() -> None:
    """
    Wypisuje krótką ściągę z obsługiwanych komend po stronie Arduino.
    """
    print("\n=== Dostępne komendy ===")
    print("PING                 -> powinno zwrócić: PONG")
    print("ECHO(txt)            -> zwraca: txt (np. ECHO(hello))")
    print("M(10) / R(5) / V(3)  -> przykłady starszych komend (ACK)")
    print("S / I / B / STOP     -> sterowanie; B/STOP kończy TEST lub PID")
    print("---------------------------")
    print("TARGET(x)            -> ustawia punkt zadany (odległość od czujnika)")
    print("PID(kp,ki,kd)        -> ustawia współczynniki regulatora PID")
    print("ZERO(x)              -> ustawia pozycję zerową serwa")
    print("TEST                 -> włącza tryb strojenia PID (telemetria, auto-follow)")
    print("START                -> uruchamia tryb zaliczeniowy (PID + MAE)")
    print("---------------------------")
    print("help                 -> pokazuje tę listę")
    print("ports                -> pokazuje dostępne porty COM")
    print("quit / exit          -> zakończenie programu\n")


def follow_telemetry(x: SerialTransport) -> None:
    """
    Odbiera i wypisuje kolejne linie telemetrii z Arduino.

    Tryb używany po komendzie TEST:
    - Arduino wysyła linię tekstu (np. 'TEL;dist=...;sp=...;err=...;out=...'),
    - klient wypisuje ją ze strzałką '<-',
    - pętla działa aż do przerwania Ctrl+C po stronie użytkownika.

    Po przerwaniu:
    - wysyłamy komendę STOP (z CRC),
    - czyścimy bufor wejściowy portu szeregowego.
    """
    print("(telemetria aktywna — Ctrl+C aby przerwać)")
    try:
        while True:
            # próbujemy przeczytać linię z krótkim timeoutem
            line = x.read_line(timeout=0.3)
            if line is not None:
                # coś przyszło — wypisujemy
                print("<-", line)
            else:
                # brak danych — dajemy trochę odetchnąć CPU
                time.sleep(0.05)
    except KeyboardInterrupt:
        # użytkownik przerwał telemetrię
        print("\n(przerwano podgląd, wysyłam STOP...)")
        try:
            # składamy ramkę STOP z CRC
            stop_frame = add_crc("STOP")
            x.write_line(stop_frame)
            print("->", stop_frame)
            # próbujemy odczytać ACK
            ack = x.read_line(timeout=2.0)
            if ack:
                print("<-", ack)
            else:
                print("<- (brak odpowiedzi na STOP)")
        except Exception as e:
            print("Błąd przy wysyłaniu STOP:", e)

        # dodatkowe czyszczenie bufora wejściowego
        try:
            x._ser.reset_input_buffer()
        except Exception:
            pass

        print("(tryb TEST zakończony)\n")


def repl(x: SerialTransport) -> None:
    """
    Prosty REPL (Read-Eval-Print Loop) do wysyłania komend do Arduino.

    Zachowanie:
    - użytkownik wpisuje tekst (np. 'PING' albo 'TARGET(25.0)'),
    - obsługiwane są komendy lokalne: help, ports, quit/exit/q,
    - pozostałe komendy są traktowane jako payload do ramki z CRC
      i wysyłane przez port szeregowy.

    Dodatkowe zachowanie dla specjalnych komend:
    - TEST: po wysłaniu komendy i odebraniu pierwszego ACK,
      wchodzimy w follow_telemetry() i drukujemy ciągłą telemetrię,
    - START: czekamy dłużej na wynik MAE (Arduino mierzy błąd średni w czasie).
    """
    print("help, ports, quit")
    while True:
        try:
            raw = input("> ")
        except EOFError:
            # koniec wejścia (np. Ctrl+D w Unix) — wychodzimy z pętli
            break

        # ignorujemy puste linie
        if not raw.strip():
            continue

        cmd = raw.strip()
        cmd_upper = cmd.upper()

        # komendy lokalne (nie wysyłane do Arduino)
        if cmd_upper in {"QUIT", "EXIT", "Q"}:
            # kończymy REPL
            break
        if cmd_upper == "HELP":
            show_help()
            continue
        if cmd_upper == "PORTS":
            show_ports()
            continue

        # --- Komenda ma pójść na Arduino ---

        # normalizujemy (na razie tylko strip)
        payload = normalize(cmd)

        # jeśli payload nie zawiera już separatora CRC '|',
        # to zakładamy, że CRC jest jeszcze nie dopięte
        if "|" not in payload:
            payload = add_crc(payload)

        # zapis w strukturze SerialTransport: ostatnio wysłana komenda.
        # Dzięki temu read_line() może np. ustawić dłuższy timeout dla START.
        x.write_line(payload)
        x._last_cmd = payload
        print("->", payload)

        # specjalne traktowanie komendy TEST
        if cmd_upper == "TEST":
            # najpierw czekamy na pierwszą odpowiedź (ACK / błąd)
            ack = x.read_line(timeout=2.0)
            print("<-", ack if ack is not None else "(brak odpowiedzi)")
            # potem przechodzimy w tryb ciągłej telemetrii
            follow_telemetry(x)
            continue

        # specjalne traktowanie komendy START
        if cmd_upper == "START":
            print("(czekam na wynik MAE... może to potrwać ~15s)")
            # czytamy pierwszą linię (MAE albo ACK+MAE, w zależności od logiki Arduino)
            first = x.read_line(timeout=None)  # timeout dobierany dynamicznie
            if first:
                print("<-", first)
                # ewentualnie druga linia (np. dodatkowe info)
                second = x.read_line(timeout=0.5)
                if second:
                    print("<-", second)
            else:
                print("<- (brak odpowiedzi)")
            continue

        # standardowa ścieżka: jedna odpowiedź z określonym timeoutem
        resp = x.read_line(timeout=2.0)
        if resp is None:
            print("<- (brak odpowiedzi)")
        else:
            print("<-", resp)


def main() -> None:
    """
    Punkt wejścia skryptu.

    Kroki:
    1. Parsowanie argumentów linii poleceń (port + opcjonalny baud).
    2. Otwarcie portu szeregowego przez SerialTransport.
    3. Krótkie czyszczenie bufora wejściowego.
    4. Uruchomienie pętli REPL.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("port", help="np. COM16")
    ap.add_argument("--baud", type=int, default=9600, help="domyślnie 9600")
    args = ap.parse_args()

    # tworzymy transport i otwieramy port
    x = SerialTransport(args.port, args.baud, timeout=1.0)
    x.open()
    print(f"Opened {args.port} @ {args.baud} baud")

    # chwilka na ustabilizowanie się portu oraz wyczyszczenie bufora
    time.sleep(1.0)
    try:
        # czyścimy wszystko co mogło leżeć w buforze wejściowym
        while True:
            line = x.read_line(timeout=0.2)
            if not line:
                break
        x._ser.reset_input_buffer()
    except Exception:
        # jeśli coś pójdzie nie tak, po prostu ignorujemy błąd
        pass
    print("(port gotowy, bufor wyczyszczony)\n")

    try:
        repl(x)
    finally:
        # przy wychodzeniu zawsze zamykamy port
        try:
            x.close()
        except Exception:
            pass
        print("Port zamknięty.")


if __name__ == "__main__":
    main()
