import os
from typing import Dict, Optional
from PyQt6.QtCore import QObject
from PyQt6.QtWebEngineCore import QWebEngineProfile

class SessionManager(QObject):
    def __init__(self, base_storage_dir: Optional[str] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        if base_storage_dir: self.base_dir = os.path.expanduser(base_storage_dir)
        else: self.base_dir = os.path.join(os.path.expanduser("~"), ".nexus_orchestrator", "profiles")
        os.makedirs(self.base_dir, exist_ok=True)
        self._profiles: Dict[str, QWebEngineProfile] = {}

    def get_or_create_profile(self, profile_id: str) -> QWebEngineProfile:
        safe_id = profile_id.replace(" ", "_").strip()
        if safe_id in self._profiles: return self._profiles[safe_id]

        storage_path = os.path.join(self.base_dir, safe_id, "storage")
        cache_path = os.path.join(self.base_dir, safe_id, "cache")
        download_dir = os.path.join(self.base_dir, safe_id, "downloads")

        os.makedirs(storage_path, exist_ok=True)
        os.makedirs(cache_path, exist_ok=True)
        os.makedirs(download_dir, exist_ok=True)

        profile = QWebEngineProfile(safe_id, self)
        profile.setPersistentStoragePath(storage_path)
        profile.setCachePath(cache_path)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        
        def _on_download_requested(download):
            download.setDownloadDirectory(download_dir)
            download.accept()
            print(f"[SESSION] 📥 Auto-downloaded {download.downloadFileName()} -> {download_dir}")

        profile.downloadRequested.connect(_on_download_requested)
        self._profiles[safe_id] = profile
        return profile
        
    def get_profile_path(self, profile_id: str) -> str:
        safe_id = profile_id.replace(" ", "_").strip()
        return os.path.join(self.base_dir, safe_id)