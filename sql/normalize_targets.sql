-- normalize_targets.sql
-- Normalize target names: trim, lower, replace common synonyms
BEGIN TRANSACTION;

-- Example: unify known synonyms to canonical names
UPDATE drug_targets
SET target_name = 'l-type calcium channel'
WHERE lower(trim(target_name)) IN ('ltcc','l-vscc','кальциевый канал l-типа','сердечный кальциевый канал');

-- Trim whitespace and collapse spaces
UPDATE drug_targets
SET target_name = trim(regexp_replace(target_name, '\\s+', ' ', 'g'))
WHERE target_name IS NOT NULL;

COMMIT;

-- Note: SQLite does not support regexp_replace by default; replace that line
-- with appropriate SQL for your engine or run normalization in Python if using SQLite.
