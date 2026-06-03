"""JSON-line packet helpers for Jempol Turbo.

Every network message is one JSON object encoded as UTF-8 and terminated by
``\n``. This keeps packet framing explicit while still being easy to inspect
from the server log or a simple socket client during demo.
"""

from __future__ import annotations

import json
from typing import Any


MAX_PACKET_BYTES = 8192
MAX_TYPE_LENGTH = 48
MAX_TOKEN_LENGTH = 128


class ProtocolError(ValueError):
    """Raised when a packet cannot be parsed or violates the protocol."""


def make_packet(
    packet_type: str,
    *,
    seq: int = 0,
    payload: dict[str, Any] | None = None,
    session_token: str | None = None,
) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "type": packet_type,
        "seq": int(seq),
        "payload": payload or {},
    }
    if session_token:
        packet["session_token"] = session_token
    return packet


def encode_packet(
    packet_type: str,
    *,
    seq: int = 0,
    payload: dict[str, Any] | None = None,
    session_token: str | None = None,
) -> bytes:
    packet = make_packet(
        packet_type,
        seq=seq,
        payload=payload,
        session_token=session_token,
    )
    return encode_packet_dict(packet)


def encode_packet_dict(packet: dict[str, Any]) -> bytes:
    validate_common_packet(packet)
    raw = json.dumps(packet, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if len(raw) > MAX_PACKET_BYTES:
        raise ProtocolError("packet too large")
    return raw + b"\n"


def parse_packet_line(line: bytes) -> dict[str, Any]:
    if not line:
        raise ProtocolError("empty packet")
    if len(line) > MAX_PACKET_BYTES:
        raise ProtocolError("packet too large")
    try:
        packet = json.loads(line.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ProtocolError("packet is not valid utf-8") from exc
    except json.JSONDecodeError as exc:
        raise ProtocolError("packet is not valid json") from exc
    if not isinstance(packet, dict):
        raise ProtocolError("packet must be a json object")
    validate_common_packet(packet)
    return packet


def validate_common_packet(packet: dict[str, Any]) -> None:
    packet_type = packet.get("type")
    if not isinstance(packet_type, str) or not packet_type:
        raise ProtocolError("packet type is required")
    if len(packet_type) > MAX_TYPE_LENGTH:
        raise ProtocolError("packet type is too long")

    seq = packet.get("seq")
    if not isinstance(seq, int) or seq < 0:
        raise ProtocolError("seq must be a non-negative integer")

    payload = packet.get("payload")
    if payload is None:
        packet["payload"] = {}
    elif not isinstance(payload, dict):
        raise ProtocolError("payload must be an object")

    token = packet.get("session_token")
    if token is not None:
        if not isinstance(token, str) or not token:
            raise ProtocolError("session_token must be a non-empty string")
        if len(token) > MAX_TOKEN_LENGTH:
            raise ProtocolError("session_token is too long")


class PacketBuffer:
    """Incrementally decodes newline-delimited packets from a byte stream."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        if not data:
            return []
        self._buffer.extend(data)
        if b"\n" not in self._buffer and len(self._buffer) > MAX_PACKET_BYTES:
            raise ProtocolError("packet too large")

        packets: list[dict[str, Any]] = []
        while True:
            newline_index = self._buffer.find(b"\n")
            if newline_index < 0:
                break
            line = bytes(self._buffer[:newline_index]).strip()
            del self._buffer[: newline_index + 1]
            if not line:
                continue
            packets.append(parse_packet_line(line))
        return packets


CLIENT_PACKET_TYPES = {
    "HELLO",
    "JOIN_MATCHMAKING",
    "RECONNECT",
    "INPUT_UPDATE",
    "PONG",
    "LEAVE_ROOM",
    "REMATCH_REQUEST",
}

SERVER_PACKET_TYPES = {
    "WELCOME",
    "QUEUED",
    "MATCH_FOUND",
    "COUNTDOWN",
    "MATCH_START",
    "STATE_UPDATE",
    "PING",
    "MATCH_FINISH",
    "PLAYER_FINISHED",
    "REMATCH_WAITING",
    "ERROR",
    "INFO",
}

AUTHENTICATED_CLIENT_PACKETS = {
    "JOIN_MATCHMAKING",
    "INPUT_UPDATE",
    "PONG",
    "LEAVE_ROOM",
    "REMATCH_REQUEST",
}


def validate_client_packet(packet: dict[str, Any]) -> None:
    validate_common_packet(packet)
    packet_type = packet["type"]
    if packet_type not in CLIENT_PACKET_TYPES:
        raise ProtocolError(f"unknown client packet type: {packet_type}")
    if packet_type in AUTHENTICATED_CLIENT_PACKETS and "session_token" not in packet:
        raise ProtocolError("session_token is required")


def get_payload_string(
    packet: dict[str, Any],
    key: str,
    *,
    required: bool = True,
    max_length: int = 256,
) -> str:
    payload = packet.get("payload", {})
    value = payload.get(key)
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise ProtocolError(f"payload.{key} must be a non-empty string")
    if len(value) > max_length:
        raise ProtocolError(f"payload.{key} is too long")
    return value
