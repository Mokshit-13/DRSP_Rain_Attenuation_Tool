from pathlib import Path
import re

from utils import find_main_narl_file
from analysis_engine import process_file


# ==============================================================================
# PROGRESS DISPLAY HELPERS
# ==============================================================================

def _progress_bar(current: int, total: int, width: int = 28) -> str:
    """
    Returns a filled/empty progress bar string.
    Example: [████████--------------------]
    """
    filled = int(width * current / total) if total > 0 else 0
    bar    = "█" * filled + "-" * (width - filled)
    pct    = int(100 * current / total) if total > 0 else 0
    return f"[{bar}] {current}/{total} ({pct}%)"


def _date_label(folder_name: str) -> str:
    """
    Attempts to extract a DD-MM-YYYY label from the folder name.
    Falls back to the raw folder name if no date pattern is found.

    Supported patterns (order tried):
        NARL_DD_MM_YYYY   →  DD-MM-YYYY
        YYYY-MM-DD        →  DD-MM-YYYY
        DD-MM-YYYY        →  DD-MM-YYYY  (already correct)
        DD_MM_YYYY        →  DD-MM-YYYY
    """
    # Pattern: NARL_14_5_2022  or  NARL_04_01_2022
    m = re.search(r"NARL_(\d{1,2})_(\d{1,2})_(\d{4})", folder_name)
    if m:
        return f"{m.group(1).zfill(2)}-{m.group(2).zfill(2)}-{m.group(3)}"

    # Pattern: 2022-01-14
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", folder_name)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

    # Pattern: 14-01-2022  or  14_01_2022
    m = re.search(r"(\d{1,2})[-_](\d{1,2})[-_](\d{4})", folder_name)
    if m:
        return f"{m.group(1).zfill(2)}-{m.group(2).zfill(2)}-{m.group(3)}"

    return folder_name


def _is_rainy_folder(folder_name: str) -> bool:
    """
    Returns True if the folder name contains a rain-day suffix.

    Recognised suffixes (case-insensitive):
        R       e.g. "07012020 1Hz R"
        L-R     e.g. "05012020 1Hz L-R"
        VL-R    e.g. "18012020 1Hz VL-R"

    Folders without a recognised suffix are treated as clear-sky and skipped.
    """
    name_upper = folder_name.upper()

    # Check for recognised rain suffixes anywhere in the folder name.
    # Use word-boundary logic: the suffix must appear as a distinct token
    # (preceded by a space) so that plain date strings are not mis-matched.
    for suffix in ("VL-R", "L-R", " R", "-R", 'r', '-r', 'l-r', 'vl-r','L-r', 'Vl-R'):
        if suffix in name_upper:
            return True

    return False



def get_year(month_folder) -> str:
    """
    Determines the year from the selected month folder by walking up to
    its parent (the year folder, e.g. "Raw_Data/2020/January_2020").

    Returns the year as a string, e.g. "2020".
    Falls back to extracting a 4-digit year from the month folder name
    itself if no sensible parent folder name is found.
    """
    month_path  = Path(month_folder)
    parent_name = month_path.parent.name

    if parent_name.isdigit() and len(parent_name) == 4:
        return parent_name

    # Fallback: pull a 4-digit year out of the month folder name
    m = re.search(r"(\d{4})", month_path.name)
    if m:
        return m.group(1)

    return parent_name


def create_output_directory(
    processed_data_root: str,
    year: str,
    month_name: str,
    day_folder_name: str,
) -> Path:
    """
    Builds and creates (if needed) the nested output directory:
        <processed_data_root>/<year>/<month_name>/<day_folder_name>/

    Returns the resulting Path.
    """
    output_dir = Path(processed_data_root) / year / month_name / day_folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir



def _render_display(
    month_name:    str,
    daily_folders: list,
    completed:     list,
    current_label: str | None,
    total:         int,
) -> str:
    """
    Builds the full console block that is printed (then cleared) each tick.
    """
    done  = len(completed)
    lines = []

    lines.append("=" * 57)
    lines.append("DRSP Rain Attenuation Tool")
    lines.append("=" * 57)
    lines.append("")
    lines.append("Processing Month")
    lines.append("")
    lines.append(f"  {month_name}")
    lines.append("")
    lines.append("Progress")
    lines.append("")
    lines.append(f"  {_progress_bar(done, total)}")
    lines.append("")

    # Show last few completed days + current in-progress day
    visible_done = completed[-4:] if len(completed) > 4 else completed
    for label in visible_done:
        lines.append(f"  ✓ {label}")

    if current_label is not None:
        lines.append(f"  ⏳ {current_label}")

    lines.append("")
    lines.append("=" * 57)

    return "\n".join(lines)


def _clear_lines(n: int) -> None:
    """Moves the cursor up n lines and clears each one."""
    for _ in range(n):
        print("\033[A\033[2K", end="")


# ==============================================================================
# PUBLIC API
# ==============================================================================

def process_month(month_folder, processed_data_root: str = "Processed_Data"):
    """
    Parameters
    ----------
    month_folder : str or Path
        Path to the month directory inside the raw data tree
        (e.g. "Raw_Data/2020/January_2020").
    processed_data_root : str, optional
        Root directory for all generated output.  Defaults to
        "Processed_Data" (relative to the current working directory).
        The full output path for each day is:
            <processed_data_root>/<year>/<month_name>/<day_folder_name>/
        The year is detected automatically from the parent of
        month_folder, and both the year and month folders are created
        automatically if they do not already exist.
    """

    month_path = Path(month_folder)
    month_name = month_path.name

    # Year is detected automatically from the raw data folder structure
    year = get_year(month_path)

    daily_folders = sorted(
        [
            folder
            for folder in month_path.iterdir()
            if folder.is_dir()
        ]
    )

    # Keep only folders that carry a recognised rain-day suffix.
    # Clear-sky folders are silently skipped; progress is based solely on
    # the rainy subset so the counter reaches N/N correctly.
    rainy_folders = [
        folder
        for folder in daily_folders
        if _is_rainy_folder(folder.name)
    ]

    total     = len(rainy_folders)
    completed = []
    failed    = []

    # ── Initial render ────────────────────────────────────────────────────────
    display = _render_display(month_name, rainy_folders, completed, None, total)
    print(display)
    last_line_count = display.count("\n") + 1

    for folder in rainy_folders:

        day_label = _date_label(folder.name)

        # Re-render with ⏳ on the current day
        _clear_lines(last_line_count)
        display = _render_display(month_name, rainy_folders, completed, day_label, total)
        print(display)
        last_line_count = display.count("\n") + 1

        # ── Determine output directory for this day ───────────────────────────
        # Structure: Processed_Data/<year>/<month_name>/<day_folder_name>/
        output_dir = create_output_directory(
            processed_data_root, year, month_name, folder.name
        )

        # ── Process the day (silent) ──────────────────────────────────────────
        main_file = find_main_narl_file(folder)
        result    = process_file(
            main_file,
            show_plot=False,
            verbose=False,
            output_dir=str(output_dir),
        )

        if result["status"] == "SUCCESS":
            completed.append(day_label)
        else:
            failed.append(day_label)

        # Re-render with ✓ on the completed day
        _clear_lines(last_line_count)
        display = _render_display(month_name, rainy_folders, completed, None, total)
        print(display)
        last_line_count = display.count("\n") + 1

    # ── Summary ───────────────────────────────────────────────────────────────
    _clear_lines(last_line_count)

    print("=" * 57)
    print()
    print("  Processing Complete")
    print()
    print(f"  Year            : {year}")
    print(f"  Month           : {month_name}")
    print(f"  Rainy days      : {total}")
    print(f"  Successful      : {len(completed)}")
    print(f"  Failed          : {len(failed)}")
    print()
    print("=" * 57)