from pathlib import Path
import csv
import math
import sys
import tkinter as tk
from tkinter import filedialog

from tabulate import tabulate


# ==============================================================================
# CONFIGURATION
# ==============================================================================

TARGET_CHANNEL      = "Att_Channel-3"    # Only this channel is analyzed
TOP_N               = 3                  # Number of top values to report per month


# ==============================================================================
# FOLDER SELECTION
# ==============================================================================

def select_processed_data_folder() -> str:
    """
    Opens a Windows folder selection dialog and returns the path chosen by
    the user.  If the user cancels or closes the dialog, prints a message
    and exits the program.
    """
    root = tk.Tk()
    root.withdraw()                         # hide the empty root window

    folder_path = filedialog.askdirectory(
        title="Select Processed_Data Folder",
    )

    root.destroy()

    if not folder_path:
        print("No folder selected. Exiting.")
        sys.exit(0)

    return folder_path


# ==============================================================================
# DISCOVERY
# ==============================================================================

def scan_processed_data(root: str):
    """
    Top-level entry point for discovery.

    Returns a sorted list of month folder paths found inside the
    Processed_Data root directory.
    """
    return find_months(root)


def find_months(root: str):
    """
    Returns a sorted list of month folder Paths inside the processed
    data root (e.g. Processed_Data/January_2020, Processed_Data/February_2020).
    """
    root_path = Path(root)

    if not root_path.exists():
        print(f"Warning: '{root_path}' does not exist. Nothing to analyze.")
        return []

    return sorted(
        folder
        for folder in root_path.iterdir()
        if folder.is_dir()
    )


def find_attenuation_files(month_folder):
    """
    Recursively finds every Attenuation_NARL_*.txt file inside a month
    folder (one level down, inside each day folder).

    Returns a sorted list of file Paths.
    """
    month_path = Path(month_folder)

    return sorted(month_path.rglob("Attenuation_NARL_*.txt"))


# ==============================================================================
# ANALYSIS
# ==============================================================================

def analyze_month(month_folder):
    """
    Reads every attenuation file inside a month folder, collects every
    Att_Channel-3 value together with its Date, Time, and source filename,
    and returns the Top N largest values across the entire month.

    Each row of an attenuation file only contains a Time column (HH:MM:SS),
    so the Date is derived from the day folder name (DD-MM-YYYY).

    Returns a list of dicts, sorted descending by attenuation value:
        [{"value": float, "date": str, "time": str, "file": str}, ...]
    """
    month_path = Path(month_folder)
    all_values = []

    attenuation_files = find_attenuation_files(month_path)

    for file_path in attenuation_files:

        # The day folder name (DD-MM-YYYY) is the parent of the file
        date_str = file_path.parent.name

        try:
            with open(file_path, "r", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")

                if TARGET_CHANNEL not in (reader.fieldnames or []):
                    print(
                        f"Warning: '{TARGET_CHANNEL}' column not found in "
                        f"{file_path} — skipping file."
                    )
                    continue

                for row in reader:
                    try:
                        value = float(row[TARGET_CHANNEL])
                        time_str = row.get("Time", "")
                    except (ValueError, KeyError):
                        # Corrupted or malformed row — skip just this row
                        continue

                    # Ignore NaN and +/- infinity — never report invalid values
                    if math.isnan(value) or math.isinf(value):
                        continue

                    all_values.append(
                        {
                            "value": value,
                            "date": date_str,
                            "time": time_str,
                            "file": file_path.name,
                        }
                    )

        except (OSError, csv.Error) as exc:
            print(f"Warning: could not read '{file_path}' ({exc}) — skipping file.")
            continue

    all_values.sort(key=lambda entry: entry["value"], reverse=True)

    return all_values[:TOP_N]


# ==============================================================================
# REPORTING
# ==============================================================================

def print_month_report(month_name: str, top_values: list):
    """
    Prints a clean console report of the Top N attenuation values for a
    single month as a formatted table.
    """
    width = 70

    print("=" * width)
    print(month_name.center(width))
    print("=" * width)

    if not top_values:
        print("No data available for this month.")
        print("=" * width)
        print()
        return

    headers = ["Rank", "Attenuation (dB)", "Date", "Time", "File"]
    rows = [
        [
            rank,
            f"{entry['value']:.2f}",
            entry["date"],
            entry["time"],
            entry["file"],
        ]
        for rank, entry in enumerate(top_values, start=1)
    ]

    print(tabulate(rows, headers=headers, tablefmt="grid"))
    print()


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    processed_data_root = select_processed_data_folder()

    month_folders = scan_processed_data(processed_data_root)

    if not month_folders:
        return

    for month_folder in month_folders:
        top_values = analyze_month(month_folder)
        print_month_report(month_folder.name, top_values)


if __name__ == "__main__":
    main()