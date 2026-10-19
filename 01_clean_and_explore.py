"""
Step 1: load, inspect, clean and explore freMTPL2 (French motor third-party liability).

Usage:
    python 01_clean_and_explore.py                 # downloads from OpenML via scikit-learn
    python 01_clean_and_explore.py --csv freMTPL2freq.csv   # use a local copy instead

Outputs (created next to this script):
    outputs/cleaning_log.txt       what was checked and what was changed
    outputs/freq_by_*.csv          claim frequency tables
    outputs/fig_freq_by_*.png      charts
    data/freMTPL2_clean.csv        cleaned data for step 2 (modelling)
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
DATA = HERE / "data"
OUT.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)

# Cleaning choices (change here, and the log updates automatically)
MAX_EXPOSURE = 1.0   # policies are annual, so exposure above 1 year is invalid
MAX_CLAIMS = 4       # cap extreme claim counts (common practice on this dataset)

log_lines = []


def log(msg=""):
    print(msg)
    log_lines.append(str(msg))


# ---------------------------------------------------------------- 1. load
def load(csv_path=None):
    if csv_path:
        df = pd.read_csv(csv_path)
    else:
        from sklearn.datasets import fetch_openml
        df = fetch_openml(data_id=41214, as_frame=True, parser="pandas").frame
    df.columns = [c.strip().replace('"', "") for c in df.columns]
    return df


# ---------------------------------------------------------------- 2. inspect
def inspect(df):
    log("=== RAW DATA ===")
    log(f"Rows: {len(df):,}   Columns: {df.shape[1]}")
    log("\nData types:")
    log(df.dtypes.to_string())
    log("\nMissing values per column:")
    log(df.isna().sum().to_string())
    log(f"\nFully duplicated rows: {df.duplicated().sum():,}")
    if "IDpol" in df.columns:
        log(f"Duplicated policy IDs: {df['IDpol'].duplicated().sum():,}")
    log("\nNumeric summary:")
    log(df.describe().T.to_string())
    log(f"\nExposure <= 0: {(df['Exposure'] <= 0).sum():,}")
    log(f"Exposure > 1 year: {(df['Exposure'] > 1).sum():,}")
    log(f"ClaimNb > {MAX_CLAIMS}: {(df['ClaimNb'] > MAX_CLAIMS).sum():,}")
    log("\nClaim count distribution:")
    log(df["ClaimNb"].value_counts().sort_index().to_string())


# ---------------------------------------------------------------- 3. clean
def clean(df):
    log("\n=== CLEANING ===")
    n0 = len(df)
    df = df.copy()

    # types
    df["ClaimNb"] = df["ClaimNb"].astype(int)
    for c in ["Area", "VehBrand", "VehGas", "Region"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip().astype("category")

    # drop exact duplicates (none expected, but check)
    d = df.duplicated().sum()
    df = df.drop_duplicates()
    log(f"Dropped {d:,} fully duplicated rows")

    # invalid exposure
    bad = df["Exposure"] <= 0
    log(f"Dropped {bad.sum():,} rows with exposure <= 0")
    df = df[~bad]

    # cap exposure
    n_cap_e = (df["Exposure"] > MAX_EXPOSURE).sum()
    df["Exposure"] = df["Exposure"].clip(upper=MAX_EXPOSURE)
    log(f"Capped exposure at {MAX_EXPOSURE} for {n_cap_e:,} rows")

    # cap claims
    n_cap_c = (df["ClaimNb"] > MAX_CLAIMS).sum()
    df["ClaimNb"] = df["ClaimNb"].clip(upper=MAX_CLAIMS)
    log(f"Capped claim count at {MAX_CLAIMS} for {n_cap_c:,} rows")

    # extreme predictor values: cap rather than drop, to keep every policy
    caps = {"VehAge": 20, "DrivAge": 90, "BonusMalus": 150}
    for col, cap in caps.items():
        n = (df[col] > cap).sum()
        df[col] = df[col].clip(upper=cap)
        log(f"Capped {col} at {cap} for {n:,} rows")

    df["LogDensity"] = np.log(df["Density"])
    log("Added LogDensity = log(Density)")

    log(f"\nRows before: {n0:,}   after: {len(df):,}   removed: {n0 - len(df):,}")
    log(f"Total exposure (policy-years): {df['Exposure'].sum():,.1f}")
    log(f"Total claims: {df['ClaimNb'].sum():,}")
    log(f"Baseline frequency (claims / exposure): "
        f"{df['ClaimNb'].sum() / df['Exposure'].sum():.4f}")
    return df


# ---------------------------------------------------------------- 4. explore
def freq_table(df, col, bins=None):
    g = df[col]
    if bins is not None:
        g = pd.cut(g, bins=bins, right=False)
    t = (df.groupby(g, observed=True)
           .agg(policies=("ClaimNb", "size"),
                exposure=("Exposure", "sum"),
                claims=("ClaimNb", "sum")))
    t["frequency"] = t["claims"] / t["exposure"]
    return t


def explore(df):
    log("\n=== CLAIM FREQUENCY BY RISK FACTOR ===")
    specs = {
        "DrivAge": [18, 21, 25, 30, 40, 50, 60, 70, 80, 91],
        "VehAge": [0, 1, 2, 4, 7, 10, 15, 21],
        "VehPower": None,
        "BonusMalus": [50, 55, 60, 70, 80, 90, 100, 120, 151],
        "Area": None,
        "Region": None,
        "VehGas": None,
        "VehBrand": None,
        "LogDensity": 8,  # 8 equal-width bins
    }
    for col, bins in specs.items():
        if col not in df.columns:
            continue
        if isinstance(bins, int):
            bins = np.linspace(df[col].min(), df[col].max() + 1e-9, bins + 1)
        t = freq_table(df, col, bins)
        t.to_csv(OUT / f"freq_by_{col}.csv")
        log(f"\n{col}:")
        log(t.round(4).to_string())

        fig, ax = plt.subplots(figsize=(8, 4))
        x = [str(i) for i in t.index]
        ax.bar(x, t["frequency"])
        ax.axhline(df["ClaimNb"].sum() / df["Exposure"].sum(),
                   color="red", ls="--", label="overall")
        ax.set_ylabel("claims per policy-year")
        ax.set_title(f"Claim frequency by {col}")
        ax.tick_params(axis="x", rotation=60)
        ax.legend()
        fig.tight_layout()
        fig.savefig(OUT / f"fig_freq_by_{col}.png", dpi=150)
        plt.close(fig)

        small = t[t["exposure"] < 500]
        if len(small):
            log(f"  Note: {len(small)} sparse group(s) in {col} with < 500 "
                f"policy-years: {[str(i) for i in small.index]}")


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="path to a local freMTPL2freq CSV")
    args = ap.parse_args()

    raw = load(args.csv)
    inspect(raw)
    cleaned = clean(raw)
    explore(cleaned)

    cleaned.to_csv(DATA / "freMTPL2_clean.csv", index=False)
    (OUT / "cleaning_log.txt").write_text("\n".join(log_lines))
    print(f"\nSaved cleaned data to {DATA / 'freMTPL2_clean.csv'}")
