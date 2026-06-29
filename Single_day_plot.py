import sys
import tkinter as tk
from tkinter import filedialog
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patheffects as pe
import mplcursors
from pathlib import Path


# ==============
# CONFIGURATION
# ==============

Y_MARGIN    = 2                              # dBm padding above/below data range
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
# FILE SELECTION
# ==============================================================================

def select_narl_file() -> str:
    """
    Opens a Windows file selection dialog and returns the path chosen by the
    user.  Only *.txt files are shown.  If the user cancels or closes the
    dialog, prints a message and exits the program.
    """
    root = tk.Tk()
    root.withdraw()                         # hide the empty root window

    file_path = filedialog.askopenfilename(
        title="Select NARL Data File",
        filetypes=[("Text files", "*.txt")],
    )

    root.destroy()

    if not file_path:
        print("No file selected. Exiting.")
        sys.exit(0)

    return file_path


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


def load_data(file_path: str) -> pd.DataFrame:
    """
    Reads the whitespace-delimited NARL data file and parses the Time column
    into datetime objects so Matplotlib can format the X-axis correctly.
    Returns a cleaned DataFrame with no NaN rows.
    """
    df = pd.read_csv(
        file_path,
        sep=r"\s+",
        names=["Time"] + CHANNELS,
        skiprows=1,
        engine="python",
    )

    print("\nFirst 5 Rows:")
    print(df.head())

    # Parse HH:MM:SS time strings into datetime (date portion is irrelevant)
    df["Time"] = pd.to_datetime(df["Time"], format="%H:%M:%S")

    # Coerce amplitude columns to numeric; drop any rows that fail
    for ch in CHANNELS:
        df[ch] = pd.to_numeric(df[ch], errors="coerce")

    df = df.dropna()
    return df


# ==============================================================================
# STATISTICS REPORT
# ==============================================================================

def report_statistics(df: pd.DataFrame) -> None:
    """Prints max / min / mean amplitude for each channel."""
    print("\n" + "=" * 44)
    print("Channel Statistics")
    print("=" * 44)

    for ch in CHANNELS:
        print(f"\n{ch}")
        print(f"  Maximum : {df[ch].max():.3f} dBm")
        print(f"  Minimum : {df[ch].min():.3f} dBm")
        print(f"  Mean    : {df[ch].mean():.3f} dBm")


# ==============================================================================
# GLOBAL Y-LIMITS
# ==============================================================================

def compute_y_limits(df: pd.DataFrame) -> tuple[float, float]:
    """
    Computes a shared Y-axis range across all four channels so every subplot
    uses the same amplitude scale.  A fixed margin is added top and bottom.
    """
    global_min = df[CHANNELS].min().min() - Y_MARGIN
    global_max = df[CHANNELS].max().max() + Y_MARGIN
    return global_min, global_max


# ==============================================================================
# PERMANENT MARKER MANAGEMENT
# ==============================================================================

class MarkerManager:
    """
    Manages permanent click-placed markers across all four subplot axes.

    Each marker consists of:
      • A small red scatter dot snapped to the nearest sample.
      • A compact annotation with a circled number, time, and amplitude.
      • A thin arrow pointing from the annotation to the dot.

    Double-clicking any subplot clears ALL markers globally.
    """

    def __init__(self, axes_list: list, df: pd.DataFrame):
        """
        Parameters
        ----------
        axes_list : list of Axes, length 4 — one per channel.
        df        : The full-resolution DataFrame (Time + Amp_Channel-N cols).
        """
        self.axes_list = axes_list
        self.df        = df
        self._markers  = []     # list of Artist references for cleanup
        self._count    = 0      # running marker count (never resets on remove)

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
        amp_col = CHANNELS[ax_index]

        # Convert click X (Matplotlib date float) to a timezone-naive datetime
        click_time = mdates.num2date(event.xdata).replace(tzinfo=None)

        # Find the nearest sample using the pre-computed numpy array
        deltas      = [abs((t - click_time).total_seconds()) for t in self._time_values]
        nearest_idx = int(pd.Series(deltas).idxmin())

        snap_time = self.df["Time"].iloc[nearest_idx]
        snap_amp  = self.df[amp_col].iloc[nearest_idx]

        # Choose the next circled-number label (cycle if > 20 markers)
        label = CIRCLED_DIGITS[self._count % len(CIRCLED_DIGITS)]
        self._count += 1

        # --- Red dot at the snapped position ---
        dot = ax.scatter(
            snap_time,
            snap_amp,
            color="red",
            s=40,               # dot size in points²
            zorder=6,           # render above the line
        )

        # --- Compact annotation with arrow ---
        annot = ax.annotate(
            f"{label}\n{snap_time.strftime('%H:%M')}\n{snap_amp:.2f} dBm",
            xy=(snap_time, snap_amp),                   # arrow tip (the dot)
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

        # Subtle text shadow so the label is legible on any background
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
        Amplitude (dBm)

    The tooltip is removed automatically when the cursor moves away
    (HoverMode.Transient achieves this without extra code).
    """
    cursor = mplcursors.cursor(
        line_artists,
        hover=mplcursors.HoverMode.Transient,   # disappears on mouse-leave
    )

    # Map each line artist → channel label for the annotation text
    artist_to_label = dict(zip(line_artists, channel_labels))

    @cursor.connect("add")
    def on_add(sel):
        x_num    = sel.target[0]
        y_val    = sel.target[1]
        t_str    = mdates.num2date(x_num).strftime("%H:%M:%S")
        ch_label = artist_to_label.get(sel.artist, "Unknown")

        sel.annotation.set_text(
            f"{ch_label}\n"
            f"Time : {t_str}\n"
            f"Amp  : {y_val:.2f} dBm"
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

def format_axes(
    ax,
    title: str,
    show_xlabel: bool,
    y_min: float,
    y_max: float,
) -> None:
    """
    Applies consistent formatting to a single subplot axis:
      - Title, axis labels, grid
      - X-axis: HH:MM with 3-hour major ticks, 45° rotation
      - Y-axis: shared global amplitude range
    """
    ax.set_title(title, fontsize=11, fontweight="bold", pad=4)
    ax.set_ylabel("Amplitude (dBm)", fontsize=9)
    ax.set_ylim(y_min, y_max)
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

def plot_amplitudes(
    df: pd.DataFrame,
    date_str: str,
    y_min: float,
    y_max: float,
) -> None:
    """
    Builds the 2×2 subplot figure, plots all four amplitude channels,
    sets up the hover tooltip, and connects the permanent-marker event handler.

    Layout
    ------
      [CH1]  [CH2]
      [CH3]  [CH4]

    The function blocks at plt.show() until the window is closed.
    """

    chan_labels = [f"CH{i}" for i in range(1, 5)]

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

    for idx, (ax, ch, label) in enumerate(
        zip(axes_flat, CHANNELS, chan_labels)
    ):
        show_xlabel = idx >= 2      # only bottom row gets the X-axis label

        line, = ax.plot(
            df["Time"],
            df[ch],
            linewidth=0.7,
            color=f"C{idx}",        # Matplotlib's default colour cycle
            label=label,
        )
        line_artists.append(line)

        format_axes(ax, label, show_xlabel, y_min, y_max)

    # --- Overall figure title ------------------------------------------------
    # y=0.98 keeps the title fully inside the canvas so it is never clipped
    # by the window frame.  tight_layout's rect parameter reserves the top
    # 4 % of the figure for the title so subplots don't overlap it.
    fig.suptitle(
        f"Radar Signal Amplitudes  —  {date_str}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    # --- Hover tooltip (mplcursors — temporary) ------------------------------
    setup_hover_cursor(line_artists, chan_labels)

    # --- Permanent markers (native Matplotlib events) ------------------------
    marker_mgr = MarkerManager(axes_flat, df)

    fig.canvas.mpl_connect(
        "button_press_event",
        marker_mgr.on_click,
    )

    # --- Instructions in the figure window title bar -------------------------
    fig.canvas.manager.set_window_title(
        "DRSP Amplitudes  |  Left-click: place marker   Double-click: clear all"
    )

    # --- Render ---------------------------------------------------------------
    plt.show()


# ==============================================================================
# ENTRY POINT
# ==============================================================================

def main() -> None:
    """
    Orchestrates the full pipeline:
      1. Load raw data.
      2. Report channel statistics.
      3. Compute shared Y-axis limits.
      4. Launch interactive plot.
    """

    # ── File selection ────────────────────────────────────────────────────────
    file_path = select_narl_file()

    # ── Date from filename ────────────────────────────────────────────────────
    date_str = extract_date_from_filename(file_path)
    print(f"\nDate extracted from filename : {date_str}")

    # ── Data loading ─────────────────────────────────────────────────────────
    df = load_data(file_path)
    print(f"Rows loaded (after NaN drop) : {len(df):,}")

    # ── Statistics ───────────────────────────────────────────────────────────
    report_statistics(df)

    # ── Shared Y-axis limits ─────────────────────────────────────────────────
    y_min, y_max = compute_y_limits(df)

    # ── Interactive plot ─────────────────────────────────────────────────────
    plot_amplitudes(df, date_str, y_min, y_max)


if __name__ == "__main__":
    main()