from tkinter import Tk
from tkinter.filedialog import askdirectory

from batch_processor import process_month


def select_month_folder():

    root = Tk()
    root.withdraw()

    folder = askdirectory(
        title="Select Month Folder"
    )

    root.destroy()

    return folder


def main():


    month_folder = select_month_folder()

    if not month_folder:
        print("No folder selected.")
        return

    process_month(month_folder)


if __name__ == "__main__":
    main()