# Laporan Final Project: Jempol Turbo

## 1. Pendahuluan

Jempol Turbo adalah game typing battle real-time untuk menunjukkan implementasi pemrograman jaringan pada sistem client-server. Project ini dipilih karena sinkronisasi state, latency, reconnect, dan validasi packet dapat terlihat jelas dalam skenario permainan sederhana.

## 2. Deskripsi dan Tujuan Project

Sistem mempertemukan dua pemain dalam satu room. Setelah matchmaking, server mengirim teks yang sama, menjalankan countdown, menerima input typing dari client, menghitung progress, WPM, akurasi, skor, dan ranking.

Mode pertandingan:

- Jempol 1000cc: 10-20 kata.
- Jempol 2000cc: 20-30 kata.
- Jempol Turbo: 40-50 kata.

Tujuan:

- Menerapkan TCP socket programming dengan Python.
- Membuat protokol aplikasi sendiri.
- Menangani banyak client memakai I/O multiplexing.
- Mengukur latency dan stabilitas server.
- Menangani disconnect, reconnect, dan malformed packet.

## 3. Arsitektur Sistem

Komponen:

- Server TCP: pusat matchmaking, room, state, scoring, latency, logging.
- Client GUI tkinter: login, matchmaking, arena typing, progress, latency, result.
- Simulator client: load test dan demo banyak client.

Alur:

1. Client mengirim `HELLO`.
2. Server memberi `WELCOME` berisi `session_token`.
3. Client mengirim `JOIN_MATCHMAKING`.
4. Server memasangkan 2 player dengan mode yang sama dan membuat room.
5. Server broadcast `MATCH_FOUND`, `COUNTDOWN`, lalu `MATCH_START`.
6. Client mengirim `INPUT_UPDATE`.
7. Server broadcast `STATE_UPDATE`.
8. Server mengirim `MATCH_FINISH` saat match selesai.

## 4. Desain Protokol Aplikasi

Transport menggunakan TCP. Semua message memakai JSON-line dengan delimiter newline.

Contoh packet:

```json
{"type":"INPUT_UPDATE","seq":7,"session_token":"abc","payload":{"typed_text":"hello"}}
```

Jenis packet utama:

- Client: `HELLO`, `JOIN_MATCHMAKING`, `RECONNECT`, `INPUT_UPDATE`, `PONG`, `LEAVE_ROOM`, `REMATCH_REQUEST`.
- Server: `WELCOME`, `QUEUED`, `MATCH_FOUND`, `COUNTDOWN`, `MATCH_START`, `STATE_UPDATE`, `PING`, `PLAYER_FINISHED`, `REMATCH_WAITING`, `MATCH_FINISH`, `ERROR`.

Detail lengkap ada di `docs/protocol.md`.

## 5. Pengujian Performa dan Beban Server

Skenario uji:

- Unit test parser packet dan scoring.
- Integration test 2 client sampai match selesai.
- Invalid packet test.
- Load test dengan simulator:

```bash
python scripts/simulate_clients.py --clients 10 --mode turbo
```

Metrik yang dicatat:

- Jumlah client berhasil selesai.
- Jumlah error.
- Durasi test.
- Latency minimum, rata-rata, maksimum.
- Stabilitas server dari log.

## 6. Hasil dan Analisis

Isi setelah menjalankan test:

| Skenario | Jumlah Client | Berhasil | Error | Avg Latency | Catatan |
|---|---:|---:|---:|---:|---|
| Local load test | 10 | TBD | TBD | TBD | TBD |

Analisis awal:

- TCP menjaga urutan update sehingga state lebih konsisten.
- Server authoritative mencegah client memalsukan skor akhir.
- `selectors` membuat server dapat menangani banyak socket tanpa thread per client.

## 7. Kendala dan Solusi

Isi setelah pengembangan:

- Kendala: GUI tidak boleh freeze saat menunggu socket.
  Solusi: network listener berjalan pada thread terpisah.
- Kendala: packet TCP tidak memiliki batas message bawaan.
  Solusi: memakai JSON-line sebagai framing.
- Kendala: client disconnect saat match.
  Solusi: session token dan reconnect window 30 detik.

## 8. Kesimpulan dan Saran

Jempol Turbo memenuhi fitur wajib game berbasis jaringan: minimal 2 player, room system, matchmaking, state synchronization, TCP socket, real-time update, reconnect, latency indicator, logging, dan anti-invalid packet.

Saran pengembangan:

- Spectator mode.
- Ranking persistence.
- Match replay.
- TLS.
- Load balancing untuk beberapa server.
