import { createClient } from "https://esm.sh/@supabase/supabase-js@2.50.0";

export function serviceClient() {
  const url = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceRoleKey) {
    throw new Error("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY.");
  }
  return createClient(url, serviceRoleKey);
}

export async function fetchMatch(client: ReturnType<typeof createClient>, matchId: string) {
  const { data: match, error: matchError } = await client
    .from("matches")
    .select("*")
    .eq("id", matchId)
    .single();
  if (matchError) throw matchError;

  const { data: players, error: playersError } = await client
    .from("match_players")
    .select("*")
    .eq("match_id", matchId)
    .order("rank", { ascending: true, nullsFirst: false })
    .order("joined_at", { ascending: true });
  if (playersError) throw playersError;

  return { match, players: players ?? [] };
}
