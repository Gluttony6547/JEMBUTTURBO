"""Authoritative TCP server for Jempol Turbo."""

from __future__ import annotations

import argparse
import logging
import selectors
import socket
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jempol_turbo.protocol import (
    MAX_PACKET_BYTES,
    PacketBuffer,
    ProtocolError,
    encode_packet,
    get_payload_string,
    validate_client_packet,
)
from jempol_turbo.scoring import compute_metrics, ranking_key
from jempol_turbo.texts import (
    DEFAULT_MODE,
    GAME_MODES,
    count_words,
    generate_target_text,
    mode_payload,
    normalize_mode,
)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5050
COUNTDOWN_SECONDS = 3.0
MATCH_DURATION_LIMIT = 120.0
STATE_BROADCAST_INTERVAL = 0.2
PING_INTERVAL = 2.0
RECONNECT_WINDOW = 30.0


@dataclass
class ClientConnection:
    sock: socket.socket
    address: tuple[str, int]
    buffer: PacketBuffer = field(default_factory=PacketBuffer)
    outgoing: bytearray = field(default_factory=bytearray)
    session_token: str | None = None
    closed: bool = False


@dataclass
class PlayerSession:
    username: str
    token: str
    conn: ClientConnection | None = None
    room_id: str | None = None
    connected: bool = True
    last_seen: float = field(default_factory=time.monotonic)
    disconnected_at: float | None = None
    latency_ms: float | None = None
    last_ping_id: str | None = None
    last_ping_sent_at: float = 0.0
    last_client_seq: int = -1
    typed_text: str = ""
    typed_chars: int = 0
    correct_chars: int = 0
    progress: float = 0.0
    accuracy: float = 0.0
    wpm: float = 0.0
    score: int = 0
    finished: bool = False
    finish_time: float | None = None
    invalid_packets: int = 0
    selected_mode: str = DEFAULT_MODE

    def reset_for_match(self) -> None:
        self.typed_text = ""
        self.typed_chars = 0
        self.correct_chars = 0
        self.progress = 0.0
        self.accuracy = 0.0
        self.wpm = 0.0
        self.score = 0
        self.finished = False
        self.finish_time = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "connected": self.connected,
            "typed_chars": self.typed_chars,
            "correct_chars": self.correct_chars,
            "progress": self.progress,
            "accuracy": self.accuracy,
            "wpm": self.wpm,
            "score": self.score,
            "finished": self.finished,
            "finish_time": self.finish_time,
            "latency_ms": self.latency_ms,
        }


@dataclass
class Room:
    room_id: str
    player_tokens: list[str]
    mode: str
    target_text: str
    state: str = "COUNTDOWN"
    created_at: float = field(default_factory=time.monotonic)
    countdown_until: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None
    last_state_broadcast_at: float = 0.0
    last_countdown_broadcast_at: float = 0.0
    rematch_requests: set[str] = field(default_factory=set)
    first_finished_token: str | None = None


class JempolTurboServer:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self.selector = selectors.DefaultSelector()
        self.server_sock: socket.socket | None = None
        self.sessions: dict[str, PlayerSession] = {}
        self.matchmaking_queues: dict[str, list[str]] = {mode: [] for mode in GAME_MODES}
        self.rooms: dict[str, Room] = {}
        self.server_seq = 0
        self.running = False
        self._shutdown_complete = False

    def start(self) -> None:
        self._shutdown_complete = False
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen()
        self.server_sock.setblocking(False)
        self.selector.register(self.server_sock, selectors.EVENT_READ, data=None)
        self.running = True
        logging.info("server listening on %s:%s", self.host, self.port)

    def serve_forever(self) -> None:
        if not self.running:
            self.start()
        try:
            while self.running:
                for key, mask in self.selector.select(timeout=0.1):
                    if key.data is None:
                        self._accept_client()
                    else:
                        conn: ClientConnection = key.data
                        if mask & selectors.EVENT_READ:
                            self._read_client(conn)
                        if mask & selectors.EVENT_WRITE:
                            self._write_client(conn)
                self._tick()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if self._shutdown_complete:
            return
        self.running = False
        try:
            selector_keys = list(self.selector.get_map().values())
        except Exception:
            selector_keys = []
        for key in selector_keys:
            if key.data is not None:
                self._close_connection(key.data, mark_disconnect=False)
        if self.server_sock is not None:
            try:
                self.selector.unregister(self.server_sock)
            except Exception:
                pass
            self.server_sock.close()
            self.server_sock = None
        try:
            self.selector.close()
        except Exception:
            pass
        self._shutdown_complete = True
        logging.info("server stopped")

    def _accept_client(self) -> None:
        assert self.server_sock is not None
        sock, address = self.server_sock.accept()
        sock.setblocking(False)
        conn = ClientConnection(sock=sock, address=address)
        self.selector.register(sock, selectors.EVENT_READ, data=conn)
        logging.info("connection accepted from %s:%s", *address)

    def _read_client(self, conn: ClientConnection) -> None:
        if conn.closed:
            return
        try:
            data = conn.sock.recv(4096)
        except ConnectionResetError:
            self._close_connection(conn)
            return
        except OSError as exc:
            logging.warning("read failed from %s: %s", conn.address, exc)
            self._close_connection(conn)
            return

        if not data:
            self._close_connection(conn)
            return

        try:
            packets = conn.buffer.feed(data)
        except ProtocolError as exc:
            self._record_invalid(conn, str(exc))
            if len(data) > MAX_PACKET_BYTES:
                self._close_connection(conn)
            return

        for packet in packets:
            self._handle_packet(conn, packet)

    def _write_client(self, conn: ClientConnection) -> None:
        if conn.closed or not conn.outgoing:
            self._refresh_selector_events(conn)
            return
        try:
            sent = conn.sock.send(conn.outgoing)
            del conn.outgoing[:sent]
        except (ConnectionResetError, BrokenPipeError, OSError):
            self._close_connection(conn)
            return
        self._refresh_selector_events(conn)

    def _handle_packet(self, conn: ClientConnection, packet: dict[str, Any]) -> None:
        try:
            validate_client_packet(packet)
        except ProtocolError as exc:
            self._record_invalid(conn, str(exc))
            return

        packet_type = packet["type"]
        try:
            if packet_type == "HELLO":
                self._handle_hello(conn, packet)
            elif packet_type == "RECONNECT":
                self._handle_reconnect(conn, packet)
            else:
                session = self._get_authenticated_session(conn, packet)
                self._check_sequence(session, packet)
                if packet_type == "JOIN_MATCHMAKING":
                    self._handle_join_matchmaking(session, packet)
                elif packet_type == "INPUT_UPDATE":
                    self._handle_input_update(session, packet)
                elif packet_type == "PONG":
                    self._handle_pong(session, packet)
                elif packet_type == "LEAVE_ROOM":
                    self._handle_leave_room(session)
                elif packet_type == "REMATCH_REQUEST":
                    self._handle_rematch_request(session)
        except ProtocolError as exc:
            self._record_invalid(conn, str(exc))

    def _handle_hello(self, conn: ClientConnection, packet: dict[str, Any]) -> None:
        if conn.session_token:
            raise ProtocolError("connection already authenticated")
        username = get_payload_string(packet, "username", max_length=24).strip()
        if any(s.username == username and s.connected for s in self.sessions.values()):
            raise ProtocolError("username is already online")

        token = uuid.uuid4().hex
        session = PlayerSession(username=username, token=token, conn=conn)
        self.sessions[token] = session
        conn.session_token = token
        self._send(
            conn,
            "WELCOME",
            {
                "username": username,
                "session_token": token,
                "reconnected": False,
                "reconnect_window_seconds": RECONNECT_WINDOW,
            },
        )
        logging.info("player login username=%s token=%s", username, token[:8])

    def _handle_reconnect(self, conn: ClientConnection, packet: dict[str, Any]) -> None:
        token = packet.get("session_token") or packet.get("payload", {}).get("session_token")
        if not isinstance(token, str) or token not in self.sessions:
            raise ProtocolError("unknown session token")
        session = self.sessions[token]
        now = time.monotonic()
        if session.connected:
            raise ProtocolError("session is already connected")
        if session.disconnected_at and now - session.disconnected_at > RECONNECT_WINDOW:
            raise ProtocolError("reconnect window expired")

        session.conn = conn
        session.connected = True
        session.disconnected_at = None
        session.last_seen = now
        conn.session_token = token
        self._send(
            conn,
            "WELCOME",
            {
                "username": session.username,
                "session_token": token,
                "reconnected": True,
                "reconnect_window_seconds": RECONNECT_WINDOW,
            },
        )
        logging.info("player reconnect username=%s token=%s", session.username, token[:8])

        if session.room_id and session.room_id in self.rooms:
            room = self.rooms[session.room_id]
            self._send(
                conn,
                "MATCH_FOUND",
                {
                    "room_id": room.room_id,
                    **mode_payload(room.mode),
                    "target_text": room.target_text,
                    "word_count": count_words(room.target_text),
                    "players": self._room_players(room),
                },
            )
            self._broadcast_state(room)

    def _get_authenticated_session(
        self,
        conn: ClientConnection,
        packet: dict[str, Any],
    ) -> PlayerSession:
        token = packet.get("session_token")
        if not isinstance(token, str) or token not in self.sessions:
            raise ProtocolError("unknown session token")
        session = self.sessions[token]
        if session.conn is not conn:
            raise ProtocolError("session token does not belong to this connection")
        session.last_seen = time.monotonic()
        return session

    def _check_sequence(self, session: PlayerSession, packet: dict[str, Any]) -> None:
        seq = int(packet["seq"])
        if seq < session.last_client_seq:
            raise ProtocolError("seq must not move backwards")
        session.last_client_seq = seq

    def _handle_join_matchmaking(self, session: PlayerSession, packet: dict[str, Any]) -> None:
        if session.room_id:
            room = self.rooms.get(session.room_id)
            if room and room.state != "FINISHED":
                raise ProtocolError("player is already in an active room")
            session.room_id = None

        payload = packet.get("payload", {})
        mode = normalize_mode(payload.get("mode") if isinstance(payload, dict) else None)
        session.selected_mode = mode

        self._remove_from_all_queues(session.token)
        queue = self.matchmaking_queues[mode]
        if session.token not in queue:
            queue.append(session.token)
        self._send_to_session(
            session,
            "QUEUED",
            {"queue_size": len(queue), **mode_payload(mode)},
        )
        logging.info(
            "player queued username=%s mode=%s queue_size=%s",
            session.username,
            mode,
            len(queue),
        )
        self._try_create_matches(mode)

    def _try_create_matches(self, mode: str) -> None:
        queue = self.matchmaking_queues[mode]
        while len(queue) >= 2:
            selected: list[str] = []
            while queue and len(selected) < 2:
                token = queue.pop(0)
                session = self.sessions.get(token)
                if session and session.connected and session.room_id is None:
                    selected.append(token)
            if len(selected) < 2:
                for token in reversed(selected):
                    queue.insert(0, token)
                return

            self._create_room(selected, mode, source="matchmaking")

    def _create_room(self, selected: list[str], mode: str, *, source: str) -> Room:
        room_id = uuid.uuid4().hex[:8]
        target_text = generate_target_text(mode)
        room = Room(
            room_id=room_id,
            player_tokens=selected,
            mode=mode,
            target_text=target_text,
            countdown_until=time.monotonic() + COUNTDOWN_SECONDS,
        )
        self.rooms[room_id] = room
        for token in selected:
            session = self.sessions[token]
            session.room_id = room_id
            session.selected_mode = mode
            session.reset_for_match()

        payload = {
            "room_id": room_id,
            **mode_payload(mode),
            "target_text": target_text,
            "word_count": count_words(target_text),
            "players": self._room_players(room),
            "countdown_seconds": COUNTDOWN_SECONDS,
        }
        self._broadcast(room, "MATCH_FOUND", payload)
        logging.info(
            "room created room=%s mode=%s source=%s players=%s",
            room_id,
            mode,
            source,
            ",".join(self.sessions[t].username for t in selected),
        )
        return room

    def _handle_input_update(self, session: PlayerSession, packet: dict[str, Any]) -> None:
        if not session.room_id or session.room_id not in self.rooms:
            raise ProtocolError("player is not in a room")
        room = self.rooms[session.room_id]
        if room.state == "FINISHED":
            return
        if room.state != "RUNNING" or room.started_at is None:
            raise ProtocolError("match is not running")
        if session.finished:
            return

        typed_text = get_payload_string(
            packet,
            "typed_text",
            required=False,
            max_length=len(room.target_text) + 24,
        )
        typed_text = typed_text[: len(room.target_text)]
        elapsed = time.monotonic() - room.started_at
        metrics = compute_metrics(room.target_text, typed_text, elapsed)

        session.typed_text = typed_text
        session.typed_chars = metrics.typed_chars
        session.correct_chars = metrics.correct_chars
        session.progress = metrics.progress
        session.accuracy = metrics.accuracy
        session.wpm = metrics.wpm
        session.score = metrics.score
        if metrics.finished and not session.finished:
            session.finished = True
            session.finish_time = round(elapsed, 3)
            if room.first_finished_token is None:
                room.first_finished_token = session.token
                self._broadcast(
                    room,
                    "PLAYER_FINISHED",
                    {
                        "room_id": room.room_id,
                        "username": session.username,
                        "finish_time": session.finish_time,
                        "first": True,
                    },
                )
            logging.info(
                "player finished username=%s room=%s finish_time=%.3f wpm=%.2f accuracy=%.2f",
                session.username,
                room.room_id,
                elapsed,
                session.wpm,
                session.accuracy,
            )

        self._broadcast_state(room)
        if all(self.sessions[token].finished for token in room.player_tokens):
            self._finish_room(room, reason="all players finished")

    def _handle_pong(self, session: PlayerSession, packet: dict[str, Any]) -> None:
        ping_id = packet.get("payload", {}).get("ping_id")
        now = time.monotonic()
        if ping_id == session.last_ping_id and session.last_ping_sent_at:
            session.latency_ms = round((now - session.last_ping_sent_at) * 1000.0, 2)

    def _handle_leave_room(self, session: PlayerSession) -> None:
        self._remove_from_all_queues(session.token)
        if session.room_id and session.room_id in self.rooms:
            room = self.rooms[session.room_id]
            if room.state != "FINISHED":
                self._finish_room(room, reason=f"{session.username} left")
        session.room_id = None
        self._send_to_session(session, "INFO", {"message": "left room"})

    def _handle_rematch_request(self, session: PlayerSession) -> None:
        if not session.room_id or session.room_id not in self.rooms:
            raise ProtocolError("player is not in a room")
        room = self.rooms[session.room_id]
        if room.state != "FINISHED":
            raise ProtocolError("rematch is only available after match finish")
        if session.token not in room.player_tokens:
            raise ProtocolError("player is not part of this room")

        room.rematch_requests.add(session.token)
        waiting_for = [
            self.sessions[token].username
            for token in room.player_tokens
            if token not in room.rematch_requests
        ]
        self._broadcast(
            room,
            "REMATCH_WAITING",
            {
                "room_id": room.room_id,
                **mode_payload(room.mode),
                "requested_by": session.username,
                "ready_count": len(room.rematch_requests),
                "needed_count": len(room.player_tokens),
                "waiting_for": waiting_for,
            },
        )
        logging.info(
            "rematch requested room=%s username=%s ready=%s/%s",
            room.room_id,
            session.username,
            len(room.rematch_requests),
            len(room.player_tokens),
        )
        if len(room.rematch_requests) == len(room.player_tokens):
            self._create_room(list(room.player_tokens), room.mode, source="rematch")

    def _tick(self) -> None:
        now = time.monotonic()
        self._send_periodic_pings(now)
        self._expire_disconnected_sessions(now)

        for room in list(self.rooms.values()):
            if room.state == "COUNTDOWN":
                if now - room.last_countdown_broadcast_at >= 0.5:
                    room.last_countdown_broadcast_at = now
                    self._broadcast(
                        room,
                        "COUNTDOWN",
                        {
                            "room_id": room.room_id,
                            **mode_payload(room.mode),
                            "remaining": max(0.0, round(room.countdown_until - now, 2)),
                        },
                    )
                if now >= room.countdown_until:
                    room.state = "RUNNING"
                    room.started_at = now
                    logging.info("match started room=%s", room.room_id)
                    self._broadcast(
                        room,
                        "MATCH_START",
                        {
                            "room_id": room.room_id,
                            **mode_payload(room.mode),
                            "target_text": room.target_text,
                            "word_count": count_words(room.target_text),
                            "duration_limit": MATCH_DURATION_LIMIT,
                        },
                    )
                    self._broadcast_state(room)
            elif room.state == "RUNNING":
                if room.started_at and now - room.started_at >= MATCH_DURATION_LIMIT:
                    self._finish_room(room, reason="duration limit reached")
                elif now - room.last_state_broadcast_at >= STATE_BROADCAST_INTERVAL:
                    self._broadcast_state(room)

    def _send_periodic_pings(self, now: float) -> None:
        for session in self.sessions.values():
            if not session.connected or session.conn is None:
                continue
            if now - session.last_ping_sent_at < PING_INTERVAL:
                continue
            ping_id = uuid.uuid4().hex[:10]
            session.last_ping_id = ping_id
            session.last_ping_sent_at = now
            self._send_to_session(
                session,
                "PING",
                {"ping_id": ping_id, "server_time": now},
            )

    def _expire_disconnected_sessions(self, now: float) -> None:
        for session in list(self.sessions.values()):
            if session.connected or session.disconnected_at is None:
                continue
            if now - session.disconnected_at <= RECONNECT_WINDOW:
                continue
            self._remove_from_all_queues(session.token)
            if session.room_id and session.room_id in self.rooms:
                room = self.rooms[session.room_id]
                if room.state != "FINISHED":
                    self._finish_room(room, reason=f"{session.username} reconnect timeout")
            logging.info("session expired username=%s token=%s", session.username, session.token[:8])

    def _broadcast_state(self, room: Room) -> None:
        now = time.monotonic()
        room.last_state_broadcast_at = now
        elapsed = 0.0
        if room.started_at:
            elapsed = max(0.0, now - room.started_at)
        payload = {
            "room_id": room.room_id,
            **mode_payload(room.mode),
            "state": room.state,
            "target_text": room.target_text,
            "word_count": count_words(room.target_text),
            "elapsed": round(elapsed, 2),
            "duration_limit": MATCH_DURATION_LIMIT,
            "first_finished": self.sessions[room.first_finished_token].username
            if room.first_finished_token
            else None,
            "players": self._room_players(room),
        }
        self._broadcast(room, "STATE_UPDATE", payload)

    def _finish_room(self, room: Room, *, reason: str) -> None:
        if room.state == "FINISHED":
            return
        room.state = "FINISHED"
        room.finished_at = time.monotonic()

        ranked_sessions = sorted(
            [self.sessions[token] for token in room.player_tokens],
            key=lambda session: ranking_key(session.snapshot()),
            reverse=True,
        )
        rankings = []
        for index, session in enumerate(ranked_sessions, start=1):
            snapshot = session.snapshot()
            snapshot["rank"] = index
            rankings.append(snapshot)

        payload = {
            "room_id": room.room_id,
            **mode_payload(room.mode),
            "reason": reason,
            "target_text": room.target_text,
            "word_count": count_words(room.target_text),
            "winner": rankings[0]["username"] if rankings else None,
            "rankings": rankings,
        }
        self._broadcast(room, "MATCH_FINISH", payload)
        logging.info("match finished room=%s reason=%s rankings=%s", room.room_id, reason, rankings)

    def _room_players(self, room: Room) -> list[dict[str, Any]]:
        return [self.sessions[token].snapshot() for token in room.player_tokens]

    def _broadcast(self, room: Room, packet_type: str, payload: dict[str, Any]) -> None:
        for token in room.player_tokens:
            session = self.sessions.get(token)
            if session:
                self._send_to_session(session, packet_type, payload)

    def _send_to_session(self, session: PlayerSession, packet_type: str, payload: dict[str, Any]) -> None:
        if session.conn is None or not session.connected:
            return
        self._send(session.conn, packet_type, payload)

    def _send(self, conn: ClientConnection, packet_type: str, payload: dict[str, Any]) -> None:
        if conn.closed:
            return
        try:
            conn.outgoing.extend(encode_packet(packet_type, seq=self.server_seq, payload=payload))
            self.server_seq += 1
            self._refresh_selector_events(conn)
        except ProtocolError as exc:
            logging.error("server attempted to send invalid packet: %s", exc)

    def _refresh_selector_events(self, conn: ClientConnection) -> None:
        if conn.closed:
            return
        events = selectors.EVENT_READ
        if conn.outgoing:
            events |= selectors.EVENT_WRITE
        try:
            self.selector.modify(conn.sock, events, data=conn)
        except (KeyError, ValueError, OSError):
            pass

    def _record_invalid(self, conn: ClientConnection, reason: str) -> None:
        session = self.sessions.get(conn.session_token or "")
        username = session.username if session else "unknown"
        if session:
            session.invalid_packets += 1
        logging.warning(
            "invalid packet username=%s address=%s:%s reason=%s",
            username,
            conn.address[0],
            conn.address[1],
            reason,
        )
        self._send(conn, "ERROR", {"message": reason})

    def _close_connection(self, conn: ClientConnection, *, mark_disconnect: bool = True) -> None:
        if conn.closed:
            return
        conn.closed = True
        try:
            self.selector.unregister(conn.sock)
        except Exception:
            pass
        try:
            conn.sock.close()
        except OSError:
            pass

        if mark_disconnect and conn.session_token and conn.session_token in self.sessions:
            session = self.sessions[conn.session_token]
            if session.conn is conn:
                session.conn = None
                session.connected = False
                session.disconnected_at = time.monotonic()
                session.last_seen = session.disconnected_at
                logging.info(
                    "player disconnected username=%s token=%s reconnect_window=%.0fs",
                    session.username,
                    session.token[:8],
                    RECONNECT_WINDOW,
                )
                self._remove_from_all_queues(session.token)
                if session.room_id and session.room_id in self.rooms:
                    self._broadcast_state(self.rooms[session.room_id])

    def _remove_from_all_queues(self, token: str) -> None:
        for queue in self.matchmaking_queues.values():
            if token in queue:
                queue.remove(token)


def configure_logging() -> None:
    Path("logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/server.log", encoding="utf-8"),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Jempol Turbo TCP server.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    configure_logging()
    server = JempolTurboServer(args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("keyboard interrupt received")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
