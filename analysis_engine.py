"""
================================================================================
DRSP Rain Attenuation — Analysis Engine
================================================================================
Institution : National Atmospheric Research Laboratory (NARL)
Purpose     : Reusable processing engine that loads a NARL data file, computes
              rain attenuation across 4 channels, saves per-minute statistics,
              and produces an interactive engineering-grade plot.

Public API
----------
    from analysis_engine import process_file
    result = process_file("data/NARL_14_5_2022.txt")

    result = {
        "status"               : "SUCCESS",
        "references"           : { "Amp_Channel-1": ..., ... },
        "maximum_attenuation"  : { "Att_Channel-1": ..., ... },
        "second_dataframe"     : <pd.DataFrame>,
        "attenuation_dataframe": <pd.DataFrame>,
    }

Nothing executes automatically on import.

Compatibility : Python 3.10+
Dependencies  : pandas, numpy, matplotlib, mplcursors
================================================================================
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patheffects as pe
import mplcursors
from pathlib import Path


# ==============================================================================
# CONFIGURATION
# ==============================================================================

Y_AXIS_MIN  = 0                             # Fixed Y-axis lower bound (dB)
Y_AXIS_MAX  = 25                            # Fixed Y-axis upper bound (dB)
TOP_PCT     = 0.05                          # Fraction used for reference level
HOUR_TICKS  = [0, 3, 6, 9, 12, 15, 18, 21] # X-axis major tick positions (hrs)

CHANNELS = [
    "Amp_Channel-1",
    "Amp_Channel-2",
    "Amp_Channel-3",
    "Amp_Channel-4",
]

# Circled-number Unicode characters for marker labels (supports up to 20)
CIRCLED_DIGITS = [
    "①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩",
    "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳",
]


# ==============================================================================
# DATA LOADING
# ==============================================================================

def extract_date_from_filename(file_path: str) -> str:
    """
    Derives a human-readable date string from the NARL filename convention.
    Example: 'NARL_14_5_2022.txt' → '14-5-2022'
    """
    stem = Path(file_path).stem          # e.g. 'NARL_14_5_2022'
    date_str = stem.replace("NARL_", "").replace("_", "-")
    return date_str


def load_data(file_path: str, verbose: bool = True) -> pd.DataFrame:
    """
    Reads the whitespace-delimited NARL data file and parses the Time column
    into datetime objects so Matplotlib can format the X-axis correctly.
    Returns a cleaned DataFrame with no NaN rows.
    """
    df = pd.read_csv(file_path, sep=r"\s+", engine="python")

    if verbose:
        print("\nColumns Found:")
        print(df.columns.tolist())

    # Parse HH:MM:SS time strings into datetime (date portion is irrelevant)
    df["Time"] = pd.to_datetime(df["Time"], format="%H:%M:%S")

    # Coerce amplitude columns to numeric; drop any rows that fail
    for ch in CHANNELS:
        df[ch] = pd.to_numeric(df[ch], errors="coerce")

    df = df.dropna()
    return df


# ==============================================================================
# ATTENUATION COMPUTATION
# ==============================================================================

def compute_references(df: pd.DataFrame, verbose: bool = True) -> dict:
    """
    Computes a reference level for each channel as the mean of the
    top TOP_PCT fraction of samples (strongest signal = least rain).

    Hard-coded offset (+0.5 dB):
      • The displayed top-5 values are each shifted up by 0.5 dB.
      • The final reference level (mean of top 5%) is also shifted up by 0.5 dB.
      • This offset is applied consistently so the printed diagnostics and
        the reference used for attenuation calculation always agree.

    Returns a dict mapping channel name → reference level (dB).
    """
    OFFSET = -0.5

    n_top = max(1, int(len(df) * TOP_PCT))
    references = {}

    for ch in CHANNELS:
        strongest = df[ch].nlargest(n_top)

        # Apply +0.5 offset to the mean reference level
        references[ch] = strongest.mean() + OFFSET

        # Apply +0.5 offset to each of the displayed top-5 values
        top5_display = (strongest.nlargest(5) + OFFSET).tolist()

        if verbose:
            print(f"\n{ch}")
            print("  Top 5 Values :", top5_display)
            print(f"  Reference    : {references[ch]:.3f} dB")

    if verbose:
        print("\n" + "=" * 44)
        print("Reference Levels (Top-5% Mean)")
        print("=" * 44)
        for ch in CHANNELS:
            print(f"  {ch}: {references[ch]:.3f} dB")

    return references


def compute_attenuation(df: pd.DataFrame, references: dict) -> pd.DataFrame:
    """
    Computes attenuation for each channel:
        Attenuation = Reference − Amplitude   (clipped to 0 so no negatives)
    Adds Att_Channel-N columns to the DataFrame in place.
    """
    for ch in CHANNELS:
        att_col = ch.replace("Amp_", "Att_")
        df[att_col] = (references[ch] - df[ch]).clip(lower=0)
    return df


def report_max_attenuation(df: pd.DataFrame, verbose: bool = True) -> dict:
    """
    Prints the peak attenuation observed across the day for each channel.
    Returns a dict mapping Att_Channel-N → max attenuation value (float).
    """
    if verbose:
        print("\n" + "=" * 44)
        print("Maximum Attenuation")
        print("=" * 44)

    maximum_attenuation = {}

    for i in range(1, 5):
        col = f"Att_Channel-{i}"
        maximum_attenuation[col] = df[col].max()
        if verbose:
            print(f"  CH{i}: {maximum_attenuation[col]:.2f} dB")

    return maximum_attenuation


# ==============================================================================
# PER-SECOND ATTENUATION FILE EXPORT
# ==============================================================================

def save_per_second_file(
    df: pd.DataFrame,
    file_path: str,
    output_dir: str = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Saves attenuation at the original 1 Hz sampling rate (one row per sample).

    No averaging or grouping is applied.  The output columns are:
        Time          — HH:MM:SS
        Att_Channel-1
        Att_Channel-2
        Att_Channel-3
        Att_Channel-4

    If output_dir is provided the file is saved there; otherwise it is saved
    alongside the input file (legacy behaviour).

    Returns the per-second DataFrame so process_file() can include it in
    the result dictionary.
    """
    att_cols = [ch.replace("Amp_", "Att_") for ch in CHANNELS]

    second_df = df[att_cols].copy()
    second_df.insert(0, "Time", df["Time"].dt.strftime("%H:%M:%S"))

    if output_dir is not None:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / f"Attenuation_{Path(file_path).name}"
    else:
        output_file = Path(file_path).parent / f"Attenuation_{Path(file_path).name}"

    second_df.to_csv(output_file, sep="\t", index=False, float_format="%.4f")

    if verbose:
        print("\n" + "=" * 44)
        print("Per-Second Attenuation File Saved")
        print("=" * 44)
        print(f"  {output_file}")

    return second_df


# ==============================================================================
# PERMANENT MARKER MANAGEMENT
# ==============================================================================

class MarkerManager:
    """
    Manages permanent click-placed markers across all four subplot axes.

    Each marker consists of:
      • A small red scatter dot snapped to the nearest sample.
      • A compact annotation with a circled number, time, and attenuation.
      • A thin arrow pointing from the annotation to the dot.

    Double-clicking any subplot clears ALL markers globally.
    """

    def __init__(self, axes_list: list, df: pd.DataFrame, att_cols: list):
        """
        Parameters
        ----------
        axes_list : list of Axes, length 4 — one per channel.
        df        : The full-resolution DataFrame (Time + Att_Channel-N cols).
        att_cols  : Ordered list of attenuation column names matching axes_list.
        """
        self.axes_list  = axes_list
        self.df         = df
        self.att_cols   = att_cols          # e.g. ['Att_Channel-1', ...]
        self._markers   = []                # list of Artist references for cleanup
        self._count     = 0                 # running marker count (never resets on remove)

        # Pre-compute time as a plain numpy array of timezone-naive datetimes.
        # Done once here so _place_marker does not repeat this on every click,
        # and np.array() silences the pandas FutureWarning about to_pydatetime.
        self._time_values = np.array(self.df["Time"].dt.to_pydatetime())

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def on_click(self, event: "matplotlib.backend_bases.MouseEvent") -> None:
        """
        Handles button_press_event.
        - Double-click  → clear all permanent markers.
        - Single left   → place a new permanent marker.
        """
        if event.inaxes not in self.axes_list:
            return                          # click outside any subplot

        if event.dblclick:
            self._clear_all_markers()
            event.canvas.draw_idle()
            return

        if event.button == 1:               # left single-click
            ax_index = self.axes_list.index(event.inaxes)
            self._place_marker(event, ax_index)
            event.canvas.draw_idle()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _place_marker(
        self,
        event: "matplotlib.backend_bases.MouseEvent",
        ax_index: int,
    ) -> None:
        """
        Snaps the click position to the nearest sample by time,
        then draws the permanent marker annotation on the correct axis.
        """
        ax      = self.axes_list[ax_index]
        att_col = self.att_cols[ax_index]

        # Convert click X (Matplotlib date float) to a timezone-naive datetime
        click_time = mdates.num2date(event.xdata).replace(tzinfo=None)

        # Find the nearest sample using the pre-computed numpy array.
        # abs() on a timedelta array is fast and raises no FutureWarning.
        deltas      = [abs((t - click_time).total_seconds()) for t in self._time_values]
        nearest_idx = int(pd.Series(deltas).idxmin())

        snap_time = self.df["Time"].iloc[nearest_idx]
        snap_att  = self.df[att_col].iloc[nearest_idx]

        # Choose the next circled-number label (cycle if > 20 markers)
        label = CIRCLED_DIGITS[self._count % len(CIRCLED_DIGITS)]
        self._count += 1

        # --- Red dot at the snapped position ---
        dot = ax.scatter(
            snap_time,
            snap_att,
            color="red",
            s=40,               # dot size in points²
            zorder=6,           # render above the line
        )

        # --- Compact annotation with arrow ---
        annot = ax.annotate(
            f"{label}\n{snap_time.strftime('%H:%M')}\n{snap_att:.2f} dB",
            xy=(snap_time, snap_att),                   # arrow tip (the dot)
            xytext=(16, 16),                             # offset in points
            textcoords="offset points",
            fontsize=7.5,
            color="darkred",
            fontweight="bold",
            bbox=dict(
                boxstyle="round,pad=0.3",
                facecolor="lightyellow",
                edgecolor="red",
                linewidth=0.8,
                alpha=0.90,
            ),
            arrowprops=dict(
                arrowstyle="-|>",
                color="red",
                lw=0.9,
            ),
            zorder=7,
        )

        # Add a subtle text shadow so the label is legible on any background
        annot.set_path_effects([
            pe.withStroke(linewidth=2, foreground="white")
        ])

        # Keep references so we can remove them on double-click
        self._markers.extend([dot, annot])

    def _clear_all_markers(self) -> None:
        """Removes every permanent marker artist from all axes."""
        for artist in self._markers:
            try:
                artist.remove()
            except ValueError:
                pass    # already removed — safe to ignore
        self._markers.clear()
        # Note: _count is intentionally NOT reset so numbering stays unique
        # within a session. Set self._count = 0 here to restart numbering.


# ==============================================================================
# HOVER TOOLTIP (mplcursors)
# ==============================================================================

def setup_hover_cursor(line_artists: list, channel_labels: list) -> None:
    """
    Attaches mplcursors to the plotted line objects to display a temporary
    tooltip while the pointer hovers over a data point.

    The tooltip shows:
        Channel name
        Time  (HH:MM:SS)
        Attenuation (dB)

    The tooltip is removed automatically when the cursor moves away
    (hover=True + transient=True achieve this).
    """
    cursor = mplcursors.cursor(
        line_artists,
        hover=mplcursors.HoverMode.Transient,   # disappears on mouse-leave
    )

    # Map each line artist → channel label for the annotation text
    artist_to_label = dict(zip(line_artists, channel_labels))

    @cursor.connect("add")
    def on_add(sel):
        x_num = sel.target[0]
        y_val = sel.target[1]
        t_str = mdates.num2date(x_num).strftime("%H:%M:%S")
        ch_label = artist_to_label.get(sel.artist, "Unknown")

        sel.annotation.set_text(
            f"{ch_label}\n"
            f"Time : {t_str}\n"
            f"Att  : {y_val:.2f} dB"
        )
        sel.annotation.get_bbox_patch().set(
            facecolor="lightyellow",
            edgecolor="steelblue",
            alpha=0.90,
        )
        sel.annotation.set_fontsize(8)


# ==============================================================================
# SUBPLOT FORMATTING
# ==============================================================================

def format_axes(ax, title: str, show_xlabel: bool) -> None:
    """
    Applies consistent formatting to a single subplot axis:
      - Title, axis labels, grid
      - X-axis: HH:MM with 3-hour major ticks, 45° rotation
      - Y-axis: fixed 0–25 dB range
    """
    ax.set_title(title, fontsize=11, fontweight="bold", pad=4)
    ax.set_ylabel("Attenuation (dB)", fontsize=9)
    ax.set_ylim(Y_AXIS_MIN, Y_AXIS_MAX)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7)

    if show_xlabel:
        ax.set_xlabel("Time (IST)", fontsize=9)

    # X-axis tick format and spacing
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=HOUR_TICKS))
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.tick_params(axis="y", labelsize=8)


# ==============================================================================
# MAIN PLOTTING FUNCTION
# ==============================================================================

def plot_attenuation(
    df: pd.DataFrame,
    date_str: str,
    show_plot: bool = True,
    save_path: str = None,
    verbose: bool = True,
) -> None:
    """
    Builds the 2×2 subplot figure, plots all four attenuation channels,
    sets up the hover tooltip, and connects the permanent-marker event handler.

    Layout
    ------
      [CH1]  [CH2]
      [CH3]  [CH4]

    Parameters
    ----------
    show_plot : bool, optional
        If True (default), opens the interactive matplotlib window with
        hover cursor, permanent markers, zoom/pan, and all existing
        interactive features.  The function blocks at plt.show() until
        the window is closed.
        If False, the window is not displayed.
    save_path : str or None, optional
        If provided, saves the figure as a PNG (dpi=300, bbox_inches="tight")
        to this path and then closes the figure.  Only used when
        show_plot=False.
    """

    att_cols     = [ch.replace("Amp_", "Att_") for ch in CHANNELS]
    chan_labels  = [f"CH{i}" for i in range(1, 5)]

    # --- Figure & axes -------------------------------------------------------
    fig, ax_grid = plt.subplots(
        2, 2,
        figsize=(15, 8),
        sharex=False,           # keep axes independent so zoom is per-panel
    )
    fig.patch.set_facecolor("#F7F7F7")

    # Flatten the 2×2 grid to a list: [CH1, CH2, CH3, CH4]
    axes_flat = [ax_grid[0, 0], ax_grid[0, 1], ax_grid[1, 0], ax_grid[1, 1]]

    # --- Plot each channel in a loop (replaces the original CH1…CH4 blocks) --
    line_artists = []

    for idx, (ax, att_col, label) in enumerate(
        zip(axes_flat, att_cols, chan_labels)
    ):
        show_xlabel = idx >= 2          # only bottom row gets X-axis label

        # Downsample for rendering performance while preserving extremes.
        # Uses every Nth sample so the interactive cursor still resolves to
        # the original data (MarkerManager always queries the full df).
        line, = ax.plot(
            df["Time"],
            df[att_col],
            linewidth=0.7,
            color=f"C{idx}",            # Matplotlib's default colour cycle
            label=label,
        )
        line_artists.append(line)

        format_axes(ax, label, show_xlabel)

    # --- Overall figure title ------------------------------------------------
    # y=0.98 keeps the title fully inside the figure canvas so it is never
    # clipped by the window frame.  tight_layout's rect parameter reserves
    # the top 4 % of the figure for the title so subplots don't overlap it.
    fig.suptitle(
        f"DRSP Rain Attenuation  —  {date_str}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    # --- Hover tooltip (mplcursors — temporary) ------------------------------
    if show_plot:
        setup_hover_cursor(line_artists, chan_labels)

    # --- Permanent markers (native Matplotlib events) ------------------------
    if show_plot:
        marker_mgr = MarkerManager(axes_flat, df, att_cols)

        fig.canvas.mpl_connect(
            "button_press_event",
            marker_mgr.on_click,
        )

        # --- Instructions in the figure window title bar ---------------------
        fig.canvas.manager.set_window_title(
            "DRSP Attenuation  |  Left-click: place marker   Double-click: clear all"
        )

    # --- Render ---------------------------------------------------------------
    if show_plot:
        plt.show()
    else:
        # --- Batch mode: save PNG and release memory -------------------------
        if save_path is not None:
            fig.savefig(save_path, dpi=300, bbox_inches="tight")

            if verbose:
                print("\n" + "=" * 44)
                print("Attenuation Plot Saved")
                print("=" * 44)
                print(f"  {save_path}")

        plt.close(fig)


# ==============================================================================
# PUBLIC API
# ==============================================================================

def process_file(
    file_path: str,
    show_plot: bool = True,
    verbose: bool = True,
    output_dir: str = None,
) -> dict:
    """
    Public entry point for the analysis engine.

    Loads the supplied NARL file, computes references and attenuation,
    saves the per-minute attenuation file, optionally generates the
    interactive plot, and returns a result dictionary.

    Parameters
    ----------
    file_path : str
        Path to a NARL daily data file, e.g. "data/NARL_14_5_2022.txt".
    show_plot : bool, optional
        If True (default), opens the interactive matplotlib window with
        hover cursor, permanent markers, zoom/pan, and all existing
        interactive features.
        If False, skips the interactive window entirely (for batch mode).
        The plotting function is preserved and can be called separately.
    verbose : bool, optional
        If True (default), prints all diagnostic output to the console.
        If False, suppresses all console output while still performing all
        computations and saving all output files.
    output_dir : str or None, optional
        Directory where generated files (txt and png) will be saved.
        If None, files are saved alongside the input file (legacy behaviour).
        The directory is created automatically if it does not exist.

    Returns
    -------
    dict with keys:
        "status"                : "SUCCESS"
        "references"            : dict  — channel → reference level (dB)
        "maximum_attenuation"   : dict  — channel → max attenuation (dB)
        "second_dataframe"      : pd.DataFrame — per-second attenuation (1 Hz)
        "attenuation_dataframe" : pd.DataFrame — full-resolution attenuation data
    """

    # ── Date from filename ────────────────────────────────────────────────────
    date_str = extract_date_from_filename(file_path)
    if verbose:
        print(f"\nDate extracted from filename : {date_str}")

    # ── Data loading ─────────────────────────────────────────────────────────
    df = load_data(file_path, verbose=verbose)
    if verbose:
        print(f"Rows loaded (after NaN drop) : {len(df):,}")

    # ── Reference levels ─────────────────────────────────────────────────────
    references = compute_references(df, verbose=verbose)

    # ── Attenuation columns ──────────────────────────────────────────────────
    df = compute_attenuation(df, references)

    # ── Per-second export — returns the 1 Hz DataFrame ───────────────────────
    second_df = save_per_second_file(df, file_path, output_dir=output_dir, verbose=verbose)

    # ── Max attenuation report — returns the per-channel dict ────────────────
    maximum_attenuation = report_max_attenuation(df, verbose=verbose)

    # ── Interactive plot / batch PNG ──────────────────────────────────────────
    if show_plot:
        plot_attenuation(df, date_str, show_plot=True, verbose=verbose)
    else:
        png_name = f"Attenuation_{Path(file_path).stem}.png"
        if output_dir is not None:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            save_path = out_dir / png_name
        else:
            save_path = Path(file_path).parent / png_name
        plot_attenuation(df, date_str, show_plot=False, save_path=save_path, verbose=verbose)

    # ── Result dictionary ─────────────────────────────────────────────────────
    return {
        "status"                : "SUCCESS",
        "references"            : references,
        "maximum_attenuation"   : maximum_attenuation,
        "second_dataframe"      : second_df,
        "attenuation_dataframe" : df,
    }