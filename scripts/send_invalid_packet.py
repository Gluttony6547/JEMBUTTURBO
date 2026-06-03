"""Send malformed and invalid packets to demonstrate server validation."""

from __future__ import annotations

import argparse
import socket

from jempol_turbo.protocol import encode_packet
from jempol_turbo.server import DEFAULT_HOST, DEFAULT_PORT


def main() -> None:
    parser = argparse.ArgumentParser(description="Send invalid packets to the Jempol Turbo server.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    with socket.create_connection((args.host, args.port), timeout=5) as sock:
        sock.settimeout(1)
        sock.sendall(b'{"type":"BROKEN","seq":0,"payload":{}\n')
        print(sock.recv(4096).decode("utf-8", errors="replace").strip())

    with socket.create_connection((args.host, args.port), timeout=5) as sock:
        sock.settimeout(1)
        sock.sendall(encode_packet("NOT_A_COMMAND", seq=0, payload={}))
        print(sock.recv(4096).decode("utf-8", errors="replace").strip())


if __name__ == "__main__":
    main()
