-- normalize_roles.sql
-- Ensure metabolism role values are in a small controlled vocabulary
BEGIN TRANSACTION;

UPDATE drug_metabolism
SET role = 'ингибитор'
WHERE lower(trim(role)) IN ('inhibitor','ингибиторы','ингибитор');

UPDATE drug_metabolism
SET role = 'субстрат'
WHERE lower(trim(role)) IN ('substrate','субстрат','субстрат?');

UPDATE drug_metabolism
SET role = 'индуктор'
WHERE lower(trim(role)) IN ('inducer','индуктор','индукция');

COMMIT;
