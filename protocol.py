#!/usr/bin/env python
# coding: utf-8

"""
Moduł obsługujący "protokół" na poziomie pojedynczej ramki tekstowej.

Główne zadania:
- policzenie CRC z payloadu (sumowanie bajtów ASCII & 0xFF),
- doklejenie CRC do payloadu w formacie "PAYLOAD|CRC",
- prosta normalizacja tekstu,
- funkcja pomocnicza do ręcznego debugowania CRC.

Przykład:
    >>> add_crc("PING")
    'PING|B0'   # (CRC zależy od sumy kodów ASCII)
"""

DEBUG = False


def compute_crc(payload: str) -> int:
    """
    Oblicza prosty CRC = suma wszystkich bajtów ASCII z payloadu, obcięta do 1 bajtu.

    Zwraca:
        int z zakresu 0..255

    Zgodność z Arduino:
    - po stronie Arduino crc8() robi to samo: sumuje bajty (uint16_t),
      a na końcu obcina do 0xFF (uint8_t).
    """
    # .encode("ascii", "ignore") – bierzemy tylko znaki ASCII, resztę ignorujemy
    return sum(payload.encode("ascii", "ignore")) & 0xFF


def add_crc(payload: str) -> str:
    """
    Przyjmuje payload (bez CRC) i zwraca ramkę w formacie: 'payload|CRC'.

    - payload: dowolny tekst komendy (np. 'PING', 'TARGET(25.0)', 'PID(3,1,0.5)'),
    - CRC: wynik compute_crc(payload) zapisany w postaci 2-cyfrowego hexa.

    Białe znaki na końcach są usuwane (strip()) – ważne, żeby CRC
    po stronie PC i Arduino było liczone z tego samego zakresu znaków.
    """
    # usuwamy białe znaki z lewej i prawej
    p = payload.strip()

    # liczymy CRC dla "czystego" tekstu
    crc = compute_crc(p)

    # składamy już pełną ramkę: payload|XX
    frame = f"{p}|{crc:02X}"

    if DEBUG:
        print(f"[CRC DEBUG] payload='{p}' crc={crc:02X} frame='{frame}'")

    return frame


def normalize(s: str) -> str:
    """
    Prosta normalizacja wpisanej przez użytkownika komendy.

    Na razie:
    - tylko .strip() (usunięcie spacji/enterów z początku i końca).

    Zostawione jako osobna funkcja, żeby w razie potrzeby
    można było dodać np. zamianę przecinka na kropkę, itp.
    """
    return s.strip()


def crc_debug(payload: str) -> None:
    """
    Wypisuje na stdout payload, CRC i finalną ramkę.

    Przydatne np. do ręcznego sprawdzenia, czy Arduino liczy to samo CRC.

    Przykład:
        >>> crc_debug("PING")
        payload : PING
        crc     : B0
        frame   : PING|B0
    """
    p = payload.strip()
    crc = compute_crc(p)
    frame = f"{p}|{crc:02X}"
    print("payload :", p)
    print("crc     :", f"{crc:02X}")
    print("frame   :", frame)
