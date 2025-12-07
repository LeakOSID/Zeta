import os
import shutil
import curses
from file_manager import FileManager
from config import Config

for root, dirs, files in os.walk(os.path.dirname(__file__)):
    if "__pycache__" in dirs:
        shutil.rmtree(os.path.join(root, "__pycache__"))

def main(stdscr):
    if curses.has_colors():
        curses.start_color()

    config = Config()
    manager = FileManager(stdscr, config)
    manager.run()

if __name__ == "__main__":
    curses.wrapper(main)
