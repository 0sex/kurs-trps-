from database import Database

def verify_database():
    """Проверить состояние и содержимое БД"""
    db = Database("drugs.db")
    
    print("=== Проверка базы данных ===\n")
    
    all_drugs = db.get_all_drugs()
    print(f"📊 Всего препаратов: {len(all_drugs)}")
    
    if all_drugs:
        print("\n📋 Список препаратов:")
        for i, drug in enumerate(all_drugs, 1):
            print(f"  {i}. {drug['name']} ({drug['substance']}) - {drug['form']} - {drug['price']} руб.")
    
    forms = db.get_all_forms()
    print(f"\n🔹 Формы выпуска ({len(forms)}): {', '.join(forms)}")
    
    manufacturers = db.get_all_manufacturers()
    print(f"\n🏭 Производители ({len(manufacturers)}): {', '.join(manufacturers)}")
    
    contraindications = db.get_all_contraindications()
    print(f"\n⚠️  Противопоказания ({len(contraindications)}): {', '.join(contraindications[:10])}")
    if len(contraindications) > 10:
        print(f"     ... и еще {len(contraindications) - 10}")
    
    conn = db._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM drug_targets")
    targets = cursor.fetchone()[0]
    print(f"\n🎯 Мишеней (drug_targets): {targets}")
    
    cursor.execute("SELECT COUNT(*) FROM drug_metabolism")
    metabolism = cursor.fetchone()[0]
    print(f"🧬 Метаболизма (drug_metabolism): {metabolism}")
    
    cursor.execute("SELECT COUNT(*) FROM drug_effect_profile")
    effects = cursor.fetchone()[0]
    print(f"💊 Профилей эффектов (drug_effect_profile): {effects}")
    
    cursor.execute("SELECT COUNT(*) FROM drug_interaction_cache")
    cache = cursor.fetchone()[0]
    print(f"⚡ Кэш взаимодействий (drug_interaction_cache): {cache}")
    
    conn.close()
    
    print("\n✓ База данных готова к работе!")

if __name__ == "__main__":
    verify_database()
