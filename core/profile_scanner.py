"""
Profile Scanner Module
Discovers Chrome profiles, display names, and signed-in email addresses on Windows.
Bypasses PowerShell by directly reading the 'Local State' JSON file.
"""

import json
import os
from typing import Dict, List

class ChromeProfileScanner:
    def __init__(self):
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        self.local_state_path = os.path.join(
            local_appdata, "Google", "Chrome", "User Data", "Local State"
        )

    def is_chrome_installed(self) -> bool:
        """Check if Chrome's user data directory exists on this PC."""
        return os.path.isfile(self.local_state_path)

    def scan_profiles(self) -> List[Dict[str, str]]:
        """
        Parse Chrome's Local State file and extract profile information.
        Returns a list of dictionaries containing profile directory and email.
        """
        if not self.is_chrome_installed():
            print("[Warning] Chrome Local State not found. Chrome may not be installed.")
            return []

        discovered = []
        try:
            with open(self.local_state_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            info_cache = data.get("profile", {}).get("info_cache", {})
            for profile_dir, details in info_cache.items():
                display_name = details.get("name", profile_dir)
                user_name = details.get("user_name", "")  # The signed-in Google account email

                discovered.append({
                    "profile_dir": profile_dir,
                    "display_name": display_name,
                    "email": user_name if user_name else "Not Signed In",
                })

        except (json.JSONDecodeError, PermissionError, OSError) as err:
            print(f"[Warning] Failed to read Chrome Local State: {err}")
            return []

        return discovered
