import re
from collections import Counter
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Universal Broker Log Analyzer",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp{background:#0f172a;color:#e5e7eb}
section[data-testid="stSidebar"]{background:#020617;border-right:1px solid #1e293b}
h1,h2,h3,h4,h5,h6,p,label,span{color:#e5e7eb!important}
.stTextArea textarea{background:#0f172a!important;color:white!important;border:1px solid #475569!important;border-radius:14px!important;font-family:Consolas,monospace!important;font-size:14px!important}
.stFileUploader{background:#0f172a!important;border-radius:16px!important;padding:16px!important;border:1px dashed #64748b!important}
.stButton button{background:linear-gradient(90deg,#2563eb,#7c3aed)!important;color:white!important;border-radius:14px!important;height:50px;font-weight:800;border:none!important}
.card{background:rgba(15,23,42,.96);border:1px solid #334155;border-radius:20px;padding:22px;margin-bottom:18px;box-shadow:0 15px 35px rgba(0,0,0,.35)}
.metric-card{background:linear-gradient(135deg,#111827,#1e293b);border:1px solid #334155;border-radius:18px;padding:20px}
.metric-label{color:#94a3b8!important;font-size:13px}
.metric-value{color:white!important;font-size:22px;font-weight:900}
.success{background:rgba(34,197,94,.14);border:1px solid rgba(34,197,94,.5);border-radius:16px;padding:18px}
.warning{background:rgba(234,179,8,.14);border:1px solid rgba(234,179,8,.5);border-radius:16px;padding:18px}
.danger{background:rgba(239,68,68,.16);border:1px solid rgba(239,68,68,.55);border-radius:16px;padding:18px}
.info{background:rgba(59,130,246,.14);border:1px solid rgba(59,130,246,.5);border-radius:16px;padding:18px}
code{color:#93c5fd!important}
</style>
""", unsafe_allow_html=True)

FIX_MSG_TYPES = {
    "0": "Heartbeat", "1": "Test Request", "2": "Resend Request", "3": "Session Reject",
    "4": "Sequence Reset", "5": "Logout", "A": "Logon", "D": "New Order Single",
    "8": "Execution Report", "9": "Order Cancel Reject", "F": "Order Cancel Request",
    "G": "Order Cancel Replace Request", "j": "Business Message Reject",
    "V": "Market Data Request", "W": "Market Data Snapshot",
    "X": "Market Data Incremental Refresh", "Y": "Market Data Request Reject",
    "R": "Quote Request", "S": "Quote", "i": "Mass Quote",
}

ORDER_STATUS = {
    "0": "New", "1": "Partially Filled", "2": "Filled", "4": "Cancelled",
    "8": "Rejected", "A": "Pending New",
}
EXEC_TYPE = {
    "0": "New", "1": "Partial Fill", "2": "Fill", "F": "Trade",
    "4": "Cancelled", "8": "Rejected", "A": "Pending New",
}
SIDE = {"1": "BUY", "2": "SELL"}

KB = {
    "SLIPPAGE_DETECTED": {
        "title": "Slippage Detected",
        "severity": "High",
        "source": "Liquidity / Market Depth / LP Execution",
        "meaning": "The order was executed at a different average price than the requested price.",
        "causes": [
            "Market order executed against available liquidity levels",
            "Full volume was not available at requested price",
            "Fast market movement",
            "Low depth from LP",
            "Large order size compared to available liquidity",
        ],
        "actions": [
            "Check market depth at execution time",
            "Compare LP top-of-book and depth",
            "Check bridge routing and slippage settings",
            "Review whether order was market order",
            "Ask LP for execution report / depth snapshot",
        ],
        "client": "The order was executed at available market prices. The full quantity was not available at the requested price, so the remaining volume was filled at the next available levels, causing slippage.",
    },
    "PRODUCT_NOT_EXIST": {
        "title": "Product / Symbol Does Not Exist",
        "severity": "High",
        "source": "LP / Symbol Mapping",
        "meaning": "The requested symbol is not available, not enabled, or incorrectly mapped.",
        "causes": ["Symbol not enabled on LP", "Wrong bridge symbol mapping", "Market data subscription missing"],
        "actions": ["Check LP symbol list", "Verify bridge symbol mapping", "Confirm product is enabled for FIX session"],
        "client": "The product is not available from the liquidity side or the symbol mapping is incorrect.",
    },
    "NO_PRICE": {
        "title": "No Price / No Liquidity",
        "severity": "High",
        "source": "LP / Market Data",
        "meaning": "No executable price was available.",
        "causes": ["LP not streaming price", "Market closed", "Symbol session disabled", "No liquidity"],
        "actions": ["Check LP price feed", "Check symbol session", "Check bridge market data route"],
        "client": "The order could not execute because executable market price was not available.",
    },
    "MARKET_CLOSED": {
        "title": "Market Closed",
        "severity": "High",
        "source": "Symbol Session",
        "meaning": "Trading was attempted outside allowed market hours.",
        "causes": ["Market closed", "Holiday", "Trading disabled"],
        "actions": ["Check MT5 symbol session", "Check LP holiday schedule", "Verify group permissions"],
        "client": "The order was not executed because market/session was closed.",
    },
    "INVALID_ACCOUNT": {
        "title": "Invalid Account / Permission Issue",
        "severity": "High",
        "source": "Account / Group / FIX",
        "meaning": "The trading account is not recognized or not allowed to trade.",
        "causes": ["Wrong FIX account tag", "Account not mapped", "Trading disabled"],
        "actions": ["Check FIX tag 1", "Check bridge account mapping", "Check MT5 trading permission"],
        "client": "The order was rejected due to account or permission validation.",
    },
    "INSUFFICIENT_MARGIN": {
        "title": "Insufficient Margin",
        "severity": "High",
        "source": "MT4 / MT5 Margin Engine",
        "meaning": "The account did not have enough free margin.",
        "causes": ["Low free margin", "Large volume", "High margin requirement"],
        "actions": ["Check equity/free margin", "Check symbol margin settings", "Check leverage/group"],
        "client": "The order could not complete because account free margin was not enough.",
    },
    "TIMEOUT": {
        "title": "Timeout / No Response",
        "severity": "Medium",
        "source": "Network / Bridge / LP",
        "meaning": "The request did not receive response in expected time.",
        "causes": ["LP delay", "Bridge delay", "Network latency"],
        "actions": ["Check LP response time", "Check bridge logs", "Check FIX heartbeat"],
        "client": "The request did not receive a response within expected time.",
    },
    "SESSION_DISCONNECT": {
        "title": "FIX Session Disconnect / Logout",
        "severity": "High",
        "source": "FIX Session / Network",
        "meaning": "FIX connection disconnected or became unstable.",
        "causes": ["Heartbeat timeout", "Network issue", "Sequence reset"],
        "actions": ["Check heartbeat", "Check sequence numbers", "Restart FIX session if required"],
        "client": "There was a connectivity/session issue during this period.",
    },
    "PARTIAL_FILL": {
        "title": "Partial Fill",
        "severity": "Low",
        "source": "Liquidity / Market Depth",
        "meaning": "Only part of requested quantity was filled initially.",
        "causes": ["Liquidity split", "Order filled in multiple levels", "Large quantity"],
        "actions": ["Check market depth", "Check final fill status", "Explain partial fills are normal"],
        "client": "The order was filled in parts due to available liquidity.",
    },
    "ORDER_REJECTED": {
        "title": "Order Rejected",
        "severity": "High",
        "source": "Bridge / LP / Platform",
        "meaning": "Order was not accepted by execution system.",
        "causes": ["Invalid symbol", "Invalid account", "Market closed", "No price", "LP rejected"],
        "actions": ["Check tag 58", "Check bridge route", "Check symbol/account mapping"],
        "client": "The order was rejected by the execution system.",
    },
}

SAMPLE_LOG = """20260622-19:50:34.746748000 [out] : 8=FIX.4.4 |9=154 |35=D |34=5468 |49=T116 |52=20260622-19:50:34.746 |56=XC691 |1=AVT_5173 |11=194062_1 |38=50 |40=1 |44=51800.620000 |54=2 |55=US30 |60=20260622-19:50:34.746 |526=100142 |10=041 |
20260622-19:50:34.749376000 [in] : 8=FIX.4.4 |9=186 |35=8 |34=5797 |49=XC691 |52=20260622-19:50:34.749 |56=T116 |11=194062_1 |14=0.0 |15=USD |17=0 |37=2871571 |38=50.0 |39=0 |40=1 |44=51800.62 |54=2 |55=US30 |60=20260622-19:50:34.747 |110=0 |150=0 |151=50.0 |10=097 |
20260622-19:50:34.763361000 [in] : 8=FIX.4.4 |9=236 |35=8 |34=5798 |49=XC691 |52=20260622-19:50:34.763 |56=T116 |6=51800.7 |11=194062_1 |14=3.0 |15=USD |17=2871571_0_0 |31=51800.7 |32=3.0 |37=2871571 |38=50.0 |39=1 |40=1 |44=51800.62 |54=2 |55=US30 |60=20260622-19:50:34.763 |64=20260622 |110=0 |150=F |151=47.0 |10=033 |
20260622-19:50:34.764447000 [in] : 8=FIX.4.4 |9=240 |35=8 |34=5799 |49=XC691 |52=20260622-19:50:34.764 |56=T116 |6=51800.07 |11=194062_1 |14=33.0 |15=USD |17=2871571_1_0 |31=51800.01 |32=30.0 |37=2871571 |38=50.0 |39=1 |40=1 |44=51800.62 |54=2 |55=US30 |60=20260622-19:50:34.764 |64=20260622 |110=0 |150=F |151=17.0 |10=218 |
20260622-19:50:34.764559000 [in] : 8=FIX.4.4 |9=237 |35=8 |34=5800 |49=XC691 |52=20260622-19:50:34.764 |56=T116 |6=51798.21 |11=194062_1 |14=50.0 |15=USD |17=2871571_2_0 |31=51794.61 |32=17.0 |37=2871571 |38=50.0 |39=2 |40=1 |44=51800.62 |54=2 |55=US30 |60=20260622-19:50:34.764 |64=20260622 |110=0 |150=F |151=0 |10=093 |"""


def normalize_fix(text):
    return text.replace("\x01", "|").replace("", "|").replace("␁", "|").replace("^A", "|")


def detect_timestamp(line):
    for pattern in [
        r"(\d{8}-\d{2}:\d{2}:\d{2}\.\d+)",
        r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)",
        r"(\d{2}:\d{2}:\d{2}(?:\.\d+)?)",
    ]:
        m = re.search(pattern, line)
        if m:
            return m.group(1)
    return ""


def detect_direction(line):
    low = line.lower()
    if "[in]" in low or "received" in low:
        return "IN"
    if "[out]" in low or "sent" in low:
        return "OUT"
    return "UNKNOWN"


def parse_key_values(line):
    data = {}
    part = line.split(":", 1)[-1] if "|" in line else line
    for item in part.split("|"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            data[k.strip()] = v.strip()
    return data


def to_float(v):
    try:
        return float(str(v).strip())
    except Exception:
        return None


def is_fix_line(line):
    line = normalize_fix(line)
    return "8=FIX" in line or "|35=" in line


def detect_log_type(text):
    low = normalize_fix(text).lower()
    if "8=fix" in low or "|35=" in low:
        if "|35=v" in low or "|35=y" in low:
            return "FIX Market Data / Reject"
        if "|35=d" in low or "|35=8" in low:
            return "FIX Order / Execution"
        if "|35=a" in low or "|35=5" in low or "|35=3" in low:
            return "FIX Session"
        return "FIX General"
    if "centroid" in low:
        return "Centroid Bridge Log"
    if "fxcubic" in low:
        return "FXCubic Bridge Log"
    if "onezero" in low:
        return "OneZero Bridge Log"
    if "primexm" in low or "prime xm" in low:
        return "PrimeXM Bridge Log"
    if "mt5" in low or "metatrader 5" in low:
        return "MT5 Journal / Server Log"
    if "mt4" in low or "metatrader 4" in low:
        return "MT4 Journal / Server Log"
    if any(x in low for x in ["error", "reject", "failed", "timeout", "exception"]):
        return "Generic Error Log"
    return "Generic Log"


def classify_line(line, kv):
    low = line.lower()
    if is_fix_line(line):
        return FIX_MSG_TYPES.get(kv.get("35", ""), f"FIX Message {kv.get('35', '')}")
    if any(x in low for x in ["reject", "rejected", "does not exist", "invalid", "not found"]):
        return "Reject / Validation Issue"
    if any(x in low for x in ["error", "exception", "failed", "failure"]):
        return "Error"
    if "timeout" in low or "timed out" in low:
        return "Timeout"
    if "disconnect" in low or "logout" in low:
        return "Connectivity"
    if "filled" in low or "executed" in low:
        return "Execution"
    if "margin" in low or "stop out" in low:
        return "Margin / Stop-Out"
    if "price" in low or "quote" in low:
        return "Pricing / Market Data"
    return "Information"


def detect_severity(line, event):
    low = line.lower()
    if any(x in low for x in ["reject", "rejected", "error", "failed", "exception", "does not exist", "invalid"]):
        return "High"
    if any(x in low for x in ["timeout", "disconnect", "cancelled", "warning", "partial"]):
        return "Medium"
    if event in ["Reject / Validation Issue", "Error"]:
        return "High"
    return "Low"


def parse_any_logs(text):
    text = normalize_fix(text)
    rows = []

    for idx, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue

        kv = parse_key_values(line)
        event = classify_line(line, kv)

        rows.append({
            "Line": idx,
            "Time": detect_timestamp(line),
            "Direction": detect_direction(line),
            "Event": event,
            "Severity": detect_severity(line, event),
            "FIX MsgType": kv.get("35", ""),
            "FIX MsgType Name": FIX_MSG_TYPES.get(kv.get("35", ""), kv.get("35", "")),
            "Symbol": kv.get("55") or kv.get("48") or kv.get("262") or "",
            "Account": kv.get("1", ""),
            "Order ID": kv.get("37") or kv.get("11") or "",
            "Sender": kv.get("49", ""),
            "Target": kv.get("56", ""),
            "Message": kv.get("58", ""),
            "Side": SIDE.get(kv.get("54", ""), kv.get("54", "")),
            "Order Qty": kv.get("38", ""),
            "Requested Price": kv.get("44", ""),
            "Last Qty": kv.get("32", ""),
            "Last Price": kv.get("31", ""),
            "Avg Price": kv.get("6", ""),
            "Cum Qty": kv.get("14", ""),
            "Leaves Qty": kv.get("151", ""),
            "Status": ORDER_STATUS.get(kv.get("39", ""), kv.get("39", "")),
            "Execution": EXEC_TYPE.get(kv.get("150", ""), kv.get("150", "")),
            "Raw": line,
        })

    return pd.DataFrame(rows)


def calculate_slippage(df):
    if df.empty:
        return None

    order_rows = df[df["FIX MsgType"] == "D"]
    exec_rows = df[df["FIX MsgType"] == "8"]

    if order_rows.empty or exec_rows.empty:
        return None

    first_order = order_rows.iloc[0]
    side = first_order.get("Side", "")
    requested_price = to_float(first_order.get("Requested Price"))
    order_qty = to_float(first_order.get("Order Qty"))

    filled_rows = exec_rows[
        (exec_rows["Last Price"].astype(str) != "") &
        (exec_rows["Last Qty"].astype(str) != "")
    ].copy()

    if filled_rows.empty or requested_price is None:
        return None

    filled_rows["LastPriceFloat"] = filled_rows["Last Price"].apply(to_float)
    filled_rows["LastQtyFloat"] = filled_rows["Last Qty"].apply(to_float)
    filled_rows = filled_rows.dropna(subset=["LastPriceFloat", "LastQtyFloat"])

    if filled_rows.empty:
        return None

    total_qty = filled_rows["LastQtyFloat"].sum()
    weighted_value = (filled_rows["LastPriceFloat"] * filled_rows["LastQtyFloat"]).sum()
    avg_fill = weighted_value / total_qty if total_qty else None

    if avg_fill is None:
        return None

    if side == "BUY":
        slippage_points = avg_fill - requested_price
        positive = slippage_points < 0
        worst_fill = filled_rows["LastPriceFloat"].max()
    elif side == "SELL":
        slippage_points = requested_price - avg_fill
        positive = slippage_points < 0
        worst_fill = filled_rows["LastPriceFloat"].min()
    else:
        slippage_points = abs(avg_fill - requested_price)
        positive = False
        worst_fill = filled_rows["LastPriceFloat"].iloc[-1]

    direction = "Positive Slippage" if positive else "Negative Slippage" if slippage_points > 0 else "No Slippage"
    estimated_impact = None

    return {
        "detected": abs(slippage_points) > 0,
        "side": side,
        "requested_price": requested_price,
        "avg_fill_price": round(avg_fill, 6),
        "slippage_points": round(abs(slippage_points), 6),
        "direction": direction,
        "worst_fill_price": round(worst_fill, 6),
        "filled_qty": total_qty,
        "order_qty": order_qty,
        "estimated_impact": None,
        "fills": filled_rows[["Line", "LastQtyFloat", "LastPriceFloat", "Cum Qty", "Avg Price"]].rename(
            columns={"LastQtyFloat": "Fill Qty", "LastPriceFloat": "Fill Price"}
        ),
    }


def classify_issues(text, df, slip):
    low = text.lower()
    issues = []

    if slip and slip["detected"] and slip["slippage_points"] > 0:
        issues.append("SLIPPAGE_DETECTED")
    if "product does not exist" in low or "unknown symbol" in low or "invalid symbol" in low:
        issues.append("PRODUCT_NOT_EXIST")
    if "no price" in low or "no prices" in low or "off quotes" in low or "no liquidity" in low:
        issues.append("NO_PRICE")
    if "market closed" in low or "session closed" in low or "trade is disabled" in low:
        issues.append("MARKET_CLOSED")
    if "invalid account" in low or "account not found" in low or "not authorized" in low:
        issues.append("INVALID_ACCOUNT")
    if "not enough money" in low or "insufficient margin" in low or "stop out" in low:
        issues.append("INSUFFICIENT_MARGIN")
    if "timeout" in low or "timed out" in low or "no response" in low:
        issues.append("TIMEOUT")
    if "logout" in low or "disconnected" in low or "heartbeat timeout" in low:
        issues.append("SESSION_DISCONNECT")
    if "39=1" in low or "150=1" in low:
        issues.append("PARTIAL_FILL")
    if "39=8" in low or "150=8" in low or "35=j" in low or "rejected" in low:
        issues.append("ORDER_REJECTED")

    final = []
    for x in issues:
        if x not in final:
            final.append(x)
    return final


def build_summary(df, text):
    slip = calculate_slippage(df)
    issues = classify_issues(text, df, slip)

    log_type = detect_log_type(text)
    high = len(df[df["Severity"] == "High"])
    medium = len(df[df["Severity"] == "Medium"])
    low_count = len(df[df["Severity"] == "Low"])

    symbols = [x for x in df["Symbol"].dropna().astype(str).tolist() if x and x != "[N/A]"]
    accounts = [x for x in df["Account"].dropna().astype(str).tolist() if x]
    senders = [x for x in df["Sender"].dropna().astype(str).tolist() if x]
    targets = [x for x in df["Target"].dropna().astype(str).tolist() if x]

    main_symbol = Counter(symbols).most_common(1)[0][0] if symbols else "-"
    main_account = Counter(accounts).most_common(1)[0][0] if accounts else "-"
    main_sender = Counter(senders).most_common(1)[0][0] if senders else "-"
    main_target = Counter(targets).most_common(1)[0][0] if targets else "-"

    primary = issues[0] if issues else None

    if primary:
        kb = KB[primary]
        severity = kb["severity"]
        source = kb["source"]
        root = kb["meaning"]
        action = " | ".join(kb["actions"][:3])
        key = kb["title"]
    else:
        severity = "High" if high else "Medium" if medium else "Low"
        source = "No clear issue source detected"
        root = "No clear critical issue detected."
        action = "Review decoded logs for confirmation."
        key = "No critical message found"

    simple = (
        f"Log type: {log_type}. Parsed lines: {len(df)}. "
        f"Main symbol/product: {main_symbol}. Likely source: {source}."
    )

    if slip and slip["detected"]:
        simple += (
            f" Slippage detected: {slip['direction']} of {slip['slippage_points']} points. "
            f"Requested price: {slip['requested_price']}. Average fill: {slip['avg_fill_price']}. "
            f"Worst fill: {slip['worst_fill_price']}. Filled quantity: {slip['filled_qty']}."
        )

    return {
        "Log Type": log_type,
        "Severity": severity,
        "High": high,
        "Medium": medium,
        "Low": low_count,
        "Main Symbol": main_symbol,
        "Main Account": main_account,
        "Main Sender": main_sender,
        "Main Target": main_target,
        "Issue Source": source,
        "Root Cause": root,
        "Action": action,
        "Simple Summary": simple,
        "Key Message": key,
        "Detected Issues": issues,
        "Primary Issue": primary,
        "Slippage": slip,
    }


def create_report(summary, df):
    slip = summary["Slippage"]

    report = f"""UNIVERSAL BROKER LOG ANALYSIS REPORT

Log Type: {summary['Log Type']}
Severity: {summary['Severity']}
Main Symbol/Product: {summary['Main Symbol']}
Main Account: {summary['Main Account']}
Sender: {summary['Main Sender']}
Target: {summary['Main Target']}

Simple Summary:
{summary['Simple Summary']}

Issue Source:
{summary['Issue Source']}

Root Cause:
{summary['Root Cause']}

Recommended Action:
{summary['Action']}

Detected Issues:
{", ".join(summary["Detected Issues"]) if summary["Detected Issues"] else "No known issue matched"}
"""

    if slip:
        report += f"""

SLIPPAGE ANALYSIS:
Side: {slip['side']}
Requested Price: {slip['requested_price']}
Average Fill Price: {slip['avg_fill_price']}
Worst Fill Price: {slip['worst_fill_price']}
Slippage: {slip['slippage_points']} points
Slippage Direction: {slip['direction']}
Filled Quantity: {slip['filled_qty']}

"""

    report += "\nTimeline:\n"
    for _, row in df.iterrows():
        msg = row["Message"] or row["Event"]
        report += f"\nLine {row['Line']} | {row['Time']} | {row['Event']} | {row['Severity']} | {msg}"

    return report


with st.sidebar:
    st.markdown("## 🧠 Universal Log Analyzer")
    st.caption("Broker log analyzer with slippage detection.")
    st.divider()

    mode = st.radio("Input Mode", ["Paste Logs", "Upload File", "Use Sample"], index=0)

    st.divider()
    st.markdown("### Supported")
    st.markdown("""
- FIX Order Logs
- FIX Market Data Logs
- FIX Session Logs
- MT4 / MT5 Logs
- Bridge Logs
- LP Logs
- Any Error Logs
""")


st.markdown("# 🧠 Universal Broker Log Analyzer")

log_text = ""

st.markdown('<div class="card">', unsafe_allow_html=True)

if mode == "Paste Logs":
    log_text = st.text_area("Paste any logs here", height=300)
elif mode == "Upload File":
    uploaded = st.file_uploader("Upload log file", type=["txt", "log", "fix", "csv"])
    if uploaded:
        log_text = uploaded.read().decode("utf-8", errors="ignore")
else:
    log_text = SAMPLE_LOG
    st.text_area("Sample logs", value=SAMPLE_LOG, height=300)

st.markdown("</div>", unsafe_allow_html=True)

if st.button("🚀 Analyze Logs", use_container_width=True):
    if not log_text.strip():
        st.warning("Please paste or upload logs first.")
        st.stop()

    df = parse_any_logs(log_text)

    if df.empty:
        st.error("No readable logs found.")
        st.stop()

    summary = build_summary(df, log_text)
    slip = summary["Slippage"]

    col1, col2, col3, col4 = st.columns(4)
    metrics = [
        ("Log Type", summary["Log Type"]),
        ("Severity", summary["Severity"]),
        ("Issue", summary["Key Message"]),
        ("Symbol", summary["Main Symbol"]),
    ]

    for col, item in zip([col1, col2, col3, col4], metrics):
        with col:
            st.markdown(
                f"""
<div class="metric-card">
<div class="metric-label">{item[0]}</div>
<div class="metric-value">{item[1]}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    box = "danger" if summary["Severity"] == "High" else "warning" if summary["Severity"] == "Medium" else "success"

    st.markdown("## Executive Summary")
    st.markdown(
        f"""
<div class="{box}">
<b>Simple Explanation:</b><br><br>
{summary["Simple Summary"]}<br><br>
<b>Key Message:</b> {summary["Key Message"]}
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Root Cause")
        st.markdown(f"""
<div class="info">
{summary["Root Cause"]}<br><br>
<b>Issue Source:</b> {summary["Issue Source"]}
</div>
""", unsafe_allow_html=True)

    with c2:
        st.markdown("### Recommended Action")
        st.markdown(f'<div class="warning">{summary["Action"]}</div>', unsafe_allow_html=True)

    if slip:
        st.markdown("## Slippage Analysis")
        s1, s2, s3, s4 = st.columns(4)
        slip_metrics = [
            ("Requested Price", slip["requested_price"]),
            ("Average Fill", slip["avg_fill_price"]),
            ("Slippage Points", slip["slippage_points"]),
            ("Worst Fill", slip["worst_fill_price"]),
        ]

        for col, item in zip([s1, s2, s3, s4], slip_metrics):
            with col:
                st.markdown(
                    f"""
<div class="metric-card">
<div class="metric-label">{item[0]}</div>
<div class="metric-value">{item[1]}</div>
</div>
""",
                    unsafe_allow_html=True,
                )

        st.markdown(
            f"""
<div class="danger">
<b>{slip["direction"]}</b><br><br>
Side: {slip["side"]}<br>
Filled Qty: {slip["filled_qty"]}<br>

</div>
""",
            unsafe_allow_html=True,
        )

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        ["📋 Decoded Logs", "🕒 Timeline", "📉 Slippage", "📊 Analytics", "📚 Knowledge Base", "🔍 Raw Logs", "📄 Export"]
    )

    with tab1:
        visible = [
            "Line", "Time", "Direction", "Event", "Severity", "FIX MsgType", "FIX MsgType Name",
            "Symbol", "Account", "Order ID", "Sender", "Target", "Message", "Side",
            "Order Qty", "Requested Price", "Last Qty", "Last Price", "Avg Price",
            "Cum Qty", "Leaves Qty", "Status", "Execution",
        ]
        st.dataframe(df[visible], use_container_width=True)

    with tab2:
        st.dataframe(df[["Line", "Time", "Event", "Severity", "Message", "Symbol", "Sender", "Target"]], use_container_width=True)

    with tab3:
        if slip:
            st.dataframe(slip["fills"], use_container_width=True)
            fig = px.bar(
                slip["fills"],
                x="Line",
                y="Fill Price",
                text="Fill Qty",
                title="Fill Price by Execution Level",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No slippage data detected.")

    with tab4:
        a, b = st.columns(2)
        with a:
            sev = df["Severity"].value_counts().reset_index()
            sev.columns = ["Severity", "Count"]
            st.plotly_chart(px.pie(sev, names="Severity", values="Count"), use_container_width=True)
        with b:
            events = df["Event"].value_counts().reset_index()
            events.columns = ["Event", "Count"]
            st.plotly_chart(px.bar(events, x="Event", y="Count"), use_container_width=True)

    with tab5:
        detected = summary["Detected Issues"]
        if not detected:
            st.info("No known broker issue matched.")
        for code in detected:
            kb = KB[code]
            with st.expander(f'{kb["title"]} | Severity: {kb["severity"]}', expanded=True):
                st.markdown(f'**Meaning:** {kb["meaning"]}')
                st.markdown(f'**Likely Source:** {kb["source"]}')
                st.markdown("**Possible Causes:**")
                for x in kb["causes"]:
                    st.markdown(f"- {x}")
                st.markdown("**Recommended Actions:**")
                for x in kb["actions"]:
                    st.markdown(f"- {x}")
                st.markdown("**Client Reply:**")
                st.success(kb["client"])

    with tab6:
        for _, row in df.iterrows():
            with st.expander(f'Line {row["Line"]} | {row["Event"]} | {row["Severity"]}'):
                st.code(row["Raw"])

    with tab7:
        report = create_report(summary, df)
        st.text_area("Client-Friendly Report", report, height=420)
        st.download_button("Download TXT Report", report, "universal_log_report.txt", "text/plain", use_container_width=True)
        st.download_button(
            "Download CSV Decode",
            df.to_csv(index=False).encode("utf-8"),
            "decoded_logs.csv",
            "text/csv",
            use_container_width=True,
        )

else:
    st.markdown("""
<div class="card">
<h2>What this tool does</h2>
<p>
Paste or upload broker logs. The analyzer detects log type, issue type, root cause,
recommended action, slippage, partial fills, and generates client-friendly reports.
</p>
</div>
""", unsafe_allow_html=True)
