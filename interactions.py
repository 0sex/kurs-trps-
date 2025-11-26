from typing import Dict, List, Tuple, Any
from datetime import datetime
from abc import ABC, abstractmethod
import csv
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

    def analyze(self, pharm_a: Dict[str, Any], pharm_b: Dict[str, Any], drug_a_name: str, drug_b_name: str) -> Tuple[float, List[str], List[str]]:
        score = 0.0
        mechanisms = []
        comments = []
        metab_a = pharm_a.get('metabolism', [])
        metab_b = pharm_b.get('metabolism', [])
        score_m, mech_m, comm_m = self._analyze_metabolic(metab_a, metab_b)
        score += score_m
        mechanisms += mech_m
        comments += comm_m
        targets_a = pharm_a.get('targets', [])
        targets_b = pharm_b.get('targets', [])
        score_d, mech_d, comm_d = self._analyze_dynamical(targets_a, targets_b)
        score += score_d
        mechanisms += mech_d
        comments += comm_d
        effects_a = pharm_a.get('effects', [])
        effects_b = pharm_b.get('effects', [])
        score_t, mech_t, comm_t = self._analyze_toxicity(effects_a, effects_b, drug_a_name, drug_b_name)
        score += score_t
        mechanisms += mech_t
        comments += comm_t
        return score, mechanisms, comments

    def _analyze_metabolic(self, metab_a, metab_b):
        return 0.0, [], []

    def _analyze_dynamical(self, targets_a, targets_b):
        return 0.0, [], []

    def _analyze_toxicity(self, effects_a, effects_b, drug_a_name, drug_b_name):
        return 0.0, [], []


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
        drug_a_name = drug_a_data['drug']['name']
        drug_b_name = drug_b_data['drug']['name']
        
        if drug_a_data['targets']:
            mechanisms.append(f"{drug_a_name}: {len(drug_a_data['targets'])} целей")
        if drug_a_data['metabolism']:
            mechanisms.append(f"{drug_a_name}: {len(drug_a_data['metabolism'])} ферментов")
        if drug_a_data['effects']:
            mechanisms.append(f"{drug_a_name}: {len(drug_a_data['effects'])} известно побочных эффектов")
        
        if drug_b_data['targets']:
            mechanisms.append(f"{drug_b_name}: {len(drug_b_data['targets'])} целей")
        if drug_b_data['metabolism']:
            mechanisms.append(f"{drug_b_name}: {len(drug_b_data['metabolism'])} ферментов")
        if drug_b_data['effects']:
            mechanisms.append(f"{drug_b_name}: {len(drug_b_data['effects'])} известно побочных эффектов")
        
        if mechanisms:
            mechanisms.insert(0, f"Возможное взаимодействие: {drug_a_name} + {drug_b_name} (оба фармакологически активны)")
        else:
            mechanisms.append('Нет особого фармакологического профиля для взаимодействия')
        
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
    
    def export_to_csv(self, filename: str) -> None:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Drug A', 'Drug B', 'Risk', 'Mechanisms', 'Comments'])
            for r in range(self.table.rowCount()):
                writer.writerow([
                    self.table.item(r, 0).text(),
                    self.table.item(r, 1).text(),
                    self.table.item(r, 2).text(),
                    self.table.item(r, 3).text(),
                    self.table.item(r, 4).text()
                ])


class InteractionWindow(QWidget):    
    def __init__(self, database: Database, parent=None):
        super().__init__(parent)
        self.db = database
        self.engine = InteractionEngine(self.db)
        self.setWindowTitle('Анализ взаимодействий лекарств')
        self.resize(900, 600)
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
        
        export_btn = QPushButton('Экспорт в CSV')
        export_btn.clicked.connect(self.on_export_csv)
        left_layout.addWidget(export_btn)
        
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
    
    def on_export_csv(self) -> None:
        if self.results_table_widget.rowCount() == 0:
            QMessageBox.information(self, 'Информация', 'Нет данных для экспорта')
            return
        
        filename, _ = QFileDialog.getSaveFileName(self, 'Экспорт результатов', '', 'CSV Files (*.csv)')
        if not filename:
            return
        
        try:
            self.results_table.export_to_csv(filename)
            QMessageBox.information(self, 'Успех', f'Файл сохранён: {filename}')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при сохранении: {e}')



class InteractionReporter:
    def __init__(self, engine: InteractionEngine):
        self.engine = engine
    
    def generate_report(self, output_file: str = 'interaction_report.csv') -> Dict[str, int]:
        db = self.engine.db
        drugs = db.get_all_drugs()
        drug_ids = [d['id'] for d in drugs]
        
        results = []
        total_analyzed = 0
        
        for i in range(len(drug_ids)):
            for j in range(i + 1, len(drug_ids)):
                try:
                    res = self.engine.analyze_interaction(drug_ids[i], drug_ids[j])
                    total_analyzed += 1
                    
                    if res.get('level') and res['level'] != 'Низкий':
                        results.append(res)
                except Exception:
                    continue
        
        results.sort(key=lambda r: r['score'], reverse=True)
        
        self._write_results_to_csv(output_file, results)
        
        return {
            'total_analyzed': total_analyzed,
            'significant_found': len(results),
            'output_file': output_file
        }
    
    def _write_results_to_csv(self, filename: str, results: List[Dict]) -> None:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Drug A', 'Drug B', 'Score', 'Level', 'Mechanisms', 'Comments', 'Timestamp'])
            for r in results:
                mechanisms_text = '; '.join(r.get('mechanisms') or [])
                writer.writerow([
                    r.get('drug_a'),
                    r.get('drug_b'),
                    r.get('score'),
                    r.get('level'),
                    mechanisms_text,
                    r.get('comments'),
                    r.get('timestamp')
                ])


def run_interaction_report():
    db = Database()
    engine = InteractionEngine(db)
    reporter = InteractionReporter(engine)
    report = reporter.generate_report()
    
    print(f"Report generated: {report['output_file']}")
    print(f"Total pairs analyzed: {report['total_analyzed']}")
    print(f"Significant interactions found: {report['significant_found']}")
