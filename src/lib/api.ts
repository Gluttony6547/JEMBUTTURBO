import type { MatchPayload, MatchmakingResponse, ModeId } from "../types";
import { invokeFunction } from "./supabase";

export function joinMatchmaking(username: string, mode: ModeId) {
  return invokeFunction<MatchmakingResponse>("matchmaking", { username, mode });
}

export function leaveMatchmaking(username: string) {
  return invokeFunction<{ ok: true }>("matchmaking", { username }, "DELETE");
}

export function submitInput(room_id: string, username: string, typed_text: string) {
  return invokeFunction<{ match: MatchPayload }>("submit-input", { room_id, username, typed_text });
}

export function updateMatchState(room_id: string, event: string, data: Record<string, unknown>) {
  return invokeFunction<{ match: MatchPayload }>("match-state", { room_id, event, data });
}
