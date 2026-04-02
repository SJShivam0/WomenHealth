import streamlit as st
import sqlite3
from datetime import datetime, timedelta, date
import pandas as pd
import json
from openai import OpenAI

st.set_page_config(page_title="🌸 Women's Health AI", layout="centered", page_icon="🌸")

# ===================== GROQ SETUP =====================
if "GROQ" in st.secrets:
    groq_key = st.secrets["GROQ"]["API_KEY"]
    st.success("✅ Groq API key loaded from Secrets")
else:
    groq_key = st.text_input("Enter your Groq API Key", type="password")

if not groq_key:
    st.error("Groq API key is required.")
    st.stop()

groq_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)

# ===================== DATABASE =====================
conn = sqlite3.connect("app", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        password TEXT,
        full_name TEXT,
        is_partner INTEGER DEFAULT 0
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS cycle_data (
        email TEXT PRIMARY KEY,
        last_period TEXT,
        cycle_length INTEGER,
        age INTEGER,
        health_notes TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS mood_data (
        email TEXT,
        date TEXT,
        mood TEXT,
        score INTEGER,
        cycle_day INTEGER,
        phase TEXT,
        reasons TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_queries (
        email TEXT,
        date TEXT,
        query TEXT
    )
""")
conn.commit()

# ===================== SESSION =====================
if 'user' not in st.session_state:
    st.session_state.user = None
if 'full_name' not in st.session_state:
    st.session_state.full_name = None
if 'is_partner' not in st.session_state:
    st.session_state.is_partner = False
if 'page' not in st.session_state:
    st.session_state.page = "login"

# ===================== HELPERS =====================
def today():
    return datetime.today().date()

def predict_next_period(last_date_str, cycle_length):
    last = datetime.strptime(last_date_str, "%Y-%m-%d").date()
    return (last + timedelta(days=cycle_length)).strftime("%d %B %Y")

def days_to_next_period(last_date_str, cycle_length):
    last = datetime.strptime(last_date_str, "%Y-%m-%d").date()
    return max(0, (last + timedelta(days=cycle_length) - today()).days)

def get_cycle_day(last_date_str, cycle_length):
    last = datetime.strptime(last_date_str, "%Y-%m-%d").date()
    days = (today() - last).days
    if days < 0: return 0
    return (days % cycle_length) + 1

def get_phase(day):
    if day <= 5: return "Menstrual 🩸"
    elif day <= 13: return "Follicular 🌱"
    elif day <= 16: return "Ovulation 🌼"
    else: return "Luteal 🌙"

def load_cycle(email):
    cursor.execute("SELECT last_period, cycle_length, age, health_notes FROM cycle_data WHERE email=?", (email,))
    row = cursor.fetchone()
    if row:
        return {"last_period_date": row[0], "cycle_length": row[1], "age": row[2], "health_notes": row[3] or ""}
    return None

def save_cycle(email, last_date, cycle_length, age, health_notes):
    cursor.execute("INSERT OR REPLACE INTO cycle_data VALUES (?, ?, ?, ?, ?)",
                   (email, last_date.strftime("%Y-%m-%d"), cycle_length, age, health_notes))
    conn.commit()

mood_map = {"😊 Happy": 5, "😐 Neutral": 3, "😔 Low": 2, "😡 Irritated": 1, "😴 Tired": 2}

def save_mood(email, mood, reasons, cycle_day, phase):
    score = mood_map.get(mood, 3)
    today_str = today().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO mood_data VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (email, today_str, mood, score, cycle_day, phase, json.dumps(reasons or [])))
    conn.commit()

def save_ai_query(email, query):
    today_str = today().strftime("%Y-%m-%d")
    cursor.execute("INSERT INTO ai_queries VALUES (?, ?, ?)", (email, today_str, query))
    conn.commit()

def generate_ai_response(prompt):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are a caring, supportive women's health coach."},
                      {"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=400
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}"

# ===================== LOGIN SCREEN =====================
def show_login():
    st.title("🌸 Women's Health AI")
    st.markdown("### Track your cycle • Get guidance • Support your partner")

    # Admin Button at the top right
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("🔐 Admin Login"):
            st.session_state.page = "admin_login"
            st.rerun()

    # Normal User Login
    full_name = st.text_input("Full Name (optional)")
    email = st.text_input("Email Address")
    password = st.text_input("Password", type="password")
    mode = st.radio("I am:", ["Tracking my own cycle", "Partner (Boyfriend/Husband)"], horizontal=True)

    if st.button("🚀 Login / Register", type="primary"):
        if email and password:
            cursor.execute("SELECT password, full_name, is_partner FROM users WHERE email=?", (email,))
            existing = cursor.fetchone()

            if existing:
                saved_password, saved_name, is_partner = existing
                if saved_password == password:
                    st.session_state.user = email
                    st.session_state.full_name = saved_name or email.split('@')[0]
                    st.session_state.is_partner = bool(is_partner)
                    st.success(f"Welcome back, {st.session_state.full_name}!")
                    st.session_state.page = "dashboard"
                    st.rerun()
                else:
                    st.error("Incorrect password")
            else:
                is_partner = 1 if mode == "Partner (Boyfriend/Husband)" else 0
                cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (email, password, full_name, is_partner))
                conn.commit()
                st.session_state.user = email
                st.session_state.full_name = full_name or email.split('@')[0]
                st.session_state.is_partner = bool(is_partner)
                st.success(f"Welcome, {st.session_state.full_name}!")
                st.session_state.page = "dashboard"
                st.rerun()
        else:
            st.error("Email and Password are required")

# ===================== ADMIN LOGIN SCREEN =====================
def show_admin_login():
    st.title("🔐 Admin Login")

    admin_email = st.text_input("Admin Email", value="admin@yourapp.com")
    admin_password = st.text_input("Admin Password", type="password")

    if st.button("Login as Admin"):
        if admin_email == "shivam_j1@ms.iitr.ac.in" and admin_password == "Alice@1510rke202020!":   # Change this password!
            st.session_state.user = admin_email
            st.session_state.full_name = "Admin"
            st.session_state.page = "admin_panel"
            st.success("Admin Login Successful!")
            st.rerun()
        else:
            st.error("Incorrect Admin credentials")

    if st.button("Back to User Login"):
        st.session_state.page = "login"
        st.rerun()

# ===================== ADMIN PANEL =====================
def show_admin_panel():
    st.title("🔐 Admin Dashboard - All Data")

    st.subheader("Registered Users")
    cursor.execute("SELECT email, full_name, is_partner FROM users")
    for u in cursor.fetchall():
        st.write(f"**{u[1] or u[0]}** | {u[0]} | Partner: {'Yes' if u[2] else 'No'}")

    st.subheader("Cycle Data")
    cursor.execute("SELECT * FROM cycle_data")
    data = cursor.fetchall()
    if data:
        df = pd.DataFrame(data, columns=["Email", "Last Period", "Cycle Length", "Age", "Health Notes"])
        st.dataframe(df, use_container_width=True)

    st.subheader("Mood Logs")
    cursor.execute("SELECT * FROM mood_data ORDER BY date DESC")
    mood_data = cursor.fetchall()
    if mood_data:
        df_mood = pd.DataFrame(mood_data, columns=["Email", "Date", "Mood", "Score", "Cycle Day", "Phase", "Reasons"])
        st.dataframe(df_mood, use_container_width=True)

    st.subheader("AI Queries")
    cursor.execute("SELECT * FROM ai_queries ORDER BY date DESC")
    ai_data = cursor.fetchall()
    if ai_data:
        df_ai = pd.DataFrame(ai_data, columns=["Email", "Date", "Query"])
        st.dataframe(df_ai, use_container_width=True)

    if st.button("Back to Login"):
        st.session_state.clear()
        st.rerun()

# ===================== USER DASHBOARD =====================
def show_dashboard():
    email = st.session_state.user
    full_name = st.session_state.full_name
    is_partner = st.session_state.is_partner

    st.title(f"🌸 Welcome, {full_name}!")

    with st.sidebar:
        st.success(f"Logged in as **{full_name}**")
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

    memory = load_cycle(email)

    with st.sidebar.expander("📅 Your Information", expanded=True):
        default_date = None if not memory else datetime.strptime(memory.get("last_period_date", "2025-01-01"), "%Y-%m-%d").date()
        last_date_input = st.date_input("Last Period Date", value=default_date, max_value=today())

        cycle_length = st.number_input("Average Cycle Length (days)", 20, 45, value=memory.get("cycle_length", 28) if memory else 28)
        age = st.number_input("Your Age", 13, 60, value=memory.get("age", 25) if memory else 25)
        health_notes = st.text_area("Health History / Important Events", 
                                    value=memory.get("health_notes", "") if memory else "",
                                    placeholder="Recent pregnancy, delivery, breastfeeding, PCOS, etc.")

        if st.button("💾 Save Information", type="primary"):
            if last_date_input:
                save_cycle(email, last_date_input, int(cycle_length), int(age), health_notes)
                st.success("✅ Information saved successfully!")
                st.rerun()

    if not memory:
        st.info("👉 Please fill your information from the sidebar and click **Save Information**.")
        st.stop()

    cycle_day = get_cycle_day(memory["last_period_date"], memory["cycle_length"])
    phase = get_phase(cycle_day)
    next_period = predict_next_period(memory["last_period_date"], memory["cycle_length"])
    days_left = days_to_next_period(memory["last_period_date"], memory["cycle_length"])

    if is_partner:
        st.info("👫 You are in **Partner Mode**")
        tab1, tab2 = st.tabs(["📊 Overview", "💡 Support Suggestions"])
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "😊 Mood Tracker", "🤖 AI Coach", "💬 Ask AI"])

    with tab1:
        st.subheader("Cycle Overview")
        col1, col2, col3 = st.columns(3)
        col1.metric("Cycle Day", f"Day {cycle_day}")
        col2.metric("Current Phase", phase)
        col3.metric("Next Period", next_period)
        st.metric("Days until next period", f"{days_left} days")

    if is_partner:
        with tab2:
            st.subheader("💡 How You Can Support Her")
            with st.spinner("AI thinking..."):
                advice = generate_ai_response(f"She is on cycle day {cycle_day} in {phase} phase.")
            st.markdown(advice)
    else:
        with tab2:
            st.subheader("😊 Log Today's Mood")
            mood = st.selectbox("How are you feeling today?", list(mood_map.keys()))
            reasons = st.multiselect("What influenced your mood?", ["Cycle", "Work Stress", "Sleep", "Diet", "Relationship", "Other"])
            if st.button("Save Mood"):
                save_mood(email, mood, reasons, cycle_day, phase)
                st.success("✅ Mood saved!")

        with tab3:
            st.subheader("🤖 Today's AI Coach")
            with st.spinner("AI thinking..."):
                coach = generate_ai_response(f"User is on cycle day {cycle_day} in {phase} phase.")
            st.markdown(coach)

        with tab4:
            st.subheader("💬 Ask AI Anything")
            question = st.text_area("Ask about diet, symptoms, cramps, energy, mood, etc.")
            if st.button("Get Answer"):
                if question:
                    save_ai_query(email, question)
                    with st.spinner("Thinking..."):
                        answer = generate_ai_response(question)
                    st.markdown(answer)

    st.caption("⚠️ This is not medical advice.")

# ===================== MAIN =====================
if st.session_state.page == "login":
    show_login()
elif st.session_state.page == "admin_login":
    show_admin_login()
elif st.session_state.page == "admin_panel":
    show_admin_panel()
else:
    show_dashboard()
