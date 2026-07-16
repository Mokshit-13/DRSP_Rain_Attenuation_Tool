# DRSP Rain Attenuation Tool

Toolkit for processing NARL radar text data into rain attenuation outputs, quality reports, exceedance statistics, and exploratory plots.

## What this repository does

This project supports end-to-end work on daily/monthly/yearly radar attenuation analysis:

- Convert raw `NARL_*.txt` files into per-second attenuation files and plots
- Batch-process rainy day folders for a full month
- Validate INF values in raw data (single file / month / year)
- Build yearly monthly-exceedance Excel tables
- Extract top attenuation events from processed data
- Visualize raw amplitudes or attenuation interactively

---

## 1) Input data expectations

## Raw file format (core input)

Expected columns in each raw text file:

- `Time` (HH:MM:SS)
- `Amp_Channel-1`
- `Amp_Channel-2`
- `Amp_Channel-3`
- `Amp_Channel-4`

Expected file name pattern:

- `NARL_<day>_<month>_<year>.txt`  
  Example: `NARL_14_5_2022.txt`

## Recommended folder layout

```text
Raw_Data/
└── 2020/
    └── January_2020/
        ├── 07012020 1Hz R/
        │   └── NARL_7_1_2020.txt
        ├── 08012020 1Hz L-R/
        │   └── NARL_8_1_2020.txt
        └── 09012020 1Hz VL-R/
            └── NARL_9_1_2020.txt
```

Rainy day suffixes recognized by batch processing include `R`, `L-R`, `VL-R`.

---

## 2) Installation and dependencies

Use Python 3.10+.

Install required packages:

```bash
pip install pandas numpy matplotlib mplcursors openpyxl tabulate
```

---

## 3) Scenarios (input → processing → output)

## Scenario A — Batch monthly attenuation processing

Script: `main.py` (uses `batch_processor.py` + `analysis_engine.py`)

### Input
- Select one month folder (for example `Raw_Data/2020/January_2020`)
- Inside it, day folders containing raw NARL file

### Processing
- Detect year from parent folder
- Keep only rainy day folders (`R`, `L-R`, `VL-R`)
- For each rainy day:
  - find main NARL file
  - clean time/value formatting
  - normalize to one sample per second if duplicates exist
  - compute per-channel references (top 5%)
  - compute attenuation (`Reference - Amplitude`, clipped at 0)
  - save attenuation text + PNG plot

### Output
For each processed day:

`Processed_Data/<year>/<month>/<day_folder>/`
- `Attenuation_NARL_<d>_<m>_<y>.txt` (tab-delimited, per-second attenuation)
- `Attenuation_NARL_<d>_<m>_<y>.png` (2x2 channel plot)

### Pictorial flow
```text
Month Folder
    │
    ├── Filter rainy day folders
    │
    └── For each day
         ├── Read NARL file
         ├── Clean + normalize (1 Hz)
         ├── Compute references
         ├── Compute attenuation
         └── Save TXT + PNG
```

---

## Scenario B — Single-day attenuation interactive analysis

Script: `Attenuation.py`

### Input
- Select one raw NARL file in file picker

### Processing
- Parse and clean file
- Compute reference levels and attenuation channels
- Show max attenuation values
- Open interactive 2x2 attenuation plot (hover + click markers)

### Output
- Interactive attenuation figure window
- Console summary (references, max attenuation)

### Pictorial flow
```text
Single NARL file
      │
      ├── Parse + convert columns
      ├── Compute references
      ├── Compute attenuation
      └── Display interactive attenuation plots
```

---

## Scenario C — Single-day raw amplitude visualization

Script: `Single_day_plot.py`

### Input
- Select one raw NARL file in file picker

### Processing
- Parse time and amplitude channels
- Compute per-channel statistics (min/max/mean)
- Compute global Y-axis limits
- Open interactive 2x2 amplitude plot

### Output
- Interactive amplitude figure window
- Console statistics for all channels

### Pictorial flow
```text
Single NARL file
      │
      ├── Load amplitude channels
      ├── Compute stats
      ├── Compute shared axis limits
      └── Display interactive amplitude plots
```

---

## Scenario D — INF value validation (data quality)

Scripts: `data_validator.py` and `inf_validator.py`  
(both currently implement INF validation flow)

### Input
Menu modes:
- Single file
- Single month
- Entire year

Then select report format:
- TXT
- Excel (`.xlsx`)

### Processing
- Scan raw file(s)
- Detect timestamps where any amplitude channel is `+inf` or `-inf`
- Deduplicate timestamps per folder
- Aggregate summary counts

### Output
Saved under:

`Processed_Data/Validation_Reports/`
- `INF_Report_<source>.txt`
- `INF_Report_<source>.xlsx`

Includes:
- affected folders
- INF occurrence times
- summary counts

### Pictorial flow
```text
Mode Select (file/month/year)
          │
          ├── Scan NARL datasets
          ├── Find ±inf timestamps
          ├── Summarize counts
          └── Save TXT or XLSX report
```

---

## Scenario E — Yearly monthly exceedance table

Script: `exceedence_engine.py`

### Input
- Select one year folder under processed data  
  (example: `Processed_Data/2020`)

### Processing
- Find all month folders
- Read all `Attenuation_NARL_*.txt`
- For `Att_Channel-3`, count samples above thresholds:
  - lower: `1.00 dB`
  - upper: `58.00 dB`
  - step: `0.10 dB`
- Build month-wise and total exceedance table

### Output
Saved at:

`Processed_Data/Exceedance_Tables/Exceedance_Table_<year>.xlsx`

Sheet: `Monthly Exceedance`

### Pictorial flow
```text
Processed year folder
      │
      ├── Collect monthly attenuation files
      ├── Sweep thresholds (1.00 → 58.00)
      ├── Count Att_Channel-3 exceedances
      └── Save monthly exceedance Excel table
```

---

## Scenario F — Top attenuation values per month

Script: `statistics_engine.py`

### Input
- Select processed-data root folder

### Processing
- Scan month folders
- Read all attenuation files per month
- Extract top 3 highest `Att_Channel-3` values with date/time/file

### Output
- Console table report for each month (ranked top 3 events)

### Pictorial flow
```text
Processed_Data root
      │
      ├── Scan month folders
      ├── Read attenuation files
      ├── Rank top Att_Channel-3 values
      └── Print month-wise top-event report
```

---

## 4) Typical end-to-end workflow

```text
Raw NARL Data
   │
   ├── (Optional) Validate INF values
   │
   ├── Batch monthly processing (main.py)
   │       └── Produces Processed_Data/<year>/<month>/<day>/*.txt + *.png
   │
   ├── Yearly exceedance analysis (exceedence_engine.py)
   │       └── Produces Exceedance_Table_<year>.xlsx
   │
   └── Monthly top-event review (statistics_engine.py)
```

---

## 5) Notes and edge cases

- If folder/file selection is canceled, scripts exit safely.
- Batch processing skips clear-sky day folders without rain suffix.
- Missing or malformed values are coerced and dropped during analysis.
- `statistics_engine.py` and `exceedence_engine.py` depend on outputs generated by batch processing.
- `config.py`, `plotting.py`, and `summary.py` are currently placeholders.

---

## 6) Quick run commands

```bash
python main.py
python Attenuation.py
python Single_day_plot.py
python data_validator.py
python inf_validator.py
python exceedence_engine.py
python statistics_engine.py
```

