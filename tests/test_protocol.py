import unittest

from jempol_turbo.protocol import (
    PacketBuffer,
    ProtocolError,
    encode_packet,
    parse_packet_line,
    validate_client_packet,
)


class ProtocolTests(unittest.TestCase):
    def test_encode_and_parse_roundtrip(self):
        raw = encode_packet(
            "INPUT_UPDATE",
            seq=7,
            session_token="token-1",
            payload={"typed_text": "hello"},
        )
        packet = parse_packet_line(raw.strip())
        self.assertEqual(packet["type"], "INPUT_UPDATE")
        self.assertEqual(packet["seq"], 7)
        self.assertEqual(packet["session_token"], "token-1")
        self.assertEqual(packet["payload"]["typed_text"], "hello")

    def test_buffer_handles_split_packets(self):
        raw = encode_packet("HELLO", seq=0, payload={"username": "alice"})
        buffer = PacketBuffer()
        self.assertEqual(buffer.feed(raw[:5]), [])
        packets = buffer.feed(raw[5:])
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0]["type"], "HELLO")

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(ProtocolError):
            parse_packet_line(b'{"type":')

    def test_authenticated_packet_requires_token(self):
        packet = {"type": "JOIN_MATCHMAKING", "seq": 1, "payload": {}}
        with self.assertRaises(ProtocolError):
            validate_client_packet(packet)


if __name__ == "__main__":
    unittest.main()
