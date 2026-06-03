# Panduan Penggunaan dan Cara Bermain Jempol Turbo

## 1. Tujuan Dokumen

Dokumen ini berisi langkah penggunaan aplikasi dan cara bermain Jempol Turbo dari sisi pengguna.

## 2. Persiapan

Pastikan:

- Python 3.10 atau lebih baru sudah terpasang.
- Semua file project berada dalam satu folder yang sama.
- Server dan client dijalankan dari jaringan yang saling terhubung.

## 3. Menjalankan Aplikasi

### Menjalankan server

Buka terminal pada folder project, lalu jalankan:

```bash
python server.py --host 127.0.0.1 --port 5050
```

Keterangan:

- `127.0.0.1` dipakai jika server dan client dijalankan di komputer yang sama.
- Jika server dijalankan dari komputer lain atau VPS, ganti `host` sesuai alamat server.

### Menjalankan client

Buka dua terminal terpisah, lalu jalankan pada masing-masing terminal:

```bash
python client.py --host 127.0.0.1 --port 5050
```

Satu jendela client digunakan oleh satu pemain.

## 4. Langkah Penggunaan

1. Jalankan server terlebih dahulu.
2. Jalankan dua client.
3. Pada masing-masing client, isi:
   - `Server host`
   - `Server port`
   - `Username`
4. Klik `Connect`.
5. Setelah berhasil login, pilih mode permainan.
6. Klik `Join Matchmaking`.
7. Tunggu sampai dua pemain masuk queue dan room terbentuk.

## 5. Mode Permainan

Jempol Turbo memiliki tiga mode:

- `Jempol 1000cc`: teks pendek sekitar 10-20 kata.
- `Jempol 2000cc`: teks sedang sekitar 20-30 kata.
- `Jempol Turbo`: teks panjang sekitar 40-50 kata.

Agar langsung bertemu, dua pemain harus memilih mode yang sama.

## 6. Cara Bermain

1. Setelah matchmaking berhasil, client akan menampilkan room dan teks target.
2. Tunggu countdown selesai.
3. Saat status berubah menjadi mulai, ketik teks target pada area input.
4. Selama pertandingan, layar akan menampilkan:
   - progress pemain
   - progress lawan
   - WPM
   - akurasi
   - skor
   - latency
5. Jika ada pemain yang finish lebih dulu, banner status akan memberi tahu.
6. Match selesai saat kedua pemain selesai atau saat kondisi akhir lain diputuskan server.
7. Hasil akhir menampilkan ranking, WPM, akurasi, skor, dan waktu finish.

## 7. Reconnect

Jika koneksi client terputus saat match berjalan:

1. Catat `Session token` milik pemain.
2. Buka kembali client.
3. Isi `Server host`, `Server port`, dan `Session token`.
4. Klik `Reconnect`.

Catatan:

- Server menahan slot pemain selama kurang lebih 30 detik.
- Jika reconnect terlalu lama, match dapat dianggap selesai oleh server.

## 8. Rematch

Setelah match selesai:

1. Klik `Rematch` jika ingin bermain lagi dengan lawan yang sama.
2. Match baru akan dimulai jika kedua pemain sama-sama memilih `Rematch`.
3. Jika ingin mencari lawan lain, klik `Cari Lawan Baru`.

## 9. Skenario Demo yang Disarankan

Untuk demo ke dosen atau asisten:

1. Jalankan 1 server dan 2 client.
2. Login dengan dua username berbeda.
3. Pilih mode yang sama lalu mulai match.
4. Tunjukkan progress real-time, latency, dan hasil akhir.
5. Tunjukkan satu pemain finish lebih dulu.
6. Tunjukkan fitur `Rematch`.
7. Tunjukkan `Reconnect` dengan menutup salah satu client lalu masuk kembali memakai `Session token`.

## 10. Troubleshooting Singkat

Jika client gagal connect:

- pastikan server sudah berjalan
- pastikan `host` dan `port` benar
- pastikan firewall tidak memblokir koneksi

Jika matchmaking tidak mulai:

- pastikan ada dua pemain
- pastikan kedua pemain memilih mode yang sama

Jika reconnect gagal:

- pastikan `Session token` benar
- pastikan reconnect masih dalam batas waktu server
