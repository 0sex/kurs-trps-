from typing import Dict, List, Tuple, Any
from datetime import datetime
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


# --- Synonyms and normalization maps ---
TARGET_SYNONYMS = {
    "ltcc": "l-type calcium channel",
    "l-vscc": "l-type calcium channel",
    "кальциевый канал l-типа": "l-type calcium channel",
    "сердечный кальциевый канал": "l-type calcium channel",
}

EFFECT_SYNONYMS = {
    "гипотензия": "низкое давление",
    "ортостатическая гипотензия": "низкое давление",
    "low blood pressure": "низкое давление",

    "гипонатриемия": "низкий натрий",
    "низкий уровень натрия": "низкий натрий",

    "жк-кровотечение": "желудочно-кишечное кровотечение",
    "ulcer": "желудочно-кишечкое кровотечение",
}


# Global tuning weights (metabolic, dynamical, toxicity)
# Increased back to get proper distribution now that score/mechanism are separated
WEIGHTS = {
    'metabolic': 0.35,
    'dynamical': 0.25,
    'toxicity': 0.15
}

# Additional synonym suggestions (collected from DB frequency)
TARGET_SYNONYMS.update({
    'cox1': 'COX1',
    'cox2': 'COX2',
    'cox3': 'COX3',
    'sert': 'SERT',
    'at1-рецептор': 'AT1 receptor',
    'na-k-2cl котранспортер': 'Na-K-2Cl cotransporter',
    'na-cl котранспортер': 'Na-Cl cotransporter',
    'h+/k+-атфаза': 'H+/K+-ATPase',
})

EFFECT_SYNONYMS.update({
    'гипотензия': 'низкое давление',
    'ортостатическая гипотензия': 'низкое давление',
    'гипонатриемия': 'низкий натрий',
    'серотониновый синдром': 'серотониновый синдром',
})


def normalize(text: str) -> str:
    if not text:
        return ""
    text = str(text).strip().lower()
    if not text:
        return ""

    # exact synonym maps
    if text in TARGET_SYNONYMS:
        return TARGET_SYNONYMS[text]
    if text in EFFECT_SYNONYMS:
        return EFFECT_SYNONYMS[text]

    # basic normalization: remove punctuation and multiple spaces
    text = re.sub(r"[^a-z0-9а-яё -]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fuzzy_match(key: str, candidates: List[str], cutoff: float = 0.65) -> List[str]:
    if not key or not candidates:
        return []
    key_n = normalize(key)
    cand_map = {normalize(c): c for c in candidates}
    normalized_candidates = list(cand_map.keys())
    matches = difflib.get_close_matches(key_n, normalized_candidates, n=3, cutoff=cutoff)
    return [cand_map[m] for m in matches]


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
        """Find shared enzymes. More permissive - adds any shared enzyme."""
        pairs = []
        enzymes_b = {normalize(m.get('enzyme_name', '')): m for m in metab_b}
        for ma in metab_a:
            name = normalize(ma.get('enzyme_name', ''))
            if not name:
                continue
            if name in enzymes_b:
                pairs.append((ma, enzymes_b[name]))
                continue
            # fuzzy fallback - more permissive
            matches = difflib.get_close_matches(name, list(enzymes_b.keys()), n=1, cutoff=0.70)
            if matches:
                pairs.append((ma, enzymes_b[matches[0]]))
        return pairs

    def _shared_targets(self, targets_a: List[Dict], targets_b: List[Dict]) -> List[Tuple[Dict, Dict]]:
        """Find shared targets between two drugs. More permissive than before - adds any shared target."""
        pairs = []
        mapped_b = {normalize(t.get('target_name', '')): t for t in targets_b}
        b_keys = list(mapped_b.keys())
        for ta in targets_a:
            na = normalize(ta.get('target_name', ''))
            if not na:
                continue
            if na in mapped_b:
                pairs.append((ta, mapped_b[na]))
                continue
            # fuzzy try - more permissive cutoff
            matches = difflib.get_close_matches(na, b_keys, n=2, cutoff=0.65)
            for m in matches:
                pairs.append((ta, mapped_b[m]))
        return pairs

    def _effects_overlap(self, effects_a: List[Dict], effects_b: List[Dict]) -> List[Tuple[Dict, Dict]]:
        eb = {normalize(e.get('effect_name', '')): e for e in effects_b}
        pairs = []
        b_keys = list(eb.keys())
        for ea in effects_a:
            name = normalize(ea.get('effect_name', ''))
            if not name:
                continue
            if name in eb:
                pairs.append((ea, eb[name]))
                continue
            matches = difflib.get_close_matches(name, b_keys, n=2, cutoff=0.75)
            for m in matches:
                pairs.append((ea, eb[m]))
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
            if role_a == 'ингибитор' and role_b == 'субстрат':
                metabolic_score += 0.50
                mechanisms.append(f"{ma['enzyme_name']}: ингибирование (A ингибирует B)")
            elif role_b == 'ингибитор' and role_a == 'субстрат':
                metabolic_score += 0.50
                mechanisms.append(f"{ma['enzyme_name']}: ингибирование (B ингибирует A)")
            elif role_a == 'индуктор' and role_b == 'субстрат':
                metabolic_score += 0.25
                mechanisms.append(f"{ma['enzyme_name']}: индукция (A индуцирует B)")
            elif role_b == 'индуктор' and role_a == 'субстрат':
                metabolic_score += 0.25
                mechanisms.append(f"{ma['enzyme_name']}: индукция (B индуцирует A)")
            else:
                # Any shared enzyme is a mechanism
                metabolic_score += 0.15
                mechanisms.append(f"{ma['enzyme_name']}: оба препарата метаболизируются этим ферментом")

        shared_targets = self._shared_targets(a['targets'], b['targets'])
        for ta, tb in shared_targets:
            et_a = (ta.get('effect_type') or '').lower()
            et_b = (tb.get('effect_type') or '').lower()
            target_name = ta.get('target_name', 'Unknown')
            
            # Always add mechanism for shared target, even if effect types differ
            mechanisms.append(f"{target_name}: оба препарата действуют на эту цель ({et_a} + {et_b})")
            
            # Boost score based on effect type compatibility
            if et_a == 'ингибитор' and et_b == 'ингибитор':
                dynamical_score += 0.40
                mechanisms[-1] = f"{target_name}: суммарное ингибирование"
            elif et_a == 'агонист' and et_b == 'агонист':
                dynamical_score += 0.35
                mechanisms[-1] = f"{target_name}: суммарная активация"
            elif (et_a in ('агонист','активатор') and et_b in ('антагонист','ингибитор')) or (et_b in ('агонист','активатор') and et_a in ('антагонист','ингибитор')):
                dynamical_score += 0.30
                mechanisms[-1] = f"{target_name}: противоположное действие"
            else:
                # Different or unclear effect types - still add small score
                dynamical_score += 0.10
                mechanisms[-1] = f"{target_name}: оба препарата действуют на эту цель"

        shared_effects = self._effects_overlap(a['effects'], b['effects'])
        for ea, eb in shared_effects:
            level_a = int(ea.get('level') or 0)
            level_b = int(eb.get('level') or 0)
            effect_name = ea.get('effect_name', 'Unknown')
            # Reasonable toxicity contribution for shared effects
            toxicity_score += (level_a + level_b) / 5.0
            # Always add mechanism - this is an actual shared side effect
            mechanisms.append(f"{effect_name}: оба препарата могут вызвать этот побочный эффект (уровень {level_a}+{level_b})")

        # --- Custom clinical rules (semantic/class interactions) ---
        drugA = a['drug']['name'].lower()
        drugB = b['drug']['name'].lower()

        ssri_keywords = ['сертралин', 'флуоксетин', 'флувоксамин', 'пароксетин', 'эсциталопрам', 'ssri']
        acei_keywords = ['рамиприл', 'эналаприл', 'лизиноприл', 'периндоприл', 'каптоприл', 'ризиноприл', 'ace-i', 'ace inhibitor']
        beta_keywords = ['метопролол', 'атенолол', 'пропранолол', 'бисопролол', 'acebutolol']
        nsaid_keywords = ['ибупрофен', 'диклофенак', 'напроксен', 'аспирин', 'nsaid']

        # Helper extractors (handle DB keys vs JSON keys)
        def _get_target_names(entry_list):
            names = []
            for t in entry_list or []:
                n = t.get('target_name') or t.get('name') or ''
                n = normalize(n)
                if n:
                    names.append(n)
            return names

        def _get_effect_names(entry_list):
            names = []
            for e in entry_list or []:
                n = e.get('effect_name') or e.get('name') or ''
                n = normalize(n)
                if n:
                    names.append(n)
            return names

        def _get_enzymes(entry_list):
            enzymes = []
            for m in entry_list or []:
                en = m.get('enzyme_name') or m.get('enzyme') or ''
                role = (m.get('role') or '').strip().lower()
                en_n = normalize(en)
                if en_n:
                    enzymes.append((en_n, role))
            return enzymes

        a_targets = _get_target_names(a.get('targets', []))
        b_targets = _get_target_names(b.get('targets', []))
        a_effects = _get_effect_names(a.get('effects', []))
        b_effects = _get_effect_names(b.get('effects', []))
        a_enz = _get_enzymes(a.get('metabolism', []))
        b_enz = _get_enzymes(b.get('metabolism', []))

        # Precompute class flags for clarity
        a_is_ssri = any(k in drugA for k in ssri_keywords) or any(('sert' in t or 'seroton' in t) for t in a_targets + a_effects)
        b_is_ssri = any(k in drugB for k in ssri_keywords) or any(('sert' in t or 'seroton' in t) for t in b_targets + b_effects)
        a_is_acei = any(k in drugA for k in acei_keywords) or any(('апф' in t or 'ace' in t) for t in a_targets + a_effects)
        b_is_acei = any(k in drugB for k in acei_keywords) or any(('апф' in t or 'ace' in t) for t in b_targets + b_effects)
        a_is_beta = any(k in drugA for k in beta_keywords) or any(('beta' in t or 'бета' in t) for t in a_targets)
        b_is_beta = any(k in drugB for k in beta_keywords) or any(('beta' in t or 'бета' in t) for t in b_targets)
        a_is_nsaid = any(k in drugA for k in nsaid_keywords) or any(('nsaid' in t or 'нпвп' in t) for t in a_targets + a_effects)
        b_is_nsaid = any(k in drugB for k in nsaid_keywords) or any(('nsaid' in t or 'нпвп' in t) for t in b_targets + b_effects)

        # Rule: SSRI + ACE inhibitor → hyponatremia risk
        if (a_is_ssri and b_is_acei) or (b_is_ssri and a_is_acei):
            toxicity_score += 0.15
            comments.append('Риск гипонатриемии повышен')

        # Rule: SSRI + beta-blocker → bradycardia risk
        if (a_is_ssri and b_is_beta) or (b_is_ssri and a_is_beta):
            dynamical_score += 0.15
            comments.append('Повышение риска брадикардии')

        # Rule: NSAIDs + ACE inhibitors → renal risk (triple whammy pattern)
        if (a_is_nsaid and b_is_acei) or (b_is_nsaid and a_is_acei):
            toxicity_score += 0.20
            comments.append('Риск ухудшения функции почек')

        # --- Enzyme-based clinical rules: detect strong CYP inhibitor + substrate pairs ---
        major_cyps = ['cyp2d6', 'cyp3a4', 'cyp2c9', 'cyp2c19', 'cyp1a2']
        for enz, role in a_enz:
            for benz, brole in b_enz:
                for c in major_cyps:
                    if c in enz and c in benz:
                        if (role == 'ингибитор' and brole == 'субстрат') or (brole == 'ингибитор' and role == 'субстрат'):
                            metabolic_score += 0.25
                            mechanisms.append(f'Shared {c.upper()} substrate + inhibitor')
                            comments.append(f'Взаимодействие через {c.upper()} (ингибитор + субстрат)')

        # --- Serotonin syndrome detection (target/effect based) ---
        serotonin_markers = ['sert', 'seroton', 'серотон']
        if (any(any(m in t for m in serotonin_markers) for t in a_targets + a_effects) and any(any(m in t for m in serotonin_markers) for t in b_targets + b_effects)) or ('серотониновый синдром' in a_effects and 'серотониновый синдром' in b_effects):
            toxicity_score += 0.25
            comments.append('Риск серотонинового синдрома')

        # --- Hyperkalemia risk (aldosterone antagonists + ACE/ARB) ---
        if (any('альдостерон' in t or 'спиронолактон' in drugA for t in a_targets + a_effects) and any('апф' in t or 'арб' in t or any(k in drugB for k in acei_keywords) for t in b_targets + b_effects)) or (any('альдостерон' in t or 'спиронолактон' in drugB for t in b_targets + b_effects) and any('апф' in t or 'арб' in t or any(k in drugA for k in acei_keywords) for t in a_targets + a_effects)):
            toxicity_score += 0.20
            comments.append('Риск гиперкалиемии')

        # --- Bleeding risk: antiplatelet/anticoagulant + NSAID/antiplatelet ---
        bleed_markers = ['жк-кровотечение', 'желудочно-кишечное кровотечение', 'bleeding', 'anticoagulant', 'antiplatelet', 'агрегация']
        if (any(m in ' '.join(a_effects) for m in bleed_markers) or any('cox1' in t or 'агрегация' in t for t in a_targets)) and (any(m in ' '.join(b_effects) for m in bleed_markers) or any('cox1' in t or 'агрегация' in t for t in b_targets)):
            toxicity_score += 0.20
            comments.append('Повышенный риск кровотечения')

        # --- QT prolongation risk (hERG/Ikr targets) ---
        qt_markers = ['herg', 'ikr', 'пролонгация qt', 'удлинение qt']
        if any(any(m in t for m in qt_markers) for t in a_targets + a_effects) and any(any(m in t for m in qt_markers) for t in b_targets + b_effects):
            toxicity_score += 0.15
            comments.append('Риск удлинения QT интервала')

        # use global WEIGHTS so we can tune without changing logic
        w1 = WEIGHTS.get('metabolic', 0.45)
        w2 = WEIGHTS.get('dynamical', 0.35)
        w3 = WEIGHTS.get('toxicity', 0.2)
        raw_score = w1 * metabolic_score + w2 * dynamical_score + w3 * toxicity_score

        score = max(0.0, min(1.0, raw_score))

        # If no mechanisms found by specific/shared rules, add mechanisms based on individual drug profiles
        if not mechanisms:
            # Check drug A's pharmacology
            drug_a_mechanisms = []
            if a_targets:
                drug_a_mechanisms.append(f"{a['drug']['name']}: {len(a_targets)} целей")
            if a_enz:
                drug_a_mechanisms.append(f"{a['drug']['name']}: {len(a_enz)} ферментов")
            if a_effects:
                drug_a_mechanisms.append(f"{a['drug']['name']}: {len(a_effects)} известно побочных эффектов")
            
            # Check drug B's pharmacology
            drug_b_mechanisms = []
            if b_targets:
                drug_b_mechanisms.append(f"{b['drug']['name']}: {len(b_targets)} целей")
            if b_enz:
                drug_b_mechanisms.append(f"{b['drug']['name']}: {len(b_enz)} ферментов")
            if b_effects:
                drug_b_mechanisms.append(f"{b['drug']['name']}: {len(b_effects)} известно побочных эффектов")
            
            # If both drugs have pharmacological activity, they may interact
            if (drug_a_mechanisms or drug_b_mechanisms):
                mechanisms.extend(drug_a_mechanisms)
                mechanisms.extend(drug_b_mechanisms)
                mechanisms.insert(0, f"Возможное взаимодействие: {a['drug']['name']} + {b['drug']['name']} (оба фармакологически активны)")
        
        # Ensure mechanisms are never empty - always show something
        if not mechanisms:
            mechanisms.append('Нет особого фармакологического профиля для взаимодействия')
        
        # Determine level based ONLY on numerical score, not on presence of mechanisms
        if score < 0.3:
            level = 'Низкий'
        elif score < 0.6:
            level = 'Средний'
        else:
            level = 'Высокий'

        mechanisms_text = ' '.join(mechanisms).lower()
        if 'гепато' in mechanisms_text or 'печён' in mechanisms_text:
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
        
        # clear_cache_btn = QPushButton('Очистить кэш')
        # clear_cache_btn.clicked.connect(self.on_clear_cache)
        # left_layout.addWidget(clear_cache_btn)
        
        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(self.close)
        left_layout.addWidget(close_btn)
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
            
            # Handle mechanisms which could be a list or a string from cache
            mechanisms = res.get('mechanisms', []) or []
            if isinstance(mechanisms, str):
                mech_text = mechanisms
            else:
                mech_text = ', '.join(mechanisms)
            mech_item = QTableWidgetItem(mech_text)
            
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
            # def on_clear_cache(self):
            #     try:
            #         conn = self.db._get_connection()
            #         conn.execute('DELETE FROM drug_interaction_cache')
            #         conn.commit()
            #         conn.close()
            #         QMessageBox.information(self, 'Успех', 'Кэш взаимодействий очищен')
            #     except Exception as e:
            #         QMessageBox.critical(self, 'Ошибка', f'Ошибка при очистке кэша: {e}')
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
