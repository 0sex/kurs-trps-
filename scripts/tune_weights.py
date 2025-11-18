import sys
sys.path.insert(0, r"e:\Code\kurs-trps-")
from database import Database
from interactions import InteractionEngine, WEIGHTS

print('Current WEIGHTS:', WEIGHTS)

db = Database()
engine = InteractionEngine(db)

drugs = db.get_all_drugs()
ids = [d['id'] for d in drugs]

counts = {'Низкий':0, 'Средний':0, 'Высокий':0}

total = 0
for i in range(len(ids)):
    for j in range(i+1, len(ids)):
        a = ids[i]; b=ids[j]
        res = engine.analyze_interaction(a,b)
        lvl = res.get('level','Низкий')
        counts[lvl] = counts.get(lvl,0)+1
        total += 1

print('Total pairs:', total)
print('Counts:', counts)
high_frac = counts['Высокий']/total if total else 0
print('High fraction:', high_frac)

# simple tuning rule
desired = 0.10
new_weights = WEIGHTS.copy()
if high_frac > desired * 1.5:
    factor = 0.9
    new_weights = {k: v*factor for k,v in WEIGHTS.items()}
    s = sum(new_weights.values())
    new_weights = {k: round(v/s,3) for k,v in new_weights.items()}
    print('Proposed new weights (scaled):', new_weights)
else:
    print('No change proposed')

# print as python literal for apply_patch
print('\nPY_LITERAL = ' + repr(new_weights))
