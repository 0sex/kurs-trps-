"""
Main UI module for the drug analog search application.

This module defines the graphical user interface using PyQt5.
"""

import sys
from user_auth import UserAuth
from login_dialog import LoginDialog
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QFormLayout, QDoubleSpinBox, QComboBox,
    QMenuBar, QMenu, QAction, QFileDialog, QCheckBox, QGroupBox,
    QHeaderView, QStatusBar, QTextEdit, QSplitter
)
from PyQt5.QtCore import Qt, QAbstractTableModel, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor
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
        self.resize(500, 450)
        self.setup_ui()
        
        if existing_drug:
            self.load_drug_data()
    
    def setup_ui(self):
        """Create UI elements."""
        layout = QFormLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.name_edit = QLineEdit()
        self.name_edit.setMinimumHeight(35)
        self.substance_edit = QLineEdit()
        self.substance_edit.setPlaceholderText("Можно несколько через '+' или ','")
        self.substance_edit.setMinimumHeight(35)
        self.form_edit = QLineEdit()
        self.form_edit.setMinimumHeight(35)
        self.manufacturer_edit = QLineEdit()
        self.manufacturer_edit.setMinimumHeight(35)
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setRange(0.0, 99999.0)
        self.price_spin.setDecimals(2)
        self.price_spin.setSingleStep(1.0)
        self.price_spin.setSuffix(" руб.")
        self.price_spin.setMinimumHeight(35)
        self.contraindications_edit = QLineEdit()
        self.contraindications_edit.setPlaceholderText("Можно несколько через ',' или ';'")
        self.contraindications_edit.setMinimumHeight(35)
        
        # Description field - use QTextEdit for multi-line text
        from PyQt5.QtWidgets import QTextEdit
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Опишите действие препарата и для чего его применяют...")
        self.description_edit.setMinimumHeight(80)
        self.description_edit.setMaximumHeight(120)
        
        layout.addRow("Название:", self.name_edit)
        layout.addRow("Действующее вещество:", self.substance_edit)
        layout.addRow("Форма выпуска:", self.form_edit)
        layout.addRow("Производитель:", self.manufacturer_edit)
        layout.addRow("Цена:", self.price_spin)
        layout.addRow("Противопоказания:", self.contraindications_edit)
        layout.addRow("Описание действия:", self.description_edit)
        
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        save_btn = QPushButton("💾 Сохранить")
        cancel_btn = QPushButton("❌ Отмена")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        buttons.addStretch()
        
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
            self.description_edit.setPlainText(self.existing_drug.get('description', '') or '')
    
    def get_data(self) -> Dict:
        """Get form data as dictionary."""
        return {
            'name': self.name_edit.text().strip(),
            'substance': self.substance_edit.text().strip(),
            'form': self.form_edit.text().strip(),
            'manufacturer': self.manufacturer_edit.text().strip(),
            'price': self.price_spin.value(),
            'contraindications': self.contraindications_edit.text().strip(),
            'description': self.description_edit.toPlainText().strip()
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
        self.table.setRowCount(8)
        self.table.setHorizontalHeaderLabels([drug['name'] for drug in self.drugs])
        self.table.setVerticalHeaderLabels([
            "Действующее вещество",
            "Форма выпуска",
            "Производитель",
            "Цена",
            "Противопоказания",
            "Описание",
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
            self.table.setItem(5, col, QTableWidgetItem(str(drug.get('description', '') or '')))
            
            # Calculate price per unit (simplified)
            price_per_unit = f"{drug['price']:.2f}"
            self.table.setItem(6, col, QTableWidgetItem(price_per_unit))
            
            # Calculate difference from first drug
            if col > 0:
                diff = drug['price'] - self.drugs[0]['price']
                diff_text = f"{'+' if diff > 0 else ''}{diff:.2f} руб."
                self.table.setItem(7, col, QTableWidgetItem(diff_text))
            else:
                self.table.setItem(7, col, QTableWidgetItem("—"))
        
        # Make table read-only
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Auto-size columns
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # Enable alternating row colors
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
        
        close_btn = QPushButton("❌ Закрыть")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                padding: 10px 30px;
                border-radius: 6px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        self.init_database()
        self.auth = UserAuth()
        self.setup_ui()
        self.load_filter_options()
        self.load_all_drugs()
        
        # Initially set as regular user
        self.auth.current_user = {"username": "user", "role": "user"}
        self.update_ui_for_role()
        
    def show_login(self) -> bool:
        """Show login dialog and handle authentication."""
        dialog = LoginDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            username, password = dialog.get_credentials()
            if self.auth.login(username, password):
                self.update_ui_for_role()
                return True
            else:
                QMessageBox.warning(self, "Ошибка", "Неверное имя пользователя или пароль")
                return self.show_login()
        return False
        
    def toggle_admin_login(self):
        """Handle admin login/logout."""
        if not self.auth.is_admin():
            # Try to log in as admin
            dialog = LoginDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                username, password = dialog.get_credentials()
                if self.auth.login(username, password):
                    if self.auth.is_admin():
                        self.update_ui_for_role()
                    else:
                        QMessageBox.warning(self, "Ошибка", "Требуются права администратора")
                        self.auth.current_user = {"username": "user", "role": "user"}
                        self.update_ui_for_role()
                else:
                    QMessageBox.warning(self, "Ошибка", "Неверное имя пользователя или пароль")
        else:
            # Log out admin
            self.auth.current_user = {"username": "user", "role": "user"}
            self.update_ui_for_role()
    
    def update_ui_for_role(self):
        """Update UI elements based on user role."""
        is_admin = self.auth.is_admin()
        role_text = "администратор" if is_admin else "пользователь"
        
        # Update menu items
        menubar = self.menuBar()
        file_menu = menubar.findChild(QMenu, "Файл")
        if file_menu:
            for action in file_menu.actions():
                if action.text() in ["Добавить препарат", "Редактировать препарат", "Удалить препарат"]:
                    action.setEnabled(is_admin)
        
        # Update login/logout action text
        self.login_action.setText("Выход из админ. режима" if is_admin else "Вход для администратора")
        
        self.statusBar().showMessage(f"Режим работы: {role_text}")
    
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
        self.setMinimumSize(1200, 700)
        
        # Apply modern dark theme styling to the window
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #252525;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: #4a9eff;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 120px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
                border: 1px solid #4a9eff;
                color: #4a9eff;
            }
            QPushButton:pressed {
                background-color: #1d1d1d;
                border: 1px solid #5aafff;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
                border: 1px solid #333333;
            }
            QLineEdit, QComboBox, QDoubleSpinBox {
                padding: 8px;
                border: 2px solid #3d3d3d;
                border-radius: 5px;
                background-color: #2d2d2d;
                color: #e0e0e0;
                font-size: 10pt;
                selection-background-color: #4a9eff;
                selection-color: #ffffff;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
                border: 2px solid #4a9eff;
                background-color: #333333;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #3d3d3d;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #e0e0e0;
                width: 0;
                height: 0;
            }
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                selection-background-color: #4a9eff;
                selection-color: #ffffff;
                color: #e0e0e0;
            }
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
                background-color: #3d3d3d;
                border: none;
                width: 20px;
                border-radius: 3px;
            }
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
                background-color: #4a9eff;
            }
            QDoubleSpinBox::up-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 4px solid #e0e0e0;
                width: 0;
                height: 0;
            }
            QDoubleSpinBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #e0e0e0;
                width: 0;
                height: 0;
            }
            QTableWidget {
                gridline-color: #3d3d3d;
                background-color: #252525;
                alternate-background-color: #2a2a2a;
                selection-background-color: #4a9eff;
                selection-color: #ffffff;
                border: 2px solid #3d3d3d;
                border-radius: 8px;
                color: #e0e0e0;
            }
            QTableWidget::item {
                padding: 8px;
                border: none;
            }
            QTableWidget::item:hover {
                background-color: #333333;
            }
            QTableWidget::item:selected {
                background-color: #4a9eff;
                color: #ffffff;
            }
            QTableWidget::item:selected:hover {
                background-color: #5aafff;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #e0e0e0;
                padding: 10px;
                border: none;
                border-right: 1px solid #3d3d3d;
                border-bottom: 2px solid #4a9eff;
                font-weight: bold;
                font-size: 10pt;
            }
            QHeaderView::section:hover {
                background-color: #3d3d3d;
                color: #4a9eff;
            }
            QHeaderView::section:first {
                border-left: none;
            }
            QHeaderView::section:last {
                border-right: none;
            }
            QStatusBar {
                background-color: #252525;
                color: #e0e0e0;
                border-top: 1px solid #3d3d3d;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 10pt;
            }
            QMenuBar {
                background-color: #252525;
                color: #e0e0e0;
                border-bottom: 1px solid #3d3d3d;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 8px 12px;
            }
            QMenuBar::item:selected {
                background-color: #3d3d3d;
                color: #4a9eff;
            }
            QMenu {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
            }
            QMenu::item:selected {
                background-color: #4a9eff;
                color: #ffffff;
            }
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #4d4d4d;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5d5d5d;
            }
            QScrollBar:horizontal {
                background-color: #2d2d2d;
                height: 12px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background-color: #4d4d4d;
                min-width: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #5d5d5d;
            }
            QCheckBox {
                color: #e0e0e0;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #3d3d3d;
                border-radius: 3px;
                background-color: #2d2d2d;
            }
            QCheckBox::indicator:hover {
                border: 2px solid #4a9eff;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
                border: 2px solid #4a9eff;
            }
            QTextEdit {
                padding: 8px;
                border: 2px solid #3d3d3d;
                border-radius: 5px;
                background-color: #2d2d2d;
                color: #e0e0e0;
                font-size: 10pt;
                selection-background-color: #4a9eff;
                selection-color: #ffffff;
            }
            QTextEdit:focus {
                border: 2px solid #4a9eff;
                background-color: #333333;
            }
        """)
        
        # Create central widget with modern styling and gradient background
        central_widget = QWidget()
        central_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e1e1e, stop:1 #252525);
            }
        """)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # Search section
        search_group = QGroupBox("🔍 Поиск аналогов")
        search_layout = QVBoxLayout()
        
        search_input_layout = QHBoxLayout()
        search_label = QLabel("Название препарата:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите название препарата...")
        search_btn = QPushButton("🔍 Найти аналоги")
        search_btn.clicked.connect(self.search_analogs)
        self.search_input.returnPressed.connect(search_btn.click)
        search_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4a9eff, stop:1 #357abd);
                color: white;
                font-weight: bold;
                border: none;
                padding: 10px 24px;
                border-radius: 6px;
                font-size: 11pt;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5aafff, stop:1 #458acd);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3a8eef, stop:1 #256aad);
            }
        """)
        
        search_input_layout.addWidget(search_label)
        search_input_layout.addWidget(self.search_input)
        search_input_layout.addWidget(search_btn)
        search_layout.addLayout(search_input_layout)
        
        search_group.setLayout(search_layout)
        main_layout.addWidget(search_group)
        
        # Filters section (separate from search)
        filters_group = QGroupBox("🔽 Фильтры препаратов")
        filters_layout = QVBoxLayout()
        
        filters_row1 = QHBoxLayout()
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
        
        filters_row1.addWidget(filter_label)
        filters_row1.addWidget(self.form_filter)
        filters_row1.addWidget(self.manufacturer_filter)
        filters_row1.addWidget(self.min_price_filter)
        filters_row1.addWidget(self.max_price_filter)
        filters_layout.addLayout(filters_row1)
        
        filters_row2 = QHBoxLayout()
        self.contraindication_filter = QComboBox()
        self.contraindication_filter.setEditable(True)
        self.contraindication_filter.setCurrentText("")
        self.contraindication_filter.setPlaceholderText("Исключить противопоказание")
        
        apply_filters_btn = QPushButton("✅ Применить фильтры")
        apply_filters_btn.clicked.connect(self.apply_filters)
        apply_filters_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                border: 2px solid #28a745;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #218838;
                border: 2px solid #218838;
                transform: scale(1.05);
            }
            QPushButton:pressed {
                background-color: #1e7e34;
                border: 2px solid #1e7e34;
            }
        """)
        
        clear_filters_btn = QPushButton("🗑️ Очистить")
        clear_filters_btn.clicked.connect(self.clear_filters)
        clear_filters_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                border: 2px solid #dc3545;
                padding: 10px 20px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #c82333;
                border: 2px solid #c82333;
            }
            QPushButton:pressed {
                background-color: #bd2130;
                border: 2px solid #bd2130;
            }
        """)
        
        filters_row2.addWidget(QLabel("Исключить противопоказание:"))
        filters_row2.addWidget(self.contraindication_filter)
        filters_row2.addStretch()
        filters_row2.addWidget(apply_filters_btn)
        filters_row2.addWidget(clear_filters_btn)
        filters_layout.addLayout(filters_row2)
        
        filters_group.setLayout(filters_layout)
        main_layout.addWidget(filters_group)
        
        # Results section
        results_group = QGroupBox("📊 Препараты")
        results_layout = QVBoxLayout()
        
        # Action buttons with modern styling
        action_buttons_layout = QHBoxLayout()
        action_buttons_layout.setSpacing(10)
        
        self.compare_btn = QPushButton("⚖️ Сравнить выбранные")
        self.compare_btn.clicked.connect(self.compare_selected)
        self.compare_btn.setEnabled(False)
        self.compare_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #6f42c1, stop:1 #5a32a3);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #7f52d1, stop:1 #6a42b3);
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
                border: 1px solid #333333;
            }
        """)
        
        self.export_csv_btn = QPushButton("📄 Экспорт в CSV")
        self.export_csv_btn.clicked.connect(self.export_to_csv)
        self.export_csv_btn.setEnabled(False)
        self.export_csv_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #17a2b8, stop:1 #138496);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #27b2c8, stop:1 #2384a6);
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
                border: 1px solid #333333;
            }
        """)
        
        self.export_json_btn = QPushButton("📋 Экспорт в JSON")
        self.export_json_btn.clicked.connect(self.export_to_json)
        self.export_json_btn.setEnabled(False)
        self.export_json_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffc107, stop:1 #e0a800);
                color: #1e1e1e;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ffd107, stop:1 #f0b800);
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666666;
                border: 1px solid #333333;
            }
        """)
        
        action_buttons_layout.addWidget(self.compare_btn)
        action_buttons_layout.addWidget(self.export_csv_btn)
        action_buttons_layout.addWidget(self.export_json_btn)
        action_buttons_layout.addStretch()
        
        results_layout.addLayout(action_buttons_layout)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels([
            "Выбор",
            "Название",
            "Действующее вещество",
            "Форма",
            "Производитель",
            "Противопоказания",
            "Описание",
            "Цена"
        ])
        # Enable sorting on all columns
        self.results_table.setSortingEnabled(True)
        # Make columns resizable (Interactive mode)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        
        # Set word wrap for description column
        self.results_table.setWordWrap(True)
        # Set default column widths
        self.results_table.setColumnWidth(0, 60)  # Выбор
        self.results_table.setColumnWidth(1, 180)  # Название
        self.results_table.setColumnWidth(2, 200)  # Действующее вещество
        self.results_table.setColumnWidth(3, 150)  # Форма
        self.results_table.setColumnWidth(4, 180)  # Производитель
        self.results_table.setColumnWidth(5, 200)  # Противопоказания
        self.results_table.setColumnWidth(6, 350)  # Описание (увеличена ширина)
        self.results_table.setColumnWidth(7, 100)  # Цена
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        # Enable alternating row colors for better readability
        self.results_table.setAlternatingRowColors(True)
        
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
        
        # Add login/logout action
        self.login_action = QAction("Вход для администратора", self)
        self.login_action.triggered.connect(self.toggle_admin_login)
        file_menu.addAction(self.login_action)
        
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
    
    def get_filter_values(self):
        """Get current filter values from UI."""
        form = self.form_filter.currentText().strip() if self.form_filter.currentText().strip() else None
        manufacturer = self.manufacturer_filter.currentText().strip() if self.manufacturer_filter.currentText().strip() else None
        min_price = self.min_price_filter.value() if self.min_price_filter.value() > 0 else None
        max_price = self.max_price_filter.value() if self.max_price_filter.value() < 99999 else None
        exclude_contraindication = self.contraindication_filter.currentText().strip() if self.contraindication_filter.currentText().strip() else None
        return form, manufacturer, min_price, max_price, exclude_contraindication
    
    def apply_filters(self):
        """Apply filters to all drugs and display results."""
        try:
            form, manufacturer, min_price, max_price, exclude_contraindication = self.get_filter_values()
            
            # Get filtered drugs from database
            filtered_drugs = self.database.get_drugs_by_filters(
                form, manufacturer, min_price, max_price, exclude_contraindication
            )
            
            if filtered_drugs:
                # Convert to format expected by display_results: (drug, similarity)
                formatted_results = [(drug, 1.0) for drug in filtered_drugs]
                self.display_results(formatted_results)
                self.statusBar().showMessage(f"Отображено препаратов: {len(filtered_drugs)}")
            else:
                self.results_table.setRowCount(0)
                self.statusBar().showMessage("Препараты не найдены по заданным фильтрам")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка применения фильтров: {str(e)}")
            self.statusBar().showMessage("Ошибка применения фильтров")
    
    def load_all_drugs(self):
        """Load all drugs from database and apply filters."""
        self.apply_filters()
        
        # After loading drugs, adjust the description column width
        self.results_table.setColumnWidth(6, 350)  # Make description column wider
        self.results_table.resizeRowsToContents()  # Adjust row heights automatically
    
    def search_analogs(self):
        """Perform analog search based on input and filters."""
        query = self.search_input.text().strip()
        
        if not query:
            QMessageBox.warning(self, "Внимание", "Введите название препарата для поиска")
            return
        
        try:
            # Get filter values using helper method
            form, manufacturer, min_price, max_price, exclude_contraindication = self.get_filter_values()
            
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
        # Temporarily disable sorting while populating to avoid issues
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(len(results))
        
        for row, (drug, similarity) in enumerate(results):
            # Checkbox
            checkbox = QTableWidgetItem()
            checkbox.setCheckState(Qt.Unchecked)
            # Make checkbox non-sortable
            checkbox.setFlags(checkbox.flags() & ~Qt.ItemIsEditable)
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
            
            # Description
            description = drug.get('description', '')
            description_item = QTableWidgetItem(description if description else '')
            description_item.setTextAlignment(Qt.AlignLeft | Qt.AlignTop)
            self.results_table.setItem(row, 6, description_item)
            
            # Calculate row height based on description text
            metrics = self.results_table.fontMetrics()
            description_width = self.results_table.columnWidth(6) - 20  # Account for padding
            text_height = metrics.boundingRect(
                0, 0, description_width, 1000,
                Qt.TextWordWrap | Qt.AlignLeft | Qt.AlignTop,
                description if description else ''
            ).height()
            self.results_table.setRowHeight(row, max(40, text_height + 20))
            
            # Price - store numeric value for proper sorting
            price_item = QTableWidgetItem()
            price_item.setData(Qt.DisplayRole, f"{drug['price']:.2f} руб.")
            price_item.setData(Qt.UserRole, drug['price'])
            # Set numeric value for sorting
            price_item.setData(Qt.EditRole, drug['price'])
            self.results_table.setItem(row, 7, price_item)
        
        # Adjust row heights for descriptions after all items are set
        # This ensures column widths are already set
        for row in range(len(results)):
            description_item = self.results_table.item(row, 6)
            if description_item:
                description = description_item.text()
                if description:
                    # Use column width (default 350) for calculation
                    col_width = self.results_table.columnWidth(6) or 350
                    # Approximate: ~10 pixels per character, but account for word wrapping
                    chars_per_line = max(35, col_width // 10)
                    estimated_lines = max(1, (len(description) + chars_per_line - 1) // chars_per_line)
                    # Set row height: minimum 30, maximum 120, ~25 pixels per line
                    row_height = max(30, min(120, estimated_lines * 25 + 10))
                    self.results_table.setRowHeight(row, row_height)
        
        # Re-enable sorting after populating
        self.results_table.setSortingEnabled(True)
        
        # Enable buttons
        self.compare_btn.setEnabled(len(results) > 0)
        self.export_csv_btn.setEnabled(len(results) > 0)
        self.export_json_btn.setEnabled(len(results) > 0)
    
    def clear_filters(self):
        """Clear all filters and reload all drugs."""
        self.form_filter.setCurrentText("")
        self.manufacturer_filter.setCurrentText("")
        self.min_price_filter.setValue(0.0)
        self.max_price_filter.setValue(99999.0)
        self.contraindication_filter.setCurrentText("")
        # Apply filters after clearing (will show all drugs)
        self.apply_filters()
    
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
                    "Производитель", "Противопоказания", "Описание", "Цена"
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
                            self.results_table.item(row, 6).text(),
                            self.results_table.item(row, 7).text()
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
                    drug_id = name_item.data(Qt.UserRole)
                    drug = self.database.get_drug_by_id(drug_id)
                    if drug:
                        data['drugs'].append({
                            'name': drug['name'],
                            'substance': drug['substance'],
                            'form': drug['form'],
                            'manufacturer': drug['manufacturer'],
                            'price': drug['price'],
                            'contraindications': drug.get('contraindications', '') or '',
                            'description': drug.get('description', '') or ''
                        })
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "Успех", 
                                  f"Данные успешно экспортированы в {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта: {str(e)}")
    
    def add_drug(self):
        """Show add drug dialog."""
        if not self.auth.is_admin():
            QMessageBox.warning(self, "Ошибка", "Только администратор может добавлять препараты")
            return
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
                    data['manufacturer'], data['price'], data.get('contraindications', ''),
                    data.get('description', '')
                )
                QMessageBox.information(self, "Успех", "Препарат успешно добавлен")
                self.load_filter_options()
                self.load_all_drugs()  # Refresh the list
                self.statusBar().showMessage(f"Добавлен препарат ID: {drug_id}")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка добавления: {str(e)}")
    
    def edit_drug(self):
        """Show edit drug dialog."""
        if not self.auth.is_admin():
            QMessageBox.warning(self, "Ошибка", "Только администратор может редактировать препараты")
            return
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
                    data['manufacturer'], data['price'], data.get('contraindications', ''),
                    data.get('description', '')
                )
                QMessageBox.information(self, "Успех", "Препарат успешно обновлен")
                self.load_filter_options()
                self.load_all_drugs()  # Refresh the list
                self.statusBar().showMessage("Препарат обновлен")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Ошибка обновления: {str(e)}")
    
    def delete_drug(self):
        """Delete selected drug."""
        if not self.auth.is_admin():
            QMessageBox.warning(self, "Ошибка", "Только администратор может удалять препараты")
            return
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
        <div style="color: #e0e0e0;">
        <h2 style="color: #4a9eff;">💊 Поиск аналогов лекарственных препаратов</h2>
        <p><b>Версия 1.0</b></p>
        <p>Система для поиска аналогов лекарственных препаратов 
        на основе действующих веществ.</p>
        <p>Разработано с использованием Python 3.13 и PyQt5.</p>
        <hr style="color: #3d3d3d;">
        <p><b style="color: #4a9eff;">✨ Функции:</b></p>
        <ul>
            <li>🔍 Поиск аналогов по действующему веществу</li>
            <li>🔽 Фильтрация по форме выпуска, производителю и цене</li>
            <li>⚖️ Сравнение препаратов</li>
            <li>📄 Экспорт результатов в CSV и JSON</li>
            <li>📊 Управление базой данных препаратов</li>
            <li>🌙 Темная тема интерфейса</li>
            <li>📈 Сортировка и настройка колонок</li>
        </ul>
        </div>
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("О программе")
        msg.setText(about_text)
        msg.setIcon(QMessageBox.Information)
        msg.exec_()


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Apply modern dark color palette
    palette = QPalette()
    # Window colors
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, QColor(224, 224, 224))
    # Base colors
    palette.setColor(QPalette.Base, QColor(45, 45, 45))
    palette.setColor(QPalette.AlternateBase, QColor(42, 42, 42))
    # Text colors
    palette.setColor(QPalette.Text, QColor(224, 224, 224))
    palette.setColor(QPalette.BrightText, QColor(255, 255, 255))
    # Button colors
    palette.setColor(QPalette.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ButtonText, QColor(224, 224, 224))
    # Tooltip colors
    palette.setColor(QPalette.ToolTipBase, QColor(45, 45, 45))
    palette.setColor(QPalette.ToolTipText, QColor(224, 224, 224))
    # Link and highlight colors
    palette.setColor(QPalette.Link, QColor(74, 158, 255))
    palette.setColor(QPalette.Highlight, QColor(74, 158, 255))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    # Disabled colors
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(102, 102, 102))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(102, 102, 102))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(102, 102, 102))
    app.setPalette(palette)
    
    # Set modern application font
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

