import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import time
import calendar
from dateutil.relativedelta import relativedelta
import numpy as np
import os
from supabase import create_client, Client
import google.generativeai as genai
import plotly.express as px
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

# --------------------------
# CONFIGURATION (using environment variables)
# --------------------------

# Initialize configuration from environment variables or Streamlit secrets
SUPABASE_URL = st.secrets.get("SUPABASE_URL", os.getenv("SUPABASE_URL"))
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", os.getenv("SUPABASE_KEY"))
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))

# Validate configuration
if not all([SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY]):
    st.error("Missing required configuration. Please check your environment variables or Streamlit secrets.")
    st.stop()

# --------------------------
# INITIALIZATION
# --------------------------

@st.cache_resource
def init_supabase():
    """Initialize and cache Supabase client"""
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Failed to initialize Supabase client: {e}")
        st.stop()

@st.cache_resource
def init_gemini():
    """Initialize and cache Gemini client"""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        return genai.GenerativeModel('gemini-pro')
    except Exception as e:
        st.error(f"Failed to initialize Gemini client: {e}")
        st.stop()

# Initialize clients
sb = init_supabase()
financial_model = init_gemini()

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
                "username": "default_user",
                "password": "default_password_should_be_changed",  # In production, hash this
                "currency": "USD",
                "financial_goals": []
            }).execute()
        return True
    except Exception as e:
        st.error(f"Database init error: {e}")
        return False

# [Rest of your database functions remain the same...]

# --------------------------
# STREAMLIT APP CONFIGURATION
# --------------------------

def configure_page():
    """Configure Streamlit page settings"""
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

# --------------------------
# MAIN APP
# --------------------------

def main():
    # Configure page first
    configure_page()
    
    # Initialize database
    if not init_db():
        st.error("Failed to initialize database")
        st.stop()
    
    current_user_id = 1  # In a real app, you'd get this from authentication
    user_settings = get_user_settings(current_user_id)
    
    # [Rest of your main application code remains the same...]

if __name__ == "__main__":
    main()
