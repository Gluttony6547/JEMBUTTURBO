import { FormEvent, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  Gauge,
  LoaderCircle,
  Radio,
  RotateCcw,
  SatelliteDish,
  Send,
  Shield,
  Swords,
  Trophy,
  Wifi,
} from "lucide-react";
import type { BroadcastEvent, MatchPayload, ModeId, PlayerSnapshot, Screen } from "./types";
import { joinMatchmaking, leaveMatchmaking, submitInput, updateMatchState } from "./lib/api";
import { createDemoMatch, finishMatch, updatePlayerFromTyping } from "./lib/demo";
import { computeMetrics } from "./lib/scoring";
import { GAME_MODES } from "./lib/texts";
import { isSupabaseConfigured } from "./lib/supabase";
import { useMatchChannel } from "./hooks/useMatchChannel";

const COUNTDOWN_SECONDS = 3;
const SESSION_KEY = "jempol-turbo-web-session";

function App() {
  const [screen, setScreen] = useState<Screen>("login");
  const [username, setUsername] = useState("");
  const [mode, setMode] = useState<ModeId>("1000cc");
  const [match, setMatch] = useState<MatchPayload | null>(null);
  const [typedText, setTypedText] = useState("");
  const [queueSize, setQueueSize] = useState(0);
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);
  const [status, setStatus] = useState("Ready for sortie.");
  const [error, setError] = useState("");
  const [finishBanner, setFinishBanner] = useState("Belum ada yang finish.");
  const [rematchReady, setRematchReady] = useState({ ready: 0, needed: 2, waitingFor: [] as string[] });
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const lastSubmitAt = useRef(0);

  const channel = useMatchChannel(match?.room_id ?? null, (event, payload) => {
    handleBroadcast(event, payload);
  });

  const remoteEnabled = isSupabaseConfigured;

  useEffect(() => {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return;
    try {
      const saved = JSON.parse(raw) as { username?: string; mode?: ModeId };
      if (saved.username) setUsername(saved.username);
      if (saved.mode && GAME_MODES[saved.mode]) setMode(saved.mode);
    } catch {
      localStorage.removeItem(SESSION_KEY);
    }
  }, []);

  useEffect(() => {
    if (screen !== "matchmaking" || !remoteEnabled || !username) return;
    const interval = window.setInterval(() => {
      void pollMatchmaking();
    }, 1600);
    return () => window.clearInterval(interval);
  }, [screen, remoteEnabled, username, mode]);

  useEffect(() => {
    if (!match || screen !== "arena" || match.state !== "COUNTDOWN") return;
    setCountdown(COUNTDOWN_SECONDS);
    const tick = window.setInterval(() => {
      setCountdown((value) => {
        if (value <= 1) {
          window.clearInterval(tick);
          startMatch();
          return 0;
        }
        return value - 1;
      });
    }, 1000);
    return () => window.clearInterval(tick);
  }, [match?.room_id, match?.state, screen]);

  useEffect(() => {
    if (!match || screen !== "arena" || match.state !== "RUNNING" || remoteEnabled) return;
    const interval = window.setInterval(() => {
      setMatch((current) => {
        if (!current || current.state !== "RUNNING" || startedAt === null) return current;
        const elapsed = (Date.now() - startedAt) / 1000;
        const rival = current.players[1];
        const rivalTargetChars = Math.min(current.target_text.length, Math.floor(elapsed * 8.5));
        const updatedRival = updatePlayerFromTyping(
          rival,
          current.target_text,
          current.target_text.slice(0, rivalTargetChars),
          elapsed,
        );
        const players = [current.players[0], updatedRival];
        const firstFinished = current.first_finished ?? players.find((player) => player.finished)?.username ?? null;
        if (updatedRival.finished && firstFinished === updatedRival.username) {
          setFinishBanner(`${updatedRival.username} finish duluan. Kejar akurasi dan skor.`);
        }
        if (players.every((player) => player.finished)) {
          const rankings = finishMatch(players);
          setScreen("results");
          return {
            ...current,
            state: "FINISHED",
            players,
            rankings,
            winner: rankings[0]?.username ?? null,
            reason: "all players finished",
            first_finished: firstFinished,
          };
        }
        return { ...current, players, first_finished: firstFinished };
      });
    }, 260);
    return () => window.clearInterval(interval);
  }, [match?.room_id, match?.state, remoteEnabled, screen, startedAt]);

  async function handleJoin(event?: FormEvent) {
    event?.preventDefault();
    setError("");
    const normalizedUsername = username.trim();
    if (!normalizedUsername) {
      setError("Username wajib diisi.");
      return;
    }

    localStorage.setItem(SESSION_KEY, JSON.stringify({ username: normalizedUsername, mode }));

    if (!remoteEnabled) {
      const demoMatch = createDemoMatch(normalizedUsername, mode);
      setStatus("Demo mode aktif. Isi Supabase env untuk multiplayer online.");
      enterMatch(demoMatch);
      return;
    }

    try {
      setStatus(`Joining ${GAME_MODES[mode].label} queue...`);
      const response = await joinMatchmaking(normalizedUsername, mode);
      if (response.status === "matched") {
        enterMatch(response.match);
      } else {
        setQueueSize(response.queue_size);
        setScreen("matchmaking");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal masuk matchmaking.");
    }
  }

  async function pollMatchmaking() {
    try {
      const response = await joinMatchmaking(username.trim(), mode);
      if (response.status === "matched") {
        enterMatch(response.match);
      } else {
        setQueueSize(response.queue_size);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Polling matchmaking gagal.");
    }
  }

  async function handleCancelQueue() {
    if (remoteEnabled && username) {
      await leaveMatchmaking(username).catch(() => undefined);
    }
    setScreen("login");
    setStatus("Queue canceled.");
  }

  function enterMatch(nextMatch: MatchPayload) {
    setMatch({ ...nextMatch, state: nextMatch.state ?? "COUNTDOWN" });
    setTypedText("");
    setFinishBanner("Belum ada yang finish.");
    setRematchReady({ ready: 0, needed: 2, waitingFor: [] });
    setScreen("arena");
    setStatus(`Room ${nextMatch.room_id} ready.`);
    channel.send("MATCH_FOUND", nextMatch);
  }

  function startMatch() {
    const now = Date.now();
    setStartedAt(now);
    setMatch((current) => {
      if (!current || current.state !== "COUNTDOWN") return current;
      const next = { ...current, state: "RUNNING" as const, started_at: new Date(now).toISOString() };
      channel.send("MATCH_START", next);
      if (remoteEnabled) {
        void updateMatchState(next.room_id, "MATCH_START", { started_at: next.started_at }).catch(() => undefined);
      }
      return next;
    });
    setStatus("Match running.");
  }

  function handleTyping(value: string) {
    setTypedText(value);
    if (!match || match.state !== "RUNNING" || startedAt === null) return;
    const elapsed = (Date.now() - startedAt) / 1000;
    const metrics = computeMetrics(match.target_text, value, elapsed);
    const nextPlayers = match.players.map((player) =>
      player.username === username
        ? {
            ...player,
            ...metrics,
            finish_time: metrics.finished && !player.finish_time ? Number(elapsed.toFixed(3)) : player.finish_time,
          }
        : player,
    );
    const firstFinished = match.first_finished ?? nextPlayers.find((player) => player.finished)?.username ?? null;
    if (metrics.finished) {
      setFinishBanner("Kamu finish. Menunggu lawan atau hasil akhir.");
    }

    const nextMatch = { ...match, players: nextPlayers, first_finished: firstFinished };
    setMatch(nextMatch);

    if (remoteEnabled && Date.now() - lastSubmitAt.current > 80) {
      lastSubmitAt.current = Date.now();
      void submitInput(match.room_id, username, value)
        .then(({ match: updatedMatch }) => {
          setMatch(updatedMatch);
          channel.send("STATE_UPDATE", updatedMatch);
          if (updatedMatch.state === "FINISHED") setScreen("results");
        })
        .catch((err) => setError(err instanceof Error ? err.message : "Submit input gagal."));
    } else if (!remoteEnabled && nextPlayers.every((player) => player.finished)) {
      const rankings = finishMatch(nextPlayers);
      setMatch({
        ...nextMatch,
        state: "FINISHED",
        rankings,
        winner: rankings[0]?.username ?? null,
        reason: "all players finished",
      });
      setScreen("results");
    }
  }

  function handleBroadcast(event: BroadcastEvent, payload: unknown) {
    const next = payload as MatchPayload & {
      username?: string;
      ready_count?: number;
      needed_count?: number;
      waiting_for?: string[];
    };
    if (event === "MATCH_START" || event === "STATE_UPDATE" || event === "MATCH_FINISH") {
      setMatch(next);
      if (next.state === "RUNNING" && !startedAt) setStartedAt(Date.now());
      if (next.state === "FINISHED") setScreen("results");
    }
    if (event === "PLAYER_FINISHED" && next.username) {
      setFinishBanner(next.username === username ? "Kamu finish duluan." : `${next.username} finish duluan.`);
    }
    if (event === "REMATCH_WAITING") {
      setRematchReady({
        ready: next.ready_count ?? 0,
        needed: next.needed_count ?? 2,
        waitingFor: next.waiting_for ?? [],
      });
    }
  }

  function handleRematch() {
    if (!match) return;
    setRematchReady((current) => ({ ...current, ready: Math.max(current.ready, 1) }));
    channel.send("REMATCH_WAITING", {
      room_id: match.room_id,
      ready_count: 1,
      needed_count: 2,
      waiting_for: ["opponent"],
    });

    if (!remoteEnabled) {
      enterMatch(createDemoMatch(username, match.mode));
    } else {
      void updateMatchState(match.room_id, "REMATCH_REQUEST", { username })
        .then((response) => {
          if (response.ready_count !== undefined) {
            setRematchReady({
              ready: response.ready_count,
              needed: response.needed_count ?? match.players.length,
              waitingFor: response.waiting_for ?? [],
            });
          }
          if (response.match.room_id !== match.room_id) {
            enterMatch(response.match);
            channel.send("MATCH_FOUND", response.match);
          }
        })
        .catch((err) => setError(err instanceof Error ? err.message : "Rematch gagal."));
    }
  }

  const myPlayer = match?.players.find((player) => player.username === username) ?? match?.players[0] ?? null;
  const opponent = match?.players.find((player) => player.username !== username) ?? match?.players[1] ?? null;

  return (
    <main className="min-h-screen overflow-hidden bg-space text-armor">
      <div className="fixed inset-0 -z-10 bg-[radial-gradient(circle_at_18%_15%,rgba(59,130,246,0.25),transparent_28%),radial-gradient(circle_at_80%_20%,rgba(234,179,8,0.18),transparent_24%),linear-gradient(135deg,#0A0E1A_0%,#111827_48%,#05070D_100%)]" />
      <div className="fixed inset-0 -z-10 opacity-30 hud-grid" />

      <section className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-5 md:px-8">
        <Header remoteEnabled={remoteEnabled} status={status} />

        {error && (
          <div className="mb-4 border-l-4 border-zeon bg-red-950/70 px-4 py-3 text-sm text-red-100 shadow-warning">
            {error}
          </div>
        )}

        {screen === "login" && (
          <LoginPanel
            username={username}
            setUsername={setUsername}
            mode={mode}
            setMode={setMode}
            onJoin={handleJoin}
            remoteEnabled={remoteEnabled}
          />
        )}

        {screen === "matchmaking" && (
          <MatchmakingPanel
            mode={mode}
            queueSize={queueSize}
            onCancel={handleCancelQueue}
          />
        )}

        {screen === "arena" && match && (
          <ArenaPanel
            match={match}
            countdown={countdown}
            typedText={typedText}
            onTyping={handleTyping}
            myPlayer={myPlayer}
            opponent={opponent}
            finishBanner={finishBanner}
          />
        )}

        {screen === "results" && match && (
          <ResultsPanel
            match={match}
            username={username}
            rematchReady={rematchReady}
            onRematch={handleRematch}
            onNewOpponent={() => void handleJoin()}
            onReturn={() => setScreen("login")}
          />
        )}
      </section>
    </main>
  );
}

function Header({ remoteEnabled, status }: { remoteEnabled: boolean; status: string }) {
  return (
    <header className="mb-5 grid gap-4 border border-white/10 bg-white/5 p-4 backdrop-blur md:grid-cols-[1fr_auto]">
      <div>
        <div className="flex items-center gap-3 text-vfin">
          <Shield className="h-7 w-7" />
          <h1 className="font-display text-3xl font-black uppercase tracking-[0.12em] md:text-5xl">
            Jempol Turbo
          </h1>
        </div>
        <p className="mt-1 max-w-2xl text-sm text-blue-100/75">
          Browser typing battle dengan Supabase Realtime, mode cc, rematch, dan HUD cockpit.
        </p>
      </div>
      <div className="grid gap-2 text-sm md:min-w-72">
        <StatusPill icon={<SatelliteDish className="h-4 w-4" />} label={remoteEnabled ? "Supabase online" : "Demo local"} />
        <StatusPill icon={<Radio className="h-4 w-4" />} label={status} muted />
      </div>
    </header>
  );
}

function StatusPill({ icon, label, muted = false }: { icon: ReactNode; label: string; muted?: boolean }) {
  return (
    <div className={`flex items-center gap-2 border px-3 py-2 ${muted ? "border-white/10 bg-white/5" : "border-beam/40 bg-beam/10"}`}>
      {icon}
      <span>{label}</span>
    </div>
  );
}

function LoginPanel({
  username,
  setUsername,
  mode,
  setMode,
  onJoin,
  remoteEnabled,
}: {
  username: string;
  setUsername: (value: string) => void;
  mode: ModeId;
  setMode: (mode: ModeId) => void;
  onJoin: (event: FormEvent) => void;
  remoteEnabled: boolean;
}) {
  return (
    <form onSubmit={onJoin} className="grid flex-1 gap-5 lg:grid-cols-[0.9fr_1.1fr]">
      <section className="panel-bright p-6 text-space">
        <div className="mb-8 flex items-center gap-3 text-gundam">
          <Swords className="h-6 w-6" />
          <h2 className="font-display text-3xl font-black uppercase">Sortie Setup</h2>
        </div>
        <label className="text-xs font-bold uppercase tracking-[0.2em] text-gunmetal">Pilot username</label>
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          className="mt-2 w-full border-2 border-gunmetal/20 bg-white px-4 py-3 font-display text-xl font-bold outline-none transition focus:border-gundam"
          placeholder="contoh: Naufal"
          maxLength={24}
        />
        <button className="mt-7 flex w-full items-center justify-center gap-2 bg-gundam px-5 py-4 font-display text-lg font-black uppercase tracking-[0.16em] text-white shadow-beam transition hover:bg-beam">
          <Send className="h-5 w-5" />
          Join Matchmaking
        </button>
        <p className="mt-4 text-sm text-gunmetal">
          {remoteEnabled
            ? "Mode online aktif. Player akan dipasangkan melalui Supabase."
            : "Env Supabase belum diisi, jadi app berjalan dalam demo mode agar UI tetap bisa diuji."}
        </p>
      </section>

      <section className="grid gap-4">
        {(Object.keys(GAME_MODES) as ModeId[]).map((modeId) => (
          <button
            type="button"
            key={modeId}
            onClick={() => setMode(modeId)}
            className={`group border p-5 text-left transition ${
              mode === modeId
                ? "border-vfin bg-vfin/15 shadow-warning"
                : "border-white/10 bg-white/5 hover:border-beam/60 hover:bg-beam/10"
            }`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="font-display text-2xl font-black uppercase">{GAME_MODES[modeId].label}</h3>
                <p className="mt-1 text-blue-100/70">{GAME_MODES[modeId].description}</p>
              </div>
              <div
                className="h-12 w-2"
                style={{ backgroundColor: GAME_MODES[modeId].accent }}
              />
            </div>
            <div className="mt-4 flex items-center gap-3 text-sm text-blue-100/80">
              <Gauge className="h-4 w-4" />
              {GAME_MODES[modeId].minWords}-{GAME_MODES[modeId].maxWords} kata
            </div>
          </button>
        ))}
      </section>
    </form>
  );
}

function MatchmakingPanel({ mode, queueSize, onCancel }: { mode: ModeId; queueSize: number; onCancel: () => void }) {
  return (
    <section className="panel-dark mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center p-10 text-center">
      <LoaderCircle className="h-16 w-16 animate-spin text-vfin" />
      <h2 className="mt-6 font-display text-4xl font-black uppercase">Standing By</h2>
      <p className="mt-3 text-blue-100/75">
        Queue {GAME_MODES[mode].label}. Menunggu pilot kedua dengan mode yang sama.
      </p>
      <div className="mt-6 border border-vfin/40 bg-vfin/10 px-6 py-3 font-display text-2xl font-bold text-vfin">
        Queue size: {queueSize}
      </div>
      <button onClick={onCancel} className="mt-8 border border-white/20 px-5 py-3 font-bold uppercase text-blue-100 hover:bg-white/10">
        Cancel Sortie
      </button>
    </section>
  );
}

function ArenaPanel({
  match,
  countdown,
  typedText,
  onTyping,
  myPlayer,
  opponent,
  finishBanner,
}: {
  match: MatchPayload;
  countdown: number;
  typedText: string;
  onTyping: (value: string) => void;
  myPlayer: PlayerSnapshot | null;
  opponent: PlayerSnapshot | null;
  finishBanner: string;
}) {
  const isRunning = match.state === "RUNNING";
  return (
    <section className="grid flex-1 gap-4">
      <div className="grid gap-4 md:grid-cols-4">
        <HudStat icon={<Activity />} label="State" value={match.state === "COUNTDOWN" ? `${countdown}` : match.state} accent="text-vfin" />
        <HudStat icon={<Wifi />} label="Latency" value={`${myPlayer?.latency_ms ?? "-"} ms`} accent="text-beam" />
        <HudStat icon={<Gauge />} label="Mode" value={match.mode_label} accent="text-armor" />
        <HudStat icon={<Trophy />} label="Words" value={`${match.word_count}`} accent="text-vfin" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1fr_0.8fr]">
        <section className="panel-bright p-5 text-space">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-display text-2xl font-black uppercase text-gundam">Target Text</h2>
            <span className="bg-gundam px-3 py-1 text-xs font-bold uppercase text-white">Authoritative Sync</span>
          </div>
          <p className="target-text">{match.target_text}</p>
        </section>

        <section className="panel-dark p-5">
          <h2 className="font-display text-2xl font-black uppercase text-vfin">Pilot Telemetry</h2>
          <div className="mt-4 grid gap-4">
            <PlayerBar label="You" player={myPlayer} color="bg-gundam" />
            <PlayerBar label="Opponent" player={opponent} color="bg-zeon" />
          </div>
        </section>
      </div>

      <div className="border border-vfin/40 bg-vfin/10 px-4 py-3 font-display text-lg font-bold uppercase text-vfin">
        {finishBanner}
      </div>

      <textarea
        value={typedText}
        onChange={(event) => onTyping(event.target.value)}
        disabled={!isRunning}
        className="min-h-52 w-full border-2 border-beam/40 bg-slate-950/90 p-5 font-mono text-xl leading-relaxed text-armor outline-none transition focus:border-vfin disabled:cursor-not-allowed disabled:opacity-55"
        placeholder={isRunning ? "Ketik target text di sini..." : "Menunggu countdown..."}
      />
    </section>
  );
}

function HudStat({ icon, label, value, accent }: { icon: ReactNode; label: string; value: string; accent: string }) {
  return (
    <div className="panel-dark flex items-center gap-3 p-4">
      <div className={accent}>{icon}</div>
      <div>
        <div className="text-xs font-bold uppercase tracking-[0.2em] text-blue-100/55">{label}</div>
        <div className={`font-display text-2xl font-black ${accent}`}>{value}</div>
      </div>
    </div>
  );
}

function PlayerBar({ label, player, color }: { label: string; player: PlayerSnapshot | null; color: string }) {
  const progress = Math.round((player?.progress ?? 0) * 100);
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-4">
        <span className="font-display text-lg font-bold uppercase">{label}: {player?.username ?? "-"}</span>
        <span className="text-sm text-blue-100/70">{player?.wpm ?? 0} WPM / {player?.accuracy ?? 0}%</span>
      </div>
      <div className="h-4 border border-white/10 bg-black/40">
        <div className={`h-full ${color} transition-all duration-300`} style={{ width: `${progress}%` }} />
      </div>
      <div className="mt-1 text-sm text-blue-100/65">Score {player?.score ?? 0} / Progress {progress}%</div>
    </div>
  );
}

function ResultsPanel({
  match,
  username,
  rematchReady,
  onRematch,
  onNewOpponent,
  onReturn,
}: {
  match: MatchPayload;
  username: string;
  rematchReady: { ready: number; needed: number; waitingFor: string[] };
  onRematch: () => void;
  onNewOpponent: () => void;
  onReturn: () => void;
}) {
  const rankings = match.rankings ?? finishMatch(match.players);
  const winner = match.winner ?? rankings[0]?.username ?? "-";
  const victory = winner === username;
  return (
    <section className="panel-bright flex-1 p-6 text-space">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className={`font-display text-5xl font-black uppercase ${victory ? "text-vfin" : "text-zeon"}`}>
            {victory ? "Victory" : "Defeated"}
          </h2>
          <p className="mt-2 text-gunmetal">Winner: {winner} / Reason: {match.reason ?? "match finished"}</p>
        </div>
        <div className="text-right font-display text-xl font-bold text-gundam">{match.mode_label}</div>
      </div>

      <div className="mt-7 overflow-x-auto">
        <table className="w-full min-w-[680px] border-collapse text-left">
          <thead>
            <tr className="bg-space text-armor">
              {["Rank", "Username", "WPM", "Accuracy", "Score", "Finish"].map((heading) => (
                <th key={heading} className="px-4 py-3 text-sm uppercase tracking-[0.16em]">{heading}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rankings.map((player, index) => (
              <tr key={player.username} className="border-b border-slate-200">
                <td className="px-4 py-4 font-display text-xl font-black">{player.rank ?? index + 1}</td>
                <td className="px-4 py-4 font-bold">{player.username}</td>
                <td className="px-4 py-4">{player.wpm}</td>
                <td className="px-4 py-4">{player.accuracy}%</td>
                <td className="px-4 py-4">{player.score}</td>
                <td className="px-4 py-4">{player.finish_time ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-7 flex flex-wrap gap-3">
        <button onClick={onRematch} className="flex items-center gap-2 bg-zeon px-5 py-3 font-bold uppercase text-white">
          <RotateCcw className="h-4 w-4" />
          Rematch
        </button>
        <button onClick={onNewOpponent} className="bg-gundam px-5 py-3 font-bold uppercase text-white">
          Find New Opponent
        </button>
        <button onClick={onReturn} className="border border-gunmetal/30 px-5 py-3 font-bold uppercase text-gunmetal">
          Return to Base
        </button>
      </div>
      {rematchReady.ready > 0 && (
        <p className="mt-4 text-sm text-gunmetal">
          Rematch ready {rematchReady.ready}/{rematchReady.needed}. Waiting for {rematchReady.waitingFor.join(", ") || "opponent"}.
        </p>
      )}
    </section>
  );
}

export default App;
