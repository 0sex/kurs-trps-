"""
Database module for the drug analog search application.

This module handles all database operations including initialization,
CRUD operations for drugs and analog links, and data queries.
"""

import sqlite3
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class Database:
    """Manages SQLite database operations for drug analog search system."""
    
    def __init__(self, db_path: str = "drugs.db"):
        """
        Initialize the database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._initialize_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection.
        
        Returns:
            SQLite connection object
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _initialize_database(self):
        """Create database tables if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Create drugs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drugs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                substance TEXT NOT NULL,
                form TEXT NOT NULL,
                manufacturer TEXT NOT NULL,
                price REAL NOT NULL,
                contraindications TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add contraindications column if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE drugs ADD COLUMN contraindications TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # Create analog_links table
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
        
        # Create indexes for better search performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_substance ON drugs(substance)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_name ON drugs(name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_contraindications ON drugs(contraindications)
        """)
        
        conn.commit()
        conn.close()
    
    def add_drug(self, name: str, substance: str, form: str, 
                 manufacturer: str, price: float, contraindications: str = '') -> int:
        """
        Add a new drug to the database.
        
        Args:
            name: Drug name
            substance: Active substance(s), can be multiple separated by '+' or ','
            form: Release form
            manufacturer: Manufacturer name
            price: Price in currency units
            contraindications: Contraindications, separated by ',' or ';'
            
        Returns:
            ID of the inserted drug
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO drugs (name, substance, form, manufacturer, price, contraindications)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, substance, form, manufacturer, price, contraindications))
            conn.commit()
            drug_id = cursor.lastrowid
            return drug_id
        finally:
            conn.close()
    
    def get_drug_by_id(self, drug_id: int) -> Optional[Dict]:
        """
        Get drug by ID.
        
        Args:
            drug_id: Drug ID
            
        Returns:
            Dictionary with drug data or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM drugs WHERE id = ?", (drug_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
        finally:
            conn.close()
    
    def get_drugs_by_substance(self, substance: str) -> List[Dict]:
        """
        Get all drugs with specified active substance.
        Supports multiple substances - finds drugs that contain at least one matching substance.
        
        Args:
            substance: Active substance name or multiple substances separated by '+' or ','
            
        Returns:
            List of drug dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Split substances by common delimiters
            substances = [s.strip() for s in substance.replace('+', ',').split(',') if s.strip()]
            
            if not substances:
                return []
            
            # Build query to match any of the substances
            # Check if any of the substances appears in the drug's substance field
            placeholders = ' OR '.join(['substance LIKE ?'] * len(substances))
            params = [f'%{sub}%' for sub in substances]
            
            cursor.execute(f"""
                SELECT * FROM drugs 
                WHERE {placeholders}
                ORDER BY price
            """, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def search_drugs_by_name(self, query: str) -> List[Dict]:
        """
        Search drugs by name (case-insensitive partial match).
        
        Args:
            query: Search query
            
        Returns:
            List of matching drug dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM drugs 
                WHERE name LIKE ?
                ORDER BY name
            """, (f"%{query}%",))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_all_drugs(self) -> List[Dict]:
        """
        Get all drugs from database.
        
        Returns:
            List of all drug dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM drugs ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def update_drug(self, drug_id: int, name: str, substance: str, 
                   form: str, manufacturer: str, price: float, contraindications: str = '') -> bool:
        """
        Update drug information.
        
        Args:
            drug_id: Drug ID to update
            name: New name
            substance: New substance
            form: New form
            manufacturer: New manufacturer
            price: New price
            contraindications: New contraindications
            
        Returns:
            True if update successful, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE drugs 
                SET name = ?, substance = ?, form = ?, manufacturer = ?, price = ?, contraindications = ?
                WHERE id = ?
            """, (name, substance, form, manufacturer, price, contraindications, drug_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def delete_drug(self, drug_id: int) -> bool:
        """
        Delete drug from database.
        
        Args:
            drug_id: Drug ID to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Delete analog links first
            cursor.execute("DELETE FROM analog_links WHERE drug_id = ? OR analog_id = ?", 
                         (drug_id, drug_id))
            # Delete drug
            cursor.execute("DELETE FROM drugs WHERE id = ?", (drug_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def add_analog_link(self, drug_id: int, analog_id: int, 
                       similarity_score: float = 1.0) -> bool:
        """
        Add analog link between two drugs.
        
        Args:
            drug_id: First drug ID
            analog_id: Analog drug ID
            similarity_score: Similarity score (default: 1.0)
            
        Returns:
            True if successful, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO analog_links (drug_id, analog_id, similarity_score)
                VALUES (?, ?, ?)
            """, (drug_id, analog_id, similarity_score))
            conn.commit()
            return True
        except sqlite3.Error:
            return False
        finally:
            conn.close()
    
    def get_analogs(self, drug_id: int) -> List[Tuple[Dict, float]]:
        """
        Get analog drugs for a given drug.
        
        Args:
            drug_id: Drug ID
            
        Returns:
            List of tuples (drug_dict, similarity_score)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT d.*, a.similarity_score 
                FROM drugs d
                JOIN analog_links a ON d.id = a.analog_id
                WHERE a.drug_id = ?
                ORDER BY a.similarity_score DESC, d.price
            """, (drug_id,))
            return [(dict(row), row['similarity_score']) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_drugs_by_filters(self, form: Optional[str] = None, 
                            manufacturer: Optional[str] = None,
                            min_price: Optional[float] = None,
                            max_price: Optional[float] = None,
                            exclude_contraindication: Optional[str] = None) -> List[Dict]:
        """
        Get drugs filtered by criteria.
        
        Args:
            form: Filter by release form
            manufacturer: Filter by manufacturer
            min_price: Minimum price
            max_price: Maximum price
            exclude_contraindication: Exclude drugs containing this contraindication
            
        Returns:
            List of matching drug dictionaries
        """
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
        """
        Get all unique contraindications from database.
        
        Returns:
            List of unique contraindication names
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT DISTINCT contraindications FROM drugs WHERE contraindications IS NOT NULL AND contraindications != ''")
            all_contraindications = set()
            for row in cursor.fetchall():
                contraindications = row[0]
                if contraindications:
                    # Split by common delimiters
                    for delim in [',', ';', '+']:
                        contraindications = contraindications.replace(delim, ',')
                    items = [c.strip() for c in contraindications.split(',') if c.strip()]
                    all_contraindications.update(items)
            return sorted(list(all_contraindications))
        finally:
            conn.close()
    
    def get_all_forms(self) -> List[str]:
        """
        Get all unique release forms.
        
        Returns:
            List of unique form names
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT DISTINCT form FROM drugs ORDER BY form")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def get_all_manufacturers(self) -> List[str]:
        """
        Get all unique manufacturers.
        
        Returns:
            List of unique manufacturer names
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT DISTINCT manufacturer FROM drugs ORDER BY manufacturer")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def populate_sample_data(self):
        """Populate database with sample drug data for demonstration."""
        # Format: (name, substance, form, manufacturer, price, contraindications)
        sample_drugs = [
            # Обезболивающие и жаропонижающие
            ("Парацетамол", "Парацетамол", "Таблетки", "ОАО Фармстандарт", 45.50, "Печеночная недостаточность, Алкоголизм"),
            ("Парацетамол-МСК", "Парацетамол", "Таблетки", "Медисорб", 38.00, "Печеночная недостаточность"),
            ("Панадол", "Парацетамол", "Таблетки", "GlaxoSmithKline", 120.00, "Печеночная недостаточность, Детский возраст до 3 лет"),
            ("Эффералган", "Парацетамол", "Шипучие таблетки", "UPSA", 185.00, "Печеночная недостаточность"),
            ("Ибупрофен", "Ибупрофен", "Таблетки 200 мг", "ОАО Татхимфармпрепараты", 55.00, "Язвенная болезнь, Беременность 3 триместр"),
            ("Нурофен", "Ибупрофен", "Таблетки 200 мг", "Reckitt Benckiser", 185.00, "Язвенная болезнь, Беременность 3 триместр"),
            ("Ибуклин", "Ибупрофен + Парацетамол", "Таблетки", "Dr. Reddy's", 95.00, "Язвенная болезнь, Печеночная недостаточность"),
            ("Аспирин Кардио", "Ацетилсалициловая кислота", "Таблетки кишечнорастворимые", "Bayer", 145.00, "Язвенная болезнь, Бронхиальная астма"),
            ("Тромбо АСС", "Ацетилсалициловая кислота", "Таблетки кишечнорастворимые", "G.L. Pharma", 98.00, "Язвенная болезнь, Бронхиальная астма"),
            ("Кардиомагнил", "Ацетилсалициловая кислота + Магния гидроксид", "Таблетки", "Nycomed", 160.00, "Язвенная болезнь, Бронхиальная астма"),
            ("Анальгин", "Метамизол натрия", "Таблетки", "Фармстандарт", 42.00, "Бронхиальная астма, Беременность"),
            ("Кетанов", "Кеторолак", "Таблетки", "Dr. Reddy's", 125.00, "Язвенная болезнь, Почечная недостаточность"),
            ("Найз", "Нимесулид", "Таблетки", "Dr. Reddy's", 185.00, "Язвенная болезнь, Печеночная недостаточность"),
            ("Диклофенак", "Диклофенак", "Таблетки", "ОАО Биохимик", 58.00, "Язвенная болезнь, Сердечная недостаточность"),
            ("Вольтарен", "Диклофенак", "Таблетки", "Novartis", 280.00, "Язвенная болезнь, Сердечная недостаточность"),
            
            # Антибиотики
            ("Амоксициллин", "Амоксициллин", "Капсулы 500 мг", "ОАО Биохимик", 125.00, "Аллергия на пенициллины, Инфекционный мононуклеоз"),
            ("Амоксиклав", "Амоксициллин + Клавулановая кислота", "Таблетки", "Sandoz", 280.00, "Аллергия на пенициллины, Печеночная недостаточность"),
            ("Аугментин", "Амоксициллин + Клавулановая кислота", "Таблетки", "GlaxoSmithKline", 350.00, "Аллергия на пенициллины, Печеночная недостаточность"),
            ("Флемоксин Солютаб", "Амоксициллин", "Таблетки диспергируемые", "Astellas", 320.00, "Аллергия на пенициллины"),
            ("Азитромицин", "Азитромицин", "Капсулы", "ОАО Верофарм", 145.00, "Печеночная недостаточность, Беременность"),
            ("Сумамед", "Азитромицин", "Таблетки", "Pfizer", 420.00, "Печеночная недостаточность, Беременность"),
            ("Цефтриаксон", "Цефтриаксон", "Порошок для инъекций", "ОАО Синтез", 38.00, "Аллергия на цефалоспорины, Беременность"),
            ("Цефалексин", "Цефалексин", "Капсулы", "ОАО Синтез", 95.00, "Аллергия на цефалоспорины"),
            ("Ципрофлоксацин", "Ципрофлоксацин", "Таблетки", "ОАО Биохимик", 78.00, "Беременность, Детский возраст до 18 лет"),
            ("Цифран", "Ципрофлоксацин", "Таблетки", "Dr. Reddy's", 195.00, "Беременность, Детский возраст до 18 лет"),
            ("Левофлоксацин", "Левофлоксацин", "Таблетки", "ОАО Биохимик", 165.00, "Беременность, Эпилепсия"),
            ("Тетрациклин", "Тетрациклин", "Таблетки", "ОАО Биохимик", 45.00, "Беременность, Детский возраст до 8 лет"),
            ("Доксициклин", "Доксициклин", "Капсулы", "ОАО Синтез", 68.00, "Беременность, Детский возраст до 8 лет"),
            ("Кларитромицин", "Кларитромицин", "Таблетки", "ОАО Синтез", 185.00, "Печеночная недостаточность, Беременность"),
            ("Клацид", "Кларитромицин", "Таблетки", "Abbott", 420.00, "Печеночная недостаточность, Беременность"),
            
            # Антигистаминные
            ("Лоратадин", "Лоратадин", "Таблетки 10 мг", "ОАО Атолл", 45.00, "Беременность, Период лактации"),
            ("Кларитин", "Лоратадин", "Таблетки 10 мг", "Schering-Plough", 220.00, "Беременность, Период лактации"),
            ("Цетрин", "Цетиризин", "Таблетки 10 мг", "Dr. Reddy's", 165.00, "Беременность, Почечная недостаточность"),
            ("Зиртек", "Цетиризин", "Таблетки 10 мг", "UCB Pharma", 195.00, "Беременность, Почечная недостаточность"),
            ("Зодак", "Цетиризин", "Таблетки", "Zentiva", 145.00, "Беременность, Почечная недостаточность"),
            ("Супрастин", "Хлоропирамин", "Таблетки", "Egis", 125.00, "Бронхиальная астма, Глаукома"),
            ("Тавегил", "Клемастин", "Таблетки", "Novartis", 185.00, "Бронхиальная астма, Глаукома"),
            ("Димедрол", "Дифенгидрамин", "Таблетки", "ОАО Татхимфармпрепараты", 35.00, "Бронхиальная астма, Глаукома"),
            ("Фенистил", "Диметинден", "Капли", "Novartis", 380.00, "Бронхиальная астма, Глаукома"),
            ("Эриус", "Дезлоратадин", "Таблетки", "Schering-Plough", 420.00, "Беременность, Период лактации"),
            
            # Сердечно-сосудистые
            ("Эналаприл", "Эналаприл", "Таблетки 10 мг", "Фармастандарт", 78.00, "Беременность, Стеноз почечных артерий"),
            ("Ренитек", "Эналаприл", "Таблетки 10 мг", "Merck", 420.00, "Беременность, Стеноз почечных артерий"),
            ("Лизиноприл", "Лизиноприл", "Таблетки", "ОАО Верофарм", 95.00, "Беременность, Стеноз почечных артерий"),
            ("Диротон", "Лизиноприл", "Таблетки", "Gedeon Richter", 185.00, "Беременность, Стеноз почечных артерий"),
            ("Амлодипин", "Амлодипин", "Таблетки", "ОАО Верофарм", 125.00, "Шок, Сердечная недостаточность"),
            ("Норваск", "Амлодипин", "Таблетки", "Pfizer", 580.00, "Шок, Сердечная недостаточность"),
            ("Бисопролол", "Бисопролол", "Таблетки", "ОАО Верофарм", 145.00, "Сердечная недостаточность, Бронхиальная астма"),
            ("Конкор", "Бисопролол", "Таблетки", "Merck", 380.00, "Сердечная недостаточность, Бронхиальная астма"),
            ("Метопролол", "Метопролол", "Таблетки", "ОАО Верофарм", 98.00, "Сердечная недостаточность, Бронхиальная астма"),
            ("Эгилок", "Метопролол", "Таблетки", "Egis", 185.00, "Сердечная недостаточность, Бронхиальная астма"),
            ("Атенолол", "Атенолол", "Таблетки", "ОАО Верофарм", 68.00, "Сердечная недостаточность, Бронхиальная астма"),
            ("Верапамил", "Верапамил", "Таблетки", "ОАО Биохимик", 85.00, "Сердечная недостаточность, АВ-блокада"),
            ("Дилтиазем", "Дилтиазем", "Таблетки", "ОАО Биохимик", 125.00, "Сердечная недостаточность, АВ-блокада"),
            ("Каптоприл", "Каптоприл", "Таблетки", "ОАО Биохимик", 58.00, "Беременность, Стеноз почечных артерий"),
            ("Валсартан", "Валсартан", "Таблетки", "ОАО Верофарм", 185.00, "Беременность, Стеноз почечных артерий"),
            ("Лозап", "Лозартан", "Таблетки", "Zentiva", 280.00, "Беременность, Стеноз почечных артерий"),
            ("Нитроглицерин", "Нитроглицерин", "Таблетки", "ОАО Фармстандарт", 45.00, "Гипотензия, Глаукома"),
            
            # Желудочно-кишечные
            ("Омепразол", "Омепразол", "Капсулы", "ОАО Верофарм", 95.00, "Беременность, Детский возраст до 18 лет"),
            ("Омез", "Омепразол", "Капсулы", "Dr. Reddy's", 185.00, "Беременность, Детский возраст до 18 лет"),
            ("Ранитидин", "Ранитидин", "Таблетки", "ОАО Биохимик", 68.00, "Беременность, Почечная недостаточность"),
            ("Фамотидин", "Фамотидин", "Таблетки", "ОАО Биохимик", 125.00, "Беременность, Почечная недостаточность"),
            ("Алмагель", "Алюминия гидроксид + Магния гидроксид", "Суспензия", "Balkanpharma", 145.00, "Почечная недостаточность"),
            ("Маалокс", "Алюминия гидроксид + Магния гидроксид", "Суспензия", "Sanofi", 185.00, "Почечная недостаточность"),
            ("Смекта", "Диосмектит", "Порошок", "Ipsen", 125.00, "Кишечная непроходимость"),
            ("Энтеросгель", "Полиметилсилоксана полигидрат", "Паста", "ТНК Силма", 280.00, ""),
            ("Лоперамид", "Лоперамид", "Таблетки", "ОАО Биохимик", 45.00, "Кишечная непроходимость, Язвенный колит"),
            ("Имодиум", "Лоперамид", "Таблетки", "Johnson & Johnson", 185.00, "Кишечная непроходимость, Язвенный колит"),
            ("Мезим", "Панкреатин", "Таблетки", "Berlin-Chemie", 145.00, "Острый панкреатит"),
            ("Креон", "Панкреатин", "Капсулы", "Abbott", 420.00, "Острый панкреатит"),
            ("Фестал", "Панкреатин + Желчь", "Таблетки", "Sanofi", 185.00, "Острый панкреатит, Гепатит"),
            
            # Отхаркивающие и противокашлевые
            ("Амброксол", "Амброксол", "Таблетки", "ОАО Верофарм", 85.00, "Беременность 1 триместр, Язвенная болезнь"),
            ("Лазолван", "Амброксол", "Сироп", "Boehringer Ingelheim", 280.00, "Беременность 1 триместр, Язвенная болезнь"),
            ("АЦЦ", "Ацетилцистеин", "Таблетки шипучие", "Sandoz", 185.00, "Язвенная болезнь, Беременность"),
            ("Бромгексин", "Бромгексин", "Таблетки", "ОАО Биохимик", 58.00, "Язвенная болезнь, Беременность 1 триместр"),
            ("Синекод", "Бутамират", "Сироп", "Novartis", 280.00, "Беременность 1 триместр"),
            ("Стоптуссин", "Бутамират + Гвайфенезин", "Таблетки", "Teva", 185.00, "Беременность 1 триместр"),
            
            # Противовирусные
            ("Арбидол", "Умифеновир", "Капсулы", "Фармстандарт", 280.00, "Беременность, Детский возраст до 3 лет"),
            ("Кагоцел", "Кагоцел", "Таблетки", "Ниармедик", 185.00, "Беременность, Непереносимость лактозы"),
            ("Ингавирин", "Имидазолилэтанамид пентандиовой кислоты", "Капсулы", "Валента Фарма", 380.00, "Беременность, Детский возраст до 18 лет"),
            ("Тамифлю", "Осельтамивир", "Капсулы", "Roche", 980.00, "Беременность, Почечная недостаточность"),
            ("Ацикловир", "Ацикловир", "Таблетки", "ОАО Синтез", 125.00, "Беременность, Почечная недостаточность"),
            ("Зовиракс", "Ацикловир", "Таблетки", "GlaxoSmithKline", 420.00, "Беременность, Поречная недостаточность"),
            
            # Успокоительные и снотворные
            ("Валериана", "Экстракт валерианы", "Таблетки", "ОАО Фармстандарт", 45.00, ""),
            ("Ново-Пассит", "Комбинированный растительный", "Таблетки", "Teva", 185.00, "Миастения"),
            ("Персен", "Экстракт валерианы + Мята + Мелисса", "Таблетки", "Lek", 280.00, ""),
            ("Глицин", "Глицин", "Таблетки", "ОАО Биотики", 58.00, ""),
            ("Афобазол", "Фабомотизол", "Таблетки", "Фармстандарт", 380.00, "Беременность, Детский возраст до 18 лет"),
            ("Фенибут", "Аминофенилмасляная кислота", "Таблетки", "ОАО Органика", 185.00, "Беременность, Почечная недостаточность"),
            
            # Витамины и БАДы
            ("Компливит", "Поливитамины", "Таблетки", "Фармстандарт", 185.00, "Гипервитаминоз"),
            ("Витрум", "Поливитамины", "Таблетки", "Unipharm", 420.00, "Гипервитаминоз"),
            ("Центрум", "Поливитамины", "Таблетки", "Pfizer", 580.00, "Гипервитаминоз"),
            ("Аскорбиновая кислота", "Витамин C", "Таблетки", "ОАО Фармстандарт", 35.00, "Гипервитаминоз C"),
            ("Рыбий жир", "Омега-3", "Капсулы", "Тева", 185.00, "Гипервитаминоз A, D"),
            ("Кальций Д3", "Кальций + Витамин D3", "Таблетки", "Никомед", 280.00, "Гиперкальциемия"),
            ("Магний B6", "Магний + Витамин B6", "Таблетки", "Sanofi", 380.00, "Почечная недостаточность"),
            
            # Противогрибковые
            ("Флуконазол", "Флуконазол", "Капсулы", "ОАО Верофарм", 85.00, "Беременность, Почечная недостаточность"),
            ("Дифлюкан", "Флуконазол", "Капсулы", "Pfizer", 580.00, "Беременность, Поречная недостаточность"),
            ("Нистатин", "Нистатин", "Таблетки", "ОАО Биохимик", 45.00, "Язвенная болезнь"),
            ("Клотримазол", "Клотримазол", "Крем", "ОАО Биохимик", 58.00, ""),
            ("Пимафуцин", "Натамицин", "Свечи", "Astellas", 420.00, ""),
            
            # Противопаразитарные
            ("Мебендазол", "Мебендазол", "Таблетки", "ОАО Верофарм", 95.00, "Беременность, Язвенный колит"),
            ("Вермокс", "Мебендазол", "Таблетки", "Janssen", 185.00, "Беременность, Язвенный колит"),
            ("Пирантел", "Пирантел", "Таблетки", "ОАО Верофарм", 68.00, "Беременность, Печеночная недостаточность"),
            ("Декарис", "Левамизол", "Таблетки", "Gedeon Richter", 145.00, "Беременность, Агранулоцитоз"),
            
            # Противовоспалительные мази
            ("Гидрокортизон", "Гидрокортизон", "Мазь", "ОАО Биохимик", 58.00, "Грибковые инфекции, Вирусные инфекции"),
            ("Преднизолон", "Преднизолон", "Мазь", "ОАО Биохимик", 45.00, "Грибковые инфекции, Вирусные инфекции"),
            ("Троксевазин", "Троксерутин", "Гель", "Balkanpharma", 185.00, ""),
            ("Фастум гель", "Кетопрофен", "Гель", "A.Menarini", 280.00, "Язвенная болезнь, Беременность 3 триместр"),
            ("Долгит", "Ибупрофен", "Крем", "Доктор Редди'с", 185.00, "Язвенная болезнь, Беременность 3 триместр"),
            
            # Глазные капли
            ("Альбуцид", "Сульфацетамид", "Капли", "ОАО Синтез", 45.00, "Аллергия на сульфаниламиды"),
            ("Тобрекс", "Тобрамицин", "Капли", "Alcon", 185.00, "Грибковые инфекции"),
            ("Офтальмоферон", "Интерферон альфа-2b", "Капли", "Фирн М", 280.00, "Аллергия на интерферон"),
            ("Визин", "Тетризолин", "Капли", "Johnson & Johnson", 185.00, "Глаукома, Детский возраст до 2 лет"),
            
            # Ушные капли
            ("Отипакс", "Феназон + Лидокаин", "Капли", "Biocodex", 280.00, "Повреждение барабанной перепонки"),
            ("Отинум", "Холина салицилат", "Капли", "Teva", 185.00, "Повреждение барабанной перепонки"),
            
            # Назальные капли и спреи
            ("Називин", "Оксиметазолин", "Спрей", "Merck", 145.00, "Глаукома, Атрофический ринит"),
            ("Тизин", "Ксилометазолин", "Спрей", "Novartis", 185.00, "Глаукома, Атрофический ринит"),
            ("Снуп", "Ксилометазолин", "Спрей", "Stada", 125.00, "Глаукома, Атрофический ринит"),
            ("Аква Марис", "Морская вода", "Спрей", "Jadran", 280.00, ""),
            ("Пиносол", "Масла сосны, эвкалипта, мяты", "Капли", "Zentiva", 145.00, "Аллергический ринит"),
            
            # Спазмолитики
            ("Но-шпа", "Дротаверин", "Таблетки", "Sanofi", 185.00, "Сердечная недостаточность, Глаукома"),
            ("Спазмалгон", "Метамизол + Питофенон + Фенпивериния бромид", "Таблетки", "Balkanpharma", 145.00, "Глаукома, Бронхиальная астма"),
            ("Папаверин", "Папаверин", "Таблетки", "ОАО Биохимик", 35.00, "Глаукома, AV-блокада"),
            
            # Мочегонные
            ("Фуросемид", "Фуросемид", "Таблетки", "ОАО Биохимик", 45.00, "Почечная недостаточность, Беременность"),
            ("Лазикс", "Фуросемид", "Таблетки", "Sanofi", 185.00, "Поречная недостаточность, Беременность"),
            ("Верошпирон", "Спиронолактон", "Таблетки", "Gedeon Richter", 185.00, "Почечная недостаточность, Беременность"),
            ("Гипотиазид", "Гидрохлортиазид", "Таблетки", "Egis", 95.00, "Почечная недостаточность, Подагра"),
            
            # Антидепрессанты
            ("Амитриптилин", "Амитриптилин", "Таблетки", "ОАО Биохимик", 125.00, "Глаукома, Беременность"),
            ("Флуоксетин", "Флуоксетин", "Капсулы", "ОАО Верофарм", 185.00, "Беременность, Эпилепсия"),
            ("Прозак", "Флуоксетин", "Капсулы", "Eli Lilly", 580.00, "Беременность, Эпилепсия"),
            
            # Ноотропы
            ("Пирацетам", "Пирацетам", "Таблетки", "ОАО Верофарм", 95.00, "Почечная недостаточность, Геморрагический инсульт"),
            ("Ноотропил", "Пирацетам", "Капсулы", "UCB Pharma", 380.00, "Поречная недостаточность, Геморрагический инсульт"),
            ("Фенотропил", "Фенотропил", "Таблетки", "ОАО Валента", 580.00, "Беременность, Почечная недостаточность"),
            ("Церебролизин", "Церебролизин", "Раствор для инъекций", "EVER Neuro Pharma", 1250.00, "Беременность, Почечная недостаточность"),
            
            # Противоэпилептические
            ("Карбамазепин", "Карбамазепин", "Таблетки", "ОАО Верофарм", 125.00, "Беременность, AV-блокада"),
            ("Вальпроевая кислота", "Вальпроевая кислота", "Таблетки", "ОАО Верофарм", 185.00, "Беременность, Печеночная недостаточность"),
            
            # Противоопухолевые
            ("Метотрексат", "Метотрексат", "Таблетки", "ОАО Верофарм", 285.00, "Беременность, Почечная недостаточность"),
            ("Циклофосфамид", "Циклофосфамид", "Таблетки", "ОАО Верофарм", 450.00, "Беременность, Почечная недостаточность"),
            
            # Иммуномодуляторы
            ("Интерферон", "Интерферон альфа", "Суппозитории", "Фирн М", 185.00, "Аллергия на интерферон"),
            ("Виферон", "Интерферон альфа-2b", "Суппозитории", "Ферон", 280.00, "Аллергия на интерферон"),
            ("Циклоферон", "Акридонуксусная кислота", "Таблетки", "Полисан", 185.00, "Беременность, Цирроз печени"),
            
            # Препараты для мужчин
            ("Виагра", "Силденафил", "Таблетки", "Pfizer", 580.00, "Сердечная недостаточность, Прием нитратов"),
            ("Сиалис", "Тадалафил", "Таблетки", "Eli Lilly", 680.00, "Сердечная недостаточность, Прием нитратов"),
            ("Простамол Уно", "Экстракт плодов пальмы сабаля", "Капсулы", "Berlin-Chemie", 580.00, ""),
            
            # Препараты для женщин
            ("Дюфастон", "Дидрогестерон", "Таблетки", "Abbott", 580.00, "Беременность (осторожно)"),
            ("Утрожестан", "Прогестерон", "Капсулы", "Besins Healthcare", 420.00, "Беременность (осторожно)"),
            ("Регулон", "Этинилэстрадиол + Дезогестрел", "Таблетки", "Gedeon Richter", 380.00, "Тромбоз, Беременность"),
        ]
        
        # Check if database needs to be populated or updated
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM drugs")
        existing_count = cursor.fetchone()[0]
        conn.close()
        
        expected_count = len(sample_drugs)
        
        # If database already has all drugs, skip
        if existing_count >= expected_count:
            return
        
        # If database has some drugs but not all, clear and repopulate
        # Or if database is empty, populate
        if existing_count > 0:
            # Clear existing data to repopulate with full dataset
            print(f"Обновление базы данных: найдено {existing_count} препаратов, требуется {expected_count}. Перезаполнение...")
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM drugs")
            cursor.execute("DELETE FROM analog_links")
            conn.commit()
            conn.close()
        else:
            print(f"Заполнение базы данных: добавление {expected_count} препаратов...")
        
        # Add sample drugs
        for drug_data in sample_drugs:
            self.add_drug(*drug_data)
        
        print(f"База данных успешно обновлена: {expected_count} препаратов")

