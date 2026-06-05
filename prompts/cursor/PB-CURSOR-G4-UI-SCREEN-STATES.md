# PB-CURSOR-G4 — UI Design and Screen State Pack

## Task
Implement or design UI only against screen IDs and state definitions.

## Required states
Every screen must support loading, empty, error, forbidden, success and happy state.

## Stop conditions
Stop if a screen leaks resource existence in forbidden state, uses stale cross-tenant data, or lacks correlation_id on error.
