import re
from pathlib import Path


def find_main_narl_file(folder_path):
    """
    Finds the main NARL data file inside a measurement folder.
    """

    folder = Path(folder_path)

    pattern = re.compile(
        r"^NARL_\d{1,2}_\d{1,2}_\d{4}\.txt$"
    )

    valid_files = [
        file
        for file in folder.glob("NARL*.txt")
        if pattern.match(file.name)
    ]

    if len(valid_files) != 1:
        raise RuntimeError(
            f"Expected exactly one main NARL file in\n{folder}"
        )

    return valid_files[0]