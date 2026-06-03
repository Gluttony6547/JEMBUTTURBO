# Deploy Online Server

Jempol Turbo memakai raw TCP socket, jadi yang perlu dideploy adalah server TCP. Client tkinter tetap dijalankan dari laptop pemain dan diarahkan ke IP/domain server.

## Python Langsung di VPS

1. Upload project ke VPS.
2. Pastikan Python 3.10+ tersedia.
3. Buka inbound TCP port `5050` di firewall/security group.
4. Jalankan server:

```bash
python server.py --host 0.0.0.0 --port 5050
```

5. Di client, isi `Server host` dengan public IP/domain VPS dan `Server port` dengan `5050`.

## Docker Compose

```bash
docker compose up -d --build
```

Server listen di `0.0.0.0:5050` dan log disimpan ke folder `logs/`.

## Catatan Demo Online

- Gunakan port forwarding/security group untuk TCP `5050`.
- Jika jaringan memblokir port custom, gunakan VPS/hotspot yang portnya terbuka.
- Untuk production sungguhan, tambahkan TLS atau jalankan di balik tunnel TCP yang aman.
