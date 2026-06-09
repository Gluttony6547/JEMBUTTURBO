const ACTIVE_PLAYER_STALE_MS = 20_000;

function toNumber(value: unknown, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function isPlayerStale(player: any, cutoffTime: number) {
  const lastSeen = new Date(player.last_update_at ?? player.joined_at ?? 0).getTime();
  return !Number.isFinite(lastSeen) || lastSeen < cutoffTime;
}

function rankDisconnectedMatch(players: any[]) {
  return [...players].sort((a, b) => {
    if (a.connected !== b.connected) return a.connected ? -1 : 1;
    if (toNumber(a.score) !== toNumber(b.score)) return toNumber(b.score) - toNumber(a.score);
    if (toNumber(a.progress) !== toNumber(b.progress)) return toNumber(b.progress) - toNumber(a.progress);
    if (toNumber(a.wpm) !== toNumber(b.wpm)) return toNumber(b.wpm) - toNumber(a.wpm);
    return toNumber(b.accuracy) - toNumber(a.accuracy);
  });
}

export async function cleanupStaleActiveMatches(client: any) {
  const cutoffTime = Date.now() - ACTIVE_PLAYER_STALE_MS;
  const { data: matches, error: matchesError } = await client
    .from("matches")
    .select("*")
    .in("state", ["COUNTDOWN", "RUNNING"])
    .order("updated_at", { ascending: true })
    .limit(30);
  if (matchesError) throw matchesError;

  for (const match of matches ?? []) {
    const { data: players, error: playersError } = await client
      .from("match_players")
      .select("*")
      .eq("match_id", match.id);
    if (playersError) throw playersError;
    if (!players || players.length < 2) continue;

    const stalePlayers = players.filter((player: any) => isPlayerStale(player, cutoffTime));
    if (stalePlayers.length === 0) continue;

    await client
      .from("match_players")
      .update({ connected: false, last_update_at: new Date().toISOString() })
      .eq("match_id", match.id)
      .in(
        "username",
        stalePlayers.map((player: any) => player.username),
      );

    const refreshedPlayers = players.map((player: any) =>
      stalePlayers.some((stalePlayer: any) => stalePlayer.username === player.username)
        ? { ...player, connected: false }
        : player,
    );
    const connectedPlayers = refreshedPlayers.filter((player: any) => player.connected);
    if (connectedPlayers.length === refreshedPlayers.length) continue;

    const rankings = rankDisconnectedMatch(refreshedPlayers);
    for (let index = 0; index < rankings.length; index += 1) {
      await client.from("match_players").update({ rank: index + 1 }).eq("id", rankings[index].id);
    }

    await client
      .from("matches")
      .update({
        state: "FINISHED",
        winner: connectedPlayers[0]?.username ?? null,
        reason: connectedPlayers.length > 0 ? "opponent disconnected" : "all players disconnected",
        finished_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("id", match.id);
  }
}
