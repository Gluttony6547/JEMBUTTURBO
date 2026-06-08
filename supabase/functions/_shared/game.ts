export type ModeId = "1000cc" | "2000cc" | "turbo";

export const GAME_MODES: Record<ModeId, {
  label: string;
  description: string;
  minWords: number;
  maxWords: number;
  accent: string;
}> = {
  "1000cc": {
    label: "Jempol 1000cc",
    description: "Sprint pendek 10-20 kata.",
    minWords: 10,
    maxWords: 20,
    accent: "#00B894",
  },
  "2000cc": {
    label: "Jempol 2000cc",
    description: "Battle sedang 20-30 kata.",
    minWords: 20,
    maxWords: 30,
    accent: "#0984E3",
  },
  turbo: {
    label: "Jempol Turbo",
    description: "Maraton cepat 40-50 kata.",
    minWords: 40,
    maxWords: 50,
    accent: "#D63031",
  },
};

const WORD_BANK = [
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
  "sinkron",
  "cepat",
  "stabil",
  "responsif",
];

export function normalizeMode(mode: unknown): ModeId {
  return mode === "1000cc" || mode === "2000cc" || mode === "turbo" ? mode : "1000cc";
}

export function modePayload(mode: ModeId) {
  const data = GAME_MODES[mode];
  return {
    mode,
    mode_label: data.label,
    mode_description: data.description,
    min_words: data.minWords,
    max_words: data.maxWords,
    accent: data.accent,
  };
}

export function generateTargetText(mode: ModeId) {
  const config = GAME_MODES[mode];
  const count = config.minWords + Math.floor(Math.random() * (config.maxWords - config.minWords + 1));
  const words = Array.from({ length: count }, () => WORD_BANK[Math.floor(Math.random() * WORD_BANK.length)]);
  const text = words.join(" ");
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}.`;
}

export function countWords(text: string) {
  return text.replace(/[.]/g, " ").split(/\s+/).filter(Boolean).length;
}

export function computeMetrics(targetText: string, typedText: string, elapsedSeconds: number) {
  const cappedText = typedText.slice(0, targetText.length);
  let correctChars = 0;
  for (let index = 0; index < Math.min(targetText.length, cappedText.length); index += 1) {
    if (targetText[index] === cappedText[index]) correctChars += 1;
  }
  const typedChars = cappedText.length;
  const elapsedMinutes = Math.max(elapsedSeconds, 0.1) / 60;
  const accuracy = (correctChars / Math.max(typedChars, 1)) * 100;
  const wpm = correctChars / 5 / elapsedMinutes;
  const finished = cappedText === targetText;
  return {
    typed_text: cappedText,
    typed_chars: typedChars,
    correct_chars: correctChars,
    progress: Number((correctChars / Math.max(targetText.length, 1)).toFixed(4)),
    accuracy: Number(accuracy.toFixed(2)),
    wpm: Number(wpm.toFixed(2)),
    score: Math.round(wpm * (accuracy / 100)) + (finished ? 25 : 0),
    finished,
    finish_time: finished ? Number(elapsedSeconds.toFixed(3)) : null,
  };
}

export function rankPlayers(players: any[]) {
  return [...players].sort((a, b) => {
    if (a.finished !== b.finished) return a.finished ? -1 : 1;
    if (a.finished && b.finished && a.finish_time !== b.finish_time) {
      return Number(a.finish_time ?? 999999) - Number(b.finish_time ?? 999999);
    }
    if (Number(a.wpm) !== Number(b.wpm)) return Number(b.wpm) - Number(a.wpm);
    if (Number(a.accuracy) !== Number(b.accuracy)) return Number(b.accuracy) - Number(a.accuracy);
    return Number(b.score) - Number(a.score);
  });
}

export function shapeMatch(match: any, players: any[]) {
  const mode = normalizeMode(match.mode);
  return {
    room_id: match.room_id,
    ...modePayload(mode),
    target_text: match.target_text,
    word_count: countWords(match.target_text),
    state: match.state,
    started_at: match.started_at,
    duration_limit: 120,
    players,
    first_finished: players.find((player) => player.finished)?.username ?? null,
    winner: match.winner,
    reason: match.reason,
    rankings: players.filter((player) => player.rank).sort((a, b) => Number(a.rank) - Number(b.rank)),
  };
}
