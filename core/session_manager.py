import os
import json
from PyQt6.QtWebEngineCore import QWebEngineProfile

class SessionManager:
    """Manages browser profiles, cookies, and account configurations."""
    
    def __init__(self, storage_root: str):
        self.storage_root = os.path.expanduser(storage_root)
        os.makedirs(self.storage_root, exist_ok=True)
        self.accounts_file = os.path.join(self.storage_root, "accounts.json")
        self.profiles = {}

    def load_accounts(self) -> list:
        """Loads account configurations from disk, or generates default swarm nodes."""
        if os.path.exists(self.accounts_file):
            try:
                with open(self.accounts_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading accounts.json: {e}")
        
        # Default fallback swarm topology if no accounts file exists yet
        default_accounts = [
            {
                "id": "master_1", 
                "account_name": "Master Architect Node", 
                "platform": "claude", 
                "last_url": ""
            },
            {
                "id": "worker_1", 
                "account_name": "Subordinate Worker A", 
                "platform": "claude", 
                "last_url": ""
            },
            {
                "id": "worker_2", 
                "account_name": "Subordinate Worker B", 
                "platform": "claude", 
                "last_url": ""
            }
        ]
        self._save_accounts(default_accounts)
        return default_accounts

    def _save_accounts(self, accounts: list):
        with open(self.accounts_file, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=4)

    def get_or_create_profile(self, account_id: str, parent=None) -> QWebEngineProfile:
        """Retrieves or creates an isolated, persistent browser profile for a node."""
        if account_id in self.profiles:
            return self.profiles[account_id]
        
        profile_dir = os.path.join(self.storage_root, f"profile_{account_id}")
        os.makedirs(profile_dir, exist_ok=True)
        
        profile = QWebEngineProfile(account_id, parent)
        profile.setPersistentStoragePath(profile_dir)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        profile.setCachePath(os.path.join(profile_dir, "cache"))
        
        self.profiles[account_id] = profile
        return profile

    def update_last_url(self, account_id: str, url: str):
        """Saves the last visited URL so the node restores its state on next boot."""
        accounts = self.load_accounts()
        updated = False
        for acc in accounts:
            if acc["id"] == account_id:
                if acc.get("last_url") != url:
                    acc["last_url"] = url
                    updated = True
                break
        
        if updated:
            self._save_accounts(accounts)