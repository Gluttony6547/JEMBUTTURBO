"""Typing prompts and game modes used by the game server."""

from __future__ import annotations

import random
from typing import Any


GAME_MODES: dict[str, dict[str, Any]] = {
    "1000cc": {
        "label": "Jempol 1000cc",
        "description": "Sprint pendek 10-20 kata.",
        "min_words": 10,
        "max_words": 20,
        "accent": "#00B894",
    },
    "2000cc": {
        "label": "Jempol 2000cc",
        "description": "Battle sedang 20-30 kata.",
        "min_words": 20,
        "max_words": 30,
        "accent": "#0984E3",
    },
    "turbo": {
        "label": "Jempol Turbo",
        "description": "Maraton cepat 40-50 kata.",
        "min_words": 40,
        "max_words": 50,
        "accent": "#D63031",
    },
}

DEFAULT_MODE = "1000cc"

WORD_BANK = [
    "jaringan",
    "komputer",
    "client",
    "server",
    "socket",
    "protokol",
    "packet",
    "latency",
    "threading",
    "selectors",
    "buffer",
    "queue",
    "room",
    "matchmaking",
    "typing",
    "battle",
    "progress",
    "akurasi",
    "ranking",
    "skor",
    "reconnect",
    "timeout",
    "logging",
    "validasi",
    "serialization",
    "payload",
    "session",
    "token",
    "broadcast",
    "state",
    "update",
    "real",
    "time",
    "sinkron",
    "cepat",
    "stabil",
    "respon",
    "input",
    "output",
    "multiplexing",
    "reliable",
    "urutan",
    "koneksi",
    "ranking",
    "pemenang",
    "lawan",
    "arena",
    "countdown",
    "finish",
    "turbo",
    "performa",
    "beban",
    "simulasi",
    "demo",
    "kelas",
    "final",
    "project",
    "python",
    "message",
    "format",
    "error",
    "online",
    "mode",
    "mengetik",
    "jempol",
    "kecepatan",
    "kontrol",
    "hasil",
    "analisis",
    "kompetisi",
    "responsif",
]


def normalize_mode(mode: str | None) -> str:
    if mode in GAME_MODES:
        return str(mode)
    return DEFAULT_MODE


def mode_payload(mode: str) -> dict[str, Any]:
    normalized = normalize_mode(mode)
    data = GAME_MODES[normalized]
    return {
        "mode": normalized,
        "mode_label": data["label"],
        "mode_description": data["description"],
        "min_words": data["min_words"],
        "max_words": data["max_words"],
        "accent": data["accent"],
    }


def generate_target_text(mode: str, rng: random.Random | None = None) -> str:
    selected_rng = rng or random
    mode_data = GAME_MODES[normalize_mode(mode)]
    word_count = selected_rng.randint(mode_data["min_words"], mode_data["max_words"])
    words = [selected_rng.choice(WORD_BANK) for _ in range(word_count)]
    text = " ".join(words)
    return text[0].upper() + text[1:] + "."


def count_words(text: str) -> int:
    return len([word for word in text.replace(".", " ").split() if word])
