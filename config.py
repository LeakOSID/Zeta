# config.py
import json
import os

class Config:
    DEFAULT = {
        "keybindings": {
            "quit": "q",
            "copy": "c",
            "plugin_torrent": "D",
            "open_with": "w",
            "cut": "x",
            "paste": "v",
            "delete": "d",
            "new_file": "n",
            "new_folder": "m",
            "rename": "r",
            "extract": "e",
            "compress": "s",
            "toggle_panel": "t",
            "toggle_right": " ",
            "search": "/"
        }
    }

    def __init__(self):
        self.path = os.path.expanduser("~/.config/zeta/config.json")
        self.data = self.load()

    def load(self):
        if not os.path.exists(self.path):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w") as f:
                json.dump(self.DEFAULT, f, indent=4)
            return self.DEFAULT

        with open(self.path) as f:
            return json.load(f)

    def key(self, name):
        key_str = self.data.get("keybindings", {}).get(name)

        if not key_str:
            return None

        key_str = key_str.lower()

        if key_str == "enter":
            return 10        # curses standard
        elif key_str == "esc":
            return 27
        elif key_str == "space":
            return 32

        return ord(key_str)