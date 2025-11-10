#!/usr/bin/env python3
"""
Скрипт для принудительного обновления базы данных.
Удаляет старые данные и заполняет базу 147 препаратами с противопоказаниями.
"""

from database import Database
import os

def update_database():
    """Обновить базу данных принудительно."""
    print("=" * 60)
    print("Обновление базы данных препаратов")
    print("=" * 60)
    
    db = Database()
    
    # Проверяем текущее состояние
    drugs = db.get_all_drugs()
    print(f"\nТекущее состояние базы данных:")
    print(f"  - Всего препаратов: {len(drugs)}")
    
    drugs_with_contra = [d for d in drugs if d.get('contraindications') and d.get('contraindications').strip()]
    print(f"  - С противопоказаниями: {len(drugs_with_contra)}")
    print(f"  - Без противопоказаний: {len(drugs) - len(drugs_with_contra)}")
    
    # Очищаем базу данных
    print("\nОчистка базы данных...")
    db.force_update_database()
    print("✓ База данных очищена и переинициализирована")
    
    # Заполняем базу данных
    print("\nЗаполнение базы данных новыми данными...")
    db.populate_sample_data()
    
    # Проверяем результат
    drugs = db.get_all_drugs()
    drugs_with_contra = [d for d in drugs if d.get('contraindications') and d.get('contraindications').strip()]
    
    print(f"\nРезультат обновления:")
    print(f"  - Всего препаратов: {len(drugs)}")
    print(f"  - С противопоказаниями: {len(drugs_with_contra)}")
    print(f"  - Без противопоказаний: {len(drugs) - len(drugs_with_contra)}")
    
    print("\nПримеры препаратов с противопоказаниями:")
    for d in drugs_with_contra[:5]:
        print(f"  - {d['name']}: {d.get('contraindications', '')}")
    
    print("\n" + "=" * 60)
    print("✓ База данных успешно обновлена!")
    print("=" * 60)
    print("\nТеперь перезапустите приложение для просмотра обновленных данных.")

if __name__ == "__main__":
    update_database()

