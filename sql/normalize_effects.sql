-- normalize_effects.sql
-- Normalize effect names and map synonyms to canonical phrases
BEGIN TRANSACTION;

UPDATE drug_effect_profile
SET effect_name = 'низкое давление'
WHERE lower(trim(effect_name)) IN ('гипотензия','ортостатическая гипотензия','low blood pressure');

UPDATE drug_effect_profile
SET effect_name = 'низкий натрий'
WHERE lower(trim(effect_name)) IN ('гипонатриемия','низкий уровень натрия');

UPDATE drug_effect_profile
SET effect_name = 'желудочно-кишечное кровотечение'
WHERE lower(trim(effect_name)) IN ('жк-кровотечение','ulcer');

COMMIT;

-- As with targets, adapt regexp/trim functions for your DB engine if needed.
