import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import time

import google.generativeai as genai
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.platypus.flowables import Spacer
import calendar
from dateutil.relativedelta import relativedelta
import numpy as np

# --------------------------
# INITIALIZATION
# --------------------------

# Initialize Supabase client
@st.cache_resource
def init_supabase():
    SUPABASE_URL = st.secrets["https://hugjvlpvxqvnkuzfyacw.supabase.co"]
    SUPABASE_KEY = st.secrets["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1Z2p2bHB2eHF2bmt1emZ5YWN3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ0Nzg4NDIsImV4cCI6MjA2MDA1NDg0Mn0.BDe2Wrr74P-pkR0XF6Sfgheq6k4Z0LvidHV-7JiDC30"]
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Gemini AI
genai.configure(api_key=st.secrets["AIzaSyAtGPjtvE-kiDDNjrK75y5uKUz8SfEmQc"])

# Initialize clients
sb = init_supabase()
financial_model = genai.GenerativeModel('gemini-pro')

# --------------------------
# DATABASE FUNCTIONS
# --------------------------

def init_db():
    """Initialize database tables if they don't exist"""
    try:
        # Check if user exists
        user = sb.table("users").select("*").eq("user_id", 1).execute()
        if not user.data:
            sb.table("users").insert({
                "user_id": 1,
                "username": "user1",
                "password": "pass1",
                "currency": "USD",
                "financial_goals": []
            }).execute()
        return True
    except Exception as e:
        st.error(f"Database init error: {e}")
        return False

def get_user_settings(user_id):
    """Get user preferences and settings"""
    try:
        settings = sb.table("users").select("*").eq("user_id", user_id).execute()
        return settings.data[0] if settings.data else None
    except Exception as e:
        st.error(f"Error getting user settings: {e}")
        return None

def update_user_settings(user_id, updates):
    """Update user settings"""
    try:
        sb.table("users").update(updates).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating settings: {e}")
        return False

# --------------------------
# AI PROCESSING FUNCTIONS
# --------------------------

def analyze_spending_patterns(user_id):
    """Use AI to analyze spending patterns and provide insights"""
    try:
        expenses = sb.table("expenses").select("*").eq("user_id", user_id).execute()
        expenses_df = pd.DataFrame(expenses.data)
        
        if len(expenses_df) < 10:
            return "Not enough data for meaningful analysis"
        
        prompt = f"""
        Analyze these financial transactions and provide insights:
        {expenses_df.to_string()}
        
        Provide:
        1. Top spending categories
        2. Unusual spending patterns
        3. Potential savings opportunities
        4. Weekly/Monthly trends
        5. Personalized recommendations
        
        Format as markdown with bullet points.
        """
        
        response = financial_model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"AI analysis error: {e}")
        return "Analysis failed"

def process_financial_document(file_content, file_type):
    """Process uploaded financial documents with AI"""
    try:
        prompt = f"""
        Extract financial transactions from this {file_type} document.
        Return a JSON array with fields: date, description, amount, category.
        
        Document content:
        {str(file_content)[:10000]}... [truncated]
        """
        
        response = financial_model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Document processing error: {e}")
        return None

# --------------------------
# FINANCIAL OPERATIONS
# --------------------------

def add_transaction(user_id, trans_type, data):
    """Add a financial transaction (expense/income)"""
    try:
        data["user_id"] = user_id
        data["created_at"] = datetime.now().isoformat()
        
        if trans_type == "expense":
            sb.table("expenses").insert(data).execute()
        else:
            sb.table("income").insert(data).execute()
        
        # Update budget tracking
        if trans_type == "expense" and "category" in data:
            update_budget_usage(user_id, data["category"], data["amount"])
        
        return True
    except Exception as e:
        st.error(f"Error adding transaction: {e}")
        return False

def get_financial_summary(user_id, period="month"):
    """Get comprehensive financial summary"""
    try:
        end_date = datetime.now()
        
        if period == "week":
            start_date = end_date - timedelta(days=7)
        elif period == "month":
            start_date = end_date - timedelta(days=30)
        elif period == "year":
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)
        
        # Get expenses
        expenses = sb.table("expenses")\
                   .select("*")\
                   .eq("user_id", user_id)\
                   .gte("date", start_date.isoformat())\
                   .lte("date", end_date.isoformat())\
                   .execute()
        
        # Get income
        income = sb.table("income")\
                 .select("*")\
                 .eq("user_id", user_id)\
                 .gte("date", start_date.isoformat())\
                 .lte("date", end_date.isoformat())\
                 .execute()
        
        # Get budgets
        budgets = sb.table("budgets")\
                   .select("*")\
                   .eq("user_id", user_id)\
                   .execute()
        
        # Convert to DataFrames
        expenses_df = pd.DataFrame(expenses.data)
        income_df = pd.DataFrame(income.data)
        budgets_df = pd.DataFrame(budgets.data)
        
        # Calculate totals
        total_expenses = expenses_df['amount'].sum() if not expenses_df.empty else 0
        total_income = income_df['amount'].sum() if not income_df.empty else 0
        net_balance = total_income - total_expenses
        
        # Calculate budget usage
        budget_usage = {}
        if not budgets_df.empty and not expenses_df.empty:
            for _, budget in budgets_df.iterrows():
                category_expenses = expenses_df[expenses_df['category'] == budget['category']]['amount'].sum()
                budget_usage[budget['category']] = {
                    'limit': budget['limit_amount'],
                    'spent': category_expenses,
                    'remaining': budget['limit_amount'] - category_expenses,
                    'percentage': (category_expenses / budget['limit_amount']) * 100 if budget['limit_amount'] > 0 else 0
                }
        
        return {
            'total_income': total_income,
            'total_expenses': total_expenses,
            'net_balance': net_balance,
            'budget_usage': budget_usage,
            'expenses_by_category': expenses_df.groupby('category')['amount'].sum().to_dict(),
            'income_by_source': income_df.groupby('source')['amount'].sum().to_dict(),
            'start_date': start_date,
            'end_date': end_date
        }
    except Exception as e:
        st.error(f"Error getting financial summary: {e}")
        return None

# --------------------------
# REPORT GENERATION
# --------------------------

def generate_comprehensive_report(user_id):
    """Generate a detailed PDF financial report"""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        elements.append(Paragraph("Comprehensive Financial Report", styles['Title']))
        elements.append(Spacer(1, 12))
        
        # Date
        elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
        elements.append(Spacer(1, 24))
        
        # 1. Financial Summary
        summary = get_financial_summary(user_id, "month")
        elements.append(Paragraph("1. Financial Summary", styles['Heading2']))
        
        summary_data = [
            ["Metric", "Amount"],
            ["Total Income", f"${summary['total_income']:,.2f}"],
            ["Total Expenses", f"${summary['total_expenses']:,.2f}"],
            ["Net Balance", f"${summary['net_balance']:,.2f}"]
        ]
        
        summary_table = Table(summary_data)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2E86AB")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F5F5F5")),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 24))
        
        # 2. Budget Analysis
        elements.append(Paragraph("2. Budget Analysis", styles['Heading2']))
        
        if summary['budget_usage']:
            budget_data = [["Category", "Budget", "Spent", "Remaining", "Usage %"]]
            for category, data in summary['budget_usage'].items():
                budget_data.append([
                    category,
                    f"${data['limit']:,.2f}",
                    f"${data['spent']:,.2f}",
                    f"${data['remaining']:,.2f}",
                    f"{data['percentage']:.1f}%"
                ])
            
            budget_table = Table(budget_data)
            budget_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2E86AB")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F5F5F5")),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('TEXTCOLOR', (-1, 1), (-1, -1), 
                 colors.red if data['percentage'] > 90 else 
                 (colors.orange if data['percentage'] > 75 else colors.green))
            ]))
            elements.append(budget_table)
        else:
            elements.append(Paragraph("No budget data available", styles['Normal']))
        
        elements.append(Spacer(1, 24))
        
        # 3. AI-Powered Insights
        elements.append(Paragraph("3. AI-Powered Financial Insights", styles['Heading2']))
        insights = analyze_spending_patterns(user_id)
        elements.append(Paragraph(insights, styles['Normal']))
        
        # Build the PDF
        doc.build(elements)
        buffer.seek(0)
        return buffer
    except Exception as e:
        st.error(f"Error generating report: {e}")
        return None

# --------------------------
# STREAMLIT UI
# --------------------------

def main():
    # Initialize database
    if not init_db():
        st.error("Failed to initialize database")
        st.stop()
    
    current_user_id = 1
    user_settings = get_user_settings(current_user_id)
    
    # Page config
    st.set_page_config(
        page_title="ProFinance Manager", 
        layout="wide", 
        initial_sidebar_state="expanded",
        menu_items={
            'Get Help': 'https://github.com/your-repo',
            'Report a bug': "https://github.com/your-repo/issues",
            'About': "# Advanced Financial Tracker"
        }
    )
    
    # Custom CSS
    st.markdown("""
    <style>
        .main {
            padding: 2rem;
        }
        .sidebar .sidebar-content {
            background-color: #f8f9fa;
        }
        .stButton>button {
            background-color: #2E86AB;
            color: white;
            border-radius: 8px;
            padding: 0.5rem 1rem;
        }
        .stTextInput>div>div>input, .stNumberInput>div>div>input, .stDateInput>div>div>input {
            border-radius: 8px;
        }
        .metric-box {
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("<h1 style='text-align: center; color: #2E86AB;'>💼 ProFinance</h1>", unsafe_allow_html=True)
        st.markdown("---")
        
        # Navigation
        menu = st.expander("📋 Navigation", expanded=True)
        with menu:
            page = st.radio(
                "Go to",
                ["🏠 Dashboard", "💸 Expenses", "💵 Income", "📊 Budgets", 
                 "🎯 Goals", "📈 Analytics", "📑 Reports", "⚙️ Settings"],
                label_visibility="collapsed"
            )
        
        st.markdown("---")
        
        # Quick Add
        with st.expander("⚡ Quick Add", expanded=True):
            with st.form("quick_add_form"):
                trans_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
                amount = st.number_input("Amount", min_value=0.01, step=0.01)
                category = st.text_input("Category" if trans_type == "Expense" else "Source")
                submitted = st.form_submit_button("Add")
                
                if submitted:
                    if add_transaction(current_user_id, trans_type.lower(), {
                        "amount": amount,
                        "category": category,
                        "date": datetime.now().isoformat(),
                        "description": "Quick add"
                    }):
                        st.success("Added successfully!")
                    else:
                        st.error("Failed to add transaction")
        
        st.markdown("---")
        st.markdown("<p style='text-align: center; color: grey;'>v2.0 • Made with ❤️</p>", unsafe_allow_html=True)
    
    # Dashboard Page
    if page == "🏠 Dashboard":
        st.title("Financial Dashboard")
        
        # Financial Summary Cards
        st.subheader("Overview")
        summary = get_financial_summary(current_user_id, "month")
        
        if summary:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div class='metric-box'>
                    <h3>Total Income</h3>
                    <h2>${summary['total_income']:,.2f}</h2>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class='metric-box'>
                    <h3>Total Expenses</h3>
                    <h2>${summary['total_expenses']:,.2f}</h2>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                balance_color = "#4CAF50" if summary['net_balance'] >= 0 else "#F44336"
                st.markdown(f"""
                <div class='metric-box'>
                    <h3>Net Balance</h3>
                    <h2 style='color: {balance_color}'>${summary['net_balance']:,.2f}</h2>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                savings = sb.table("savings_goals").select("current_amount").eq("user_id", current_user_id).execute()
                total_savings = sum([s['current_amount'] for s in savings.data]) if savings.data else 0
                st.markdown(f"""
                <div class='metric-box'>
                    <h3>Total Savings</h3>
                    <h2>${total_savings:,.2f}</h2>
                </div>
                """, unsafe_allow_html=True)
        
        # File Upload and AI Processing
        st.subheader("Document Processing")
        with st.expander("📤 Upload Financial Documents", expanded=True):
            uploaded_file = st.file_uploader(
                "Upload financial documents (CSV, PDF, receipts, statements)",
                type=["csv", "pdf", "png", "jpg", "jpeg"],
                accept_multiple_files=False,
                key="doc_uploader"
            )
            
            if uploaded_file:
                with st.spinner("Processing your document with AI..."):
                    file_content = uploaded_file.read()
                    processed_data = process_financial_document(file_content, uploaded_file.type)
                    
                    if processed_data:
                        st.success("Document processed successfully!")
                        st.json(processed_data)
                        
                        if st.button("Save Extracted Data"):
                            try:
                                # Parse and save the processed data
                                transactions = eval(processed_data)  # In production, use proper JSON parsing
                                for t in transactions:
                                    add_transaction(current_user_id, "expense", {
                                        "amount": t['amount'],
                                        "category": t['category'],
                                        "date": t['date'],
                                        "description": t['description'],
                                        "payment_method": "Extracted"
                                    })
                                st.success(f"Saved {len(transactions)} transactions!")
                            except Exception as e:
                                st.error(f"Error saving data: {e}")
        
        # Recent Transactions
        st.subheader("Recent Transactions")
        col1, col2 = st.columns([3, 1])
        
        with col1:
            transactions = sb.table("transactions")\
                          .select("*")\
                          .eq("user_id", current_user_id)\
                          .order("date", desc=True)\
                          .limit(10)\
                          .execute()
            
            if transactions.data:
                trans_df = pd.DataFrame(transactions.data)
                st.dataframe(
                    trans_df[['date', 'description', 'amount', 'category']]\
                        .rename(columns={
                            'date': 'Date',
                            'description': 'Description',
                            'amount': 'Amount',
                            'category': 'Category'
                        }),
                    use_container_width=True
                )
            else:
                st.info("No recent transactions found")
        
        with col2:
            st.markdown("### Quick Filters")
            view = st.radio(
                "View",
                ["All", "Expenses", "Income"],
                index=0
            )
            
            time_frame = st.selectbox(
                "Time Frame",
                ["Last 7 days", "Last 30 days", "Last 90 days", "This year"],
                index=1
            )
        
        # Financial Charts
        st.subheader("Financial Trends")
        tab1, tab2, tab3 = st.tabs(["Spending", "Income", "Cash Flow"])
        
        with tab1:
            # Spending trends chart
            expenses = sb.table("expenses")\
                      .select("date, amount, category")\
                      .eq("user_id", current_user_id)\
                      .order("date")\
                      .execute()
            
            if expenses.data:
                exp_df = pd.DataFrame(expenses.data)
                exp_df['date'] = pd.to_datetime(exp_df['date'])
                exp_df['month'] = exp_df['date'].dt.to_period('M')
                
                monthly_expenses = exp_df.groupby(['month', 'category'])['amount'].sum().unstack().fillna(0)
                
                fig = px.bar(
                    monthly_expenses,
                    title="Monthly Spending by Category",
                    labels={'value': 'Amount', 'month': 'Month'},
                    barmode='stack'
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No expense data available")
        
        with tab2:
            # Income trends chart
            income = sb.table("income")\
                    .select("date, amount, source")\
                    .eq("user_id", current_user_id)\
                    .order("date")\
                    .execute()
            
            if income.data:
                inc_df = pd.DataFrame(income.data)
                inc_df['date'] = pd.to_datetime(inc_df['date'])
                inc_df['month'] = inc_df['date'].dt.to_period('M')
                
                monthly_income = inc_df.groupby(['month', 'source'])['amount'].sum().unstack().fillna(0)
                
                fig = px.line(
                    monthly_income,
                    title="Monthly Income by Source",
                    labels={'value': 'Amount', 'month': 'Month'}
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No income data available")
        
        with tab3:
            # Cash flow chart
            if 'exp_df' in locals() and 'inc_df' in locals():
                cash_flow = pd.concat([
                    exp_df.assign(type='Expense', amount=-exp_df['amount']),
                    inc_df.assign(type='Income')
                ])
                
                cash_flow['cumulative'] = cash_flow.groupby('type')['amount'].cumsum()
                
                fig = px.line(
                    cash_flow,
                    x='date',
                    y='cumulative',
                    color='type',
                    title="Cumulative Cash Flow",
                    labels={'date': 'Date', 'cumulative': 'Amount'}
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Not enough data for cash flow analysis")
    
    # [Other pages would follow similar patterns...]
    
    # Settings Page
    elif page == "⚙️ Settings":
        st.title("Settings")
        
        with st.form("user_settings_form"):
            st.subheader("Personal Information")
            new_username = st.text_input("Username", value=user_settings.get('username', ''))
            new_currency = st.selectbox(
                "Default Currency",
                ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"],
                index=["USD", "EUR", "GBP", "JPY", "CAD", "AUD"].index(user_settings.get('currency', 'USD'))
            )
            
            st.subheader("Security")
            current_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            
            if st.form_submit_button("Save Settings"):
                updates = {
                    "username": new_username,
                    "currency": new_currency,
                    "updated_at": datetime.now().isoformat()
                }
                
                if new_password and new_password == confirm_password:
                    updates["password"] = new_password  # In production, hash this password
                
                if update_user_settings(current_user_id, updates):
                    st.success("Settings updated successfully!")
                else:
                    st.error("Failed to update settings")
        
        st.subheader("Data Management")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Export All Data"):
                # Export functionality would go here
                st.info("Export feature coming soon!")
        
        with col2:
            if st.button("Delete Account", type="secondary"):
                st.warning("This will permanently delete all your data!")
                if st.checkbox("I understand this cannot be undone"):
                    if st.button("Confirm Deletion", type="primary"):
                        st.error("Account deletion feature coming soon!")

if __name__ == "__main__":
    main()
