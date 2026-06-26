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
.stApp {
    background: linear-gradient(135deg, #020617 0%, #0f172a 45%, #111827 100%);
    color: #e5e7eb;
}

section[data-testid="stSidebar"] {
    background: #020617;
    border-right: 1px solid #1e293b;
}

h1, h2, h3, h4, h5, h6, p, label, span {
    color: #e5e7eb !important;
}

.stTextArea textarea {
    background-color: #0f172a !important;
    color: #ffffff !important;
    border: 1px solid #475569 !important;
    border-radius: 14px !important;
    font-family: Consolas, monospace !important;
    font-size: 14px !important;
}

.stFileUploader {
    background-color: #0f172a !important;
    border-radius: 16px !important;
    padding: 16px !important;
    border: 1px dashed #64748b !important;
}

.stButton button {
    background: linear-gradient(90deg, #2563eb, #7c3aed) !important;
    color: white !important;
    border-radius: 14px !important;
    height: 50px;
    font-weight: 800;
    border: none !important;
}

.card {
    background: rgba(15, 23, 42, 0.95);
    border: 1px solid #334155;
    border-radius: 20px;
    padding: 22px;
    margin-bottom: 18px;
    box-shadow: 0 15px 35px rgba(0,0,0,0.35);
}

.metric-card {
    background: linear-gradient(135deg, #111827, #1e293b);
    border: 1px solid #334155;
    border-radius: 18px;
    padding: 20px;
}

.metric-label {
    color: #94a3b8 !important;
    font-size: 13px;
}

.metric-value {
    color: #ffffff !important;
    font-size: 24px;
    font-weight: 900;
}

.success {
    background: rgba(34,197,94,0.14);
    border: 1px solid rgba(34,197,94,0.5);
    border-radius: 16px;
    padding: 18px;
}

.warning {
    background: rgba(234,179,8,0.14);
    border: 1px solid rgba(234,179,8,0.5);
    border-radius: 16px;
    padding: 18px;
}

.danger {
    background: rgba(239,68,68,0.16);
    border: 1px solid rgba(239,68,68,0.55);
    border-radius: 16px;
    padding: 18px;
}

.info {
    background: rgba(59,130,246,0.14);
    border: 1px solid rgba(59,130,246,0.5);
    border-radius: 16px;
    padding: 18px;
}

code {
    color: #93c5fd !important;
}
</style>
""", unsafe_allow_html=True)


FIX_MSG_TYPES = {
    "0": "Heartbeat",
    "1": "Test Request",
    "2": "Resend Request",
    "3": "Session Reject",
    "4": "Sequence Reset",
    "5": "Logout",
    "A": "Logon",
    "D": "New Order Single",
    "8": "Execution Report",
    "9": "Order Cancel Reject",
    "F": "Order Cancel Request",
    "G": "Order Cancel Replace Request",
    "j": "Business Message Reject",
    "V": "Market Data Request",
    "W": "Market Data Snapshot",
    "X": "Market Data Incremental Refresh",
    "Y": "Market Data Request Reject",
    "R": "Quote Request",
    "S": "Quote",
    "i": "Mass Quote",
    "d": "Security Definition",
    "e": "Security Status",
}

ORDER_STATUS = {
    "0": "New",
    "1": "Partially Filled",
    "2": "Filled",
    "4": "Cancelled",
    "8": "Rejected",
    "A": "Pending New",
}

EXEC_TYPE = {
    "0": "New",
    "1": "Partial Fill",
    "2": "Fill",
    "4": "Cancelled",
    "8": "Rejected",
    "A": "Pending New",
}

SIDE = {"1": "BUY", "2": "SELL"}


BROKER_KNOWLEDGE_BASE = {
    "PRODUCT_NOT_EXIST": {
        "title": "Product / Symbol Does Not Exist",
        "severity": "High",
        "source": "LP / Symbol Mapping",
        "meaning": "The requested symbol is not available, not enabled, or incorrectly mapped between broker, bridge, and liquidity provider.",
        "common_logs": ["Product does not exist", "Unknown symbol", "Security not found", "Invalid symbol", "No security definition found"],
        "possible_causes": [
            "Symbol is not enabled on LP side",
            "Wrong symbol mapping in bridge",
            "Broker symbol name differs from LP symbol name",
            "Market data subscription is missing",
            "Security list was not loaded",
        ],
        "recommended_actions": [
            "Check LP symbol list",
            "Verify bridge symbol mapping",
            "Confirm the product is enabled for this FIX session",
            "Check Security Definition / Security List",
            "Ask LP to confirm exact symbol name",
        ],
        "client_reply": "The requested product is not available from the liquidity side or the symbol mapping is incorrect. We are checking the symbol configuration with the LP/bridge team.",
    },
    "NO_PRICE": {
        "title": "No Price / No Liquidity",
        "severity": "High",
        "source": "Liquidity Provider / Market Data",
        "meaning": "The platform could not receive an executable price from the LP.",
        "common_logs": ["No price", "No prices", "Off quotes", "No liquidity", "Market data unavailable", "Price not found"],
        "possible_causes": [
            "LP is not streaming prices",
            "Market is closed",
            "Symbol session is disabled",
            "Market data route is down",
            "Liquidity depth is not enough",
        ],
        "recommended_actions": [
            "Check LP price feed",
            "Check symbol trading session",
            "Check bridge market data route",
            "Verify LP connection status",
            "Compare prices with another LP",
        ],
        "client_reply": "The order could not be executed because an executable market price was not available at that time. We are checking the liquidity and price feed.",
    },
    "MARKET_CLOSED": {
        "title": "Market Closed / Session Closed",
        "severity": "High",
        "source": "Symbol Session / Trading Hours",
        "meaning": "Trading was attempted outside the allowed market session.",
        "common_logs": ["Market closed", "Session closed", "Trading disabled", "Trade is disabled", "Instrument disabled"],
        "possible_causes": [
            "Symbol trading session is closed",
            "Weekend / holiday schedule",
            "Trading disabled on group",
            "LP market is closed",
        ],
        "recommended_actions": [
            "Check MT5 symbol session",
            "Check bridge trading hours",
            "Check LP holiday schedule",
            "Verify group permissions",
        ],
        "client_reply": "The order was not executed because the market/session was closed or trading was disabled for the symbol at that time.",
    },
    "INVALID_ACCOUNT": {
        "title": "Invalid Account / Permission Issue",
        "severity": "High",
        "source": "Account / Group / FIX Session",
        "meaning": "The trading account is not allowed to trade or is not recognized by the execution system.",
        "common_logs": ["Invalid account", "Unknown account", "Account not found", "Trading not allowed", "Not authorized", "Permission denied"],
        "possible_causes": [
            "Account not mapped in bridge",
            "Trading disabled on account",
            "Wrong FIX account tag 1",
            "Account group permission issue",
            "Account is read-only or blocked",
        ],
        "recommended_actions": [
            "Check FIX tag 1 account value",
            "Check bridge account mapping",
            "Check MT5 account trade permission",
            "Check group settings",
            "Confirm account exists on LP/bridge side",
        ],
        "client_reply": "The order was rejected due to an account or permission validation issue. We are checking the account configuration.",
    },
    "INSUFFICIENT_MARGIN": {
        "title": "Insufficient Margin",
        "severity": "High",
        "source": "MT4 / MT5 Margin Engine",
        "meaning": "The account did not have enough free margin to open or maintain the position.",
        "common_logs": ["Not enough money", "Insufficient margin", "No money", "Margin check failed", "Stop out", "Stopout"],
        "possible_causes": [
            "Free margin was not enough",
            "High leverage/margin requirement",
            "Large volume order",
            "Open exposure increased margin usage",
            "Stop-out triggered",
        ],
        "recommended_actions": [
            "Check account equity and free margin",
            "Check symbol margin settings",
            "Check leverage/group settings",
            "Review open positions",
            "Verify contract size and margin calculation",
        ],
        "client_reply": "The order could not be completed because the account did not have sufficient free margin at that time.",
    },
    "TIMEOUT": {
        "title": "Timeout / No Response",
        "severity": "Medium",
        "source": "Network / Bridge / LP",
        "meaning": "The request was sent but the expected response was not received within the allowed time.",
        "common_logs": ["Timeout", "Timed out", "No response", "Request timeout", "Execution timeout"],
        "possible_causes": [
            "LP response delay",
            "Bridge processing delay",
            "Network latency",
            "Session instability",
            "High traffic during market volatility",
        ],
        "recommended_actions": [
            "Check LP response time",
            "Check bridge logs around same timestamp",
            "Check network latency",
            "Check FIX session heartbeat",
            "Compare with other LPs",
        ],
        "client_reply": "The request did not receive a response within the expected time window. We are checking bridge and LP response latency.",
    },
    "SESSION_DISCONNECT": {
        "title": "FIX Session Disconnect / Logout",
        "severity": "High",
        "source": "FIX Session / Network",
        "meaning": "The FIX connection was disconnected, logged out, or became unstable.",
        "common_logs": ["Logout", "Disconnected", "Connection lost", "Heartbeat timeout", "Socket closed", "Session reset"],
        "possible_causes": [
            "Network issue",
            "Heartbeat timeout",
            "LP disconnected the session",
            "Wrong sequence number",
            "Session reset required",
        ],
        "recommended_actions": [
            "Check FIX heartbeat",
            "Check sequence numbers",
            "Check network/VPN",
            "Restart FIX session if required",
            "Contact LP if logout came from their side",
        ],
        "client_reply": "There was a connectivity/session issue during this period. We are checking the FIX session stability and LP connection.",
    },
    "PARTIAL_FILL": {
        "title": "Partial Fill",
        "severity": "Low",
        "source": "Liquidity / Market Depth",
        "meaning": "Only part of the requested order quantity was filled initially.",
        "common_logs": ["Partial fill", "Partially filled", "39=1", "150=1"],
        "possible_causes": [
            "Available liquidity was split",
            "LP filled order in multiple levels",
            "Large order quantity",
            "Market depth was limited",
        ],
        "recommended_actions": [
            "Check market depth",
            "Check final fill status",
            "Explain that partial fills are normal in market execution",
            "Verify remaining quantity was completed or cancelled",
        ],
        "client_reply": "The order was filled in parts due to available market liquidity. This is normal in market execution.",
    },
    "ORDER_REJECTED": {
        "title": "Order Rejected",
        "severity": "High",
        "source": "Bridge / LP / Platform Validation",
        "meaning": "The order was not accepted by one of the execution components.",
        "common_logs": ["Rejected", "Order reject", "39=8", "150=8", "Business reject", "35=j"],
        "possible_causes": [
            "Invalid symbol",
            "Invalid account",
            "Market closed",
            "No price",
            "LP rejected the request",
            "Bridge rule blocked the order",
        ],
        "recommended_actions": [
            "Check reject reason tag 58",
            "Check FIX OrdStatus/ExecType",
            "Check bridge routing rule",
            "Check symbol and account mapping",
            "Check LP rejection logs",
        ],
        "client_reply": "The order was rejected by the execution system. We are reviewing the rejection reason and related bridge/LP logs.",
    },
}


SAMPLE_LOG = """20260626-11:04:41.915585000 [out] : 8=FIX.4.4|9=169|35=V|34=11548|49=RISERCAPITALFIXAPI|52=20260626-11:04:41.915|56=FIXCMC|57=MD|1=37683322|146=1|55=[N/A]|48=SOYBEAN|22=101|262=SOYBEAN|263=1|264=5|265=0|267=2|269=0|269=1|10=162|
20260626-11:04:41.923532000 [in] : 8=FIX.4.4|9=125|35=Y|34=57020490|49=FIXCMC|50=MD|52=20260626-11:04:41.923|56=RISERCAPITALFIXAPI|58=Product does not exist.|262=SOYBEAN|281=0|10=255|"""


def normalize_fix(text: str) -> str:
    return text.replace("\x01", "|").replace("", "|").replace("␁", "|").replace("^A", "|")


def detect_timestamp(line: str) -> str:
    patterns = [
        r"(\d{8}-\d{2}:\d{2}:\d{2}\.\d+)",
        r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)",
        r"(\d{2}:\d{2}:\d{2}(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, line)
        if match:
            return match.group(1)
    return ""


def detect_direction(line: str) -> str:
    low = line.lower()
    if "[in]" in low or "received" in low:
        return "IN"
    if "[out]" in low or "sent" in low:
        return "OUT"
    return "UNKNOWN"


def parse_key_values(line: str) -> dict:
    data = {}
    part = line.split(":", 1)[-1] if "|" in line else line

    for item in part.split("|"):
        if "=" in item:
            k, v = item.split("=", 1)
            data[k.strip()] = v.strip()

    for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_ -]{1,40})\s*[:=]\s*([A-Za-z0-9_./:@-]+)", line):
        k = match.group(1).strip()
        v = match.group(2).strip()
        data.setdefault(k, v)

    return data


def is_fix_line(line: str) -> bool:
    line = normalize_fix(line)
    return "8=FIX" in line or "|35=" in line


def detect_log_type(text: str) -> str:
    low = normalize_fix(text).lower()

    if "8=fix" in low or "|35=" in low:
        if "|35=v|" in low or "|35=y|" in low:
            return "FIX Market Data / Reject"
        if "|35=d|" in low or "|35=8|" in low:
            return "FIX Order / Execution"
        if "|35=a|" in low or "|35=5|" in low or "|35=3|" in low:
            return "FIX Session"
        return "FIX General"

    if "centroid" in low:
        return "Centroid Bridge Log"
    if "fxcubic" in low or "fx cubic" in low:
        return "FXCubic Bridge Log"
    if "onezero" in low:
        return "OneZero Bridge Log"
    if "primexm" in low or "prime xm" in low:
        return "PrimeXM Bridge Log"
    if "mt5" in low or "metatrader 5" in low:
        return "MT5 Journal / Server Log"
    if "mt4" in low or "metatrader 4" in low:
        return "MT4 Journal / Server Log"
    if "tradelocker" in low:
        return "TradeLocker Log"
    if "ctrader" in low:
        return "cTrader Log"
    if any(x in low for x in ["error", "reject", "failed", "timeout", "exception"]):
        return "Generic Error Log"

    return "Generic Log"


def classify_broker_issues(text: str) -> list:
    low = text.lower()
    detected = []

    for issue_code, kb in BROKER_KNOWLEDGE_BASE.items():
        for keyword in kb["common_logs"]:
            if keyword.lower() in low:
                detected.append(issue_code)
                break

    if "35=y" in low:
        if "product does not exist" in low:
            detected.insert(0, "PRODUCT_NOT_EXIST")
        else:
            detected.insert(0, "NO_PRICE")

    if "39=8" in low or "150=8" in low or "35=j" in low:
        detected.insert(0, "ORDER_REJECTED")

    if "39=1" in low or "150=1" in low:
        detected.insert(0, "PARTIAL_FILL")

    if "35=5" in low or "logout" in low:
        detected.insert(0, "SESSION_DISCONNECT")

    final = []
    for item in detected:
        if item not in final:
            final.append(item)

    return final


def classify_line(line: str, kv: dict) -> str:
    low = line.lower()

    if is_fix_line(line):
        msg_type = kv.get("35", "")
        return FIX_MSG_TYPES.get(msg_type, f"FIX Message {msg_type}")

    if any(x in low for x in ["reject", "rejected", "does not exist", "invalid", "not found"]):
        return "Reject / Validation Issue"
    if any(x in low for x in ["error", "exception", "failed", "failure"]):
        return "Error"
    if any(x in low for x in ["timeout", "timed out", "no response"]):
        return "Timeout"
    if any(x in low for x in ["disconnect", "connection lost", "logout"]):
        return "Connectivity"
    if any(x in low for x in ["filled", "partial fill", "executed", "deal"]):
        return "Execution"
    if any(x in low for x in ["margin", "stop out", "stopout"]):
        return "Margin / Stop-Out"
    if any(x in low for x in ["price", "quote", "tick", "market data"]):
        return "Pricing / Market Data"

    return "Information"


def detect_severity(line: str, event: str) -> str:
    low = line.lower()

    if any(x in low for x in ["reject", "rejected", "error", "failed", "exception", "does not exist", "invalid"]):
        return "High"

    if any(x in low for x in ["timeout", "disconnect", "cancelled", "warning", "partial"]):
        return "Medium"

    if event in ["Reject / Validation Issue", "Error", "Market Data Request Reject", "Session Reject", "Business Message Reject"]:
        return "High"

    return "Low"


def extract_entities(line: str, kv: dict) -> dict:
    symbol = kv.get("55") or kv.get("48") or kv.get("262") or ""
    account = kv.get("1") or kv.get("Account") or kv.get("Login") or ""
    order_id = kv.get("37") or kv.get("11") or kv.get("OrderID") or kv.get("Ticket") or ""
    sender = kv.get("49") or ""
    target = kv.get("56") or ""
    message = kv.get("58") or ""

    return {
        "Symbol": symbol,
        "Account": account,
        "Order ID": order_id,
        "Sender": sender,
        "Target": target,
        "Message": message,
    }


def parse_any_logs(text: str) -> pd.DataFrame:
    text = normalize_fix(text)
    rows = []

    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        kv = parse_key_values(line)
        event = classify_line(line, kv)
        severity = detect_severity(line, event)
        entities = extract_entities(line, kv)

        msg_type = kv.get("35", "") if is_fix_line(line) else ""
        msg_type_name = FIX_MSG_TYPES.get(msg_type, msg_type)

        rows.append({
            "Line": idx,
            "Time": detect_timestamp(line),
            "Direction": detect_direction(line),
            "Event": event,
            "Severity": severity,
            "FIX MsgType": msg_type,
            "FIX MsgType Name": msg_type_name,
            "Symbol": entities["Symbol"],
            "Account": entities["Account"],
            "Order ID": entities["Order ID"],
            "Sender": entities["Sender"],
            "Target": entities["Target"],
            "Message": entities["Message"],
            "Side": SIDE.get(kv.get("54", ""), kv.get("54", "")),
            "Order Qty": kv.get("38", ""),
            "Last Qty": kv.get("32", ""),
            "Last Price": kv.get("31", ""),
            "Avg Price": kv.get("6", ""),
            "Status": ORDER_STATUS.get(kv.get("39", ""), kv.get("39", "")),
            "Execution": EXEC_TYPE.get(kv.get("150", ""), kv.get("150", "")),
            "Raw": line,
        })

    return pd.DataFrame(rows)


def infer_issue_source(df: pd.DataFrame, text: str) -> str:
    low = text.lower()

    if "product does not exist" in low or "unknown symbol" in low:
        return "LP / Symbol Configuration"
    if "market data" in low or "35=v" in low or "35=y" in low:
        return "Market Data / LP Pricing"
    if "margin" in low or "stop out" in low or "stopout" in low:
        return "MT4/MT5 Margin Engine"
    if "timeout" in low or "no response" in low:
        return "Network / Bridge / LP Timeout"
    if "login" in low or "logout" in low or "disconnect" in low:
        return "FIX Session / Connectivity"
    if "reject" in low or "rejected" in low:
        return "Bridge / LP / Validation"

    if not df[df["Severity"] == "High"].empty:
        return "Execution / Platform Validation"

    return "No clear issue source detected"


def build_summary(df: pd.DataFrame, full_text: str) -> dict:
    log_type = detect_log_type(full_text)
    detected_issues = classify_broker_issues(full_text)

    total = len(df)
    high = len(df[df["Severity"] == "High"])
    medium = len(df[df["Severity"] == "Medium"])
    low = len(df[df["Severity"] == "Low"])

    symbols = [x for x in df["Symbol"].dropna().astype(str).tolist() if x and x != "[N/A]"]
    accounts = [x for x in df["Account"].dropna().astype(str).tolist() if x]
    senders = [x for x in df["Sender"].dropna().astype(str).tolist() if x]
    targets = [x for x in df["Target"].dropna().astype(str).tolist() if x]

    main_symbol = Counter(symbols).most_common(1)[0][0] if symbols else "-"
    main_account = Counter(accounts).most_common(1)[0][0] if accounts else "-"
    main_sender = Counter(senders).most_common(1)[0][0] if senders else "-"
    main_target = Counter(targets).most_common(1)[0][0] if targets else "-"

    issue_source = infer_issue_source(df, full_text)
    severity = "High" if high else "Medium" if medium else "Low"
    key_message = "No critical message found."

    messages = [x for x in df["Message"].dropna().astype(str).tolist() if x]
    if messages:
        key_message = messages[0]

    root = "No clear critical issue detected in the uploaded logs."
    action = "No urgent action required. Review decoded logs for confirmation."

    if detected_issues:
        primary_issue = detected_issues[0]
        kb = BROKER_KNOWLEDGE_BASE[primary_issue]
        root = kb["meaning"]
        action = " | ".join(kb["recommended_actions"][:3])
        issue_source = kb["source"]
        severity = kb["severity"]
        key_message = kb["title"]
    else:
        primary_issue = None

    simple_summary = (
        f"The uploaded content looks like **{log_type}**. "
        f"Total log lines parsed: **{total}**. "
        f"High severity events: **{high}**. "
        f"Main symbol/product: **{main_symbol}**. "
        f"Likely issue source: **{issue_source}**."
    )

    return {
        "Log Type": log_type,
        "Total Lines": total,
        "High": high,
        "Medium": medium,
        "Low": low,
        "Main Symbol": main_symbol,
        "Main Account": main_account,
        "Main Sender": main_sender,
        "Main Target": main_target,
        "Severity": severity,
        "Issue Source": issue_source,
        "Root Cause": root,
        "Action": action,
        "Simple Summary": simple_summary,
        "Key Message": key_message,
        "Detected Issues": detected_issues,
        "Primary Issue": primary_issue,
    }


def create_report(summary: dict, df: pd.DataFrame) -> str:
    report = f"""
UNIVERSAL BROKER LOG ANALYSIS REPORT

Log Type:
{summary["Log Type"]}

Severity:
{summary["Severity"]}

Simple Summary:
{summary["Simple Summary"]}

Main Symbol/Product:
{summary["Main Symbol"]}

Main Account:
{summary["Main Account"]}

Sender:
{summary["Main Sender"]}

Target:
{summary["Main Target"]}

Issue Source:
{summary["Issue Source"]}

Root Cause:
{summary["Root Cause"]}

Recommended Action:
{summary["Action"]}

Key Message:
{summary["Key Message"]}

Detected Issues:
{", ".join(summary["Detected Issues"]) if summary["Detected Issues"] else "No known issue matched"}

Timeline:
"""

    for _, row in df.iterrows():
        msg = row["Message"] if row["Message"] else row["Event"]
        report += f'\nLine {row["Line"]} | {row["Time"]} | {row["Event"]} | Severity: {row["Severity"]} | {msg}'

    return report


with st.sidebar:
    st.markdown("## 🧠 Universal Log Analyzer")
    st.caption("Premium broker log analyzer.")
    st.divider()

    mode = st.radio(
        "Input Mode",
        ["Paste Logs", "Upload File", "Use Sample"],
        index=0,
    )

    st.divider()
    st.markdown("### Supported Logs")
    st.markdown("""
- FIX Order Logs
- FIX Market Data Logs
- FIX Session Logs
- MT4 / MT5 Logs
- Centroid Logs
- FXCubic Logs
- OneZero Logs
- PrimeXM Logs
- TradeLocker Logs
- cTrader Logs
- Bridge Logs
- LP Logs
- Any Error Logs
""")


st.markdown("# 🧠 Universal Broker Log Analyzer")
st.markdown("### Explain any broker log in simple language: FIX, MT4, MT5, bridge, LP, server, pricing, rejection or execution logs.")

log_text = ""

st.markdown('<div class="card">', unsafe_allow_html=True)

if mode == "Paste Logs":
    log_text = st.text_area(
        "Paste any logs here",
        height=300,
        placeholder="Paste FIX / MT5 / Bridge / LP / Server logs here...",
    )
elif mode == "Upload File":
    uploaded = st.file_uploader(
        "Upload log file",
        type=["txt", "log", "fix", "csv"],
    )
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

    col1, col2, col3, col4 = st.columns(4)

    metrics = [
        ("Log Type", summary["Log Type"]),
        ("Severity", summary["Severity"]),
        ("High Events", summary["High"]),
        ("Symbol/Product", summary["Main Symbol"]),
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

    box_class = "danger" if summary["Severity"] == "High" else "warning" if summary["Severity"] == "Medium" else "success"

    st.markdown("## Executive Summary")
    st.markdown(
        f"""
<div class="{box_class}">
<b>Simple Explanation:</b><br><br>
{summary["Simple Summary"]}
<br><br>
<b>Key Message:</b> {summary["Key Message"]}
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Root Cause")
        st.markdown(
            f"""
<div class="info">
{summary["Root Cause"]}
<br><br>
<b>Issue Source:</b> {summary["Issue Source"]}
</div>
""",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown("### Recommended Action")
        st.markdown(
            f"""
<div class="warning">
{summary["Action"]}
</div>
""",
            unsafe_allow_html=True,
        )

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["📋 Decoded Logs", "🕒 Timeline", "📊 Analytics", "📚 Knowledge Base", "🔍 Raw Logs", "📄 Export"]
    )

    with tab1:
        visible_cols = [
            "Line", "Time", "Direction", "Event", "Severity",
            "FIX MsgType", "FIX MsgType Name", "Symbol", "Account",
            "Order ID", "Sender", "Target", "Message", "Status",
            "Execution", "Side", "Order Qty", "Last Qty", "Last Price", "Avg Price",
        ]
        st.dataframe(df[visible_cols], use_container_width=True)

    with tab2:
        timeline_cols = ["Line", "Time", "Event", "Severity", "Message", "Symbol", "Sender", "Target"]
        st.dataframe(df[timeline_cols], use_container_width=True)

    with tab3:
        col_a, col_b = st.columns(2)

        with col_a:
            sev_count = df["Severity"].value_counts().reset_index()
            sev_count.columns = ["Severity", "Count"]
            fig = px.pie(sev_count, names="Severity", values="Count", title="Severity Distribution")
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            event_count = df["Event"].value_counts().reset_index()
            event_count.columns = ["Event", "Count"]
            fig2 = px.bar(event_count, x="Event", y="Count", title="Event Type Count")
            st.plotly_chart(fig2, use_container_width=True)

    with tab4:
        st.subheader("Broker Knowledge Base")

        detected = summary.get("Detected Issues", [])

        if not detected:
            st.info("No known broker issue matched from the current logs.")
        else:
            for issue_code in detected:
                kb = BROKER_KNOWLEDGE_BASE[issue_code]

                with st.expander(f'{kb["title"]} | Severity: {kb["severity"]}', expanded=True):
                    st.markdown(f'**Meaning:** {kb["meaning"]}')
                    st.markdown(f'**Likely Source:** {kb["source"]}')

                    st.markdown("**Possible Causes:**")
                    for item in kb["possible_causes"]:
                        st.markdown(f"- {item}")

                    st.markdown("**Recommended Actions:**")
                    for item in kb["recommended_actions"]:
                        st.markdown(f"- {item}")

                    st.markdown("**Client Reply:**")
                    st.success(kb["client_reply"])

    with tab5:
        for _, row in df.iterrows():
            with st.expander(f'Line {row["Line"]} | {row["Event"]} | {row["Severity"]}'):
                st.code(row["Raw"])

    with tab6:
        report = create_report(summary, df)
        st.text_area("Client-Friendly Report", report, height=420)

        st.download_button(
            "Download TXT Report",
            report,
            file_name="universal_log_report.txt",
            mime="text/plain",
            use_container_width=True,
        )

        csv_data = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV Decode",
            csv_data,
            file_name="decoded_logs.csv",
            mime="text/csv",
            use_container_width=True,
        )

else:
    st.markdown("""
<div class="card">
<h2>What this tool does</h2>
<p>
Paste or upload any broker log. The analyzer will detect the log type, extract important fields,
identify errors/rejections/warnings, explain the issue in simple language, suggest action,
match the issue with broker knowledge base, and generate a client-friendly report.
</p>
</div>
""", unsafe_allow_html=True)
