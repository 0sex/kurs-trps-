from typing import Dict, List, Tuple, Any
from datetime import datetime
from abc import ABC, abstractmethod
import difflib
import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QTableWidget, QTableWidgetItem, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from database import Database


class NormalizationStrategy:    
    def __init__(self, target_synonyms: Dict[str, str] = None, 
                 effect_synonyms: Dict[str, str] = None):
        self.target_synonyms = target_synonyms or {}
        self.effect_synonyms = effect_synonyms or {}
    
    def normalize(self, text: str) -> str:
        if not text:
            return ""
        text = str(text).strip().lower()
        if not text:
            return ""
        
        if text in self.target_synonyms:
            return self.target_synonyms[text]
        if text in self.effect_synonyms:
            return self.effect_synonyms[text]
        
        text = re.sub(r"[^a-z0-9а-яё -]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    
    def fuzzy_match(self, key: str, candidates: List[str], cutoff: float = 0.65) -> List[str]:
        if not key or not candidates:
            return []
        key_n = self.normalize(key)
        cand_map = {self.normalize(c): c for c in candidates}
        normalized_candidates = list(cand_map.keys())
        matches = difflib.get_close_matches(key_n, normalized_candidates, n=3, cutoff=cutoff)
        return [cand_map[m] for m in matches]


_DEFAULT_TARGET_SYNONYMS = {
    "ltcc": "l-type calcium channel",
    "l-vscc": "l-type calcium channel",
    "кальциевый канал l-типа": "l-type calcium channel",
    "сердечный кальциевый канал": "l-type calcium channel",
    'cox1': 'COX1',
    'cox2': 'COX2',
    'cox3': 'COX3',
    'sert': 'SERT',
    'at1-рецептор': 'AT1 receptor',
    'na-k-2cl котранспортер': 'Na-K-2Cl cotransporter',
    'na-cl котранспортер': 'Na-Cl cotransporter',
    'h+/k+-атфаза': 'H+/K+-ATPase',
}

_DEFAULT_EFFECT_SYNONYMS = {
    "гипотензия": "низкое давление",
    "ортостатическая гипотензия": "низкое давление",
    "low blood pressure": "низкое давление",
    "гипонатриемия": "низкий натрий",
    "низкий уровень натрия": "низкий натрий",
    "жк-кровотечение": "желудочно-кишечное кровотечение",
    "ulcer": "желудочно-кишечкое кровотечение",
    'серотониновый синдром': 'серотониновый синдром',
}

DEFAULT_NORMALIZER = NormalizationStrategy(_DEFAULT_TARGET_SYNONYMS, _DEFAULT_EFFECT_SYNONYMS)


class InteractionAnalyzer:
    def __init__(self, normalizer: NormalizationStrategy = None):
        self.normalizer = normalizer or DEFAULT_NORMALIZER

        self.ROLE_MAPPINGS = {
            'inhibitor': ['ингибитор', 'замедление', 'снижение', 'inhibitor'],
            'inducer': ['активатор', 'стимулятор', 'индуктор', 'inducer', 'activator'],
            'substrate': ['субстрат', 'substrate'],
            'blocker': ['блокатор', 'антагонист', 'blocker', 'antagonist'],
            'agonist': ['агонист', 'миметик', 'agonist'],
        }

        self.STRENGTH_WEIGHTS = {
            'слабый': 0.5,
            'weak': 0.5,
            'сильный': 1.5,
            'strong': 1.5,
            'селективный': 1.0,
        }

    def _parse_entry(self, raw_text: str) -> dict:
        text = str(raw_text).lower()
        
        strength = 1.0
        for keyword, weight in self.STRENGTH_WEIGHTS.items():
            if keyword in text:
                strength = weight
                break
        
        role = 'unknown'
        for r_key, keywords in self.ROLE_MAPPINGS.items():
            if any(k in text for k in keywords):
                role = r_key
                break
        
        all_keywords = set()
        for k_list in self.ROLE_MAPPINGS.values():
            all_keywords.update(k_list)
        all_keywords.update(self.STRENGTH_WEIGHTS.keys())
        all_keywords.add('эффект')
        
        cleaned_text = text
        for k in all_keywords:
            cleaned_text = cleaned_text.replace(k, "")
        
        target_name = self.normalizer.normalize(cleaned_text)
        
        if len(target_name) < 2: 
            target_name = "systemic"

        return {'target': target_name, 'role': role, 'strength': strength, 'original': raw_text}

    def analyze(self, pharm_a: Dict[str, Any], pharm_b: Dict[str, Any], drug_a_name: str, drug_b_name: str) -> Tuple[float, List[str], List[str]]:
        score = 0.0
        mechanisms = []
        comments = []

        meta_a_parsed = [self._parse_entry(m) for m in pharm_a.get('metabolism', [])]
        meta_b_parsed = [self._parse_entry(m) for m in pharm_b.get('metabolism', [])]
        
        targ_a_parsed = [self._parse_entry(t) for t in pharm_a.get('targets', [])]
        targ_b_parsed = [self._parse_entry(t) for t in pharm_b.get('targets', [])]

        s_m, m_m, c_m = self._analyze_metabolic(meta_a_parsed, meta_b_parsed, drug_a_name, drug_b_name)
        score += s_m
        mechanisms.extend(m_m)
        comments.extend(c_m)

        s_d, m_d, c_d = self._analyze_dynamical(targ_a_parsed, targ_b_parsed, drug_a_name, drug_b_name)
        score += s_d
        mechanisms.extend(m_d)
        comments.extend(c_d)

        effects_a = pharm_a.get('effects', [])
        effects_b = pharm_b.get('effects', [])
        s_t, m_t, c_t = self._analyze_toxicity(effects_a, effects_b, drug_a_name, drug_b_name)
        score += s_t
        mechanisms.extend(m_t)
        comments.extend(c_t)

        return min(score, 1.0), mechanisms, comments

    def _analyze_metabolic(self, metab_a: List[dict], metab_b: List[dict], name_a: str, name_b: str):
        score = 0.0
        mechanisms = []
        comments = []

        def map_enzymes(parsed_list):
            mapping = {}
            for item in parsed_list:
                t = item['target']
                if t not in mapping: mapping[t] = []
                mapping[t].append(item)
            return mapping

        map_a = map_enzymes(metab_a)
        map_b = map_enzymes(metab_b)
        
        common_enzymes = set(map_a.keys()) & set(map_b.keys())
        
        for enz in common_enzymes:
            if enz == 'systemic': continue 

            list_a = map_a[enz]
            list_b = map_b[enz]

            for item_a in list_a:
                for item_b in list_b:                    
                    match (item_a['role'], item_b['role']):
                        case ('inhibitor', 'substrate'):
                            score += 0.4 * item_a['strength']
                            mechanisms.append(f"{name_a} ингибирует {enz.upper()}, метаболизирующий {name_b}")
                            comments.append(f"Риск повышения концентрации {name_b} и токсичности")
                            
                        case ('substrate', 'inhibitor'):
                            score += 0.4 * item_b['strength']
                            mechanisms.append(f"{name_b} ингибирует {enz.upper()}, метаболизирующий {name_a}")
                            comments.append(f"Риск повышения концентрации {name_a} и токсичности")
                            
                        case ('inducer', 'substrate'):
                            score += 0.3 * item_a['strength']
                            mechanisms.append(f"{name_a} стимулирует {enz.upper()}, разрушающий {name_b}")
                            comments.append(f"Риск снижения эффективности {name_b}")

                        case ('substrate', 'inducer'):
                            score += 0.3 * item_b['strength']
                            mechanisms.append(f"{name_b} стимулирует {enz.upper()}, разрушающий {name_a}")
                            comments.append(f"Риск снижения эффективности {name_a}")

        return score, mechanisms, comments

    def _analyze_dynamical(self, targets_a: List[dict], targets_b: List[dict], name_a: str, name_b: str):
        score = 0.0
        mechanisms = []
        comments = []
        
        for item_a in targets_a:
            for item_b in targets_b:
                t_a = item_a['target']
                t_b = item_b['target']
                
                if t_a == 'systemic' or t_b == 'systemic': continue

                if t_a == t_b:
                    role_a = item_a['role']
                    role_b = item_b['role']
                    
                    if role_a in ['blocker', 'inhibitor'] and role_b in ['blocker', 'inhibitor']:
                        s_val = 0.5 * min(item_a['strength'], item_b['strength'])
                        score += s_val
                        mechanisms.append(f"Двойная блокада мишени {t_a.upper()}")
                        comments.append("Риск усиления побочных эффектов или чрезмерного угнетения функции")
                    
                    elif (role_a == 'agonist' and role_b in ['blocker', 'antagonist']) or \
                         (role_b == 'agonist' and role_a in ['blocker', 'antagonist']):
                        s_val = 0.4
                        score += s_val
                        mechanisms.append(f"Антагонизм действия на {t_a.upper()}")
                        comments.append("Препараты могут нейтрализовать терапевтический эффект друг друга")
        
        return score, mechanisms, comments

    def _analyze_toxicity(self, effects_a, effects_b, drug_a_name, drug_b_name):
        score = 0.0
        mechanisms = []
        comments = []
        
        set_a = set()
        for eff in effects_a:
            set_a.update(self.normalizer.normalize(eff).split())
            
        set_b = set()
        for eff in effects_b:
            set_b.update(self.normalizer.normalize(eff).split())
            
        common_words = set_a.intersection(set_b)
        
        dangerous_keywords = {
            'кровотечение', 'bleeding', 'qt', 'arrhythmia', 'аритмия', 
            'liver', 'печень', 'kidney', 'почки', 'sedation', 'сетация', 
            'pressure', 'давление', 'hypotension', 'гипотензия'
        }
        
        found_dangers = common_words.intersection(dangerous_keywords)
        
        if found_dangers:
            score += 0.3
            mechanisms.append(f"Суммирование побочных эффектов: {', '.join(found_dangers)}")
            comments.append("Увеличение риска специфической токсичности")
            
        return score, mechanisms, comments


WEIGHTS = {
    'metabolic': 0.35,
    'dynamical': 0.25,
    'toxicity': 0.15
}


class InteractionEngine:    
    def __init__(self, database: Database, normalizer: NormalizationStrategy = None):
        self.db = database
        self.normalizer = normalizer or DEFAULT_NORMALIZER
        
        self.analyzer = InteractionAnalyzer(self.normalizer)
    
    def load_drug_data(self, drug_id: int) -> Dict[str, Any]:
        drug = self.db.get_drug_by_id(drug_id)
        if not drug:
            raise ValueError(f"Drug id {drug_id} not found")
        pharm = self.db.get_drug_pharmacology(drug_id)
        return {
            'drug': drug,
            'targets': pharm.get('targets', []),
            'metabolism': pharm.get('metabolism', []),
            'effects': pharm.get('effects', [])
        }
    
    def analyze_interaction(self, drug_a_id: int, drug_b_id: int) -> Dict[str, Any]:
        a = self.load_drug_data(drug_a_id)
        b = self.load_drug_data(drug_b_id)
        
        drug_a_name = a['drug']['name']
        drug_b_name = b['drug']['name']
        
        score, mechanisms, comments = self.analyzer.analyze(a, b, drug_a_name, drug_b_name)
        
        if not mechanisms:
            mechanisms = self._get_fallback_mechanisms(a, b)
        
        score = max(0.0, min(1.0, score))
        
        level = self._determine_level(score)
        
        self._add_extra_warnings(mechanisms, comments, score)
        
        result = {
            'drug_a': drug_a_name,
            'drug_b': drug_b_name,
            'score': round(score, 3),
            'level': level,
            'mechanisms': mechanisms,
            'comments': '; '.join(comments) if comments else '',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return result
    
    def _get_fallback_mechanisms(self, drug_a_data: Dict, drug_b_data: Dict) -> List[str]:
            mechanisms = []
            name_a = drug_a_data['drug']['name']
            name_b = drug_b_data['drug']['name']

            drugs_to_check = [
                (name_a, drug_a_data),
                (name_b, drug_b_data)
            ]

            for name, data in drugs_to_check:
                for category in ['targets', 'metabolism', 'effects']:
                    items = data.get(category)
                    if not items:
                        continue
                    match category:
                        case 'targets':
                            description = "целей"
                        case 'metabolism':
                            description = "ферментов"
                        case 'effects':
                            description = "известно побочных эффектов"
                        case _:
                            continue

                    mechanisms.append(f"{name}: {len(items)} {description}")

            match mechanisms:
                case []:
                    mechanisms.append('Нет особого фармакологического профиля для взаимодействия')
                case _:
                    header = f"Возможное взаимодействие: {name_a} + {name_b} (оба фармакологически активны)"
                    mechanisms.insert(0, header)
            
            return mechanisms
    
    def _determine_level(self, score: float) -> str:
        if score < 0.3:
            return 'Низкий'
        elif score < 0.6:
            return 'Средний'
        else:
            return 'Высокий'
    
    def _add_extra_warnings(self, mechanisms: List[str], comments: List[str], toxicity_score: float) -> None:
        mechanisms_text = ' '.join(mechanisms).lower()
        if 'гепато' in mechanisms_text or 'печён' in mechanisms_text:
            comments.append('Потенциально повышенная гепатотоксичность')
        if toxicity_score > 0.5:
            comments.append('Риск токсичности')
    
    def analyze_combination(self, drug_ids: List[int]) -> List[Dict[str, Any]]:
        results = []
        n = len(drug_ids)
        for i in range(n):
            for j in range(i + 1, n):
                a = drug_ids[i]
                b = drug_ids[j]
                try:
                    res = self.analyze_interaction(a, b)
                except Exception as e:
                    res = {
                        'drug_a': str(a),
                        'drug_b': str(b),
                        'score': 0.0,
                        'level': 'Низкий',
                        'mechanisms': [],
                        'comments': f'Error: {e}'
                    }
                results.append(res)
        return results



class InteractionResultsTable:    
    def __init__(self, table_widget: QTableWidget):
        self.table = table_widget
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(['Лекарство 1', 'Лекарство 2', 'Риск', 'Механизм', 'Комментарии'])
    
    def display(self, results: List[Dict]) -> None:
        self.table.setRowCount(len(results))
        for row, res in enumerate(results):
            self._add_row(row, res)
        self.table.resizeColumnsToContents()
    
    def _add_row(self, row: int, result: Dict) -> None:
        a_item = QTableWidgetItem(result.get('drug_a', ''))
        b_item = QTableWidgetItem(result.get('drug_b', ''))
        risk_item = QTableWidgetItem(result.get('level', ''))
        
        mechanisms = result.get('mechanisms', []) or []
        mech_text = ', '.join(mechanisms) if isinstance(mechanisms, list) else mechanisms
        mech_item = QTableWidgetItem(mech_text)
        
        comments_item = QTableWidgetItem(result.get('comments', ''))
        
        color = self._get_color_for_level(result.get('level', ''))
        risk_item.setBackground(color)
        
        for item in (a_item, b_item, risk_item, mech_item, comments_item):
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        
        self.table.setItem(row, 0, a_item)
        self.table.setItem(row, 1, b_item)
        self.table.setItem(row, 2, risk_item)
        self.table.setItem(row, 3, mech_item)
        self.table.setItem(row, 4, comments_item)
    
    def _get_color_for_level(self, level: str) -> QColor:
        if level == 'Высокий':
            return QColor(220, 80, 80)
        elif level == 'Средний':
            return QColor(240, 200, 80)
        else:
            return QColor(160, 220, 160)
    

class InteractionWindow(QWidget):    
    def __init__(self, database: Database, parent=None):
        super().__init__(parent)
        self.db = database
        self.engine = InteractionEngine(self.db)
        self.setWindowTitle('Анализ взаимодействий лекарств')
        self.resize(1200, 600)
        self.setup_ui()
    
    def setup_ui(self) -> None:
        layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        
        left_layout = self._create_left_panel()
        top_layout.addLayout(left_layout, 1)
        
        right_layout = QVBoxLayout()
        self.results_table_widget = QTableWidget()
        self.results_table = InteractionResultsTable(self.results_table_widget)
        right_layout.addWidget(self.results_table_widget)
        top_layout.addLayout(right_layout, 2)
        
        layout.addLayout(top_layout)
        self.setLayout(layout)
    
    def _create_left_panel(self) -> QVBoxLayout:
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel('Выберите препараты (множественный выбор):'))
        
        self.drug_list = QListWidget()
        self.drug_list.setSelectionMode(QListWidget.MultiSelection)
        left_layout.addWidget(self.drug_list)
        
        for d in self.db.get_all_drugs():
            item = QListWidgetItem(f"{d['name']} ({d['form']})")
            item.setData(Qt.UserRole, d['id'])
            self.drug_list.addItem(item)
        
        analyze_btn = QPushButton('Проанализировать взаимодействия')
        analyze_btn.clicked.connect(self.on_analyze)
        left_layout.addWidget(analyze_btn)
        
        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(self.close)
        left_layout.addWidget(close_btn)
        
        return left_layout
    
    def on_analyze(self) -> None:
        selected = [it.data(Qt.UserRole) for it in self.drug_list.selectedItems()]
        if len(selected) < 2:
            QMessageBox.warning(self, 'Внимание', 'Выберите минимум два препарата для анализа')
            return
        try:
            results = self.engine.analyze_combination(selected)
            self.results_table.display(results)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка анализа: {e}')