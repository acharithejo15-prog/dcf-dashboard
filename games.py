"""
games.py - "Games" tab for RiskWise DCF.

Mini-games that teach valuation and risk, plus XP, levels, badges and a daily challenge.
Uses randomly generated fictional companies, so there are no data calls and no cost.

NOTE: progress lives in st.session_state, so it resets when the page is refreshed.
Saving progress between visits is the job of the database step (Supabase) later.
"""

import datetime
import os
import random
import tempfile

import streamlit as st
import streamlit.components.v1 as components

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
    "blade": ("🥷", "Blade Runner", "Finish a Slash round with a life to spare"),
    "combo": ("🔥", "Combo King", "Reach a 5x combo in a Slash game"),
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
# ---------------------------------------------------------------
# Slash games (Fruit-Ninja style). The game itself runs in the browser,
# see the ninja_component/index.html file that sits next to this one.
# ---------------------------------------------------------------
SLASH_MODES = {
    "slash_terms": ("🥷 Term Ninja", "A definition appears. Slash the fruit with the matching finance term!"),
    "slash_bb": ("🥷 Bull or Bear Ninja", "A fact appears. Slash the fruit for the side it helps: bull or bear."),
    "slash_val": ("🥷 Valuation Ninja", "A company's numbers appear. Slash the right call: under, fairly, or overvalued."),
}

_NINJA_HTML = r"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { --card:#1A1F2B; --line:#2A3142; --txt:#FAFAFA; --mut:#9AA4B2; --grn:#00C48C; --blu:#4facfe; --red:#FF4B4B; --org:#F5A623; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; color:var(--txt);
         background:transparent; user-select:none; -webkit-user-select:none; }
  #wrap { max-width: 900px; margin: 0 auto; }
  #hud { display:flex; justify-content:space-between; align-items:center; gap:8px; padding:8px 14px;
         background:var(--card); border:1px solid var(--line); border-radius:12px 12px 0 0; font-weight:700; font-size:15px; }
  #cb { color:var(--org); min-width:70px; text-align:center; }
  #prompt { padding:10px 14px; min-height:66px; background:var(--card); border-left:1px solid var(--line);
            border-right:1px solid var(--line); font-size:16px; line-height:1.35; display:flex; align-items:center; }
  #prompt.good { color:var(--grn); }
  #prompt.bad { color:var(--red); }
  #barwrap { height:6px; background:#0A0E14; border-left:1px solid var(--line); border-right:1px solid var(--line); }
  #bar { height:100%; width:100%; background:var(--grn); transition: background .3s; }
  #stage { position:relative; }
  canvas { display:block; width:100%; height:auto; touch-action:none; cursor:crosshair;
           background: radial-gradient(ellipse at 50% 0%, #1d2740 0%, #0E1117 75%);
           border:1px solid var(--line); border-radius:0 0 12px 12px; }
  #ov { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; padding:14px;
        text-align:center; pointer-events:none; border-radius:0 0 12px 12px; }
  #ov.end { background:rgba(10,14,20,.88); justify-content:center; pointer-events:auto; }
  #ov .mut { color:var(--mut); font-size:14px; }
  #startbtn { pointer-events:auto; margin-top:auto; padding:10px 28px; border:0; border-radius:999px; cursor:pointer;
              background:linear-gradient(90deg,#00C48C,#4facfe); color:#fff; font-weight:800; font-size:15px; }
  .big { font-size:26px; font-weight:800; margin-bottom:8px; }
</style>
</head>
<body>
<div id="wrap">
  <div id="hud"><span id="qn">Q 0/0</span><span id="sc">Score 0</span><span id="cb"></span><span id="hp"></span></div>
  <div id="prompt">Loading...</div>
  <div id="barwrap"><div id="bar"></div></div>
  <div id="stage">
    <canvas id="cv" width="900" height="420"></canvas>
    <div id="ov"><div id="ovt"></div><button id="startbtn">Start</button></div>
  </div>
</div>

<script>
(function () {
  const cv = document.getElementById("cv"), ctx = cv.getContext("2d");
  const W = cv.width, H = cv.height, G = 520;
  const COLORS = ["#e74c3c", "#f39c12", "#27ae60", "#8e44ad", "#2980b9", "#e84393"];
  const $ = id => document.getElementById(id);

  let cfg = null, qs = [], qi = 0, score = 0, lives = 3, maxLives = 3, combo = 0, bestCombo = 0, correctCount = 0;
  let state = "idle";            // idle | play | feedback | over
  let tLeft = 15, limit = 15, sent = false;
  let fruits = [], pieces = [], parts = [], floats = [], trail = [];
  let spawnT = 0, spawnList = [], shake = 0, lastPt = null, pressed = false;

  // ---------- Streamlit component protocol ----------
  function post(m) { window.parent.postMessage(Object.assign({ isStreamlitMessage: true }, m), "*"); }
  function setH() { post({ type: "streamlit:setFrameHeight", height: document.documentElement.scrollHeight + 4 }); }
  function sendValue(v) { post({ type: "streamlit:setComponentValue", value: v, dataType: "json" }); }
  window.addEventListener("message", e => {
    if (e.data && e.data.type === "streamlit:render" && e.data.args && e.data.args.config) init(e.data.args.config);
  });
  post({ type: "streamlit:componentReady", apiVersion: 1 });
  if (window.ResizeObserver) new ResizeObserver(setH).observe(document.body);

  // ---------- helpers ----------
  function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
  function rnd(a, b) { return a + Math.random() * (b - a); }
  function shuffle(a) { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; }
  function setPrompt(t, kind) { const p = $("prompt"); p.textContent = t; p.className = kind || ""; }
  function updateHud() {
    $("qn").textContent = state === "idle" ? "Ready" : "Q " + Math.min(qi + 1, qs.length) + "/" + qs.length;
    $("sc").textContent = "Score " + score;
    $("cb").textContent = combo >= 2 ? "🔥 x" + combo : "";
    $("hp").textContent = "❤️".repeat(Math.max(lives, 0)) + "🖤".repeat(Math.max(maxLives - lives, 0));
  }

  // ---------- game flow ----------
  function init(c) {
    if (cfg && cfg.run_id === c.run_id) return;
    cfg = c; qs = c.questions; limit = c.seconds || 15; maxLives = c.lives || 3;
    resetGame(); setH();
  }
  function resetGame() {
    score = 0; lives = maxLives; combo = 0; bestCombo = 0; correctCount = 0; qi = 0; state = "idle"; sent = false;
    fruits = []; pieces = []; parts = []; floats = []; trail = [];
    $("ov").className = "";
    $("ovt").innerHTML = '<div style="font-size:20px;font-weight:800">' + esc(cfg.title) + '</div>' +
      '<div class="mut">' + qs.length + " questions · " + maxLives + " lives · slash the correct answer</div>";
    $("startbtn").style.display = "";
    setPrompt("Slash the green fruit (or press Start) to begin. Wrong fruit costs a life!", "");
    fruits.push({ x: W / 2, y: H * 0.6, vx: 0, vy: 0, r: 74, label: "SLASH TO START", idx: -1, color: "#00C48C", rot: 0, rotv: 0, st: true, t: 0 });
    updateHud();
  }
  function startGame() {
    if (state !== "idle") return;
    fruits = []; $("ovt").innerHTML = ""; $("startbtn").style.display = "none";
    newQ();
  }
  $("startbtn").addEventListener("click", startGame);

  function newQ() {
    state = "play"; tLeft = limit; spawnList = []; spawnT = 0.15; fruits = [];
    qs[qi].wrong = false;
    setPrompt(qs[qi].prompt, ""); updateHud();
  }
  function feedback(msg, kind, final) {
    state = "feedback"; setPrompt(msg, kind); updateHud();
    setTimeout(() => { if (final || qi + 1 >= qs.length) finish(); else { qi++; newQ(); } }, kind === "good" ? 2300 : 3400);
  }
  function finish() {
    state = "over"; updateHud(); fruits = [];
    const dead = lives <= 0;
    $("startbtn").style.display = "none";
    $("ov").className = "end";
    $("ovt").innerHTML = '<div class="big">' + (dead ? "💔 Game over" : "🏁 Round complete") + "</div>" +
      '<div style="font-size:20px">Score <b>' + score + "</b></div>" +
      '<div style="margin-top:6px">' + correctCount + " / " + qs.length + " right on the first try · best combo x" + bestCombo + "</div>" +
      '<div class="mut" style="margin-top:10px">Scroll down to collect your XP and start a new round.</div>';
    setPrompt(dead ? "Out of lives!" : "Nice work!", dead ? "bad" : "good");
    if (!sent) {
      sent = true;
      sendValue({ run_id: cfg.run_id, score: score, correct: correctCount, total: qs.length, best_combo: bestCombo, lives_left: Math.max(lives, 0) });
    }
    setH();
  }

  function onSlice(f) {
    if (f.idx === -1) { startGame(); return; }
    if (state !== "play") return;
    const q = qs[qi];
    if (f.idx === q.answer) {
      let pts;
      if (!q.wrong) {
        combo++; bestCombo = Math.max(bestCombo, combo); correctCount++;
        pts = 100 + Math.round(50 * tLeft / limit) + Math.min(combo - 1, 9) * 10;
      } else { pts = 40; combo = 0; }
      score += pts;
      floats.push({ x: f.x, y: f.y, txt: "+" + pts, life: 1, color: "#00C48C" });
      if (combo >= 2) floats.push({ x: f.x, y: f.y - 28, txt: "COMBO x" + combo, life: 1, color: "#F5A623" });
      feedback("✅ " + q.why, "good", false);
    } else {
      q.wrong = true; lives--; combo = 0; shake = 12;
      floats.push({ x: f.x, y: f.y, txt: "-1 ❤️", life: 1, color: "#FF4B4B" });
      updateHud();
      if (lives <= 0) feedback("💔 Out of lives. The answer was: " + q.options[q.answer] + ". " + q.why, "bad", true);
    }
    updateHud();
  }

  function timeUp() {
    const q = qs[qi]; lives--; combo = 0; shake = 10; fruits = [];
    updateHud();
    feedback("⏱ Time's up! The answer was: " + q.options[q.answer] + ". " + q.why, "bad", lives <= 0);
  }

  // ---------- spawning ----------
  function spawn(idx) {
    const label = qs[qi].options[idx];
    const r = Math.min(76, 40 + Math.sqrt(label.length) * 7);
    const x = r + Math.random() * (W - 2 * r), apex = H * (0.18 + Math.random() * 0.35);
    fruits.push({
      x: x, y: H + r, vy: -Math.sqrt(2 * G * (H + r - apex)),
      vx: (W / 2 - x) * 0.25 * (0.5 + Math.random()) + (Math.random() - 0.5) * 60,
      r: r, label: label, idx: idx, color: COLORS[idx % COLORS.length], rot: 0, rotv: (Math.random() - 0.5) * 3
    });
  }

  // ---------- slicing ----------
  function slice(f) {
    fruits.splice(fruits.indexOf(f), 1);
    for (let h = 0; h < 2; h++) {
      pieces.push({ x: f.x, y: f.y, r: f.r, color: f.color, half: h, rot: f.rot + rnd(-0.4, 0.4), rotv: (h ? 1 : -1) * rnd(1.5, 4),
                    vx: (h ? 1 : -1) * rnd(70, 150) + (f.vx || 0) * 0.4, vy: (f.vy || 0) * 0.3 - rnd(20, 90) });
    }
    for (let i = 0; i < 16; i++) parts.push({ x: f.x, y: f.y, vx: rnd(-220, 220), vy: rnd(-260, 80), life: 1, color: f.color });
    onSlice(f);
  }
  function segHit(ax, ay, bx, by, cx, cy, r) {
    const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
    let t = l2 ? ((cx - ax) * dx + (cy - ay) * dy) / l2 : 0; t = Math.max(0, Math.min(1, t));
    const px = ax + t * dx, py = ay + t * dy;
    return (cx - px) * (cx - px) + (cy - py) * (cy - py) <= r * r;
  }
  function pos(e) { const r = cv.getBoundingClientRect(); return { x: (e.clientX - r.left) * W / r.width, y: (e.clientY - r.top) * H / r.height }; }
  cv.addEventListener("pointerdown", e => { pressed = true; lastPt = pos(e); try { cv.setPointerCapture(e.pointerId); } catch (_) {} });
  window.addEventListener("pointerup", () => { pressed = false; lastPt = null; });
  cv.addEventListener("pointerleave", () => { if (!pressed) lastPt = null; });
  cv.addEventListener("pointermove", e => {
    const p = pos(e), active = e.pointerType === "mouse" || pressed;
    if (active && lastPt && Math.hypot(p.x - lastPt.x, p.y - lastPt.y) > 3) {
      const now = performance.now();
      if (!trail.length) trail.push({ x: lastPt.x, y: lastPt.y, t: now });
      trail.push({ x: p.x, y: p.y, t: now });
      for (const f of fruits.slice()) if (segHit(lastPt.x, lastPt.y, p.x, p.y, f.x, f.y, f.r * 0.92)) slice(f);
    }
    lastPt = p;
  });

  // ---------- update ----------
  function update(dt) {
    for (const f of fruits.slice()) {
      if (f.st) { f.t += dt; f.y = H * 0.6 + Math.sin(f.t * 2.2) * 7; f.rot = Math.sin(f.t) * 0.15; continue; }
      f.vy += G * dt; f.x += f.vx * dt; f.y += f.vy * dt; f.rot += f.rotv * dt;
      if (f.x < f.r) { f.x = f.r; f.vx = Math.abs(f.vx); }
      if (f.x > W - f.r) { f.x = W - f.r; f.vx = -Math.abs(f.vx); }
      if (f.y > H + f.r + 30 && f.vy > 0) fruits.splice(fruits.indexOf(f), 1);
    }
    for (const p of pieces) { p.vy += G * dt; p.x += p.vx * dt; p.y += p.vy * dt; p.rot += p.rotv * dt; }
    pieces = pieces.filter(p => p.y < H + 120);
    for (const q of parts) { q.vy += 700 * dt; q.x += q.vx * dt; q.y += q.vy * dt; q.life -= dt * 1.4; }
    parts = parts.filter(q => q.life > 0);
    for (const t of floats) { t.y -= 40 * dt; t.life -= dt * 0.7; }
    floats = floats.filter(t => t.life > 0);
    shake = Math.max(0, shake - 40 * dt);
    const now = performance.now(); trail = trail.filter(t => now - t.t < 180);

    if (state === "play") {
      tLeft -= dt;
      const frac = Math.max(tLeft / limit, 0);
      $("bar").style.width = (frac * 100) + "%";
      $("bar").style.background = frac > 0.5 ? "#00C48C" : (frac > 0.25 ? "#F5A623" : "#FF4B4B");
      if (tLeft <= 0) { timeUp(); return; }
      spawnT -= dt;
      if (spawnT <= 0 && fruits.length < 5) {
        if (!spawnList.length) spawnList = shuffle(qs[qi].options.map((_, i) => i));
        spawn(spawnList.pop());
        spawnT = 0.7 + Math.random() * 0.35;
      }
    }
  }

  // ---------- drawing ----------
  function wrap(text, maxW) {
    const words = text.split(" "), lines = []; let cur = "";
    for (const w of words) {
      const t = cur ? cur + " " + w : w;
      if (ctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t;
    }
    if (cur) lines.push(cur);
    return lines;
  }
  function drawLabel(text, x, y, r) {
    let size = 16; ctx.font = "800 " + size + "px system-ui,sans-serif";
    let lines = wrap(text, r * 1.6);
    if (lines.length > 3) { size = 13; ctx.font = "800 " + size + "px system-ui,sans-serif"; lines = wrap(text, r * 1.7); }
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    const lh = size + 2, y0 = y - (lines.length - 1) * lh / 2;
    ctx.lineWidth = 4; ctx.strokeStyle = "rgba(0,0,0,.55)"; ctx.fillStyle = "#fff"; ctx.lineJoin = "round";
    lines.forEach((l, i) => { ctx.strokeText(l, x, y0 + i * lh); ctx.fillText(l, x, y0 + i * lh); });
  }
  function drawFruit(f) {
    ctx.save(); ctx.translate(f.x, f.y); ctx.rotate(f.rot);
    ctx.fillStyle = f.color; ctx.beginPath(); ctx.arc(0, 0, f.r, 0, Math.PI * 2); ctx.fill();
    const g = ctx.createRadialGradient(-f.r * 0.35, -f.r * 0.35, f.r * 0.05, 0, 0, f.r);
    g.addColorStop(0, "rgba(255,255,255,.5)"); g.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(0, 0, f.r, 0, Math.PI * 2); ctx.fill();
    ctx.lineWidth = 3; ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.stroke();
    ctx.restore();
    drawLabel(f.label, f.x, f.y, f.r);
  }
  function drawPiece(p) {
    ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
    const a0 = p.half ? 0 : Math.PI, a1 = p.half ? Math.PI : Math.PI * 2;
    ctx.fillStyle = p.color; ctx.beginPath(); ctx.arc(0, 0, p.r, a0, a1); ctx.closePath(); ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,.55)"; ctx.beginPath(); ctx.arc(0, 0, p.r * 0.78, a0, a1); ctx.closePath(); ctx.fill();
    ctx.restore();
  }
  function draw() {
    ctx.clearRect(0, 0, W, H);
    ctx.save();
    if (shake > 0) ctx.translate(rnd(-shake, shake) * 0.5, rnd(-shake, shake) * 0.5);
    pieces.forEach(drawPiece);
    fruits.forEach(drawFruit);
    for (const q of parts) { ctx.globalAlpha = Math.max(q.life, 0); ctx.fillStyle = q.color; ctx.beginPath(); ctx.arc(q.x, q.y, 4, 0, Math.PI * 2); ctx.fill(); }
    ctx.globalAlpha = 1;
    for (let i = 1; i < trail.length; i++) {
      const a = trail[i - 1], b = trail[i], age = (performance.now() - b.t) / 180;
      ctx.strokeStyle = "rgba(160,220,255," + Math.max(1 - age, 0) + ")"; ctx.lineWidth = 6 * (1 - age) + 1; ctx.lineCap = "round";
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }
    ctx.font = "800 24px system-ui,sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    for (const t of floats) { ctx.globalAlpha = Math.max(t.life, 0); ctx.fillStyle = t.color; ctx.strokeStyle = "rgba(0,0,0,.6)"; ctx.lineWidth = 4;
      ctx.strokeText(t.txt, t.x, t.y); ctx.fillText(t.txt, t.x, t.y); }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  let last = performance.now();
  function loop(now) {
    const dt = Math.min(0.033, (now - last) / 1000); last = now;
    if (cfg) { update(dt); draw(); }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
})();
</script>
</body>
</html>
"""

_ninja_component = None


def _get_ninja():
    """Create the slash-game component. Writes index.html itself, so no extra folder is needed."""
    global _ninja_component
    if _ninja_component is None:
        folder = os.path.join(tempfile.gettempdir(), "riskwise_ninja_component")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "index.html"), "w", encoding="utf-8") as fh:
            fh.write(_NINJA_HTML)
        _ninja_component = components.declare_component("riskwise_ninja", path=folder)
    return _ninja_component


def _slash_questions(mode, rng):
    qs = []
    if mode == "slash_terms":
        for term, definition in rng.sample(TERMS, 8):
            others = [t for t, _ in TERMS if t != term]
            options = rng.sample(others, 3) + [term]
            rng.shuffle(options)
            qs.append({
                "prompt": f"Which term means: {definition}",
                "options": options, "answer": options.index(term),
                "why": f"{term}: {definition}",
            })
    elif mode == "slash_bb":
        for text, ans, why in rng.sample(STATEMENTS, 8):
            options = ["Bull case", "Bear case"]
            rng.shuffle(options)
            qs.append({"prompt": text, "options": options, "answer": options.index(ans), "why": why})
    else:
        for c in _make_companies(6, rng):
            truth = "Undervalued" if c["gap"] > 0.15 else ("Overvalued" if c["gap"] < -0.15 else "Fairly valued")
            options = ["Undervalued", "Fairly valued", "Overvalued"]
            rng.shuffle(options)
            prompt = (
                f"{c['name']} ({c['sector']}): price ${c['price']:,.2f} · FCF {_billions(c['fcf'])} · "
                f"growth {c['growth']:.1%} · WACC {c['wacc']:.1%} · terminal growth {c['tg']:.1%} · "
                f"net debt {_billions(c['net_debt'])} · {c['shares'] / 1e9:,.2f}B shares"
            )
            why = f"DCF fair value ${c['fair']:,.2f} vs price ${c['price']:,.2f} ({c['gap']:+.0%} gap)."
            qs.append({"prompt": prompt, "options": options, "answer": options.index(truth), "why": why})
    return qs


def _new_slash(mode):
    rid = f"{mode}-{random.randrange(10**9)}"
    rng = random.Random(rid)
    st.session_state.g_slash[mode] = {
        "rid": rid, "awarded": False, "res": None, "xp": 0,
        "cfg": {"title": SLASH_MODES[mode][0], "run_id": rid, "lives": 3, "seconds": 15,
                "questions": _slash_questions(mode, rng)},
    }


def _render_slash(mode):
    title, blurb = SLASH_MODES[mode]
    st.markdown(f"## {title}")
    st.write(blurb + " Move your mouse (or drag your finger) across the fruit to slash it.")
    comp = _get_ninja()
    st.session_state.setdefault("g_slash", {})
    if mode not in st.session_state.g_slash:
        _new_slash(mode)
    cur = st.session_state.g_slash[mode]

    res = comp(config=cur["cfg"], key=f"ninja_{cur['rid']}", default=None)

    if res and res.get("run_id") == cur["rid"] and not cur["awarded"]:
        cur["awarded"], cur["res"] = True, res
        correct, total = int(res.get("correct", 0)), int(res.get("total", 1))
        lives_left = int(res.get("lives_left", 0))
        cur["xp"] = correct * 8 + (20 if lives_left > 0 else 0) + (25 if correct == total else 0)
        _add_xp(cur["xp"])
        _badge("first_game")
        if lives_left > 0:
            _badge("blade")
        if int(res.get("best_combo", 0)) >= 5:
            _badge("combo")
        if correct == total:
            _badge("perfect")
        st.rerun()

    if cur["awarded"]:
        r = cur["res"]
        st.success(
            f"Round complete! Score **{int(r['score'])}**, **{int(r['correct'])} / {int(r['total'])}** "
            f"right on the first try, best combo **x{int(r['best_combo'])}**, **+{cur['xp']} XP**"
        )
        st.button("🔁 New round", key=f"{mode}_new", type="primary", on_click=_new_slash, args=(mode,))


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
        "🥷 Term Ninja": "slash_terms",
        "🥷 Bull/Bear Ninja": "slash_bb",
        "🥷 Valuation Ninja": "slash_val",
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
    elif pick == "bb":
        _run_game(
            "bb", "⚖️ Bull vs. Bear",
            "Does each fact help the bull case (reasons to own the stock) or the bear case (reasons to worry)?",
            6, _bb_make, _bb_input, _bb_grade, 8, on_finish=_fin_bb,
        )
    else:
        _render_slash(pick)
