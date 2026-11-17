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

st.set_page_config(page_title="RiskWise DCF", layout="wide")
st.markdown("""
<style>
@keyframes fadeUp {
    from { opacity: 0; transform: translateY(24px); }
    to   { opacity: 1; transform: translateY(0); }
}

h1 {
    animation: fadeUp 0.8s ease-out;
    background: linear-gradient(90deg, #00C48C, #4facfe);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

h2, h3 { animation: fadeUp 1s ease-out; }

[data-testid="stMetric"] {
    background: #1A1F2B;
    border: 1px solid #2A3142;
    border-radius: 12px;
    padding: 16px;
    animation: fadeUp 0.9s ease-out;
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-5px) scale(1.03);
    border-color: #00C48C;
    box-shadow: 0 8px 24px rgba(0, 196, 140, 0.25);
}

[data-testid="stPlotlyChart"] { animation: fadeUp 1.2s ease-out; }

/* Shrink the big text inside metric boxes */
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] * {
    font-size: 1.3rem !important;
    line-height: 1.2 !important;
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
}
</style>
""", unsafe_allow_html=True)
# ---------------- Company search ----------------
POPULAR = {
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL",
    "amazon": "AMZN", "tesla": "TSLA", "nvidia": "NVDA", "meta": "META",
    "facebook": "META", "netflix": "NFLX", "coca cola": "KO", "coca-cola": "KO",
    "pepsi": "PEP", "walmart": "WMT", "nike": "NKE", "disney": "DIS",
    "mcdonalds": "MCD", "mcdonald's": "MCD", "starbucks": "SBUX", "home depot": "HD",
    "at&t": "T", "verizon": "VZ", "intel": "INTC", "amd": "AMD", "costco": "COST",
}


@st.cache_data(ttl=3600)
def search_companies(query):
    """Look up companies by name. Returns a list of (ticker, name, exchange)."""
    out = []
    try:
        for r in yf.Search(query, max_results=10).quotes:
            if r.get("quoteType") == "EQUITY" and r.get("symbol"):
                name = r.get("longname") or r.get("shortname") or r["symbol"]
                out.append((r["symbol"], name, r.get("exchDisp") or r.get("exchange") or ""))
    except Exception:
        pass
    if not out and query.lower() in POPULAR:  # backup if the search service is unavailable
        out.append((POPULAR[query.lower()], query.title(), ""))
    return out

st.title("RiskWise DCF")

# ---------------- Page routing: home vs. analysis ----------------
if "page" not in st.session_state:
    st.session_state.page = "home"
    st.session_state.ticker = None


def go_analysis(t):
    st.session_state.ticker = t
    st.session_state.page = "analysis"


def go_home():
    st.session_state.page = "home"


if st.session_state.page == "home":
    st.markdown(
        '<div style="text-align:center; margin:6px 0 22px 0; color:#9AA4B2; font-size:1.1rem;">'
        "Learn how a company is valued, and why. Type a company below to begin."
        "</div>",
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        q = st.text_input(
            "Company", placeholder="Type a company name or ticker, e.g. Nike, Coca Cola, KO",
            label_visibility="collapsed",
        ).strip()
        found = search_companies(q) if q else []
        if found:
            labels = [f"{n} ({s})" + (f" · {e}" if e else "") for s, n, e in found]
            pick = st.selectbox("Select a match", labels)
            st.button(
                "Analyze →", type="primary", use_container_width=True,
                on_click=go_analysis, args=(found[labels.index(pick)][0],),
            )
        elif q:
            st.caption("No company found by that name. Check the spelling, or try it as a ticker.")
            st.button("Try it as a ticker", on_click=go_analysis, args=(q.upper(),))

        st.markdown("**Or start with an example:**")
        ex_cols = st.columns(4)
        for col, (nm, tk) in zip(ex_cols, [("Apple", "AAPL"), ("Coca-Cola", "KO"), ("Nike", "NKE"), ("Nvidia", "NVDA")]):
            col.button(nm, key=f"ex_{tk}", on_click=go_analysis, args=(tk,), use_container_width=True)

    st.caption("Educational tool using live Yahoo Finance data. Not investment advice.")
    st.stop()
# ---------------- Scrolling ticker tape ----------------
TAPE_SYMBOLS = {
    "^GSPC": "S&P 500", "^DJI": "DOW", "^IXIC": "NASDAQ",
    "AAPL": "AAPL", "MSFT": "MSFT", "NVDA": "NVDA", "AMZN": "AMZN",
    "GOOGL": "GOOGL", "TSLA": "TSLA", "META": "META", "JPM": "JPM", "KO": "KO",
}


@st.cache_data(ttl=300)
def load_tape():
    """Latest price and daily % change for each symbol (refreshes every 5 minutes)."""
    data = yf.download(list(TAPE_SYMBOLS.keys()), period="5d", progress=False)["Close"]
    items = []
    for sym, name in TAPE_SYMBOLS.items():
        try:
            s = data[sym].dropna()
            last, prev = float(s.iloc[-1]), float(s.iloc[-2])
            items.append((name, last, last / prev - 1))
        except Exception:
            continue
    return items


try:
    tape = load_tape()
except Exception:
    tape = []

if tape:
    pieces = []
    for name, last, chg in tape:
        cls = "up" if chg >= 0 else "down"
        arrow = "▲" if chg >= 0 else "▼"
        pieces.append(
            f'<span class="tape-item"><b>{name}</b> {last:,.2f} <span class="{cls}">{arrow} {chg:+.2%}</span></span>'
        )
    tape_html = "".join(pieces)

    st.markdown(
        """
<style>
.tape-wrap { overflow: hidden; background: #0A0E14; border: 1px solid #2A3142;
             border-radius: 8px; padding: 10px 0; margin-bottom: 14px; }
.tape-track { display: inline-flex; white-space: nowrap; animation: tapeScroll 45s linear infinite; }
.tape-wrap:hover .tape-track { animation-play-state: paused; }
.tape-item { padding: 0 28px; font-size: 0.95rem; color: #FAFAFA; }
.tape-item .up { color: #00C48C; font-weight: 600; }
.tape-item .down { color: #FF4B4B; font-weight: 600; }
@keyframes tapeScroll { from { transform: translateX(0); } to { transform: translateX(-50%); } }
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="tape-wrap"><div class="tape-track">{tape_html}{tape_html}</div></div>',
        unsafe_allow_html=True,
    )
st.caption("Live data from Yahoo Finance. For educational purposes, not investment advice.")


# ---------------------------------------------------------------
# 1. DATA: pull live market data and financial statements
# ---------------------------------------------------------------
@st.cache_data(ttl=3600)
def load_data(ticker):
    t = yf.Ticker(ticker)
    return t.cashflow, t.info
@st.cache_data(ttl=3600)
def get_ttm_eps(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        quarterly = stock.quarterly_income_stmt

        if quarterly is None or quarterly.empty:
            return None

        eps_row = None
        for row in ["Diluted EPS", "Basic EPS"]:
            if row in quarterly.index:
                eps_row = row
                break

        if eps_row is None:
            return None

        eps_values = quarterly.loc[eps_row].dropna()

        if len(eps_values) < 4:
            return None

        return float(eps_values.iloc[:4].sum())

    except Exception:
        return None

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


@st.cache_data(ttl=3600)
def load_price_history(ticker):
    """One year of daily price and volume data."""
    return yf.Ticker(ticker).history(period="1y")


# ---------------------------------------------------------------
# 2. THE DCF MODEL
# ---------------------------------------------------------------
def dcf_value(fcf0, growth, wacc, terminal_g, years, net_debt, shares):
    """Returns fair value per share. Growth fades gradually toward terminal growth."""
    flows = []
    fcf = fcf0
    for t in range(1, years + 1):
        g_t = growth + (terminal_g - growth) * (t - 1) / max(years - 1, 1)
        fcf = fcf * (1 + g_t)
        flows.append(fcf)
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


st.sidebar.button("← Back to home", on_click=go_home, use_container_width=True)
ticker = st.session_state.ticker
st.sidebar.markdown(f"**Analyzing: {ticker}**")
try:
    cf, info = load_data(ticker)
    fcf_hist = get_fcf_history(cf)
except Exception as e:
    st.error(f"Could not load data for {ticker}. Check the ticker and try again. ({e})")
    st.stop()

price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
if not price:
    try:
        price = float(yf.Ticker(ticker).history(period="5d")["Close"].dropna().iloc[-1])
    except Exception:
        price = None
shares = info.get("sharesOutstanding")
if not shares:
    try:
        shares = yf.Ticker(ticker).fast_info["shares"]
    except Exception:
        shares = None
net_debt = (info.get("totalDebt") or 0) - (info.get("totalCash") or 0)
beta = info.get("beta") or 1.0
rf = get_risk_free_rate()
erp = st.sidebar.slider(
    "Equity risk premium", 0.03, 0.08, 0.05, 0.005, format="%.3f",
    help="The extra return investors expect for owning stocks instead of safe Treasuries. Historically around 4-6%.",
)
suggested_wacc = rf + beta * erp  # CAPM

if not price or not shares or fcf_hist.empty:
    st.error("This ticker is missing price, share count, or cash flow data.")
    st.stop()

use_avg = st.sidebar.checkbox(
    "Use 3-year average FCF", value=True,
    help="Averages the last three years of free cash flow, so one unusual year does not distort the valuation.",
)
fcf0 = float(fcf_hist.tail(3).mean()) if use_avg else float(fcf_hist.iloc[-1])
if fcf0 <= 0:
    st.warning("Latest free cash flow is negative, so a simple DCF will not be meaningful for this company.")

default_g = 0.06
if len(fcf_hist) >= 3 and fcf_hist.iloc[0] > 0 and fcf_hist.iloc[-1] > 0:
    cagr = (fcf_hist.iloc[-1] / fcf_hist.iloc[0]) ** (1 / (len(fcf_hist) - 1)) - 1
    default_g = float(np.clip(cagr, 0.02, 0.12))
default_g = round(default_g / 0.005) * 0.005

growth = st.sidebar.slider(
    "FCF growth rate (year 1)", -0.05, 0.30, float(default_g), 0.005, format="%.3f",
    help="Starting growth rate. It fades gradually toward the terminal growth rate. The default is based on the company's own past cash flow growth, kept between 2% and 12%.",
)
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
st.toast(f"Loaded {ticker}: fair value ${fair_value:,.2f}", icon="📈")
upside = fair_value / price - 1
# ---------------- Model verdict ----------------
# ---------------- Model verdict ----------------
# Volatility: how much the price has swung over the last year
_h = load_price_history(ticker)
vol, max_dd = None, None
if len(_h) > 60:
    _r = _h["Close"].pct_change().dropna()
    _v = float(_r.std() * np.sqrt(252))  # annualized
    if np.isfinite(_v):
        vol = _v
        max_dd = float((_h["Close"] / _h["Close"].cummax() - 1).min())

if vol is None:
    vol_label, vol_color = "Unknown", "#9AA4B2"
elif vol < 0.20:
    vol_label, vol_color = "Low", "#00C48C"
elif vol < 0.35:
    vol_label, vol_color = "Moderate", "#4facfe"
elif vol < 0.50:
    vol_label, vol_color = "High", "#F5A623"
else:
    vol_label, vol_color = "Very high", "#FF4B4B"

# Bear and bull values (same assumptions as the scenario table)
bear_val = bull_val = None
if fcf0 > 0:
    bear_val = dcf_value(fcf0, growth - 0.04, wacc + 0.01, max(terminal_g - 0.005, 0), years, net_debt, shares)
    bull_val = dcf_value(fcf0, growth + 0.04, max(wacc - 0.01, terminal_g + 0.01), terminal_g + 0.005, years, net_debt, shares)

# Verdict
if fcf0 <= 0:
    label, color, icon = "Model Not Reliable", "#F5A623", "⚠️"
    verdict_text = "This company has negative free cash flow, so a cash flow based DCF cannot produce a meaningful valuation."
elif upside > 0.15:
    label, color, icon = "Model Value Above Price", "#00C48C", "📈"
    verdict_text = (
        f"Based on your assumptions, the model estimates a fair value of ${fair_value:,.2f}, "
        f"about {upside:.0%} above the current price of ${price:,.2f}. "
        f"If the assumptions hold, the stock may be trading below its intrinsic value."
    )
elif upside < -0.15:
    label, color, icon = "Model Value Below Price", "#FF4B4B", "📉"
    verdict_text = (
        f"Based on your assumptions, the model estimates a fair value of ${fair_value:,.2f}, "
        f"about {abs(upside):.0%} below the current price of ${price:,.2f}. "
        f"The market may be pricing in more growth than these assumptions allow."
    )
else:
    label, color, icon = "Model Value Near Price", "#4facfe", "⚖️"
    verdict_text = (
        f"Based on your assumptions, the model estimates a fair value of ${fair_value:,.2f}, "
        f"within about 15% of the current price of ${price:,.2f}. "
        f"The market price is roughly in line with the model."
    )

# Extra sections inside the banner
extra_html = ""

# 1) Potential upside / downside (all verdicts)
if bear_val is not None:
    bear_up = bear_val / price - 1
    bull_up = bull_val / price - 1
    extra_html += (
        '<div style="margin-top:12px; color:#FAFAFA;">'
        '<b>Potential upside / downside:</b> across the bear to bull scenarios, the model\'s fair value ranges from '
        f'${bear_val:,.2f} to ${bull_val:,.2f} per share, which is '
        f'<b style="color:#FF4B4B;">{bear_up:+.0%}</b> to <b style="color:#00C48C;">{bull_up:+.0%}</b> '
        'versus the current price.</div>'
    )

# 2) Margin of safety (fairly valued)
if label == "Model Value Near Price":
    mos = (fair_value - price) / fair_value
    if mos > 0:
        mos_text = f"The current price sits <b>{mos:.1%}</b> below fair value, a small cushion."
    else:
        mos_text = f"The current price sits <b>{abs(mos):.1%}</b> above fair value, so there is <b>no cushion</b> right now."
    extra_html += (
        '<div style="margin-top:12px; padding:10px 14px; background:#0E1117; border-radius:8px; color:#FAFAFA;">'
        '<b>🛡️ Margin of safety:</b> the gap between what a stock is worth and what you pay, which protects you if your estimates are wrong. '
        f'{mos_text} Many value investors wait for a 20% to 30% cushion, which in this case would mean a price of about '
        f'<b>${fair_value * 0.8:,.2f}</b> or lower (20%) or <b>${fair_value * 0.7:,.2f}</b> or lower (30%).</div>'
    )

# 3) Volatility (all verdicts, emphasized)
if vol is not None:
    if fcf0 > 0 and abs(upside) < vol:
        gap_text = (
            f"The valuation gap ({upside:+.0%}) is <b>smaller</b> than this stock's normal yearly swings, "
            "so day-to-day price movement can easily outweigh it."
        )
    elif fcf0 > 0:
        gap_text = (
            f"The valuation gap ({upside:+.0%}) is larger than normal yearly swings, "
            "but the price can still move sharply against you before any gap closes."
        )
    else:
        gap_text = ""
    dd_text = f" Its worst drop from a peak in the past year was <b>{max_dd:.0%}</b>." if max_dd is not None else ""
    extra_html += (
        f'<div style="margin-top:12px; padding:10px 14px; border:1px solid {vol_color}; border-radius:8px; color:#FAFAFA;">'
        f'<b style="color:{vol_color};">⚡ Volatility: {vol_label} ({vol:.0%} per year).</b> '
        f'In a typical year this stock\'s price can swing roughly ±{vol:.0%}.{dd_text} {gap_text}</div>'
    )

st.toast(f"{ticker}: {label}", icon=icon)

st.markdown(
    f'<div style="border-left:6px solid {color}; background:#1A1F2B; padding:16px 20px; border-radius:10px; margin:12px 0;">'
    f'<div style="font-size:1.3rem; font-weight:700; color:{color};">{icon} What the model shows: {label}</div>'
    f'<div style="margin-top:6px; color:#FAFAFA;">{verdict_text}</div>'
    f'{extra_html}'
    '<div style="margin-top:12px; font-size:0.8rem; color:#9AA4B2;">'
    'Educational model output based on the assumptions in the sidebar. Volatility is based on the past year and does not predict the future. '
    'Not investment advice and no guarantee of future results.</div>'
    '</div>',
    unsafe_allow_html=True,
)

st.subheader(f"{info.get('longName', ticker)} ({ticker})")
# ---------------- Sector badge + "About" popup ----------------
SECTOR_STYLE = {
    "Technology": ("#4facfe", "💻", "Companies that make software, chips, hardware, and internet services. Often high growth, but sensitive to interest rates and shifts in technology."),
    "Healthcare": ("#00C48C", "🏥", "Drug makers, biotech, medical devices, and health services. Demand is steady, but results depend on trials, approvals, and regulation."),
    "Financial Services": ("#F5A623", "🏦", "Banks, insurers, asset managers, and payment firms. Earnings are tied to interest rates and the health of the economy."),
    "Consumer Cyclical": ("#E056FD", "🛍️", "Businesses people spend on when times are good, like cars, retail, travel, and restaurants. Rises and falls with the economy."),
    "Consumer Defensive": ("#7BED9F", "🛒", "Everyday essentials like food, drinks, and household goods. Demand holds up in recessions, so growth is usually slower but steadier."),
    "Communication Services": ("#FF6B81", "📡", "Media, entertainment, social platforms, and telecom. Mixes steady subscription income with ad-driven swings."),
    "Industrials": ("#A4B0BE", "🏭", "Manufacturing, aerospace, defense, transport, and construction. Closely tied to business investment and the economic cycle."),
    "Energy": ("#FF7F50", "🛢️", "Oil, gas, and energy services. Profits move with commodity prices, which can swing sharply."),
    "Utilities": ("#70A1FF", "💡", "Electric, gas, and water providers. Regulated and stable, often paying dividends, with limited growth."),
    "Real Estate": ("#FFD32A", "🏢", "Property owners and REITs. Income comes from rent, and values are sensitive to interest rates."),
    "Basic Materials": ("#B8860B", "⛏️", "Miners, chemical makers, and raw-material producers. Moves with commodity prices and global demand."),
}

sector = info.get("sector")
industry = info.get("industry")
summary = info.get("longBusinessSummary")
s_color, s_icon, s_blurb = SECTOR_STYLE.get(sector, ("#9AA4B2", "📊", "Sector information is not available for this company."))

b1, b2 = st.columns([4, 1])
b1.markdown(
    f'<span style="background:{s_color}22; color:{s_color}; border:1px solid {s_color}; '
    f'padding:4px 12px; border-radius:20px; font-weight:600; font-size:0.9rem;">'
    f'{s_icon} {sector or "Sector unknown"}</span>'
    f'<span style="color:#9AA4B2; margin-left:10px; font-size:0.9rem;">{industry or ""}</span>',
    unsafe_allow_html=True,
)


def about_content():
    st.markdown(
        f'<div style="border-left:5px solid {s_color}; padding:6px 12px; margin-bottom:10px;">'
        f'<b style="color:{s_color};">{s_icon} {sector or "Sector unknown"}</b><br>'
        f'<span style="font-size:0.9rem;">{s_blurb}</span></div>',
        unsafe_allow_html=True,
    )
    if summary:
        cut = summary[:650]
        if len(summary) > 650:
            cut = cut[: cut.rfind(".") + 1] or cut + "..."
        st.write(cut)
    else:
        st.write("No business description is available for this company.")

    mcap = info.get("marketCap")
    emp = info.get("fullTimeEmployees")
    site = info.get("website")
    facts = []
    if mcap:
        facts.append(f"**Market cap:** ${mcap / 1e9:,.1f}B")
    if emp:
        facts.append(f"**Employees:** {emp:,}")
    if info.get("country"):
        facts.append(f"**Country:** {info['country']}")
    if site:
        facts.append(f"**Website:** {site}")
    if facts:
        st.markdown("  \n".join(facts))


if hasattr(st, "popover"):
    with b2.popover("ℹ️ About"):
        about_content()
else:
    with st.expander("ℹ️ About this company"):
        about_content()
        if sector in ("Financial Services", "Real Estate"):st.warning(
        f"**Heads up:** a free-cash-flow DCF works poorly for {sector.lower()} companies. "
        "Banks, insurers, and REITs have cash flows that don't mean the same thing, so treat this number as a "
        "teaching example, not a reliable valuation."
    )

tab_overview, tab_learn, tab_risk, tab_sent = st.tabs(
    ["📊 Overview", "🎓 Learn", "🎲 Risk", "💬 Sentiment"]
)
tab_overview.__enter__()
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
# PRICE CHART with selectable time range
# ---------------------------------------------------------------
RANGES = {
    "1D": ("1d", "5m"),
    "1W": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"),
    "YTD": ("ytd", "1d"),
    "1Y (TTM)": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
    "Max": ("max", "1mo"),
}


@st.cache_data(ttl=300)
def load_chart_data(ticker, period, interval):
    return yf.Ticker(ticker).history(period=period, interval=interval)


st.subheader(
    "Price chart",
    help="Choose a time range to see how the stock has moved. Green means the price is up over the selected period, red means it is down. 1D shows the most recent trading day. TTM means 'trailing twelve months', the last year.",
)

ctl1, ctl2, ctl3 = st.columns([4, 2, 2])
choice = ctl1.radio("Time range", list(RANGES.keys()), index=6, horizontal=True, label_visibility="collapsed")
chart_type = ctl2.radio("Chart type", ["Line", "Candlestick"], horizontal=True, label_visibility="collapsed")
show_fv = ctl3.checkbox("Show DCF fair value", value=False)

period, interval = RANGES[choice]
px_data = load_chart_data(ticker, period, interval)

if px_data.empty:
    st.info("No price data available for this range.")
else:
    start_px = float(px_data["Close"].iloc[0])
    end_px = float(px_data["Close"].iloc[-1])
    change = end_px / start_px - 1
    line_color = "#00C48C" if change >= 0 else "#FF4B4B"

    s1, s2, s3 = st.columns(3)
    s1.metric(f"Change ({choice})", f"{change:+.2%}")
    s2.metric("Period high", f"${px_data['High'].max():,.2f}")
    s3.metric("Period low", f"${px_data['Low'].min():,.2f}")

    fig_price = go.Figure()
    if chart_type == "Line":
        fig_price.add_trace(
            go.Scatter(
                x=px_data.index, y=px_data["Close"], mode="lines", name="Price",
                line=dict(color=line_color, width=2),
                fill="tozeroy", fillcolor="rgba(0,196,140,0.06)" if change >= 0 else "rgba(255,75,75,0.06)",
                hovertemplate="$%{y:,.2f}<extra></extra>",
            )
        )
    else:
        fig_price.add_trace(
            go.Candlestick(
                x=px_data.index,
                open=px_data["Open"], high=px_data["High"], low=px_data["Low"], close=px_data["Close"],
                increasing_line_color="#00C48C", decreasing_line_color="#FF4B4B", name="Price",
            )
        )
    if show_fv:
        fig_price.add_hline(y=fair_value, line_dash="dash", line_color="#4facfe", annotation_text="DCF fair value")

    if choice != "1D":
        fig_price.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])  # hide weekend gaps

    hover_fmt = "%b %d, %I:%M %p" if choice in ("1D", "1W") else "%b %d, %Y"
    fig_price.update_xaxes(
        showspikes=True, spikemode="across", spikethickness=1, spikedash="dot",
        spikecolor="#9AA4B2", spikesnap="cursor", hoverformat=hover_fmt, fixedrange=True,
    )
    fig_price.update_yaxes(
        showspikes=True, spikemode="across", spikethickness=1, spikedash="dot",
        spikecolor="#9AA4B2", spikesnap="cursor", fixedrange=True, tickprefix="$",
    )
    fig_price.update_layout(
        height=420, template="plotly_dark",
        hovermode="x unified", dragmode=False,
        xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10),
        hoverlabel=dict(bgcolor="#1A1F2B", font_size=13),
    )
    st.plotly_chart(
        fig_price, use_container_width=True,
        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False},
    )
    # ---------------------------------------------------------------
# LATEST NEWS
# ---------------------------------------------------------------
import html as _html


@st.cache_data(ttl=900)
def load_news(ticker, limit=3):
    """Latest headlines for a ticker (refreshes every 15 minutes)."""
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        return []

    items = []
    for n in raw:
        c = n.get("content", n)  # newer yfinance nests data under "content"
        title = c.get("title")
        link = (
            (c.get("canonicalUrl") or {}).get("url")
            or (c.get("clickThroughUrl") or {}).get("url")
            or n.get("link")
        )
        provider = c.get("provider")
        publisher = provider.get("displayName") if isinstance(provider, dict) else n.get("publisher")

        when = None
        if c.get("pubDate"):
            when = pd.to_datetime(c["pubDate"], utc=True)
        elif n.get("providerPublishTime"):
            when = pd.to_datetime(n["providerPublishTime"], unit="s", utc=True)

        if title and link:
            items.append({"title": title, "link": link, "publisher": publisher or "News", "when": when})
        if len(items) >= limit:
            break
    return items


def time_ago(ts):
    if ts is None:
        return ""
    secs = (pd.Timestamp.now(tz="UTC") - ts).total_seconds()
    if secs < 3600:
        return f"{max(int(secs // 60), 1)} min ago"
    if secs < 86400:
        return f"{int(secs // 3600)} hr ago"
    return f"{int(secs // 86400)} days ago"


st.subheader(
    f"Latest news on {ticker}",
    help="Recent headlines about this company from news outlets, so you can see what may be moving the stock. Headlines are not analyzed or endorsed by this tool, and they are not investment advice.",
)

news_items = load_news(ticker)
if not news_items:
    st.info("No recent news found for this ticker.")
else:
    for item in news_items:
        st.markdown(
            f"""
            <a href="{_html.escape(item['link'])}" target="_blank" style="text-decoration:none;">
              <div style="border-left:5px solid #4facfe; background:#1A1F2B; padding:12px 16px;
                          border-radius:10px; margin-bottom:10px;">
                <div style="color:#FAFAFA; font-weight:600; font-size:1rem;">{_html.escape(item['title'])}</div>
                <div style="color:#9AA4B2; font-size:0.8rem; margin-top:4px;">
                  {_html.escape(item['publisher'])} · {time_ago(item['when'])} ↗
                </div>
              </div>
            </a>
            """,
            unsafe_allow_html=True,
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
tab_overview.__exit__(None, None, None)
tab_risk.__enter__()
# ---------------------------------------------------------------
# 7. RISK MODEL: Monte Carlo simulation
# ---------------------------------------------------------------
st.subheader(
    "Risk model: Monte Carlo simulation",
    help="""
**What is this?**
Nobody can know exactly how fast a company will grow or what return investors will demand in the future. So instead of calculating one answer, this tool calculates thousands of answers, each using slightly different, randomly chosen assumptions.

**How do I read the chart?**
Each bar shows how many of the runs ended up at that stock value. Tall bars mean that value is more likely. The red dashed line is today's stock price.

**What should I look for?**
- If most of the bars sit to the **right** of the red line, the model thinks the stock is worth more than its price.
- If most sit to the **left**, it suggests the stock may be overpriced.
- A **narrow** chart means the valuation is stable. A **wide** chart means the answer is very sensitive to the assumptions, so treat it with caution.

This is a stress test of the assumptions, not a prediction of the future.
""",
)
n_sims = st.slider(
    "Number of simulations",
    500, 10000, 2000, 500,
    help="How many times the model is re-run with slightly different assumptions. More runs give a smoother, more reliable picture, but the overall conclusion should stay about the same. 2,000 to 5,000 is plenty.",
)
rng = np.random.default_rng(42)
g_draws = rng.normal(growth, 0.03, n_sims)
w_draws = rng.normal(wacc, 0.01, n_sims)
t_draws = np.clip(rng.normal(terminal_g, 0.005, n_sims), 0, 0.04)

w_draws = np.maximum(w_draws, t_draws + 0.01)  # keep WACC above terminal growth
results = np.array([
    dcf_value(fcf0, g, w, tg, years, net_debt, shares)
    for g, w, tg in zip(g_draws, w_draws, t_draws)
])

p5, p50, p95 = np.percentile(results, [5, 50, 95])
prob_undervalued = (results > price).mean()

m1, m2, m3, m4 = st.columns(4)
m1.metric("5th percentile", f"${p5:,.2f}",
          help="A pessimistic outcome. Only 5 out of every 100 runs gave a value lower than this.")
m2.metric("Median", f"${p50:,.2f}",
          help="The middle result. Half of the runs gave a higher value and half gave a lower one.")
m3.metric("95th percentile", f"${p95:,.2f}",
          help="An optimistic outcome. Only 5 out of every 100 runs gave a value higher than this.")
m4.metric("Probability fair value > price", f"{prob_undervalued:.0%}",
          help="The share of runs where the model's value came out higher than today's stock price. Near 50% means it's roughly a coin flip. Much higher suggests the stock may be undervalued, and much lower suggests it may be overvalued.")

fig_mc = px.histogram(x=results, nbins=60, labels={"x": "Fair value per share ($)"})
fig_mc.add_vline(x=price, line_dash="dash", line_color="red", annotation_text="Current price")
fig_mc.add_vline(x=p50, line_color="black", annotation_text="Median")
fig_mc.update_layout(height=380, showlegend=False)
st.plotly_chart(fig_mc, use_container_width=True)
tab_risk.__exit__(None, None, None)
tab_sent.__enter__()
# ---------------------------------------------------------------
# 7b. MARKET SENTIMENT: what investors think
# ---------------------------------------------------------------
st.subheader(
    "Market sentiment: what investors think",
    help="""
**What is this?**
"Hype" is how excited or worried the market is about a stock right now. This section measures it using real data: recent price momentum, Wall Street analyst ratings, analyst price targets, and how many investors are betting against the stock (short interest).

**How is the score made?**
Each signal is scored from negative (pessimistic) to positive (optimistic) and averaged into a 0 to 100 score. 50 is neutral.

**Why compare it to the valuation?**
Hype tells you what people *feel*. The DCF tells you what the cash flows *support*. When they disagree, it's worth a closer look. Strong hype with a high price can mean expectations are running ahead of fundamentals. Weak sentiment with a low price can mean the stock is out of favor.

**Important:** popular stocks can keep rising or fall hard. Sentiment is not a prediction.
""",
)

hist = load_price_history(ticker)
signals = []  # list of (name, score from -1 to +1, description)

# Signal 1: 3-month price momentum
r1 = r3 = r6 = None
if len(hist) > 130:
    close = hist["Close"]
    r1 = close.iloc[-1] / close.iloc[-21] - 1
    r3 = close.iloc[-1] / close.iloc[-63] - 1
    r6 = close.iloc[-1] / close.iloc[-126] - 1
    signals.append(("Price momentum", float(np.clip(r3 / 0.30, -1, 1)), f"{r3:+.1%} over 3 months"))

# Signal 2: analyst rating (1 = strong buy, 5 = sell)
rec_mean = info.get("recommendationMean")
n_analysts = info.get("numberOfAnalystOpinions")
if rec_mean:
    signals.append(("Analyst rating", float(np.clip((3 - rec_mean) / 2, -1, 1)), f"{rec_mean:.1f} out of 5 (1 = strong buy)"))

# Signal 3: analyst average price target vs. current price
target = info.get("targetMeanPrice")
if target and price:
    t_up = target / price - 1
    signals.append(("Analyst price target", float(np.clip(t_up / 0.30, -1, 1)), f"{t_up:+.1%} vs. current price"))

# Signal 4: short interest (investors betting against the stock)
short_pct = info.get("shortPercentOfFloat")
if short_pct is not None:
    signals.append(("Short interest", float(-np.clip(short_pct / 0.10, 0, 1)), f"{short_pct:.1%} of shares sold short"))

# Attention (not scored, since a volume spike can be good or bad news)
vol_ratio = None
if len(hist) > 63:
    vol_ratio = hist["Volume"].tail(5).mean() / hist["Volume"].tail(63).mean()

# Drop any signal whose data came back blank (NaN)
signals = [s for s in signals if np.isfinite(s[1])]

if not signals:
    st.info("Not enough sentiment data is available for this ticker.")
else:
    hype_score = (np.mean([s[1] for s in signals]) + 1) * 50  # 0 to 100

    if hype_score >= 65:
        h_label, h_color, h_icon = "High optimism", "#00C48C", "🔥"
    elif hype_score >= 35:
        h_label, h_color, h_icon = "Mixed sentiment", "#4facfe", "😐"
    else:
        h_label, h_color, h_icon = "Pessimistic", "#FF4B4B", "🧊"

    # Metrics row
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Hype score", f"{hype_score:.0f} / 100",
              help="Average of the signals below. 50 is neutral, above 65 is high optimism, below 35 is pessimistic.")
    k2.metric("Sentiment", f"{h_icon} {h_label}")
    k3.metric("Analyst opinions", f"{n_analysts}" if n_analysts else "N/A",
              help="How many Wall Street analysts cover this stock. More analysts means the consensus is more meaningful.")
    k4.metric("Trading attention", f"{vol_ratio:.1f}x" if vol_ratio and np.isfinite(vol_ratio) else "N/A",
              help="Trading volume over the last 5 days compared to the 3-month average. Well above 1x means unusual attention, which often follows big news.")

    # Signal breakdown
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Signal": n,
                    "Reading": d,
                    "Leaning": "Optimistic" if s > 0.15 else ("Pessimistic" if s < -0.15 else "Neutral"),
                }
                for n, s, d in signals
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
   
# ---------- IMPROVED P/E AND EPS CALCULATIONS ----------

def clean_num(value):
    """Convert Yahoo Finance data into a valid number."""
    try:
        value = float(value)
        return value if np.isfinite(value) else None
    except (TypeError, ValueError):
        return None


# Retrieve Yahoo Finance values
pe_t = clean_num(info.get("trailingPE"))
eps_t = clean_num(info.get("trailingEps"))

# Retrieve forward estimates from Yahoo Finance
try:
    stock = yf.Ticker(ticker)
    eps_f = clean_num(stock.info.get("forwardEps"))
    pe_f = clean_num(stock.info.get("forwardPE"))
except Exception:
    eps_f = None
    pe_f = None
# Retrieve forward estimates from Yahoo Finance
eps_f = clean_num(info.get("forwardEps"))
pe_f = clean_num(info.get("forwardPE"))

# Fallback: analyst consensus for next year, if Yahoo's main field is empty
if eps_f is None:
    try:
        est = yf.Ticker(ticker).earnings_estimate
        eps_f = clean_num(est.loc["+1y", "avg"])
    except Exception:
        eps_f = None
# BACKUP 1: Calculate trailing EPS from quarterly statements
if eps_t is None:
    eps_t = get_ttm_eps(ticker)

# BACKUP 2: Calculate trailing P/E using current stock price
if pe_t is None and eps_t is not None and eps_t > 0:
    pe_t = price / eps_t

# BACKUP 3: Calculate forward P/E if forward EPS exists
if pe_f is None and eps_f is not None and eps_f > 0:
    pe_f = price / eps_f

# Display earnings metrics
st.markdown("### Earnings and valuation multiples")

e1, e2, e3, e4 = st.columns(4)

# Trailing P/E
if pe_t is not None and pe_t > 0:
    pe_t_display = f"{pe_t:.2f}x"
else:
    pe_t_display = "N/M" if eps_t is not None and eps_t <= 0 else "N/A"

# Forward P/E
if pe_f is not None and pe_f > 0:
    pe_f_display = f"{pe_f:.2f}x"
else:
    pe_f_display = "N/M" if eps_f is not None and eps_f <= 0 else "N/A"

# Trailing EPS
eps_t_display = (
    f"${eps_t:,.2f}" if eps_t is not None else "N/A"
)

# Forward EPS
eps_f_display = (
    f"${eps_f:,.2f}" if eps_f is not None else "N/A"
)

e1.metric("P/E ratio (trailing)", pe_t_display)
e2.metric("P/E ratio (forward)", pe_f_display)
e3.metric("EPS (trailing)", eps_t_display)
e4.metric("EPS (forward estimate)", eps_f_display)

# Explain the results
if eps_t is not None and eps_t > 0:
    st.success(
        f"Investors are paying ${pe_t:.2f} for every $1 "
        f"of trailing annual earnings."
        if pe_t is not None
        else f"Trailing EPS is ${eps_t:.2f}."
    )

elif eps_t is not None and eps_t <= 0:
    st.warning(
        "The company currently has zero or negative earnings. "
        "A positive P/E ratio is not meaningful."
    )

if eps_t is not None and eps_f is not None and eps_t > 0:
    earnings_growth = eps_f / eps_t - 1

    st.write(
        f"Expected EPS growth: {earnings_growth:+.2%}"
    )

st.caption(
    "Trailing EPS uses the last 12 months of earnings. "
    "Forward EPS uses analyst estimates when available. "
    "P/E is calculated using current share price and EPS."
)

if signals:
    if fcf0 <= 0:
        v_text = "The DCF is not reliable for this company (negative free cash flow), so sentiment can't be compared to valuation."
        v_color = "#F5A623"
    elif hype_score >= 65 and upside < -0.15:
        v_text = ("**Hype is ahead of the numbers.** Investors are optimistic, but the price is above the model's fair value. "
                  "The market may be expecting more growth than these assumptions allow.")
        v_color = "#FF4B4B"
    elif hype_score >= 65 and upside > 0.15:
        v_text = ("**Sentiment and valuation agree.** Investors are optimistic and the model also sees room above the current price.")
        v_color = "#00C48C"
    elif hype_score < 35 and upside > 0.15:
        v_text = ("**Out of favor, but the model sees value.** Sentiment is weak while the price looks low versus fair value. "
                  "This can mean an overlooked stock, or that the market sees risks the model doesn't capture.")
        v_color = "#4facfe"
    elif hype_score < 35 and upside < -0.15:
        v_text = ("**Both signals are negative.** Investors are pessimistic and the model also sees the price above fair value.")
        v_color = "#FF4B4B"
    else:
        v_text = ("**No strong disagreement.** Sentiment and valuation are not sending a clear conflicting or confirming message.")
        v_color = "#4facfe"

    st.markdown(
        f"""
        <div style="border-left: 6px solid {v_color}; background: #1A1F2B;
                    padding: 16px 20px; border-radius: 10px; margin: 12px 0;">
            <div style="font-size: 1.1rem; font-weight: 700; color: {v_color};">Hype vs. valuation</div>
            <div style="margin-top: 6px; color: #FAFAFA;">{v_text}</div>
            <div style="margin-top: 8px; font-size: 0.8rem; color: #9AA4B2;">
                Educational output from public data. Sentiment can change quickly and is not a prediction
                or investment advice.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Price chart with the DCF fair value for context
    if len(hist) > 0:
        fig_px = go.Figure()
        fig_px.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Price", line=dict(color="#4facfe")))
        fig_px.add_trace(go.Scatter(x=hist.index, y=hist["Close"].rolling(50).mean(), name="50-day average",
                                    line=dict(color="#F5A623", width=1, dash="dot")))
        fig_px.add_hline(y=fair_value, line_dash="dash", line_color="#00C48C", annotation_text="DCF fair value")
        fig_px.update_layout(title="1-year price vs. DCF fair value", yaxis_title="$ per share", height=360, template="plotly_dark")
        st.plotly_chart(fig_px, use_container_width=True)
        # ---------------------------------------------------------------
# ---------------------------------------------------------------
# LEARN: why is this stock valued this way?
# ---------------------------------------------------------------
def money(x):
    return f"\\${x:,.2f}"  # escaped so Streamlit doesn't treat $ as math


def dcf_breakdown(fcf0, growth, wacc, terminal_g, years):
    """Splits enterprise value into 'next few years of cash' vs. 'everything after'."""
    flows, fcf = [], fcf0
    for t in range(1, years + 1):
        g_t = growth + (terminal_g - growth) * (t - 1) / max(years - 1, 1)
        fcf *= 1 + g_t
        flows.append(fcf)
    pv_flows = sum(f / (1 + wacc) ** t for t, f in enumerate(flows, start=1))
    tv = flows[-1] * (1 + terminal_g) / (wacc - terminal_g)
    pv_tv = tv / (1 + wacc) ** years
    return pv_flows, pv_tv


def implied_growth(target_price):
    """Reverse DCF: what year-1 growth would justify today's price? (bisection)"""
    lo, hi = -0.30, 0.60
    if not (dcf_value(fcf0, lo, wacc, terminal_g, years, net_debt, shares)
            <= target_price
            <= dcf_value(fcf0, hi, wacc, terminal_g, years, net_debt, shares)):
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if dcf_value(fcf0, mid, wacc, terminal_g, years, net_debt, shares) < target_price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


st.header(
    "Learn: why is this stock valued this way?",
    help="This section explains the reasoning behind the number, not just the number. Change the sidebar assumptions and watch the explanations update.",
)

if fcf0 <= 0:
    st.info(
        "This company has negative free cash flow, so a DCF can't value it well. "
        "That is a lesson in itself: a DCF only works for businesses whose cash flows can be "
        "reasonably forecast. Young or unprofitable companies are usually valued on other things, "
        "like revenue growth or future potential."
    )
else:
    pv_flows, pv_tv = dcf_breakdown(fcf0, growth, wacc, terminal_g, years)
    ev = pv_flows + pv_tv
    tv_share = pv_tv / ev
    imp_g = implied_growth(price)
    cost_of_equity = rf + beta * erp

    tab1, tab2, tab3, tab4 = st.tabs(
        ["📖 The big picture", "🧩 Where the value comes from", "🔍 What the market is assuming", "📚 Glossary"]
    )

    # ---- Tab 1: the story ----
    with tab1:
        st.markdown(
            f"""
**The core idea:** a company is worth the cash it will hand to its owners over its lifetime,
adjusted for the fact that money received later is worth less than money received today.

For **{info.get('longName', ticker)}**, this model does the following:

1. **Starts with real cash.** The company generates about **{money(fcf0 / 1e9)}B** of free cash flow per year
   (cash left over after running the business and paying for equipment and buildings).
2. **Guesses how it grows.** You assumed **{growth:.1%}** growth in year 1, fading toward **{terminal_g:.2%}**
   by year {years}. A fast grower slows down eventually, because no company can outgrow the economy forever.
3. **Shrinks future cash back to today's money.** Using a discount rate of **{wacc:.1%}**, a dollar received in
   year {years} is only worth about **{money(1 / (1 + wacc) ** years)}** today.
4. **Adds a "forever" value.** After year {years}, the company keeps earning, so the model adds a terminal value for all those later years.
5. **Subtracts debt and divides by shares.** The owners only get what is left after debt is paid, split across **{shares / 1e9:,.2f}B** shares.

**Result: {money(fair_value)} per share, compared with a market price of {money(price)}.**
"""
        )
        if upside > 0.15:
            st.markdown(
                f"The model's value is **{upside:.0%} above** the price. That means the market is assuming "
                "*less* growth, or a *higher* discount rate, than you chose. Either the market is "
                "being too cautious, or **your assumptions are too optimistic.** A good analyst asks both questions."
            )
        elif upside < -0.15:
            st.markdown(
                f"The model's value is **{abs(upside):.0%} below** the price. That means the market is assuming "
                "*more* growth, or a *lower* discount rate, than you chose. Either the market is being "
                "too hopeful, or **your assumptions are too pessimistic** (or the company has strengths a cash flow model doesn't capture, like a strong brand)."
            )
        else:
            st.markdown(
                "The model's value is close to the market price, so your assumptions are roughly **in line with what the market is assuming.**"
            )
        st.caption(
            "A DCF is only as good as its inputs. It shows what *must be true* for a price to make sense. It doesn't tell you what will happen."
        )

    # ---- Tab 2: where value comes from ----
    with tab2:
        st.markdown(
            "Here is how much of the company's value comes from **cash in the next "
            f"{years} years** versus **everything after that** (the terminal value)."
        )
        fig_src = go.Figure(
            go.Bar(
                x=[f"Cash flows, years 1-{years}", "Terminal value (after that)"],
                y=[pv_flows / 1e9, pv_tv / 1e9],
                marker_color=["#4facfe", "#00C48C"],
                text=[f"{money(pv_flows / 1e9)}B", f"{money(pv_tv / 1e9)}B"],
                textposition="auto",
            )
        )
        fig_src.update_layout(
            height=320, template="plotly_dark", yaxis_title="Present value ($B)",
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig_src, use_container_width=True) 
        st.markdown(
            f"**{tv_share:.0%} of this company's value comes from the terminal value.** "
            "That is typical for a DCF, and it is the model's biggest weakness: most of the answer "
            "depends on a guess about the distant future. This is why the sensitivity heatmap above "
            "matters so much."
        )
        if tv_share > 0.75:
            st.warning("More than 75% of this value rests on the terminal value, so this estimate is very sensitive to long-term guesses.")

        st.markdown("**From company value to price per share:**")
        bridge = pd.DataFrame(
            [
                {"Step": "Enterprise value (PV of all future cash)", "Amount": f"{money(ev / 1e9)}B"},
                {"Step": "Minus: net debt (debt minus cash)", "Amount": f"-{money(net_debt / 1e9)}B"},
                {"Step": "Equity value (what belongs to shareholders)", "Amount": f"{money((ev - net_debt) / 1e9)}B"},
                {"Step": f"Divided by shares ({shares / 1e9:,.2f}B)", "Amount": f"{money(fair_value)} per share"},
            ]
        )
        st.dataframe(bridge, hide_index=True, use_container_width=True)

    # ---- Tab 3: reverse DCF ----
    with tab3:
        st.markdown(
            "Instead of asking *'what is the stock worth?'*, flip the question: "
            "**'what would have to be true for today's price to be fair?'** This is called a **reverse DCF**, "
            "and many professionals consider it more useful than the forward version."
        )
        if imp_g is None:
            st.info("With your other assumptions, no reasonable growth rate matches today's price. Try changing the discount rate.")
        else:
            r1, r2, r3 = st.columns(3)
            r1.metric("Growth you assumed (yr 1)", f"{growth:.1%}")
            r2.metric("Growth the price implies", f"{imp_g:.1%}")
            r3.metric("Gap", f"{(imp_g - growth) * 100:+.1f} pts")
            hist_g = None
            if len(fcf_hist) >= 3 and fcf_hist.iloc[0] > 0 and fcf_hist.iloc[-1] > 0:
                hist_g = (fcf_hist.iloc[-1] / fcf_hist.iloc[0]) ** (1 / (len(fcf_hist) - 1)) - 1
            st.markdown(
                f"With your discount rate ({wacc:.1%}) and terminal growth ({terminal_g:.2%}), today's price of "
                f"{money(price)} makes sense **only if free cash flow grows about {imp_g:.1%} a year** at the start."
            )
            if hist_g is not None:
                st.markdown(
                    f"For context, this company's free cash flow has actually grown about **{hist_g:.1%} per year** "
                    "over the years of data available. Ask yourself: is the required growth realistic compared with the past?"
                )
        st.markdown("**Try it yourself:** move the discount rate slider up and watch the implied growth needed to justify the same price rise. Higher required returns demand more growth.")

    # ---- Tab 4: glossary ----
    with tab4:
        with st.expander("What is WACC (discount rate)?", expanded=True):
            st.markdown(
                f"""
**WACC** stands for *Weighted Average Cost of Capital*. It is the **return investors demand** for
putting money into this company instead of somewhere else. A company is financed by shareholders and lenders,
and each wants to be paid for the risk they take. WACC blends those required returns.

**Why do we discount future cash with it?** Because of two ideas:
- *Time value of money:* {money(100)} today can be invested and grow, so {money(100)} next year is worth less.
- *Risk:* the riskier the company, the higher the return investors demand, so the more future cash is shrunk.

**How this app estimates it (CAPM):**

`required return = risk-free rate + beta × equity risk premium`

| Piece | Meaning | {ticker} today |
|---|---|---|
| Risk-free rate | What a "safe" 10-year US Treasury pays | {rf:.2%} |
| Beta | How much the stock moves vs. the market (1.0 = same as market) | {beta:.2f} |
| Equity risk premium | Extra return investors expect for owning stocks instead of Treasuries (assumed) |{erp:.2%}|
| **Result** | | **{cost_of_equity:.2%}** |

**Honest caveat:** a full WACC also blends in the company's cost of *debt*, weighted by how much debt it has.
This app uses the CAPM figure only (technically the *cost of equity*) to keep things simple. Real analysts build the full blend.

**Why it matters so much:** a small change in WACC moves the valuation a lot, because it affects every year of cash flow and the terminal value. Check the sensitivity heatmap.
"""
            )
        with st.expander("What is free cash flow (FCF)?"):
            st.markdown(
                "Cash a company generates from operations **minus** what it must spend on equipment and facilities (capital expenditures) to keep the business running. "
                "It is the cash that could be paid to owners without hurting the business. Unlike accounting profit, it is hard to dress up with accounting choices."
            )
        with st.expander("What is terminal growth?"):
            st.markdown(
                "The steady growth rate assumed from the end of the forecast **forever**. It has to be small, usually near long-run inflation or economic growth (about 2-3%). "
                "If it were higher than the economy's growth, the company would eventually become bigger than the entire economy, which is impossible."
            )
        with st.expander("What is terminal value?"):
            st.markdown(
                "A company doesn't stop existing after year 5 or 10. Terminal value is a shortcut for the value of **all the cash flows after the forecast ends**, "
                "calculated with the Gordon Growth formula: `FCF × (1 + g) / (WACC − g)`. Notice that the gap between WACC and g is in the denominator, so when they get close, the value explodes. That's why the model requires WACC > terminal growth."
            )
        with st.expander("What is net debt?"):
            st.markdown(
                "Total debt minus cash. The cash flows we valued belong to *everyone* who funded the company, including lenders. "
                "Lenders get paid first, so we subtract net debt to find what is left for shareholders."
            )
        with st.expander("What is a margin of safety?"):
            st.markdown(
                "Because every DCF rests on guesses, careful investors want a price well below their estimate of value, as a cushion against being wrong. "
                "It's a way of building humility into the process."
            )
        with st.expander("What does the Monte Carlo simulation teach?"):
            st.markdown(
                "Instead of trusting one set of guesses, it runs thousands of slightly different versions. A **wide** spread of results means the valuation "
                "is very sensitive to the assumptions. That is a sign to be cautious about any single number."
            )

    st.markdown(
        '<div style="margin-top:10px; font-size:0.8rem; color:#9AA4B2;">'
        "Educational content only. This model explains how valuation works and does not recommend buying or selling any security."
        "</div>",
        unsafe_allow_html=True,
    )
    st.subheader("🧠 Test yourself")

    q1 = st.radio(
        "If you raise the discount rate (WACC), the fair value usually...",
        ["Goes up", "Goes down", "Stays the same"], index=None, key="quiz1",
    )
    if q1:
        if q1 == "Goes down":
            st.success("Correct! A higher required return shrinks the value of all future cash flows.")
        else:
            st.error("Not quite. Try moving the WACC slider and watch the fair value.")
            tab_learn.__exit__(None, None, None)
tab_overview.__enter__()
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
tab_overview.__exit__(None, None, None)
