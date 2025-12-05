#!/usr/bin/env python
# coding: utf-8

"""
Warstwa transportowa nad portem szeregowym (pyserial).

Klasa SerialTransport:
- opakowanie nad serial.Serial,
  operowania na bajtach,
- czyszczenie buforów przy otwarciu portu,
- debugowe logowanie TX/RX w trybie DEBUG.

Dodatkowo:
- funkcja available_ports() zwracająca listę dostępnych portów COM.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import time

try:
    import serial
    from serial.tools import list_ports
except Exception:
    serial = None
    list_ports = None

DEBUG = False


@dataclass
class SerialTransport:
    """
    Proste opakowanie do komunikacji tekstowej po porcie szeregowym.

    Atrybuty:
        port    : nazwa portu (np. 'COM16'),
        baud    : prędkość transmisji (domyślnie 9600),
        timeout : bazowy timeout (sekundy) dla odczytu,
        _ser    : wewnętrzny obiekt serial.Serial (ustawiany w open()).
    """
    port: str
    baud: int = 9600
    timeout: float = 1.0
    _ser: Optional[object] = None

    def open(self) -> None:
        """
        Otwiera port szeregowy z zadanymi parametrami.

        Ustawienia:
        - write_timeout: 1 s,
        - brak kontroli przepływu (rtscts, dsrdtr, xonxoff = False),
        - inter_byte_timeout: 0.05 s.

        Dodatkowo:
        - czyści bufor wejściowy i wyjściowy,
        - robi krótkie opóźnienie, żeby Arduino zdążyło się zresetować.
        """
        if serial is None:
            raise RuntimeError("pyserial not available")

        self._ser = serial.Serial(
            self.port,
            self.baud,
            timeout=self.timeout,
            write_timeout=1,
            rtscts=False,
            dsrdtr=False,
            xonxoff=False,
            inter_byte_timeout=0.05,
        )

        try:
            # czyścimy zalegające dane
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
        except Exception:
            # jeśli nie ma tych metod / błąd portu – po prostu ignorujemy
            pass

        # krótkie opóźnienie – typowe przy komunikacji z Arduino,
        # które potrafi się zresetować przy otwarciu portu
        time.sleep(1.2)

        if DEBUG:
            print(f"[DEBUG] Opened {self.port} @ {self.baud} baud")

    def close(self) -> None:
        """
        Zamyka port szeregowy, jeśli jest otwarty.

        Po zamknięciu:
        - _ser ustawiany na None, żeby kolejne operacje wywaliły czytelny błąd.
        """
        if self._ser:
            try:
                self._ser.close()
                if DEBUG:
                    print("[DEBUG] Port closed")
            finally:
                self._ser = None

    def write_line(self, line: str) -> None:
        """
        Wysyła pojedynczą linię tekstu do urządzenia.

        Zachowanie:
        - usuwa z końca istniejące \r i \n,
        - dokleja jeden znak '\n',
        - koduje tekst jako ASCII (ignoruje znaki spoza zakresu),
        - wysyła dane i flushuje bufor wyjściowy.

        Uwaga:
        - format ramki (payload|CRC) jest przygotowany wyżej (w protocol.py),
          tutaj dodajemy tylko znak nowej linii.
        """
        if not self._ser:
            raise RuntimeError("not open")

        # dopilnowujemy, że na końcu będzie dokładnie '\n'
        data = (line.rstrip("\r\n") + "\n").encode("ascii", errors="ignore")

        if DEBUG:
            # wypisujemy ramkę zarówno w formie tekstowej, jak i hex
            hex_data = " ".join(f"{b:02X}" for b in data)
            print(f"[TX] {line.strip()}  ({hex_data})")

        self._ser.write(data)
        self._ser.flush()

        # krótkie opóźnienie, żeby nie "zasypać" Arduino zbyt szybkimi komendami
        time.sleep(0.002)

    def read_line(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Blokujący odczyt jednej linii tekstu z portu.

        Parametry:
            timeout:
                - jeśli None, używamy:
                    * dłuższego timeoutu (ok. 17 s) dla ostatniej komendy START,
                    * w pozostałych przypadkach self.timeout (domyślnie 1 s),
                - jeśli przekazany timeout w sekundach, używamy go wprost.

        Zwraca:
            - odczytaną linię (bez końcowego '\n' i ewentualnego '\r'),
            - None, jeśli minął timeout i nie udało się złożyć pełnej linii.

        Implementacja:
        - czytamy po 1 bajcie,
        - budujemy bufor aż trafimy na '\n',
        - jeśli przed '\n' jest '\r', usuwamy go (standard CRLF).
        """
        if not self._ser:
            raise RuntimeError("not open")

        # logika wyboru timeoutu:
        # - brak parametru timeout => sprawdzamy, czy ostatnią komendą był START
        if timeout is None:
            if hasattr(self, "_last_cmd") and self._last_cmd and self._last_cmd.startswith("START"):
                # START może trwać dłużej (np. 15 s pomiaru MAE + zapas)
                timeout = 17.0
            else:
                # w pozostałych przypadkach bazujemy na timeout obiektu
                timeout = self.timeout or 1.0

        end = time.time() + timeout
        buf = bytearray()

        while time.time() < end:
            # próbujemy odczytać pojedynczy bajt
            b = self._ser.read(1)

            if not b:
                # brak danych – wracamy na początek pętli (czekamy dalej)
                continue

            if b == b"\n":
                # koniec linii – ewentualnie usuwamy '\r' na końcu
                if buf.endswith(b"\r"):
                    buf.pop()
                try:
                    # dekodujemy całą linię jako ASCII
                    line = buf.decode("ascii", errors="ignore")
                    if DEBUG:
                        print(f"[RX] {line}")
                    return line
                finally:
                    # czyścimy bufor, na wszelki wypadek
                    buf.clear()
            else:
                # zwykły znak – dokładamy do bufora
                buf.extend(b)

        # jeśli wyszliśmy z pętli, to znaczy, że minął timeout
        if DEBUG:
            print("[RX TIMEOUT] Brak danych z portu")
        return None


def available_ports():
    """
    Zwraca listę dostępnych portów COM/TTY w systemie.

    Jeśli pyserial nie jest dostępny, zwraca pustą listę.
    """
    if list_ports is None:
        return []
    return [p.device for p in list_ports.comports()]
