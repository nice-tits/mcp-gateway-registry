"""
Local user management utilities for MCP Gateway Registry.
Replaces Amazon Cognito with a simple file-based user system.
"""

import logging
import yaml
import bcrypt
import secrets
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class LocalUserManager:
    """Manages local users for MCP Gateway Registry authentication."""
    
    def __init__(self, users_file: str = None):
        """Initialize with users file path."""
        if users_file is None:
            users_file = Path(__file__).parent / "users.yml"
        self.users_file = Path(users_file)
        self._users_cache = None
        self._last_modified = None
        
    def _load_users(self) -> Dict[str, Any]:
        """Load users from YAML file with caching."""
        try:
            if not self.users_file.exists():
                logger.warning(f"Users file not found at {self.users_file}")
                return {"users": {}}
            
            # Check if file was modified since last load
            current_modified = self.users_file.stat().st_mtime
            if self._users_cache is None or current_modified != self._last_modified:
                with open(self.users_file, 'r') as f:
                    self._users_cache = yaml.safe_load(f) or {"users": {}}
                self._last_modified = current_modified
                logger.debug(f"Loaded {len(self._users_cache.get('users', {}))} users from {self.users_file}")
            
            return self._users_cache
        except Exception as e:
            logger.error(f"Failed to load users file {self.users_file}: {e}")
            return {"users": {}}
    
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user with username and password.
        
        Args:
            username: The username
            password: The plain text password
            
        Returns:
            User info dict if authentication successful, None otherwise
        """
        users_data = self._load_users()
        users = users_data.get("users", {})
        
        user = users.get(username)
        if not user:
            logger.warning(f"User not found: {username}")
            return None
        
        if not user.get("enabled", True):
            logger.warning(f"User account disabled: {username}")
            return None
        
        password_hash = user.get("password_hash")
        if not password_hash:
            logger.warning(f"No password hash found for user: {username}")
            return None
        
        try:
            # Verify password using bcrypt
            if bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                logger.info(f"Successfully authenticated user: {username}")
                return {
                    "username": username,
                    "groups": user.get("groups", []),
                    "is_service_account": user.get("is_service_account", False),
                    "description": user.get("description", ""),
                    "enabled": user.get("enabled", True)
                }
            else:
                logger.warning(f"Invalid password for user: {username}")
                return None
        except Exception as e:
            logger.error(f"Password verification failed for user {username}: {e}")
            return None
    
    def authenticate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate using API key (for M2M authentication).
        
        Args:
            api_key: The API key
            
        Returns:
            User info dict if authentication successful, None otherwise
        """
        users_data = self._load_users()
        users = users_data.get("users", {})
        
        # Search for user with matching API key
        for username, user in users.items():
            if user.get("api_key") == api_key and user.get("enabled", True):
                logger.info(f"Successfully authenticated API key for user: {username}")
                return {
                    "username": username,
                    "groups": user.get("groups", []),
                    "is_service_account": user.get("is_service_account", False),
                    "description": user.get("description", ""),
                    "enabled": user.get("enabled", True)
                }
        
        logger.warning("Invalid API key provided")
        return None
    
    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user information by username."""
        users_data = self._load_users()
        users = users_data.get("users", {})
        
        user = users.get(username)
        if user and user.get("enabled", True):
            return {
                "username": username,
                "groups": user.get("groups", []),
                "is_service_account": user.get("is_service_account", False),
                "description": user.get("description", ""),
                "enabled": user.get("enabled", True)
            }
        return None
    
    def create_user(self, username: str, password: str, groups: List[str] = None, 
                   is_service_account: bool = False, description: str = "") -> bool:
        """
        Create a new user.
        
        Args:
            username: The username
            password: Plain text password
            groups: List of groups the user belongs to
            is_service_account: Whether this is a service account
            description: Description of the user
            
        Returns:
            True if user was created successfully, False otherwise
        """
        try:
            users_data = self._load_users()
            users = users_data.get("users", {})
            
            if username in users:
                logger.warning(f"User already exists: {username}")
                return False
            
            # Generate password hash
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Generate API key for service accounts
            api_key = None
            if is_service_account:
                api_key = f"mcp-api-{secrets.token_hex(16)}"
            
            users[username] = {
                "password_hash": password_hash,
                "groups": groups or [],
                "enabled": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "description": description,
                "is_service_account": is_service_account
            }
            
            if api_key:
                users[username]["api_key"] = api_key
            
            # Save users back to file
            users_data["users"] = users
            with open(self.users_file, 'w') as f:
                yaml.dump(users_data, f, default_flow_style=False, indent=2)
            
            # Clear cache to force reload
            self._users_cache = None
            
            logger.info(f"Created user: {username} (service_account: {is_service_account})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create user {username}: {e}")
            return False
    
    def update_user_password(self, username: str, new_password: str) -> bool:
        """Update a user's password."""
        try:
            users_data = self._load_users()
            users = users_data.get("users", {})
            
            if username not in users:
                logger.warning(f"User not found: {username}")
                return False
            
            # Generate new password hash
            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            users[username]["password_hash"] = password_hash
            
            # Save users back to file
            users_data["users"] = users
            with open(self.users_file, 'w') as f:
                yaml.dump(users_data, f, default_flow_style=False, indent=2)
            
            # Clear cache to force reload
            self._users_cache = None
            
            logger.info(f"Updated password for user: {username}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update password for user {username}: {e}")
            return False
    
    def list_users(self) -> Dict[str, Dict[str, Any]]:
        """List all users (without password hashes)."""
        users_data = self._load_users()
        users = users_data.get("users", {})
        
        result = {}
        for username, user in users.items():
            result[username] = {
                "groups": user.get("groups", []),
                "is_service_account": user.get("is_service_account", False),
                "description": user.get("description", ""),
                "enabled": user.get("enabled", True),
                "created_at": user.get("created_at", "")
            }
        return result

# Global instance
user_manager = LocalUserManager()

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Convenience function to authenticate a user."""
    return user_manager.authenticate_user(username, password)

def authenticate_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    """Convenience function to authenticate using API key."""
    return user_manager.authenticate_api_key(api_key)

def get_user(username: str) -> Optional[Dict[str, Any]]:
    """Convenience function to get user information."""
    return user_manager.get_user(username)

def generate_password_hash(password: str) -> str:
    """Generate a bcrypt password hash."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')