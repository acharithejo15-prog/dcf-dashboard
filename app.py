"""
DCF Valuation & Risk Dashboard
Run with:  streamlit run app.py
"""

import numpy as np
import pandas as pd
import yfinance as yf
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="DCF Valuation Dashboard", layout="wide")
st.title("DCF Valuation & Risk Dashboard")
st.caption("Live data from Yahoo Finance. For educational purposes, not investment advice.")


# ---------------------------------------------------------------
# 1. DATA: pull live market data and financial statements
# ---------------------------------------------------------------
@st.cache_data(ttl=3600)
def load_data(ticker):
    t = yf.Ticker(ticker)
    return t.cashflow, t.info


@st.cache_data(ttl=3600)
def get_risk_free_rate():
    """10-year US Treasury yield (^TNX) as the risk-free rate."""
    try:
        price = yf.Ticker("^TNX").history(period="5d")["Close"].iloc[-1]
        return price / 100
    except Exception:
        return 0.04  # fallback if the data call fails


def get_fcf_history(cf):
    """Free cash flow = operating cash flow - capital expenditures."""
    if "Free Cash Flow" in cf.index:
        return cf.loc["Free Cash Flow"].dropna().sort_index()
    ocf = cf.loc["Operating Cash Flow"]
    capex = cf.loc["Capital Expenditure"]  # reported as a negative number
    return (ocf + capex).dropna().sort_index()


# ---------------------------------------------------------------
# 2. THE DCF MODEL
# ---------------------------------------------------------------
def dcf_value(fcf0, growth, wacc, terminal_g, years, net_debt, shares):
    """Returns fair value per share."""
    flows = [fcf0 * (1 + growth) ** t for t in range(1, years + 1)]
    pv_flows = sum(f / (1 + wacc) ** t for t, f in enumerate(flows, start=1))
    terminal_value = flows[-1] * (1 + terminal_g) / (wacc - terminal_g)
    pv_terminal = terminal_value / (1 + wacc) ** years
    enterprise_value = pv_flows + pv_terminal
    equity_value = enterprise_value - net_debt
    return equity_value / shares


# ---------------------------------------------------------------
# 3. SIDEBAR INPUTS
# ---------------------------------------------------------------
st.sidebar.header("Inputs")
ticker = st.sidebar.text_input("Ticker", "AAPL").upper().strip()

try:
    cf, info = load_data(ticker)
    fcf_hist = get_fcf_history(cf)
except Exception as e:
    st.error(f"Could not load data for {ticker}. Check the ticker and try again. ({e})")
    st.stop()

price = info.get("currentPrice") or info.get("regularMarketPrice")
shares = info.get("sharesOutstanding")
net_debt = (info.get("totalDebt") or 0) - (info.get("totalCash") or 0)
beta = info.get("beta") or 1.0
rf = get_risk_free_rate()
suggested_wacc = rf + beta * 0.05  # CAPM: risk-free + beta * 5% equity risk premium

if not price or not shares or fcf_hist.empty:
    st.error("This ticker is missing price, share count, or cash flow data.")
    st.stop()

fcf0 = float(fcf_hist.iloc[-1])
if fcf0 <= 0:
    st.warning("Latest free cash flow is negative, so a simple DCF will not be meaningful for this company.")

growth = st.sidebar.slider("FCF growth rate (years 1-5)", -0.05, 0.30, 0.08, 0.005, format="%.3f")
wacc = st.sidebar.slider(
    "Discount rate (WACC)", 0.05, 0.15, float(np.clip(round(suggested_wacc, 3), 0.05, 0.15)), 0.005, format="%.3f"
)
terminal_g = st.sidebar.slider("Terminal growth rate", 0.00, 0.04, 0.025, 0.0025, format="%.4f")
years = st.sidebar.slider("Projection years", 3, 10, 5)

if wacc <= terminal_g:
    st.error("WACC must be higher than terminal growth.")
    st.stop()

# ---------------------------------------------------------------
# 4. HEADLINE RESULTS
# ---------------------------------------------------------------
fair_value = dcf_value(fcf0, growth, wacc, terminal_g, years, net_debt, shares)
upside = fair_value / price - 1

st.subheader(f"{info.get('longName', ticker)} ({ticker})")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Current price", f"${price:,.2f}")
c2.metric("DCF fair value", f"${fair_value:,.2f}")
c3.metric("Upside / downside", f"{upside:+.1%}")
c4.metric("Latest FCF", f"${fcf0 / 1e9:,.1f}B")
st.caption(
    f"Risk-free rate (10Y Treasury): {rf:.2%} | Beta: {beta:.2f} | "
    f"CAPM-suggested discount rate: {suggested_wacc:.2%} | Net debt: ${net_debt / 1e9:,.1f}B"
)

# ---------------------------------------------------------------
# 5. SCENARIOS: bear / base / bull
# ---------------------------------------------------------------
st.subheader("Scenario analysis")
scenarios = {
    "Bear": dict(growth=growth - 0.04, wacc=wacc + 0.01, terminal_g=max(terminal_g - 0.005, 0)),
    "Base": dict(growth=growth, wacc=wacc, terminal_g=terminal_g),
    "Bull": dict(growth=growth + 0.04, wacc=max(wacc - 0.01, terminal_g + 0.01), terminal_g=terminal_g + 0.005),
}
rows = []
for name, p in scenarios.items():
    v = dcf_value(fcf0, p["growth"], p["wacc"], p["terminal_g"], years, net_debt, shares)
    rows.append(
        {
            "Scenario": name,
            "Growth": f"{p['growth']:.1%}",
            "WACC": f"{p['wacc']:.1%}",
            "Terminal g": f"{p['terminal_g']:.2%}",
            "Fair value": round(v, 2),
            "vs. price": f"{v / price - 1:+.1%}",
        }
    )
scen_df = pd.DataFrame(rows)

left, right = st.columns([1, 1])
left.dataframe(scen_df, hide_index=True, use_container_width=True)

fig_scen = go.Figure(go.Bar(x=scen_df["Scenario"], y=scen_df["Fair value"], marker_color=["#c0392b", "#7f8c8d", "#27ae60"]))
fig_scen.add_hline(y=price, line_dash="dash", annotation_text="Current price")
fig_scen.update_layout(title="Fair value by scenario", yaxis_title="$ per share", height=320)
right.plotly_chart(fig_scen, use_container_width=True)

# ---------------------------------------------------------------
# 6. SENSITIVITY HEATMAP: WACC vs terminal growth
# ---------------------------------------------------------------
st.subheader("Sensitivity: fair value across WACC and terminal growth")
wacc_range = np.round(np.arange(wacc - 0.02, wacc + 0.0201, 0.005), 4)
tg_range = np.round(np.arange(max(terminal_g - 0.01, 0), terminal_g + 0.0101, 0.005), 4)
grid = pd.DataFrame(index=[f"{w:.1%}" for w in wacc_range], columns=[f"{g:.1%}" for g in tg_range], dtype=float)
for w in wacc_range:
    for g in tg_range:
        if w > g + 0.005:
            grid.loc[f"{w:.1%}", f"{g:.1%}"] = dcf_value(fcf0, growth, w, g, years, net_debt, shares)

fig_heat = px.imshow(
    grid.values,
    x=grid.columns,
    y=grid.index,
    text_auto=".0f",
    color_continuous_scale="RdYlGn",
    aspect="auto",
    labels=dict(x="Terminal growth", y="WACC", color="$/share"),
)
fig_heat.update_layout(height=420)
st.plotly_chart(fig_heat, use_container_width=True)

# ---------------------------------------------------------------
# 7. RISK MODEL: Monte Carlo simulation
# ---------------------------------------------------------------
st.subheader("Risk model: Monte Carlo simulation")
n_sims = st.slider("Number of simulations", 500, 10000, 2000, 500)
rng = np.random.default_rng(42)
g_draws = rng.normal(growth, 0.03, n_sims)
w_draws = rng.normal(wacc, 0.01, n_sims)
t_draws = np.clip(rng.normal(terminal_g, 0.005, n_sims), 0, 0.04)

results = []
for g, w, tg in zip(g_draws, w_draws, t_draws):
    if w > tg + 0.01:
        results.append(dcf_value(fcf0, g, w, tg, years, net_debt, shares))
results = np.array(results)

p5, p50, p95 = np.percentile(results, [5, 50, 95])
prob_undervalued = (results > price).mean()

m1, m2, m3, m4 = st.columns(4)
m1.metric("5th percentile", f"${p5:,.2f}")
m2.metric("Median", f"${p50:,.2f}")
m3.metric("95th percentile", f"${p95:,.2f}")
m4.metric("Probability fair value > price", f"{prob_undervalued:.0%}")

fig_mc = px.histogram(x=results, nbins=60, labels={"x": "Fair value per share ($)"})
fig_mc.add_vline(x=price, line_dash="dash", line_color="red", annotation_text="Current price")
fig_mc.add_vline(x=p50, line_color="black", annotation_text="Median")
fig_mc.update_layout(height=380, showlegend=False)
st.plotly_chart(fig_mc, use_container_width=True)

# ---------------------------------------------------------------
# 8. HISTORICAL FCF
# ---------------------------------------------------------------
st.subheader("Historical free cash flow")
fig_fcf = px.bar(x=fcf_hist.index.year, y=fcf_hist.values / 1e9, labels={"x": "Year", "y": "FCF ($B)"})
fig_fcf.update_layout(height=320)
st.plotly_chart(fig_fcf, use_container_width=True)

with st.expander("How this model works"):
    st.markdown(
        """
        1. Take the latest free cash flow (operating cash flow minus capex).
        2. Project it forward using the growth rate you choose.
        3. Estimate a terminal value with the Gordon Growth formula: FCF x (1+g) / (WACC - g).
        4. Discount everything back to today at the WACC.
        5. Subtract net debt and divide by shares outstanding.
        The Monte Carlo run repeats this thousands of times with randomized assumptions to show a range of outcomes.
        """
    )
