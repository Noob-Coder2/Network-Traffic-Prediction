import os
import json
from tkinter import simpledialog, messagebox
import ast

# --- Global Configuration ---
APP_NAME = "FileConsolidator"
CONFIG_DIR = os.path.join(os.path.expanduser("~"), f".{APP_NAME}")
CONFIG_FILE = os.path.join(CONFIG_DIR, "app_config.json")
PROFILES_FILE = os.path.join(CONFIG_DIR, "profiles.json")
MAX_RECENT_FOLDERS = 5
DEFAULT_GLOBAL_IGNORE_FOLDERS = ['__pycache__', '.venv', '.git', 'node_modules', 'build', 'dist']
DEFAULT_GLOBAL_IGNORE_FILES = ['.DS_Store', '*.pyc', '*.log', '.env']

class ConfigHandler:
    """
    Manages loading and saving of application settings, profiles,
    and global ignore patterns.
    """
    def __init__(self, app):
        self.app = app
        self.MAX_RECENT_FOLDERS = MAX_RECENT_FOLDERS

        # --- Configurable Instance Variables ---
        self.global_folder_ignores = list(DEFAULT_GLOBAL_IGNORE_FOLDERS)
        self.global_file_ignores = list(DEFAULT_GLOBAL_IGNORE_FILES)

        os.makedirs(CONFIG_DIR, exist_ok=True)
        self.load_profiles()
        self.load_settings()

    def load_profiles(self):
        """Loads saved profiles from the profiles JSON file."""
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, 'r') as f:
                    self.app.profiles = json.load(f)
            except (IOError, json.JSONDecodeError):
                self.app.profiles = {}

    def save_profile(self):
        """Saves the current settings as a new profile."""
        name = simpledialog.askstring("Save Profile", "Enter a name for this profile:", parent=self.app)
        if not name: return

        try:
            folder_ignores = ast.literal_eval(self.app.folder_ignore_patterns.get())
            file_ignores = ast.literal_eval(self.app.file_ignore_patterns.get())
        except (ValueError, SyntaxError):
            folder_ignores = self.global_folder_ignores
            file_ignores = self.global_file_ignores
            messagebox.showwarning("Invalid Patterns", "Ignore patterns were invalid and reset to defaults.")

        self.app.profiles[name] = {
            "file_types": self.app.file_types.get(),
            "output_format": self.app.output_format.get(),
            "folder_ignores": folder_ignores,
            "file_ignores": file_ignores,
            "include_headers": self.app.include_headers.get(),
        }
        try:
            with open(PROFILES_FILE, 'w') as f:
                json.dump(self.app.profiles, f, indent=4)
            messagebox.showinfo("Success", f"Profile '{name}' saved.")
            self.app.ui_manager.populate_profiles_menu()
        except IOError as e:
            messagebox.showerror("Error", f"Could not save profiles.\n{e}")

    def load_profile(self, name):
        """Loads a selected profile's settings into the UI."""
        if name in self.app.profiles:
            p = self.app.profiles[name]
            self.app.file_types.set(p.get("file_types", ".py"))
            self.app.output_format.set(p.get("output_format", "TXT"))
            self.app.folder_ignore_patterns.set(str(p.get("folder_ignores", [])))
            self.app.file_ignore_patterns.set(str(p.get("file_ignores", [])))
            self.app.include_headers.set(p.get("include_headers", True))
            self.app.ui_manager.status_label.config(text=f"Profile '{name}' loaded.")
            self.app.ui_manager.populate_file_tree()

    def load_settings(self):
        """Loads the last session's settings and global configurations."""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    s = json.load(f)
                    self.app.recent_folders = s.get("recent_folders", [])
                    self.app.theme_var.set(s.get("theme", "light"))

                    custom_globals = s.get("custom_global_ignores", {})
                    self.global_folder_ignores = custom_globals.get("folders", list(DEFAULT_GLOBAL_IGNORE_FOLDERS))
                    self.global_file_ignores = custom_globals.get("files", list(DEFAULT_GLOBAL_IGNORE_FILES))

                    last_session = s.get("last_session_settings")
                    if last_session:
                        self.app.file_types.set(last_session.get("file_types", ".py,.txt,.md"))
                        self.app.output_format.set(last_session.get("output_format", "TXT"))
                        self.app.folder_ignore_patterns.set(str(last_session.get("folder_ignores", self.global_folder_ignores)))
                        self.app.file_ignore_patterns.set(str(last_session.get("file_ignores", self.global_file_ignores)))
                        self.app.include_headers.set(last_session.get("include_headers", True))
                    else:
                        self._set_defaults()
            else:
                self._set_defaults()
        except (IOError, json.JSONDecodeError):
            self._set_defaults()

    def save_settings(self):
        """Saves the current session's settings and global configurations."""
        try:
            folder_ignores = eval(self.app.folder_ignore_patterns.get())
            file_ignores = eval(self.app.file_ignore_patterns.get())
        except:
            folder_ignores = self.global_folder_ignores
            file_ignores = self.global_file_ignores

        settings_to_save = {
            "last_session_settings": {
                "file_types": self.app.file_types.get(),
                "output_format": self.app.output_format.get(),
                "folder_ignores": folder_ignores,
                "file_ignores": file_ignores,
                "include_headers": self.app.include_headers.get(),
            },
            "custom_global_ignores": {
                "folders": self.global_folder_ignores,
                "files": self.global_file_ignores
            },
            "recent_folders": self.app.recent_folders,
            "theme": self.app.theme_var.get()
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(settings_to_save, f, indent=4)
        except IOError as e:
            print(f"Warning: Could not save settings to {CONFIG_FILE}. Error: {e}")

    def _set_defaults(self):
        """Applies default settings if no config file is found."""
        self.app.theme_var.set("light")
        self.app.folder_ignore_patterns.set(str(self.global_folder_ignores))
        self.app.file_ignore_patterns.set(str(self.global_file_ignores))
