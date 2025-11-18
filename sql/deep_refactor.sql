-- deep_refactor.sql
-- WARNING: example deep refactor. Review before running.
-- This script demonstrates rekeying and canonicalization steps for targets/effects.
-- Recommended approach for SQLite: export, run a Python normalizer, re-import.

BEGIN TRANSACTION;

-- (1) Create canonical lookup tables
CREATE TABLE IF NOT EXISTS canonical_targets (id INTEGER PRIMARY KEY, canonical_name TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS canonical_effects (id INTEGER PRIMARY KEY, canonical_name TEXT UNIQUE);

-- (2) Populate from existing normalized values (example)
INSERT OR IGNORE INTO canonical_targets (canonical_name)
SELECT DISTINCT lower(trim(target_name)) FROM drug_targets WHERE target_name IS NOT NULL;

INSERT OR IGNORE INTO canonical_effects (canonical_name)
SELECT DISTINCT lower(trim(effect_name)) FROM drug_effect_profile WHERE effect_name IS NOT NULL;

-- (3) Optionally link drug_targets -> canonical_targets by id (requires schema change)

COMMIT;

-- Run manually after review. Deep structural changes are safer via a Python migration.
