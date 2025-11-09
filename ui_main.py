"""
Main UI module for the drug analog search application.

This module defines the graphical user interface using PyQt5.
"""

import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QFormLayout, QDoubleSpinBox, QComboBox,
    QMenuBar, QMenu, QAction, QFileDialog, QCheckBox, QGroupBox,
    QHeaderView, QStatusBar, QTextEdit, QSplitter
)
from PyQt5.QtCore import Qt, QAbstractTableModel, pyqtSignal
from PyQt5.QtGui import QFont
from typing import List, Dict, Optional, Tuple
import csv
import json
from datetime import datetime


class AddDrugDialog(QDialog):
    """Dialog for adding new drugs to the database."""
    
    def __init__(self, parent=None, existing_drug=None):
        """
        Initialize dialog.
        
        Args:
            parent: Parent widget
            existing_drug: Existing drug data for editing (optional)
        """
        super().__init__(parent)
        self.existing_drug = existing_drug
        self.setWindowTitle("Редактировать препарат" if existing_drug else "Добавить препарат")
        self.setModal(True)
        self.setup_ui()
        
        if existing_drug:
            self.load_drug_data()
    
    def setup_ui(self):
        """Create UI elements."""
        layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.substance_edit = QLineEdit()
        self.substance_edit.setPlaceholderText("Можно несколько через '+' или ','")
        self.form_edit = QLineEdit()
        self.manufacturer_edit = QLineEdit()
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0.0, 99999.0)
        self.price_spin.setDecimals(2)
        self.price_spin.setSingleStep(1.0)
        self.price_spin.setSuffix(" руб.")
        self.contraindications_edit = QLineEdit()
        self.contraindications_edit.setPlaceholderText("Можно несколько через ',' или ';'")
        
        layout.addRow("Название:", self.name_edit)
        layout.addRow("Действующее вещество:", self.substance_edit)
        layout.addRow("Форма выпуска:", self.form_edit)
        layout.addRow("Производитель:", self.manufacturer_edit)
        layout.addRow("Цена:", self.price_spin)
        layout.addRow("Противопоказания:", self.contraindications_edit)
        
        buttons = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        cancel_btn = QPushButton("Отмена")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        
        layout.addRow(buttons)
        self.setLayout(layout)
    
    def load_drug_data(self):
        """Load existing drug data into form."""
        if self.existing_drug:
            self.name_edit.setText(self.existing_drug['name'])
            self.substance_edit.setText(self.existing_drug['substance'])
            self.form_edit.setText(self.existing_drug['form'])
            self.manufacturer_edit.setText(self.existing_drug['manufacturer'])
            self.price_spin.setValue(self.existing_drug['price'])
            self.contraindications_edit.setText(self.existing_drug.get('contraindications', '') or '')
    
    def get_data(self) -> Dict:
        """Get form data as dictionary."""
        return {
            'name': self.name_edit.text().strip(),
            'substance': self.substance_edit.text().strip(),
            'form': self.form_edit.text().strip(),
            'manufacturer': self.manufacturer_edit.text().strip(),
            'price': self.price_spin.value(),
            'contraindications': self.contraindications_edit.text().strip()
        }


class ComparisonDialog(QDialog):
    """Dialog for comparing multiple drugs."""
    
    def __init__(self, drugs: List[Dict], parent=None):
        """
        Initialize comparison dialog.
        
        Args:
            drugs: List of drug dictionaries to compare
            parent: Parent widget
        """
        super().__init__(parent)
        self.drugs = drugs
        self.setWindowTitle("Сравнение препаратов")
        self.setModal(True)
        self.resize(800, 400)
        self.setup_ui()
    
    def setup_ui(self):
        """Create UI elements."""
        layout = QVBoxLayout()
        
        # Create comparison table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.drugs))
        self.table.setRowCount(7)
        self.table.setHorizontalHeaderLabels([drug['name'] for drug in self.drugs])
        self.table.setVerticalHeaderLabels([
            "Действующее вещество",
            "Форма выпуска",
            "Производитель",
            "Цена",
            "Противопоказания",
            "Цена за единицу",
            "Разница с базовой ценой"
        ])
        
        # Fill table data
        for col, drug in enumerate(self.drugs):
            self.table.setItem(0, col, QTableWidgetItem(str(drug['substance'])))
            self.table.setItem(1, col, QTableWidgetItem(str(drug['form'])))
            self.table.setItem(2, col, QTableWidgetItem(str(drug['manufacturer'])))
            self.table.setItem(3, col, QTableWidgetItem(f"{drug['price']:.2f} руб."))
            self.table.setItem(4, col, QTableWidgetItem(str(drug.get('contraindications', '') or '')))
            
            # Calculate price per unit (simplified)
            price_per_unit = f"{drug['price']:.2f}"
            self.table.setItem(5, col, QTableWidgetItem(price_per_unit))
            
            # Calculate difference from first drug
            if col > 0:
                diff = drug['price'] - self.drugs[0]['price']
                diff_text = f"{'+' if diff > 0 else ''}{diff:.2f} руб."
                self.table.setItem(6, col, QTableWidgetItem(diff_text))
            else:
                self.table.setItem(6, col, QTableWidgetItem("—"))
        
        # Make table read-only
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Auto-size columns
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.table)
        
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        self.init_database()
        self.setup_ui()
        self.load_filter_options()
        self.load_all_drugs()
    
    def init_database(self):
        """Initialize database and populate sample data."""
        from database import Database
        from search_engine import SearchEngine
        
        self.database = Database()
        self.search_engine = SearchEngine(self.database)
        
        # Populate with sample data if database is empty
        self.database.populate_sample_data()
    
    def setup_ui(self):
        """Create and setup UI elements."""
        self.setWindowTitle("Поиск аналогов лекарственных препаратов")
        self.setMinimumSize(1000, 600)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Search section
        search_group = QGroupBox("Поиск аналогов")
        search_layout = QVBoxLayout()
        
        search_input_layout = QHBoxLayout()
        search_label = QLabel("Название препарата:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите название препарата...")
        search_btn = QPushButton("Найти аналоги")
        search_btn.clicked.connect(self.search_analogs)
        self.search_input.returnPressed.connect(search_btn.click)
        
        search_input_layout.addWidget(search_label)
        search_input_layout.addWidget(self.search_input)
        search_input_layout.addWidget(search_btn)
        search_layout.addLayout(search_input_layout)
        
        # Filters
        filters_layout = QHBoxLayout()
        
        filter_label = QLabel("Фильтры:")
        self.form_filter = QComboBox()
        self.form_filter.setEditable(True)
        self.form_filter.setCurrentText("")
        self.form_filter.setPlaceholderText("Форма выпуска")
        
        self.manufacturer_filter = QComboBox()
        self.manufacturer_filter.setEditable(True)
        self.manufacturer_filter.setCurrentText("")
        self.manufacturer_filter.setPlaceholderText("Производитель")
        
        self.min_price_filter = QDoubleSpinBox()
        self.min_price_filter.setRange(0.0, 99999.0)
        self.min_price_filter.setDecimals(2)
        self.min_price_filter.setSuffix(" руб.")
        self.min_price_filter.setSpecialValueText("Мин. цена")
        
        self.max_price_filter = QDoubleSpinBox()
        self.max_price_filter.setRange(0.0, 99999.0)
        self.max_price_filter.setDecimals(2)
        self.max_price_filter.setSuffix(" руб.")
        self.max_price_filter.setValue(99999.0)
        self.max_price_filter.setSpecialValueText("Макс. цена")
        
        self.contraindication_filter = QComboBox()
        self.contraindication_filter.setEditable(True)
        self.contraindication_filter.setCurrentText("")
        self.contraindication_filter.setPlaceholderText("Исключить противопоказание")
        
        clear_filters_btn = QPushButton("Очистить")
        clear_filters_btn.clicked.connect(self.clear_filters)
        
        filters_layout.addWidget(filter_label)
        filters_layout.addWidget(self.form_filter)
        filters_layout.addWidget(self.manufacturer_filter)
        filters_layout.addWidget(self.min_price_filter)
        filters_layout.addWidget(self.max_price_filter)
        filters_layout.addWidget(QLabel("Исключить:"))
        filters_layout.addWidget(self.contraindication_filter)
        filters_layout.addWidget(clear_filters_btn)
        search_layout.addLayout(filters_layout)
        
        search_group.setLayout(search_layout)
        main_layout.addWidget(search_group)
        
        # Results section
        results_group = QGroupBox("Результаты поиска")
        results_layout = QVBoxLayout()
        
        # Action buttons
        action_buttons_layout = QHBoxLayout()
        self.compare_btn = QPushButton("Сравнить выбранные")
        self.compare_btn.clicked.connect(self.compare_selected)
        self.compare_btn.setEnabled(False)
        
        self.export_csv_btn = QPushButton("Экспорт в CSV")
        self.export_csv_btn.clicked.connect(self.export_to_csv)
        self.export_csv_btn.setEnabled(False)
        
        self.export_json_btn = QPushButton("Экспорт в JSON")
        self.export_json_btn.clicked.connect(self.export_to_json)
        self.export_json_btn.setEnabled(False)
        
        action_buttons_layout.addWidget(self.compare_btn)
        action_buttons_layout.addWidget(self.export_csv_btn)
        action_buttons_layout.addWidget(self.export_json_btn)
        action_buttons_layout.addStretch()
        
        results_layout.addLayout(action_buttons_layout)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels([
            "Выбор",
            "Название",
            "Действующее вещество",
            "Форма",
            "Производитель",
            "Противопоказания",
            "Цена"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        results_layout.addWidget(self.results_table)
        results_group.setLayout(results_layout)
        main_layout.addWidget(results_group)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create status bar
        self.statusBar().showMessage("Готов к работе")
    
    def create_menu_bar(self):
        """Create application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("Файл")
        
        add_action = QAction("Добавить препарат", self)
        add_action.triggered.connect(self.add_drug)
        file_menu.addAction(add_action)
        
        edit_action = QAction("Редактировать препарат", self)
        edit_action.triggered.connect(self.edit_drug)
        file_menu.addAction(edit_action)
        
        delete_action = QAction("Удалить препарат", self)
        delete_action.triggered.connect(self.delete_drug)
        file_menu.addAction(delete_action)
        
        file_menu.addSeparator()
        
        refresh_action = QAction("Показать все препараты", self)
        refresh_action.triggered.connect(self.load_all_drugs)
        file_menu.addAction(refresh_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("Справка")
        
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def load_filter_options(self):
        """Load filter options from database."""
        forms = self.database.get_all_forms()
        manufacturers = self.database.get_all_manufacturers()
        contraindications = self.database.get_all_contraindications()
        
        self.form_filter.clear()
        self.form_filter.addItem("")
        self.form_filter.addItems(forms)
        
        self.manufacturer_filter.clear()
        self.manufacturer_filter.addItem("")
        self.manufacturer_filter.addItems(manufacturers)
        
        self.contraindication_filter.clear()
        self.contraindication_filter.addItem("")
        self.contraindication_filter.addItems(contraindications)
    
    def load_all_drugs(self):
        """Load all drugs from database and display them."""
        try:
            all_drugs = self.database.get_all_drugs()
            
            if all_drugs:
                # Convert to format expected by display_results: (drug, similarity)
                formatted_results = [(drug, 1.0) for drug in all_drugs]
                self.display_results(formatted_results)
                self.statusBar().showMessage(f"Загружено препаратов: {len(all_drugs)}")
            else:
                self.statusBar().showMessage("База данных пуста")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки препаратов: {str(e)}")
            self.statusBar().showMessage("Ошибка загрузки данных")
    
    def search_analogs(self):
        """Perform analog search based on input and filters."""
        query = self.search_input.text().strip()
        
        if not query:
            QMessageBox.warning(self, "Внимание", "Введите название препарата для поиска")
            return
        
        try:
            # Get filter values
            form = self.form_filter.currentText().strip() if self.form_filter.currentText().strip() else None
            manufacturer = self.manufacturer_filter.currentText().strip() if self.manufacturer_filter.currentText().strip() else None
            min_price = self.min_price_filter.value() if self.min_price_filter.value() > 0 else None
            max_price = self.max_price_filter.value() if self.max_price_filter.value() < 99999 else None
            exclude_contraindication = self.contraindication_filter.currentText().strip() if self.contraindication_filter.currentText().strip() else None
            
            # Perform search
            results = self.search_engine.search_with_filters(
                query, form, manufacturer, min_price, max_price, exclude_contraindication
            )
            
            # Display results
            self.display_results(results)
            
            if not results:
                self.statusBar().showMessage("Аналоги не найдены")
                QMessageBox.information(self, "Информация", 
                                      "Не найдено аналогов для указанного препарата")
            else:
                self.statusBar().showMessage(f"Найдено аналогов: {len(results)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка поиска: {str(e)}")
            self.statusBar().showMessage("Ошибка выполнения поиска")
    
    def display_results(self, results: List[Tuple[Dict, float]]):
        """Display search results in table."""
        self.results_table.setRowCount(len(results))
        
        for row, (drug, similarity) in enumerate(results):
            # Checkbox
            checkbox = QTableWidgetItem()
            checkbox.setCheckState(Qt.Unchecked)
            self.results_table.setItem(row, 0, checkbox)
            
            # Name
            name_item = QTableWidgetItem(drug['name'])
            name_item.setData(Qt.UserRole, drug['id'])
            self.results_table.setItem(row, 1, name_item)
            
            # Substance
            self.results_table.setItem(row, 2, QTableWidgetItem(drug['substance']))
            
            # Form
            self.results_table.setItem(row, 3, QTableWidgetItem(drug['form']))
            
            # Manufacturer
            self.results_table.setItem(row, 4, QTableWidgetItem(drug['manufacturer']))
            
            # Contraindications
            contraindications = drug.get('contraindications', '') or ''
            self.results_table.setItem(row, 5, QTableWidgetItem(contraindications))
            
            # Price
            price_item = QTableWidgetItem(f"{drug['price']:.2f} руб.")
            price_item.setData(Qt.UserRole, drug['price'])
            self.results_table.setItem(row, 6, price_item)
        
        # Enable buttons
        self.compare_btn.setEnabled(len(results) > 0)
        self.export_csv_btn.setEnabled(len(results) > 0)
        self.export_json_btn.setEnabled(len(results) > 0)
    
    def clear_filters(self):
        """Clear all filters."""
        self.form_filter.setCurrentText("")
        self.manufacturer_filter.setCurrentText("")
        self.min_price_filter.setValue(0.0)
        self.max_price_filter.setValue(99999.0)
        self.contraindication_filter.setCurrentText("")
    
    def get_selected_drug_ids(self) -> List[int]:
        """Get IDs of selected drugs in results table."""
        selected_ids = []
        for row in range(self.results_table.rowCount()):
            checkbox = self.results_table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                name_item = self.results_table.item(row, 1)
                if name_item:
                    drug_id = name_item.data(Qt.UserRole)
                    if drug_id:
                        selected_ids.append(drug_id)
        return selected_ids
    
    def compare_selected(self):
        """Compare selected drugs."""
        selected_ids = self.get_selected_drug_ids()
        
        if len(selected_ids) < 2:
            QMessageBox.warning(self, "Внимание", 
                              "Выберите не менее двух препаратов для сравнения")
            return
        
        drugs = self.search_engine.compare_drugs(selected_ids)
        dialog = ComparisonDialog(drugs, self)
        dialog.exec_()
    
    def export_to_csv(self):
        """Export results to CSV file."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в CSV", "", "CSV Files (*.csv)"
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Название", "Действующее вещество", "Форма выпуска",
                    "Производитель", "Противопоказания", "Цена"
                ])
                
                for row in range(self.results_table.rowCount()):
                    name_item = self.results_table.item(row, 1)
                    if name_item:
                        writer.writerow([
                            self.results_table.item(row, 1).text(),
                            self.results_table.item(row, 2).text(),
                            self.results_table.item(row, 3).text(),
                            self.results_table.item(row, 4).text(),
                            self.results_table.item(row, 5).text(),
                            self.results_table.item(row, 6).text()
                        ])
            
            QMessageBox.information(self, "Успех", 
                                  f"Данные успешно экспортированы в {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта: {str(e)}")
    
    def export_to_json(self):
        """Export results to JSON file."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Экспорт в JSON", "", "JSON Files (*.json)"
        )
        
        if not filename:
            return
        
        try:
            data = {
                'export_date': datetime.now().isoformat(),
                'drugs': []
            }
            
            for row in range(self.results_table.rowCount()):
                name_item = self.results_table.item(row, 1)
                if name_item:
                    drug = {
                        'name': self.results_table.item(row, 1).text(),
                        'substance': self.results_table.item(row, 2).text(),
                        'form': self.results_table.item(row, 3).text(),
                        'manufacturer': self.results_table.item(row, 4).text(),
                        'contraindications': self.results_table.item(row, 5).text(),
                        'price': self.results_table.item(row, 6).text()
                    }
                    data['drugs'].append(drug)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "Успех", 
                                  f"Данные успешно экспортированы в {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта: {str(e)}")
    
    def add_drug(self):
        """Show add drug dialog."""
        dialog = AddDrugDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            
            # Validate (contraindications can be empty)
            if not data['name'] or not data['substance'] or not data['form'] or not data['manufacturer']:
                QMessageBox.warning(self, "Внимание", 
                                  "Заполните все обязательные поля")
                return
            
            try:
                drug_id = self.database.add_drug(
                    data['name'], data['substance'], data['form'],
                    data['manufacturer'], data['price'], data.get('contraindications', '')
                )
                QMessageBox.information(self, "Успех", "Препарат успешно добавлен")
                self.load_filter_options()
                self.load_all_drugs()  # Refresh the list
                self.statusBar().showMessage(f"Добавлен препарат ID: {drug_id}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка добавления: {str(e)}")
    
    def edit_drug(self):
        """Show edit drug dialog."""
        # Get currently selected drug from results or show list
        if self.results_table.rowCount() == 0:
            QMessageBox.warning(self, "Внимание", 
                              "Нет данных для редактирования. Выполните поиск.")
            return
        
        # Get first selected row or first row
        selected_row = -1
        for row in range(self.results_table.rowCount()):
            if self.results_table.item(row, 0).checkState() == Qt.Checked:
                selected_row = row
                break
        
        if selected_row == -1:
            selected_row = 0
        
        name_item = self.results_table.item(selected_row, 1)
        if not name_item:
            return
        
        drug_id = name_item.data(Qt.UserRole)
        drug = self.database.get_drug_by_id(drug_id)
        
        if not drug:
            QMessageBox.warning(self, "Внимание", "Препарат не найден")
            return
        
        dialog = AddDrugDialog(self, existing_drug=drug)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            
            # Validate (contraindications can be empty)
            if not data['name'] or not data['substance'] or not data['form'] or not data['manufacturer']:
                QMessageBox.warning(self, "Внимание", "Заполните все обязательные поля")
                return
            
            try:
                self.database.update_drug(
                    drug_id, data['name'], data['substance'], data['form'],
                    data['manufacturer'], data['price'], data.get('contraindications', '')
                )
                QMessageBox.information(self, "Успех", "Препарат успешно обновлен")
                self.load_filter_options()
                self.load_all_drugs()  # Refresh the list
                self.statusBar().showMessage("Препарат обновлен")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка обновления: {str(e)}")
    
    def delete_drug(self):
        """Delete selected drug."""
        if self.results_table.rowCount() == 0:
            QMessageBox.warning(self, "Внимание", 
                              "Нет данных для удаления. Выполните поиск.")
            return
        
        # Get first selected row or first row
        selected_row = -1
        for row in range(self.results_table.rowCount()):
            if self.results_table.item(row, 0).checkState() == Qt.Checked:
                selected_row = row
                break
        
        if selected_row == -1:
            selected_row = 0
        
        name_item = self.results_table.item(selected_row, 1)
        if not name_item:
            return
        
        drug_id = name_item.data(Qt.UserRole)
        drug_name = name_item.text()
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, "Подтверждение", 
            f"Удалить препарат '{drug_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.database.delete_drug(drug_id)
                QMessageBox.information(self, "Успех", "Препарат успешно удален")
                self.load_filter_options()
                self.load_all_drugs()  # Refresh the list after deletion
                self.statusBar().showMessage("Препарат удален")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка удаления: {str(e)}")
    
    def show_about(self):
        """Show about dialog."""
        about_text = """
        <h2>Поиск аналогов лекарственных препаратов</h2>
        <p>Версия 1.0</p>
        <p>Система для поиска аналогов лекарственных препаратов 
        на основе действующих веществ.</p>
        <p>Разработано с использованием Python 3.13 и PyQt5.</p>
        <hr>
        <p><b>Функции:</b></p>
        <ul>
            <li>Поиск аналогов по действующему веществу</li>
            <li>Фильтрация по форме выпуска, производителю и цене</li>
            <li>Сравнение препаратов</li>
            <li>Экспорт результатов в CSV и JSON</li>
            <li>Управление базой данных препаратов</li>
        </ul>
        """
        QMessageBox.about(self, "О программе", about_text)


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

