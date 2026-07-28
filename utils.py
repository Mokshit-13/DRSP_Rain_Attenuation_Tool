import re
from pathlib import Path


def find_main_data_file(folder_path, dataset_mode: str = "current"):
    """
    Finds the main raw attenuation data file inside a measurement folder.

    The naming convention (and therefore the search pattern) depends on
    which dataset generation is being processed. dataset_mode is passed
    in by the caller (ultimately originating from the single selection
    made once in main.py) — this function never asks the user anything.

    dataset_mode == "current"  (2019 onwards)
        Searches only for files matching:  NARL_D_M_YYYY.txt
        e.g. NARL_14_5_2022.txt
        Ignored: NARL_F_*, NARL_N_*, summary files, PNG files.

    dataset_mode == "legacy"  (2017)
        Searches only for files matching:  NAR_D_M_YYYY.txt
        e.g. NAR_14_5_2017.txt
        Ignored: NAR_F_*, NAR_N_*, NAR_Summary_*, PNG files.

    In both modes, exactly ONE matching file must exist in the folder;
    otherwise a descriptive RuntimeError is raised (same behaviour as
    before, just dataset-aware now).
    """

    folder = Path(folder_path)

    if dataset_mode == "legacy":
        glob_pattern = "NAR_*.txt"
        pattern = re.compile(
            r"^NAR_\d{1,2}_\d{1,2}_\d{4}\.txt$"
        )
    else:
        glob_pattern = "NARL_*.txt"
        pattern = re.compile(
            r"^NARL_\d{1,2}_\d{1,2}_\d{4}\.txt$"
        )

    valid_files = [
        file
        for file in folder.glob(glob_pattern)
        if pattern.match(file.name)
    ]

    if len(valid_files) != 1:
        raise RuntimeError(
            f"Expected exactly one main data file in\n{folder}"
        )

    return valid_files[0]
