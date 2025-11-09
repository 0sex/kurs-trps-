"""
Additional tests for Database module focusing on edge cases.

Tests error handling, data validation, and complex queries.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database


class TestDatabaseAdvanced(unittest.TestCase):
    """Advanced test cases for Database class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_db_path = "test_drugs_advanced.db"
        
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        
        self.database = Database(self.test_db_path)
    
    def tearDown(self):
        """Clean up after tests."""
        self.database = None
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
    
    def test_analog_links(self):
        """Test analog links functionality."""
        drug_id1 = self.database.add_drug("Drug 1", "Sub A", "Tab", "Man1", 100.0)
        drug_id2 = self.database.add_drug("Drug 2", "Sub A", "Cap", "Man2", 200.0)
        
        # Add analog link
        success = self.database.add_analog_link(drug_id1, drug_id2, 0.9)
        self.assertTrue(success)
        
        # Get analogs
        analogs = self.database.get_analogs(drug_id1)
        self.assertEqual(len(analogs), 1)
        self.assertEqual(analogs[0][0]['id'], drug_id2)
        self.assertEqual(analogs[0][1], 0.9)
    
    def test_complex_filters(self):
        """Test complex filtering combinations."""
        self.database.add_drug("D1", "Sub1", "Таблетки", "M1", 50.0)
        self.database.add_drug("D2", "Sub1", "Капсулы", "M1", 150.0)
        self.database.add_drug("D3", "Sub1", "Таблетки", "M2", 100.0)
        self.database.add_drug("D4", "Sub2", "Таблетки", "M1", 200.0)
        
        # Filter by form and manufacturer
        results = self.database.get_drugs_by_filters(
            form="Таблетки", manufacturer="M1"
        )
        
        self.assertEqual(len(results), 2)
        self.assertIn("D1", [r['name'] for r in results])
        self.assertIn("D4", [r['name'] for r in results])
    
    def test_price_range_filter(self):
        """Test price range filtering."""
        self.database.add_drug("D1", "Sub", "Tab", "Man", 50.0)
        self.database.add_drug("D2", "Sub", "Tab", "Man", 100.0)
        self.database.add_drug("D3", "Sub", "Tab", "Man", 150.0)
        self.database.add_drug("D4", "Sub", "Tab", "Man", 200.0)
        
        # Filter by price range
        results = self.database.get_drugs_by_filters(min_price=75.0, max_price=175.0)
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['name'], "D2")  # 100.0
        self.assertEqual(results[1]['name'], "D3")  # 150.0
    
    def test_get_all_forms_and_manufacturers(self):
        """Test getting unique forms and manufacturers."""
        self.database.add_drug("D1", "Sub", "Таблетки", "Мануфактура1", 100.0)
        self.database.add_drug("D2", "Sub", "Капсулы", "Мануфактура2", 100.0)
        self.database.add_drug("D3", "Sub", "Таблетки", "Мануфактура1", 100.0)
        
        forms = self.database.get_all_forms()
        manufacturers = self.database.get_all_manufacturers()
        
        self.assertIn("Таблетки", forms)
        self.assertIn("Капсулы", forms)
        self.assertEqual(len(forms), 2)
        
        self.assertIn("Мануфактура1", manufacturers)
        self.assertIn("Мануфактура2", manufacturers)
        self.assertEqual(len(manufacturers), 2)
    
    def test_empty_results(self):
        """Test queries with no results."""
        # Empty database
        results = self.database.get_all_drugs()
        self.assertEqual(len(results), 0)
        
        results = self.database.search_drugs_by_name("Nonexistent")
        self.assertEqual(len(results), 0)
        
        results = self.database.get_drugs_by_substance("Nonexistent")
        self.assertEqual(len(results), 0)
    
    def test_nonexistent_drug_id(self):
        """Test queries with nonexistent IDs."""
        drug = self.database.get_drug_by_id(99999)
        self.assertIsNone(drug)
        
        success = self.database.update_drug(99999, "Name", "Sub", "Tab", "Man", 100.0)
        self.assertFalse(success)
        
        success = self.database.delete_drug(99999)
        self.assertFalse(success)
    
    def test_special_characters(self):
        """Test handling of special characters in names."""
        drug_id = self.database.add_drug(
            "Test® Drug™", "Substance (Active)", "Таблетки-форте", 
            "Manufacturer & Co.", 100.50
        )
        
        drug = self.database.get_drug_by_id(drug_id)
        self.assertEqual(drug['name'], "Test® Drug™")
        self.assertEqual(drug['substance'], "Substance (Active)")
        self.assertEqual(drug['form'], "Таблетки-форте")
    
    def test_case_insensitive_search(self):
        """Test case-insensitive search."""
        self.database.add_drug("Aspirin", "Sub", "Tab", "Man", 100.0)
        self.database.add_drug("aspirin", "Sub", "Tab", "Man", 100.0)
        self.database.add_drug("ASPIRIN", "Sub", "Tab", "Man", 100.0)
        
        results = self.database.search_drugs_by_name("aspirin")
        self.assertEqual(len(results), 3)
        
        results = self.database.search_drugs_by_name("ASPIRIN")
        self.assertEqual(len(results), 3)
    
    def test_decimal_prices(self):
        """Test handling of decimal prices."""
        drug_id = self.database.add_drug(
            "Test", "Sub", "Tab", "Man", 99.99
        )
        
        drug = self.database.get_drug_by_id(drug_id)
        self.assertEqual(drug['price'], 99.99)
        
        # Update with different decimal
        self.database.update_drug(drug_id, "Test", "Sub", "Tab", "Man", 199.50)
        drug = self.database.get_drug_by_id(drug_id)
        self.assertEqual(drug['price'], 199.50)


if __name__ == "__main__":
    unittest.main()


