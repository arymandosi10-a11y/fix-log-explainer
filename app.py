import re
from datetime import datetime
from collections import defaultdict

import pandas as pd
import plotly.express as px
import streamlit as st


# ==============================
# PAGE CONFIG
# ==============================

st.set_page_config(
    page_title="FIX Log Explainer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ==============================
# PREMIUM CSS
# ==============================

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #07111f 0%, #0b1628 40%, #111827 100%);
        color: #f8fafc;
    }

    section[data-testid="stSidebar"] {
        background: #07111f;
        border-right: 1px solid rgba(148, 163, 184, 0.2);
    }

    .main-title {
        font-size: 42px;
        font-weight: 800;
        color: #ffffff;
        margin-bottom: 4px;
    }

    .subtitle {
        color: #94a3b8;
        font-size: 16px;
        margin-bottom: 25px;
    }

    .metric-card {
        background: rgba(15, 23, 42, 0.95);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 18px;
        padding: 22px;
        box-shadow: 0 15px 35px rgba(0,0,0,0.25);
    }

    .metric-label {
        color: #94a3b8;
        font-size: 13px;
    }

    .metric-value {
        color: #ffffff;
        font-size: 28px;
        font-weight: 800;
    }

    .success-box {
        background: rgba(22, 163, 74, 0.15);
        border: 1px solid rgba(34, 197, 94, 0.35);
        padding: 18px;
        border-radius: 14px;
        color: #dcfce7;
    }

    .warning-box {
        background: rgba(234, 179, 8, 0.15);
        border: 1px solid rgba(234, 179, 8, 0.35);
        padding: 18px;
        border-radius: 14px;
        color: #fef9c3;
    }

    .danger-box {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.35);
        padding: 18px;
        border-radius: 14px;
        color: #fee2e2;
    }

    .info-box {
        background: rgba(59, 130, 246, 0.15);
        border: 1px solid rgba(59, 130, 246, 0.35);
        padding: 18px;
        border-radius: 14px;
        color: #dbeafe;
    }

    .section-card {
        background: rgba(15, 23, 42, 0.92);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 18px;
        padding: 22px;
        margin-top: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.25);
    }

    .small-muted {
        color: #94a3b8;
        font-size: 13px;
    }

    h1, h2, h3 {
        color: #ffffff !important;
    }

    div[data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==============================
# FIX DICTIONARIES
# ==============================

FIX_TAGS = {
    "8": "BeginString",
    "9": "BodyLength",
    "35": "MsgType",
    "34": "MsgSeqNum",
    "49": "SenderCompID",
    "52": "SendingTime",
    "56": "TargetCompID",
    "1": "Account",
    "6": "AvgPx",
    "11": "ClOrdID",
    "14": "CumQty",
    "17": "ExecID",
    "31": "LastPx",
    "32": "LastQty",
    "37": "OrderID",
    "38": "OrderQty",
    "39": "OrdStatus",
    "40": "OrdType",
    "44": "Price",
    "54": "Side",
    "55": "Symbol",
    "58": "Text",
    "59": "TimeInForce",
    "60": "TransactTime",
    "150": "ExecType",
    "151": "LeavesQty",
    "10": "Checksum",
}

MSG_TYPE = {
    "D": "New Order Single",
    "8": "Execution Report",
    "F": "Order Cancel Request",
    "G": "Order Replace Request",
    "9": "Order Cancel Reject",
    "j": "Business Message Reject",
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

SIDE = {
    "1": "BUY",
    "2": "SELL",
}

ORDER_TYPE = {
    "1": "Market",
    "2": "Limit",
    "3": "Stop",
    "4": "Stop Limit",
}

TIF = {
    "0": "Day",
    "1": "GTC",
    "3": "IOC",
    "4": "FOK",
}


# ==============================
# SAMPLE LOG
# ==============================

SAMPLE_LOG = """20260623-02:57:55.869897000 [in] : 8=FIX.4.4|9=184|35=D|34=3862|49=TD_Mazi_Finance_2_FIX|52=20260623-02:57:55.850|56=CENTROID_SOL|1=tem_Mazifinance_2|11=LuOFHPNVOXS6z|38=5000|40=1|44=63.488|54=1|55=XAGUSD|59=3|60=20260623-02:57:55.850|10=240|
20260623-02:57:55.870176000 [out] : 8=FIX.4.4|9=280|35=8|34=3866|49=CENTROID_SOL|52=20260623-02:57:55.870|56=TD_Mazi_Finance_2_FIX|1=tem_Mazifinance_2|6=0.0000000000|11=LuOFHPNVOXS6z|14=0.00|17=7168138|31=0.0000000000|32=0.00|37=7168138|38=5000.00|39=0|40=1|54=1|55=XAGUSD|58=New Request|59=3|60=20260623-02:57:55|150=0|151=5000.00|10=051|
20260623-02:57:55.911589000 [out] : 8=FIX.4.4|9=286|35=8|34=3867|49=CENTROID_SOL|52=20260623-02:57:55.911|56=TD_Mazi_Finance_2_FIX|1=tem_Mazifinance_2|6=63.4840000000|11=LuOFHPNVOXS6z|14=2500.00|17=7168138|31=63.4840000000|32=2500.00|37=7168138|38=5000.00|39=1|40=1|54=1|55=XAGUSD|58=Processed|59=3|60=20260623-02:57:55|150=1|151=2500.00|10=111|
20260623-02:57:55.911905000 [out] : 8=FIX.4.4|9=283|35=8|34=3868|49=CENTROID_SOL|52=20260623-02:57:55.911|56=TD_Mazi_Finance_2_FIX|1=tem_Mazifinance_2|6=63.4840000000|11=LuOFHPNVOXS6z|14=5000.00|17=7168138|31=63.4830000000|32=2500.00|37=7168138|38=5000.00|39=2|40=1|54=1|55=XAGUSD|58=Processed|59=3|60=20260623-02:57:55|150=2|151=0.00|10=213|"""


# ==============================
# FUNCTIONS
# ==============================

def safe_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


def extract_timestamp(line):
    match = re.match(r"^(\d{8}-\d{2}:\d{2}:\d{2}\.\d+)", line)
    if match:
        return match.group(1)
    return ""


def parse_fix_message(line):
    if "|" not in line or "=" not in line:
        return None

    direction = "Unknown"
    if "[in]" in line:
        direction = "Client → Bridge / LP"
    elif "[out]" in line:
        direction = "Bridge / LP → Client"

    timestamp = extract_timestamp(line)

    fix_part = line.split(":", 1)[-1].strip()
    pairs = fix_part.split("|")

    raw = {}

    for pair in pairs:
        if "=" in pair:
            tag, value = pair.split("=", 1)
            raw[tag] = value

    row = {
        "Timestamp": timestamp,
        "Direction": direction,
        "Msg Type": MSG_TYPE.get(raw.get("35", ""), raw.get("35", "")),
        "Account": raw.get("1", ""),
        "Client Order ID": raw.get("11", ""),
        "Order ID": raw.get("37", ""),
        "Symbol": raw.get("55", ""),
        "Side": SIDE.get(raw.get("54", ""), raw.get("54", "")),
        "Order Type": ORDER_TYPE.get(raw.get("40", ""), raw.get("40", "")),
        "TIF": TIF.get(raw.get("59", ""), raw.get("59", "")),
        "Order Qty": raw.get("38", ""),
        "Cum Qty": raw.get("14", ""),
        "Last Qty": raw.get("32", ""),
        "Leaves Qty": raw.get("151", ""),
        "Requested Price": raw.get("44", ""),
        "Last Price": raw.get("31", ""),
        "Avg Price": raw.get("6", ""),
        "Order Status": ORDER_STATUS.get(raw.get("39", ""), raw.get("39", "")),
        "Execution Type": EXEC_TYPE.get(raw.get("150", ""), raw.get("150", "")),
        "Message": raw.get("58", ""),
        "Sender": raw.get("49", ""),
        "Target": raw.get("56", ""),
        "Seq No": raw.get("34", ""),
        "Raw": line,
    }

    return row


def parse_logs(log_text):
    rows = []
    for line in log_text.splitlines():
        parsed = parse_fix_message(line.strip())
        if parsed:
            rows.append(parsed)
    return rows


def group_orders(rows):
    groups = defaultdict(list)
    for row in rows:
        key = row.get("Client Order ID") or row.get("Order ID") or "Unknown"
        groups[key].append(row)
    return groups


def calculate_latency_ms(rows):
    timestamps = []
    for row in rows:
        ts = row.get("Timestamp")
        if not ts:
            continue
        try:
            dt = datetime.strptime(ts[:24], "%Y%m%d-%H:%M:%S.%f")
            timestamps.append(dt)
        except Exception:
            pass

    if len(timestamps) < 2:
        return 0

    return round((max(timestamps) - min(timestamps)).total_seconds() * 1000, 3)


def analyze_order(rows):
    if not rows:
        return {}

    first = rows[0]
    last = rows[-1]

    rejected = any(r["Order Status"] == "Rejected" or r["Execution Type"] == "Rejected" for r in rows)
    cancelled = any(r["Order Status"] == "Cancelled" or r["Execution Type"] == "Cancelled" for r in rows)
    partial = any(r["Order Status"] == "Partially Filled" or r["Execution Type"] == "Partial Fill" for r in rows)
    filled = any(r["Order Status"] == "Filled" or r["Execution Type"] == "Fill" for r in rows)
    new = any(r["Order Status"] == "New" or r["Execution Type"] == "New" for r in rows)

    symbol = first.get("Symbol") or last.get("Symbol")
    side = first.get("Side") or last.get("Side")
    account = first.get("Account") or last.get("Account")
    order_qty = first.get("Order Qty") or last.get("Order Qty")
    avg_price = last.get("Avg Price")
    final_status = last.get("Order Status")
    message = last.get("Message")
    latency = calculate_latency_ms(rows)

    issue_source = "No issue"
    severity = "Low"
    action = "No technical action required."
    root_cause = "Order lifecycle completed normally."

    if rejected:
        severity = "High"
        issue_source = "LP / Bridge / Symbol / Account"
        root_cause = "The order was rejected by the execution side."
        action = "Check rejection message, symbol mapping, trading session, account permissions, bridge route, and LP pricing."
    elif cancelled:
        severity = "Medium"
        issue_source = "Client / Bridge / LP"
        root_cause = "The order was cancelled before full execution."
        action = "Check whether cancellation was requested by client, bridge timeout, or LP."
    elif filled and partial:
        severity = "Low"
        issue_source = "Liquidity fragmentation"
        root_cause = "The order was fully executed in multiple fills."
        action = "No fix required. Explain to client that the full quantity was completed in parts due to available liquidity."
    elif filled:
        severity = "Low"
        issue_source = "No issue"
        root_cause = "The order was fully executed successfully."
        action = "No action required."
    elif partial:
        severity = "Medium"
        issue_source = "Liquidity Provider"
        root_cause = "Only part of the requested quantity was filled."
        action = "Check remaining quantity, LP depth, market liquidity, and routing configuration."
    elif new:
        severity = "Medium"
        issue_source = "Pending execution"
        root_cause = "The order was accepted but no final execution status was found in the uploaded logs."
        action = "Upload more logs after this time or check bridge and LP response."

    simple_summary = (
        f"A {side} {first.get('Order Type', '')} order was placed for {symbol} "
        f"with quantity {order_qty} on account {account}. "
        f"Final status is {final_status}. "
    )

    if avg_price and safe_float(avg_price) > 0:
        simple_summary += f"The average execution price was {avg_price}. "

    if latency:
        simple_summary += f"Total lifecycle latency was around {latency} ms. "

    if message:
        simple_summary += f"System message: {message}."

    return {
        "Client Order ID": first.get("Client Order ID"),
        "Order ID": last.get("Order ID"),
        "Account": account,
        "Symbol": symbol,
        "Side": side,
        "Order Qty": order_qty,
        "Final Status": final_status,
        "Average Price": avg_price,
        "Latency ms": latency,
        "Severity": severity,
        "Issue Source": issue_source,
        "Root Cause": root_cause,
        "Action": action,
        "Simple Summary": simple_summary,
        "Message Count": len(rows),
    }


def build_timeline(rows):
    timeline = []
    for i, row in enumerate(rows, start=1):
        event = row["Execution Type"] or row["Order Status"] or row["Msg Type"]
        details = ""

        if event == "New":
            details = "Order accepted by execution system."
        elif event == "Partial Fill":
            details = f"Partial execution: {row.get('Last Qty')} filled at {row.get('Last Price')}."
        elif event == "Fill":
            details = f"Final execution: {row.get('Last Qty')} filled at {row.get('Last Price')}."
        elif event == "Rejected":
            details = f"Rejected: {row.get('Message')}"
        elif event == "Cancelled":
            details = "Order cancelled."
        else:
            details = row.get("Message") or row.get("Msg Type")

        timeline.append(
            {
                "Step": i,
                "Time": row.get("Timestamp"),
                "Event": event,
                "Status": row.get("Order Status"),
                "Details": details,
                "Direction": row.get("Direction"),
            }
        )

    return pd.DataFrame(timeline)


def create_client_report(analysis, timeline_df):
    report = f"""
FIX LOG INCIDENT REPORT

Client Order ID: {analysis.get("Client Order ID")}
Order ID: {analysis.get("Order ID")}
Account: {analysis.get("Account")}
Symbol: {analysis.get("Symbol")}
Side: {analysis.get("Side")}
Quantity: {analysis.get("Order Qty")}
Final Status: {analysis.get("Final Status")}
Average Price: {analysis.get("Average Price")}
Latency: {analysis.get("Latency ms")} ms
Severity: {analysis.get("Severity")}

SIMPLE SUMMARY
{analysis.get("Simple Summary")}

ROOT CAUSE
{analysis.get("Root Cause")}

ISSUE SOURCE
{analysis.get("Issue Source")}

RECOMMENDED ACTION
{analysis.get("Action")}

ORDER TIMELINE
"""

    for _, row in timeline_df.iterrows():
        report += f"\nStep {row['Step']} | {row['Time']} | {row['Event']} | {row['Details']}"

    return report


# ==============================
# SIDEBAR
# ==============================

with st.sidebar:
    st.markdown("## 📊 FIX Log Explainer")
    st.markdown("Premium log analyzer for Forex brokers.")
    st.divider()

    mode = st.radio(
        "Input Mode",
        ["Upload File", "Paste Logs", "Use Sample"],
    )

    st.divider()

    st.markdown("### Supported")
    st.markdown(
        """
        - FIX 4.2 / 4.4 / 5.0  
        - Centroid FIX logs  
        - Bridge execution logs  
        - LP order flow  
        - Client order lifecycle  
        """
    )

    st.divider()
    st.caption("Version 1.0 | Streamlit Cloud Ready")


# ==============================
# HEADER
# ==============================

st.markdown('<div class="main-title">FIX Log Explainer</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">AI-style FIX, bridge and liquidity log analyzer for brokers, support teams and non-technical users.</div>',
    unsafe_allow_html=True,
)


# ==============================
# INPUT
# ==============================

log_text = ""

if mode == "Upload File":
    uploaded_file = st.file_uploader("Upload FIX log file", type=["txt", "log", "fix"])
    if uploaded_file:
        log_text = uploaded_file.read().decode("utf-8", errors="ignore")

elif mode == "Paste Logs":
    log_text = st.text_area("Paste FIX logs here", height=260)

else:
    log_text = SAMPLE_LOG
    st.text_area("Sample FIX logs", value=SAMPLE_LOG, height=260)


analyze = st.button("🚀 Analyze Logs", use_container_width=True)


# ==============================
# ANALYSIS OUTPUT
# ==============================

if analyze:
    if not log_text.strip():
        st.warning("Please upload or paste FIX logs first.")
        st.stop()

    rows = parse_logs(log_text)

    if not rows:
        st.error("No valid FIX messages found.")
        st.stop()

    df = pd.DataFrame(rows)
    grouped = group_orders(rows)

    all_analyses = []
    for _, order_rows in grouped.items():
        all_analyses.append(analyze_order(order_rows))

    summary_df = pd.DataFrame(all_analyses)
    main_analysis = all_analyses[0]
    timeline_df = build_timeline(grouped[main_analysis["Client Order ID"]])

    # METRICS
    total_orders = len(grouped)
    total_msgs = len(rows)
    filled_count = len(summary_df[summary_df["Final Status"] == "Filled"])
    rejected_count = len(summary_df[summary_df["Final Status"] == "Rejected"])

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Total Orders</div>
                <div class="metric-value">{total_orders}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">FIX Messages</div>
                <div class="metric-value">{total_msgs}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Filled Orders</div>
                <div class="metric-value">{filled_count}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">Rejected Orders</div>
                <div class="metric-value">{rejected_count}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("## Executive Summary")

    severity = main_analysis["Severity"]

    if severity == "High":
        box_class = "danger-box"
    elif severity == "Medium":
        box_class = "warning-box"
    else:
        box_class = "success-box"

    st.markdown(
        f"""
        <div class="{box_class}">
            <b>Simple Explanation:</b><br><br>
            {main_analysis["Simple Summary"]}
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Root Cause")
        st.markdown(
            f"""
            <div class="info-box">
            {main_analysis["Root Cause"]}<br><br>
            <b>Issue Source:</b> {main_analysis["Issue Source"]}
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown("### Recommended Action")
        st.markdown(
            f"""
            <div class="warning-box">
            {main_analysis["Action"]}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # TABS
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📌 Order Summary",
            "🕒 Timeline",
            "📊 Analytics",
            "🔍 Raw FIX Decode",
            "📄 Export Report",
        ]
    )

    with tab1:
        st.subheader("Order-Level Summary")
        st.dataframe(summary_df, use_container_width=True)

    with tab2:
        st.subheader("Execution Timeline")
        st.dataframe(timeline_df, use_container_width=True)

        fig = px.timeline(
            timeline_df,
            x_start="Step",
            x_end="Step",
            y="Event",
            color="Status",
            hover_data=["Time", "Details", "Direction"],
            title="Order Lifecycle Timeline",
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("Execution Analytics")

        col_a, col_b = st.columns(2)

        with col_a:
            status_counts = df["Order Status"].replace("", "Unknown").value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]

            fig_status = px.pie(
                status_counts,
                names="Status",
                values="Count",
                title="Order Status Distribution",
            )
            st.plotly_chart(fig_status, use_container_width=True)

        with col_b:
            exec_counts = df["Execution Type"].replace("", "Unknown").value_counts().reset_index()
            exec_counts.columns = ["Execution Type", "Count"]

            fig_exec = px.bar(
                exec_counts,
                x="Execution Type",
                y="Count",
                title="Execution Type Count",
            )
            st.plotly_chart(fig_exec, use_container_width=True)

        st.markdown("### Latency")
        st.info(f"Detected lifecycle latency: {main_analysis['Latency ms']} ms")

    with tab4:
        st.subheader("Decoded FIX Messages")
        visible_cols = [
            "Timestamp",
            "Direction",
            "Msg Type",
            "Account",
            "Client Order ID",
            "Order ID",
            "Symbol",
            "Side",
            "Order Type",
            "Order Qty",
            "Cum Qty",
            "Last Qty",
            "Leaves Qty",
            "Requested Price",
            "Last Price",
            "Avg Price",
            "Order Status",
            "Execution Type",
            "Message",
            "Sender",
            "Target",
            "Seq No",
        ]
        st.dataframe(df[visible_cols], use_container_width=True)

        with st.expander("View Raw Logs"):
            for row in rows:
                st.code(row["Raw"])

    with tab5:
        st.subheader("Client-Friendly Report")

        report = create_client_report(main_analysis, timeline_df)

        st.text_area("Report", report, height=420)

        st.download_button(
            "Download TXT Report",
            report,
            file_name="fix_log_incident_report.txt",
            mime="text/plain",
            use_container_width=True,
        )

        csv_data = summary_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV Summary",
            csv_data,
            file_name="fix_log_summary.csv",
            mime="text/csv",
            use_container_width=True,
        )

else:
    st.markdown(
        """
        <div class="section-card">
        <h3>What this tool does</h3>
        <p>
        Upload or paste FIX logs and this tool will automatically decode the messages,
        explain the order lifecycle, detect issues, identify the possible source,
        and generate a client-friendly incident report.
        </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
