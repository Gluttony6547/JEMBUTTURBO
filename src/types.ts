export type ModeId = "1000cc" | "2000cc" | "turbo";

export type MatchState = "COUNTDOWN" | "RUNNING" | "FINISHED";

export type Screen = "login" | "matchmaking" | "arena" | "results";

export type PlayerSnapshot = {
  username: string;
  connected: boolean;
  typed_chars: number;
  correct_chars: number;
  progress: number;
  accuracy: number;
  wpm: number;
  score: number;
  finished: boolean;
  finish_time: number | null;
  latency_ms?: number | null;
  rank?: number;
};

export type MatchPayload = {
  room_id: string;
  mode: ModeId;
  mode_label: string;
  mode_description: string;
  target_text: string;
  word_count: number;
  state: MatchState;
  started_at?: string | null;
  duration_limit: number;
  players: PlayerSnapshot[];
  first_finished?: string | null;
  winner?: string | null;
  reason?: string | null;
  rankings?: PlayerSnapshot[];
};

export type MatchmakingResponse =
  | {
      status: "queued";
      queue_size: number;
      mode: ModeId;
      mode_label: string;
      mode_description: string;
    }
  | {
      status: "matched";
      match: MatchPayload;
    };

export type BroadcastEvent =
  | "MATCH_FOUND"
  | "COUNTDOWN"
  | "MATCH_START"
  | "STATE_UPDATE"
  | "PLAYER_FINISHED"
  | "MATCH_FINISH"
  | "REMATCH_WAITING";
