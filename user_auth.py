from typing import Optional, Dict


class UserAuth:
    def __init__(self):
        self._users = {
            "admin": {"password": "admin123", "role": "admin"},
            "user": {"password": "user123", "role": "user"}
        }
        self.current_user: Optional[Dict] = None

    def login(self, username: str, password: str) -> bool:
        if username in self._users and self._users[username]["password"] == password:
            self.current_user = {"username": username, "role": self._users[username]["role"]}
            return True
        return False

    def logout(self):
        self.current_user = None

    def is_admin(self) -> bool:
        return self.current_user is not None and self.current_user["role"] == "admin"

    def is_authenticated(self) -> bool:
        return self.current_user is not None