"""
Unit tests for the SearchEngine module.

Tests search functionality, filtering, and comparison logic.
"""

import unittest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from search_engine import SearchEngine


class TestSearchEngine(unittest.TestCase):
    """Test cases for SearchEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Use separate test database
        self.test_db_path = "test_drugs.db"
        
        # Remove test database if exists
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        
        self.database = Database(self.test_db_path)
        self.search_engine = SearchEngine(self.database)
        
        # Add test data
        self._add_test_drugs()
    
    def tearDown(self):
        """Clean up after tests."""
        # Close database connections
        if hasattr(self, 'database'):
            self.database = None
        
        # Remove test database
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
    
    def _add_test_drugs(self):
        """Add test drugs to database."""
        self.database.add_drug(
            "Аспирин", "Ацетилсалициловая кислота", "Таблетки", 
            "Bayer", 150.00
        )
        self.database.add_drug(
            "Тромбо АСС", "Ацетилсалициловая кислота", 
            "Таблетки кишечнорастворимые", "G.L. Pharma", 100.00
        )
        self.database.add_drug(
            "Парацетамол", "Парацетамол", "Таблетки", 
            "Фармстандарт", 50.00
        )
        self.database.add_drug(
            "Панадол", "Парацетамол", "Таблетки", 
            "GlaxoSmithKline", 120.00
        )
        self.database.add_drug(
            "Ибупрофен", "Ибупрофен", "Таблетки", 
            "Татхимфармпрепараты", 60.00
        )
    
    def test_find_analogs_by_name(self):
        """Test finding analogs by drug name."""
        results = self.search_engine.find_analogs("Аспирин")
        
        self.assertGreater(len(results), 0, "Should find at least one analog")
        self.assertTrue(
            any(drug['name'] == 'Тромбо АСС' for drug, _ in results),
            "Should find Тромбо АСС as analog of Аспирин"
        )
    
    def test_no_analogs_for_unique_drug(self):
        """Test that drugs without analogs return empty results."""
        results = self.search_engine.find_analogs("Ибупрофен")
        
        # Ибупрофен has only one entry, so should have no analogs
        self.assertEqual(len(results), 0, 
                        "Drug with no analogs should return empty results")
    
    def test_similarity_calculation(self):
        """Test similarity score calculation."""
        drug1 = {"substance": "Test", "form": "Таблетки", 
                "manufacturer": "TestCorp", "price": 100.0}
        drug2 = {"substance": "Test", "form": "Таблетки", 
                "manufacturer": "TestCorp", "price": 100.0}
        
        similarity = self.search_engine._calculate_similarity(drug1, drug2)
        
        # Maximum similarity with all matching attributes
        self.assertAlmostEqual(similarity, 1.7, places=1,
                              msg="Maximum similarity should be around 1.7")
    
    def test_search_with_form_filter(self):
        """Test search with form filter."""
        results = self.search_engine.search_with_filters(
            "Аспирин", form="Таблетки кишечнорастворимые"
        )
        
        # Should only return Тромбо АСС which has this form
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0]['name'], "Тромбо АСС")
    
    def test_search_with_price_filter(self):
        """Test search with price filter."""
        results = self.search_engine.search_with_filters(
            "Парацетамол", min_price=100.0
        )
        
        # Should only return Панадол (120) as it's >= 100
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0]['name'], "Панадол")
    
    def test_search_with_manufacturer_filter(self):
        """Test search with manufacturer filter."""
        results = self.search_engine.search_with_filters(
            "Парацетамол", manufacturer="Glaxo"
        )
        
        # Should only return Панадол by GlaxoSmithKline
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0]['name'], "Панадол")
    
    def test_search_with_multiple_filters(self):
        """Test search with multiple filters."""
        results = self.search_engine.search_with_filters(
            "Парацетамол", 
            form="Таблетки",
            min_price=100.0,
            max_price=150.0
        )
        
        # Should return Панадол which matches all filters
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0]['name'], "Панадол")
    
    def test_find_analogs_by_id(self):
        """Test finding analogs by drug ID."""
        # Get ID of Аспирин
        drugs = self.database.search_drugs_by_name("Аспирин")
        aspirin_id = drugs[0]['id']
        
        results = self.search_engine.find_analogs_by_id(aspirin_id)
        
        self.assertGreater(len(results), 0)
        self.assertTrue(
            any(drug['name'] == 'Тромбо АСС' for drug, _ in results)
        )
    
    def test_compare_drugs(self):
        """Test drug comparison functionality."""
        # Get drug IDs
        aspirin = self.database.search_drugs_by_name("Аспирин")[0]
        tromb_ass = self.database.search_drugs_by_name("Тромбо АСС")[0]
        
        drugs = self.search_engine.compare_drugs([
            aspirin['id'], tromb_ass['id']
        ])
        
        self.assertEqual(len(drugs), 2)
        # Should be sorted by substance and price
        self.assertEqual(drugs[0]['name'], 'Тромбо АСС')  # Lower price
        self.assertEqual(drugs[1]['name'], 'Аспирин')
    
    def test_empty_search_query(self):
        """Test search with empty query."""
        # Empty search should return empty results as it won't find any drugs
        results = self.search_engine.find_analogs("   ")  # Only whitespace
        
        self.assertEqual(len(results), 0)
    
    def test_nonexistent_drug(self):
        """Test search for non-existent drug."""
        results = self.search_engine.find_analogs("Несуществующий препарат")
        
        self.assertEqual(len(results), 0)


class TestDatabase(unittest.TestCase):
    """Test cases for Database class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_db_path = "test_drugs.db"
        
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        
        self.database = Database(self.test_db_path)
    
    def tearDown(self):
        """Clean up after tests."""
        self.database = None
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
    
    def test_add_and_get_drug(self):
        """Test adding and retrieving drug."""
        drug_id = self.database.add_drug(
            "Test Drug", "Test Substance", "Таблетки", 
            "Test Manufacturer", 100.0
        )
        
        self.assertIsNotNone(drug_id)
        
        drug = self.database.get_drug_by_id(drug_id)
        self.assertEqual(drug['name'], "Test Drug")
        self.assertEqual(drug['substance'], "Test Substance")
    
    def test_get_drugs_by_substance(self):
        """Test getting drugs by substance."""
        self.database.add_drug("Drug 1", "Substance A", "Tab", "Man1", 100.0)
        self.database.add_drug("Drug 2", "Substance A", "Cap", "Man2", 200.0)
        self.database.add_drug("Drug 3", "Substance B", "Tab", "Man3", 150.0)
        
        drugs = self.database.get_drugs_by_substance("Substance A")
        
        self.assertEqual(len(drugs), 2)
        # Should be sorted by price
        self.assertEqual(drugs[0]['price'], 100.0)
    
    def test_update_drug(self):
        """Test updating drug information."""
        drug_id = self.database.add_drug(
            "Old Name", "Old Substance", "Tab", "Man", 100.0
        )
        
        success = self.database.update_drug(
            drug_id, "New Name", "New Substance", "Cap", "New Man", 200.0
        )
        
        self.assertTrue(success)
        
        drug = self.database.get_drug_by_id(drug_id)
        self.assertEqual(drug['name'], "New Name")
        self.assertEqual(drug['price'], 200.0)
    
    def test_delete_drug(self):
        """Test deleting drug."""
        drug_id = self.database.add_drug(
            "To Delete", "Substance", "Tab", "Man", 100.0
        )
        
        success = self.database.delete_drug(drug_id)
        self.assertTrue(success)
        
        drug = self.database.get_drug_by_id(drug_id)
        self.assertIsNone(drug)
    
    def test_search_drugs_by_name(self):
        """Test searching drugs by name."""
        self.database.add_drug("Аспирин", "Sub", "Tab", "Man", 100.0)
        self.database.add_drug("Аспирин Форте", "Sub", "Tab", "Man", 150.0)
        
        results = self.database.search_drugs_by_name("Аспирин")
        
        self.assertEqual(len(results), 2)


if __name__ == "__main__":
    unittest.main()

