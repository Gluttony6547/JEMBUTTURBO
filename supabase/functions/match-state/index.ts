import { corsHeaders, errorResponse, jsonResponse } from "../_shared/cors.ts";
import { fetchMatch, serviceClient } from "../_shared/supabase.ts";
import { generateTargetText, shapeMatch } from "../_shared/game.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return errorResponse("method not allowed", 405);

  try {
    const client = serviceClient();
    const body = await req.json();
    const roomId = String(body.room_id ?? "");
    const event = String(body.event ?? "");
    const data = (body.data ?? {}) as Record<string, unknown>;
    if (!roomId || !event) return errorResponse("room_id and event are required");

    const { data: match, error: matchError } = await client
      .from("matches")
      .select("*")
      .eq("room_id", roomId)
      .single();
    if (matchError) throw matchError;

    if (event === "MATCH_START" && match.state === "COUNTDOWN") {
      await client
        .from("matches")
        .update({
          state: "RUNNING",
          started_at: data.started_at ?? new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
        .eq("id", match.id);
      const refreshed = await fetchMatch(client, match.id);
      return jsonResponse({ match: shapeMatch(refreshed.match, refreshed.players) });
    }

    if (event === "REMATCH_REQUEST") {
      const username = String(data.username ?? "").trim();
      const requests = new Set<string>([...(match.rematch_requests ?? []), username].filter(Boolean));
      await client.from("matches").update({ rematch_requests: [...requests] }).eq("id", match.id);
      const full = await fetchMatch(client, match.id);
      const allReady = full.players.every((player) => requests.has(player.username));
      if (!allReady) {
        return jsonResponse({
          waiting: true,
          ready_count: requests.size,
          needed_count: full.players.length,
          waiting_for: full.players.filter((player) => !requests.has(player.username)).map((player) => player.username),
          match: shapeMatch(full.match, full.players),
        });
      }

      const targetText = generateTargetText(match.mode);
      const roomId = crypto.randomUUID().slice(0, 8);
      const { data: newMatch, error: newMatchError } = await client
        .from("matches")
        .insert({ room_id: roomId, mode: match.mode, target_text: targetText, state: "COUNTDOWN" })
        .select("*")
        .single();
      if (newMatchError) throw newMatchError;

      await client.from("match_players").insert(
        full.players.map((player) => ({
          match_id: newMatch.id,
          username: player.username,
          connected: true,
        })),
      );
      const refreshed = await fetchMatch(client, newMatch.id);
      return jsonResponse({ waiting: false, match: shapeMatch(refreshed.match, refreshed.players) });
    }

    const full = await fetchMatch(client, match.id);
    return jsonResponse({ match: shapeMatch(full.match, full.players) });
  } catch (error) {
    return errorResponse(error instanceof Error ? error.message : "match-state failed", 500);
  }
});
