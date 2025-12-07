import os
import importlib.util

class PluginManager:
    def __init__(self, app):
        self.app = app   # ✅ SIMPAN FileManager DI SINI

    def load_plugins(self):
        plugin_dir = os.path.expanduser("~/.config/zeta/plugins")

        if not os.path.exists(plugin_dir):
            os.makedirs(plugin_dir, exist_ok=True)
            return

        for fname in os.listdir(plugin_dir):
            if fname.endswith(".py"):
                path = os.path.join(plugin_dir, fname)

                try:
                    spec = importlib.util.spec_from_file_location(fname, path)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    # ✅ KIRIM APP, BUKAN PLUGIN MANAGER
                    if hasattr(mod, "setup"):
                        mod.setup(self.app)

                except Exception as e:
                    self.app.show_message(f"Plugin error: {e}", 4)

