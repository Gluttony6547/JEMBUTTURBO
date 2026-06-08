# Jempol Turbo

Jempol Turbo adalah game typing battle real-time berbasis jaringan. Dua pemain masuk matchmaking, ditempatkan dalam satu room, menerima teks yang sama, lalu berlomba mengetik. Server menyinkronkan progress, menghitung WPM, akurasi, skor, ranking, latency, reconnect, dan menolak packet invalid.

## Fitur

- Python TCP socket client-server.
- React + Vite + TypeScript web app.
- Supabase-ready matchmaking, Edge Functions, dan Realtime Broadcast.
- Vercel-ready frontend deploy.
- Server memakai `selectors` untuk I/O multiplexing banyak client.
- Room system: 1 room berisi 2 player.
- Matchmaking otomatis.
- Match lifecycle: `COUNTDOWN`, `RUNNING`, `FINISHED`.
- Real-time state synchronization.
- Reconnect handling memakai `session_token`.
- Ping/latency indicator.
- Colorful tkinter GUI dengan pilihan mode, banner finish, dan layar pemenang.
- Mode: `Jempol 1000cc`, `Jempol 2000cc`, dan `Jempol Turbo`.
- Rematch setelah match selesai.
- Server logging di `logs/server.log`.
- JSON-line packet serialization.
- Anti-invalid packet sederhana.
- Simulator client untuk load test.

## Struktur

```text
jempol_turbo/
  client.py       Tkinter GUI client
  server.py       Authoritative TCP server
  protocol.py     JSON-line packet parser, encoder, validator
  scoring.py      WPM, accuracy, score, ranking
  texts.py        Bank teks pertandingan
scripts/
  simulate_clients.py     Load test dengan bot client
  send_invalid_packet.py  Demo malformed/invalid packet
tests/
  test_protocol.py
  test_scoring.py
  test_server_integration.py
docs/
  deploy.md
  panduan_penggunaan.md
  protocol.md
  laporan.md
  web_deploy.md
```

## Web App

Install dependency:

```bash
npm install
```

Jalankan web app:

```bash
npm run dev
```

Build dan test:

```bash
npm run test
npm run build
```

Isi `.env.local` dari `.env.example` untuk mengaktifkan Supabase online mode. Tanpa env, web app berjalan dalam demo lokal.

## Cara Menjalankan

Gunakan Python 3.10+.

Jalankan server:

```bash
python server.py --host 127.0.0.1 --port 5050
```

Jalankan 2 client di terminal berbeda:

```bash
python client.py --host 127.0.0.1 --port 5050
```

Langkah main:

1. Isi username berbeda di tiap client.
2. Klik `Connect`.
3. Klik `Join Matchmaking`.
4. Setelah countdown selesai, ketik teks yang tampil.
5. Lihat progress, WPM, akurasi, skor, ranking, dan latency.

## Reconnect Demo

1. Login dari client dan simpan `Session token`.
2. Masuk match.
3. Tutup client saat match berjalan.
4. Buka client lagi.
5. Isi `Session token`.
6. Klik `Reconnect`.

Server menahan slot player selama 30 detik.

## Load Test

Jalankan server dulu, lalu:

```bash
python scripts/simulate_clients.py --clients 10 --mode turbo --host 127.0.0.1 --port 5050
```

Output menampilkan jumlah client selesai, jumlah error, durasi, dan statistik latency jika tersedia.

## Invalid Packet Demo

Jalankan server dulu, lalu:

```bash
python scripts/send_invalid_packet.py --host 127.0.0.1 --port 5050
```

Server akan membalas packet `ERROR` dan mencatat invalid packet di log.

## Test

```bash
python -m unittest discover -s tests
```

Test mencakup:

- JSON-line packet parser dan validator.
- Scoring WPM, akurasi, progress, ranking.
- Integrasi 2 client sampai match selesai.
- Invalid packet rejection.

## Alasan Memilih TCP

Typing battle membutuhkan pesan yang reliable dan berurutan. Jika update input hilang atau urutannya kacau, progress, WPM, dan hasil match bisa tidak konsisten. Karena itu TCP dipilih agar packet sampai secara reliable, tetap berurutan, dan lebih mudah dijelaskan untuk demo pemrograman jaringan.

## Protokol Singkat

Semua packet adalah JSON UTF-8 dengan delimiter newline `\n`.

Contoh:

```json
{"type":"INPUT_UPDATE","seq":7,"session_token":"abc","payload":{"typed_text":"hello"}}
```

Packet utama:

- Client: `HELLO`, `JOIN_MATCHMAKING`, `RECONNECT`, `INPUT_UPDATE`, `PONG`, `LEAVE_ROOM`, `REMATCH_REQUEST`.
- Server: `WELCOME`, `QUEUED`, `MATCH_FOUND`, `COUNTDOWN`, `MATCH_START`, `STATE_UPDATE`, `PING`, `PLAYER_FINISHED`, `REMATCH_WAITING`, `MATCH_FINISH`, `ERROR`.

Detail ada di `docs/protocol.md`.

## Deploy Online

Server bisa dijalankan online di VPS/cloud dengan TCP port `5050`.

```bash
python server.py --host 0.0.0.0 --port 5050
```

Atau dengan Docker:

```bash
docker compose up -d --build
```

Detail ada di `docs/deploy.md`.

## Pembagian Tugas Kelompok

Isi bagian ini sebelum submit:

- Anggota 1: server, protocol, logging.
- Anggota 2: client GUI, reconnect flow, latency display.
- Anggota 3: testing, load test, README, laporan, video demo.
