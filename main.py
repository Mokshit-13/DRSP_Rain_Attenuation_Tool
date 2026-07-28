from pathlib import Path

from tkinter import Tk
from tkinter.filedialog import askdirectory

from batch_processor import process_month, get_year, create_output_directory
from analysis_engine import process_file
from utils import find_main_data_file


def select_dataset_mode():
    """
    Displays the dataset-type menu ONCE, at program start, and returns the
    selected mode.

    This is the single source of truth for dataset_mode. Every other
    module (batch_processor.py, utils.py, analysis_engine.py) simply
    receives this value as a parameter — the user is never asked again.

    Returns
    -------
    "current" — 2019-onwards 4-channel NARL dataset
    "legacy"  — 2017 single-channel legacy dataset
    None      — user chose to exit
    """
    while True:
        print("=" * 57)
        print("DRSP Rain Attenuation Tool")
        print("=" * 57)
        print()
        print("Select Dataset Type")
        print()
        print("1. New Dataset (2019 onwards)")
        print("2. Old Dataset")
        print("0. Exit")
        print()
        print("=" * 57)

        choice = input("Enter Choice : ").strip()

        if choice == "1":
            return "current"
        elif choice == "2":
            return "legacy"
        elif choice == "0":
            return None
        else:
            print("\nInvalid choice. Please enter 1, 2, or 0.\n")


def select_processing_mode():
    """
    Displays the processing-mode menu ONCE, right after dataset-mode
    selection, and returns the selected mode.

    processing_mode answers "how should the application behave while
    processing?" and is completely independent of dataset_mode (which
    answers "what type of dataset am I processing?"). Every other module
    (batch_processor.py, analysis_engine.py) simply receives this value
    as a parameter — the user is never asked again.

    Returns
    -------
    "single" — Interactive Single Day (Engineering / Debug Mode)
    "month"  — Process Month (batch, non-interactive)
    "year"   — Process Year (batch, non-interactive)
    None     — user chose to exit
    """
    while True:
        print("=" * 57)
        print("DRSP Rain Attenuation Tool")
        print("=" * 57)
        print()
        print("Select Processing Mode")
        print()
        print("1. Interactive Single Day")
        print("2. Process Month")
        print("3. Process Year")
        print("0. Exit")
        print()
        print("=" * 57)

        choice = input("Enter Choice : ").strip()

        if choice == "1":
            return "single"
        elif choice == "2":
            return "month"
        elif choice == "3":
            return "year"
        elif choice == "0":
            return None
        else:
            print("\nInvalid choice. Please enter 1, 2, 3, or 0.\n")


def select_folder(title: str):

    root = Tk()
    root.withdraw()

    folder = askdirectory(title=title)

    root.destroy()

    return folder


def select_month_folder():
    return select_folder("Select Month Folder")


def process_single_day(day_folder, dataset_mode: str):
    """
    Handles processing_mode == "single".

    Locates the main data file inside the selected day folder, derives the
    year/month from the folder's position in the raw data tree (reusing
    get_year() and create_output_directory() from batch_processor.py so
    the output structure and folder-detection logic are never duplicated),
    and calls process_file() directly with processing_mode="single" so the
    plot is fully interactive (mplcursors, click markers, zoom/pan) exactly
    as it has always worked.
    """
    day_path   = Path(day_folder)
    month_path = day_path.parent
    year       = get_year(month_path)

    output_dir = create_output_directory(
        "Processed_Data", year, month_path.name, day_path.name
    )

    main_file = find_main_data_file(day_path, dataset_mode=dataset_mode)

    result = process_file(
        main_file,
        dataset_mode=dataset_mode,
        processing_mode="single",
        verbose=True,
        output_dir=str(output_dir),
    )

    print()
    print("=" * 57)
    print("  Single Day Processing Complete")
    print(f"  Status : {result['status']}")
    print("=" * 57)


def process_year(year_folder, dataset_mode: str):
    """
    Handles processing_mode == "year".

    Iterates over every month folder inside the selected year folder and
    calls process_month() once per month — exactly as if the user had run
    "Process Month" for each month in turn — forwarding
    processing_mode="year" so plotting stays non-interactive. This does
    not touch process_month()'s own folder traversal, dashboard, or
    progress-bar logic in any way.
    """
    year_path = Path(year_folder)

    month_folders = sorted(
        folder for folder in year_path.iterdir() if folder.is_dir()
    )

    for month_folder in month_folders:
        process_month(
            month_folder,
            dataset_mode=dataset_mode,
            processing_mode="year",
        )


def main():

    dataset_mode = select_dataset_mode()

    if dataset_mode is None:
        print("Exiting.")
        return

    processing_mode = select_processing_mode()

    if processing_mode is None:
        print("Exiting.")
        return

    if processing_mode == "single":
        day_folder = select_folder("Select Day Folder")
        if not day_folder:
            print("No folder selected.")
            return
        process_single_day(day_folder, dataset_mode)

    elif processing_mode == "month":
        month_folder = select_folder("Select Month Folder")
        if not month_folder:
            print("No folder selected.")
            return
        process_month(month_folder, dataset_mode=dataset_mode, processing_mode="month")

    elif processing_mode == "year":
        year_folder = select_folder("Select Year Folder")
        if not year_folder:
            print("No folder selected.")
            return
        process_year(year_folder, dataset_mode)


if __name__ == "__main__":
    main()
