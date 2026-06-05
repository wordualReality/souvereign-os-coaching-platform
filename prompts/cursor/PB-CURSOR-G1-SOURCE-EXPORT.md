# PB-CURSOR-G1 — Source / Dossier Export Pack

## Task
Validate and maintain the Project B source truth. Do not change product scope.

## Allowed inputs
- `01_G1_Source_Dossier_Export_Pack/ProjectB_Current_Truth_Register_v1_0.json`
- `ProjectB_Source_Dossier_Ledger_v1_0.csv`
- prior Enterprise Architecture Design Bundle v0.2

## Output
Update source ledger only when a source is read, superseded or promoted.

## Stop conditions
Stop if a source implies Project B owns Core or DB/Canonical truth.
