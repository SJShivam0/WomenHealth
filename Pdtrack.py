import streamlit as st
import sqlite3
from datetime import datetime, timedelta, date
import pandas as pd
from openai import OpenAI

# ===================== CONFIG =====================
st.markdown("""
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="🌸 Women's Health AI", layout="centered", page_icon="🌸")

# ===================== GROQ =====================
if "GROQ" in st.secrets:
    groq_key = st.secrets["GROQ"]["API_KEY"]
else:
    groq_key = st.text_input("Enter your Groq API Key", type="password")

if not groq_key:
    st.error("Groq API key is required.")
    st.stop()

groq_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)

# ===================== DATABASE =====================
conn = sqlite3.connect("app", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""CREATE TABLE IF NOT EXISTS users 
    (email TEXT PRIMARY KEY, password TEXT, full_name TEXT, is_partner INTEGER DEFAULT 0)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS cycle_data 
    (email TEXT PRIMARY KEY, last_period TEXT, cycle_length INTEGER, age INTEGER, health_notes TEXT)""")

cursor.execute("""CREATE TABLE IF NOT EXISTS mood_data 
    (email TEXT, date TEXT, mood TEXT, score INTEGER, cycle_day INTEGER, phase TEXT, reasons TEXT)""")

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
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# ===================== HELPERS =====================
def today():
    return datetime.today().date()

def get_cycle_day(last_date_str, cycle_length):
    last = datetime.strptime(last_date_str, "%Y-%m-%d").date()
    days = (today() - last).days
    return (days % cycle_length) + 1 if days >= 0 else 0

def get_phase(day):
    if day <= 5:
        return "Menstrual Phase (Period / Rest Phase) 🩸"
    elif day <= 13:
        return "Follicular Phase (Growth & Energy Phase) 🌱"
    elif day <= 16:
        return "Ovulation Phase (Fertile Window) 🌼"
    else:
        return "Luteal Phase (Pre-Period Phase) 🌙"

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

def generate_ai_response(prompt):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are a caring, supportive women's health coach."},
                      {"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=450
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ AI is temporarily unavailable. Error: {str(e)}"

# ===================== LOGIN =====================
def show_login():
    st.title("🌸 Women's Health AI")
    st.markdown("### Track your cycle • Get guidance • Support your partner")

    col1, col2 = st.columns([5, 1])
    with col2:
        if st.button("🔐 Admin"):
            st.session_state.page = "admin_login"
            st.rerun()

    full_name = st.text_input("Full Name (optional)")
    email = st.text_input("Email Address")
    password = st.text_input("Password", type="password")
    mode = st.radio("I am:", ["Tracking my own cycle", "Partner (Boyfriend/Husband)"], horizontal=True)

    if st.button("🚀 Login / Register", type="primary"):
        if not email or not password:
            st.error("Email and Password are required")
            return

        cursor.execute("SELECT password, full_name, is_partner FROM users WHERE email=?", (email,))
        existing = cursor.fetchone()

        if existing:
            if existing[0] == password:
                st.session_state.user = email
                st.session_state.full_name = existing[1] or email.split('@')[0]
                st.session_state.is_partner = bool(existing[2])
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

# ===================== ADMIN =====================
def show_admin_login():
    st.title("🔐 Admin Login")
    admin_email = st.text_input("Admin Email", "admin@yourapp.com")
    admin_pass = st.text_input("Admin Password", type="password")
    if st.button("Login as Admin"):
        if admin_email == "shivam_j1@ms.iitr.ac.in" and admin_pass == "Alice@1510rke202020!":
            st.session_state.user = admin_email
            st.session_state.full_name = "Admin"
            st.session_state.page = "admin_panel"
            st.rerun()
        else:
            st.error("Wrong credentials")
    if st.button("← Back"):
        st.session_state.page = "login"
        st.rerun()

def show_admin_panel():
    st.title("🔐 Admin Dashboard")
    cursor.execute("SELECT * FROM cycle_data")
    data = cursor.fetchall()
    if data:
        st.dataframe(pd.DataFrame(data, columns=["Email", "Last Period", "Cycle Length", "Age", "Health Notes"]), use_container_width=True)
    if st.button("← Back"):
        st.session_state.clear()
        st.rerun()

# ===================== DASHBOARD =====================
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
    if not memory:
        st.info("👉 Please fill information from sidebar and click Save.")
        st.stop()

    cycle_day = get_cycle_day(memory["last_period_date"], memory["cycle_length"])
    phase = get_phase(cycle_day)

    # Sidebar Information
    sidebar_title = "📅 Your Partner's Information" if is_partner else "📅 Your Information"
    with st.sidebar.expander(sidebar_title, expanded=True):
        last_date = st.date_input("Last Period Date", value=datetime.strptime(memory["last_period_date"], "%Y-%m-%d").date())
        cycle_length = st.number_input("Average Cycle Length (days)", 20, 45, memory["cycle_length"])
        age = st.number_input("Age", 13, 60, memory["age"])
        health_notes = st.text_area("Health History / Important Events (Helps AI give personalized suggestions)", 
                                    value=memory["health_notes"],
                                    placeholder="PCOS, thyroid, recent pregnancy, breastfeeding, etc.")

        if st.button("💾 Save Information", type="primary"):
            save_cycle(email, last_date, int(cycle_length), int(age), health_notes)
            st.success("✅ Saved successfully!")
            st.rerun()

    if is_partner:
        st.info("👫 You are in **Partner Mode**")
        tab1, tab2 = st.tabs(["📊 Overview", "💡 Support Suggestions"])
    else:
        tab1, tab2, tab3 = st.tabs(["📊 Overview", "😊 Mood Tracker", "🤖 AI Coach"])

    with tab1:
        st.subheader("Cycle Overview")
        col1, col2, col3 = st.columns(3)
        col1.metric("Cycle Day", f"Day {cycle_day}")
        col2.metric("Current Phase", phase)
        col3.metric("Next Period", predict_next_period(memory["last_period_date"], memory["cycle_length"]))
        st.metric("Days until next period", f"{days_to_next_period(memory['last_period_date'], memory['cycle_length'])} days")

    if is_partner:
        with tab2:
            st.subheader("💡 How You Can Support Her")
            st.markdown("Answer if you know, otherwise click **Skip** for general advice.")
            partner_input = st.text_area("Your observations:", height=100, placeholder="Skip if unsure")
            if st.button("Get Support Suggestions", type="primary"):
                prompt = f"Give caring suggestions for a boyfriend. His partner is on cycle day {cycle_day} in {phase}. Health notes: {memory.get('health_notes','None')}. Partner input: {partner_input or 'No specific input'}"
                with st.spinner("Thinking..."):
                    advice = generate_ai_response(prompt)
                st.session_state.chat_history = [{"role": "assistant", "content": advice}]
                st.rerun()
            if st.session_state.chat_history:
                st.write("**AI Coach:**", st.session_state.chat_history[0]["content"])
    else:
        # Women's AI Coach with Radio Buttons
        with tab2:
            st.subheader("😊 Log Today's Mood")
            mood = st.selectbox("How are you feeling today?", list(mood_map.keys()))
            reasons = st.multiselect("What influenced your mood?", ["Cycle", "Work Stress", "Sleep", "Diet", "Relationship", "Other"])
            if st.button("Save Mood"):
                save_mood(email, mood, reasons, cycle_day, phase)   # Note: save_mood function needs to be added if you want full mood saving
                st.success("✅ Mood saved!")

        with tab3:
            st.subheader("🤖 AI Coach")
            st.markdown("**Answer these questions to get personalised suggestions**")

            # Dynamic Questions with Radio Buttons
            with st.spinner("Preparing questions based on your phase..."):
                q_prompt = f"""Create 3 relevant questions for a woman on cycle day {cycle_day} in {phase} phase.
Health notes: {memory.get('health_notes', 'None')}.
For each question give 3-4 clear options + "Other"."""

                questions_text = generate_ai_response(q_prompt)

            st.markdown(questions_text)

            answers = st.text_area("Write your answers below (you can copy-paste the questions):", height=250)

            if st.button("Get Personalised Advice", type="primary"):
                if answers.strip():
                    prompt = f"""Cycle day {cycle_day} • Phase: {phase}
Health notes: {memory.get('health_notes', 'None')}
User answers: {answers}

Give warm, practical and highly personalised advice."""
                    with st.spinner("AI Coach is thinking..."):
                        advice = generate_ai_response(prompt)
                    st.session_state.chat_history = [{"role": "assistant", "content": advice}]
                    st.rerun()

            if st.session_state.chat_history:
                st.markdown("---")
                st.markdown("**Continue conversation with AI Coach**")
                for msg in st.session_state.chat_history:
                    st.write(f"**AI Coach:** {msg['content']}")

                follow_up = st.text_input("Type your follow-up question...")
                if st.button("Send Follow-up"):
                    if follow_up:
                        st.session_state.chat_history.append({"role": "user", "content": follow_up})
                        with st.spinner("Thinking..."):
                            answer = generate_ai_response(follow_up)
                        st.session_state.chat_history.append({"role": "assistant", "content": answer})
                        st.rerun()

    st.caption("⚠️ This is not medical advice.")

# ===================== MAIN FLOW =====================
if st.session_state.page == "login":
    show_login()
elif st.session_state.page == "admin_login":
    show_admin_login()
elif st.session_state.page == "admin_panel":
    show_admin_panel()
else:
    show_dashboard()
