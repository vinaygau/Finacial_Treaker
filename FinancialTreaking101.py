import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import time
import calendar
from dateutil.relativedelta import relativedelta
import numpy as np
import os
import google.generativeai as genai


# --------------------------
# CONFIGURATION (using environment variables)
# --------------------------

# Initialize configuration from environment variables or Streamlit secrets
def get_config():
    """Get configuration from secrets or environment variables"""
    return {
        "SUPABASE_URL": st.secrets.get("SUPABASE_URL", os.getenv("https://hugjvlpvxqvnkuzfyacw.supabase.co")),
        "SUPABASE_KEY": st.secrets.get("SUPABASE_KEY", os.getenv("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imh1Z2p2bHB2eHF2bmt1emZ5YWN3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQ0Nzg4NDIsImV4cCI6MjA2MDA1NDg0Mn0.BDe2Wrr74P-pkR0XF6Sfgheq6k4Z0LvidHV-7JiDC30")),
        "GEMINI_API_KEY": st.secrets.get("GEMINI_API_KEY", os.getenv("AIzaSyAtGPjtvE-kiDDNjrK75y5uKUz8SfEmQcI"))
    }

config = get_config()

# Validate configuration
if not all(config.values()):
    st.error("""Missing required configuration. Please check:
            1. For local development: Create a .env file with SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY
            2. For Streamlit Cloud: Add these as secrets in secrets.toml""")
    st.stop()

# Assign to variables
SUPABASE_URL = config["SUPABASE_URL"]
SUPABASE_KEY = config["SUPABASE_KEY"]
GEMINI_API_KEY = config["GEMINI_API_KEY"]

# --------------------------
# INITIALIZATION
# --------------------------

@st.cache_resource
def init_supabase():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Supabase connection failed: {e}")
        st.stop()

@st.cache_resource
def init_gemini():
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        return genai.GenerativeModel('gemini-pro')
    except Exception as e:
        st.error(f"Gemini AI setup failed: {e}")
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
