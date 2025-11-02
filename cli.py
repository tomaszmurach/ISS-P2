#!/usr/bin/env python
# coding: utf-8

from __future__ import annotations
import argparse
from transport import SerialTransport, available_ports
from protocol import add_crc, normalize

def show_ports():
    for p in available_ports() or []:
        print(p)

def show_help():
    print("\n=== Dostępne komendy ===")
    print("PING            -> powinno zwrócić: PONG")
    print("ECHO(txt)       -> zwraca: txt (np. ECHO(hello))")
    print("M(10) / R(5) / V(3) -> przykłady starszych komend (ACK)")
    print("S / I / B / STOP -> sterowanie, B lub STOP kończy TEST lub PID")
    print("---------------------------")
    print("TARGET(x)       -> ustawia punkt zadany (odległość od czujnika)")
    print("PID(kp,ki,kd)   -> ustawia współczynniki regulatora PID")
    print("ZERO(x)         -> ustawia pozycję zerową serwa")
    print("TEST            -> włącza tryb strojenia PID (telemetria)")
    print("START           -> uruchamia tryb zaliczeniowy (PID + MAE)")
    print("---------------------------")
    print("help            -> pokazuje tę listę")
    print("ports           -> pokazuje dostępne porty COM")
    print("quit / exit     -> zakończenie programu\n")

def repl(x: SerialTransport):
    print("help, ports, quit")
    while True:
        try:
            raw = input("> ")
        except EOFError:
            break

        if not raw.strip():
            continue

        cmd = raw.strip()
        cmd_lower = cmd.lower()

        if cmd_lower in {"quit", "exit", "q"}:
            break
        if cmd_lower == "help":
            show_help()
            continue
        if cmd_lower == "ports":
            show_ports()
            continue

        payload = normalize(cmd)
        if "|" not in payload:
            payload = add_crc(payload)

        x.write_line(payload)
        x._last_cmd = payload
        print("->", payload)

        resp = x.read_line(timeout=2.0)
        if resp is None:
            print("<- (brak odpowiedzi)")
        else:
            print("<-", resp)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", help="np. COM16 lub /dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=9600, help="domyślnie 9600")
    args = ap.parse_args()

    x = SerialTransport(args.port, args.baud, timeout=1.0)
    x.open()
    print(f"Opened {args.port} @ {args.baud} baud")

    try:
        repl(x)
    finally:
        x.close()

if __name__ == "__main__":
    main()
