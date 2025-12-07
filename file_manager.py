import os
import curses
import subprocess
import shutil
import pwd
import stat
import time

from curses import textpad
from pathlib import Path
import traceback
from panel import FilePanel
from colors import ColorScheme
from archive_extractor import ArchiveExtractor
from plug import PluginManager


class FileManager:
    def __init__(self, stdscr, config):
        self.stdscr = stdscr
        self.color_scheme = ColorScheme()
        self.left_panel = FilePanel(str(Path.home()))
        self.config = config
        self.right_panel = FilePanel("/")
        self.active_panel = "left"
        self.search_mode = False
        self.search_query = ""
        self.message = ""
        self.message_timer = 0
        self.clipboard_path = ""
        self.clipboard_mode = ""  # "copy" or "cut"
        self.right_panel_visible = True
        self.bg_task = None        # nama task
        self.bg_progress = 0       # 0–100
        self.bg_current = ""       # nama file
        self.bg_done = False       # selesai atau belum
        self.bg_total = 0
        self.bg_now = 0
        self.bg_paused = False
        self.needs_full_redraw = True
        self.plugin_keybindings = {}      # <-- pindahkan ke atas

        self.plug = PluginManager(self)
        self.plug.load_plugins()

        # Hapus semua variabel terkait command line
        self.create_windows()
        self.init_ui()

    def init_ui(self):
        self.stdscr.keypad(True)
        curses.curs_set(0)
        curses.use_default_colors()
        curses.noecho()
        curses.cbreak()
        self.stdscr.clear()
        self.stdscr.refresh()

    @property
    def current_panel(self):
        return self.left_panel if self.active_panel == "left" else self.right_panel

    @property
    def inactive_panel(self):
        return self.right_panel if self.active_panel == "left" else self.left_panel

    def create_windows(self):
        h, w = self.stdscr.getmaxyx()
        mid = w // 2

        try:
            # Hapus windows lama jika ada
            if hasattr(self, 'left_win'):
                self.left_win.erase()
                del self.left_win
            if hasattr(self, 'right_win'):
                self.right_win.erase()
                del self.right_win
        except:
            pass

        # Buat panel utama
        self.left_win = curses.newwin(h - 4, mid - 1, 2, 0)
        self.right_win = curses.newwin(h - 4, w - mid - 1, 2, mid + 1)
        
        self.left_win.keypad(True)
        self.right_win.keypad(True)

    # =====================================================
    #                    DRAW UI
    # =====================================================
    def draw(self):
        try:
            height, width = self.stdscr.getmaxyx()

            if height <= 0 or width <= 0:
                return

            if height < 10 or width < 40:
                try:
                    self.stdscr.clear()
                    msg = "Terminal terlalu kecil. Perbesar dan jalankan ulang."
                    self.stdscr.addstr(0, 0, msg[:width-1])
                    self.stdscr.refresh()
                    curses.napms(2000)
                    return
                except:
                    return

            # Bersihkan layar
            self.stdscr.erase()
            
            # Header (baris 0)
            self.draw_header_safe(width, height)
            
            # Hitung tinggi untuk panel file
            panel_height = max(height - 4, 5)
            
            # Tentukan lebar panel
            if self.right_panel_visible:
                panel_width = max((width - 4) // 2, 10)
            else:
                panel_width = width - 4
            
            # Left panel (mulai dari baris 2)
            if 2 < height and 1 < width:
                self.draw_panel_safe(
                    self.left_panel,
                    2,  # y-position
                    1,  # x-position
                    panel_height,
                    panel_width,
                    self.active_panel == "left",
                    height,
                    width
                )
            
            # Right panel
            if self.right_panel_visible and panel_width + 2 < width:
                self.draw_panel_safe(
                    self.right_panel,
                    2,
                    panel_width + 2,
                    panel_height,
                    panel_width,
                    self.active_panel == "right",
                    height,
                    width
                )
            
            # Status bar (baris terakhir - 1)
            status_bar_y = height - 2
            if status_bar_y > 0:
                try:
                    self.draw_status_bar_safe(status_bar_y, width)
                except:
                    pass
            
            # Progress bar (jika ada, di atas status bar)
            if height > 3:
                try:
                    self.draw_progress_bar_safe(height - 3, width)
                except:
                    pass
            
            # Message (tampilkan di atas progress bar)
            if self.message and self.message_timer > 0:
                if height > 4:
                    try:
                        msg = self.message.ljust(width - 1)[:width-1]
                        color = curses.color_pair(8 if "Error" in self.message else 9)
                        self.stdscr.addstr(height - 4, 0, msg, color)
                    except:
                        pass
                self.message_timer -= 1
            
            self.stdscr.refresh()
            
        except Exception as e:
            try:
                self.stdscr.clear()
                self.stdscr.addstr(0, 0, f"Draw error: {str(e)[:30]}")
                self.stdscr.refresh()
                curses.napms(100)
            except:
                pass

    def draw_header_safe(self, width, height):
        if height < 1 or width < 1:
            return
            
        try:
            header = "[ Zeta Manager ]"
            x = max(0, (width - len(header)) // 2)
            x = min(x, width - len(header))
            
            bg_color = self.color_scheme.get(12)
            text_color = self.color_scheme.get(2) | curses.A_BOLD
            self.stdscr.attron(bg_color)
            self.stdscr.addstr(0, 0, " " * width)
            self.stdscr.attroff(bg_color)
            if x + len(header) <= width:
                self.stdscr.attron(bg_color)
                self.stdscr.addstr(0, x, " " * min(len(header), width-x))
                self.stdscr.attroff(bg_color)
                self.stdscr.addstr(0, x, header, text_color)
        except:
            pass

    def draw_panel_safe(self, panel, y, x, height, width, active, screen_h, screen_w):
        if y >= screen_h or x >= screen_w or height <= 0 or width <= 0:
            return
            
        if x + width > screen_w:
            width = screen_w - x - 1
        if y + height > screen_h:
            height = screen_h - y - 1
            
        if width <= 0 or height <= 0:
            return
            
        try:
            # Header
            if active and self.search_mode:
                search_line = f"[ /: {self.search_query}"
                search_bg = self.color_scheme.get(12) | curses.A_BOLD

                self.stdscr.attron(search_bg)
                safe_width = min(width + 1, screen_w - x)
                if safe_width > 0:
                    self.stdscr.addstr(y, x, " " * safe_width)
                    if x + 2 < screen_w:
                        self.stdscr.addstr(y, x + 2, search_line[: width - 3])
                self.stdscr.attroff(search_bg)
                panel_y = y + 1

            else:
                path_line = panel.path
                if len(path_line) > width - 4:
                    path_line = "..." + path_line[-(width - 7):]

                header_color = self.color_scheme.get(12 if active else 4)
                self.stdscr.attron(header_color)
                safe_width = min(width + 1, screen_w - x)
                if safe_width > 0:
                    self.stdscr.addstr(y, x, " " * safe_width)
                    if x + 2 < screen_w:
                        self.stdscr.addstr(y, x + 2, path_line.ljust(width - 3)[:width-3])
                self.stdscr.attroff(header_color)
                panel_y = y + 1

            if panel_y >= screen_h:
                return

            # Border
            border_color = curses.color_pair(2) if active else curses.color_pair(3)
            self.stdscr.attron(border_color)
            try:
                for i in range(panel_y, min(panel_y + height + 1, screen_h)):
                    if i == panel_y:
                        border_line = "┌" + "─" * (width - 1) + "┐"
                        if x + len(border_line) <= screen_w:
                            self.stdscr.addstr(i, x, border_line[:screen_w-x])
                    elif i == min(panel_y + height, screen_h - 1):
                        border_line = "└" + "─" * (width - 1) + "┘"
                        if x + len(border_line) <= screen_w:
                            self.stdscr.addstr(i, x, border_line[:screen_w-x])
                    else:
                        if x < screen_w:
                            self.stdscr.addstr(i, x, "│")
                        if x + width < screen_w:
                            self.stdscr.addstr(i, x + width, "│")
            except:
                pass
            self.stdscr.attroff(border_color)

            # Files
            total_files = len(panel.files)
            visible_items = height - 2
            if visible_items <= 0:
                return
                
            start = panel.scroll_offset
            end = min(start + visible_items, total_files)

            for i, item in enumerate(panel.files[start:end]):
                idx = start + i
                is_selected = idx == panel.cursor_pos
                full_path = os.path.join(panel.path, item)
                is_dir = os.path.isdir(full_path)

                if is_dir:
                    size_str = "<DIR>"
                else:
                    try:
                        size_str = f"{os.path.getsize(full_path)} B"
                    except:
                        size_str = "N/A"

                icon = self.get_icon(item)
                name_trim = item if len(item) <= width - 20 else item[:width - 23] + "..."
                display_name = f"{icon} {name_trim}"
                line = f"{display_name:<{width - 15}} {size_str:>10}"

                color = (
                    self.color_scheme.get(7) if is_selected and is_dir
                    else self.color_scheme.get(5) if is_selected
                    else self.color_scheme.get(6) if is_dir
                    else self.color_scheme.get(1)
                )

                line_y = panel_y + 1 + i
                line_x = x + 2
                
                if line_y < screen_h and line_x < screen_w:
                    safe_line = line[: width - 3]
                    if line_x + len(safe_line) <= screen_w:
                        try:
                            self.stdscr.addstr(line_y, line_x, safe_line, color)
                        except:
                            pass

            # Footer
            try:
                summary_y = panel_y + height
                summary_x = x + 2
                if summary_y < screen_h and summary_x < screen_w:
                    summary_text = f"[ {total_files} files ]"
                    summary_color = self.color_scheme.get(9 if active else 8) | curses.A_BOLD
                    safe_summary = summary_text[: width - 4]
                    if summary_x + len(safe_summary) <= screen_w:
                        self.stdscr.attron(summary_color)
                        self.stdscr.addstr(summary_y, summary_x, safe_summary)
                        self.stdscr.attroff(summary_color)
            except:
                pass
                
        except Exception as e:
            pass

    def draw_status_bar_safe(self, height, width):
        if height < 1 or width < 10:
            return
            
        selected = self.current_panel.get_selected()
        if not selected or selected == "[Permission Denied]":
            return

        try:
            full_path = os.path.join(self.current_panel.path, selected)
            stat_info = os.stat(full_path)
            size = self.human_size(stat_info.st_size) if not os.path.isdir(full_path) else "<DIR>"
            owner = pwd.getpwuid(stat_info.st_uid).pw_name
            perms = self.file_permissions(stat_info.st_mode)
            mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(stat_info.st_mtime))

            info = f"{selected} | {size} | {owner} | {perms} | {mtime}"
        except Exception:
            info = f"{selected} | <no info>"

        color = self.color_scheme.get(2) | curses.A_BOLD
        
        # Bersihkan baris sebelumnya
        try:
            self.stdscr.addstr(height, 0, " " * width)
        except:
            pass
        
        safe_info = info[: width - 2]
        try:
            self.stdscr.addstr(height, 1, safe_info, color)
        except:
            pass

    def draw_progress_bar_safe(self, height, width):
        if not self.bg_task or self.bg_done:
            return
        
        if height < 1 or width < 30:
            return
        
        bar_width = min(width - 20, 50)
        filled = int((self.bg_progress / 100) * bar_width)
        empty = bar_width - filled

        bar = "[" + "=" * filled + " " * empty + "]"
        line = f"{self.bg_task}: {self.bg_current} {bar} {self.bg_progress:.0f}%"
        
        # Bersihkan baris sebelumnya
        try:
            self.stdscr.addstr(height, 0, " " * width)
        except:
            pass
        
        safe_line = line[: width - 2]
        try:
            self.stdscr.addstr(height, 1, safe_line, self.color_scheme.get(3) | curses.A_BOLD)
        except:
            pass

    def human_size(self, size):
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}PB"

    def file_permissions(self, mode):
        perms = [
            stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR,
            stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP,
            stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH,
        ]
        symbols = ["r", "w", "x"] * 3
        return "".join(symbols[i] if mode & perms[i] else "-" for i in range(9))

    # =====================================================
    #                      TOGGLE
    # =====================================================
    def toggle_right_panel(self):
        self.right_panel_visible = not self.right_panel_visible

        if not self.right_panel_visible and self.active_panel == "right":
            self.active_panel = "left"

        self.show_message(
            f"Toggle panel {'hidden' if not self.right_panel_visible else 'shown'}",
            2
        )

    def toggle_panel(self):
        try:
            if self.active_panel == "left":
                self.active_panel = "right"
                self.show_message("Switched to right panel", 1)
            else:
                self.active_panel = "left"
                self.show_message("Switched to left panel", 1)
            self.needs_full_redraw = True
            return True
        except Exception as e:
            self.show_message(f"Toggle error: {str(e)[:30]}", 3)
            return True

    def get_icon(self, filename):
        name = filename.lower()
        full = os.path.join(self.current_panel.path, filename)

        if os.path.isdir(full):
            if filename == self.current_panel.get_selected():
                return ""
            return ""

        if filename == "[Permission Denied]":
            return ""

        if os.path.islink(full):
            return ""

        if name.startswith("."):
            return ""

        if os.access(full, os.X_OK) and not os.path.isdir(full):
            return ""

        # Programming languages
        if name.endswith(".py"): return ""
        if name.endswith((".c", ".h")): return ""
        if name.endswith((".cpp", ".hpp", ".cc", ".cxx")): return ""
        if name.endswith(".rs"): return ""
        if name.endswith(".go"): return ""
        if name.endswith(".java"): return ""
        if name.endswith(".kt"): return ""
        if name.endswith(".swift"): return ""
        if name.endswith(".cs"): return ""
        if name.endswith(".php"): return ""
        if name.endswith(".rb"): return ""
        if name.endswith(".lua"): return ""
        if name.endswith(".js"): return ""
        if name.endswith(".mjs"): return ""
        if name.endswith(".ts"): return ""
        if name.endswith(".tsx"): return ""
        if name.endswith(".html"): return ""
        if name.endswith(".css"): return ""
        if name.endswith(".scss"): return ""
        if name.endswith(".less"): return ""
        if name.endswith(".svelte"): return ""
        if name.endswith(".vue"): return "﵂"
        if name.endswith((".sql", ".db", ".sqlite", ".sqlite3")):
            return ""
        if name.endswith(".json"): return ""
        if name.endswith(".yaml") or name.endswith(".yml"): return ""
        if name.endswith(".toml"): return ""
        if name.endswith((".ini", ".cfg")): return ""
        if name in ("makefile", "gnumakefile") or name.endswith(".mk"):
            return ""
        if name.endswith(".cmake"):
            return "󰔷"
        if name.endswith((".asm", ".s")):
            return ""
        if name.endswith((".sh", ".bash", ".zsh")):
            return ""
        if name == "dockerfile":
            return ""
        if name.endswith(".tf"):
            return ""
        if name.endswith(".patch"): return ""
        if name.endswith(".diff"): return ""

        # Documents
        if name.endswith(".md"): return ""
        if name.endswith(".txt"): return ""
        if name.endswith(".pdf"): return ""
        if name.endswith((".doc", ".docx")): return ""
        if name.endswith((".ppt", ".pptx")): return ""
        if name.endswith((".xls", ".xlsx")): return ""
        if name.endswith(".xml"): return ""

        # Media
        if name.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")):
            return ""
        if name.endswith((".mp4", ".mkv", ".avi", ".mov", ".flv")):
            return ""
        if name.endswith((".mp3", ".wav", ".flac", ".ogg")):
            return ""

        # Archive
        if name.endswith((".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz")):
            return ""

        # Fonts
        if name.endswith((".ttf", ".otf", ".woff", ".woff2")):
            return ""

        return ""

    # =====================================================
    #                FILE OPERATIONS
    # =====================================================
    def create_new_file(self):
        selected = self.current_panel.path
        if not selected:
            self.show_message("No directory selected", 2)
            return

        height, width = self.stdscr.getmaxyx()
        popup_h = 5
        popup_w = min(50, width - 10)
        popup_y = max(1, height // 2 - popup_h // 2)
        popup_x = max(1, width // 2 - popup_w // 2)

        popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
        popup.border()
        popup.addstr(0, 2, " Create New File ")
        popup.addstr(1, 2, "Enter new file name: ")
        popup.refresh()

        input_win = curses.newwin(1, popup_w - 12, popup_y + 2, popup_x + 11)

        curses.curs_set(1)
        curses.noecho()

        try:
            box = textpad.Textbox(input_win)
            new_file_name = box.edit().strip()

            if new_file_name:
                new_file_path = os.path.join(self.current_panel.path, new_file_name)
                with open(new_file_path, "w") as f:
                    f.write("")
                self.show_message(f"Created '{new_file_name}'", 3)
                self.current_panel.refresh_files()

        finally:
            curses.curs_set(0)
            self.stdscr.touchwin()
            self.stdscr.refresh()

    def copy_file(self):
        selected = self.current_panel.get_selected()
        if not selected or selected == "[Permission Denied]":
            self.show_message("No file selected", 2)
            return

        self.clipboard_path = os.path.join(self.current_panel.path, selected)
        self.clipboard_mode = "copy"
        self.show_message(f"Copied: {selected}", 3)

    def cut_file(self):
        selected = self.current_panel.get_selected()
        if not selected or selected == "[Permission Denied]":
            self.show_message("No file selected", 2)
            return

        self.clipboard_path = os.path.join(self.current_panel.path, selected)
        self.clipboard_mode = "cut"
        self.show_message(f"Cut: {selected}", 3)

    def paste_file(self):
        if not self.clipboard_path:
            self.show_message("Clipboard empty", 2)
            return

        src = self.clipboard_path
        dest_dir = self.current_panel.path
        filename = os.path.basename(src)
        dest = os.path.join(dest_dir, filename)

        if os.path.isdir(src):
            self.show_message("Folder copy not yet supported with progress", 3)
            return

        self.bg_task = "Copy" if self.clipboard_mode == "copy" else "Move"
        self.bg_progress = 0
        self.bg_current = filename
        self.bg_done = False

        try:
            self.bg_total = os.path.getsize(src)
        except:
            self.show_message("Error getting file size", 5)
            return
            
        self.bg_now = 0

        import threading
        
        def worker():
            try:
                with open(src, "rb") as fsrc, open(dest, "wb") as fdst:
                    chunk = 1024 * 1024  # 1MB
                    while True:
                        if self.bg_done:
                            break
                        
                        data = fsrc.read(chunk)
                        if not data:
                            break
                        
                        fdst.write(data)
                        self.bg_now += len(data)
                        self.bg_progress = (self.bg_now / self.bg_total) * 100
                        
            except Exception as e:
                self.bg_done = True
                self.show_message(f"Error during copy: {e}", 5)
                return

            if not self.bg_done and self.clipboard_mode == "cut":
                try:
                    os.remove(src)
                except:
                    pass

            if not self.bg_done:
                self.bg_done = True

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        
        self.stdscr.nodelay(True)
        while thread.is_alive():
            self.draw()
            key = self.stdscr.getch()
            if key != -1:
                if key == 27:
                    self.bg_done = True
                    thread.join(timeout=1)
                    self.show_message("Operation cancelled", 3)
                    self.stdscr.nodelay(False)
                    return
                self.handle_input()
            curses.napms(50)
        
        self.stdscr.nodelay(False)
        
        self.current_panel.refresh_files()
        self.show_message(f"{self.bg_task} done: {filename}", 3)
        self.bg_task = None

    def delete_file(self):
        selected = self.current_panel.get_selected()
        if not selected:
            self.show_message("No file selected", 2)
            return

        #path = os.path.join(self.current_panel.path, selected)
        selected_path = os.path.join(self.current_panel.path, selected)

        height, width = self.stdscr.getmaxyx()

        popup_h = 5
        popup_w = 50
        popup = curses.newwin(
            popup_h, popup_w, height // 2 - popup_h // 2, width // 2 - popup_w // 2
        )
        popup.border()
        popup.addstr(0, 2, " Confirm Delete ")
        popup.addstr(1, 2, f"Delete '{selected[:30]}'?")
        popup.addstr(2, 2, "This action cannot be undone!")
        popup.addstr(3, 2, "Press Y to confirm, any key to cancel")
        popup.refresh()

        key = self.stdscr.getch()

        if key in [ord("Y"), ord("y")]:
            try:
                if os.path.isdir(selected_path):
                    shutil.rmtree(selected_path)
                    self.show_message(f"Folder '{selected}' deleted", 3)
                elif os.path.isfile(selected_path):
                # Jika yang dipilih adalah file, hapus file
                    os.remove(selected_path)
                    self.show_message(f"File '{selected}' deleted", 3)

                else:
                    self.show_message(f"{selected} is not a file or folder", 2)
                self.current_panel.refresh_files()

            except Exception as e:
                self.show_message(f"Error deleting {selected}: {str(e)}", 2)
        else:
            self.show_message("Deletion cancelled", 2)

    def delete_folder(self):
        selected = self.current_panel.get_selected()
        if not selected:
            self.show_message("No folder selected", 2)
            return

        full_path = os.path.join(self.current_panel.path, selected)
        
        if not os.path.isdir(full_path):
            self.show_message("Selected item is not a folder", 2)
            return

        height, width = self.stdscr.getmaxyx()

        total_size = 0
        file_count = 0
        dir_count = 0
        
        try:
            for root, dirs, files in os.walk(full_path):
                dir_count += len(dirs)
                file_count += len(files)
                for file in files:
                    try:
                        total_size += os.path.getsize(os.path.join(root, file))
                    except:
                        pass
        except:
            pass

        popup_h = 8
        popup_w = min(70, width - 10)
        popup_y = max(1, height // 2 - popup_h // 2)
        popup_x = max(1, width // 2 - popup_w // 2)

        popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
        popup.border()
        popup.addstr(0, 2, " DELETE FOLDER ")
        
        folder_display = selected[:popup_w-10]
        popup.addstr(1, 2, f"Folder: {folder_display}")
        popup.addstr(2, 2, f"Location: {self.current_panel.path[:popup_w-12]}")
        popup.addstr(3, 2, f"Contains: {file_count} files, {dir_count} folders")
        popup.addstr(4, 2, f"Total size: {self.human_size(total_size)}")
        
        popup.addstr(5, 2, "This will PERMANENTLY delete everything!")
        popup.addstr(6, 2, "Press Y to confirm, any key to cancel")
        
        popup.refresh()

        key = self.stdscr.getch()

        if key in [ord("Y"), ord("y")]:
            self.bg_task = "Deleting"
            self.bg_progress = 0
            self.bg_current = selected
            self.bg_done = False
            self.bg_total = file_count + dir_count
            self.bg_now = 0
            
            import threading
            
            def delete_worker():
                try:
                    def on_error(func, path, exc_info):
                        self.show_message(f"Error deleting {path}", 3)
                    
                    shutil.rmtree(full_path, onerror=on_error)
                    
                    self.bg_progress = 100
                    self.bg_done = True
                    
                except Exception as e:
                    self.bg_done = True
                    self.show_message(f"Error deleting folder: {e}", 5)
                    return
            
            thread = threading.Thread(target=delete_worker, daemon=True)
            thread.start()
            
            self.stdscr.nodelay(True)
            start_time = time.time()
            
            while thread.is_alive():
                elapsed = time.time() - start_time
                progress = min(90, int((elapsed / 30) * 100))
                
                if progress > self.bg_progress:
                    self.bg_progress = progress
                
                self.draw()
                key = self.stdscr.getch()
                
                if key != -1:
                    if key == 27:
                        self.bg_done = True
                        self.show_message("Deletion cancelled", 3)
                        self.stdscr.nodelay(False)
                        return
                
                curses.napms(100)
            
            self.stdscr.nodelay(False)
            
            self.bg_task = None
            self.bg_done = True
            
            self.current_panel.refresh_files()
            self.show_message(f"Folder '{selected}' deleted successfully", 3)

    def create_new_folder(self):
        selected_path = self.current_panel.path
        if not os.access(selected_path, os.W_OK):
           self.show_message("Permission denied", 3)
           return
        height, width = self.stdscr.getmaxyx()
        popup_h = 5
        popup_w = min(60, width - 10)
        popup_y = height // 2 - popup_h // 2
        popup_x = width // 2 - popup_w // 2
        popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
        popup.border()
        popup.addstr(0, 2,  " Create New Folder ")
        popup.addstr(1, 2, "Folder name:")
        popup.refresh()

        input_win = curses.newwin(1, popup_w - 16, popup_y + 2, popup_x + 14)
        curses.curs_set(1)
        curses.echo()
        try:
            input_win.addstr(0, 0, "")  # clear
            folder_name = input_win.getstr(0, 0, popup_w - 18).decode().strip()

            if not folder_name:
                self.show_message("Cancelled", 2)
                return
            if "/" in folder_name or "\0" in folder_name:
                self.show_message("Invalid folder name", 3)
                return

            new_folder_path = os.path.join(selected_path, folder_name)

            if os.path.exists(new_folder_path):
                self.show_message(f"'{folder_name}' already exists!", 4)
                return
            os.makedirs(new_folder_path)
            self.show_message(f"Folder created: {folder_name}", 3)
            self.current_panel.refresh_files()

           # Sorot folder yang baru dibuat
            if folder_name in self.current_panel.files:
                idx = self.current_panel.files.index(folder_name)
                self.current_panel.cursor_pos = idx
                visible = self.get_visible_height()
                if idx < self.current_panel.scroll_offset:
                    self.current_panel.scroll_offset = idx
                elif idx >= self.current_panel.scroll_offset + visible:
                    self.current_panel.scroll_offset = idx - visible + 1
        except Exception as e:
              self.show_message(f"Error: {str(e)}", 5)
        finally:
              curses.curs_set(0)
              curses.noecho()
              self.stdscr.touchwin()
              self.stdscr.refresh()

    # =====================================================
    #                   USER INPUT HANDLER
    # =====================================================
    def handle_input(self):
        if self.bg_task and not self.bg_done:
            self.stdscr.timeout(100)
        else:
            self.stdscr.timeout(-1)
        
        key = self.stdscr.getch()
        self.stdscr.timeout(-1)
        
        if key == -1:
            return True
        
        # Hapus pengecekan command_mode
        
        if self.search_mode:
            self.handle_search_input(key)
            return True

        actions = {
            curses.KEY_UP: lambda: self.current_panel.navigate(-1, self.get_visible_height()),
            curses.KEY_DOWN: lambda: self.current_panel.navigate(1, self.get_visible_height()),
            curses.KEY_LEFT: self.current_panel.go_up,
            curses.KEY_RIGHT: self.current_panel.enter_directory,
            10: self.execute_or_enter,                 # ENTER normal
            curses.KEY_ENTER: self.execute_or_enter,  # ENTER numpad / SSH
            # === CONFIG SHORTCUT ===
            self.config.key("open"): self.execute_or_enter,
            self.config.key("open_with"): self.open_with_menu,

            self.config.key("copy"): self.copy_file,
            self.config.key("cut"): self.cut_file,
            self.config.key("paste"): self.paste_file,
            self.config.key("delete"): self.delete_file,
            self.config.key("new_file"): self.create_new_file,
            self.config.key("new_folder"): self.create_new_folder,
            self.config.key("rename"): self.rename_file,
            self.config.key("extract"): self.extract_file,
            self.config.key("compress"): self.compress_file,
            self.config.key("toggle_panel"): self.toggle_panel,
            self.config.key("toggle_right"): self.toggle_right_panel,
            self.config.key("search"): self.start_search,
            self.config.key("quit"): self.exit_program,

            27: self.cancel_background_task,  # ESC tetap hardcode
        }
        for k, func in self.plugin_keybindings.items():
            actions[k] = func
        action = actions.get(key)
        if action:
            try:
                result = action()
                return result if isinstance(result, bool) else True
            except Exception as e:
                self.show_message(f"Error: {str(e)[:30]}", 3)
                return True

        return True


    def register_plugin_key(self, key, callback):
        self.plugin_keybindings[key] = callback

    def cancel_background_task(self):
        if self.bg_task and not self.bg_done:
            self.bg_done = True
            self.show_message("Operation cancelled", 3)
            return True
        return False
    
    
    def open_with_menu(self):
        selected = self.current_panel.get_selected()
        if not selected:
            return

        full_path = os.path.join(self.current_panel.path, selected)

        apps = [
            ("Open Default (xdg)", ["xdg-open", full_path]),
            ("Open with Nano", ["nano", full_path]),
            ("Open with Vim", ["vim", full_path]),
            ("Open with MPV", ["mpv", full_path]),
            ("Open with VLC", ["vlc", full_path]),
            ("Open with Feh", ["feh", full_path]),
            ("Open with Gimp", ["gimp", full_path]),
            ("Open with Firefox", ["firefox", full_path]),
            ("Open with VSCode", ["code --no-sandbox", full_path]),
            ("Open with Qbitorrent", ["qbittorrent-nox", full_path]),
            ("Cancel", None)
        ]

        h, w = self.stdscr.getmaxyx()

        # === DROP-DOWN POSISI DI DEKAT FILE AKTIF ===
        panel_y = 2
        cursor_row = self.current_panel.cursor_pos - self.current_panel.scroll_offset
        drop_y = panel_y + 2 + cursor_row
        drop_x = 4 if self.active_panel == "left" else w // 2 + 4

        win_h = len(apps) + 2
        win_w = 40

        if drop_y + win_h >= h:
            drop_y = h - win_h - 1
        if drop_x + win_w >= w:
            drop_x = w - win_w - 1

        win = curses.newwin(win_h, win_w, drop_y, drop_x)
        win.keypad(True)

        selected_idx = 0

        while True:
            win.clear()
            win.box()

            for i, (name, _) in enumerate(apps):
                if i == selected_idx:
                    win.attron(curses.A_REVERSE)
                win.addstr(i + 1, 2, name[:win_w - 4])
                if i == selected_idx:
                    win.attroff(curses.A_REVERSE)

            win.refresh()
            key = win.getch()

            if key == curses.KEY_UP and selected_idx > 0:
                selected_idx -= 1
            elif key == curses.KEY_DOWN and selected_idx < len(apps) - 1:
                selected_idx += 1

            elif key in (10, 13):  # ENTER
                label, cmd = apps[selected_idx]

                if cmd is None:
                    break

                try:
                    # === JIKA APLIKASI CLI → KELUAR DARI CURSES DULU ===
                    if cmd[0] in ("nano", "vim"):
                        curses.endwin()
                        subprocess.call(cmd)
                        self.init_ui()
                        self.create_windows()
                    else:
                        subprocess.Popen(cmd, start_new_session=True)

                except Exception as e:
                    self.show_message(f"Open Error: {str(e)}", 4)

                break

            elif key == 27:  # ESC
                break

        del win
        self.stdscr.touchwin()
        self.stdscr.refresh()





    def extract_file(self):
        selected = self.current_panel.get_selected()
        if not selected or not os.path.isfile(os.path.join(self.current_panel.path, selected)):
            self.show_message("No valid file selected", 2)
            return

        success, message = ArchiveExtractor.extract_any(
            self.stdscr,
            self.current_panel.path,
            selected
        )

        self.show_message(message, 4)
        if success:
            self.current_panel.refresh_files()

    def compress_file(self):
         selected = self.current_panel.get_selected()
         selected_path = os.path.join(self.current_panel.path, selected)

    # Cek apakah yang dipilih adalah folder atau file
         if not selected or not os.path.exists(selected_path):
             self.show_message("No file or folder selected", 2)
             return

    # Jika yang dipilih adalah file, beri tahu pengguna untuk memilih folder jika perlu
         if not os.path.isdir(selected_path):
             self.show_message("Please select a folder for compression", 2)
             return
         height, width = self.stdscr.getmaxyx()
         # Pilih format kompresi
         popup_h = 5
         popup_w = 60
         popup_y = max(1, height // 2 - popup_h // 2)
         popup_x = max(1, width // 2 - popup_w // 2)
         popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
         popup.border()
         popup.addstr(0, 2, " Select Compression Format ")
         popup.addstr(1, 2, f"Folder: {selected[:popup_w-10]}")
         popup.addstr(2, 2, "Press Z for ZIP, T for TAR.GZ, 7 for 7z")
         popup.refresh()

         key = self.stdscr.getch()

         if key == ord('z'):
             output_zip = os.path.join(self.current_panel.path, f"{selected}.zip")
             success, message = ArchiveExtractor.compress_to_zip(self.stdscr, self.current_panel.path, selected, output_zip)
             self.show_message(message, 3)
             if success:
                 self.current_panel.refresh_files()
         elif key == ord('t'):
             output_tar = os.path.join(self.current_panel.path, f"{selected}.tar.gz")
             success, message = ArchiveExtractor.compress_to_tar_gz(self.stdscr, self.current_panel.path, selected, output_tar)
             self.show_message(message, 3)
             if success:
                 self.current_panel.refresh_files()
         elif key == ord('7'):
             output_7z = os.path.join(self.current_panel.path, f"{selected}.7z")
             success, message = ArchiveExtractor.compress_to_7z(self.stdscr, self.current_panel.path, selected, output_7z)
             self.show_message(message, 3)
             if success:
                 self.current_panel.refresh_files()
         else:
             self.show_message("Cancelled", 2)


    def get_visible_height(self):
        try:
            h, _ = self.left_win.getmaxyx()
            return max(h - 2, 3)
        except:
            return 5

    def execute_or_enter(self):
        selected = self.current_panel.get_selected()
        if not selected:
            return

        full_path = os.path.join(self.current_panel.path, selected)

        # ===== JIKA FOLDER → MASUK =====
        if os.path.isdir(full_path):
            self.current_panel.enter_directory()
            return

        try:
            ext = os.path.splitext(full_path)[1].lower()

            # Auto chmod script
            if ext in [".py", ".sh"] and not os.access(full_path, os.X_OK):
                os.chmod(full_path, os.stat(full_path).st_mode | 0o111)

            terminal = "xterm"

            if ext == ".py":
                subprocess.Popen(
                    [terminal, "-e", "bash", "-c",
                    f'cd "{os.path.dirname(full_path)}" && python3 "{os.path.basename(full_path)}"; echo; echo "Press Enter to close..."; read'],
                    start_new_session=True,
                )

            elif ext == ".sh":
                subprocess.Popen(
                    [terminal, "-e", "bash", "-c",
                    f'cd "{os.path.dirname(full_path)}" && bash "{os.path.basename(full_path)}"; echo; echo "Press Enter to close..."; read'],
                    start_new_session=True,
                )

            elif ext in [".txt", ".md", ".c", ".cpp", ".h", ".java", ".js", ".html",
                        ".css", ".py", ".json", ".yml", ".yaml", ".xml", ".ini", ".conf"]:
                subprocess.Popen([terminal, "-e", "nano", full_path], start_new_session=True)

            elif ext in [".jpg", ".png", ".jpeg", ".gif", ".webp", ".bmp", ".svg"]:
                if shutil.which("feh"):
                    subprocess.Popen(["feh", full_path], start_new_session=True)
                elif shutil.which("eog"):
                    subprocess.Popen(["eog", full_path], start_new_session=True)
                else:
                    subprocess.Popen(["xdg-open", full_path], start_new_session=True)

            elif ext == ".pdf":
                if shutil.which("evince"):
                    subprocess.Popen(["evince", full_path], start_new_session=True)
                else:
                    subprocess.Popen(["xdg-open", full_path], start_new_session=True)

            elif ext in [".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv"]:
                if shutil.which("mpv"):
                    subprocess.Popen(["mpv", full_path], start_new_session=True)
                elif shutil.which("vlc"):
                    subprocess.Popen(["vlc", full_path], start_new_session=True)
                else:
                    subprocess.Popen(["xdg-open", full_path], start_new_session=True)

            elif ext in [".mp3", ".wav", ".ogg", ".flac"]:
                if shutil.which("mpv"):
                    subprocess.Popen(["mpv", full_path], start_new_session=True)
                else:
                    subprocess.Popen(["xdg-open", full_path], start_new_session=True)

            else:
                if os.access(full_path, os.X_OK):
                    subprocess.Popen(
                        [terminal, "-e", "bash", "-c",
                        f'cd "{os.path.dirname(full_path)}" && "./{os.path.basename(full_path)}"; echo; echo "Press Enter to close..."; read'],
                        start_new_session=True,
                    )
                else:
                    subprocess.Popen(
                        [terminal, "-e", "bash", "-c",
                        f'echo "=== File: {os.path.basename(full_path)} ===" && echo && cat "{full_path}" && '
                        'echo && echo "=== End of file ===" && echo && echo "Press Enter to close..."; read'],
                        start_new_session=True,
                    )

        except Exception as e:
            self.show_message(f"Error executing: {str(e)}", 5)

    def start_search(self):
        self.search_mode = True
        self.search_query = ""

    def exit_program(self):
        self.stdscr.clear()
        self.stdscr.refresh()
        return False

    def handle_search_input(self, key):
        if key == 27:
            self.search_mode = False
            self.current_panel.filter = ""
            self.current_panel.refresh_files()

        elif key in [curses.KEY_BACKSPACE, 127]:
            self.search_query = self.search_query[:-1]
            self.current_panel.filter = self.search_query
            self.current_panel.refresh_files()

        elif key in [10, curses.KEY_ENTER]:
            self.search_mode = False

        elif 32 <= key <= 126:
            self.search_query += chr(key)
            self.current_panel.filter = self.search_query
            self.current_panel.refresh_files()

    def show_message(self, message, duration=3):
        self.message = message
        self.message_timer = duration

    def rename_file(self):
        selected = self.current_panel.get_selected()
        if not selected or selected == "[Permission Denied]":
            self.show_message("Invalid selection", 2)
            return

        old_path = os.path.join(self.current_panel.path, selected)
        height, width = self.stdscr.getmaxyx()

        popup_h = 5
        popup_w = min(50, width - 10)
        popup_y = max(1, height // 2 - popup_h // 2)
        popup_x = max(1, width // 2 - popup_w // 2)

        popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
        popup.border()
        popup.addstr(0, 2, " Rename File ")
        popup.addstr(1, 2, f"Original: {selected[:popup_w-12]}")
        popup.addstr(2, 2, "New name: ")
        popup.refresh()

        input_width = min(40, popup_w - 12)
        input_win = curses.newwin(1, input_width, popup_y + 2, popup_x + 11)
        input_win.addstr(0, 0, selected[:input_width])

        curses.curs_set(1)
        curses.noecho()

        try:
            box = textpad.Textbox(input_win)
            new_name = box.edit().strip()

            if new_name and new_name != selected:
                new_path = os.path.join(self.current_panel.path, new_name)
                try:
                    os.rename(old_path, new_path)
                    self.show_message(f"Renamed to '{new_name[:20]}'", 3)
                    self.current_panel.refresh_files()
                except OSError as e:
                    self.show_message(f"Error: {e.strerror}", 5)

        finally:
            curses.curs_set(0)
            self.stdscr.touchwin()
            self.stdscr.refresh()

    def view_mounts(self):
        paths = []
        for base in ["/mnt", "/media"]:
            if os.path.exists(base):
                for entry in os.listdir(base):
                    full = os.path.join(base, entry)
                    if os.path.ismount(full):
                        paths.append(full)

        height, width = self.stdscr.getmaxyx()
        popup_h = min(20, height - 4)
        popup_w = min(70, width - 4)
        popup_y = max(1, (height - popup_h) // 2)
        popup_x = max(1, (width - popup_w) // 2)

        popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
        popup.border()
        popup.addstr(0, 2, " Mounted in /mnt and /media ")

        if not paths:
            popup.addstr(2, 2, "No mounts found in /mnt or /media.")
        else:
            for i, path in enumerate(paths[:popup_h - 3]):
                popup.addstr(i + 1, 2, path[:popup_w - 4])

        popup.addstr(popup_h - 2, 2, "Press any key to close")
        popup.refresh()
        self.stdscr.getch()
        self.stdscr.touchwin()
        self.stdscr.refresh()

    def extract_zip(self):
        selected = self.current_panel.get_selected()
        if not selected or not selected.endswith('.zip'):
            self.show_message("Select a .zip file first", 2)
            return
        
        success, message = ArchiveExtractor.extract_zip(
            self.stdscr, 
            self.current_panel.path, 
            selected
        )
        self.show_message(message, 3)
        if success:
            self.current_panel.refresh_files()

    def extract_tar_gz(self):
        selected = self.current_panel.get_selected()
        if not selected or not (selected.endswith('.tar.gz') or selected.endswith('.tgz')):
            self.show_message("Select a .tar.gz or .tgz file first", 2)
            return
        
        success, message = ArchiveExtractor.extract_tar_gz(
            self.stdscr,
            self.current_panel.path,
            selected
        )
        self.show_message(message, 3)
        if success:
            self.current_panel.refresh_files()

    def extract_tar_xz(self):
        selected = self.current_panel.get_selected()
        if not selected or not selected.endswith('.tar.xz'):
            self.show_message("Select a .tar.xz file first", 2)
            return
        
        success, message = ArchiveExtractor.extract_tar_xz(
            self.stdscr,
            self.current_panel.path,
            selected
        )
        self.show_message(message, 3)
        if success:
            self.current_panel.refresh_files()

    

    # =====================================================
    #                      MAIN LOOP
    # =====================================================
    def run(self):
        import signal
        
        running = True
        self.needs_full_redraw = True

        def hard_clear_terminal():
            os.system("printf '\\033[2J\\033[H'")

        def on_resize(signum, frame):
            try:
                curses.endwin()
                hard_clear_terminal()
                
                os.system('stty sane 2>/dev/null')
                
                self.stdscr = curses.initscr()
                self.init_ui()
                self.create_windows()
                
                self.left_panel.scroll_offset = 0
                self.right_panel.scroll_offset = 0
                self.needs_full_redraw = True
                
            except Exception as e:
                try:
                    self.stdscr.clear()
                    self.stdscr.refresh()
                    self.needs_full_redraw = True
                except:
                    pass

        signal.signal(signal.SIGWINCH, on_resize)

        try:
            while running:
                try:
                    if self.needs_full_redraw:
                        self.stdscr.erase()
                        self.draw()
                        self.needs_full_redraw = False
                    else:
                        self.draw()

                    running = self.handle_input()
                    
                    curses.napms(50)

                except KeyboardInterrupt:
                    running = False
                    break
                except Exception as e:
                    try:
                        self.stdscr.clear()
                        self.stdscr.addstr(0, 0, f"Loop error: {str(e)[:30]}")
                        self.stdscr.refresh()
                        curses.napms(1000)
                        self.needs_full_redraw = True
                    except:
                        running = False
                        break

        finally:
            try:
                curses.nocbreak()
                self.stdscr.keypad(False)
                curses.echo()
                curses.endwin()
            except:
                pass
            finally:
                os.system('stty sane 2>/dev/null')
                os.system("printf '\\033[?25h' 2>/dev/null")
                os.system("printf '\\033[0m' 2>/dev/null")

        return False
