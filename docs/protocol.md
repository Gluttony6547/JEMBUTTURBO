# Desain Protokol Aplikasi

## Transport

Jempol Turbo memakai TCP socket.

Alasan:

- Packet typing update perlu reliable.
- Urutan packet penting untuk progress dan state match.
- TCP menyederhanakan reconnect, framing, dan demo.

## Framing dan Serialization

Setiap packet adalah satu JSON object UTF-8 dan diakhiri newline `\n`.

Format umum:

```json
{
  "type": "INPUT_UPDATE",
  "seq": 7,
  "session_token": "abc123",
  "payload": {
    "typed_text": "hello"
  }
}
```

Field:

- `type`: jenis command/event.
- `seq`: sequence number non-negatif dari pengirim.
- `session_token`: token sesi, wajib untuk packet client setelah login.
- `payload`: object data.

Ukuran packet maksimal: 8192 byte.

## Client to Server

### HELLO

Login awal.

```json
{"type":"HELLO","seq":0,"payload":{"username":"alice"}}
```

### JOIN_MATCHMAKING

Masuk queue matchmaking sesuai mode.

```json
{"type":"JOIN_MATCHMAKING","seq":1,"session_token":"abc","payload":{"mode":"turbo"}}
```

Mode valid:

- `1000cc`: Jempol 1000cc, 10-20 kata.
- `2000cc`: Jempol 2000cc, 20-30 kata.
- `turbo`: Jempol Turbo, 40-50 kata.

### RECONNECT

Mengambil kembali session lama.

```json
{"type":"RECONNECT","seq":0,"session_token":"abc","payload":{"session_token":"abc"}}
```

### INPUT_UPDATE

Mengirim teks yang sedang diketik. Server menghitung semua metric.

```json
{"type":"INPUT_UPDATE","seq":8,"session_token":"abc","payload":{"typed_text":"hello"}}
```

### PONG

Balasan latency check.

```json
{"type":"PONG","seq":9,"session_token":"abc","payload":{"ping_id":"p123"}}
```

### LEAVE_ROOM

Keluar dari room aktif atau queue.

```json
{"type":"LEAVE_ROOM","seq":10,"session_token":"abc","payload":{}}
```

### REMATCH_REQUEST

Meminta rematch setelah match selesai. Rematch dimulai jika kedua player meminta.

```json
{"type":"REMATCH_REQUEST","seq":11,"session_token":"abc","payload":{}}
```

## Server to Client

### WELCOME

Login/reconnect berhasil.

```json
{"type":"WELCOME","seq":0,"payload":{"username":"alice","session_token":"abc","reconnected":false}}
```

### QUEUED

Player masuk queue.

```json
{"type":"QUEUED","seq":1,"payload":{"queue_size":1}}
```

### MATCH_FOUND

Room terbentuk.

```json
{"type":"MATCH_FOUND","seq":2,"payload":{"room_id":"room1","mode":"turbo","mode_label":"Jempol Turbo","target_text":"...","word_count":45,"players":[]}}
```

### COUNTDOWN

Countdown sebelum match dimulai.

```json
{"type":"COUNTDOWN","seq":3,"payload":{"room_id":"room1","remaining":2.5}}
```

### MATCH_START

Match dimulai.

```json
{"type":"MATCH_START","seq":4,"payload":{"room_id":"room1","target_text":"...","duration_limit":120}}
```

### STATE_UPDATE

State sinkron untuk kedua client.

```json
{
  "type": "STATE_UPDATE",
  "seq": 5,
  "payload": {
    "room_id": "room1",
    "state": "RUNNING",
    "elapsed": 5.2,
    "players": [
      {
        "username": "alice",
        "connected": true,
        "progress": 0.5,
        "accuracy": 96.0,
        "wpm": 54.0,
        "score": 52,
        "latency_ms": 14.2
      }
    ]
  }
}
```

### PING

Latency check dari server.

```json
{"type":"PING","seq":6,"payload":{"ping_id":"p123","server_time":123.4}}
```

### MATCH_FINISH

Hasil akhir match.

```json
{"type":"MATCH_FINISH","seq":7,"payload":{"reason":"all players finished","winner":"alice","rankings":[]}}
```

### PLAYER_FINISHED

Dikirim saat satu player finish lebih dulu.

```json
{"type":"PLAYER_FINISHED","seq":8,"payload":{"room_id":"room1","username":"alice","finish_time":12.4,"first":true}}
```

### REMATCH_WAITING

Status rematch saat belum semua player siap.

```json
{"type":"REMATCH_WAITING","seq":9,"payload":{"ready_count":1,"needed_count":2,"waiting_for":["bob"]}}
```

### ERROR

Packet invalid atau command tidak sesuai state.

```json
{"type":"ERROR","seq":8,"payload":{"message":"unknown client packet type: BAD"}}
```

## Validasi Packet

Server menolak packet jika:

- JSON rusak.
- `type` kosong atau tidak dikenal.
- `seq` bukan integer non-negatif.
- `payload` bukan object.
- `session_token` hilang untuk command yang wajib login.
- Packet lebih dari 8192 byte.
- Sequence number mundur.
- Command tidak sesuai state, misalnya `INPUT_UPDATE` sebelum match berjalan.
