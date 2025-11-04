# Banking / Customer Deposits Tracker — Streamlit App
# ---------------------------------------------------
# Features
# - Upload existing workbook OR start fresh
# - Per-transaction daily entry (Date, Customer, Deposit, Rate, Amount Paid)
# - Auto-calc Total Amount (Deposit*Rate), Outstanding, Status
# - Customer Summary (totals & outstanding)
# - Purchase/Payment Summary (paid vs outstanding)
# - Daily Summary & Profit (Expenses entered manually)
# - Download updated Excel with 4 sheets

import streamlit as st
import pandas as pd
from datetime import date
import io

# ---------------- AUTHENTICATION ---------------- #
st.set_page_config(page_title="Banking Deposits Tracker", page_icon="💼")

# Ask for password stored in Streamlit Secrets
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state.password_correct = False

    password = st.text_input("Enter Password", type="password")

    if password == st.secrets["app_password"]:
        st.session_state.password_correct = True
    else:
        st.error("Incorrect password")

    return st.session_state.password_correct

if not check_password():
    st.stop()


st.set_page_config(page_title="Banking Deposits Tracker", page_icon="💼", layout="wide")

MAIN_SHEET = "Main Data"
CUSTOMER_SHEET = "Customer Summary"
PURCHASE_SHEET = "Purchase Summary"
DAILY_SHEET = "Daily Summary"

# -----------------------------
# Helpers
# -----------------------------

def _empty_frames():
    main = pd.DataFrame(columns=[
        'Date', 'Customer', 'Deposit Amount', 'Rate', 'Total Amount', 'Amount Paid', 'Outstanding', 'Status'
    ])
    customer = pd.DataFrame(columns=['Customer', 'Total Deposit', 'Total Paid', 'Outstanding', 'Status'])
    purchase = pd.DataFrame(columns=['Metric', 'Value'])
    daily = pd.DataFrame(columns=['Metric', 'Value'])
    return {MAIN_SHEET: main, CUSTOMER_SHEET: customer, PURCHASE_SHEET: purchase, DAILY_SHEET: daily}


def _load_workbook(file) -> dict:
    try:
        book = pd.read_excel(file, sheet_name=None)
        # Ensure all 4 sheets exist
        frames = _empty_frames()
        for sheet in [MAIN_SHEET, CUSTOMER_SHEET, PURCHASE_SHEET, DAILY_SHEET]:
            if sheet in book:
                frames[sheet] = book[sheet]
        return frames
    except Exception:
        return _empty_frames()


def _sanitize_types(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    # Date to date
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
    # Numeric columns
    for c in ['Deposit Amount', 'Rate', 'Total Amount', 'Amount Paid', 'Outstanding']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
    # Status
    if 'Outstanding' in df.columns:
        df['Status'] = df['Outstanding'].apply(lambda x: 'Paid' if x <= 0 else 'Not Paid')
    return df


def _recompute_from_main(main_df: pd.DataFrame, expense: float, other_expense: float) -> dict:
    main = _sanitize_types(main_df)

    # --- Customer Summary
    if main.empty:
        cust = pd.DataFrame(columns=['Customer', 'Total Deposit', 'Total Paid', 'Outstanding', 'Status'])
        paid_total = 0.0
        outstanding_total = 0.0
        total_amount_sum = 0.0
    else:
        grp = main.groupby('Customer', dropna=False).agg({
            'Deposit Amount': 'sum',
            'Amount Paid': 'sum',
            'Outstanding': 'sum',
            'Total Amount': 'sum'
        }).reset_index()
        grp.rename(columns={'Deposit Amount': 'Total Deposit', 'Amount Paid': 'Total Paid'}, inplace=True)
        grp['Status'] = grp['Outstanding'].apply(lambda x: 'Paid' if x <= 0 else 'Not Paid')
        cust = grp[['Customer', 'Total Deposit', 'Total Paid', 'Outstanding', 'Status']]
        paid_total = main['Amount Paid'].sum()
        outstanding_total = main['Outstanding'].sum()
        total_amount_sum = main['Total Amount'].sum()

    # --- Purchase/Payment Summary
    purchase = pd.DataFrame({
        'Metric': [
            'Total Amount (Σ deposit*rate)',
            'Total Paid',
            'Total Outstanding',
            'Paid Share (%)',
            'Outstanding Share (%)',
        ],
        'Value': [
            total_amount_sum,
            paid_total,
            outstanding_total,
            (paid_total / total_amount_sum * 100) if total_amount_sum else 0.0,
            (outstanding_total / total_amount_sum * 100) if total_amount_sum else 0.0,
        ]
    })

    # --- Daily Summary (Profit)
    # Profit = Sum(Total Amount) - Total Paid - Expense - Other Expense
    profit = total_amount_sum - paid_total - expense - other_expense
    daily = pd.DataFrame({
        'Metric': ['Expense', 'Other Expense', 'Sum of Total Amount', 'Total Paid', 'Profit'],
        'Value': [expense, other_expense, total_amount_sum, paid_total, profit]
    })

    return {MAIN_SHEET: main, CUSTOMER_SHEET: cust, PURCHASE_SHEET: purchase, DAILY_SHEET: daily}


def _to_excel_bytes(frames: dict) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        for name, df in frames.items():
            # order columns neatly for main
            if name == MAIN_SHEET and not df.empty:
                df = df[['Date','Customer','Deposit Amount','Rate','Total Amount','Amount Paid','Outstanding','Status']]
            df.to_excel(writer, sheet_name=name, index=False)
    buffer.seek(0)
    return buffer.read()

# -----------------------------
# Load/Init Data
# -----------------------------
with st.sidebar:
    st.markdown("### 📦 Workbook Source")
    uploaded = st.file_uploader("Upload existing Excel (optional)", type=["xlsx", "xlsm", "xls"])

if uploaded:
    frames = _load_workbook(uploaded)
else:
    frames = _empty_frames()

# Persist frames in session
if 'frames' not in st.session_state:
    st.session_state.frames = frames
else:
    # Merge freshly loaded frames when new upload happens
    if uploaded:
        st.session_state.frames = frames

frames = st.session_state.frames
main_df = _sanitize_types(frames[MAIN_SHEET])

# -----------------------------
# Sidebar: Expenses & Controls
# -----------------------------
with st.sidebar:
    st.markdown("### 💸 Expenses (Today)")
    expense = st.number_input("Expense", min_value=0.0, value=float(frames[DAILY_SHEET]['Value'][0]) if not frames[DAILY_SHEET].empty and 'Expense' in frames[DAILY_SHEET]['Metric'].values else 0.0, step=100.0)
    other_expense = st.number_input("Other Expense", min_value=0.0, value=float(frames[DAILY_SHEET]['Value'][1]) if not frames[DAILY_SHEET].empty and 'Other Expense' in frames[DAILY_SHEET]['Metric'].values else 0.0, step=100.0)
    st.markdown("---")
    st.markdown("### 💾 Export")
    recomputed = _recompute_from_main(main_df, expense, other_expense)
    export_bytes = _to_excel_bytes(recomputed)
    st.download_button("⬇️ Download Updated Excel", data=export_bytes, file_name="banking_tracker.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# -----------------------------
# Main Layout
# -----------------------------
colA, colB = st.columns([1, 1])
with colA:
    st.title("💼 Banking / Deposits Tracker")
    st.caption("Per-transaction daily entries → auto summaries & profit. Upload previous workbook or start fresh.")

# -----------------------------
# Entry Form (Per Transaction, Per Day)
# -----------------------------
with st.expander("➕ Add Transaction", expanded=True):
    form = st.form("entry_form")
    c1, c2, c3 = form.columns([1, 1, 1])

    entry_date = c1.date_input("Date", value=date.today())

    # Customer dropdown with "+ Add new" option
    existing_customers = sorted([x for x in main_df['Customer'].dropna().unique()]) if not main_df.empty else []
    options = ["+ Add new customer"] + existing_customers
    selected = c2.selectbox("Customer", options)
    if selected == "+ Add new customer":
        customer = c2.text_input("New Customer Name", key="new_customer_input")
    else:
        customer = selected

    deposit = c3.number_input("Deposit Amount", min_value=0.0, step=100.0)

    c4, c5, c6 = form.columns([1, 1, 1])
    rate = c4.number_input("Rate (currency rate for this entry)", min_value=0.0, step=0.1)
    amount_paid = c5.number_input("Amount Paid (optional)", min_value=0.0, step=100.0, value=0.0)

    # Live preview
    total_amount = deposit * rate
    outstanding = max(total_amount - amount_paid, 0.0)
    status = "Paid" if outstanding <= 0.0 and total_amount > 0 else ("Not Paid" if total_amount > 0 else "-")

    c4.metric("Total Amount", f"{total_amount:,.2f}")
    c5.metric("Outstanding", f"{outstanding:,.2f}")
    c6.metric("Status", status)

    submitted = form.form_submit_button("Add Entry")

    if submitted:
        if not customer or customer.strip() == "":
            st.error("Please enter a customer name.")
        else:
            new_row = pd.DataFrame([{
                'Date': entry_date,
                'Customer': customer.strip(),
                'Deposit Amount': deposit,
                'Rate': rate,
                'Total Amount': total_amount,
                'Amount Paid': amount_paid,
                'Outstanding': total_amount - amount_paid,
                'Status': 'Paid' if (total_amount - amount_paid) <= 0 else 'Not Paid'
            }])
            updated_main = pd.concat([main_df, new_row], ignore_index=True)
            st.session_state.frames = _recompute_from_main(updated_main, expense, other_expense)
            st.success("Entry added and summaries updated.")
            st.experimental_rerun()

# -----------------------------
# Dashboards
# -----------------------------
re_frames = st.session_state.frames

# Top KPIs
k1, k2, k3, k4 = st.columns(4)
main_now = re_frames[MAIN_SHEET]
if not main_now.empty:
    sum_total_amt = float(main_now['Total Amount'].sum())
    sum_paid = float(main_now['Amount Paid'].sum())
    sum_out = float(main_now['Outstanding'].sum())
else:
    sum_total_amt = sum_paid = sum_out = 0.0

k1.metric("Σ Total Amount", f"{sum_total_amt:,.2f}")
k2.metric("Σ Paid", f"{sum_paid:,.2f}")
k3.metric("Σ Outstanding", f"{sum_out:,.2f}")

# Profit from Daily sheet
daily_df = re_frames[DAILY_SHEET]
profit_val = float(daily_df.loc[daily_df['Metric']=='Profit','Value'].iloc[0]) if not daily_df.empty and 'Profit' in daily_df['Metric'].values else 0.0
k4.metric("Profit", f"{profit_val:,.2f}")

st.markdown("---")

# Tables
t1, t2 = st.tabs(["📄 Main Data", "👤 Customer Summary"])
with t1:
    st.dataframe(re_frames[MAIN_SHEET], use_container_width=True)
with t2:
    st.dataframe(re_frames[CUSTOMER_SHEET], use_container_width=True)

st.markdown("---")

cA, cB = st.columns(2)
with cA:
    st.subheader("📦 Purchase / Payment Summary")
    st.dataframe(re_frames[PURCHASE_SHEET], use_container_width=True)
with cB:
    st.subheader("📆 Daily Summary")
    st.dataframe(re_frames[DAILY_SHEET], use_container_width=True)

st.caption("Tip: Upload your last saved Excel in the sidebar to continue from previous data. Use the download button to export the updated workbook with all four sheets.")
