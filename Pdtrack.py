import streamlit as st
import sqlite3
from datetime import datetime, timedelta, date
import pandas as pd
import json
from openai import OpenAI

st.set_page_config(page_title="🌸 Women's Health AI", layout="centered", page_icon="🌸")

# ===================== GROQ SETUP =====================
groq_key = st.text_input("Enter your Groq API Key", type="password", help="Get it from https://console.groq.com/keys")

if not groq_key:
    st.warning("Please enter your Groq API key above to enable AI features.")
    groq_client = None
else:
    groq_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)

# ===================== DATABASE - Recreate with new structure =====================
conn = sqlite3.connect("app.db", check_same_thread=False)
cursor = conn.cursor()

# Drop old tables to fix column errors
cursor.execute("DROP TABLE IF EXISTS users")
cursor.execute("DROP TABLE IF EXISTS cycle_data")
cursor.execute("DROP TABLE IF EXISTS mood_data")

cursor.execute("""
    CREATE TABLE users (
        email TEXT PRIMARY KEY,
        password TEXT,
        full_name TEXT,
        is_partner INTEGER DEFAULT 0
    )
""")

cursor.execute("""
    CREATE TABLE cycle_data (
        email TEXT PRIMARY KEY,
        last_period TEXT,
        cycle_length INTEGER,
        age INTEGER,
        health_notes TEXT
    )
""")

cursor.execute("""
    CREATE TABLE mood_data (
        email TEXT,
        date TEXT,
        mood TEXT,
        score INTEGER,
        cycle_day INTEGER,
        phase TEXT,
        reasons TEXT
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
        return {
            "last_period_date": row[0],
            "cycle_length": row[1],
            "age": row[2],
            "health_notes": row[3] or ""
        }
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

def generate_ai_response(prompt):
    if not groq_key:
        return "Please enter your Groq API key above."
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

# ===================== LOGIN =====================
def show_login():
    st.title("🌸 Women's Health AI")
    st.markdown("### Track your cycle • Get guidance • Support your partner")

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
                is_partner = 1 if "Partner" in mode else 0
                cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)", 
                             (email, password, full_name, is_partner))
                conn.commit()
                st.session_state.user = email
                st.session_state.full_name = full_name or email.split('@')[0]
                st.session_state.is_partner = bool(is_partner)
                st.success(f"Account created successfully! Welcome, {st.session_state.full_name}!")
                st.session_state.page = "dashboard"
                st.rerun()
        else:
            st.error("Email and Password are required")

# ===================== ADMIN DASHBOARD =====================
def show_admin_dashboard():
    st.title("🔐 Admin Dashboard - All Customers")

    cursor.execute("SELECT email, full_name, is_partner FROM users")
    users = cursor.fetchall()
    for u in users:
        st.write(f"**{u[1] or u[0]}** ({u[0]}) | Partner: {'Yes' if u[2] else 'No'}")

    cursor.execute("SELECT * FROM cycle_data")
    data = cursor.fetchall()
    if data:
        df = pd.DataFrame(data, columns=["Email", "Last Period", "Cycle Length", "Age", "Health Notes"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No cycle data yet.")

    if st.button("Back to App"):
        st.session_state.page = "dashboard"
        st.rerun()

# ===================== DASHBOARD =====================
def show_dashboard():
    email = st.session_state.user
    full_name = st.session_state.full_name
    is_partner = st.session_state.is_partner

    if email and email.lower() == "admin@example.com":
        if st.sidebar.button("🔐 Open Admin Dashboard"):
            st.session_state.page = "admin"
            st.rerun()

    st.title(f"🌸 Welcome, {full_name}!")

    with st.sidebar:
        st.success(f"Logged in as **{full_name}**")
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

    memory = load_cycle(email)

    with st.sidebar.expander("📅 Your Information", expanded=True):
        last_date_input = st.date_input("Last Period Date", 
                                        value=None if not memory else datetime.strptime(memory.get("last_period_date", ""), "%Y-%m-%d").date(),
                                        max_value=today())
        
        cycle_length = st.number_input("Average Cycle Length (days)", 20, 45, 
                                       value=memory.get("cycle_length", 28) if memory else 28)
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

        if memory.get("health_notes"):
            st.info(f"**Health Note:** {memory['health_notes']}")

    if is_partner:
        with tab2:
            st.subheader("💡 How You Can Support Her")
            context = f"Give caring suggestions. She is {memory.get('age', 'unknown')} years old, on cycle day {cycle_day} in {phase} phase."
            with st.spinner("AI thinking..."):
                advice = generate_ai_response(context)
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
            context = f"User is {memory.get('age', 'unknown')} years old, on cycle day {cycle_day} in {phase} phase."
            with st.spinner("AI thinking..."):
                coach = generate_ai_response(context)
            st.markdown(coach)

        with tab4:
            st.subheader("💬 Ask AI Anything")
            question = st.text_area("Ask about diet, symptoms, cramps, energy, mood, etc.")
            if st.button("Get Answer"):
                if question:
                    prompt = f"User age: {memory.get('age')}, day {cycle_day} ({phase}). Health: {memory.get('health_notes','None')}\nQuestion: {question}"
                    with st.spinner("Thinking..."):
                        answer = generate_ai_response(prompt)
                    st.markdown(answer)
                else:
                    st.warning("Please type a question")

    st.caption("⚠️ This is not medical advice. Consult a doctor when needed.")

# ===================== MAIN =====================
if st.session_state.user is None:
    show_login()
elif st.session_state.user == "admin@example.com":
    show_admin_dashboard()
else:
    show_dashboard()
