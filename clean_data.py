"""Clean StatCan Table 13-10-0114-01 (complete life tables) into a tidy qx table.

Raw file is read-only; output is data/qx_clean.csv with columns:
period, geo, sex, age, qx
"""
import re
import sys
import pandas as pd

RAW = sys.argv[1] if len(sys.argv) > 1 else "13100114.csv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "data/qx_clean.csv"
QX = "Death probability between age x and x+1 (qx)"

raw = pd.read_csv(RAW, usecols=["REF_DATE", "GEO", "Age group", "Sex", "Element", "VALUE"])
df = raw[raw["Element"] == QX].copy()

df["age"] = df["Age group"].str.extract(r"(\d+)").astype(int)
df = df.rename(columns={"REF_DATE": "period", "GEO": "geo", "Sex": "sex", "VALUE": "qx"})
df = df[["period", "geo", "sex", "age", "qx"]]

# --- checks (documented, not silently fixed) ---
print("rows:", len(df))
print("missing qx:", df["qx"].isna().sum())
print("duplicates:", df.duplicated(["period", "geo", "sex", "age"]).sum())
bad = df[(df["qx"] < 0) | (df["qx"] > 1)]
print("qx outside [0,1]:", len(bad))
print("age range:", df["age"].min(), "-", df["age"].max())

df = df.sort_values(["period", "geo", "sex", "age"]).reset_index(drop=True)
df.to_csv(OUT, index=False)
print("wrote", OUT)
