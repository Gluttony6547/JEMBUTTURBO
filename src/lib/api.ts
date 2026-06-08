import type { MatchPayload, MatchmakingResponse, ModeId, PlayerSnapshot } from "../types";
import { computeMetrics, rankPlayers } from "./scoring";
import { invokeFunction, supabase } from "./supabase";
import { countWords, generateTargetText, modePayload, normalizeMode } from "./texts";

type MatchRow = {
  id: string;
  room_id: string;
  mode: ModeId;
  target_text: string;
  state: MatchPayload["state"];
  started_at?: string | null;
  winner?: string | null;
  reason?: string | null;
  rematch_requests?: string[] | null;
};

type PlayerRow = PlayerSnapshot & {
  id: string;
  match_id: string;
  joined_at?: string;
};

type QueueRow = {
  username: string;
  mode: ModeId;
  joined_at: string;
  last_seen_at: string;
};

type MatchStateResponse = {
  match: MatchPayload;
  waiting?: boolean;
  ready_count?: number;
  needed_count?: number;
  waiting_for?: string[];
};

const QUEUE_STALE_MS = 15_000;

function client() {
  if (!supabase) {
    throw new Error("Supabase is not configured. Fill VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.");
  }
  return supabase;
}

async function invokeOrDirect<T>(
  functionName: string,
  body: Record<string, unknown>,
  fallback: () => Promise<T>,
  method: "POST" | "DELETE" = "POST",
): Promise<T> {
  try {
    return await invokeFunction<T>(functionName, body, method);
  } catch (error) {
    console.warn(`Falling back to direct Supabase API for ${functionName}.`, error);
    return fallback();
  }
}

function createRoomId() {
  if ("randomUUID" in crypto) {
    return crypto.randomUUID().split("-").join("").slice(0, 8);
  }
  return Math.random().toString(36).slice(2, 10);
}

function toNumber(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function shapePlayer(row: Partial<PlayerRow>): PlayerSnapshot {
  return {
    username: String(row.username ?? ""),
    connected: Boolean(row.connected ?? true),
    typed_chars: toNumber(row.typed_chars),
    correct_chars: toNumber(row.correct_chars),
    progress: toNumber(row.progress),
    accuracy: toNumber(row.accuracy),
    wpm: toNumber(row.wpm),
    score: toNumber(row.score),
    finished: Boolean(row.finished),
    finish_time: row.finish_time === null || row.finish_time === undefined ? null : toNumber(row.finish_time),
    latency_ms: row.latency_ms === null || row.latency_ms === undefined ? null : toNumber(row.latency_ms),
    rank: row.rank === null || row.rank === undefined ? undefined : toNumber(row.rank),
  };
}

function shapeMatch(match: MatchRow, players: PlayerRow[]): MatchPayload {
  const mode = normalizeMode(match.mode);
  const shapedPlayers = players.map(shapePlayer);
  return {
    room_id: match.room_id,
    ...modePayload(mode),
    target_text: match.target_text,
    word_count: countWords(match.target_text),
    state: match.state,
    started_at: match.started_at,
    duration_limit: 120,
    players: shapedPlayers,
    first_finished: shapedPlayers.find((player) => player.finished)?.username ?? null,
    winner: match.winner ?? null,
    reason: match.reason ?? null,
    rankings: shapedPlayers
      .filter((player) => player.rank)
      .sort((a, b) => Number(a.rank) - Number(b.rank)),
  };
}

async function fetchMatchById(matchId: string): Promise<MatchPayload> {
  const db = client();
  const { data: match, error: matchError } = await db.from("matches").select("*").eq("id", matchId).single();
  if (matchError) throw matchError;

  const { data: players, error: playersError } = await db
    .from("match_players")
    .select("*")
    .eq("match_id", matchId)
    .order("rank", { ascending: true, nullsFirst: false })
    .order("joined_at", { ascending: true });
  if (playersError) throw playersError;

  return shapeMatch(match as MatchRow, (players ?? []) as PlayerRow[]);
}

async function fetchMatchByRoom(roomId: string): Promise<{ row: MatchRow; payload: MatchPayload }> {
  const db = client();
  const { data: match, error } = await db.from("matches").select("*").eq("room_id", roomId).single();
  if (error) throw error;
  return {
    row: match as MatchRow,
    payload: await fetchMatchById((match as MatchRow).id),
  };
}

async function directJoinMatchmaking(username: string, mode: ModeId): Promise<MatchmakingResponse> {
  const db = client();
  const cleanUsername = username.trim().slice(0, 24);
  if (!cleanUsername) throw new Error("username is required");

  const { data: existingLinks, error: existingError } = await db
    .from("match_players")
    .select("match_id")
    .eq("username", cleanUsername)
    .order("joined_at", { ascending: false })
    .limit(8);
  if (existingError) throw existingError;

  for (const link of existingLinks ?? []) {
    const { data: activeMatch, error } = await db
      .from("matches")
      .select("*")
      .eq("id", link.match_id)
      .in("state", ["COUNTDOWN", "RUNNING"])
      .maybeSingle();
    if (error) throw error;
    if (activeMatch) {
      return { status: "matched", match: await fetchMatchById((activeMatch as MatchRow).id) };
    }
  }

  const normalizedMode = normalizeMode(mode);
  const now = new Date().toISOString();
  const staleCutoff = new Date(Date.now() - QUEUE_STALE_MS).toISOString();

  const { error: staleDeleteError } = await db.from("matchmaking_queue").delete().lt("last_seen_at", staleCutoff);
  if (staleDeleteError) throw staleDeleteError;

  const { data: currentQueueEntry, error: currentQueueError } = await db
    .from("matchmaking_queue")
    .select("username, mode, joined_at, last_seen_at")
    .eq("username", cleanUsername)
    .maybeSingle();
  if (currentQueueError) throw currentQueueError;

  const queueEntry = currentQueueEntry as QueueRow | null;
  const { error: queueWriteError } =
    queueEntry?.mode === normalizedMode
      ? await db.from("matchmaking_queue").update({ last_seen_at: now }).eq("username", cleanUsername)
      : await db
          .from("matchmaking_queue")
          .upsert(
            { username: cleanUsername, mode: normalizedMode, joined_at: now, last_seen_at: now },
            { onConflict: "username" },
          );
  if (queueWriteError) throw queueWriteError;

  const { data: queue, error: queueError } = await db
    .from("matchmaking_queue")
    .select("username, mode, joined_at, last_seen_at")
    .eq("mode", normalizedMode)
    .order("joined_at", { ascending: true })
    .limit(2);
  if (queueError) throw queueError;

  if (!queue || queue.length < 2 || queue[0].username !== cleanUsername) {
    return { status: "queued", queue_size: queue?.length ?? 1, ...modePayload(normalizedMode) };
  }

  const { data: match, error: matchError } = await db
    .from("matches")
    .insert({
      room_id: createRoomId(),
      mode: normalizedMode,
      target_text: generateTargetText(normalizedMode),
      state: "COUNTDOWN",
    })
    .select("*")
    .single();
  if (matchError) throw matchError;

  const playerRows = queue.map((item) => ({
    match_id: (match as MatchRow).id,
    username: item.username,
    connected: true,
  }));
  const { error: playersError } = await db.from("match_players").insert(playerRows);
  if (playersError) throw playersError;

  const { error: deleteError } = await db
    .from("matchmaking_queue")
    .delete()
    .in(
      "username",
      queue.map((item) => item.username),
    );
  if (deleteError) throw deleteError;

  return { status: "matched", match: await fetchMatchById((match as MatchRow).id) };
}

async function directLeaveMatchmaking(username: string) {
  const { error } = await client().from("matchmaking_queue").delete().eq("username", username.trim().slice(0, 24));
  if (error) throw error;
  return { ok: true as const };
}

async function directSubmitInput(roomId: string, username: string, typedText: string): Promise<{ match: MatchPayload }> {
  const db = client();
  const { row: match } = await fetchMatchByRoom(roomId);

  if (match.state === "FINISHED") {
    return { match: await fetchMatchById(match.id) };
  }
  if (match.state !== "RUNNING" || !match.started_at) {
    throw new Error("match is not running");
  }

  const elapsedSeconds = (Date.now() - new Date(match.started_at).getTime()) / 1000;
  const metrics = computeMetrics(match.target_text, typedText, elapsedSeconds);
  const finishTime = metrics.finished ? Number(elapsedSeconds.toFixed(3)) : null;

  const { data: currentPlayer, error: currentPlayerError } = await db
    .from("match_players")
    .select("finish_time")
    .eq("match_id", match.id)
    .eq("username", username.trim().slice(0, 24))
    .maybeSingle();
  if (currentPlayerError) throw currentPlayerError;

  const { error: updateError } = await db
    .from("match_players")
    .update({
      typed_text: typedText.slice(0, match.target_text.length),
      ...metrics,
      finish_time: metrics.finished ? currentPlayer?.finish_time ?? finishTime : null,
      last_update_at: new Date().toISOString(),
    })
    .eq("match_id", match.id)
    .eq("username", username.trim().slice(0, 24));
  if (updateError) throw updateError;

  const { data: players, error: playersError } = await db.from("match_players").select("*").eq("match_id", match.id);
  if (playersError) throw playersError;

  if (players && players.length > 0 && players.every((player) => player.finished)) {
    const rankings = rankPlayers((players as PlayerRow[]).map((player) => ({ ...shapePlayer(player), id: player.id })));
    for (let index = 0; index < rankings.length; index += 1) {
      const rankedPlayer = rankings[index] as PlayerSnapshot & { id?: string };
      if (rankedPlayer.id) {
        await db.from("match_players").update({ rank: index + 1 }).eq("id", rankedPlayer.id);
      }
    }
    await db
      .from("matches")
      .update({
        state: "FINISHED",
        winner: rankings[0]?.username ?? null,
        reason: "all players finished",
        finished_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("id", match.id);
  }

  return { match: await fetchMatchById(match.id) };
}

async function directUpdateMatchState(
  roomId: string,
  event: string,
  data: Record<string, unknown>,
): Promise<MatchStateResponse> {
  const db = client();
  const { row: match } = await fetchMatchByRoom(roomId);

  if (event === "MATCH_START" && match.state === "COUNTDOWN") {
    await db
      .from("matches")
      .update({
        state: "RUNNING",
        started_at: typeof data.started_at === "string" ? data.started_at : new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("id", match.id);
    return { match: await fetchMatchById(match.id) };
  }

  if (event === "REMATCH_REQUEST") {
    const username = String(data.username ?? "").trim().slice(0, 24);
    const requests = new Set<string>([...(match.rematch_requests ?? []), username].filter(Boolean));
    await db.from("matches").update({ rematch_requests: [...requests] }).eq("id", match.id);

    const currentMatch = await fetchMatchById(match.id);
    const allReady = currentMatch.players.every((player) => requests.has(player.username));
    if (!allReady) {
      return {
        waiting: true,
        ready_count: requests.size,
        needed_count: currentMatch.players.length,
        waiting_for: currentMatch.players.filter((player) => !requests.has(player.username)).map((player) => player.username),
        match: currentMatch,
      };
    }

    const { data: newMatch, error: newMatchError } = await db
      .from("matches")
      .insert({
        room_id: createRoomId(),
        mode: match.mode,
        target_text: generateTargetText(match.mode),
        state: "COUNTDOWN",
      })
      .select("*")
      .single();
    if (newMatchError) throw newMatchError;

    const { error: playersError } = await db.from("match_players").insert(
      currentMatch.players.map((player) => ({
        match_id: (newMatch as MatchRow).id,
        username: player.username,
        connected: true,
      })),
    );
    if (playersError) throw playersError;

    return { waiting: false, match: await fetchMatchById((newMatch as MatchRow).id) };
  }

  return { match: await fetchMatchById(match.id) };
}

export function joinMatchmaking(username: string, mode: ModeId) {
  return invokeOrDirect<MatchmakingResponse>("matchmaking", { username, mode }, () => directJoinMatchmaking(username, mode));
}

export function leaveMatchmaking(username: string) {
  return invokeOrDirect<{ ok: true }>("matchmaking", { username }, () => directLeaveMatchmaking(username), "DELETE");
}

export function submitInput(room_id: string, username: string, typed_text: string) {
  return invokeOrDirect<{ match: MatchPayload }>("submit-input", { room_id, username, typed_text }, () =>
    directSubmitInput(room_id, username, typed_text),
  );
}

export function updateMatchState(room_id: string, event: string, data: Record<string, unknown>) {
  return invokeOrDirect<MatchStateResponse>("match-state", { room_id, event, data }, () =>
    directUpdateMatchState(room_id, event, data),
  );
}
