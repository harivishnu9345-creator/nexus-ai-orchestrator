"""
Session Manager Module
Manages isolated QWebEngineProfile instances and cookie persistence paths.
Ensures Google accounts stay logged in across application restarts.
"""

import os
from typing import Dict, Optional
from PyQt6.QtCore import QObject
from PyQt6.QtWebEngineCore import QWebEngineProfile

class SessionManager(QObject):
    # Standard desktop User-Agent to prevent Google OAuth 'disallowed_useragent' blocks
    DESKTOP_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def __init__(self, base_storage_dir: Optional[str] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        if base_storage_dir:
            self.base_dir = os.path.expanduser(base_storage_dir)
        else:
            self.base_dir = os.path.join(os.path.expanduser("~"), ".nexus_orchestrator", "profiles")

        os.makedirs(self.base_dir, exist_ok=True)
        self._profiles: Dict[str, QWebEngineProfile] = {}

    def get_or_create_profile(self, profile_id: str) -> QWebEngineProfile:
        """
        Retrieves an existing QWebEngineProfile or creates a new isolated persistent profile.
        """
        if profile_id in self._profiles:
            return self._profiles[profile_id]

        storage_path = os.path.join(self.base_dir, profile_id, "storage")
        cache_path = os.path.join(self.base_dir, profile_id, "cache")

        os.makedirs(storage_path, exist_ok=True)
        os.makedirs(cache_path, exist_ok=True)

        # Create persistent named profile attached to disk
        profile = QWebEngineProfile(profile_id, self)
        profile.setPersistentStoragePath(storage_path)
        profile.setCachePath(cache_path)

        # Force cookies and web cache to write to disk to maintain sessions
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        
        # Spoof Desktop User Agent for Google Login compatibility
        profile.setHttpUserAgent(self.DESKTOP_USER_AGENT)

        self._profiles[profile_id] = profile
        return profile
        
    def get_profile_path(self, profile_id: str) -> str:
        """Returns the physical directory on disk where the profile data lives."""
        return os.path.join(self.base_dir, profile_id)
