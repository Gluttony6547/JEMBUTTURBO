"""Run simulated Jempol Turbo clients for demo and load testing."""

from __future__ import annotations

import argparse
import socket
import statistics
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from jempol_turbo.protocol import PacketBuffer, ProtocolError, encode_packet
from jempol_turbo.server import DEFAULT_HOST, DEFAULT_PORT
from jempol_turbo.texts import DEFAULT_MODE


@dataclass
class SimResult:
    username: str
    finished: bool = False
    rank: int | None = None
    score: int = 0
    wpm: float = 0.0
    accuracy: float = 0.0
    errors: list[str] = field(default_factory=list)
    latency_samples: list[float] = field(default_factory=list)
    duration_seconds: float = 0.0


class SimulatedClient:
    def __init__(self, username: str, host: str, port: int, speed_delay: float, mode: str) -> None:
        self.username = username
        self.host = host
        self.port = port
        self.speed_delay = speed_delay
        self.mode = mode
        self.sock: socket.socket | None = None
        self.buffer = PacketBuffer()
        self.seq = 0
        self.token = ""
        self.target_text = ""
        self.running = False
        self.typed_index = 0
        self.last_type_at = 0.0
        self.pending_pings: dict[str, float] = {}

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=5)
        self.sock.settimeout(0.2)
        self.send("HELLO", {"username": self.username}, include_token=False)

    def send(self, packet_type: str, payload: dict[str, Any], *, include_token: bool = True) -> None:
        assert self.sock is not None
        raw = encode_packet(
            packet_type,
            seq=self.seq,
            payload=payload,
            session_token=self.token if include_token else None,
        )
        self.seq += 1
        self.sock.sendall(raw)

    def recv_packets(self) -> list[dict[str, Any]]:
        assert self.sock is not None
        try:
            data = self.sock.recv(4096)
        except socket.timeout:
            return []
        if not data:
            raise ConnectionError("server closed connection")
        return self.buffer.feed(data)

    def run(self, timeout: float = 25.0) -> SimResult:
        result = SimResult(username=self.username)
        started_at = time.monotonic()
        try:
            self.connect()
            while time.monotonic() - started_at < timeout:
                for packet in self.recv_packets():
                    self.handle_packet(packet, result)
                    if result.finished:
                        result.duration_seconds = round(time.monotonic() - started_at, 3)
                        return result
                self.maybe_type()
            result.errors.append("timeout")
        except Exception as exc:
            result.errors.append(str(exc))
        finally:
            result.duration_seconds = round(time.monotonic() - started_at, 3)
            if self.sock is not None:
                try:
                    self.sock.close()
                except OSError:
                    pass
        return result

    def handle_packet(self, packet: dict[str, Any], result: SimResult) -> None:
        packet_type = packet.get("type")
        payload = packet.get("payload", {})
        if packet_type == "WELCOME":
            self.token = payload["session_token"]
            self.send("JOIN_MATCHMAKING", {"mode": self.mode})
        elif packet_type == "MATCH_FOUND":
            self.target_text = payload["target_text"]
        elif packet_type == "MATCH_START":
            self.running = True
            self.last_type_at = 0.0
        elif packet_type == "PING":
            ping_id = payload.get("ping_id")
            if isinstance(ping_id, str):
                self.pending_pings[ping_id] = time.monotonic()
                self.send("PONG", {"ping_id": ping_id})
        elif packet_type == "STATE_UPDATE":
            for player in payload.get("players", []):
                if player.get("username") == self.username and player.get("latency_ms") is not None:
                    result.latency_samples.append(float(player["latency_ms"]))
        elif packet_type == "MATCH_FINISH":
            for player in payload.get("rankings", []):
                if player.get("username") == self.username:
                    result.finished = True
                    result.rank = int(player.get("rank", 0))
                    result.score = int(player.get("score", 0))
                    result.wpm = float(player.get("wpm", 0.0))
                    result.accuracy = float(player.get("accuracy", 0.0))
        elif packet_type == "ERROR":
            result.errors.append(str(payload.get("message", "server error")))

    def maybe_type(self) -> None:
        if not self.running or not self.target_text:
            return
        now = time.monotonic()
        if now - self.last_type_at < self.speed_delay:
            return
        self.last_type_at = now
        self.typed_index = min(len(self.target_text), self.typed_index + 1)
        self.send("INPUT_UPDATE", {"typed_text": self.target_text[: self.typed_index]})


def run_one(username: str, host: str, port: int, speed_delay: float, mode: str, results: list[SimResult]) -> None:
    client = SimulatedClient(username, host, port, speed_delay, mode)
    results.append(client.run())


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate multiple Jempol Turbo clients.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--clients", type=int, default=10)
    parser.add_argument("--speed-delay", type=float, default=0.025)
    parser.add_argument("--mode", default=DEFAULT_MODE, choices=["1000cc", "2000cc", "turbo"])
    args = parser.parse_args()

    results: list[SimResult] = []
    threads = [
        threading.Thread(
            target=run_one,
            args=(f"bot-{index + 1}", args.host, args.port, args.speed_delay, args.mode, results),
            daemon=True,
        )
        for index in range(args.clients)
    ]

    started_at = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    finished = [result for result in results if result.finished]
    errors = [result for result in results if result.errors]
    latencies = [sample for result in results for sample in result.latency_samples]
    print(f"clients={args.clients} finished={len(finished)} errors={len(errors)} duration={time.monotonic() - started_at:.2f}s")
    if latencies:
        print(
            "latency_ms "
            f"min={min(latencies):.2f} "
            f"avg={statistics.mean(latencies):.2f} "
            f"max={max(latencies):.2f}"
        )
    for result in sorted(results, key=lambda item: item.username):
        status = "ok" if result.finished and not result.errors else "error"
        print(
            f"{status} {result.username} "
            f"rank={result.rank} score={result.score} "
            f"wpm={result.wpm:.2f} accuracy={result.accuracy:.2f} "
            f"errors={';'.join(result.errors) or '-'}"
        )


if __name__ == "__main__":
    main()
