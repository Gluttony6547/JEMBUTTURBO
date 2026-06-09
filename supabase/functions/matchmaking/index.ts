import { corsHeaders, errorResponse, jsonResponse } from "../_shared/cors.ts";
import { cleanupStaleActiveMatches } from "../_shared/cleanup.ts";
import { fetchMatch, serviceClient } from "../_shared/supabase.ts";
import { generateTargetText, modePayload, normalizeMode, shapeMatch } from "../_shared/game.ts";

const QUEUE_STALE_MS = 15_000;

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const client = serviceClient();
    const body = await req.json().catch(() => ({}));
    const username = String(body.username ?? "").trim().slice(0, 24);

    if (!username) return errorResponse("username is required");
    await cleanupStaleActiveMatches(client);

    if (req.method === "DELETE") {
      const { error } = await client.from("matchmaking_queue").delete().eq("username", username);
      if (error) throw error;
      return jsonResponse({ ok: true });
    }

    if (req.method !== "POST") return errorResponse("method not allowed", 405);

    const existing = await client
      .from("match_players")
      .select("match_id, matches!inner(id, state)")
      .eq("username", username)
      .in("matches.state", ["COUNTDOWN", "RUNNING"])
      .maybeSingle();

    if (existing.data?.match_id) {
      const { match, players } = await fetchMatch(client, existing.data.match_id);
      return jsonResponse({ status: "matched", match: shapeMatch(match, players) });
    }

    const mode = normalizeMode(body.mode);
    const now = new Date().toISOString();
    const staleCutoff = new Date(Date.now() - QUEUE_STALE_MS).toISOString();

    const { error: staleDeleteError } = await client.from("matchmaking_queue").delete().lt("last_seen_at", staleCutoff);
    if (staleDeleteError) throw staleDeleteError;

    const { data: currentQueueEntry, error: currentQueueError } = await client
      .from("matchmaking_queue")
      .select("username, mode, joined_at, last_seen_at")
      .eq("username", username)
      .maybeSingle();
    if (currentQueueError) throw currentQueueError;

    const queuePayload =
      currentQueueEntry?.mode === mode
        ? { username, last_seen_at: now }
        : { username, mode, joined_at: now, last_seen_at: now };

    const { error: upsertError } = await client
      .from("matchmaking_queue")
      .upsert(queuePayload, { onConflict: "username" });
    if (upsertError) throw upsertError;

    const { data: queue, error: queueError } = await client
      .from("matchmaking_queue")
      .select("username, mode, joined_at, last_seen_at")
      .eq("mode", mode)
      .order("joined_at", { ascending: true })
      .limit(2);
    if (queueError) throw queueError;

    if (!queue || queue.length < 2 || queue[0].username !== username) {
      return jsonResponse({ status: "queued", queue_size: queue?.length ?? 1, ...modePayload(mode) });
    }

    const targetText = generateTargetText(mode);
    const roomId = crypto.randomUUID().slice(0, 8);
    const { data: match, error: matchError } = await client
      .from("matches")
      .insert({ room_id: roomId, mode, target_text: targetText, state: "COUNTDOWN" })
      .select("*")
      .single();
    if (matchError) throw matchError;

    const players = queue.map((item) => ({
      match_id: match.id,
      username: item.username,
      connected: true,
    }));
    const { error: playersError } = await client.from("match_players").insert(players);
    if (playersError) throw playersError;

    const { error: deleteError } = await client
      .from("matchmaking_queue")
      .delete()
      .in("username", queue.map((item) => item.username));
    if (deleteError) throw deleteError;

    const fullMatch = await fetchMatch(client, match.id);
    return jsonResponse({ status: "matched", match: shapeMatch(fullMatch.match, fullMatch.players) });
  } catch (error) {
    return errorResponse(error instanceof Error ? error.message : "matchmaking failed", 500);
  }
});
