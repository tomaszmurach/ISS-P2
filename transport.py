#!/usr/bin/env python
# coding: utf-8

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
    port: str
    baud: int = 9600
    timeout: float = 1.0
    _ser: Optional[object] = None

    def open(self) -> None:
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
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
        except Exception:
            pass
        time.sleep(1.2)
        if DEBUG:
            print(f"[DEBUG] Opened {self.port} @ {self.baud} baud")

    def close(self) -> None:
        if self._ser:
            try:
                self._ser.close()
                if DEBUG:
                    print("[DEBUG] Port closed")
            finally:
                self._ser = None

    def write_line(self, line: str) -> None:
        if not self._ser:
            raise RuntimeError("not open")
        data = (line.rstrip("\r\n") + "\n").encode("ascii", errors="ignore")
        if DEBUG:
            hex_data = " ".join(f"{b:02X}" for b in data)
            print(f"[TX] {line.strip()}  ({hex_data})")
        self._ser.write(data)
        self._ser.flush()
        time.sleep(0.002)

    def read_line(self, timeout: Optional[float] = None) -> Optional[str]:
        if not self._ser:
            raise RuntimeError("not open")

        if timeout is None:
            if hasattr(self, "_last_cmd") and self._last_cmd and self._last_cmd.startswith("START"):
                timeout = 17.0
            else:
                timeout = self.timeout or 1.0

        end = time.time() + timeout
        buf = bytearray()

        while time.time() < end:
            b = self._ser.read(1)
            if not b:
                continue
            if b == b"\n":
                if buf.endswith(b"\r"):
                    buf.pop()
                try:
                    line = buf.decode("ascii", errors="ignore")
                    if DEBUG:
                        print(f"[RX] {line}")
                    return line
                finally:
                    buf.clear()
            else:
                buf.extend(b)
        if DEBUG:
            print("[RX TIMEOUT] Brak danych z portu")
        return None

def available_ports():
    if list_ports is None:
        return []
    return [p.device for p in list_ports.comports()]
