import type { MatchPayload, ModeId, PlayerSnapshot } from "../types";
import { computeMetrics, rankPlayers } from "./scoring";
import { countWords, generateTargetText, modePayload } from "./texts";

export function createDemoMatch(username: string, mode: ModeId): MatchPayload {
  const targetText = generateTargetText(mode);
  const base = modePayload(mode);
  return {
    room_id: `demo-${crypto.randomUUID().slice(0, 8)}`,
    mode,
    mode_label: base.mode_label,
    mode_description: base.mode_description,
    target_text: targetText,
    word_count: countWords(targetText),
    state: "COUNTDOWN",
    duration_limit: 120,
    players: [
      emptyPlayer(username),
      emptyPlayer("RX-78 Rival"),
    ],
  };
}

export function emptyPlayer(username: string): PlayerSnapshot {
  return {
    username,
    connected: true,
    typed_chars: 0,
    correct_chars: 0,
    progress: 0,
    accuracy: 0,
    wpm: 0,
    score: 0,
    finished: false,
    finish_time: null,
    latency_ms: username === "RX-78 Rival" ? 28 : 18,
  };
}

export function updatePlayerFromTyping(
  player: PlayerSnapshot,
  targetText: string,
  typedText: string,
  elapsedSeconds: number,
): PlayerSnapshot {
  const metrics = computeMetrics(targetText, typedText, elapsedSeconds);
  return {
    ...player,
    ...metrics,
    finish_time: metrics.finished && !player.finish_time ? Number(elapsedSeconds.toFixed(3)) : player.finish_time,
  };
}

export function finishMatch(players: PlayerSnapshot[]): PlayerSnapshot[] {
  return rankPlayers(players).map((player, index) => ({ ...player, rank: index + 1 }));
}
