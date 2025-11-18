import sys
import os
sys.path.insert(0, r"e:\Code\kurs-trps-")
from interactions import run_interaction_report

run_interaction_report()
print('REPORT_DONE')
# print first 20 lines of generated CSV if exists
p = os.path.join(os.getcwd(), 'interaction_report.csv')
if os.path.exists(p):
    with open(p, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            print(line.strip())
            if i >= 19:
                break
else:
    print('interaction_report.csv not found')
