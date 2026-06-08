import type { ModeId } from "../types";

export const GAME_MODES: Record<
  ModeId,
  {
    label: string;
    description: string;
    minWords: number;
    maxWords: number;
    accent: string;
  }
> = {
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

export const DEFAULT_MODE: ModeId = "1000cc";

export const WORD_BANK = [
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
];

export function normalizeMode(mode: string | null | undefined): ModeId {
  return mode === "1000cc" || mode === "2000cc" || mode === "turbo" ? mode : DEFAULT_MODE;
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

export function generateTargetText(mode: ModeId, random = Math.random): string {
  const config = GAME_MODES[mode];
  const count = config.minWords + Math.floor(random() * (config.maxWords - config.minWords + 1));
  const words = Array.from({ length: count }, () => WORD_BANK[Math.floor(random() * WORD_BANK.length)]);
  const text = words.join(" ");
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}.`;
}

export function countWords(text: string): number {
  return text.replace(/[.]/g, " ").split(/\s+/).filter(Boolean).length;
}
