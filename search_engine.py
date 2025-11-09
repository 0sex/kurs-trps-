"""
Search engine module for finding drug analogs.

This module implements the core logic for finding analogs based on
active substances and similarity scoring.
"""

from typing import List, Dict, Tuple
from database import Database


class SearchEngine:
    """Implements drug analog search functionality."""
    
    def __init__(self, database: Database):
        """
        Initialize search engine with database.
        
        Args:
            database: Database instance
        """
        self.database = database
    
    def find_analogs(self, drug_name: str) -> List[Tuple[Dict, float]]:
        """
        Find analogs for a given drug by name.
        Supports multiple substances - finds drugs with at least one matching substance.
        
        Args:
            drug_name: Name of the drug to find analogs for
            
        Returns:
            List of tuples (drug_dict, similarity_score)
        """
        # First, find the drug by name
        drugs = self.database.search_drugs_by_name(drug_name)
        
        if not drugs:
            return []
        
        # Use the first matching drug
        main_drug = drugs[0]
        main_substance = main_drug['substance']
        
        # Find all drugs with at least one matching active substance
        # get_drugs_by_substance now supports multiple substances
        analogs = self.database.get_drugs_by_substance(main_substance)
        
        # Filter out the original drug and calculate similarity
        result = []
        for analog in analogs:
            # Skip the drug itself
            if analog['id'] == main_drug['id']:
                continue
            
            # Check if substances actually match (at least one)
            if not self._has_matching_substance(main_drug['substance'], analog['substance']):
                continue
            
            # Calculate similarity score based on multiple factors
            similarity = self._calculate_similarity(main_drug, analog)
            result.append((analog, similarity))
        
        # Sort by similarity score (descending) and then by price (ascending)
        result.sort(key=lambda x: (-x[1], x[0]['price']))
        
        return result
    
    def _has_matching_substance(self, main_substance: str, analog_substance: str) -> bool:
        """
        Check if at least one substance from main_drug matches analog.
        
        Args:
            main_substance: Substance(s) of the main drug
            analog_substance: Substance(s) of the analog drug
            
        Returns:
            True if at least one substance matches
        """
        # Normalize delimiters
        def normalize_substances(substance_str: str) -> List[str]:
            substances = [s.strip() for s in substance_str.replace('+', ',').split(',') if s.strip()]
            return [s.lower() for s in substances]
        
        main_substances = normalize_substances(main_substance)
        analog_substances = normalize_substances(analog_substance)
        
        # Check if any substance from main matches any from analog
        for main_sub in main_substances:
            for analog_sub in analog_substances:
                # Check for exact match or partial match
                if main_sub == analog_sub or main_sub in analog_sub or analog_sub in main_sub:
                    return True
        return False
    
    def _calculate_similarity(self, drug1: Dict, drug2: Dict) -> float:
        """
        Calculate similarity score between two drugs.
        
        The score is based on:
        - Same substance (at least one): +1.0
        - Same form: +0.3
        - Same manufacturer: +0.2
        - Price proximity: +0.0 to +0.2
        - Substance overlap: +0.0 to +0.3 (for multiple substances)
        
        Args:
            drug1: First drug dictionary
            drug2: Second drug dictionary
            
        Returns:
            Similarity score from 0.0 to 2.0+
        """
        score = 1.0  # Base score for at least one matching substance
        
        # Calculate substance overlap for multiple substances
        def get_substances(drug: Dict) -> List[str]:
            substances = [s.strip() for s in drug['substance'].replace('+', ',').split(',') if s.strip()]
            return [s.lower() for s in substances]
        
        substances1 = set(get_substances(drug1))
        substances2 = set(get_substances(drug2))
        
        # Calculate overlap ratio
        if len(substances1) > 1 or len(substances2) > 1:
            overlap = len(substances1 & substances2)
            total_unique = len(substances1 | substances2)
            if total_unique > 0:
                overlap_ratio = overlap / total_unique
                score += overlap_ratio * 0.3  # Up to +0.3 for perfect overlap
        
        # Check form similarity
        if drug1['form'].lower() == drug2['form'].lower():
            score += 0.3
        
        # Check manufacturer similarity
        if drug1['manufacturer'].lower() == drug2['manufacturer'].lower():
            score += 0.2
        
        # Check price proximity (relative difference)
        if drug1['price'] > 0 and drug2['price'] > 0:
            price_diff = abs(drug1['price'] - drug2['price']) / drug1['price']
            if price_diff < 0.1:  # Less than 10% difference
                score += 0.2
            elif price_diff < 0.3:  # Less than 30% difference
                score += 0.1
        
        return score
    
    def find_analogs_by_id(self, drug_id: int) -> List[Tuple[Dict, float]]:
        """
        Find analogs for a drug by ID.
        
        Args:
            drug_id: ID of the drug
            
        Returns:
            List of tuples (drug_dict, similarity_score)
        """
        drug = self.database.get_drug_by_id(drug_id)
        if not drug:
            return []
        
        return self.find_analogs(drug['name'])
    
    def search_with_filters(self, query: str, form: str = None,
                           manufacturer: str = None,
                           min_price: float = None,
                           max_price: float = None,
                           exclude_contraindication: str = None) -> List[Tuple[Dict, float]]:
        """
        Search for analogs with additional filters.
        
        Args:
            query: Drug name to search
            form: Filter by release form
            manufacturer: Filter by manufacturer
            min_price: Minimum price filter
            max_price: Maximum price filter
            exclude_contraindication: Exclude drugs with this contraindication
            
        Returns:
            List of tuples (drug_dict, similarity_score)
        """
        analogs = self.find_analogs(query)
        
        # Apply filters
        filtered = []
        for drug, score in analogs:
            # Apply form filter
            if form and drug['form'].lower() != form.lower():
                continue
            
            # Apply manufacturer filter
            if manufacturer and manufacturer.lower() not in drug['manufacturer'].lower():
                continue
            
            # Apply price filters
            if min_price is not None and drug['price'] < min_price:
                continue
            
            if max_price is not None and drug['price'] > max_price:
                continue
            
            # Apply contraindication filter
            if exclude_contraindication:
                contraindications = drug.get('contraindications', '') or ''
                if exclude_contraindication.lower() in contraindications.lower():
                    continue
            
            filtered.append((drug, score))
        
        return filtered
    
    def compare_drugs(self, drug_ids: List[int]) -> List[Dict]:
        """
        Compare multiple drugs side by side.
        
        Args:
            drug_ids: List of drug IDs to compare
            
        Returns:
            List of drug dictionaries
        """
        drugs = []
        for drug_id in drug_ids:
            drug = self.database.get_drug_by_id(drug_id)
            if drug:
                drugs.append(drug)
        
        # Sort by key attributes for comparison
        drugs.sort(key=lambda x: (x['substance'], x['price']))
        
        return drugs

