# KDB-M01 Foundation

This package establishes the versioned KDB foundation in an isolated Supabase development project.

It deliberately excludes personal runtime data, Arcava journey ownership, n8n activation, secrets, and any write to the existing KDB integration project.

The SQL file is a forward migration designed to tolerate the legacy `canonical.protocol` table when later reviewed for promotion. A repository timestamped migration filename must be created with the Supabase CLI before Git integration; this runtime did not invent one because the CLI is unavailable here.

Promotion target `zobjpmyccszkabybdmsf` requires a separate exact-hash admission.
