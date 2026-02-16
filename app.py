import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import io

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(page_title="Audit Dashboard", layout="wide")
st.title("📂 Audit Dashboard")

# =====================================================
# GOOGLE SHEETS HELPERS
# =====================================================
@st.cache_resource
def get_gsheet_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(creds)

@st.cache_data(show_spinner=False)
def get_worksheet_names(sheet_url):
    client = get_gsheet_client()
    sheet = client.open_by_url(sheet_url)
    return [ws.title for ws in sheet.worksheets()]

def load_google_sheet(sheet_url, worksheet_name):
    client = get_gsheet_client()
    sheet = client.open_by_url(sheet_url)
    ws = sheet.worksheet(worksheet_name)
    data = ws.get_all_records()
    return pd.DataFrame(data), ws

def write_back(ws, df):
    ws.clear()
    ws.update([df.columns.tolist()] + df.values.tolist())

# =====================================================
# SIDEBAR — DATA SOURCE
# =====================================================
st.sidebar.header("Data Source")
source = st.sidebar.radio(
    "Choose source",
    ["Upload File", "Google Sheets"],
    key="data_source"
)

# =====================================================
# RESET LOGIC (critical for responsiveness)
# =====================================================
def reset_state():
    for k in ["audit_df", "ws", "active_ws"]:
        if k in st.session_state:
            del st.session_state[k]

# =====================================================
# FILE UPLOAD MODE
# =====================================================
if source == "Upload File":
    reset_state()

    uploaded_file = st.sidebar.file_uploader(
        "Choose a CSV or Excel file",
        type=["csv", "xlsx"]
    )

    if uploaded_file:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        if "Audit Result" not in df.columns:
            df["Audit Result"] = "Pending"

        st.session_state.audit_df = df
        st.session_state.ws = None

# =====================================================
# GOOGLE SHEETS MODE
# =====================================================
elif source == "Google Sheets":
    sheet_url = st.sidebar.text_input(
        "Google Sheet URL",
        key="sheet_url"
    )

    if sheet_url:
        try:
            worksheet_names = get_worksheet_names(sheet_url)

            selected_ws = st.sidebar.radio(
                "Select Worksheet",
                worksheet_names,
                key="worksheet_radio"
            )

            # Instant reload on worksheet change
            if st.session_state.get("active_ws") != selected_ws:
                reset_state()
                st.session_state.active_ws = selected_ws
                df, ws = load_google_sheet(sheet_url, selected_ws)

                if "Audit Result" not in df.columns:
                    df["Audit Result"] = "Pending"

                st.session_state.audit_df = df
                st.session_state.ws = ws

        except Exception as e:
            st.sidebar.error(f"Error loading sheet: {e}")

# =====================================================
# MAIN AUDIT UI
# =====================================================
if "audit_df" in st.session_state:
    df = st.session_state.audit_df

    total = len(df)
    completed = len(df[df["Audit Result"] != "Pending"])

    col1, col2 = st.columns([3, 1])
    with col1:
        st.progress(completed / total if total else 0)
        st.write(f"**Progress:** {completed} / {total}")

    with col2:
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        st.download_button(
            "📥 Download CSV",
            buf.getvalue(),
            "audited_output.csv",
            "text/csv"
        )

    st.divider()

    # =================================================
    # TILE GRID
    # =================================================
    cols_per_row = 3
    for i in range(0, len(df), cols_per_row):
        row_slice = df.iloc[i:i + cols_per_row]
        cols = st.columns(cols_per_row)

        for j, (idx, row) in enumerate(row_slice.iterrows()):
            with cols[j]:
                with st.container(border=True):
                    st.subheader(f"Row {idx + 1}")

                    for col_name in df.columns[:4]:
                        st.write(f"**{col_name}:** {row[col_name]}")

                    st.write(f"**Status:** {row['Audit Result']}")

                    c1, c2 = st.columns(2)

                    if c1.button("✅ Yes", key=f"yes_{idx}_{st.session_state.get('active_ws')}"):
                        df.at[idx, "Audit Result"] = "Yes"
                        if st.session_state.ws:
                            write_back(st.session_state.ws, df)
                        st.rerun()

                    if c2.button("❌ No", key=f"no_{idx}_{st.session_state.get('active_ws')}"):
                        df.at[idx, "Audit Result"] = "No"
                        if st.session_state.ws:
                            write_back(st.session_state.ws, df)
                        st.rerun()

else:
    st.info("Select a data source to begin auditing.")
