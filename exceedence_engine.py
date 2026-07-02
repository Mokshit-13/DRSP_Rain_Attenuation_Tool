from pathlib import Path
from datetime import datetime
import csv
import math
import sys
import time
import tkinter as tk
from tkinter import filedialog

from tabulate import tabulate

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter


# ==============================================================================
# CONFIGURATION
# ==============================================================================

TARGET_CHANNEL = "Att_Channel-3"   # Only this channel is analyzed

LOWER_LIMIT = 1.00                 # Lowest threshold (dB)
UPPER_LIMIT = 58.00                # Highest threshold (dB)
STEP_SIZE   = 0.10                 # Threshold step size (dB)

MONTH_ORDER = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


# ==============================================================================
# FOLDER SELECTION
# ==============================================================================

def select_year_folder() -> str:
    """
    Opens a Windows folder selection dialog and returns the path chosen by
    the user (expected to be a Processed_Data/<year> folder).  If the user
    cancels or closes the dialog, prints a message and exits the program.
    """
    root = tk.Tk()
    root.withdraw()                         # hide the empty root window

    folder_path = filedialog.askdirectory(
        title="Select Year Folder",
    )

    root.destroy()

    if not folder_path:
        print("No folder selected. Exiting.")
        sys.exit(0)

    return folder_path


# ==============================================================================
# DISCOVERY
# ==============================================================================

def find_months(year_folder: str):
    """
    Returns a sorted list of month folder Paths inside the selected year
    folder (e.g. Processed_Data/2020/January_2020, .../February_2020).
    """
    year_path = Path(year_folder)

    if not year_path.exists():
        print(f"Warning: '{year_path}' does not exist. Nothing to analyze.")
        return []

    return sorted(
        folder
        for folder in year_path.iterdir()
        if folder.is_dir()
    )


def find_attenuation_files(month_folder):
    """
    Recursively finds every Attenuation_NARL_*.txt file inside a month
    folder (one level down, inside each rainy-day folder).  PNG files are
    ignored entirely.

    Returns a sorted list of file Paths.
    """
    month_path = Path(month_folder)

    return sorted(month_path.rglob("Attenuation_NARL_*.txt"))


def _month_label(month_folder_name: str) -> str:
    """
    Maps a month folder name (e.g. "January_2020") to its short calendar
    name (e.g. "January") used for table grouping and ordering.

    Falls back to the raw folder name if no known month name is found.
    """
    for month in MONTH_ORDER:
        if month_folder_name.lower().startswith(month.lower()):
            return month

    return month_folder_name


# ==============================================================================
# ANALYSIS
# ==============================================================================

def _build_thresholds():
    """
    Builds the list of thresholds from LOWER_LIMIT to UPPER_LIMIT
    (inclusive) in STEP_SIZE increments.  Values are rounded to 2 decimal
    places to avoid floating-point drift.
    """
    thresholds = []
    n_steps = round((UPPER_LIMIT - LOWER_LIMIT) / STEP_SIZE)

    for i in range(n_steps + 1):
        value = LOWER_LIMIT + (i * STEP_SIZE)
        thresholds.append(round(value, 2))

    return thresholds


def _read_channel_values(file_path):
    """
    Reads a single attenuation file and returns a list of valid
    Att_Channel-3 float values (NaN and +/- infinity excluded).

    Skips and warns on unreadable files or missing columns.  Skips
    individual malformed rows without aborting the rest of the file.
    """
    values = []

    try:
        with open(file_path, "r", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")

            if TARGET_CHANNEL not in (reader.fieldnames or []):
                print(
                    f"Warning: '{TARGET_CHANNEL}' column not found in "
                    f"{file_path} — skipping file."
                )
                return values

            for row in reader:
                try:
                    value = float(row[TARGET_CHANNEL])
                except (ValueError, KeyError):
                    # Corrupted or malformed row — skip just this row
                    continue

                if math.isnan(value) or math.isinf(value):
                    continue

                values.append(value)

    except (OSError, csv.Error) as exc:
        print(f"Warning: could not read '{file_path}' ({exc}) — skipping file.")

    return values


def _calculate_month_counts(month_folder, thresholds):
    """
    Computes the exceedance count for a single month, for every threshold.

    Returns a dict: {threshold: exceedance_count}
    """
    month_counts = {t: 0 for t in thresholds}

    attenuation_files = find_attenuation_files(month_folder)

    for file_path in attenuation_files:
        values = _read_channel_values(file_path)

        for threshold in thresholds:
            exceed_count = sum(1 for v in values if v > threshold)
            month_counts[threshold] += exceed_count

    return month_counts


def calculate_monthly_exceedance(year_folder: str, progress_callback=None):
    """
    Scans every month folder inside the year folder and computes, for
    every threshold, the number of 1 Hz samples where
        Att_Channel-3 > Threshold
    separately for each month.

    Parameters
    ----------
    progress_callback : callable, optional
        If provided, called as progress_callback(month_label, month_index,
        total_months) immediately after each month finishes processing,
        so a caller can update a live dashboard.

    Returns
    -------
    thresholds : list of float
        The sorted list of thresholds (LOWER_LIMIT..UPPER_LIMIT).
    month_labels : list of str
        The month names found, in calendar order.
    counts : dict
        Nested dict: counts[month_label][threshold] = exceedance count (int)
    """
    thresholds = _build_thresholds()

    month_folders = find_months(year_folder)

    # Preserve calendar order, but only include months that were found
    found_labels = []
    counts = {}

    total_months = len(month_folders)

    for idx, month_folder in enumerate(month_folders, start=1):
        label = _month_label(month_folder.name)

        if label not in found_labels:
            found_labels.append(label)
            counts[label] = {t: 0 for t in thresholds}

        month_counts = _calculate_month_counts(month_folder, thresholds)

        for threshold in thresholds:
            counts[label][threshold] += month_counts[threshold]

        if progress_callback is not None:
            progress_callback(label, idx, total_months)

    # Sort discovered month labels into calendar order
    month_labels = [m for m in MONTH_ORDER if m in found_labels]
    # Append any unrecognised labels (fallback case) at the end, as found
    month_labels += [m for m in found_labels if m not in MONTH_ORDER]

    return thresholds, month_labels, counts


# ==============================================================================
# TABLE BUILDING & DISPLAY
# ==============================================================================

def build_table(thresholds, month_labels, counts):
    """
    Builds the output table as a list of rows and a list of headers,
    ready to be passed to tabulate().

    Each row:
        [Lower Limit, Upper Limit, <month1 count>, ..., <monthN count>, Total Seconds]
    """
    headers = ["Lower Limit", "Upper Limit"] + month_labels + ["Total Seconds"]

    rows = []

    for threshold in thresholds:
        month_counts = [counts[label][threshold] for label in month_labels]
        total_seconds = sum(month_counts)

        row = [f"{threshold:.2f}", f"{UPPER_LIMIT:.2f}"] + month_counts + [total_seconds]
        rows.append(row)

    return headers, rows


def print_table(headers, rows):
    """
    Prints the exceedance table using tabulate with a grid format.
    """
    print(tabulate(rows, headers=headers, tablefmt="grid"))


def _thin_border() -> Border:
    """Returns a Border object with thin lines on all four sides."""
    side = Side(style="thin")
    return Border(left=side, right=side, top=side, bottom=side)


def _apply_header_style(cell) -> None:
    """Applies bold, centred, light-blue header formatting with a thin border."""
    cell.font      = Font(name="Arial", bold=True, size=10)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.fill      = PatternFill("solid", start_color="BDD7EE")
    cell.border    = _thin_border()


def _apply_data_style(cell) -> None:
    """Applies centred Arial formatting with a thin border to a data cell."""
    cell.font      = Font(name="Arial", size=10)
    cell.alignment = Alignment(horizontal="center", vertical="center")
    cell.border    = _thin_border()


def save_report(
    year: str,
    headers,
    rows,
    output_root: str = "Processed_Data",
) -> Path:
    """
    Writes the exceedance report as a professionally formatted Excel workbook
    (.xlsx) inside <output_root>/Exceedance_Tables/Exceedance_Table_<year>.xlsx

    Worksheet: Monthly Exceedance
    Columns  : Lower Limit (dB) | Upper Limit (dB) | <months...> | Total Seconds
    Formatting:
        • Bold, centre-aligned, light-blue header row
        • Thin borders on every cell
        • Numeric cells stored as numbers (not strings)
        • Auto-adjusted column widths
        • First row frozen

    Creates the Exceedance_Tables folder automatically if it does not exist.
    Returns the full Path of the saved workbook.
    """
    output_dir = Path(output_root) / "Exceedance_Tables"
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / f"Exceedance_Table_{year}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "Monthly Exceedance"

    # ── Build column headers ──────────────────────────────────────────────────
    # Replace plain "Lower Limit" / "Upper Limit" labels with labelled versions
    excel_headers = []
    for h in headers:
        if h == "Lower Limit":
            excel_headers.append("Lower Limit (dB)")
        elif h == "Upper Limit":
            excel_headers.append("Upper Limit (dB)")
        else:
            excel_headers.append(h)

    # Write header row
    for col_idx, label in enumerate(excel_headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=label)
        _apply_header_style(cell)

    # Freeze the header row
    ws.freeze_panes = "A2"

    # ── Write data rows ───────────────────────────────────────────────────────
    for row_idx, row_data in enumerate(rows, start=2):
        for col_idx, value in enumerate(row_data, start=1):
            # Convert threshold strings ("1.00", "1.10" …) to float;
            # leave month counts and Total Seconds as int.
            if col_idx <= 2:                        # Lower / Upper Limit columns
                cell_value = float(value)
            elif col_idx == len(row_data):          # Total Seconds (last column)
                cell_value = int(value)
            else:                                   # Monthly counts
                cell_value = int(value)

            cell = ws.cell(row=row_idx, column=col_idx, value=cell_value)
            _apply_data_style(cell)

            # Format threshold columns to 2 decimal places
            if col_idx <= 2:
                cell.number_format = "0.00"

    # ── Auto-adjust column widths ─────────────────────────────────────────────
    for col_idx, header_label in enumerate(excel_headers, start=1):
        col_letter = get_column_letter(col_idx)

        # Measure the widest content in this column
        max_width = len(header_label)
        for row_idx in range(2, len(rows) + 2):
            cell_val = ws.cell(row=row_idx, column=col_idx).value
            if cell_val is not None:
                max_width = max(max_width, len(str(cell_val)))

        ws.column_dimensions[col_letter].width = max_width + 4   # padding

    wb.save(report_path)
    return report_path


# ==============================================================================
# TERMINAL DASHBOARD
# ==============================================================================

_CLEAR_LINE = "\033[2K"


def _clear_lines(n: int) -> None:
    """Moves the cursor up n lines and clears each one."""
    for _ in range(n):
        print("\033[A" + _CLEAR_LINE, end="")


def _bar(pct: float, width: int = 32) -> str:
    """Returns a filled/empty progress bar string for the given 0-100 pct."""
    filled = int(width * pct / 100)
    return "█" * filled + "-" * (width - filled)


class Dashboard:
    """
    Manages an in-place terminal dashboard for the exceedance engine,
    mirroring the style used in batch_processor.py.
    """

    def __init__(self, year: str):
        self.year = year
        self.scanned_months: list[str] = []
        self.progress_pct = 0
        self.stage = "scanning"   # "scanning" -> "generating" -> "saving" -> "done"
        self.saved_filename = ""
        self._lines_drawn = 0

        self._draw()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def month_scanned(self, month_label: str, idx: int, total: int) -> None:
        self.scanned_months.append(month_label)
        self.progress_pct = int(100 * idx / total) if total > 0 else 100
        self._draw()

    def set_stage(self, stage: str) -> None:
        self.stage = stage
        self._draw()

    def report_saved(self, filename: str) -> None:
        self.saved_filename = filename
        self.stage = "saved"
        self._draw()

    def close(self) -> None:
        self._draw()
        print()  # leave a trailing blank line after the dashboard settles

    # ------------------------------------------------------------------
    # Internal drawing helpers
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        lines = self._build_lines()

        if self._lines_drawn > 0:
            _clear_lines(self._lines_drawn)

        for line in lines:
            print(line)

        self._lines_drawn = len(lines)

    def _build_lines(self) -> list:
        w = 58
        sep = "=" * w

        lines = []
        lines.append(sep)
        lines.append("DRSP Exceedance Statistics Engine")
        lines.append(sep)
        lines.append("")
        lines.append("Selected Year")
        lines.append(f"  {self.year}")
        lines.append("")
        lines.append("Scanning Months")
        for month in self.scanned_months:
            lines.append(f"  \u2713 {month}")
        if not self.scanned_months:
            lines.append("  (none yet)")
        lines.append("")

        if self.stage in ("generating", "saving", "saved"):
            lines.append("Generating Exceedance Table...")
            lines.append("Progress")
            lines.append(f"  [{_bar(self.progress_pct)}] {self.progress_pct}%")
            lines.append("")

        if self.stage in ("saving", "saved"):
            lines.append("Saving Report...")
            if self.stage == "saved":
                lines.append(f"  \u2713 {self.saved_filename}")
            lines.append("")

        lines.append(sep)
        if self.stage == "saved":
            lines.append("Completed Successfully")
            lines.append(sep)

        return lines


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    start_time = time.monotonic()

    year_folder = select_year_folder()
    year = Path(year_folder).name

    dash = Dashboard(year)

    def _on_month_done(month_label, idx, total):
        dash.month_scanned(month_label, idx, total)

    thresholds, month_labels, counts = calculate_monthly_exceedance(
        year_folder, progress_callback=_on_month_done
    )

    if not month_labels:
        dash.close()
        print("No month folders found. Nothing to report.")
        return

    dash.set_stage("generating")
    headers, rows = build_table(thresholds, month_labels, counts)

    dash.set_stage("saving")
    report_path = save_report(year, headers, rows)

    dash.report_saved(report_path.name)
    dash.close()

    elapsed = time.monotonic() - start_time

    print("\u2713 Report saved successfully")
    print()
    print("Location")
    print(f"  {report_path}")
    print()
    print("Rows Generated")
    print(f"  {len(rows)}")
    print()
    print("Thresholds Processed")
    print(f"  {len(thresholds)}")
    print()
    print("Execution Time")
    print(f"  {elapsed:.2f}s")


if __name__ == "__main__":
    main()