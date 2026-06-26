import re
import json
from datetime import datetime
from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Universal Log Analyzer",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================
# PREMIUM UI CSS
# =========================

st.markdown(
    """
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
    font-size: 26px;
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
""",
    unsafe_allow_html=True,
)


# =========================
# FIX DICTIONARY
# =========================

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

FIX_TAGS = {
    "1": "Account",
    "6": "AvgPx",
    "8": "BeginString",
    "9": "BodyLength",
    "10": "Checksum",
    "11": "ClOrdID",
    "14": "CumQty",
    "17": "ExecID",
    "31": "LastPx",
    "32": "LastQty",
    "34": "MsgSeqNum",
    "35": "MsgType",
    "37": "OrderID",
    "38": "OrderQty",
    "39": "OrdStatus",
    "40": "OrdType",
    "44": "Price",
    "49": "SenderCompID",
    "52": "SendingTime",
    "54": "Side",
    "55": "Symbol",
    "56": "TargetCompID",
    "58": "Text",
    "59": "TimeInForce",
    "60": "TransactTime",
    "146": "NoRelatedSym",
    "150": "ExecType",
    "151": "LeavesQty",
    "262": "MDReqID",
    "263": "SubscriptionRequestType",
    "264": "MarketDepth",
    "265": "MDUpdateType",
    "267": "NoMDEntryTypes",
    "269": "MDEntryType",
    "281": "MDReqRejReason",
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
ORDER_TYPE = {"1": "Market", "2": "Limit", "3": "Stop", "4": "Stop Limit"}


SAMPLE_LOG = """20260626-11:04:41.915585000 [out] : 8=FIX.4.4|9=169|35=V|34=11548|49=RISERCAPITALFIXAPI|52=20260626-11:04:41.915|56=FIXCMC|57=MD|1=37683322|146=1|55=[N/A]|48=SOYBEAN|22=101|262=SOYBEAN|263=1|264=5|265=0|267=2|269=0|269=1|10=162|
20260626-11:04:41.923532000 [in] : 8=FIX.4.4|9=125|35=Y|34=57020490|49=FIXCMC|50=MD|52=20260626-11:04:41.923|56=RISERCAPITALFIXAPI|58=Product does not exist.|262=SOYBEAN|281=0|10=255|"""


# =========================
# HELPERS
# =========================

def normalize_fix_separators(text: str) -> str:
    return text.replace("\x01", "|").replace("", "|").replace("␁", "|").replace("^A", "|")


def safe_get(pattern, text, default=""):
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else default


def detect_direction(line: str) -> str:
    low = line.lower()
    if "[in]" in low or " inbound " in low or "received" in low:
        return "IN"
    if "[out]" in low or " outbound " in low or "sent" in low:
        return "OUT"
    return "UNKNOWN"


def detect_timestamp(line: str) -> str:
    patterns = [
        r"(\d{8}-\d{2}:\d{2}:\d{2}\.\d+)",
        r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)",
        r"(\d{2}:\d{2}:\d{2}(?:\.\d+)?)",
    ]
    for p in patterns:
        m = re.search(p, line)
        if m:
            return m.group(1)
    return ""


def parse_key_values(line: str) -> dict:
    data = {}

    # FIX format tag=value|
    fix_part = line.split(":", 1)[-1] if "|" in line else line
    for item in fix_part.split("|"):
        if "=" in item:
            k, v = item.split("=", 1)
            data[k.strip()] = v.strip()

    # generic key=value or key: value
    for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_\- ]{1,40})\s*[:=]\s*([A-Za-z0-9_\-./:@]+)", line):
        k = m.group(1).strip()
        v = m.group(2).strip()
        data.setdefault(k, v)

    return data


def is_fix_line(line: str) -> bool:
    line = normalize_fix_separators(line)
    return "8=FIX" in line or "|35=" in line or "\x0135=" in line


def detect_log_type(text: str) -> str:
    t = normalize_fix_separators(text)
    low = t.lower()

    if "8=fix" in low or "|35=" in low:
        if "|35=v|" in low or "\x0135=v" in low:
            return "FIX Market Data"
        if "|35=y|" in low:
            return "FIX Market Data Reject"
        if "|35=d|" in low or "|35=8|" in low:
            return "FIX Order / Execution"
        if "|35=a|" in low or "|35=5|" in low or "|35=3|" in low:
            return "FIX Session"
        return "FIX General"

    if "centroid" in low:
        return "Centroid Bridge Log"
    if "fxcubic" in low or "fx cubic" in low:
        return "FXCubic Bridge Log"
    if "onezero" in low or "one zero" in low:
        return "OneZero Bridge Log"
    if "primexm" in low or "prime xm" in low:
        return "PrimeXM Bridge Log"
    if "metatrader 5" in low or "mt5" in low:
        return "MT5 Journal / Server Log"
    if "metatrader 4" in low or "mt4" in low:
        return "MT4 Journal / Server Log"
    if "tradelocker" in low:
        return "TradeLocker Log"
    if "ctrader" in low:
        return "cTrader Log"

    if any(x in low for x in ["error", "reject", "failed", "timeout", "exception"]):
        return "Generic Error Log"

    return "Generic Log"


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
    if event in ["Reject / Validation Issue", "Error", "FIX Market Data Request Reject", "Session Reject", "Business Message Reject"]:
        return "High"
    return "Low"


def extract_entities(line: str, kv: dict) -> dict:
    symbol = kv.get("55") or kv.get("48") or kv.get("262") or safe_get(r"\b(symbol|sym)\s*[:=]\s*([A-Za-z0-9._-]+)", line)
    account = kv.get("1") or safe_get(r"\b(account|login)\s*[:=]\s*([A-Za-z0-9._-]+)", line)
    order_id = kv.get("37") or kv.get("11") or safe_get(r"\b(order|orderid|ticket)\s*[:=]\s*([A-Za-z0-9._-]+)", line)
    sender = kv.get("49") or safe_get(r"\b(sender)\s*[:=]\s*([A-Za-z0-9._-]+)", line)
    target = kv.get("56") or safe_get(r"\b(target)\s*[:=]\s*([A-Za-z0-9._-]+)", line)
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
    text = normalize_fix_separators(text)
    rows = []

    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        kv = parse_key_values(line)
        event = classify_line(line, kv)
        severity = detect_severity(line, event)
        entities = extract_entities(line, kv)

        msg_type = ""
        msg_type_desc = ""

        if is_fix_line(line):
            msg_type = kv.get("35", "")
            msg_type_desc = FIX_MSG_TYPES.get(msg_type, msg_type)

        row = {
            "Line": idx,
            "Time": detect_timestamp(line),
            "Direction": detect_direction(line),
            "Event": event,
            "Severity": severity,
            "FIX MsgType": msg_type,
            "FIX MsgType Name": msg_type_desc,
            "Symbol": entities["Symbol"],
            "Account": entities["Account"],
            "Order ID": entities["Order ID"],
            "Sender": entities["Sender"],
            "Target": entities["Target"],
            "Message": entities["Message"],
            "Raw": line,
        }

        # Add decoded common FIX fields
        if is_fix_line(line):
            row["Side"] = {"1": "BUY", "2": "SELL"}.get(kv.get("54", ""), kv.get("54", ""))
            row["Order Qty"] = kv.get("38", "")
            row["Last Qty"] = kv.get("32", "")
            row["Last Price"] = kv.get("31", "")
            row["Avg Price"] = kv.get("6", "")
            row["Status"] = ORDER_STATUS.get(kv.get("39", ""), kv.get("39", ""))
            row["Execution"] = EXEC_TYPE.get(kv.get("150", ""), kv.get("150", ""))
            row["Text"] = kv.get("58", "")
        else:
            row["Side"] = ""
            row["Order Qty"] = ""
            row["Last Qty"] = ""
            row["Last Price"] = ""
            row["Avg Price"] = ""
            row["Status"] = ""
            row["Execution"] = ""
            row["Text"] = entities["Message"]

        rows.append(row)

    return pd.DataFrame(rows)


def infer_issue_source(df: pd.DataFrame, text: str) -> str:
    low = text.lower()

    if "product does not exist" in low or "unknown symbol" in low or "symbol" in low and "not found" in low:
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
    if "centroid" in low:
        return "Centroid Bridge"
    if "fxcubic" in low:
        return "FXCubic Bridge"
    if "onezero" in low:
        return "OneZero Bridge"
    if "primexm" in low:
        return "PrimeXM Bridge"

    high = df[df["Severity"] == "High"]
    if not high.empty:
        return "Execution / Platform Validation"

    return "No clear issue source detected"


def build_summary(df: pd.DataFrame, full_text: str) -> dict:
    log_type = detect_log_type(full_text)

    total = len(df)
    high = len(df[df["Severity"] == "High"])
    medium = len(df[df["Severity"] == "Medium"])
    low = len(df[df["Severity"] == "Low"])

    issue_source = infer_issue_source(df, full_text)

    key_messages = []
    for _, row in df.iterrows():
        if row["Severity"] in ["High", "Medium"] or row["Message"] or row["Text"]:
            msg = row["Message"] or row["Text"] or row["Raw"]
            key_messages.append(str(msg))

    key_message = key_messages[0] if key_messages else "No critical message found."

    symbols = [x for x in df["Symbol"].dropna().astype(str).tolist() if x]
    accounts = [x for x in df["Account"].dropna().astype(str).tolist() if x]
    senders = [x for x in df["Sender"].dropna().astype(str).tolist() if x]
    targets = [x for x in df["Target"].dropna().astype(str).tolist() if x]

    main_symbol = Counter(symbols).most_common(1)[0][0] if symbols else "-"
    main_account = Counter(accounts).most_common(1)[0][0] if accounts else "-"
    main_sender = Counter(senders).most_common(1)[0][0] if senders else "-"
    main_target = Counter(targets).most_common(1)[0][0] if targets else "-"

    lower = full_text.lower()

    if "product does not exist" in lower:
        root = f"The requested product/symbol `{main_symbol}` does not exist or is not enabled on the liquidity provider / market data side."
        action = (
            "Check the LP symbol list, broker symbol mapping, FIX Security List, Market Data subscription, "
            "and whether the product is enabled for this FIX session."
        )
        severity = "High"
    elif high > 0:
        root = f"The logs contain high severity errors or rejections. Main message: {key_message}"
        action = "Check the exact reject reason, symbol/account configuration, bridge route, LP session, and platform permissions."
        severity = "High"
    elif medium > 0:
        root = "The logs contain warnings, timeout, cancellation, or incomplete execution events."
        action = "Check next log lines, bridge status, LP response time, and whether the request completed later."
        severity = "Medium"
    else:
        root = "No clear critical issue detected in the uploaded logs."
        action = "No urgent action required. Review decoded logs for confirmation."
        severity = "Low"

    simple = (
        f"The uploaded content looks like **{log_type}**. "
        f"Total log lines parsed: **{total}**. "
        f"Detected high severity events: **{high}**. "
        f"Main symbol/product: **{main_symbol}**. "
        f"Likely issue source: **{issue_source}**. "
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
        "Simple Summary": simple,
        "Key Message": key_message,
    }


def create_report(summary: dict, df: pd.DataFrame) -> str:
    report = f"""
UNIVERSAL LOG ANALYSIS REPORT

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

Timeline:
"""

    for _, row in df.iterrows():
        report += f'\nLine {row["Line"]} | {row["Time"]} | {row["Event"]} | Severity: {row["Severity"]} | {row["Message"] or row["Text"]}'

    return report


# =========================
# SIDEBAR
# =========================

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
    st.markdown(
        """
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
"""
    )


# =========================
# MAIN UI
# =========================

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

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["📋 Decoded Logs", "🕒 Timeline", "📊 Analytics", "🔍 Raw Logs", "📄 Export"]
    )

    with tab1:
        visible_cols = [
            "Line",
            "Time",
            "Direction",
            "Event",
            "Severity",
            "FIX MsgType",
            "FIX MsgType Name",
            "Symbol",
            "Account",
            "Order ID",
            "Sender",
            "Target",
            "Message",
            "Status",
            "Execution",
            "Side",
            "Order Qty",
            "Last Qty",
            "Last Price",
            "Avg Price",
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
        for _, row in df.iterrows():
            with st.expander(f'Line {row["Line"]} | {row["Event"]} | {row["Severity"]}'):
                st.code(row["Raw"])

    with tab5:
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
    st.markdown(
        """
<div class="card">
<h2>What this tool does</h2>
<p>
Paste or upload any broker log. The analyzer will detect the log type, extract important fields,
identify errors/rejections/warnings, explain the issue in simple language, suggest action,
and generate a client-friendly report.
</p>
</div>
""",
        unsafe_allow_html=True,
    )
