#!/usr/bin/env python
# coding: utf-8


DEBUG = False

def compute_crc(payload: str) -> int:
    return sum(payload.encode("ascii", "ignore")) & 0xFF

def add_crc(payload: str) -> str:
    p = payload.strip()
    crc = compute_crc(p)
    frame = f"{p}|{crc:02X}"
    if DEBUG:
        print(f"[CRC DEBUG] payload='{p}' crc={crc:02X} frame='{frame}'")
    return frame

def normalize(s: str) -> str:
    return s.strip()

def crc_debug(payload: str) -> None:
    p = payload.strip()
    crc = compute_crc(p)
    frame = f"{p}|{crc:02X}"
    print("payload :", p)
    print("crc     :", f"{crc:02X}")
    print("frame   :", frame)
