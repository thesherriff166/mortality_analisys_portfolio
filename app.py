"""Life Insurance Pricing Explorer (educational illustration).

Run from the repo root:  streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from premium_calculator import level_annual_net_premium, net_single_premium  # noqa: E402

DATA = ROOT / "data" / "qx_clean.csv"
GEO = "Canada"

st.set_page_config(page_title="Life Insurance Pricing Explorer", layout="wide")


@st.cache_data
def load_data():
    df = pd.read_csv(DATA)
    return df[df.geo == GEO]


def qx_series(df, sex, period):
    sub = df[(df.sex == sex) & (df.period == period)]
    return sub.set_index("age")["qx"].sort_index()


df = load_data()
periods = sorted(df.period.unique(), reverse=True)

st.title("Life Insurance Pricing Explorer")
st.caption(
    "Educational illustration. Net premiums from Statistics Canada population life tables "
    "(Table 13-10-0114-01). These are not insurance quotes: no expenses, profit, lapses, taxes "
    "or underwriting, and population mortality is not insured-life mortality."
)

with st.sidebar:
    st.header("Policy inputs")
    sex = st.radio("Sex", ["Males", "Females"], horizontal=True)
    age = st.slider("Issue age", 20, 65, 35)
    benefit = st.select_slider("Death benefit ($)", [100_000, 250_000, 500_000, 1_000_000],
                               value=250_000, format_func=lambda v: f"{v:,}")
    term = st.radio("Term (years)", [10, 15, 20], horizontal=True)
    rate_pct = st.slider("Annual interest rate (%)", 1.0, 7.0, 3.0, 0.5)
    period = st.selectbox("Life table period", periods, index=0)
    st.caption("Three-year period table (a snapshot, not a forecast). "
               "2020/2022 to 2021/2023 windows include COVID-19 years.")

i = rate_pct / 100
qx = qx_series(df, sex, period)

nsp = net_single_premium(qx, age, term, i, benefit)
annual = level_annual_net_premium(qx, age, term, i, benefit)

c1, c2, c3 = st.columns(3)
c1.metric("Net single premium", f"${nsp:,.2f}")
c2.metric("Annual net premium", f"${annual:,.2f}")
c3.metric("Total of annual premiums", f"${annual * term:,.2f}",
          help="Undiscounted, and ignores that payments stop on death.")
st.write(f"{sex[:-1]}, age {age}, {term}-year term, ${benefit:,} benefit, {rate_pct:.1f}% interest, "
         f"Canada {period}.")

tab1, tab2, tab3 = st.tabs(["Mortality", "Sensitivity", "Premium table"])

with tab1:
    fig, ax = plt.subplots(figsize=(8, 4))
    for s in ["Males", "Females"]:
        q = qx_series(df, s, period)
        ax.plot(q.index, q.values, label=s)
    ax.axvspan(age, age + term - 1, alpha=0.12, color="gray", label="Policy ages")
    ax.set(yscale="log", xlabel="Age", ylabel="qx (log scale)", title=f"Probability of death by age, Canada {period}")
    ax.legend(); ax.grid(alpha=0.3)
    st.pyplot(fig)
    st.caption("Describes patterns in the population life table only; it does not imply causation.")

with tab2:
    left, right = st.columns(2)
    ages = list(range(20, 66))
    fig, ax = plt.subplots(figsize=(5.5, 4))
    for n in [10, 15, 20]:
        ax.plot(ages, [level_annual_net_premium(qx, a, n, i, benefit) for a in ages], label=f"{n}-year")
    ax.axvline(age, color="gray", ls="--", lw=1)
    ax.set(xlabel="Issue age", ylabel="Annual net premium ($)", title="By issue age and term")
    ax.legend(); ax.grid(alpha=0.3)
    left.pyplot(fig)

    rates = [r / 100 for r in range(1, 8)]
    fig, ax = plt.subplots(figsize=(5.5, 4))
    ax.plot([r * 100 for r in rates], [level_annual_net_premium(qx, age, term, r, benefit) for r in rates], marker="o")
    ax.set(xlabel="Annual interest rate (%)", ylabel="Annual net premium ($)",
           title=f"Interest-rate sensitivity (age {age}, {term}-year)")
    ax.grid(alpha=0.3)
    right.pyplot(fig)
    st.caption("Premium sensitivity shows how the model responds to inputs, not how accurate it is.")

with tab3:
    rows = []
    for n in [10, 15, 20]:
        for r in [0.01, 0.03, 0.05, 0.07]:
            rows.append({"Term": n, "Interest": f"{r:.0%}",
                         "Net single premium": net_single_premium(qx, age, n, r, benefit),
                         "Annual net premium": level_annual_net_premium(qx, age, n, r, benefit)})
    t = pd.DataFrame(rows)
    st.dataframe(t.style.format({"Net single premium": "${:,.2f}", "Annual net premium": "${:,.2f}"}),
                 hide_index=True, width="stretch")
