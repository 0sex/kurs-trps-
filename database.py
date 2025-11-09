"""
Database module for the drug analog search application.

This module handles all database operations including initialization,
CRUD operations for drugs and analog links, and data queries.
"""

import sqlite3
import json
import os
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
        
        # Add description column if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE drugs ADD COLUMN description TEXT DEFAULT ''")
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
                 manufacturer: str, price: float, contraindications: str = '', 
                 description: str = '') -> int:
        """
        Add a new drug to the database.
        
        Args:
            name: Drug name
            substance: Active substance(s), can be multiple separated by '+' or ','
            form: Release form
            manufacturer: Manufacturer name
            price: Price in currency units
            contraindications: Contraindications, separated by ',' or ';'
            description: Description of drug action and usage
            
        Returns:
            ID of the inserted drug
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO drugs (name, substance, form, manufacturer, price, contraindications, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, substance, form, manufacturer, price, contraindications, description))
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
                   form: str, manufacturer: str, price: float, contraindications: str = '', 
                   description: str = '') -> bool:
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
            description: New description of drug action and usage
            
        Returns:
            True if update successful, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE drugs 
                SET name = ?, substance = ?, form = ?, manufacturer = ?, price = ?, contraindications = ?, description = ?
                WHERE id = ?
            """, (name, substance, form, manufacturer, price, contraindications, description, drug_id))
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
        # Load data from JSON file
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
            self.add_drug(
                drug_data['name'],
                drug_data['substance'],
                drug_data['form'],
                drug_data['manufacturer'],
                drug_data['price'],
                drug_data.get('contraindications', '') or '',
                drug_data.get('description', '') or ''
            )
        
        print(f"База данных успешно обновлена: {expected_count} препаратов")
        
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

