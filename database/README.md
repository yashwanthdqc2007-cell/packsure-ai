# PackSure AI — Database

PostgreSQL via Supabase.

## Tables

| Table | Purpose |
|---|---|
| `users` | Inspector accounts |
| `product_categories` | Product types and their applicable rules |
| `rules` | Versioned Legal Metrology rule definitions |
| `scans` | Each compliance check session |
| `extracted_declarations` | OCR + AI extracted mandatory fields |
| `violations` | Rule violations found per scan |
| `ai_analysis` | Gemini API responses (audit trail) |
| `reports` | Generated compliance reports |

## Setup

1. Create a Supabase project.
2. Run `schema.sql` in the Supabase SQL editor.
3. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` in backend `.env`.

## Migrations

Migrations go in `migrations/`. Use sequential numbering: `001_initial.sql`, `002_add_column.sql`, etc.

## Seeds

Development seed data goes in `seeds/`. See `seeds/README.md`.
