"""
================================================================================
DRSP Rain Attenuation Tool — Data Validator
================================================================================
Standalone utility for inspecting raw NARL data quality.

Scans every daily folder inside a selected month, detects rows where ANY
amplitude column contains +inf or -inf, and prints a clean summary table.

Does NOT modify any files.  Does NOT save any output.  Read-only.
================================================================================
"""

import sys
import math
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

import pandas as pd

from utils import find_main_narl_file


# ==============================================================================
# CONFIGURATION
# ==============================================================================

CHANNELS = [
    "Amp_Channel-1",
    "Amp_Channel-2",
    "Amp_Channel-3",
    "Amp_Channel-4",
]


# ==============================================================================
# FOLDER SELECTION
# ==============================================================================

def select_month_folder() -> str:
    """
    Opens a Windows folder selection dialog and returns the path chosen by
    the user (expected to be a single month folder, e.g. September_2019).
    If the user cancels or closes the dialog, prints a message and exits.
    """
    root = tk.Tk()
    root.withdraw()

    folder_path = filedialog.askdirectory(
        title="Select Month Folder to Validate",
    )

    root.destroy()

    if not folder_path:
        print("No folder selected. Exiting.")
        sys.exit(0)

    return folder_path


# ==============================================================================
# SCANNING
# ==============================================================================

def find_inf_timestamps(file_path) -> list:
    """
    Reads a single raw NARL file and returns a sorted list of HH:MM:SS
    strings where at least one amplitude channel contains +inf or -inf.

    Each timestamp is included only once regardless of how many channels
    are infinite at that moment.

    Returns an empty list if the file cannot be read or contains no inf values.
    """
    try:
        df = pd.read_csv(file_path, sep=r"\s+", engine="python")
    except Exception:
        return []

    # Keep only columns that actually exist
    present = [ch for ch in CHANNELS if ch in df.columns]
    if not present or "Time" not in df.columns:
        return []

    # Convert amplitude columns to numeric, coercing bad strings to NaN
    for ch in present:
        df[ch] = pd.to_numeric(df[ch].astype(str).str.strip(), errors="coerce")

    # Build a mask: True for any row where at least one channel is ±inf
    inf_mask = df[present].apply(
        lambda col: col.apply(lambda v: isinstance(v, float) and math.isinf(v))
    ).any(axis=1)

    if not inf_mask.any():
        return []

    # Extract and deduplicate timestamps from matching rows
    raw_times = df.loc[inf_mask, "Time"].astype(str).str.strip()

    # Extract the HH:MM:SS portion only (ignore trailing characters)
    cleaned = raw_times.str.extract(r"(\d{1,2}:\d{2}:\d{2})", expand=False).dropna()

    return sorted(cleaned.unique().tolist())


def scan_day(day_folder) -> dict:
    """
    Locates the main NARL file inside a daily folder and checks it for
    inf values.

    Returns a dict:
        {
            "folder"     : str   — folder name
            "timestamps" : list  — sorted list of HH:MM:SS strings (may be empty)
            "error"      : str   — error message if file could not be found/read
        }
    """
    day_path = Path(day_folder)
    result = {
        "folder"     : day_path.name,
        "timestamps" : [],
        "error"      : None,
    }

    try:
        main_file = find_main_narl_file(day_path)
        result["timestamps"] = find_inf_timestamps(main_file)
    except Exception as exc:
        result["error"] = str(exc)

    return result


def _progress_bar(current: int, total: int, width: int = 28) -> str:
    """Returns a filled/empty progress bar string."""
    filled = int(width * current / total) if total > 0 else 0
    bar    = "█" * filled + "-" * (width - filled)
    pct    = int(100 * current / total) if total > 0 else 0
    return f"[{bar}] {current}/{total} ({pct}%)"


def _clear_lines(n: int) -> None:
    """Moves the cursor up n lines and clears each one."""
    for _ in range(n):
        print("\033[A\033[2K", end="")


def _render_dashboard(month_name: str, current: int, total: int, current_folder: str) -> str:
    """Builds the in-place dashboard block."""
    lines = [
        "=" * 57,
        "INF Value Validator",
        "=" * 57,
        "",
        "Scanning Month",
        "",
        f"  {month_name}",
        "",
        "Progress",
        "",
        f"  {_progress_bar(current, total)}",
        "",
        f"  \u23f3 {current_folder}",
        "",
        "=" * 57,
    ]
    return "\n".join(lines)


def scan_month(month_folder: str) -> tuple:
    """
    Scans EVERY daily subfolder inside the month folder (rainy and clear-sky).
    Displays an in-place progress dashboard while scanning.

    Returns
    -------
    daily_results : list of dicts from scan_day()
    month_name    : str
    """
    month_path = Path(month_folder)
    month_name = month_path.name

    daily_folders = sorted(
        folder
        for folder in month_path.iterdir()
        if folder.is_dir()
    )

    total = len(daily_folders)
    daily_results = []

    display = _render_dashboard(month_name, 0, total, "")
    print(display)
    last_line_count = display.count("\n") + 1

    for i, folder in enumerate(daily_folders, start=1):
        _clear_lines(last_line_count)
        display = _render_dashboard(month_name, i - 1, total, folder.name)
        print(display)
        last_line_count = display.count("\n") + 1

        daily_results.append(scan_day(folder))

    # Final render showing 100 %
    _clear_lines(last_line_count)
    display = _render_dashboard(month_name, total, total, "Done")
    print(display)

    return daily_results, month_name


# ==============================================================================
# REPORTING
# ==============================================================================

def print_table(daily_results: list, month_name: str) -> None:
    """
    Prints the complete INF validation report to the terminal.
    """
    # Filter to only folders that have inf occurrences
    affected = [r for r in daily_results if r["timestamps"]]

    total_scanned    = len(daily_results)
    total_affected   = len(affected)
    total_occurrences = sum(len(r["timestamps"]) for r in affected)

    width = 62

    print()
    print("=" * width)
    print("INF VALUE VALIDATOR".center(width))
    print("=" * width)
    print()
    print(f"Month : {month_name}")
    print()

    if not affected:
        print("No INF values were found.")
    else:
        # Column widths
        col_no     = 5
        col_folder = 24
        col_times  = 27

        # Header row
        h_no     = "No.".ljust(col_no)
        h_folder = "Day Folder".ljust(col_folder)
        h_times  = "INF Occurrence Times".ljust(col_times)

        row_div  = f"+{'-' * (col_no + 2)}+{'-' * (col_folder + 2)}+{'-' * (col_times + 2)}+"
        hdr_row  = f"| {h_no} | {h_folder} | {h_times} |"

        print(row_div)
        print(hdr_row)

        for idx, result in enumerate(affected, start=1):
            times   = result["timestamps"]
            folder  = result["folder"]

            print(row_div)

            # First time on same row as number + folder
            first_time = times[0] if times else ""
            print(
                f"| {str(idx).ljust(col_no)} "
                f"| {folder[:col_folder].ljust(col_folder)} "
                f"| {first_time.ljust(col_times)} |"
            )

            # Remaining times on continuation rows (blank no. and folder)
            for t in times[1:]:
                print(
                    f"| {''.ljust(col_no)} "
                    f"| {''.ljust(col_folder)} "
                    f"| {t.ljust(col_times)} |"
                )

        print(row_div)

    print()
    print("=" * width)
    print()
    print(f"Total Daily Folders Scanned : {total_scanned}")
    print(f"Folders Containing INF      : {total_affected}")
    print(f"Total INF Occurrences       : {total_occurrences}")
    print()
    print("=" * width)
    print()


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    month_folder = select_month_folder()
    daily_results, month_name = scan_month(month_folder)
    print_table(daily_results, month_name)


if __name__ == "__main__":
    main()