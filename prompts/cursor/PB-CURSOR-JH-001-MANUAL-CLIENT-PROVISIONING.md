# PB-CURSOR-JH-001 Manual Client Provisioning Wizard

## Task
Implement the manual client provisioning architecture patch.

## Inputs
- Manual_Client_Provisioning_Wizard_Dossier_v1_1.md
- Manual_Client_Provisioning_Flow_Steps_v1_1.csv
- data_model_patch_project_b_v1_1.sql
- OpenAPI_Patch_Register_Journey_Provisioning_v1_1.csv

## Outputs
- provisioning session data model / migration
- provisioning wizard route skeleton
- admin UI screen skeletons
- service commands for draft, gate, assignment, invite and status
- audit events
- tests JH-T001 to JH-T005

## Do not do
- Do not bypass Core access truth.
- Do not activate delivery before entitlement/consent/access gates pass.
- Do not hide manual bypass reason.
