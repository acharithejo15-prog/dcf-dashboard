"""
games.py - "Games" tab for RiskWise DCF.

Mini-games that teach valuation and risk, plus XP, levels, badges and a daily challenge.
Uses randomly generated fictional companies, so there are no data calls and no cost.

NOTE: progress lives in st.session_state, so it resets when the page is refreshed.
Saving progress between visits is the job of the database step (Supabase) later.
"""

import datetime
import random

import streamlit as st

# ---------------------------------------------------------------
# Levels and badges
# ---------------------------------------------------------------
LEVELS = [
    (0, "Rookie"),
    (100, "Analyst"),
    (250, "Associate"),
    (500, "Strategist"),
    (900, "Portfolio Manager"),
    (1500, "Market Legend"),
]

BADGES = {
    "first_game": ("🎮", "First Game", "Finish any game"),
    "perfect": ("💯", "Perfect Round", "Answer every question in a game correctly"),
    "valuation_rookie": ("🔍", "Valuation Rookie", "Make 10 correct Over/Undervalued calls"),
    "vocab_pro": ("📚", "Vocab Pro", "Get a perfect score in Term Match"),
    "sharp_eye": ("🎯", "Sharp Eye", "Guess a valuation gap within 5 points"),
    "bull_bear": ("⚖️", "Both Sides", "Get a perfect score in Bull vs. Bear"),
    "daily": ("📅", "Daily Player", "Complete a daily challenge"),
    "level3": ("🚀", "Associate", "Reach level 3"),
}


def _init():
    s = st.session_state
    s.setdefault("g_xp", 0)
    s.setdefault("g_badges", [])
    s.setdefault("g_stats", {"ou_correct": 0})
    s.setdefault("g_runs", {})


def _level(xp):
    idx = 0
    for i, (need, _) in enumerate(LEVELS):
        if xp >= need:
            idx = i
    cur_need, name = LEVELS[idx]
    if idx + 1 < len(LEVELS):
        nxt_need = LEVELS[idx + 1][0]
        frac = (xp - cur_need) / (nxt_need - cur_need)
    else:
        nxt_need, frac = None, 1.0
    return idx + 1, name, nxt_need, frac


def _badge(key):
    if key not in st.session_state.g_badges:
        st.session_state.g_badges.append(key)
        icon, name, _ = BADGES[key]
        st.toast(f"New badge: {name}", icon=icon)


def _add_xp(n):
    before = _level(st.session_state.g_xp)[0]
    st.session_state.g_xp += int(n)
    after = _level(st.session_state.g_xp)[0]
    if after > before:
        st.toast(f"Level up! You are now level {after}", icon="⬆️")
    if after >= 3:
        _badge("level3")


# ---------------------------------------------------------------
# Fictional companies + a mini DCF (same math as the main app)
# ---------------------------------------------------------------
# (name, sector, growth range, WACC range)
ARCHETYPES = [
    ("Bluepeak Software", "Software", (0.08, 0.14), (0.09, 0.11)),
    ("Northwind Foods", "Consumer staples", (0.03, 0.06), (0.065, 0.08)),
    ("Maple Utilities", "Utilities", (0.02, 0.04), (0.06, 0.07)),
    ("Zenith Chips", "Semiconductors", (0.08, 0.13), (0.09, 0.115)),
    ("Ironbridge Energy", "Energy", (0.02, 0.06), (0.08, 0.10)),
    ("Aster Pharma", "Healthcare", (0.05, 0.10), (0.07, 0.09)),
    ("Cobalt Logistics", "Industrials", (0.04, 0.08), (0.075, 0.095)),
    ("Lumen Retail", "Retail", (0.03, 0.07), (0.08, 0.10)),
]
PRICE_MULTS = [0.55, 0.7, 0.9, 1.0, 1.1, 1.3, 1.6, 1.9]  # price relative to fair value


def _dcf(fcf0, growth, wacc, tg, years, net_debt, shares):
    """Returns (fair value per share, share of enterprise value from terminal value)."""
    flows, fcf = [], fcf0
    for t in range(1, years + 1):
        g_t = growth + (tg - growth) * (t - 1) / max(years - 1, 1)
        fcf *= 1 + g_t
        flows.append(fcf)
    pv = sum(f / (1 + wacc) ** t for t, f in enumerate(flows, start=1))
    tv = flows[-1] * (1 + tg) / (wacc - tg) / (1 + wacc) ** years
    ev = pv + tv
    return (ev - net_debt) / shares, tv / ev


def _make_company(arch, rng):
    name, sector, (g_lo, g_hi), (w_lo, w_hi) = arch
    while True:
        c = {
            "name": name,
            "sector": sector,
            "fcf": round(rng.uniform(2, 40), 1) * 1e9,
            "growth": round(rng.uniform(g_lo, g_hi), 3),
            "wacc": round(rng.uniform(w_lo, w_hi), 3),
            "tg": rng.choice([0.02, 0.025, 0.03]),
            "years": 5,
            "shares": round(rng.uniform(0.5, 5), 2) * 1e9,
        }
        c["net_debt"] = c["fcf"] * rng.uniform(-1, 4)
        fair, tv_share = _dcf(c["fcf"], c["growth"], c["wacc"], c["tg"], c["years"], c["net_debt"], c["shares"])
        if fair > 1:
            c["fair"], c["tv_share"] = fair, tv_share
            c["price"] = round(fair * rng.choice(PRICE_MULTS), 2)
            c["gap"] = c["fair"] / c["price"] - 1
            return c


def _make_companies(n, rng):
    return [_make_company(a, rng) for a in rng.sample(ARCHETYPES, n)]


def _m(x):
    """Dollar amount escaped for st.markdown."""
    return f"\\${x:,.2f}"


def _billions(x):
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x) / 1e9:,.1f}B"


def _show_company(c):
    st.markdown(f"#### {c['name']} · {c['sector']}")
    a = st.columns(4)
    a[0].metric("Share price", f"${c['price']:,.2f}")
    a[1].metric("Free cash flow", _billions(c["fcf"]))
    a[2].metric("Year-1 growth", f"{c['growth']:.1%}")
    a[3].metric("Discount rate (WACC)", f"{c['wacc']:.1%}")
    b = st.columns(4)
    b[0].metric("Terminal growth", f"{c['tg']:.1%}")
    b[1].metric("Net debt", _billions(c["net_debt"]))
    b[2].metric("Shares", f"{c['shares'] / 1e9:,.2f}B")
    b[3].metric("Forecast years", c["years"])


def _reveal(c):
    return (
        f"**{c['name']}'s DCF fair value is {_m(c['fair'])}** against a price of {_m(c['price'])}, "
        f"a gap of **{c['gap']:+.0%}**. About **{c['tv_share']:.0%}** of its value comes from the "
        f"terminal value, so small changes to WACC or terminal growth move the answer a lot."
    )


# ---------------------------------------------------------------
# Game 1 and 2: Over or Undervalued / Guess the Gap
# ---------------------------------------------------------------
def _ou_input(item, key):
    _show_company(item)
    with st.expander("Need a hint?"):
        st.markdown(
            "- Higher growth and a **lower** discount rate push fair value **up**.\n"
            "- Lots of debt pulls the value to shareholders **down**.\n"
            "- Within about 15% of fair value counts as *fairly valued*."
        )
    return st.radio(
        "Your call", ["Undervalued", "Fairly valued", "Overvalued"],
        index=None, key=key, horizontal=True,
    )


def _ou_grade(item, answer):
    gap = item["gap"]
    truth = "Undervalued" if gap > 0.15 else ("Overvalued" if gap < -0.15 else "Fairly valued")
    ok = answer == truth
    head = "✅ Correct." if ok else f"❌ Not quite. It was **{truth}**."
    return {"score": 1.0 if ok else 0.0, "correct": ok, "msg": f"{head}\n\n{_reveal(item)}"}


def _gap_input(item, key):
    _show_company(item)
    st.caption("Fair value is how much higher (+) or lower (-) than the price? Estimate it.")
    return st.slider("Fair value vs. price (%)", -60, 100, 0, 5, key=key)


def _gap_grade(item, answer):
    actual = item["gap"] * 100
    err = abs(answer - actual)
    ok = err <= 10
    score = max(0.0, 1 - err / 40)
    head = f"{'✅' if ok else '❌'} You guessed **{answer:+d}%**, the real gap was **{actual:+.0f}%** (off by {err:.0f} points)."
    return {"score": score, "correct": ok, "err": err, "msg": f"{head}\n\n{_reveal(item)}"}


# ---------------------------------------------------------------
# Game 3: Term Match
# ---------------------------------------------------------------
TERMS = [
    ("WACC", "The return investors demand for funding a company, used to discount future cash."),
    ("Free cash flow", "Cash from operations minus the spending needed to maintain and grow the business."),
    ("Terminal value", "The value of all cash flows after the forecast period ends."),
    ("Margin of safety", "The cushion between what you think something is worth and what you pay."),
    ("Beta", "How much a stock tends to move compared with the overall market."),
    ("Net debt", "Total debt minus cash on hand."),
    ("Enterprise value", "The value of the whole business to everyone who funds it, debt and equity together."),
    ("Monte Carlo simulation", "Running a model thousands of times with randomized inputs to see a range of outcomes."),
    ("Equity risk premium", "The extra return investors expect from stocks over safe government bonds."),
    ("P/E ratio", "Share price divided by earnings per share."),
    ("Volatility", "How widely and quickly a price swings around its average."),
    ("Discounting", "Shrinking future money to what it is worth today."),
]


def _term_make(n, rng):
    items = []
    for term, definition in rng.sample(TERMS, n):
        others = [d for t, d in TERMS if t != term]
        options = rng.sample(others, 3) + [definition]
        rng.shuffle(options)
        items.append({"term": term, "answer": definition, "options": options})
    return items


def _term_input(item, key):
    st.markdown(f"### What does **{item['term']}** mean?")
    return st.radio("Pick the best definition", item["options"], index=None, key=key, label_visibility="collapsed")


def _term_grade(item, answer):
    ok = answer == item["answer"]
    head = "✅ Correct." if ok else "❌ Not quite."
    return {"score": 1.0 if ok else 0.0, "correct": ok, "msg": f"{head} **{item['term']}**: {item['answer']}"}


# ---------------------------------------------------------------
# Game 4: Bull vs. Bear
# ---------------------------------------------------------------
STATEMENTS = [
    ("Free cash flow has grown faster every year for five years.", "Bull case",
     "Accelerating cash flow is the kind of trend that supports a higher valuation."),
    ("The company's debt is rising while its cash flow is flat.", "Bear case",
     "More debt with no growth in cash means more risk for shareholders."),
    ("Management is buying back shares at fair prices using spare cash.", "Bull case",
     "Buybacks at sensible prices raise value per share."),
    ("Three of its five biggest customers are leaving for a competitor.", "Bear case",
     "Losing major customers threatens future revenue and cash flow."),
    ("The stock trades at twice its industry's average P/E with no extra growth.", "Bear case",
     "Paying a big premium without extra growth leaves little room for error."),
    ("Interest rates are falling, which lowers the discount rate.", "Bull case",
     "A lower discount rate raises the present value of future cash flows."),
    ("The company dominates its market and keeps raising prices without losing customers.", "Bull case",
     "Pricing power is a strong sign of a durable competitive advantage."),
    ("Most of the company's value depends on growth far in the future.", "Bear case",
     "Value that sits mostly in the distant future is very sensitive to guesses."),
    ("A new product line is expected to add a second revenue stream.", "Bull case",
     "A new, well-run revenue stream can lift growth, if it succeeds."),
    ("New regulation may force the company to cut its prices.", "Bear case",
     "Forced price cuts would squeeze profits and cash flow."),
    ("The company keeps spending more on equipment just to maintain output.", "Bear case",
     "High maintenance spending eats into free cash flow."),
    ("Its return on new investments is higher than its cost of capital.", "Bull case",
     "Investing at returns above the cost of capital creates value."),
]


def _bb_make(n, rng):
    return [{"text": t, "answer": a, "why": w} for t, a, w in rng.sample(STATEMENTS, n)]


def _bb_input(item, key):
    st.markdown(f"### {item['text']}")
    return st.radio("Which side does this help?", ["Bull case", "Bear case"], index=None, key=key, horizontal=True)


def _bb_grade(item, answer):
    ok = answer == item["answer"]
    head = "✅ Correct." if ok else f"❌ Not quite. This is a **{item['answer']}**."
    return {"score": 1.0 if ok else 0.0, "correct": ok, "msg": f"{head} {item['why']}"}


# ---------------------------------------------------------------
# On-finish hooks (badges)
# ---------------------------------------------------------------
def _fin_ou(run):
    st.session_state.g_stats["ou_correct"] += sum(r["correct"] for r in run["results"])
    if st.session_state.g_stats["ou_correct"] >= 10:
        _badge("valuation_rookie")


def _fin_gap(run):
    if any(r.get("err", 99) <= 5 for r in run["results"]):
        _badge("sharp_eye")


def _fin_terms(run):
    if all(r["correct"] for r in run["results"]):
        _badge("vocab_pro")


def _fin_bb(run):
    if all(r["correct"] for r in run["results"]):
        _badge("bull_bear")


def _fin_daily(run):
    _badge("daily")
    _add_xp(30)


# ---------------------------------------------------------------
# Generic game runner
# ---------------------------------------------------------------
def _start(gid, n, make_items, seed):
    rng = random.Random(seed if seed is not None else random.randrange(10**9))
    st.session_state.g_runs[gid] = {
        "id": random.randrange(10**9), "items": make_items(n, rng), "idx": 0,
        "phase": "ask", "results": [], "awarded": False, "xp": 0,
    }


def _lock(gid, grade, key):
    run = st.session_state.g_runs[gid]
    answer = st.session_state.get(key)
    run["results"].append(grade(run["items"][run["idx"]], answer))
    run["phase"] = "review"


def _next(gid):
    run = st.session_state.g_runs[gid]
    run["idx"] += 1
    run["phase"] = "ask"


def _reset(gid):
    st.session_state.g_runs.pop(gid, None)


def _run_game(gid, title, blurb, n, make_items, render_input, grade, xp_per, on_finish=None, seed=None, replay=True):
    st.markdown(f"## {title}")
    run = st.session_state.g_runs.get(gid)

    if run is None:
        st.write(blurb)
        st.button("▶ Start", key=f"{gid}_start", type="primary", on_click=_start, args=(gid, n, make_items, seed))
        return

    # ----- finished -----
    if run["idx"] >= n:
        total = sum(r["score"] for r in run["results"])
        right = sum(r["correct"] for r in run["results"])
        perfect = right == n
        if not run["awarded"]:
            run["awarded"] = True
            run["xp"] = round(total * xp_per) + 20 + (25 if perfect else 0)
            _add_xp(run["xp"])
            _badge("first_game")
            if perfect:
                _badge("perfect")
            if on_finish:
                on_finish(run)
        st.success(f"Finished! **{right} / {n}** correct, **+{run['xp']} XP**" + (" (perfect bonus!)" if perfect else ""))
        if replay:
            st.button("🔁 Play again", key=f"{gid}_again", on_click=_reset, args=(gid,))
        else:
            st.caption("Come back tomorrow for a new one.")
        return

    # ----- in progress -----
    idx = run["idx"]
    st.progress(idx / n, text=f"Question {idx + 1} of {n}")
    item = run["items"][idx]

    if run["phase"] == "ask":
        key = f"{gid}_in_{run['id']}_{idx}"
        answer = render_input(item, key)
        st.button(
            "Lock in answer", key=f"{gid}_lock_{run['id']}_{idx}", type="primary",
            disabled=answer is None, on_click=_lock, args=(gid, grade, key),
        )
    else:
        res = run["results"][idx]
        if res["correct"]:
            st.success(res["msg"])
        else:
            st.error(res["msg"])
        label = "Next →" if idx + 1 < n else "See results"
        st.button(label, key=f"{gid}_next_{run['id']}_{idx}", type="primary", on_click=_next, args=(gid,))


# ---------------------------------------------------------------
# The tab
# ---------------------------------------------------------------
def _header():
    xp = st.session_state.g_xp
    lvl, name, nxt, frac = _level(xp)
    c1, c2, c3 = st.columns([1, 1, 2])
    c1.metric("Level", f"{lvl} · {name}")
    c2.metric("XP", xp)
    with c3:
        if nxt:
            st.progress(frac, text=f"{nxt - xp} XP to next level")
        else:
            st.progress(1.0, text="Max level reached")
    with st.expander(f"🏅 Badges ({len(st.session_state.g_badges)} / {len(BADGES)})"):
        cols = st.columns(4)
        for i, (key, (icon, nm, how)) in enumerate(BADGES.items()):
            got = key in st.session_state.g_badges
            cols[i % 4].markdown(
                f"{icon if got else '🔒'} **{nm}**  \n"
                f"<span style='color:#9AA4B2; font-size:0.8rem;'>{how}</span>",
                unsafe_allow_html=True,
            )


def render_games_tab():
    _init()
    st.subheader("🎮 Games")
    st.caption(
        "Learn valuation by playing. All companies here are made up, so there is no real data and no "
        "investment advice. Progress resets if you refresh the page."
    )
    _header()
    st.divider()

    today = datetime.date.today()
    choices = {
        "📅 Daily challenge": "daily",
        "🔍 Over or Undervalued?": "ou",
        "🎯 Guess the Gap": "gap",
        "📚 Term Match": "terms",
        "⚖️ Bull vs. Bear": "bb",
    }
    pick = choices[st.radio("Choose a game", list(choices), horizontal=True, key="g_pick", label_visibility="collapsed")]

    if pick == "daily":
        _run_game(
            f"daily_{today.isoformat()}", "📅 Daily challenge",
            "Three companies, the same for everyone today. Call each one: undervalued, fairly valued, or overvalued. "
            "Finish for a 30 XP bonus.",
            3, _make_companies, _ou_input, _ou_grade, 15, on_finish=_fin_daily,
            seed=today.toordinal(), replay=False,
        )
    elif pick == "ou":
        _run_game(
            "ou", "🔍 Over or Undervalued?",
            "Five companies. Read their numbers and decide whether the stock is undervalued, fairly valued, "
            "or overvalued. Then the DCF reveals the answer.",
            5, _make_companies, _ou_input, _ou_grade, 10, on_finish=_fin_ou,
        )
    elif pick == "gap":
        _run_game(
            "gap", "🎯 Guess the Gap",
            "Estimate how far each company's DCF fair value is from its price. Closer guesses earn more XP.",
            5, _make_companies, _gap_input, _gap_grade, 10, on_finish=_fin_gap,
        )
    elif pick == "terms":
        _run_game(
            "terms", "📚 Term Match",
            "Pick the right meaning for each finance term.",
            6, _term_make, _term_input, _term_grade, 8, on_finish=_fin_terms,
        )
    else:
        _run_game(
            "bb", "⚖️ Bull vs. Bear",
            "Does each fact help the bull case (reasons to own the stock) or the bear case (reasons to worry)?",
            6, _bb_make, _bb_input, _bb_grade, 8, on_finish=_fin_bb,
        )
