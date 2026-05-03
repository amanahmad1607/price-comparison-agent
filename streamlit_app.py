"""
streamlit_app.py — Price Comparison Agent UI (Zepto + Blinkit)
Run: streamlit run streamlit_app.py
"""
import streamlit as st
import requests
import html
from datetime import datetime

st.set_page_config(page_title="Price Compare", page_icon="🛒", layout="wide")

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #f8f7f4; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1100px; }
#MainMenu, footer, header { visibility: hidden; }
.app-header { background:white; border-radius:16px; padding:28px 32px; margin-bottom:24px; border:1px solid #e8e6df; }
.app-title  { font-size:28px; font-weight:600; color:#1a1a18; margin-bottom:4px; }
.app-sub    { font-size:15px; color:#6b6a64; }
.platform-card        { background:white; border-radius:14px; padding:20px; border:1.5px solid #e8e6df; }
.platform-card.winner { border-color:#1D9E75; background:#f0fdf8; }
.plat-label  { font-size:11px; font-weight:700; letter-spacing:.06em; color:#888780; text-transform:uppercase; margin-bottom:10px; }
.price-big   { font-size:34px; font-weight:600; color:#1a1a18; line-height:1; margin:8px 0 4px; }
.ppu         { font-size:12px; color:#888780; margin-bottom:12px; }
.prod-name   { font-size:13px; color:#444441; line-height:1.5; margin-bottom:10px; }
.delivery    { font-size:12px; color:#6b6a64; margin-top:6px; }
.badge              { display:inline-block; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; margin-bottom:8px; }
.badge-cheapest     { background:#E1F5EE; color:#085041; }
.badge-fastest      { background:#EEEDFE; color:#3C3489; }
.badge-value        { background:#FAEEDA; color:#633806; }
.summary-bar  { background:white; border-radius:12px; padding:16px 20px; border:1px solid #e8e6df; margin-bottom:20px; }
.summary-item { display:inline-block; font-size:13px; color:#6b6a64; margin-right:28px; }
.summary-item strong { color:#1a1a18; font-weight:500; }
.meta-tag   { display:inline-block; padding:3px 10px; border-radius:20px; font-size:12px; font-weight:500; margin-right:6px; }
.meta-cache { background:#EEEDFE; color:#3C3489; }
.meta-miss  { background:#F1EFE8; color:#5F5E5A; }
.meta-time  { background:#F1EFE8; color:#5F5E5A; }
.stTextInput input { border-radius:10px !important; border:1.5px solid #d3d1c7 !important; font-size:15px !important; }
.stButton button { background:#534AB7 !important; color:white !important; border-radius:10px !important; border:none !important; font-size:15px !important; font-weight:500 !important; width:100% !important; }
.stButton button:hover { background:#3C3489 !important; }
[data-testid="stLinkButton"] a { background:transparent !important; color:#534AB7 !important; border:1.5px solid #534AB7 !important; border-radius:8px !important; font-size:13px !important; font-weight:500 !important; padding:6px 12px !important; text-decoration:none !important; display:block !important; text-align:center !important; margin-top:8px !important; }
[data-testid="stLinkButton"] a:hover { background:#EEEDFE !important; }
.plat-pill-zepto   { background:#E8F4FD; color:#185FA5; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:600; }
.plat-pill-blinkit { background:#FFF3E0; color:#E65100; padding:2px 8px; border-radius:20px; font-size:11px; font-weight:600; }
.empty-card { background:white; border-radius:12px; padding:24px; border:1px solid #e8e6df; text-align:center; }
</style>
""", unsafe_allow_html=True)

# ── Config ─────────────────────────────────────────────────────────────────────
API_URL = "https://aman16072002-price-comparison-agent.hf.space/compare"
TIMEOUT = 90   # HF Space can take up to 30s to wake + 15s to scrape

PINCODE_CITIES = {
    "560001": "Bengaluru", "400001": "Mumbai", "110001": "Delhi",
    "600001": "Chennai",   "500001": "Hyderabad", "700001": "Kolkata",
    "411001": "Pune",      "380001": "Ahmedabad",
}
EMOJIS = {"zepto": "⚡", "blinkit": "🟠"}
BADGE_MAP = {
    "Cheapest":         '<span class="badge badge-cheapest">Cheapest</span><br>',
    "Fastest delivery": '<span class="badge badge-fastest">Fastest delivery</span><br>',
    "Best value":       '<span class="badge badge-value">Best value</span><br>',
}


def call_api(query: str, pincode: str, platforms: list) -> dict | None:
    """Call the Hugging Face API with proper error handling."""
    try:
        resp = requests.post(
            API_URL,
            json={"query": query, "pincode": pincode or None, "platforms": platforms},
            timeout=TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json()
        st.error(f"API error {resp.status_code}: {resp.text[:200]}")
        return None
    except requests.exceptions.Timeout:
        st.error(
            "⏱️ Request timed out. The Hugging Face Space may be waking up — "
            "please wait 30 seconds and try again."
        )
        return None
    except requests.exceptions.ConnectionError:
        st.error(
            "❌ Cannot connect to the API at Hugging Face. "
            "Check: https://huggingface.co/spaces/aman16072002/price-comparison-agent"
        )
        return None
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <div class="app-title">🛒 Price Compare</div>
  <div class="app-sub">Compare grocery prices across Zepto &amp; Blinkit in real-time</div>
</div>
""", unsafe_allow_html=True)

# ── Search form ────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns([4, 2, 2, 1.2])
with c1:
    query = st.text_input("Product", placeholder="e.g. Maggi 70g, Amul milk 500ml", label_visibility="collapsed")
with c2:
    pincode = st.text_input("Pincode", value="560001", max_chars=6, label_visibility="collapsed")
with c3:
    plat_sel = st.selectbox("Platform", ["Both platforms", "zepto", "blinkit"], label_visibility="collapsed")
with c4:
    go = st.button("Compare", use_container_width=True)

if pincode in PINCODE_CITIES:
    st.caption(f"📍 {PINCODE_CITIES[pincode]}")

# Session state
if "history" not in st.session_state:
    st.session_state.history = []
if "result" not in st.session_state:
    st.session_state.result = None

# Recent searches
if st.session_state.history:
    st.markdown("**Recent:**")
    rcols = st.columns(min(len(st.session_state.history), 6))
    for i, h in enumerate(st.session_state.history[-6:]):
        with rcols[i]:
            if st.button(h, key=f"h{i}"):
                query = h
                go = True

# Platform filter
plat_filter = [] if plat_sel == "Both platforms" else [plat_sel]

# ── API call ──────────────────────────────────────────────────────────────────
if go and query.strip():
    if query not in st.session_state.history:
        st.session_state.history.append(query)
    with st.spinner("Searching Zepto and Blinkit... (first request may take ~30s)"):
        st.session_state.result = call_api(query.strip(), pincode, plat_filter)

# ── Results ───────────────────────────────────────────────────────────────────
result = st.session_state.result
if result:
    comp       = result.get("comparison")
    cache_hit  = result.get("cache_hit", False)
    duration   = result.get("duration_ms", 0)
    error      = result.get("error")
    plats_srch = result.get("platforms_searched", [])
    plats_fail = result.get("platforms_failed", [])

    cache_lbl = '<span class="meta-tag meta-cache">⚡ Cache hit</span>' if cache_hit else '<span class="meta-tag meta-miss">🔄 Live fetch</span>'
    st.markdown(f'<div style="margin-bottom:14px">{cache_lbl}<span class="meta-tag meta-time">⏱ {duration:.0f}ms</span></div>', unsafe_allow_html=True)

    if not comp:
        st.error(error or "No products found on Zepto or Blinkit.")
    else:
        summaries  = comp.get("platform_summaries", [])
        cheapest   = comp.get("cheapest_platform")
        fastest    = comp.get("fastest_delivery_platform")
        plats_with = comp.get("platforms_with_results", [])

        spread = 0
        if len(summaries) > 1:
            prices = [s["best_price"] for s in summaries]
            spread = max(prices) - min(prices)

        cheapest_price = next((s["best_price"] for s in summaries if s["platform"] == cheapest), 0)
        fastest_time   = next((s.get("delivery_time_min") for s in summaries if s["platform"] == fastest), None)

        bar = '<div class="summary-bar">'
        if cheapest:
            bar += f'<span class="summary-item">Cheapest: <strong>{cheapest.capitalize()} &#8377;{cheapest_price:.0f}</strong></span>'
        if fastest and fastest_time:
            bar += f'<span class="summary-item">Fastest: <strong>{fastest.capitalize()} {fastest_time} min</strong></span>'
        if spread > 0:
            bar += f'<span class="summary-item">Price spread: <strong>&#8377;{spread:.2f}</strong></span>'
        bar += f'<span class="summary-item">Platforms with results: <strong>{len(plats_with)}/{len(plats_srch)}</strong></span>'
        bar += '</div>'
        st.markdown(bar, unsafe_allow_html=True)

        if not summaries:
            st.warning("No products found.")
        else:
            cols = st.columns(len(summaries))
            for i, s in enumerate(summaries):
                platform  = s["platform"]
                is_winner = platform == cheapest
                emoji     = EMOJIS.get(platform, "•")
                price     = s["best_price"]
                mrp       = s.get("mrp", price)
                disc      = s.get("discount_pct", 0)

                badge_html = BADGE_MAP.get(s.get("badge", ""), "")
                mrp_html = (
                    f'<span style="font-size:12px;color:#b4b2a9;text-decoration:line-through">&#8377;{mrp:.0f}</span> '
                    f'<span style="font-size:12px;color:#0F6E56;font-weight:500">{disc:.0f}% off</span><br>'
                ) if disc > 0 and mrp > price else ""

                ppu       = html.escape(s.get("price_per_unit_label", ""))
                prod_name = html.escape(s.get("best_product_name", ""))
                if len(prod_name) > 70:
                    prod_name = prod_name[:70] + "..."
                safe_url  = html.escape(s.get("best_product_url", "#"), quote=True)
                deliv     = s.get("delivery_time_min")
                deliv_html = f'<div class="delivery">🕐 {deliv} min delivery</div>' if deliv else ""
                card_class = "platform-card winner" if is_winner else "platform-card"

                with cols[i]:
                    st.markdown(
                        f'<div class="{card_class}">'
                        f'<div class="plat-label">{emoji} {platform.capitalize()}</div>'
                        f'{badge_html}'
                        f'<div class="price-big">&#8377;{price:.2f}</div>'
                        f'<div class="ppu">{ppu}</div>'
                        f'{mrp_html}'
                        f'<div class="prod-name">{prod_name}</div>'
                        f'{deliv_html}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if safe_url and safe_url != "#":
                        st.link_button("View product →", safe_url, use_container_width=True)

        if plats_fail:
            st.markdown(
                f'<div style="margin-top:12px;font-size:12px;color:#A32D2D">'
                f'⚠️ No results from: {", ".join(p.capitalize() for p in plats_fail)}</div>',
                unsafe_allow_html=True,
            )

        all_prods = comp.get("all_products", [])
        if all_prods:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander(f"📋 All {len(all_prods)} products", expanded=False):
                sorted_prods = sorted(all_prods, key=lambda x: x["selling_price"])
                hc = st.columns([3.5, 1.5, 1, 1, 1.5])
                for col, lbl in zip(hc, ["**Product**","**Platform**","**Price**","**MRP**","**Per unit**"]):
                    col.markdown(lbl)
                st.divider()
                for p in sorted_prods:
                    rc    = st.columns([3.5, 1.5, 1, 1, 1.5])
                    name  = html.escape(p["name"][:55] + ("..." if len(p["name"]) > 55 else ""))
                    brand = html.escape(p.get("brand") or "")
                    plat  = p["platform"]
                    ppu_t = html.escape(p.get("price_per_unit_label", ""))
                    rc[0].markdown(f'<div style="font-size:13px">{name}</div><div style="font-size:11px;color:#888">{brand}</div>', unsafe_allow_html=True)
                    rc[1].markdown(f'<span class="plat-pill-{plat}">{plat.capitalize()}</span>', unsafe_allow_html=True)
                    rc[2].markdown(f"**&#8377;{p['selling_price']:.2f}**")
                    rc[3].markdown(f'<span style="color:#b4b2a9;text-decoration:line-through">&#8377;{p["mrp"]:.0f}</span>', unsafe_allow_html=True)
                    rc[4].markdown(f'<span style="font-size:12px;color:#6b6a64">{ppu_t}</span>', unsafe_allow_html=True)

        ck  = comp.get("cache_key", "")
        gat = comp.get("generated_at", "")
        if ck:
            try:
                fmt = datetime.fromisoformat(gat.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M UTC")
            except Exception:
                fmt = gat
            st.markdown(f'<div style="margin-top:16px;font-size:11px;color:#b4b2a9">Data: {fmt} · Cache key: {ck}</div>', unsafe_allow_html=True)

else:
    # Empty state
    st.markdown("<br>", unsafe_allow_html=True)
    ec1, ec2, ec3 = st.columns(3)
    for col, icon, title, desc in [
        (ec1, "⚡", "Real-time prices",  "Live Playwright scraping from Zepto &amp; Blinkit"),
        (ec2, "🔄", "Smart caching",     "Repeated queries return in &lt;500ms via Redis"),
        (ec3, "🏷️", "Price-per-unit",   "True value comparison across different pack sizes"),
    ]:
        with col:
            st.markdown(
                f'<div class="empty-card">'
                f'<div style="font-size:28px;margin-bottom:8px">{icon}</div>'
                f'<div style="font-weight:500;margin-bottom:4px;color:#1a1a18">{title}</div>'
                f'<div style="font-size:13px;color:#6b6a64">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>**Try these:**", unsafe_allow_html=True)
    examples = [
        "Maggi masala noodles 70g", "Amul toned milk 500ml", "Lay's Classic chips",
        "Parle-G biscuits 800g",    "Tata Salt 1kg",         "Britannia bread",
    ]
    ecols = st.columns(3)
    for i, ex in enumerate(examples):
        with ecols[i % 3]:
            if st.button(ex, key=f"ex{i}"):
                st.session_state["_eq"] = ex
                st.rerun()

# Handle example query clicks
if "_eq" in st.session_state:
    eq = st.session_state.pop("_eq")
    if eq not in st.session_state.history:
        st.session_state.history.append(eq)
    with st.spinner("Searching... (first request may take ~30s)"):
        st.session_state.result = call_api(eq, "560001", [])
    st.rerun()
