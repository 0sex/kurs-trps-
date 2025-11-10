"""
Login dialog for the drug analog search application.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QLineEdit, QMessageBox
)


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Вход в систему")
        self.setModal(True)
        self.resize(300, 150)
        self.setup_ui()
        
    def setup_ui(self):
        """Create UI elements."""
        layout = QFormLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Введите имя пользователя")
        self.username_edit.setMinimumHeight(30)
        
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Введите пароль")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setMinimumHeight(30)
        
        layout.addRow("Имя пользователя:", self.username_edit)
        layout.addRow("Пароль:", self.password_edit)
        
        buttons = QHBoxLayout()
        login_btn = QPushButton("Войти")
        cancel_btn = QPushButton("Отмена")
        
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
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
                padding: 8px 16px;
                border-radius: 4px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        
        login_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(login_btn)
        buttons.addWidget(cancel_btn)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def get_credentials(self) -> tuple[str, str]:
        """Get entered username and password."""
        return self.username_edit.text(), self.password_edit.text()