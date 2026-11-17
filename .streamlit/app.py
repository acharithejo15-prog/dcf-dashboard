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
st.title("DCF Valuation & Risk Dashboard")
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
st.toast(f"Loaded {ticker}: fair value ${fair_value:,.2f}", icon="📈")
upside = fair_value / price - 1
# ---------------- Model verdict ----------------
if fcf0 <= 0:
    label, color, icon = "Model Not Reliable", "#F5A623", "⚠️"
    summary = (
        "This company has negative free cash flow, so a cash flow based DCF "
        "cannot produce a meaningful valuation."
    )
elif upside > 0.15:
    label, color, icon = "Appears Undervalued", "#00C48C", "📈"
    summary = (
        f"Based on your assumptions, the model estimates a fair value of "
        f"${fair_value:,.2f}, about {upside:.0%} above the current price of ${price:,.2f}. "
        f"If the assumptions hold, the stock may be trading below its intrinsic value."
    )
elif upside < -0.15:
    label, color, icon = "Appears Overvalued", "#FF4B4B", "📉"
    summary = (
        f"Based on your assumptions, the model estimates a fair value of "
        f"${fair_value:,.2f}, about {abs(upside):.0%} below the current price of ${price:,.2f}. "
        f"The market may be pricing in more growth than these assumptions allow."
    )
else:
    label, color, icon = "Appears Fairly Valued", "#4facfe", "⚖️"
    summary = (
        f"Based on your assumptions, the model estimates a fair value of "
        f"${fair_value:,.2f}, within about 15% of the current price of ${price:,.2f}. "
        f"The market price is roughly in line with the model."
    )

st.toast(f"{ticker}: {label}", icon=icon)

st.markdown(
    f"""
    <div style="border-left: 6px solid {color}; background: #1A1F2B;
                padding: 16px 20px; border-radius: 10px; margin: 12px 0;">
        <div style="font-size: 1.3rem; font-weight: 700; color: {color};">
            {icon} Model signal: {label}
        </div>
        <div style="margin-top: 6px; color: #FAFAFA;">{summary}</div>
        <div style="margin-top: 8px; font-size: 0.8rem; color: #9AA4B2;">
            This is an educational model output based on the assumptions in the sidebar.
            It is not investment advice and does not guarantee future results.
            Change the assumptions and the signal will change.
        </div>
    </div>
    """,
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
            go.Scatter(x=px_data.index, y=px_data["Close"], mode="lines", name="Price", line=dict(color=line_color, width=2))
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
    fig_price.update_layout(
        height=420, template="plotly_dark", yaxis_title="$ per share",
        xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(fig_price, use_container_width=True)
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

results = []
for g, w, tg in zip(g_draws, w_draws, t_draws):
    if w > tg + 0.01:
        results.append(dcf_value(fcf0, g, w, tg, years, net_debt, shares))
results = np.array(results)

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

    # Hype vs. valuation: the key insight
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
