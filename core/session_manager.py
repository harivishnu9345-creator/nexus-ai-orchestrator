import os
import json
from typing import List, Dict
from PyQt6.QtCore import QUrl, QDateTime, QByteArray
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineScript
from PyQt6.QtNetwork import QNetworkCookie


NO_PASSKEY_STEALTH_JS = """
(function() {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    if (navigator.credentials && navigator.credentials.get) {
        navigator.credentials.get = function() {
            return Promise.reject(new DOMException("NotAllowedError", "NotAllowedError"));
        };
    }
})();
"""


class SessionManager:
    def __init__(self, storage_root: str = "~/.nexus_orchestrator"):
        self.root_dir = os.path.expanduser(storage_root)
        self.profiles_dir = os.path.join(self.root_dir, "profiles")
        self.gemini_cookies_file = os.path.join(self.root_dir, "gemini_cookies", "default_gemini_cookies.json")
        self.accounts_file = os.path.join(self.root_dir, "accounts.json")
        self._active_profiles: Dict[str, QWebEngineProfile] = {}

        os.makedirs(self.profiles_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.gemini_cookies_file), exist_ok=True)

    def load_accounts(self) -> List[Dict]:
        if not os.path.exists(self.accounts_file):
            default_accounts = [
                {"id": "acc_1", "account_name": "Harivishnu0558", "platform": "claude", "last_url": "https://" + "claude.ai/new"},
                {"id": "acc_2", "account_name": "Yasnax678", "platform": "claude", "last_url": "https://" + "claude.ai/new"},
                {"id": "acc_3", "account_name": "Batmanrock1357", "platform": "claude", "last_url": "https://" + "claude.ai/new"},
                {"id": "acc_4", "account_name": "Lgostv94", "platform": "claude", "last_url": "https://" + "claude.ai/new"}
            ]
            self.save_accounts(default_accounts)
            return default_accounts

        try:
            with open(self.accounts_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def save_accounts(self, accounts: List[Dict]):
        with open(self.accounts_file, "w", encoding="utf-8") as f:
            json.dump(accounts, f, indent=2)

    def update_last_url(self, account_id: str, url: str):
        if not url or "login" in url.lower() or "accounts.google.com" in url.lower():
            return
        accounts = self.load_accounts()
        for acc in accounts:
            if acc.get("id") == account_id:
                acc["last_url"] = url
                break
        self.save_accounts(accounts)

    def get_or_create_profile(self, account_id: str, parent=None) -> QWebEngineProfile:
        if account_id in self._active_profiles:
            return self._active_profiles[account_id]

        profile_path = os.path.abspath(os.path.join(self.profiles_dir, account_id))
        os.makedirs(profile_path, exist_ok=True)

        profile = QWebEngineProfile(account_id, parent)
        profile.setPersistentStoragePath(profile_path)
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )

        # Prevent Windows Security Passkey modal from interrupting password entry
        script = QWebEngineScript()
        script.setName("disable_webauthn_passkey")
        script.setSourceCode(NO_PASSKEY_STEALTH_JS)
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(True)
        profile.scripts().insert(script)

        self._active_profiles[account_id] = profile
        return profile

    def inject_default_gemini_cookies(self, profile: QWebEngineProfile) -> int:
        if not os.path.exists(self.gemini_cookies_file):
            return 0
        try:
            with open(self.gemini_cookies_file, "r", encoding="utf-8") as f:
                cookie_data = json.load(f)
        except Exception:
            return 0

        store = profile.cookieStore()
        injected_count = 0

        for c in (cookie_data or []):
            if "partitionKey" in c:
                continue
            domain = c.get("domain", "").strip()
            if "google.com" not in domain:
                continue
            raw_name = c.get("name", "")
            raw_val = c.get("value", "")
            if not raw_name:
                continue

            path = c.get("path", "/")
            is_secure = bool(c.get("secure", False)) or raw_name.startswith("__Secure-") or raw_name.startswith("__Host-")
            is_http_only = bool(c.get("httpOnly", False))
            same_site_raw = (c.get("sameSite") or "").lower()

            header_parts = [f"{raw_name}={raw_val}", f"Path={path}"]
            if not c.get("hostOnly", False) and not raw_name.startswith("__Host-"):
                header_parts.append(f"Domain={domain}")
            if "expirationDate" in c and not c.get("session", False):
                dt = QDateTime.fromSecsSinceEpoch(int(float(c["expirationDate"]))).toUTC()
                expires_str = dt.toString("ddd, dd MMM yyyy hh:mm:ss 'GMT'")
                header_parts.append(f"Expires={expires_str}")
            if is_secure:
                header_parts.append("Secure")
            if is_http_only:
                header_parts.append("HttpOnly")
            if same_site_raw in ("no_restriction", "none"):
                header_parts.append("SameSite=None")
            elif same_site_raw == "lax":
                header_parts.append("SameSite=Lax")
            elif same_site_raw == "strict":
                header_parts.append("SameSite=Strict")

            raw_header = "; ".join(header_parts).encode("utf-8")
            parsed_cookies = QNetworkCookie.parseCookies(QByteArray(raw_header))
            if parsed_cookies:
                qcookie = parsed_cookies[0]
            else:
                qcookie = QNetworkCookie(raw_name.encode("utf-8"), raw_val.encode("utf-8"))
                qcookie.setDomain(domain)
                qcookie.setPath(path)
                qcookie.setSecure(is_secure)
                qcookie.setHttpOnly(is_http_only)

            clean_host = domain.lstrip(".")
            if clean_host == "google.com":
                store.setCookie(qcookie, QUrl("https://" + "www.google.com/"))
                store.setCookie(qcookie, QUrl("https://" + "accounts.google.com/"))
                store.setCookie(qcookie, QUrl("https://" + "gemini.google.com/"))
            else:
                store.setCookie(qcookie, QUrl("https://" + clean_host + "/"))
            injected_count += 1

        return injected_count
