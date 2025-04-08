import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import sqlite3
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import time

# Initialize database with retry mechanism
def init_db():
    retries = 5
    for attempt in range(retries):
        try:
            conn = sqlite3.connect('finance.db', check_same_thread=False, timeout=10)
            c = conn.cursor()
            
            # Drop and recreate tables
            c.execute('''DROP TABLE IF EXISTS expenses''')
            c.execute('''DROP TABLE IF EXISTS budgets''')
            c.execute('''DROP TABLE IF EXISTS savings_goals''')
            c.execute('''DROP TABLE IF EXISTS income''')
            c.execute('''DROP TABLE IF EXISTS users''')
            
            # Create tables
            c.execute('''CREATE TABLE IF NOT EXISTS users
                        (user_id INTEGER PRIMARY KEY, username TEXT, password TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS expenses
                        (expense_id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, 
                        category TEXT, subcategory TEXT, date DATE, description TEXT, 
                        payment_method TEXT, FOREIGN KEY(user_id) REFERENCES users(user_id))''')
            c.execute('''CREATE TABLE IF NOT EXISTS budgets
                        (budget_id INTEGER PRIMARY KEY, user_id INTEGER, category TEXT, 
                        subcategory TEXT, limit_amount REAL, period TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(user_id))''')
            c.execute('''CREATE TABLE IF NOT EXISTS savings_goals
                        (goal_id INTEGER PRIMARY KEY, user_id INTEGER, goal_name TEXT, 
                        target_amount REAL, current_amount REAL, target_date DATE, 
                        priority INTEGER, description TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(user_id))''')
            c.execute('''CREATE TABLE IF NOT EXISTS income
                        (income_id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL, 
                        source TEXT, date DATE, description TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(user_id))''')
            
            # Insert sample data
            c.execute("INSERT OR IGNORE INTO users (user_id, username, password) VALUES (1, 'user1', 'pass1')")
            c.execute("INSERT INTO expenses (user_id, amount, category, date, description, payment_method) VALUES (1, 500, 'Housing', '2025-04-01', 'Rent', 'Bank Transfer')")
            c.execute("INSERT INTO expenses (user_id, amount, category, date, description, payment_method) VALUES (1, 100, 'Food', '2025-04-02', 'Groceries', 'Credit Card')")
            c.execute("INSERT INTO income (user_id, amount, source, date, description) VALUES (1, 3000, 'Salary', '2025-04-01', 'Monthly salary')")
            c.execute("INSERT INTO savings_goals (user_id, goal_name, target_amount, current_amount, target_date, priority) VALUES (1, 'Vacation', 2000, 500, '2025-12-31', 1)")
            c.execute("INSERT INTO budgets (user_id, category, limit_amount, period) VALUES (1, 'Food', 300, 'Monthly')")
            
            conn.commit()
            return conn
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < retries - 1:
                time.sleep(1)  # Wait before retrying
                continue
            else:
                st.error(f"Database error: {e}")
                raise
    st.error("Failed to initialize database after multiple attempts.")
    return None

conn = init_db()
if conn is None:
    st.stop()

# Page config and constants
st.set_page_config(page_title="Personal Finance Manager", layout="wide")
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "Expense Tracking", "Income Tracking", 
                                 "Budget Management", "Savings Goals", "Analytics", "Reports"])
current_user_id = 1

EXPENSE_CATEGORIES = ["Housing", "Food", "Transportation", "Utilities", "Healthcare", 
                     "Entertainment", "Education", "Personal", "Debt Payments", "Savings", 
                     "Investments", "Gifts", "Other"]
PAYMENT_METHODS = ["Cash", "Credit Card", "Debit Card", "Bank Transfer", "Digital Wallet", "Check"]
INCOME_SOURCES = ["Salary", "Freelance", "Investments", "Rental", "Business", "Gifts", "Other"]

def get_last_month():
    today = datetime.now()
    first_day = today.replace(day=1)
    last_month = first_day - timedelta(days=1)
    return last_month.strftime("%Y-%m")

# Function to generate PDF report
def generate_pdf_report():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("Personal Finance Report", styles['Title']))
    
    current_month = datetime.now().strftime("%Y-%m")
    monthly_spending = pd.read_sql(f"SELECT SUM(amount) as total FROM expenses WHERE user_id = {current_user_id} AND strftime('%Y-%m', date) = '{current_month}'", conn).iloc[0,0] or 0
    monthly_income = pd.read_sql(f"SELECT SUM(amount) as total FROM income WHERE user_id = {current_user_id} AND strftime('%Y-%m', date) = '{current_month}'", conn).iloc[0,0] or 0
    savings = pd.read_sql(f"SELECT SUM(current_amount) as saved FROM savings_goals WHERE user_id = {current_user_id}", conn).iloc[0,0] or 0
    
    summary_data = [
        ["Metric", "Value"],
        ["Monthly Spending", f"${monthly_spending:,.2f}"],
        ["Monthly Income", f"${monthly_income:,.2f}"],
        ["Savings", f"${savings:,.2f}"]
    ]
    table = Table(summary_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Dashboard Page with Upload and Edit
if page == "Dashboard":
    st.title("💰 Personal Finance Dashboard")
    
    # CSV Upload
    st.subheader("📤 Upload Your Financial Data")
    uploaded_file = st.file_uploader("Upload a CSV file with financial data (optional)", type=["csv"])
    if uploaded_file:
        uploaded_df = pd.read_csv(uploaded_file)
        st.write("Uploaded Data Preview:")
        st.dataframe(uploaded_df.head())
        
        # Check for required 'type' column
        if 'type' not in uploaded_df.columns:
            st.error("CSV must contain a 'type' column (values: expense, income, savings, budget). Using default data instead.")
        else:
            # Clear existing data to use only uploaded data
            c = conn.cursor()
            c.execute("DELETE FROM expenses WHERE user_id = ?", (current_user_id,))
            c.execute("DELETE FROM income WHERE user_id = ?", (current_user_id,))
            c.execute("DELETE FROM savings_goals WHERE user_id = ?", (current_user_id,))
            c.execute("DELETE FROM budgets WHERE user_id = ?", (current_user_id,))
            
            # Process CSV data
            for index, row in uploaded_df.iterrows():
                try:
                    if row['type'].lower() == 'expense':
                        c.execute("INSERT INTO expenses (user_id, amount, category, date, description, payment_method) VALUES (?, ?, ?, ?, ?, ?)",
                                  (current_user_id, row.get('amount', 0), row.get('category', 'Other'), row.get('date', datetime.now().strftime('%Y-%m-%d')), 
                                   row.get('description', ''), row.get('payment_method', 'Unknown')))
                    elif row['type'].lower() == 'income':
                        c.execute("INSERT INTO income (user_id, amount, source, date, description) VALUES (?, ?, ?, ?, ?)",
                                  (current_user_id, row.get('amount', 0), row.get('source', 'Other'), row.get('date', datetime.now().strftime('%Y-%m-%d')), 
                                   row.get('description', '')))
                    elif row['type'].lower() == 'savings':
                        c.execute("INSERT INTO savings_goals (user_id, goal_name, target_amount, current_amount, target_date, priority) VALUES (?, ?, ?, ?, ?, ?)",
                                  (current_user_id, row.get('goal_name', 'Unnamed Goal'), row.get('target_amount', 0), row.get('current_amount', 0), 
                                   row.get('target_date', '2025-12-31'), 1))
                    elif row['type'].lower() == 'budget':
                        c.execute("INSERT INTO budgets (user_id, category, limit_amount, period) VALUES (?, ?, ?, ?)",
                                  (current_user_id, row.get('category', 'Other'), row.get('limit_amount', 0), 'Monthly'))
                except KeyError as e:
                    st.warning(f"Skipping row {index}: Missing column {e}")
            conn.commit()
            st.success("Data uploaded and integrated successfully!")

    # Editing Existing Data
    st.subheader("✏️ Edit Existing Data")
    edit_option = st.selectbox("Select data to edit", ["Expenses", "Income", "Budgets", "Savings Goals"])
    c = conn.cursor()
    if edit_option == "Expenses":
        expenses_df = pd.read_sql(f"SELECT * FROM expenses WHERE user_id = {current_user_id}", conn)
        st.dataframe(expenses_df)
        expense_id = st.number_input("Enter Expense ID to edit", min_value=1, step=1)
        if st.button("Load Expense"):
            expense = pd.read_sql(f"SELECT * FROM expenses WHERE expense_id = {expense_id}", conn)
            if not expense.empty:
                with st.form("edit_expense"):
                    amount = st.number_input("Amount", value=float(expense['amount'].iloc[0]))
                    category = st.selectbox("Category", EXPENSE_CATEGORIES, index=EXPENSE_CATEGORIES.index(expense['category'].iloc[0]))
                    date = st.date_input("Date", value=datetime.strptime(expense['date'].iloc[0], '%Y-%m-%d'))
                    description = st.text_input("Description", value=expense['description'].iloc[0])
                    payment_method = st.selectbox("Payment Method", PAYMENT_METHODS, index=PAYMENT_METHODS.index(expense['payment_method'].iloc[0]))
                    if st.form_submit_button("Update"):
                        c.execute("UPDATE expenses SET amount=?, category=?, date=?, description=?, payment_method=? WHERE expense_id=?",
                                  (amount, category, date, description, payment_method, expense_id))
                        conn.commit()
                        st.success("Expense updated!")
    elif edit_option == "Income":
        income_df = pd.read_sql(f"SELECT * FROM income WHERE user_id = {current_user_id}", conn)
        st.dataframe(income_df)
        income_id = st.number_input("Enter Income ID to edit", min_value=1, step=1)
        if st.button("Load Income"):
            income = pd.read_sql(f"SELECT * FROM income WHERE income_id = {income_id}", conn)
            if not income.empty:
                with st.form("edit_income"):
                    amount = st.number_input("Amount", value=float(income['amount'].iloc[0]))
                    source = st.selectbox("Source", INCOME_SOURCES, index=INCOME_SOURCES.index(income['source'].iloc[0]))
                    date = st.date_input("Date", value=datetime.strptime(income['date'].iloc[0], '%Y-%m-%d'))
                    description = st.text_input("Description", value=income['description'].iloc[0])
                    if st.form_submit_button("Update"):
                        c.execute("UPDATE income SET amount=?, source=?, date=?, description=? WHERE income_id=?",
                                  (amount, source, date, description, income_id))
                        conn.commit()
                        st.success("Income updated!")

    today = datetime.now()
    current_month = today.strftime("%Y-%m")
    last_month = get_last_month()
    
    cols = st.columns(4)
    with cols[0]:
        monthly_spending = pd.read_sql(f"SELECT SUM(amount) as total FROM expenses WHERE user_id = {current_user_id} AND strftime('%Y-%m', date) = '{current_month}'", conn).iloc[0,0] or 0
        last_month_spending = pd.read_sql(f"SELECT SUM(amount) as total FROM expenses WHERE user_id = {current_user_id} AND strftime('%Y-%m', date) = '{last_month}'", conn).iloc[0,0] or 0
        change = ((monthly_spending - last_month_spending) / last_month_spending * 100) if last_month_spending else 0
        st.metric("Monthly Spending", f"${monthly_spending:,.2f}", f"{change:.1f}%")

    with cols[1]:
        monthly_income = pd.read_sql(f"SELECT SUM(amount) as total FROM income WHERE user_id = {current_user_id} AND strftime('%Y-%m', date) = '{current_month}'", conn).iloc[0,0] or 0
        last_month_income = pd.read_sql(f"SELECT SUM(amount) as total FROM income WHERE user_id = {current_user_id} AND strftime('%Y-%m', date) = '{last_month}'", conn).iloc[0,0] or 0
        income_change = ((monthly_income - last_month_income) / last_month_income * 100) if last_month_income else 0
        st.metric("Monthly Income", f"${monthly_income:,.2f}", f"{income_change:.1f}%")

    with cols[2]:
        savings = pd.read_sql(f"SELECT SUM(current_amount) as saved FROM savings_goals WHERE user_id = {current_user_id}", conn).iloc[0,0] or 0
        target = pd.read_sql(f"SELECT SUM(target_amount) as target FROM savings_goals WHERE user_id = {current_user_id}", conn).iloc[0,0] or 0
        progress = (savings/target*100) if target else 0
        st.metric("Savings Progress", f"${savings:,.2f}", f"{progress:.1f}% of ${target:,.2f}")

    with cols[3]:
        net_worth = monthly_income - monthly_spending + savings
        st.metric("Net Cash Flow", f"${net_worth:,.2f}")

    st.subheader("Financial Overview")
    time_period = st.selectbox("Time Period", ["Last 3 Months", "Last 6 Months", "Last 12 Months", "Current Year"])
    
    date_filter = {
        "Last 3 Months": "date >= date('now', '-3 months')",
        "Last 6 Months": "date >= date('now', '-6 months')",
        "Last 12 Months": "date >= date('now', '-12 months')",
        "Current Year": "strftime('%Y', date) = strftime('%Y', 'now')"
    }[time_period]
    
    spending_data = pd.read_sql(f"SELECT strftime('%Y-%m', date) as month, SUM(amount) as spending FROM expenses WHERE user_id = {current_user_id} AND {date_filter} GROUP BY month ORDER BY month", conn)
    income_data = pd.read_sql(f"SELECT strftime('%Y-%m', date) as month, SUM(amount) as income FROM income WHERE user_id = {current_user_id} AND {date_filter} GROUP BY month ORDER BY month", conn)
    
    comparison_data = pd.merge(spending_data, income_data, on='month', how='outer').fillna(0)
    comparison_data['savings'] = comparison_data['income'] - comparison_data['spending']
    
    fig = px.bar(comparison_data, x='month', y=['income', 'spending', 'savings'],
                 barmode='group', title=f"Financial Flow ({time_period})",
                 labels={'value': 'Amount ($)', 'month': 'Month'},
                 color_discrete_map={'income': '#00CC96', 'spending': '#EF553B', 'savings': '#636EFA'})
    st.plotly_chart(fig)

# Expense Tracking
elif page == "Expense Tracking":
    st.title("💸 Expense Tracking")
    with st.expander("➕ Add New Expense", expanded=True):
        with st.form("expense_form"):
            amount = st.number_input("Amount ($)", min_value=0.01, step=0.01)
            col1, col2 = st.columns(2)
            category = col1.selectbox("Category", EXPENSE_CATEGORIES)
            subcategory = col2.text_input("Subcategory (Optional)")
            col1, col2 = st.columns(2)
            date = col1.date_input("Date", datetime.now())
            payment_method = col2.selectbox("Payment Method", PAYMENT_METHODS)
            description = st.text_input("Description (Optional)")
            submitted = st.form_submit_button("Add Expense")
            if submitted:
                c = conn.cursor()
                c.execute("INSERT INTO expenses (user_id, amount, category, subcategory, date, description, payment_method) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (current_user_id, amount, category, subcategory, date, description, payment_method))
                conn.commit()
                st.success("Expense added!")

    st.subheader("Expense Analysis")
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start Date", datetime.now() - timedelta(days=30))
    end_date = col2.date_input("End Date", datetime.now())
    
    expenses_df = pd.read_sql(f"SELECT date, category, amount, payment_method, description FROM expenses WHERE user_id = {current_user_id} AND date BETWEEN '{start_date}' AND '{end_date}' ORDER BY date DESC", conn)
    total_spent = expenses_df['amount'].sum()
    avg_daily = total_spent / ((end_date - start_date).days + 1) if (end_date - start_date).days > 0 else total_spent
    
    st.write(f"**Total Spent:** ${total_spent:,.2f} | **Avg Daily:** ${avg_daily:,.2f}")
    st.dataframe(expenses_df)
    
    cat_data = expenses_df.groupby('category')['amount'].sum().reset_index()
    fig = px.pie(cat_data, values='amount', names='category', title="Expense Distribution")
    st.plotly_chart(fig)

# Income Tracking
elif page == "Income Tracking":
    st.title("💵 Income Tracking")
    
    with st.expander("➕ Add New Income", expanded=True):
        with st.form("income_form"):
            amount = st.number_input("Amount ($)", min_value=0.01, step=0.01)
            col1, col2 = st.columns(2)
            source = col1.selectbox("Source", INCOME_SOURCES)
            date = col2.date_input("Date", datetime.now())
            description = st.text_input("Description (Optional)")
            submitted = st.form_submit_button("Add Income")
            if submitted:
                c = conn.cursor()
                c.execute("INSERT INTO income (user_id, amount, source, date, description) VALUES (?, ?, ?, ?, ?)",
                         (current_user_id, amount, source, date, description))
                conn.commit()
                st.success("Income added!")
    
    st.subheader("Income Analysis")
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start Date", datetime.now() - timedelta(days=30))
    end_date = col2.date_input("End Date", datetime.now())
    
    income_df = pd.read_sql(f"SELECT date, source, amount, description FROM income WHERE user_id = {current_user_id} AND date BETWEEN '{start_date}' AND '{end_date}' ORDER BY date DESC", conn)
    total_income = income_df['amount'].sum()
    avg_daily = total_income / ((end_date - start_date).days + 1) if (end_date - start_date).days > 0 else total_income
    
    st.write(f"**Total Income:** ${total_income:,.2f} | **Avg Daily:** ${avg_daily:,.2f}")
    st.dataframe(income_df)
    
    source_data = income_df.groupby('source')['amount'].sum().reset_index()
    fig = px.bar(source_data, x='source', y='amount', title="Income by Source",
                 labels={'source': 'Income Source', 'amount': 'Amount ($)'})
    st.plotly_chart(fig)

# Budget Management
elif page == "Budget Management":
    st.title("📊 Budget Management")
    tab1, tab2 = st.tabs(["Set Budgets", "Budget Analysis"])
    
    with tab1:
        with st.form("budget_form"):
            category = st.selectbox("Category", EXPENSE_CATEGORIES)
            limit_amount = st.number_input("Monthly Limit ($)", min_value=0.01, step=0.01)
            submitted = st.form_submit_button("Save Budget")
            if submitted:
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO budgets (user_id, category, limit_amount, period) VALUES (?, ?, ?, ?)",
                         (current_user_id, category, limit_amount, "Monthly"))
                conn.commit()
                st.success("Budget saved!")
    
    with tab2:
        current_month = datetime.now().strftime("%Y-%m")
        budget_status = pd.read_sql(f"""
            SELECT b.category, b.limit_amount, COALESCE(SUM(e.amount), 0) as spent
            FROM budgets b
            LEFT JOIN expenses e ON b.category = e.category AND strftime('%Y-%m', e.date) = '{current_month}'
            WHERE b.user_id = {current_user_id}
            GROUP BY b.category, b.limit_amount
        """, conn)
        
        budget_status['remaining'] = budget_status['limit_amount'] - budget_status['spent']
        budget_status['progress'] = (budget_status['spent'] / budget_status['limit_amount'] * 100).clip(0, 100)
        
        st.dataframe(budget_status)
        fig = px.bar(budget_status, x='category', y=['spent', 'limit_amount'],
                     barmode='group', title="Budget vs Actual Spending")
        st.plotly_chart(fig)

# Savings Goals
elif page == "Savings Goals":
    st.title("🎯 Savings Goals")
    
    with st.expander("➕ Add New Goal", expanded=True):
        with st.form("goal_form"):
            goal_name = st.text_input("Goal Name")
            target_amount = st.number_input("Target Amount ($)", min_value=0.01)
            current_amount = st.number_input("Current Amount ($)", min_value=0.0)
            target_date = st.date_input("Target Date")
            priority = st.slider("Priority", 1, 5, 3)
            description = st.text_area("Description (Optional)")
            submitted = st.form_submit_button("Add Goal")
            if submitted:
                c = conn.cursor()
                c.execute("INSERT INTO savings_goals (user_id, goal_name, target_amount, current_amount, target_date, priority, description) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (current_user_id, goal_name, target_amount, current_amount, target_date, priority, description))
                conn.commit()
                st.success("Goal added!")
    
    st.subheader("Goal Progress")
    goals = pd.read_sql(f"SELECT goal_name, target_amount, current_amount, target_date FROM savings_goals WHERE user_id = {current_user_id}", conn)
    goals['progress'] = (goals['current_amount'] / goals['target_amount'] * 100).clip(0, 100)
    
    for _, row in goals.iterrows():
        st.write(f"**{row['goal_name']}** - Target: ${row['target_amount']:,.2f} by {row['target_date']}")
        st.progress(row['progress']/100, f"Progress: ${row['current_amount']:,.2f} ({row['progress']:.1f}%)")
    
    fig = px.bar(goals, x='goal_name', y=['current_amount', 'target_amount'],
                 barmode='group', title="Savings Goals Progress")
    st.plotly_chart(fig)

# Analytics
elif page == "Analytics":
    st.title("📈 Financial Analytics")
    
    st.subheader("Income vs Expenses Trend")
    time_period = st.selectbox("Time Period", ["Last 3 Months", "Last 6 Months", "Last 12 Months"])
    date_filter = {
        "Last 3 Months": '-3 months',
        "Last 6 Months": '-6 months',
        "Last 12 Months": '-12 months'
    }[time_period]
    
    monthly_data = pd.read_sql(f"""
        SELECT strftime('%Y-%m', date) as month,
               SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) as expenses,
               SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as income
        FROM (SELECT date, -amount as amount FROM expenses WHERE user_id = {current_user_id}
              UNION ALL
              SELECT date, amount FROM income WHERE user_id = {current_user_id})
        WHERE date >= date('now', '{date_filter}')
        GROUP BY month
        ORDER BY month
    """, conn)
    
    monthly_data['net'] = monthly_data['income'] + monthly_data['expenses']
    fig = px.line(monthly_data, x='month', y=['income', 'expenses', 'net'],
                  title=f"Financial Trends ({time_period})",
                  labels={'value': 'Amount ($)', 'month': 'Month'})
    st.plotly_chart(fig)
    
    st.subheader("Financial Health Indicators")
    savings_rate = (monthly_data['net'].mean() / monthly_data['income'].mean() * 100) if monthly_data['income'].mean() else 0
    st.metric("Average Savings Rate", f"{savings_rate:.1f}%")
    
    expense_ratio = (-monthly_data['expenses'].mean() / monthly_data['income'].mean() * 100) if monthly_data['income'].mean() else 0
    st.metric("Expense-to-Income Ratio", f"{expense_ratio:.1f}%")

# Reports Page with Conclusion
elif page == "Reports":
    st.title("📊 Financial Reports")
    
    st.subheader("Generate Financial Report")
    with st.form("report_form"):
        report_period = st.selectbox("Report Period", ["Current Month", "Last 3 Months", "Last 6 Months"])
        include_charts = st.checkbox("Include Charts in Report")
        submitted = st.form_submit_button("Generate PDF Report")
        
        if submitted:
            pdf_buffer = generate_pdf_report()
            st.download_button(
                label="Download PDF Report",
                data=pdf_buffer,
                file_name="financial_report.pdf",
                mime="application/pdf"
            )
            st.success("Report generated successfully!")

    st.subheader("Financial Conclusion and Recommendations")
    current_month = datetime.now().strftime("%Y-%m")
    monthly_spending = pd.read_sql(f"SELECT SUM(amount) as total FROM expenses WHERE user_id = {current_user_id} AND strftime('%Y-%m', date) = '{current_month}'", conn).iloc[0,0] or 0
    monthly_income = pd.read_sql(f"SELECT SUM(amount) as total FROM income WHERE user_id = {current_user_id} AND strftime('%Y-%m', date) = '{current_month}'", conn).iloc[0,0] or 0
    savings = pd.read_sql(f"SELECT SUM(current_amount) as saved FROM savings_goals WHERE user_id = {current_user_id}", conn).iloc[0,0] or 0
    target_savings = pd.read_sql(f"SELECT SUM(target_amount) as target FROM savings_goals WHERE user_id = {current_user_id}", conn).iloc[0,0] or 0
    
    last_month_spending = pd.read_sql(f"SELECT SUM(amount) as total FROM expenses WHERE user_id = {current_user_id} AND strftime('%Y-%m', date) = '{get_last_month()}'", conn).iloc[0,0] or 0
    spending_reduction = last_month_spending - monthly_spending if last_month_spending > monthly_spending else 0
    
    st.write(f"**Total Income This Month:** ${monthly_income:,.2f}")
    st.write(f"**Total Spending This Month:** ${monthly_spending:,.2f}")
    st.write(f"**Net Savings This Month:** ${monthly_income - monthly_spending:,.2f}")
    st.write(f"**Total Savings Accumulated:** ${savings:,.2f} (of ${target_savings:,.2f} goal)")
    st.write(f"**Spending Reduction from Last Month:** ${spending_reduction:,.2f}")
    
    if monthly_income > monthly_spending:
        st.success(f"Great job! You're saving ${monthly_income - monthly_spending:,.2f} this month.")
    else:
        st.warning(f"Caution: Your spending exceeds your income by ${monthly_spending - monthly_income:,.2f} this month.")
    
    if savings >= target_savings * 0.75:
        st.success("Excellent progress! You're 75%+ towards your savings goals.")
    elif savings >= target_savings * 0.5:
        st.info("Good progress! You're halfway to your savings goals.")
    else:
        st.warning("Savings are below 50% of your goals. Consider increasing contributions.")

    st.subheader("Recommendations to Minimize Finances")
    if monthly_spending > monthly_income * 0.8:
        st.write("- **Reduce Discretionary Spending**: Your expenses are high relative to income. Cut back on non-essential categories like Entertainment or Personal.")
    if spending_reduction == 0 and last_month_spending > 0:
        st.write("- **Maintain Spending Discipline**: No reduction from last month. Review high-cost categories (e.g., Housing) for savings opportunities.")
    if savings < target_savings * 0.5:
        st.write(f"- **Boost Savings**: Allocate an additional ${(target_savings - savings) * 0.1:,.2f} monthly to reach your goals faster.")

conn.close()