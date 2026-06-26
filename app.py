import re
from datetime import datetime
from collections import defaultdict

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="FIX Log Explainer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp {
    background: #0f172a;
    color: #e5e7eb;
}

section[data-testid="stSidebar"] {
    background: #020617;
    border-right: 1px solid #1e293b;
}

h1, h2, h3, h4, h5, h6, p, label, span, div {
    color: #e5e7eb !important;
}

.stTextArea textarea {
    background-color: #111827 !important;
    color: #ffffff !important;
    border: 1px solid #334155 !important;
    border-radius: 12px !important;
}

.stTextInput input {
    background-color: #111827 !important;
    color: #ffffff !important;
}

.stFileUploader {
    background-color: #111827 !important;
    border-radius: 14px !important;
    padding: 15px !important;
    border: 1px dashed #475569 !important;
}

.stButton button {
    background: linear-gradient(90deg, #2563eb, #7c3aed) !important;
    color: white !important;
    border-radius: 12px !important;
    height: 48px;
    font-weight: 700;
    border: none !important;
}

.card {
    background: #111827;
    border: 1px solid #334155;
    border-radius: 18px;
    padding: 22px;
    margin-bottom: 18px;
    box-shadow: 0 12px 35px rgba(0,0,0,0.35);
}

.metric-card {
    background: linear-gradient(135deg, #111827, #1e293b);
    border: 1px solid #334155;
    border-radius: 18px;
    padding: 20px;
}

.metric-label {
    color: #94a3b8 !important;
    font-size: 14px;
}

.metric-value {
    color: white !important;
    font-size: 30px;
    font-weight: 800;
}

.success {
    background: rgba(34,197,94,0.15);
    border: 1px solid rgba(34,197,94,0.5);
    border-radius: 14px;
    padding: 18px;
}

.warning {
    background: rgba(234,179,8,0.15);
    border: 1px solid rgba(234,179,8,0.5);
    border-radius: 14px;
    padding: 18px;
}

.danger {
    background: rgba(239,68,68,0.15);
    border: 1px solid rgba(239,68,68,0.5);
    border-radius: 14px;
    padding: 18px;
}
</style>
""", unsafe_allow_html=True)


FIX_TAGS = {
    "35": "MsgType", "49": "SenderCompID", "56": "TargetCompID",
    "1": "Account", "6": "AvgPx", "11": "ClOrdID", "14": "CumQty",
    "17": "ExecID", "31": "LastPx", "32": "LastQty", "37": "OrderID",
    "38": "OrderQty", "39": "OrdStatus", "40": "OrdType", "44": "Price",
    "54": "Side", "55": "Symbol", "58": "Text", "59": "TimeInForce",
    "60": "TransactTime", "150": "ExecType", "151": "LeavesQty"
}

MSG_TYPE = {"D": "New Order", "8": "Execution Report"}
ORDER_STATUS = {"0": "New", "1": "Partially Filled", "2": "Filled", "4": "Cancelled", "8": "Rejected"}
EXEC_TYPE = {"0": "New", "1": "Partial Fill", "2": "Fill", "4": "Cancelled", "8": "Rejected"}
SIDE = {"1": "BUY", "2": "SELL"}
ORDER_TYPE = {"1": "Market", "2": "Limit", "3": "Stop", "4": "Stop Limit"}
TIF = {"0": "Day", "1": "GTC", "3": "IOC", "4": "FOK"}

SAMPLE_LOG = """20260623-02:57:55.869897000 [in] : 8=FIX.4.4|9=184|35=D|34=3862|49=TD_Mazi_Finance_2_FIX|52=20260623-02:57:55.850|56=CENTROID_SOL|1=tem_Mazifinance_2|11=LuOFHPNVOXS6z|38=5000|40=1|44=63.488|54=1|55=XAGUSD|59=3|60=20260623-02:57:55.850|10=240|
20260623-02:57:55.870176000 [out] : 8=FIX.4.4|9=280|35=8|34=3866|49=CENTROID_SOL|52=20260623-02:57:55.870|56=TD_Mazi_Finance_2_FIX|1=tem_Mazifinance_2|6=0.0000000000|11=LuOFHPNVOXS6z|14=0.00|17=7168138|31=0.0000000000|32=0.00|37=7168138|38=5000.00|39=0|40=1|54=1|55=XAGUSD|58=New Request|59=3|60=20260623-02:57:55|150=0|151=5000.00|10=051|
20260623-02:57:55.911589000 [out] : 8=FIX.4.4|9=286|35=8|34=3867|49=CENTROID_SOL|52=20260623-02:57:55.911|56=TD_Mazi_Finance_2_FIX|1=tem_Mazifinance_2|6=63.4840000000|11=LuOFHPNVOXS6z|14=2500.00|17=7168138|31=63.4840000000|32=2500.00|37=7168138|38=5000.00|39=1|40=1|54=1|55=XAGUSD|58=Processed|59=3|60=20260623-02:57:55|150=1|151=2500.00|10=111|
20260623-02:57:55.911905000 [out] : 8=FIX.4.4|9=283|35=8|34=3868|49=CENTROID_SOL|52=20260623-02:57:55.911|56=TD_Mazi_Finance_2_FIX|1=tem_Mazifinance_2|6=63.4840000000|11=LuOFHPNVOXS6z|14=5000.00|17=7168138|31=63.4830000000|32=2500.00|37=7168138|38=5000.00|39=2|40=1|54=1|55=XAGUSD|58=Processed|59=3|60=20260623-02:57:55|150=2|151=0.00|10=213|"""


def parse_fix(line):
    if "|" not in line:
        return None

    direction = "IN" if "[in]" in line else "OUT" if "[out]" in line else "UNKNOWN"
    timestamp = line.split(" ")[0] if " " in line else ""

    fix_part = line.split(":", 1)[-1].strip()
    raw = {}

    for item in fix_part.split("|"):
        if "=" in item:
            k, v = item.split("=", 1)
            raw[k] = v

    return {
        "Time": timestamp,
        "Direction": direction,
        "Msg Type": MSG_TYPE.get(raw.get("35", ""), raw.get("35", "")),
        "Account": raw.get("1", ""),
        "Client Order ID": raw.get("11", ""),
        "Order ID": raw.get("37", ""),
        "Symbol": raw.get("55", ""),
        "Side": SIDE.get(raw.get("54", ""), raw.get("54", "")),
        "Order Type": ORDER_TYPE.get(raw.get("40", ""), raw.get("40", "")),
        "Order Qty": raw.get("38", ""),
        "Cum Qty": raw.get("14", ""),
        "Last Qty": raw.get("32", ""),
        "Leaves Qty": raw.get("151", ""),
        "Requested Price": raw.get("44", ""),
        "Last Price": raw.get("31", ""),
        "Avg Price": raw.get("6", ""),
        "Status": ORDER_STATUS.get(raw.get("39", ""), raw.get("39", "")),
        "Execution": EXEC_TYPE.get(raw.get("150", ""), raw.get("150", "")),
        "Message": raw.get("58", ""),
        "Sender": raw.get("49", ""),
        "Target": raw.get("56", ""),
        "Raw": line,
    }


def parse_logs(text):
    rows = []
    for line in text.splitlines():
        parsed = parse_fix(line.strip())
        if parsed:
            rows.append(parsed)
    return rows


def analyze(rows):
    if not rows:
        return {}

    first = rows[0]
    last = rows[-1]

    rejected = any(r["Status"] == "Rejected" or r["Execution"] == "Rejected" for r in rows)
    cancelled = any(r["Status"] == "Cancelled" or r["Execution"] == "Cancelled" for r in rows)
    partial = any(r["Status"] == "Partially Filled" or r["Execution"] == "Partial Fill" for r in rows)
    filled = any(r["Status"] == "Filled" or r["Execution"] == "Fill" for r in rows)

    if rejected:
        severity = "High"
        root = "Order was rejected by bridge or liquidity provider."
        action = "Check rejection reason, symbol mapping, account permission, market session and LP pricing."
        box = "danger"
    elif cancelled:
        severity = "Medium"
        root = "Order was cancelled before completion."
        action = "Check whether cancellation came from client, bridge timeout, or LP."
        box = "warning"
    elif filled and partial:
        severity = "Low"
        root = "Order was fully executed in multiple partial fills."
        action = "No issue. Explain to client that liquidity was filled in parts."
        box = "success"
    elif filled:
        severity = "Low"
        root = "Order was fully executed successfully."
        action = "No action required."
        box = "success"
    elif partial:
        severity = "Medium"
        root = "Order is partially filled."
        action = "Check LP depth and remaining quantity."
        box = "warning"
    else:
        severity = "Medium"
        root = "Order status is not final in uploaded logs."
        action = "Upload next log lines or check bridge/LP response."
        box = "warning"

    summary = (
        f"{first.get('Side')} {first.get('Order Type')} order for "
        f"{first.get('Symbol')} quantity {first.get('Order Qty')} "
        f"on account {first.get('Account')}. Final status: {last.get('Status')}. "
        f"Average price: {last.get('Avg Price')}."
    )

    return {
        "summary": summary,
        "severity": severity,
        "root": root,
        "action": action,
        "box": box,
    }


with st.sidebar:
    st.markdown("## 📊 FIX Log Explainer")
    st.caption("Premium log analyzer for Forex brokers.")
    st.divider()

    mode = st.radio(
        "Input Mode",
        ["Paste Logs", "Upload File", "Use Sample"],
        index=0
    )

    st.divider()
    st.markdown("### Supported")
    st.markdown("- FIX 4.2 / 4.4 / 5.0\n- Centroid\n- Bridge Logs\n- LP Logs")


st.markdown("# 🚀 FIX Log Explainer")
st.markdown("### Premium FIX, Bridge & Liquidity Log Analyzer")

log_text = ""

st.markdown('<div class="card">', unsafe_allow_html=True)

if mode == "Paste Logs":
    log_text = st.text_area(
        "Paste your FIX logs here",
        height=280,
        placeholder="Paste raw FIX logs here..."
    )

elif mode == "Upload File":
    uploaded = st.file_uploader(
        "Upload FIX log file",
        type=["txt", "log", "fix"]
    )
    if uploaded:
        log_text = uploaded.read().decode("utf-8", errors="ignore")

else:
    log_text = SAMPLE_LOG
    st.text_area("Sample logs", value=SAMPLE_LOG, height=280)

st.markdown('</div>', unsafe_allow_html=True)

if st.button("🚀 Analyze Logs", use_container_width=True):
    if not log_text.strip():
        st.warning("Please paste or upload logs first.")
        st.stop()

    rows = parse_logs(log_text)

    if not rows:
        st.error("No valid FIX logs found.")
        st.stop()

    df = pd.DataFrame(rows)
    result = analyze(rows)

    col1, col2, col3, col4 = st.columns(4)

    metrics = [
        ("Messages", len(df)),
        ("Symbol", df["Symbol"].replace("", pd.NA).dropna().iloc[0] if not df["Symbol"].replace("", pd.NA).dropna().empty else "-"),
        ("Final Status", df.iloc[-1]["Status"]),
        ("Severity", result["severity"]),
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

    st.markdown("## Executive Summary")
    st.markdown(
        f"""
        <div class="{result['box']}">
        <b>Simple Explanation:</b><br><br>
        {result['summary']}
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Root Cause")
        st.markdown(f'<div class="card">{result["root"]}</div>', unsafe_allow_html=True)

    with c2:
        st.markdown("### Recommended Action")
        st.markdown(f'<div class="card">{result["action"]}</div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📋 Decoded Logs", "🕒 Timeline", "📊 Analytics", "📄 Export"])

    with tab1:
        st.dataframe(df.drop(columns=["Raw"]), use_container_width=True)

    with tab2:
        timeline = df[["Time", "Execution", "Status", "Message", "Last Qty", "Last Price"]]
        st.dataframe(timeline, use_container_width=True)

    with tab3:
        status_count = df["Status"].replace("", "Unknown").value_counts().reset_index()
        status_count.columns = ["Status", "Count"]
        fig = px.pie(status_count, names="Status", values="Count", title="Status Distribution")
        st.plotly_chart(fig, use_container_width=True)

    with tab4:
        report = f"""
FIX LOG INCIDENT REPORT

Summary:
{result['summary']}

Root Cause:
{result['root']}

Recommended Action:
{result['action']}
"""
        st.text_area("Client Report", report, height=250)

        st.download_button(
            "Download Report",
            report,
            file_name="fix_log_report.txt",
            mime="text/plain",
            use_container_width=True,
        )

else:
    st.markdown("""
    <div class="card">
    <h2>What this tool does</h2>
    <p>
    Paste or upload FIX logs. The tool will decode the messages, explain the order lifecycle,
    detect issues, identify the issue source, and generate a client-friendly report.
    </p>
    </div>
    """, unsafe_allow_html=True)
