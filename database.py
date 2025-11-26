import sqlite3
import json
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class Database:
    def __init__(self, db_path: str = "drugs.db"):
        self.db_path = db_path
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_database(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drugs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                substance TEXT NOT NULL,
                form TEXT NOT NULL,
                manufacturer TEXT NOT NULL,
                price REAL NOT NULL,
                contraindications TEXT DEFAULT '',
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            cursor.execute("ALTER TABLE drugs ADD COLUMN contraindications TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE drugs ADD COLUMN description TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analog_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_id INTEGER NOT NULL,
                analog_id INTEGER NOT NULL,
                similarity_score REAL DEFAULT 1.0,
                FOREIGN KEY (drug_id) REFERENCES drugs(id),
                FOREIGN KEY (analog_id) REFERENCES drugs(id),
                UNIQUE(drug_id, analog_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drug_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_id INTEGER NOT NULL,
                target_name TEXT NOT NULL,
                effect_type TEXT NOT NULL,
                potency REAL DEFAULT 0.0,
                FOREIGN KEY (drug_id) REFERENCES drugs(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drug_metabolism (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_id INTEGER NOT NULL,
                enzyme_name TEXT NOT NULL,
                role TEXT NOT NULL,
                rate REAL DEFAULT 0.0,
                FOREIGN KEY (drug_id) REFERENCES drugs(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drug_effect_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_id INTEGER NOT NULL,
                effect_name TEXT NOT NULL,
                level INTEGER DEFAULT 0,
                FOREIGN KEY (drug_id) REFERENCES drugs(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drug_interaction_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_a_id INTEGER NOT NULL,
                drug_b_id INTEGER NOT NULL,
                score REAL NOT NULL,
                level TEXT NOT NULL,
                mechanisms TEXT,
                notes TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(drug_a_id, drug_b_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_substance ON drugs(substance)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_name ON drugs(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_contraindications ON drugs(contraindications)")
        conn.commit()
        conn.close()

    def add_drug(self, name: str, substance: str, form: str, manufacturer: str, price: float, contraindications: str = '', description: str = '', dosage: str = '', brand: str = '', targets_json: List[Dict] = None, metabolism_json: List[Dict] = None, side_effects_json: List[Dict] = None) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO drugs (name, substance, form, manufacturer, price, contraindications, description) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (name, substance, form, manufacturer, price, contraindications, description)
            )
            conn.commit()
            drug_id = cursor.lastrowid
            
            if targets_json:
                for target in targets_json:
                    self.add_target(drug_id, target.get('name', ''), target.get('effect_type', ''), target.get('potency', 0.0))
            
            if metabolism_json:
                for met in metabolism_json:
                    self.add_metabolism(drug_id, met.get('enzyme', ''), met.get('role', ''), met.get('rate', 0.0))
            
            if side_effects_json:
                for effect in side_effects_json:
                    self.add_effect_profile(drug_id, effect.get('name', ''), effect.get('severity', 0))
            
            return drug_id
        finally:
            conn.close()

    def get_drug_by_id(self, drug_id: int) -> Optional[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM drugs WHERE id = ?", (drug_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_drugs_by_substance(self, substance: str) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            substances = [s.strip() for s in substance.replace('+', ',').split(',') if s.strip()]
            if not substances:
                return []
            placeholders = ' OR '.join(['substance LIKE ?'] * len(substances))
            params = [f'%{sub}%' for sub in substances]
            cursor.execute(f"SELECT * FROM drugs WHERE {placeholders} ORDER BY price", params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def search_drugs_by_name(self, query: str) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM drugs WHERE name LIKE ? ORDER BY name", (f"%{query}%",))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_drugs(self) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM drugs ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update_drug(self, drug_id: int, name: str, substance: str, form: str, manufacturer: str, price: float, contraindications: str = '', description: str = '') -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE drugs SET name = ?, substance = ?, form = ?, manufacturer = ?, price = ?, contraindications = ?, description = ? WHERE id = ?",
                (name, substance, form, manufacturer, price, contraindications, description, drug_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_drug(self, drug_id: int) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM analog_links WHERE drug_id = ? OR analog_id = ?", (drug_id, drug_id))
            cursor.execute("DELETE FROM drugs WHERE id = ?", (drug_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def add_analog_link(self, drug_id: int, analog_id: int, similarity_score: float = 1.0) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR REPLACE INTO analog_links (drug_id, analog_id, similarity_score) VALUES (?, ?, ?)", (drug_id, analog_id, similarity_score))
            conn.commit()
            return True
        except sqlite3.Error:
            return False
        finally:
            conn.close()

    def get_analogs(self, drug_id: int) -> List[Tuple[Dict, float]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT d.*, a.similarity_score FROM drugs d JOIN analog_links a ON d.id = a.analog_id WHERE a.drug_id = ? ORDER BY a.similarity_score DESC, d.price", (drug_id,))
            return [(dict(row), row['similarity_score']) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_drugs_by_filters(self, form: Optional[str] = None, manufacturer: Optional[str] = None, min_price: Optional[float] = None, max_price: Optional[float] = None, exclude_contraindication: Optional[str] = None) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            query = "SELECT * FROM drugs WHERE 1=1"
            params = []
            if form:
                query += " AND form = ?"
                params.append(form)
            if manufacturer:
                query += " AND manufacturer LIKE ?"
                params.append(f"%{manufacturer}%")
            if min_price is not None:
                query += " AND price >= ?"
                params.append(min_price)
            if max_price is not None:
                query += " AND price <= ?"
                params.append(max_price)
            if exclude_contraindication:
                query += " AND (contraindications IS NULL OR contraindications = '' OR contraindications NOT LIKE ?)"
                params.append(f"%{exclude_contraindication}%")
            query += " ORDER BY price"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_contraindications(self) -> List[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT DISTINCT contraindications FROM drugs WHERE contraindications IS NOT NULL AND contraindications != ''")
            all_contraindications = set()
            for row in cursor.fetchall():
                contraindications = row[0]
                if contraindications:
                    for delim in [',', ';', '+']:
                        contraindications = contraindications.replace(delim, ',')
                    items = [c.strip() for c in contraindications.split(',') if c.strip()]
                    all_contraindications.update(items)
            return sorted(list(all_contraindications))
        finally:
            conn.close()

    def get_all_forms(self) -> List[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT DISTINCT form FROM drugs ORDER BY form")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_manufacturers(self) -> List[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT DISTINCT manufacturer FROM drugs ORDER BY manufacturer")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def add_target(self, drug_id: int, target_name: str, effect_type: str, potency: float = 0.0):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO drug_targets (drug_id, target_name, effect_type, potency) VALUES (?, ?, ?, ?)", (drug_id, target_name, effect_type, potency))
            conn.commit()
        finally:
            conn.close()

    def add_metabolism(self, drug_id: int, enzyme_name: str, role: str, rate: float = 0.0):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO drug_metabolism (drug_id, enzyme_name, role, rate) VALUES (?, ?, ?, ?)", (drug_id, enzyme_name, role, rate))
            conn.commit()
        finally:
            conn.close()

    def add_effect_profile(self, drug_id: int, effect_name: str, level: int = 0):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO drug_effect_profile (drug_id, effect_name, level) VALUES (?, ?, ?)", (drug_id, effect_name, level))
            conn.commit()
        finally:
            conn.close()

    def get_drug_pharmacology(self, drug_id: int) -> Dict:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT target_name, effect_type, potency FROM drug_targets WHERE drug_id = ?", (drug_id,))
            targets = [dict(row) for row in cursor.fetchall()]
            cursor.execute("SELECT enzyme_name, role, rate FROM drug_metabolism WHERE drug_id = ?", (drug_id,))
            metabolism = [dict(row) for row in cursor.fetchall()]
            cursor.execute("SELECT effect_name, level FROM drug_effect_profile WHERE drug_id = ?", (drug_id,))
            effects = [dict(row) for row in cursor.fetchall()]
            return {'targets': targets, 'metabolism': metabolism, 'effects': effects}
        finally:
            conn.close()

    def cache_interaction_result(self, drug_a_id: int, drug_b_id: int, score: float, level: str, mechanisms: str = None, notes: str = None):
        a, b = (drug_a_id, drug_b_id) if drug_a_id <= drug_b_id else (drug_b_id, drug_a_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR REPLACE INTO drug_interaction_cache (drug_a_id, drug_b_id, score, level, mechanisms, notes, timestamp) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", (a, b, score, level, mechanisms, notes))
            conn.commit()
        finally:
            conn.close()

    def get_cached_interaction(self, drug_a_id: int, drug_b_id: int) -> Optional[Dict]:
        a, b = (drug_a_id, drug_b_id) if drug_a_id <= drug_b_id else (drug_b_id, drug_a_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM drug_interaction_cache WHERE drug_a_id = ? AND drug_b_id = ?", (a, b))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def close_connection(self):
        pass

    def clear_interaction_cache(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM drug_interaction_cache")
            conn.commit()
        finally:
            conn.close()

    def force_update_database(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS analog_links")
        cursor.execute("DROP TABLE IF EXISTS drugs")
        conn.commit()
        conn.close()
        self._initialize_database()
        self.populate_sample_data()

    def populate_pharmacology_if_empty(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM drug_targets")
            count = cursor.fetchone()[0]
            if count > 0:
                conn.close()
                return
            sample_map =  {
        
                    'Ибупрофен': {
                        'targets': [('COX1', 'ингибитор', 0.9), ('COX2', 'ингибитор', 0.95), ('PGE2', 'ингибитор', 0.7)],
                        'metabolism': [('CYP2C9', 'субстрат', 0.8), ('CYP2C8', 'субстрат', 0.5)],
                        'effects': [('ЖК-кровотечение', 4), ('Гепатотоксичность', 2), ('Нефротоксичность', 3)]
                    },

                    'Парацетамол': {
                        'targets': [('COX3', 'ингибитор', 0.6), ('TRPV1', 'модулятор', 0.4)],
                        'metabolism': [('CYP2E1', 'субстрат', 0.9), ('CYP1A2', 'субстрат', 0.4)],
                        'effects': [('Гепатотоксичность', 5), ('Сыпь', 2)]
                    },

                    'Амлодипин': {
                        'targets': [('L-type calcium channel', 'ингибитор', 0.85), ('LTCC', 'блокатор', 0.8)],
                        'metabolism': [('CYP3A4', 'субстрат', 0.95), ('CYP3A5', 'субстрат', 0.4)],
                        'effects': [('Гипотензия', 3), ('Отёки', 2), ('Головная боль', 2)]
                    },

                    'Аспирин Кардио': {
                        'targets': [('COX1', 'ингибитор', 0.99), ('Агрегация тромбоцитов', 'ингибитор', 0.95)],
                        'metabolism': [('CYP2C9', 'ингибитор', 0.3), ('Эстеразы', 'субстрат', 0.8)],
                        'effects': [('ЖК-кровотечение', 5), ('Язвообразование', 4)]
                    },

                    'Метопролол': {
                        'targets': [('Beta-1 adrenergic', 'антагонист', 0.95), ('Контроль ЧСС', 'снижение', 0.9)],
                        'metabolism': [('CYP2D6', 'субстрат', 0.9), ('Конъюгация', 'процесс', 0.5)],
                        'effects': [('Брадикардия', 3), ('Гипотензия', 2), ('Утомляемость', 2)]
                    },

                    'Атенолол': {
                        'targets': [('Beta-1 adrenergic', 'антагонист', 0.92), ('Частота сердцебиений', 'снижение', 0.88)],
                        'metabolism': [('Почечная экскреция', 'путь', 0.95), ('Минимальный печёночный', 'метаболизм', 0.1)],
                        'effects': [('Брадикардия', 3), ('Гипотензия', 2)]
                    },

                    'Нимодипин': {
                        'targets': [('Церебральный кальциевый канал', 'блокатор', 0.95), ('L-VSCC', 'ингибитор', 0.9)],
                        'metabolism': [('CYP3A4', 'субстрат', 0.95), ('Первичный проход', 'метаболизм', 0.8)],
                        'effects': [('Церебральная вазодилатация', 5), ('Гипотензия', 2)]
                    },

                    'Спиронолактон': {
                        'targets': [('Альдостероновый рецептор', 'антагонист', 0.95), ('Задержка K+', 'эффект', 0.9)],
                        'metabolism': [('CYP3A4', 'субстрат', 0.7), ('Печёночный метаболизм', 'активные метаболиты', 0.8)],
                        'effects': [('Гиперкалиемия', 4), ('Гинекомастия', 2)]
                    },

                    'Дилтиазем': {
                        'targets': [('Кальциевый канал L-типа', 'ингибитор', 0.9), ('AV-узел', 'замедление', 0.85)],
                        'metabolism': [('CYP3A4', 'субстрат', 0.95), ('CYP3A5', 'субстрат', 0.3)],
                        'effects': [('Брадикардия', 3), ('AV-блокада', 2), ('Отёки', 2)]
                    },

                    'Верапамил': {
                        'targets': [('Кальциевый канал L-типа', 'ингибитор', 0.92), ('SA/AV узлы', 'эффект', 0.9)],
                        'metabolism': [('CYP3A4', 'субстрат', 0.9), ('CYP1A2', 'субстрат', 0.3)],
                        'effects': [('Запор', 4), ('AV-блокада', 3), ('Гипотензия', 2)]
                    },

                    'Флуоксетин': {
                        'targets': [('SERT', 'ингибитор', 0.95), ('Обратный захват серотонина', 'блокатор', 0.95)],
                        'metabolism': [('CYP2D6', 'субстрат', 0.9), ('CYP2C9', 'субстрат', 0.4)],
                        'effects': [('Серотониновый синдром', 2), ('Гипонатриемия', 2)]
                    },

                    'Сертралин': {
                        'targets': [('SERT', 'ингибитор', 0.93), ('Обратный захват допамина', 'слабый ингибитор', 0.3)],
                        'metabolism': [('CYP2D6', 'субстрат', 0.7), ('CYP3A4', 'субстрат', 0.3)],
                        'effects': [('Серотониновый синдром', 2), ('Сексуальная дисфункция', 3)]
                    },

                    'Амитриптилин': {
                        'targets': [('Обратный захват норадреналина', 'ингибитор', 0.95), ('Обратный захват серотонина', 'ингибитор', 0.8)],
                        'metabolism': [('CYP2D6', 'субстрат', 0.9), ('CYP2C19', 'субстрат', 0.7)],
                        'effects': [('Антихолинергические эффекты', 4), ('Кардиотоксичность', 3), ('Гипотензия', 3)]
                    },

                    'Метформин': {
                        'targets': [('AMPK', 'активатор', 0.8), ('Глюконеогенез', 'ингибитор', 0.85)],
                        'metabolism': [('Нет печёночного', 'метаболизма', 0.0), ('Почечная экскреция', 'основная', 0.95)],
                        'effects': [('ЖК-расстройства', 3), ('Лактацидоз', 1), ('Дефицит B12', 2)]
                    },

                    'Глибенкламид': {
                        'targets': [('Калиевый канал', 'блокатор', 0.95), ('Секреция инсулина', 'стимулятор', 0.9)],
                        'metabolism': [('CYP3A4', 'субстрат', 0.8), ('CYP2C9', 'субстрат', 0.6)],
                        'effects': [('Гипогликемия', 4), ('Прибавка в весе', 3)]
                    },

                    'Статины': {
                        'targets': [('HMG-CoA редуктаза', 'ингибитор', 0.95)],
                        'metabolism': [('CYP3A4', 'субстрат', 0.85)],
                        'effects': [('Миопатия', 2), ('Дисфункция печени', 1)]
                    },

                    'Лизиноприл': {
                        'targets': [('АПФ', 'ингибитор', 0.95), ('Потенцирование кининов', 'эффект', 0.8)],
                        'metabolism': [('Нет печёночного', 'метаболизма', 0.0), ('Почечная экскреция', 'основная', 0.95)],
                        'effects': [('Кашель', 3), ('Ангиоотёк', 1), ('Гиперкалиемия', 2)]
                    },

                    'Эналаприл': {
                        'targets': [('АПФ', 'ингибитор', 0.93), ('Ангиотензин II', 'снижение', 0.9)],
                        'metabolism': [('Гидролиз эстеразами', 'пролекарство', 0.95), ('Почечная экскреция', 'активный метаболит', 0.9)],
                        'effects': [('Кашель', 3), ('Гипотензия', 2)]
                    },

                    'Лозартан': {
                        'targets': [('AT1-рецептор', 'антагонист', 0.95), ('Ангиотензин II', 'блокатор', 0.95)],
                        'metabolism': [('CYP2C9', 'субстрат', 0.8), ('Глюкуронирование', 'путь', 0.6)],
                        'effects': [('Гиперкалиемия', 2), ('Гипотензия', 2)]
                    },

                    'Валсартан': {
                        'targets': [('AT1-рецептор', 'антагонист', 0.94), ('Ангиотензин II', 'блокирование', 0.93)],
                        'metabolism': [('CYP2C9', 'субстрат', 0.7), ('CYP3A4', 'незначительно', 0.2)],
                        'effects': [('Гиперкалиемия', 2), ('Головокружение', 2)]
                    },

                    'ДПП-4 ингибиторы': {
                        'targets': [('Фермент DPP-4', 'ингибитор', 0.95)],
                        'metabolism': [('CYP3A4', 'субстрат', 0.6)],
                        'effects': [('Панкреатит', 1), ('Гипогликемия редкая', 1)]
                    },

                    'Инсулины': {
                        'targets': [('Инсулиновый рецептор', 'агонист', 1.0), ('Поглощение глюкозы', 'стимулятор', 1.0)],
                        'metabolism': [('Протеазное расщепление', 'основной путь', 0.9)],
                        'effects': [('Гипогликемия', 5), ('Липодистрофия', 2)]
                    }
                }

            for name, pdata in sample_map.items():
                cursor.execute("SELECT id FROM drugs WHERE name LIKE ?", (f'%{name}%',))
                rows = cursor.fetchall()
                for row in rows:
                    did = row[0]
                    for tname, etype, pot in pdata.get('targets', []):
                        cursor.execute("INSERT OR IGNORE INTO drug_targets (drug_id, target_name, effect_type, potency) VALUES (?, ?, ?, ?)", (did, tname, etype, pot))
                    for ename, role, rate in pdata.get('metabolism', []):
                        cursor.execute("INSERT OR IGNORE INTO drug_metabolism (drug_id, enzyme_name, role, rate) VALUES (?, ?, ?, ?)", (did, ename, role, rate))
                    for ename, lvl in pdata.get('effects', []):
                        cursor.execute("INSERT OR IGNORE INTO drug_effect_profile (drug_id, effect_name, level) VALUES (?, ?, ?)", (did, ename, lvl))
            conn.commit()
            conn.close()
            try:
                self.clear_interaction_cache()
            except Exception:
                pass
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    def populate_sample_data(self):
        json_file = "drugs_data.json"
        if not os.path.exists(json_file):
            print(f"Файл {json_file} не найден. База данных будет пустой.")
            return
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                sample_drugs = json.load(f)
        except Exception as e:
            print(f"Ошибка при загрузке файла {json_file}: {e}")
            return
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM drugs")
        existing_count = cursor.fetchone()[0]
        conn.close()
        expected_count = len(sample_drugs)
        if existing_count >= expected_count:
            return
        if existing_count > 0:
            print(f"Обновление базы данных: найдено {existing_count} препаратов, требуется {expected_count}. Перезаполнение...")
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM drugs")
            cursor.execute("DELETE FROM analog_links")
            conn.commit()
            conn.close()
        else:
            print(f"Заполнение базы данных: добавление {expected_count} препаратов...")
        for drug_data in sample_drugs:
            self.add_drug(drug_data['name'], drug_data['substance'], drug_data['form'], drug_data['manufacturer'], drug_data['price'], drug_data.get('contraindications', '') or '', drug_data.get('description', '') or '')
        print(f"База данных успешно обновлена: {expected_count} препаратов")

