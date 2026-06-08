# Jempol Turbo Web Deploy

Dokumen ini menjelaskan versi web React + Supabase + Vercel. Versi Python TCP tetap tersedia untuk demo socket lokal.

## Live URL

- Production: https://jempol-turbo-web.vercel.app
- Inspect: https://vercel.com/gluttony6547s-projects/jempol-turbo-web/De771TMm7Jg9ZKP1UsdYJdXEEoKn

Catatan: deployment frontend sudah aktif. Env Supabase production sudah diisi di Vercel dan migration database sudah diterapkan. Selama Edge Functions belum dideploy, frontend memakai direct Supabase table fallback untuk matchmaking online.

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

Jika belum login Supabase CLI tetapi punya database password, migration bisa diterapkan dengan direct Postgres URL:

```bash
supabase db push --db-url "postgresql://postgres:<db-password>@db.<project-ref>.supabase.co:5432/postgres"
```

4. Deploy Edge Functions:

```bash
supabase functions deploy matchmaking
supabase functions deploy submit-input
supabase functions deploy match-state
```

Edge Functions membutuhkan Supabase access token/login account. Tanpa token, app masih dapat berjalan online melalui direct table fallback, karena tabel sudah diberi RLS policy demo untuk `anon` dan `authenticated`.

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
