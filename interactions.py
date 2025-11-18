from typing import Dict, List, Tuple, Any
from datetime import datetime
import csv
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QTableWidget, QTableWidgetItem, QFileDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from database import Database


class InteractionEngine:
    def __init__(self, database: Database):
        self.db = database

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

    def _shared_enzymes(self, metab_a: List[Dict], metab_b: List[Dict]) -> List[Tuple[Dict, Dict]]:
        pairs = []
        enzymes_b = {m['enzyme_name'].lower(): m for m in metab_b}
        for ma in metab_a:
            name = ma['enzyme_name'].lower()
            if name in enzymes_b:
                pairs.append((ma, enzymes_b[name]))
        return pairs

    def _shared_targets(self, targets_a: List[Dict], targets_b: List[Dict]) -> List[Tuple[Dict, Dict]]:
        pairs = []
        tb = {t['target_name'].lower(): t for t in targets_b}
        for ta in targets_a:
            name = ta['target_name'].lower()
            if name in tb:
                pairs.append((ta, tb[name]))
        return pairs

    def _effects_overlap(self, effects_a: List[Dict], effects_b: List[Dict]) -> List[Tuple[Dict, Dict]]:
        eb = {e['effect_name'].lower(): e for e in effects_b}
        pairs = []
        for ea in effects_a:
            name = ea['effect_name'].lower()
            if name in eb:
                pairs.append((ea, eb[name]))
        return pairs

    def analyze_interaction(self, drug_a_id: int, drug_b_id: int, use_cache: bool = True) -> Dict[str, Any]:
        if use_cache:
            cached = self.db.get_cached_interaction(drug_a_id, drug_b_id)
            if cached:
                return {
                    'drug_a': self.db.get_drug_by_id(cached['drug_a_id'])['name'],
                    'drug_b': self.db.get_drug_by_id(cached['drug_b_id'])['name'],
                    'score': float(cached['score']),
                    'level': cached['level'],
                    'mechanisms': cached.get('mechanisms') or '',
                    'comments': cached.get('notes') or '',
                    'cached': True,
                    'timestamp': cached.get('timestamp')
                }

        a = self.load_drug_data(drug_a_id)
        b = self.load_drug_data(drug_b_id)

        mechanisms: List[str] = []
        comments: List[str] = []

        metabolic_score = 0.0
        dynamical_score = 0.0
        toxicity_score = 0.0

        shared_enz = self._shared_enzymes(a['metabolism'], b['metabolism'])
        for ma, mb in shared_enz:
            role_a = (ma.get('role') or '').lower()
            role_b = (mb.get('role') or '').lower()
            if role_a == 'inhibitor' and role_b == 'substrate':
                metabolic_score += 0.6
                mechanisms.append(f"{ma['enzyme_name']} inhibition (A inhibits B)")
            elif role_b == 'inhibitor' and role_a == 'substrate':
                metabolic_score += 0.6
                mechanisms.append(f"{ma['enzyme_name']} inhibition (B inhibits A)")
            elif role_a == 'inducer' and role_b == 'substrate':
                metabolic_score += 0.3
                mechanisms.append(f"{ma['enzyme_name']} induction (A induces B)")
            elif role_b == 'inducer' and role_a == 'substrate':
                metabolic_score += 0.3
                mechanisms.append(f"{ma['enzyme_name']} induction (B induces A)")

        shared_targets = self._shared_targets(a['targets'], b['targets'])
        for ta, tb in shared_targets:
            et_a = (ta.get('effect_type') or '').lower()
            et_b = (tb.get('effect_type') or '').lower()
            if et_a == 'inhibitor' and et_b == 'inhibitor':
                dynamical_score += 0.5
                mechanisms.append(f"{ta['target_name']} additive inhibition")
            elif et_a == 'agonist' and et_b == 'agonist':
                dynamical_score += 0.4
                mechanisms.append(f"{ta['target_name']} additive activation")
            elif (et_a in ('agonist','activator') and et_b in ('antagonist','inhibitor')) or (et_b in ('agonist','activator') and et_a in ('antagonist','inhibitor')):
                dynamical_score += 0.8
                mechanisms.append(f"{ta['target_name']} opposing activity")

        shared_effects = self._effects_overlap(a['effects'], b['effects'])
        for ea, eb in shared_effects:
            level_a = int(ea.get('level') or 0)
            level_b = int(eb.get('level') or 0)
            toxicity_score += (level_a + level_b) / 10.0
            mechanisms.append(f"{ea['effect_name']} overlapping side-effect")

        w1, w2, w3 = 0.45, 0.35, 0.2
        raw_score = w1 * metabolic_score + w2 * dynamical_score + w3 * toxicity_score

        score = max(0.0, min(1.0, raw_score))

        if score < 0.3:
            level = 'Низкий'
        elif score < 0.6:
            level = 'Средний'
        else:
            level = 'Высокий'

        if 'hepat' in ' '.join(mechanisms).lower() or 'liver' in ' '.join(mechanisms).lower():
            comments.append('Потенциально повышенная гепатотоксичность')
        if toxicity_score > 0.5:
            comments.append('Риск токсичности')

        result = {
            'drug_a': a['drug']['name'],
            'drug_b': b['drug']['name'],
            'score': round(score, 3),
            'level': level,
            'mechanisms': mechanisms,
            'comments': '; '.join(comments) if comments else '',
            'cached': False,
            'timestamp': datetime.utcnow().isoformat()
        }

        try:
            mech_text = ', '.join(mechanisms) if mechanisms else None
            notes = result['comments'] if result['comments'] else None
            self.db.cache_interaction_result(drug_a_id, drug_b_id, result['score'], result['level'], mech_text, notes)
        except Exception:
            pass

        return result

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


class InteractionWindow(QWidget):
    def __init__(self, database: Database, parent=None):
        super().__init__(parent)
        self.db = database
        self.engine = InteractionEngine(self.db)
        self.setWindowTitle('Анализ взаимодействий лекарств')
        self.resize(900, 600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
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
        top_layout.addLayout(left_layout, 1)
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(['Лекарство 1', 'Лекарство 2', 'Риск', 'Механизм', 'Комментарии'])
        right_layout.addWidget(self.results_table)
        top_layout.addLayout(right_layout, 2)
        layout.addLayout(top_layout)
        self.setLayout(layout)

    def on_analyze(self):
        selected = [it.data(Qt.UserRole) for it in self.drug_list.selectedItems()]
        if len(selected) < 2:
            QMessageBox.warning(self, 'Внимание', 'Выберите минимум два препарата для анализа')
            return
        try:
            results = self.engine.analyze_combination(selected)
            self.display_results(results)
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка анализа: {e}')

    def display_results(self, results: List[Dict]):
        self.results_table.setRowCount(len(results))
        for row, res in enumerate(results):
            a_item = QTableWidgetItem(res.get('drug_a', ''))
            b_item = QTableWidgetItem(res.get('drug_b', ''))
            risk_item = QTableWidgetItem(res.get('level', ''))
            mech_item = QTableWidgetItem(', '.join(res.get('mechanisms', []) or []))
            comments_item = QTableWidgetItem(res.get('comments', ''))
            lvl = res.get('level', '')
            if lvl == 'Высокий':
                color = QColor(220, 80, 80)
            elif lvl == 'Средний':
                color = QColor(240, 200, 80)
            else:
                color = QColor(160, 220, 160)
            for it in (a_item, b_item, risk_item, mech_item, comments_item):
                it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            risk_item.setBackground(color)
            self.results_table.setItem(row, 0, a_item)
            self.results_table.setItem(row, 1, b_item)
            self.results_table.setItem(row, 2, risk_item)
            self.results_table.setItem(row, 3, mech_item)
            self.results_table.setItem(row, 4, comments_item)
        self.results_table.resizeColumnsToContents()

    def on_export_csv(self):
        if self.results_table.rowCount() == 0:
            QMessageBox.information(self, 'Информация', 'Нет данных для экспорта')
            return
        filename, _ = QFileDialog.getSaveFileName(self, 'Экспорт результатов', '', 'CSV Files (*.csv)')
        if not filename:
            return
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Drug A', 'Drug B', 'Risk', 'Mechanisms', 'Comments'])
                for r in range(self.results_table.rowCount()):
                    writer.writerow([
                        self.results_table.item(r, 0).text(),
                        self.results_table.item(r, 1).text(),
                        self.results_table.item(r, 2).text(),
                        self.results_table.item(r, 3).text(),
                        self.results_table.item(r, 4).text()
                    ])
            QMessageBox.information(self, 'Успех', f'Файл сохранён: {filename}')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка при сохранении: {e}')


def run_interaction_report():
    db = Database()
    engine = InteractionEngine(db)
    drugs = db.get_all_drugs()
    ids = [d['id'] for d in drugs]
    results = []
    total = 0
    for i in range(len(ids)):
        for j in range(i+1, len(ids)):
            a = ids[i]
            b = ids[j]
            try:
                res = engine.analyze_interaction(a, b)
            except Exception:
                continue
            total += 1
            if res.get('level') and res['level'] != 'Низкий':
                results.append(res)
    results.sort(key=lambda r: r['score'], reverse=True)
    csv_file = 'interaction_report.csv'
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Drug A', 'Drug B', 'Score', 'Level', 'Mechanisms', 'Comments', 'Timestamp'])
        for r in results:
            writer.writerow([r.get('drug_a'), r.get('drug_b'), r.get('score'), r.get('level'), '; '.join(r.get('mechanisms') or []), r.get('comments'), r.get('timestamp')])
