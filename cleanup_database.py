# Run this script to clean up database.py
# This will remove all duplicate code after line 488

with open('database.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Keep only the first 488 lines (indices 0-487)
cleaned_lines = lines[:488]

with open('database.py', 'w', encoding='utf-8') as f:
    f.writelines(cleaned_lines)

print("Cleaned database.py - removed duplicate code")

