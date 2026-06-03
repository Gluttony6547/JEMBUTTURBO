import socket
import threading
import time
import unittest

import jempol_turbo.server as server_module
from jempol_turbo.protocol import PacketBuffer, encode_packet
from jempol_turbo.server import JempolTurboServer


class SocketClient:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        self.sock.settimeout(0.2)
        self.buffer = PacketBuffer()
        self.seq = 0
        self.token = ""

    def send(self, packet_type, payload=None, token=True):
        raw = encode_packet(
            packet_type,
            seq=self.seq,
            payload=payload or {},
            session_token=self.token if token else None,
        )
        self.seq += 1
        self.sock.sendall(raw)

    def read_until(self, packet_type, timeout=4.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                continue
            if not data:
                raise AssertionError("server closed connection")
            for packet in self.buffer.feed(data):
                if packet["type"] == "WELCOME":
                    self.token = packet["payload"]["session_token"]
                if packet["type"] == "PING":
                    self.send("PONG", {"ping_id": packet["payload"].get("ping_id")})
                if packet["type"] == packet_type:
                    return packet
        raise AssertionError(f"timed out waiting for {packet_type}")

    def close(self):
        self.sock.close()


class ServerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.old_countdown = server_module.COUNTDOWN_SECONDS
        self.old_ping = server_module.PING_INTERVAL
        server_module.COUNTDOWN_SECONDS = 0.1
        server_module.PING_INTERVAL = 999.0
        self.server = JempolTurboServer("127.0.0.1", 0)
        self.server.start()
        self.port = self.server.server_sock.getsockname()[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        server_module.COUNTDOWN_SECONDS = self.old_countdown
        server_module.PING_INTERVAL = self.old_ping

    def test_two_clients_can_match_and_finish(self):
        alice = SocketClient(self.port)
        bob = SocketClient(self.port)
        try:
            alice.send("HELLO", {"username": "alice"}, token=False)
            bob.send("HELLO", {"username": "bob"}, token=False)
            alice.read_until("WELCOME")
            bob.read_until("WELCOME")

            alice.send("JOIN_MATCHMAKING")
            bob.send("JOIN_MATCHMAKING")
            found = alice.read_until("MATCH_FOUND")
            bob.read_until("MATCH_FOUND")
            target = found["payload"]["target_text"]
            self.assertEqual(found["payload"]["mode"], "1000cc")
            self.assertGreaterEqual(found["payload"]["word_count"], 10)
            self.assertLessEqual(found["payload"]["word_count"], 20)

            alice.read_until("MATCH_START")
            bob.read_until("MATCH_START")
            alice.send("INPUT_UPDATE", {"typed_text": target})
            bob.send("INPUT_UPDATE", {"typed_text": target})

            result = alice.read_until("MATCH_FINISH")
            self.assertEqual(result["payload"]["reason"], "all players finished")
            self.assertEqual(len(result["payload"]["rankings"]), 2)
        finally:
            alice.close()
            bob.close()

    def test_mode_queue_and_rematch(self):
        alice = SocketClient(self.port)
        bob = SocketClient(self.port)
        try:
            alice.send("HELLO", {"username": "mode-alice"}, token=False)
            bob.send("HELLO", {"username": "mode-bob"}, token=False)
            alice.read_until("WELCOME")
            bob.read_until("WELCOME")

            alice.send("JOIN_MATCHMAKING", {"mode": "turbo"})
            bob.send("JOIN_MATCHMAKING", {"mode": "turbo"})
            found = alice.read_until("MATCH_FOUND")
            bob.read_until("MATCH_FOUND")
            self.assertEqual(found["payload"]["mode"], "turbo")
            self.assertGreaterEqual(found["payload"]["word_count"], 40)
            self.assertLessEqual(found["payload"]["word_count"], 50)
            target = found["payload"]["target_text"]

            alice.read_until("MATCH_START")
            bob.read_until("MATCH_START")
            alice.send("INPUT_UPDATE", {"typed_text": target})
            bob.send("INPUT_UPDATE", {"typed_text": target})
            alice.read_until("MATCH_FINISH")
            bob.read_until("MATCH_FINISH")

            alice.send("REMATCH_REQUEST")
            waiting = alice.read_until("REMATCH_WAITING")
            self.assertEqual(waiting["payload"]["ready_count"], 1)
            bob.send("REMATCH_REQUEST")
            rematch = alice.read_until("MATCH_FOUND")
            self.assertEqual(rematch["payload"]["mode"], "turbo")
        finally:
            alice.close()
            bob.close()

    def test_invalid_packet_returns_error(self):
        client = SocketClient(self.port)
        try:
            client.sock.sendall(b'{"type":"BROKEN","seq":0,"payload":{}\n')
            error = client.read_until("ERROR")
            self.assertIn("json", error["payload"]["message"])
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
