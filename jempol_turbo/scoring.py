"""Typing metrics and ranking helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metrics:
    typed_chars: int
    correct_chars: int
    progress: float
    accuracy: float
    wpm: float
    score: int
    finished: bool


def count_correct_chars(target_text: str, typed_text: str) -> int:
    correct = 0
    for expected, actual in zip(target_text, typed_text):
        if expected == actual:
            correct += 1
    return correct


def compute_metrics(
    target_text: str,
    typed_text: str,
    elapsed_seconds: float,
    *,
    completion_bonus: int = 25,
) -> Metrics:
    typed_text = typed_text[: len(target_text)]
    typed_chars = len(typed_text)
    correct_chars = count_correct_chars(target_text, typed_text)
    total_chars = max(len(target_text), 1)
    elapsed_minutes = max(elapsed_seconds, 0.1) / 60.0

    progress = correct_chars / total_chars
    accuracy = correct_chars / max(typed_chars, 1) * 100.0
    wpm = (correct_chars / 5.0) / elapsed_minutes
    finished = typed_text == target_text
    score = round(wpm * (accuracy / 100.0))
    if finished:
        score += completion_bonus

    return Metrics(
        typed_chars=typed_chars,
        correct_chars=correct_chars,
        progress=round(progress, 4),
        accuracy=round(accuracy, 2),
        wpm=round(wpm, 2),
        score=int(score),
        finished=finished,
    )


def ranking_key(player_state: dict) -> tuple[int, float, float, float, int]:
    """Sort key for player ranking.

    Finished players win over unfinished players. Among finished players,
    lower finish time is better. Remaining ties use WPM, accuracy, and score.
    """

    finished = 1 if player_state.get("finished") else 0
    finish_time = float(player_state.get("finish_time") or 999999.0)
    return (
        finished,
        -finish_time,
        float(player_state.get("wpm", 0.0)),
        float(player_state.get("accuracy", 0.0)),
        int(player_state.get("score", 0)),
    )
