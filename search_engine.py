from typing import List, Dict, Tuple
from database import Database


class SearchEngine:
    def __init__(self, database: Database):
        self.database = database

    def find_analogs(self, drug_name: str) -> List[Tuple[Dict, float]]:
        drugs = self.database.search_drugs_by_name(drug_name)
        if not drugs:
            return []
        main_drug = drugs[0]
        main_substance = main_drug['substance']
        analogs = self.database.get_drugs_by_substance(main_substance)
        result = []
        for analog in analogs:
            if analog['id'] == main_drug['id']:
                continue
            if not self._has_matching_substance(main_drug['substance'], analog['substance']):
                continue
            similarity = self._calculate_similarity(main_drug, analog)
            result.append((analog, similarity))
        result.sort(key=lambda x: (-x[1], x[0]['price']))
        return result

    def _has_matching_substance(self, main_substance: str, analog_substance: str) -> bool:
        def normalize_substances(substance_str: str) -> List[str]:
            substances = [s.strip() for s in substance_str.replace('+', ',').split(',') if s.strip()]
            return [s.lower() for s in substances]
        main_substances = normalize_substances(main_substance)
        analog_substances = normalize_substances(analog_substance)
        for main_sub in main_substances:
            for analog_sub in analog_substances:
                if main_sub == analog_sub or main_sub in analog_sub or analog_sub in main_sub:
                    return True
        return False

    def _calculate_similarity(self, drug1: Dict, drug2: Dict) -> float:
        score = 1.0
        def get_substances(drug: Dict) -> List[str]:
            substances = [s.strip() for s in drug['substance'].replace('+', ',').split(',') if s.strip()]
            return [s.lower() for s in substances]
        substances1 = set(get_substances(drug1))
        substances2 = set(get_substances(drug2))
        if len(substances1) > 1 or len(substances2) > 1:
            overlap = len(substances1 & substances2)
            total_unique = len(substances1 | substances2)
            if total_unique > 0:
                overlap_ratio = overlap / total_unique
                score += overlap_ratio * 0.3
        if drug1['form'].lower() == drug2['form'].lower():
            score += 0.3
        if drug1['manufacturer'].lower() == drug2['manufacturer'].lower():
            score += 0.2
        if drug1['price'] > 0 and drug2['price'] > 0:
            price_diff = abs(drug1['price'] - drug2['price']) / drug1['price']
            if price_diff < 0.1:
                score += 0.2
            elif price_diff < 0.3:
                score += 0.1
        return score

    def find_analogs_by_id(self, drug_id: int) -> List[Tuple[Dict, float]]:
        drug = self.database.get_drug_by_id(drug_id)
        if not drug:
            return []
        return self.find_analogs(drug['name'])

    def search_with_filters(self, query: str, form: str = None,
                           manufacturer: str = None,
                           min_price: float = None,
                           max_price: float = None,
                           exclude_contraindication: str = None) -> List[Tuple[Dict, float]]:
        analogs = self.find_analogs(query)
        filtered = []
        for drug, score in analogs:
            if form and drug['form'].lower() != form.lower():
                continue
            if manufacturer and manufacturer.lower() not in drug['manufacturer'].lower():
                continue
            if min_price is not None and drug['price'] < min_price:
                continue
            if max_price is not None and drug['price'] > max_price:
                continue
            if exclude_contraindication:
                contraindications = drug.get('contraindications', '') or ''
                if exclude_contraindication.lower() in contraindications.lower():
                    continue
            filtered.append((drug, score))
        return filtered

    def compare_drugs(self, drug_ids: List[int]) -> List[Dict]:
        drugs = []
        for drug_id in drug_ids:
            drug = self.database.get_drug_by_id(drug_id)
            if drug:
                drugs.append(drug)
        drugs.sort(key=lambda x: (x['substance'], x['price']))
        return drugs

