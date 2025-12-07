# archive_extractor.py — VERSI LENGKAP & FINAL (2025)

import os
import zipfile
import tarfile
import py7zr
import curses


class ArchiveExtractor:
    """
    Universal archive extractor & compressor untuk Zeta Manager
    Cukup panggil extract_any() atau compress_any() → semua format otomatis terdeteksi
    """

    # ==================== EKSTRAKSI ====================
    _EXTRACTORS = {
        # format            → (display_name, extractor_lambda)
        '.zip':             ('ZIP',      lambda p, d: zipfile.ZipFile(p).extractall(d)),

        '.tar.gz':          ('TAR.GZ',   lambda p, d: tarfile.open(p, 'r:gz').extractall(d)),
        '.tgz':             ('TAR.GZ',   lambda p, d: tarfile.open(p, 'r:gz').extractall(d)),

        '.tar.xz':          ('TAR.XZ',   lambda p, d: tarfile.open(p, 'r:xz').extractall(d)),
        '.pkg.tar.xz':      ('TAR.XZ',   lambda p, d: tarfile.open(p, 'r:xz').extractall(d)),

        '.tar.bz2':         ('TAR.BZ2',  lambda p, d: tarfile.open(p, 'r:bz2').extractall(d)),
        '.tbz':             ('TAR.BZ2',  lambda p, d: tarfile.open(p, 'r:bz2').extractall(d)),
        '.tbz2':            ('TAR.BZ2',  lambda p, d: tarfile.open(p, 'r:bz2').extractall(d)),

        '.tar':             ('TAR',      lambda p, d: tarfile.open(p, 'r').extractall(d)),

        '.7z':              ('7Z',       lambda p, d: py7zr.SevenZipFile(p).extractall(d)),
    }

    @staticmethod
    def extract_any(stdscr, path: str, filename: str):
        """Satu fungsi → ekstrak semua format yang didukung otomatis"""
        file_path = os.path.join(path, filename)

        # Deteksi format (longest match, case-insensitive)
        extractor_func = None
        display_name = "UNKNOWN"
        matched_ext = ""

        for ext, (name, func) in ArchiveExtractor._EXTRACTORS.items():
            if filename.lower().endswith(ext.lower()):
                if len(ext) > len(matched_ext):  # ambil yang paling panjang
                    extractor_func = func
                    display_name = name
                    matched_ext = ext

        if not extractor_func:
            return False, "Format tidak didukung"

        # Buat nama folder tujuan (buang semua ekstensi yang dikenali)
        dest_name = filename
        for ext in ArchiveExtractor._EXTRACTORS.keys():
            if dest_name.lower().endswith(ext.lower()):
                dest_name = dest_name[:-len(ext)]
        dest_dir = os.path.join(path, dest_name)

        # Popup konfirmasi
        h, w = stdscr.getmaxyx()
        win = curses.newwin(8, 72, h//2 - 4, max(0, w//2 - 36))
        win.border()
        win.addstr(1, 2, f" Extract {display_name} Archive ", curses.A_BOLD)
        win.addstr(3, 2, f"File  → {filename[:62]}")
        win.addstr(4, 2, f"To    → {dest_name[:62]}")
        win.addstr(6, 2, "Press Y to confirm • any other key to cancel")
        win.refresh()

        if stdscr.getch() not in (ord('y'), ord('Y')):
            return False, "Dibatalkan"

        try:
            os.makedirs(dest_dir, exist_ok=True)
            extractor_func(file_path, dest_dir)
            return True, f"Extracted → {dest_name}"
        except Exception as e:
            return False, f"Gagal: {str(e)[:60]}"

    # ==================== KOMPRESI ====================

    @staticmethod
    def compress_any(stdscr, path: str, folder_name: str, format: str = "zip"):
        """Compress folder ke format yang dipilih"""
        format = format.lower().strip()
        folder_path = os.path.join(path, folder_name)

        if not os.path.isdir(folder_path):
            return False, "Folder tidak ditemukan"

        compressors = {
            'zip':     (f"{folder_name}.zip",     ArchiveExtractor.compress_to_zip),
            'tar.gz':  (f"{folder_name}.tar.gz",  ArchiveExtractor.compress_to_tar_gz),
            'tgz':     (f"{folder_name}.tgz",     ArchiveExtractor.compress_to_tar_gz),
            'tar.xz':  (f"{folder_name}.tar.xz",  ArchiveExtractor.compress_to_tar_xz),
            'tar.bz2': (f"{folder_name}.tar.bz2", ArchiveExtractor.compress_to_tar_bz2),
            'tbz2':    (f"{folder_name}.tbz2",    ArchiveExtractor.compress_to_tar_bz2),
            '7z':      (f"{folder_name}.7z",      ArchiveExtractor.compress_to_7z),
        }

        if format not in compressors:
            return False, "Format kompresi tidak didukung"

        output_file, compressor_func = compressors[format]
        output_path = os.path.join(path, output_file)

        try:
            result = compressor_func(stdscr, path, folder_name, output_path)
            return result
        except Exception as e:
            return False, f"Kompresi gagal: {str(e)[:50]}"

    @staticmethod
    def compress_to_zip(stdscr, path, folder_name, output=None):
        output = output or os.path.join(path, f"{folder_name}.zip")
        folder_path = os.path.join(path, folder_name)
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(folder_path):
                for f in files:
                    fp = os.path.join(root, f)
                    arcname = os.path.relpath(fp, folder_path)
                    z.write(fp, arcname)
        return True, f"Compressed → {os.path.basename(output)}"

    @staticmethod
    def compress_to_tar_gz(stdscr, path, folder_name, output=None):
        output = output or os.path.join(path, f"{folder_name}.tar.gz")
        return ArchiveExtractor._compress_tar(path, folder_name, output, 'w:gz')

    @staticmethod
    def compress_to_tar_xz(stdscr, path, folder_name, output=None):
        output = output or os.path.join(path, f"{folder_name}.tar.xz")
        return ArchiveExtractor._compress_tar(path, folder_name, output, 'w:xz')

    @staticmethod
    def compress_to_tar_bz2(stdscr, path, folder_name, output=None):
        output = output or os.path.join(path, f"{folder_name}.tar.bz2")
        return ArchiveExtractor._compress_tar(path, folder_name, output, 'w:bz2')

    @staticmethod
    def _compress_tar(path, folder_name, output_path, mode):
        folder_path = os.path.join(path, folder_name)
        with tarfile.open(output_path, mode) as tar:
            tar.add(folder_path, arcname=os.path.basename(folder_path))
        return True, f"Compressed → {os.path.basename(output_path)}"

    @staticmethod
    def compress_to_7z(stdscr, path, folder_name, output=None):
        output = output or os.path.join(path, f"{folder_name}.7z")
        with py7zr.SevenZipFile(output, 'w') as z:
            z.writeall(os.path.join(path, folder_name), folder_name)
        return True, f"Compressed → {os.path.basename(output)}"

    # ==================== INFO ====================

    @staticmethod
    def get_supported_formats():
        return [
            '.zip', '.tar.gz', '.tgz',
            '.tar.xz', '.pkg.tar.xz',
            '.tar.bz2', '.tbz', '.tbz2',
            '.tar', '.7z'
        ]