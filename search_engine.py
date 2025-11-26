from typing import List, Dict, Tuple
from abc import ABC, abstractmethod
import difflib
from database import Database


class SubstanceNormalizer:    
    @staticmethod
    def normalize_substances(substance_str: str) -> List[str]:
        substances = [s.strip() for s in substance_str.replace('+', ',').split(',') if s.strip()]
        return [s.lower() for s in substances]
    
    @staticmethod
    def has_matching_substance(main_substance: str, analog_substance: str) -> bool:
        main_substances = SubstanceNormalizer.normalize_substances(main_substance)
        analog_substances = SubstanceNormalizer.normalize_substances(analog_substance)
        
        for main_sub in main_substances:
            for analog_sub in analog_substances:
                if main_sub == analog_sub or main_sub in analog_sub or analog_sub in main_sub:
                    return True
        return False



class SimilarityCalculator:    
    def __init__(self, normalizer: SubstanceNormalizer = None):
        self.normalizer = normalizer or SubstanceNormalizer()
    
    def calculate(self, drug1: Dict, drug2: Dict) -> float:
        score = 1.0
        score += self._calculate_substance_similarity(drug1, drug2)
        score += self._calculate_form_similarity(drug1, drug2)
        score += self._calculate_manufacturer_similarity(drug1, drug2)
        score += self._calculate_price_similarity(drug1, drug2)
        return score
    
    def _calculate_substance_similarity(self, drug1: Dict, drug2: Dict) -> float:
        substances1 = set(self.normalizer.normalize_substances(drug1.get('substance', '')))
        substances2 = set(self.normalizer.normalize_substances(drug2.get('substance', '')))
        
        if len(substances1) <= 1 and len(substances2) <= 1:
            return 0.0
        
        overlap = len(substances1 & substances2)
        total_unique = len(substances1 | substances2)
        
        if total_unique > 0:
            overlap_ratio = overlap / total_unique
            return overlap_ratio * 0.3
        return 0.0
    
    def _calculate_form_similarity(self, drug1: Dict, drug2: Dict) -> float:
        if drug1.get('form', '').lower() == drug2.get('form', '').lower():
            return 0.3
        return 0.0
    
    def _calculate_manufacturer_similarity(self, drug1: Dict, drug2: Dict) -> float:
        if drug1.get('manufacturer', '').lower() == drug2.get('manufacturer', '').lower():
            return 0.2
        return 0.0
    
    def _calculate_price_similarity(self, drug1: Dict, drug2: Dict) -> float:
        price1 = drug1.get('price', 0)
        price2 = drug2.get('price', 0)
        
        if price1 <= 0 or price2 <= 0:
            return 0.0
        
        price_diff = abs(price1 - price2) / price1
        if price_diff < 0.1:
            return 0.2
        elif price_diff < 0.3:
            return 0.1
        return 0.0


class SearchStrategy:
    def __init__(self, database: Database, similarity_calc: SimilarityCalculator = None):
        self.database = database
        self.similarity_calc = similarity_calc or SimilarityCalculator()
        self.normalizer = SubstanceNormalizer()

    def search(self, query: str, mode: str = 'substance') -> List[Tuple[Dict, float]]:
        if mode == 'id':
            try:
                drug_id = int(query)
            except ValueError:
                return []
            drug = self.database.get_drug_by_id(drug_id)
            if not drug:
                return []
            # Поиск аналогов для найденного препарата по веществу
            main_substance = drug.get('substance', '')
            return self._find_by_substance(main_substance, drug['id'])
        
        drugs = self.database.search_drugs_by_name(query)
        
        if drugs:
            main_drug = drugs[0]
            main_substance = main_drug.get('substance', '')
            return self._find_by_substance(main_substance, main_drug['id'])
        
        all_drugs = self.database.get_all_drugs()
        matching_drugs = [d for d in all_drugs if query.lower() == d.get('substance', '').lower()]
        
        if matching_drugs:
            main_substance = query
            main_drug_id = matching_drugs[0]['id']
            return self._find_by_substance(main_substance, main_drug_id)
        
        return []
    
    def _find_by_substance(self, substance: str, exclude_drug_id: int = None) -> List[Tuple[Dict, float]]:
        analogs = self.database.get_drugs_by_substance(substance)
        result = []
        
        for analog in analogs:
            if exclude_drug_id and analog['id'] == exclude_drug_id:
                continue
            
            if not self.normalizer.has_matching_substance(substance, analog.get('substance', '')):
                continue
            
            similarity = 1.0
            result.append((analog, similarity))
        
        result.sort(key=lambda x: (-x[1], x[0].get('price', 0)))
        return result


class DrugFilter:
    
    @staticmethod
    def apply_filters(drugs: List[Tuple[Dict, float]], 
                     form: str = None,
                     manufacturer: str = None,
                     min_price: float = None,
                     max_price: float = None,
                     exclude_contraindication: str = None) -> List[Tuple[Dict, float]]:
        filtered = []
        
        for drug, score in drugs:
            if not DrugFilter._passes_all_filters(
                drug, form, manufacturer, min_price, max_price, exclude_contraindication
            ):
                continue
            filtered.append((drug, score))
        
        return filtered
    
    @staticmethod
    def _passes_all_filters(drug: Dict, form: str, manufacturer: str,
                           min_price: float, max_price: float,
                           exclude_contraindication: str) -> bool:
        if form and drug.get('form', '').lower() != form.lower():
            return False
        
        if manufacturer and manufacturer.lower() not in drug.get('manufacturer', '').lower():
            return False
        
        price = drug.get('price', 0)
        if min_price is not None and price < min_price:
            return False
        
        if max_price is not None and price > max_price:
            return False
        
        if exclude_contraindication:
            contraindications = drug.get('contraindications', '') or ''
            if exclude_contraindication.lower() in contraindications.lower():
                return False
        
        return True


class DrugComparator:
    
    @staticmethod
    def compare(database: Database, drug_ids: List[int]) -> List[Dict]:
        drugs = []
        for drug_id in drug_ids:
            drug = database.get_drug_by_id(drug_id)
            if drug:
                drugs.append(drug)
        
        drugs.sort(key=lambda x: (x.get('substance', ''), x.get('price', 0)))
        return drugs


class SearchEngine:
    
    def __init__(self, database: Database):
        self.database = database
        self.similarity_calc = SimilarityCalculator()
        self.search_strategy = SearchStrategy(database, self.similarity_calc)
        self.filter = DrugFilter()
        self.comparator = DrugComparator()
    
    def find_analogs(self, drug_name: str) -> List[Tuple[Dict, float]]:
        return self.search_strategy.search(drug_name, mode='substance')

    def find_analogs_by_id(self, drug_id: int) -> List[Tuple[Dict, float]]:
        return self.search_strategy.search(str(drug_id), mode='id')
    
    def search_with_filters(self, query: str, form: str = None,
                           manufacturer: str = None,
                           min_price: float = None,
                           max_price: float = None,
                           exclude_contraindication: str = None) -> List[Tuple[Dict, float]]:
        analogs = self.find_analogs(query)
        return self.filter.apply_filters(
            analogs, form, manufacturer, min_price, max_price, exclude_contraindication
        )
    
    def compare_drugs(self, drug_ids: List[int]) -> List[Dict]:
        return self.comparator.compare(self.database, drug_ids)

