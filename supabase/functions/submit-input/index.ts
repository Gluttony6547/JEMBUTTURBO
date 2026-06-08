import { corsHeaders, errorResponse, jsonResponse } from "../_shared/cors.ts";
import { computeMetrics, rankPlayers, shapeMatch } from "../_shared/game.ts";
import { fetchMatch, serviceClient } from "../_shared/supabase.ts";

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return errorResponse("method not allowed", 405);

  try {
    const client = serviceClient();
    const body = await req.json();
    const roomId = String(body.room_id ?? "");
    const username = String(body.username ?? "").trim().slice(0, 24);
    const typedText = String(body.typed_text ?? "");

    if (!roomId || !username) return errorResponse("room_id and username are required");

    const { data: match, error: matchError } = await client
      .from("matches")
      .select("*")
      .eq("room_id", roomId)
      .single();
    if (matchError) throw matchError;
    if (match.state === "FINISHED") {
      const full = await fetchMatch(client, match.id);
      return jsonResponse({ match: shapeMatch(full.match, full.players) });
    }
    if (match.state !== "RUNNING" || !match.started_at) {
      return errorResponse("match is not running");
    }

    const elapsedSeconds = (Date.now() - new Date(match.started_at).getTime()) / 1000;
    const metrics = computeMetrics(match.target_text, typedText, elapsedSeconds);
    const { error: updateError } = await client
      .from("match_players")
      .update({
        ...metrics,
        finish_time: metrics.finished ? metrics.finish_time : null,
        last_update_at: new Date().toISOString(),
      })
      .eq("match_id", match.id)
      .eq("username", username);
    if (updateError) throw updateError;

    const full = await fetchMatch(client, match.id);
    if (full.players.length > 0 && full.players.every((player) => player.finished)) {
      const rankings = rankPlayers(full.players);
      for (let index = 0; index < rankings.length; index += 1) {
        await client.from("match_players").update({ rank: index + 1 }).eq("id", rankings[index].id);
      }
      await client
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

    const refreshed = await fetchMatch(client, match.id);
    return jsonResponse({ match: shapeMatch(refreshed.match, refreshed.players) });
  } catch (error) {
    return errorResponse(error instanceof Error ? error.message : "submit failed", 500);
  }
});
