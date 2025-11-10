"""
User authentication module for the drug analog search application.
"""

from typing import Optional, Dict


class UserAuth:
    def __init__(self):
        # In production, use a secure database and proper password hashing
        self._users = {
            "admin": {"password": "admin123", "role": "admin"},
            "user": {"password": "user123", "role": "user"}
        }
        self.current_user: Optional[Dict] = None
    
    def login(self, username: str, password: str) -> bool:
        """
        Attempt to log in a user.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            True if login successful, False otherwise
        """
        if username in self._users and self._users[username]["password"] == password:
            self.current_user = {
                "username": username,
                "role": self._users[username]["role"]
            }
            return True
        return False
    
    def logout(self):
        """Log out the current user."""
        self.current_user = None
    
    def is_admin(self) -> bool:
        """Check if current user has admin role."""
        return self.current_user is not None and self.current_user["role"] == "admin"
    
    def is_authenticated(self) -> bool:
        """Check if a user is currently logged in."""
        return self.current_user is not None