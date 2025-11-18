import os
import sqlite3
from database import Database

def reset_database():
    """Удалить текущую БД и создать новую с корректными данными"""
    db_path = "drugs.db"
    
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"✓ Удалена текущая база данных: {db_path}")
    
    db = Database(db_path)
    print(f"✓ Создана новая база данных: {db_path}")
    
    db.populate_sample_data()
    print(f"✓ Заполнена базовыми данными из drugs_data.json")
    
    db.populate_pharmacology_if_empty()
    print(f"✓ Добавлена фармакологическая информация")
    
    db.clear_interaction_cache()
    print(f"✓ Очищен кэш взаимодействий")
    
    conn = db._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM drugs")
    drugs_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM drug_targets")
    targets_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM drug_metabolism")
    metabolism_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM drug_effect_profile")
    effects_count = cursor.fetchone()[0]
    
    conn.close()
    
    print("\n=== Статистика новой БД ===")
    print(f"Препаратов: {drugs_count}")
    print(f"Мишеней (targets): {targets_count}")
    print(f"Метаболизма: {metabolism_count}")
    print(f"Профилей эффектов: {effects_count}")
    print("\n✓ База данных успешно переинициализирована!")

if __name__ == "__main__":
    reset_database()
