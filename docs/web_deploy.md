# Jempol Turbo Web Deploy

Dokumen ini menjelaskan versi web React + Supabase + Vercel. Versi Python TCP tetap tersedia untuk demo socket lokal.

## Live URL

- Production: https://jempol-turbo-web.vercel.app
- Inspect: https://vercel.com/gluttony6547s-projects/jempol-turbo-web/7wLHLjuK8e54Biaj2Q5AjW2FUREd

Catatan: deployment frontend sudah aktif. Multiplayer online penuh baru aktif setelah `VITE_SUPABASE_URL` dan `VITE_SUPABASE_ANON_KEY` diisi di Vercel, lalu migration dan Edge Functions Supabase diterapkan.

## Local Web Run

1. Install dependency:

```bash
npm install
```

2. Buat `.env.local` dari `.env.example`, lalu isi:

```bash
VITE_SUPABASE_URL=https://your-project-ref.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-or-publishable-key
```

3. Jalankan web app:

```bash
npm run dev
```

Jika env belum diisi, web app tetap bisa dibuka dalam `Demo local` mode. Mode ini hanya untuk validasi UI, bukan multiplayer online.

## Supabase Setup

1. Install dan login Supabase CLI.
2. Link project:

```bash
supabase link --project-ref <project-ref>
```

3. Apply migration:

```bash
supabase db push
```

4. Deploy Edge Functions:

```bash
supabase functions deploy matchmaking
supabase functions deploy submit-input
supabase functions deploy match-state
```

Tables yang dibuat:

- `matches`
- `match_players`
- `matchmaking_queue`

Edge Functions:

- `matchmaking`
- `submit-input`
- `match-state`

## Vercel Deploy

Pastikan env berikut sudah diisi di Vercel Project Settings:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Deploy preview:

```bash
vercel deploy
```

Deploy production:

```bash
vercel deploy --prod
```

## Verification

Run sebelum deploy:

```bash
npm run test
npm run build
```

Smoke test manual:

1. Buka web app di dua browser/tab.
2. Masukkan username berbeda.
3. Pilih mode yang sama.
4. Join matchmaking.
5. Ketik target text sampai match selesai.
6. Cek result dan rematch.
