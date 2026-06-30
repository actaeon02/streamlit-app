import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import dateutil.relativedelta
import altair as alt
import pytz

# --- Page Configuration ---
st.set_page_config(
    page_title="Personal Finance Tracker",
    page_icon="💸",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- App Title and Tab Menu ---
st.title("💸 Personal Finance Tracker")
menu = st.radio("📚 Select View", ["Expenses", "Income"], horizontal=True)

# --- Google Sheets Connection Setup ---
@st.cache_resource
def get_google_sheets_connection():
    try:
        gcp_secrets = st.secrets["connections"]["gsheets"]
        SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
        private_key = gcp_secrets["private_key"].replace("\\n", "\n")
        credentials = Credentials.from_service_account_info(
            {
                "type": gcp_secrets["type"],
                "project_id": gcp_secrets["project_id"],
                "private_key_id": gcp_secrets["private_key_id"],
                "private_key": private_key,
                "client_email": gcp_secrets["client_email"],
                "client_id": gcp_secrets["client_id"],
                "auth_uri": gcp_secrets["auth_uri"],
                "token_uri": gcp_secrets["token_uri"],
                "auth_provider_x509_cert_url": gcp_secrets["auth_provider_x509_cert_url"],
                "client_x509_cert_url": gcp_secrets["client_x509_cert_url"],
            },
            scopes=SCOPE
        )
        spreadsheet_url = gcp_secrets["spreadsheet"]
    except Exception:
        SERVICE_ACCOUNT_FILE = r"C:\\Users\\Mikael\\service_account_keys.json"
        SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPE)
        spreadsheet_url = "https://docs.google.com/spreadsheets/d/14XBx3LvGTUOmx5tN43OSWyabT5sdUHML2h2rfI6YemI/edit?gid=258870691"
    
    gc = gspread.authorize(credentials)
    sh = gc.open_by_url(spreadsheet_url)
    return sh

@st.cache_data(ttl=60)  # Cache for 60 seconds
def load_sheet_data(sheet_name):
    sh = get_google_sheets_connection()
    ws = sh.worksheet(sheet_name)
    return pd.DataFrame(ws.get_all_records())

# Load data
sh = get_google_sheets_connection()
ws_expenses = sh.worksheet("Expenses")
ws_income = sh.worksheet("Income")
ws_budget = sh.worksheet("Budget")

expenses_df = load_sheet_data("Expenses")
income_df = load_sheet_data("Income")
budget_df = load_sheet_data("Budget")

# Preprocess dates and values
if not expenses_df.empty:
    expenses_df["Amount"] = pd.to_numeric(expenses_df["Amount"], errors="coerce")
    expenses_df.dropna(subset=["Amount"], inplace=True)
    expenses_df["Purchase Date"] = pd.to_datetime(expenses_df["Purchase Date"], errors="coerce")
    expenses_df["Timestamp"] = pd.to_datetime(expenses_df["Timestamp"], errors="coerce")
    expenses_df.dropna(subset=["Purchase Date", "Timestamp"], inplace=True)

if not income_df.empty:
    income_df["Income Amount"] = pd.to_numeric(income_df["Income Amount"], errors="coerce")
    income_df["Date"] = pd.to_datetime(income_df["Date"], errors="coerce")
    income_df.dropna(subset=["Date", "Income Amount"], inplace=True)

# Define monthly period range
today = datetime.today().date()
if today.day >= 28:
    period_start = today.replace(day=28)
    period_end = period_start + dateutil.relativedelta.relativedelta(months=1)
else:
    period_end = today.replace(day=28)
    period_start = period_end - dateutil.relativedelta.relativedelta(months=1)

period_start_dt = pd.to_datetime(period_start)
period_end_dt = pd.to_datetime(period_end)

expenses_period = expenses_df[
    (expenses_df["Purchase Date"] >= period_start_dt) & 
    (expenses_df["Purchase Date"] < period_end_dt)
].copy()

income_period = income_df[
    (income_df["Date"] >= period_start_dt) & 
    (income_df["Date"] < period_end_dt)
].copy()

# --- Expense Tab ---
if menu == "Expenses":
    st.header("💳 Expense Tracker")
    st.subheader("Record a New Expense")

    category_options = [
        "Bills",
        "Subscriptions",
        "Entertainment",
        "Food & Drink",
        "Groceries",
        "Health & Wellbeing",
        "Shopping",
        "Transport",
        "Travel",
        "Business",
        "Laundry",
        "Gifts",
        "Investment",
        "Credit Card Payment",
        "PayLater Payment",
        "Other",
    ]

    # Initialize session state keys if they don't exist
    if "selected_description" not in st.session_state:
        st.session_state.selected_description = "New Entry"
    if "form_amount" not in st.session_state:
        st.session_state.form_amount = 1000.00
    if "form_category" not in st.session_state:
        st.session_state.form_category = "Other"

    # Get a list of unique descriptions from expenses data
    unique_descriptions = ["New Entry"] + sorted(list(expenses_df["Item"].unique()))

    # Initialize form reset counter
    if "form_reset_counter" not in st.session_state:
        st.session_state.form_reset_counter = 0

    # Callback function to update form fields when description changes
    def update_fields():
        selected_desc = st.session_state.description_select
        st.session_state.selected_description = selected_desc
        
        if selected_desc != "New Entry":
            latest_record_df = expenses_df[
                expenses_df["Item"] == selected_desc
            ].sort_values("Purchase Date", ascending=False)

            if not latest_record_df.empty:
                # Update Amount
                st.session_state.form_amount = float(latest_record_df["Amount"].iloc[0])

                # Update Category
                prev_cat = latest_record_df["Category"].iloc[0]
                if prev_cat in category_options:
                    st.session_state.form_category = prev_cat
                else:
                    st.session_state.form_category = "Other"
        else:
            # Reset to defaults for new entry
            st.session_state.form_amount = 1000.00
            st.session_state.form_category = "Other"

        # Increment counter to force widget recreation
        st.session_state.form_reset_counter += 1

    # Description selector (outside form)
    selected_description = st.selectbox(
        "Description",
        unique_descriptions,
        key="description_select",
        on_change=update_fields,
    )

    # Get item description
    if selected_description == "New Entry":
        item = st.text_input("New Description", key="new_description_input")
    else:
        item = selected_description

    # Form for expense entry
    with st.form("expense_form", clear_on_submit=True):
        user = st.radio("Who?", ["Mikael", "Josephine"], key="expense_user")
        
        purchase_date = st.date_input(
            "Date", 
            value=datetime.today().date(),
            key="expense_date_input"
        )

        # CRITICAL FIX: Use session state value directly, not the key parameter
        amount = st.number_input(
            "Amount",
            min_value=1000.00,
            step=1000.00,
            format="%.2f",
            value=st.session_state.form_amount,
            # key="amount_input"
            key=f"amount_input_{st.session_state.get('form_reset_counter', 0)}"
        )

        category = st.selectbox(
            "Category",
            category_options,
            index=category_options.index(st.session_state.form_category) if st.session_state.form_category in category_options else category_options.index("Other"),
            # key="category_input"
            key=f"category_input_{st.session_state.get('form_reset_counter', 0)}"
        )

        method = st.radio(
            "Payment Method", 
            ["CC Mikael", "CC Josephine", "Debit", "Cash", "PayLater"], 
            key="expense_method"
        )

        submit = st.form_submit_button("➕ Add Expense")

        if submit and item and amount > 0:
            timestamp = datetime.now(pytz.timezone("Asia/Jakarta")).strftime(
                "%m/%d/%Y %H:%M:%S"
            )
            row = [
                timestamp,
                user,
                purchase_date.strftime("%m/%d/%Y"),
                item,
                amount,
                category,
                method,
            ]
            ws_expenses.append_row(row)
            
            # Clear cache to reload data
            st.cache_data.clear()
            
            st.success(f"Expense added: {item} - {amount:,.2f} IDR ({category})")
            
            # Reset to defaults for next entry
            st.session_state.form_amount = 1000.00
            st.session_state.form_category = "Other"
            st.session_state.selected_description = "New Entry"
            st.session_state.form_reset_counter += 1
            
            st.rerun()

    # Add filter option for CC/PayLater payments
    st.subheader("📊 Monthly Category Spending")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        exclude_cc_payments = st.checkbox(
            "Exclude CC/PayLater bill payments", 
            value=True,
            help="Exclude credit card and PayLater bill payments from spending view"
        )
    
    if not expenses_period.empty:
        target_categories = ["Bills", "Food & Drink", "Subscriptions", "Shopping"]
        
        # Filter based on checkbox
        if exclude_cc_payments:
            filtered = expenses_period[
                (expenses_period["Category"].isin(target_categories)) &
                (~expenses_period["Category"].isin(["Credit Card Payment", "PayLater Payment"]))
            ]
        else:
            filtered = expenses_period[
                (expenses_period["Category"].isin(target_categories))
            ]
        
        if not filtered.empty:
            category_spending = filtered.groupby("Category")["Amount"].sum().reset_index()
            full_category_df = pd.DataFrame({"Category": target_categories})
            category_spending = pd.merge(full_category_df, category_spending, on="Category", how="left").fillna(0)

            bar = alt.Chart(category_spending).mark_bar().encode(
                x=alt.X("Category", sort=target_categories, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Amount", title="Total Spending (IDR)"),
                color=alt.Color("Category", legend=None),
                tooltip=["Category", alt.Tooltip("Amount", format=",.2f")]
            )

            text = alt.Chart(category_spending).mark_text(
                align='center',
                baseline='bottom',
                color='white',
                dy=-10
            ).encode(
                x=alt.X("Category", sort=target_categories),
                y="Amount",
                text=alt.Text("Amount:Q", format=",.0f")
            )

            st.altair_chart(bar + text, use_container_width=True)
            st.dataframe(category_spending, column_config={
                "Amount": st.column_config.NumberColumn("Amount", format='accounting')
            }, use_container_width=True)
        else:
            st.info("No spending data for the selected categories this period.")

    # Spending per User
    st.subheader("📊 Total Spending Per User")
    if not expenses_period.empty:
        # Apply the same filter logic
        if exclude_cc_payments:
            user_filtered = expenses_period[
                (expenses_period["Payment Method"] != "PayLater") &
                (~expenses_period["Category"].isin(["Credit Card Payment", "PayLater Payment"]))
            ]
        else:
            user_filtered = expenses_period[expenses_period["Payment Method"] != "PayLater"]
        
        if not user_filtered.empty:
            user_spending = user_filtered.groupby("User")["Amount"].sum().reset_index()
            user_order = user_spending.sort_values("Amount", ascending=False)["User"].tolist()
            user_spending["User"] = pd.Categorical(user_spending["User"], categories=user_order, ordered=True)

            bar_user = alt.Chart(user_spending).mark_bar().encode(
                x=alt.X("User", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Amount", sort=user_order, title="Total Spending (IDR)"),
                color=alt.Color("User", legend=None),
                tooltip=["User", alt.Tooltip("Amount", format=",.2f")]
            )

            text_user = alt.Chart(user_spending).mark_text(
                align='center',
                baseline='bottom',
                color='white',
                dy=-10
            ).encode(
                x="User",
                y="Amount",
                text=alt.Text("Amount:Q", format=",.0f")
            )

            st.altair_chart(bar_user + text_user, use_container_width=True)

            # Sort user_spending by Amount descending
            user_spending_sorted = user_spending.sort_values("Amount", ascending=False).reset_index(drop=True)
            st.dataframe(user_spending_sorted, column_config={
                "Amount": st.column_config.NumberColumn("Amount", format='accounting')
            }, use_container_width=True)
        else:
            st.info("No spending data for users this period.")

    # Show CC/PayLater summary if payments exist
    if not expenses_period.empty:
        cc_payments = expenses_period[
            expenses_period["Category"].isin(["Credit Card Payment", "PayLater Payment"])
        ]
        if not cc_payments.empty:
            st.subheader("💳 Credit Card & PayLater Payments This Period")
            cc_summary = cc_payments.groupby("Category")["Amount"].sum().reset_index()
            st.dataframe(cc_summary, column_config={
                "Amount": st.column_config.NumberColumn("Amount", format='accounting')
            }, use_container_width=True)

    # Recent Transactions
    st.subheader("📝 Recent Transactions")
    if not expenses_df.empty:
        df_show = expenses_df.copy()
        df_show["Purchase Date"] = df_show["Purchase Date"].dt.date
        st.dataframe(df_show.tail(25).drop(columns=["Timestamp"]), use_container_width=True)

# --- Income Tab ---
elif menu == "Income":
    st.header("💰 Income Recorder")
    st.subheader("Record a New Income")

    with st.form("income_form", clear_on_submit=True):
        income_user = st.radio("Who earned it?", ["Mikael", "Josephine"], key="income_user")
        income_date = st.date_input("Income Date", value=datetime.today().date())
        income_source = st.selectbox("Source", ["Salary", "Freelance", "Other"])
        income_desc = st.text_input("Income Description")
        income_amt = st.number_input("Income Amount", min_value=1000.00, step=1000.00, format="%.2f")
        income_submit = st.form_submit_button("➕ Add Income")
        
        if income_submit and income_amt > 0:
            timestamp = datetime.now(pytz.timezone("Asia/Jakarta")).strftime("%m/%d/%Y %H:%M:%S")
            row = [timestamp, income_user, income_date.strftime("%m/%d/%Y"), income_source, income_desc, income_amt]
            ws_income.append_row(row)
            
            # Clear cache to reload data
            st.cache_data.clear()
            
            st.success("Income recorded!")
            st.rerun()

    # Income vs Expense Chart
    st.subheader("📊 Income vs. Expenses")
    
    # Add option to exclude CC payments from expense total
    exclude_from_comparison = st.checkbox(
        "Exclude CC/PayLater bill payments from expense total", 
        value=True,
        help="Removes credit card and PayLater bill payments from the comparison"
    )
    
    if exclude_from_comparison:
        expense_sum = expenses_period[
            ~expenses_period["Category"].isin(["Credit Card Payment", "PayLater Payment"])
        ]["Amount"].sum()
    else:
        expense_sum = expenses_period["Amount"].sum()
    
    income_sum = income_period["Income Amount"].sum()
    
    inc_exp_df = pd.DataFrame({"Type": ["Income", "Expenses"], "Amount": [income_sum, expense_sum]})
    inc_exp_df["Type"] = pd.Categorical(inc_exp_df["Type"], categories=["Income", "Expenses"], ordered=True)

    color_scale = alt.Scale(domain=["Income", "Expenses"], range=["#0a54a3", "#88bdee"])

    bar_income = alt.Chart(inc_exp_df).mark_bar().encode(
        x=alt.X("Type", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Amount", title="Amount (IDR)"),
        color=alt.Color("Type", scale=color_scale, legend=None),
        tooltip=["Type", alt.Tooltip("Amount", format=",.0f")]
    )

    text_income = alt.Chart(inc_exp_df).mark_text(
        align='center',
        baseline='bottom',
        dy=-5,
        color='white'
    ).encode(
        x="Type",
        y="Amount",
        text=alt.Text("Amount:Q", format=",.0f")
    )

    st.altair_chart(bar_income + text_income, use_container_width=True)
    
    # Show detailed breakdown
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Income", f"{income_sum:,.0f} IDR")
    with col2:
        st.metric("Total Expenses", f"{expense_sum:,.0f} IDR", 
                 delta=f"{income_sum - expense_sum:,.0f} IDR" if income_sum > expense_sum else None)

# --- Budget Tab ---
# elif menu == "Budget":
#     st.header("📈 Budget Overview")
#     st.markdown(f"Budget period: **{period_start}** to **{period_end - timedelta(days=1)}**")

#     if not budget_df.empty and not expenses_period.empty:
#         df_sum = expenses_period.groupby("Category")["Amount"].sum().reset_index()
#         df_merged = pd.merge(budget_df, df_sum, on="Category", how="left").fillna(0)
#         df_merged["Total Budget"] = pd.to_numeric(df_merged["Total Budget"], errors="coerce")
#         df_merged["Remaining"] = df_merged["Total Budget"] - df_merged["Amount"]

#         # Format for display (accounting style with commas, parentheses for negatives)
#         display_df = df_merged[["Category", "Mikael", "Josephine", "Total Budget", "Amount", "Remaining"]].copy()
#         for col in ["Mikael", "Josephine", "Total Budget", "Amount", "Remaining"]:
#             display_df[col] = display_df[col].apply(lambda x: f"{x:,.0f}" if x >= 0 else "0")

#         # Show in Streamlit
#         st.dataframe(display_df)

#         bar = alt.Chart(df_merged).mark_bar().encode(
#             x=alt.X("Category", axis=alt.Axis(labelAngle=-30)),
#             y=alt.Y("Total Budget", title="IDR"),
#             y2="Amount",
#             color=alt.condition(
#                 alt.datum["Amount"] > alt.datum["Total Budget"],
#                 alt.value("red"),
#                 alt.value("green")
#             ),
#             tooltip=["Category", "Total Budget", "Amount", "Remaining"]
#         )
#         st.altair_chart(bar, use_container_width=True)
#     else:
#         st.info("No budget or expense data found.")
