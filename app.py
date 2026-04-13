import streamlit as st
from pymongo import MongoClient
import pandas as pd
from groq import Groq
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ---------- PAGE CONFIG ----------
st.set_page_config(page_title="AI-Based Personalized Study Planner", layout="wide", page_icon="📊")

# ---------- THEME CSS ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    background-color: #080c14 !important;
    color: #e2e8f0 !important;
    font-family: 'DM Sans', sans-serif !important;
}
h1, h2, h3 {
    font-family: 'Space Mono', monospace !important;
    letter-spacing: -0.5px;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #0a0f1a 100%) !important;
    border-right: 1px solid #1e2d40 !important;
}
section[data-testid="stMain"] { background-color: #080c14 !important; }
.kpi-card {
    background: linear-gradient(135deg, #0d1b2e 0%, #112240 100%);
    border: 1px solid #1e3a5f;
    border-radius: 16px;
    padding: 24px 20px;
    text-align: center;
    position: relative;
    overflow: hidden;
    margin-bottom: 8px;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #00d4ff, #0099ff);
}
.kpi-value {
    font-family: 'Space Mono', monospace;
    font-size: 2.2rem;
    font-weight: 700;
    color: #00d4ff;
    line-height: 1;
    margin-bottom: 6px;
}
.kpi-label {
    font-size: 0.78rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}
.kpi-card.admin::before { background: linear-gradient(90deg, #ff6b6b, #ff4757); }
.kpi-card.admin .kpi-value { color: #ff6b6b; }
.section-header {
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 3px;
    color: #3b82f6;
    margin: 24px 0 12px 0;
    padding-bottom: 6px;
    border-bottom: 1px solid #1e2d40;
}
.stButton>button {
    width: 100%;
    background: transparent !important;
    color: #94a3b8 !important;
    border: none !important;
    text-align: left !important;
    padding: 10px 16px !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.88rem !important;
    transition: all 0.2s !important;
}
.stButton>button:hover {
    background: #0f2040 !important;
    color: #00d4ff !important;
}
.insight-box {
    background: linear-gradient(135deg, #0a1f3a, #0d2d1a);
    border: 1px solid #1e3a5f;
    border-left: 4px solid #00d4ff;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 10px 0;
    font-size: 0.88rem;
}
.insight-box.warning {
    background: linear-gradient(135deg, #2d1a0a, #2d0d0d);
    border-left: 4px solid #ff6b35;
}
.progress-wrap {
    background: #0d1b2e;
    border-radius: 20px;
    height: 8px;
    margin: 4px 0 12px 0;
    overflow: hidden;
}
.progress-fill {
    height: 100%;
    border-radius: 20px;
    background: linear-gradient(90deg, #00d4ff, #0099ff);
}
.progress-fill.danger { background: linear-gradient(90deg, #ef4444, #ff6b6b); }
.progress-fill.warning { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
.badge-green {
    background: #0d2d1a; color: #22c55e;
    border: 1px solid #22c55e44;
    padding: 3px 10px; border-radius: 20px;
    font-size: 0.75rem; font-family: 'Space Mono', monospace;
}
.badge-blue {
    background: #0a1f3a; color: #00d4ff;
    border: 1px solid #00d4ff44;
    padding: 3px 10px; border-radius: 20px;
    font-size: 0.75rem; font-family: 'Space Mono', monospace;
}
[data-testid="stDataFrame"] {
    border: 1px solid #1e2d40 !important;
    border-radius: 12px !important;
}
[data-testid="stExpander"] {
    background: #0d1b2e !important;
    border: 1px solid #1e3a5f !important;
    border-radius: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# ---------- GROQ ----------
client_groq = Groq(api_key="Ypur_API_KEY")

# ---------- DATABASE ----------
# (must be before email functions so users_col is available)
mongo_client = MongoClient("mongodb://localhost:27017/")
db = mongo_client["study_planner"]
users_col = db["users"]
marks_col = db["marks"]
tasks_col = db["tasks"]
quizzes_col = db["quizzes"]
quiz_results_col = db["quiz_results"]

# ---------- EMAIL CONFIG ----------
# Reads credentials from a .env file in the same folder as app.py
# Create a file called  .env  and add these two lines:
#   EMAIL_SENDER=yourgmail@gmail.com
#   EMAIL_PASSWORD=your_16char_app_password
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional; fall back to os.environ or placeholders

EMAIL_SENDER   = os.environ.get("EMAIL_SENDER",   "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")

def send_email(to_address: str, subject: str, body: str) -> tuple[bool, str]:
    """Send an HTML email. Returns (success, error_message)."""
    # Allow credentials saved via the Email Settings UI to override .env
    sender   = st.session_state.get("email_sender",   EMAIL_SENDER).strip()
    password = st.session_state.get("email_password", EMAIL_PASSWORD).strip()

    if not to_address or "@" not in to_address:
        return False, f"Invalid email address: '{to_address}'"
    if not sender or not password:
        return False, "Email credentials not set. Go to Admin → Email Settings and save your Gmail + App Password."
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = sender
        msg["To"]      = to_address
        msg.attach(MIMEText(body, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(sender, password)
            server.sendmail(sender, to_address, msg.as_string())
        return True, ""
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail authentication failed. Use an App Password (not your regular Gmail password). See Admin → Email Settings for instructions."
    except smtplib.SMTPRecipientsRefused:
        return False, f"Recipient address refused: {to_address}"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"

def send_quiz_reminder(student_email: str, student_name: str, quiz_title: str, subject: str) -> tuple[bool, str]:
    """Send a quiz reminder email to a student. Returns (success, error)."""
    subject_line = f"[Study Planner] New Quiz: {quiz_title} - {subject}"
    body = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;">
    <div style="max-width:600px;margin:auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.1);">
      <div style="background:linear-gradient(135deg,#0d1b2e,#112240);padding:30px;text-align:center;">
        <h1 style="color:#00d4ff;font-family:monospace;margin:0;">Study Planner</h1>
        <p style="color:#94a3b8;margin:8px 0 0 0;">AI Based Personalized Study Planner</p>
      </div>
      <div style="padding:30px;">
        <h2 style="color:#1e293b;">Hi {student_name}!</h2>
        <p style="color:#475569;font-size:16px;">A new quiz has been assigned to you. Don't miss it!</p>
        <div style="background:#f0f9ff;border-left:4px solid #00d4ff;border-radius:8px;padding:16px 20px;margin:20px 0;">
          <p style="margin:0;color:#0f172a;"><strong>Subject:</strong> {subject}</p>
          <p style="margin:8px 0 0 0;color:#0f172a;"><strong>Quiz Title:</strong> {quiz_title}</p>
        </div>
        <p style="color:#475569;">Log in to your study planner and go to the <strong>Take Quiz</strong> section to attempt it now.</p>
        <p style="color:#94a3b8;font-size:13px;">Keep studying hard - your performance matters!</p>
      </div>
      <div style="background:#f8fafc;padding:16px;text-align:center;border-top:1px solid #e2e8f0;">
        <p style="color:#94a3b8;font-size:12px;margin:0;">AI Based Personalized Study Planner</p>
      </div>
    </div>
    </body></html>
    """
    return send_email(student_email, subject_line, body)

def send_bulk_quiz_reminders(quiz_title: str, subject: str) -> tuple[int, int, list]:
    """
    Send quiz reminders to all students who have a registered email.
    Returns (sent_count, failed_count, list_of_error_messages).
    """
    students = list(users_col.find({"role": "student", "email": {"$exists": True, "$ne": ""}}))
    sent, failed, errors = 0, 0, []
    for s in students:
        ok, err = send_quiz_reminder(s["email"], s["username"], quiz_title, subject)
        if ok:
            sent += 1
        else:
            failed += 1
            errors.append(f"{s['username']} ({s['email']}): {err}")
    return sent, failed, errors

# ---------- SESSION ----------
if "page" not in st.session_state:
    st.session_state.page = "login"

# ---------- HELPERS ----------
def do_login(username, password):
    return users_col.find_one({"username": username, "password": password})

def do_register(username, password, role, email=""):
    if users_col.find_one({"username": username}):
        return False
    users_col.insert_one({"username": username, "password": password, "role": role, "email": email})
    return True

def get_grade(avg):
    if avg >= 90: return "A+", "#22c55e"
    elif avg >= 80: return "A", "#22c55e"
    elif avg >= 70: return "B", "#00d4ff"
    elif avg >= 60: return "C", "#f59e0b"
    elif avg >= 50: return "D", "#f97316"
    else: return "F", "#ef4444"

def progress_bar(value, max_val=100):
    pct = min(100, (value / max_val) * 100) if max_val > 0 else 0
    cls = "danger" if pct < 50 else ("warning" if pct < 70 else "")
    return f"<div class='progress-wrap'><div class='progress-fill {cls}' style='width:{pct}%'></div></div>"

# ============================================================
# LOGIN
# ============================================================
def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align:center;color:#00d4ff;font-size:2rem;'>🤖 AI Based Personalized Study Planner</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:#64748b;margin-bottom:32px;'>Intelligent Study Performance Platform</p>", unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["Sign In", "Register"])
        with tab1:
            u = st.text_input("Username", placeholder="Enter username")
            p = st.text_input("Password", type="password", placeholder="Enter password")
            if st.button("Sign In →", use_container_width=True):
                user = do_login(u, p)
                if user:
                    st.session_state.user = user
                    st.session_state.page = user.get("role", "student")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
        with tab2:
            nu = st.text_input("Username", placeholder="Choose username", key="reg_u")
            np_val = st.text_input("Password", type="password", placeholder="Choose password", key="reg_p")
            ne = st.text_input("Email Address", placeholder="Enter your email (for quiz reminders)", key="reg_e")
            role = st.selectbox("Role", ["student", "admin"])
            if st.button("Create Account", use_container_width=True):
                if do_register(nu, np_val, role, ne):
                    st.success("Account created! Please sign in.")
                else:
                    st.error("Username already taken.")

# ============================================================
# STUDENT DASHBOARD
# ============================================================
def student_dashboard():
    user = st.session_state.user["username"]

    with st.sidebar:
        st.markdown(f"<div style='padding:16px 8px;'><div style='font-family:Space Mono;color:#00d4ff;font-size:0.8rem;'>STUDENT</div><div style='font-size:1.1rem;font-weight:600;'>{user}</div></div>", unsafe_allow_html=True)
        st.markdown("<hr style='border-color:#1e2d40;margin:0 0 12px 0;'>", unsafe_allow_html=True)

        if "menu" not in st.session_state:
            st.session_state.menu = "Dashboard"

        pages = [
            ("🏠", "Dashboard"),
            ("📈", "My Analytics"),
            ("➕", "Add Marks"),
            ("📅", "Study Plan"),
            ("📝", "Take Quiz"),
            ("🏆", "Quiz History"),
            ("✅", "My Tasks"),
            ("🤖", "AI Tutor"),
        ]
        for icon, label in pages:
            if st.button(f"{icon}  {label}", key=f"nav_{label}"):
                st.session_state.menu = label
                if label != "Take Quiz" and "quiz_state" in st.session_state:
                    del st.session_state["quiz_state"]

        st.markdown("<hr style='border-color:#1e2d40;'>", unsafe_allow_html=True)
        if st.button("Logout"):
            st.session_state.clear()
            st.session_state.page = "login"
            st.rerun()

    menu = st.session_state.menu

    # ======== DASHBOARD ========
    if menu == "Dashboard":
        st.markdown(f"<h2>Welcome back, {user} 👋</h2>", unsafe_allow_html=True)
        data = list(marks_col.find({"username": user}))
        quiz_data = list(quiz_results_col.find({"student": user}))
        tasks = list(tasks_col.find({"student": user}))

        if data:
            df = pd.DataFrame(data)
            avg = round(df["marks"].mean(), 1)
            max_m = df["marks"].max()
            subjects = df["subject"].nunique()
            grade, gcolor = get_grade(avg)
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.markdown(f"<div class='kpi-card'><div class='kpi-value'>{avg}</div><div class='kpi-label'>Avg Score</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='kpi-card'><div class='kpi-value'>{max_m}</div><div class='kpi-label'>Best Score</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='kpi-card'><div class='kpi-value'>{subjects}</div><div class='kpi-label'>Subjects</div></div>", unsafe_allow_html=True)
            c4.markdown(f"<div class='kpi-card'><div class='kpi-value' style='color:{gcolor};'>{grade}</div><div class='kpi-label'>Grade</div></div>", unsafe_allow_html=True)
            c5.markdown(f"<div class='kpi-card'><div class='kpi-value'>{len(quiz_data)}</div><div class='kpi-label'>Quizzes Taken</div></div>", unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<div class='section-header'>Subject Performance</div>", unsafe_allow_html=True)
                sub_avg = df.groupby("subject")["marks"].mean().sort_values()
                for subj, val in sub_avg.items():
                    g, gc = get_grade(val)
                    st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;'><span style='font-size:0.85rem;'>{subj}</span><span style='font-family:Space Mono;font-size:0.85rem;color:{gc};'>{round(val,1)} ({g})</span></div>", unsafe_allow_html=True)
                    st.markdown(progress_bar(val), unsafe_allow_html=True)
            with col2:
                st.markdown("<div class='section-header'>Quick Insights</div>", unsafe_allow_html=True)
                weak_subjects = df[df["marks"] < 50]["subject"].unique()
                strong_subjects = df[df["marks"] >= 80]["subject"].unique()
                if len(weak_subjects) > 0:
                    st.markdown(f"<div class='insight-box warning'>⚠️ <strong>Needs Attention:</strong> {', '.join(weak_subjects)}</div>", unsafe_allow_html=True)
                if len(strong_subjects) > 0:
                    st.markdown(f"<div class='insight-box'>✅ <strong>Strong Subjects:</strong> {', '.join(strong_subjects)}</div>", unsafe_allow_html=True)
                total_quizzes_available = quizzes_col.count_documents({})
                st.markdown(f"<div class='insight-box'>📝 <strong>Quizzes Available:</strong> {total_quizzes_available}</div>", unsafe_allow_html=True)
                if tasks:
                    st.markdown(f"<div class='insight-box'>📌 <strong>Tasks Assigned:</strong> {len(tasks)}</div>", unsafe_allow_html=True)
        else:
            st.info("No marks recorded yet. Go to 'Add Marks' to get started.")

    # ======== MY ANALYTICS ========
    elif menu == "My Analytics":
        st.markdown("<h2>📈 My Analytics</h2>", unsafe_allow_html=True)
        data = list(marks_col.find({"username": user}))
        if data:
            df = pd.DataFrame(data)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<div class='section-header'>Score Distribution by Subject</div>", unsafe_allow_html=True)
                st.bar_chart(df.groupby("subject")["marks"].mean())
            with col2:
                st.markdown("<div class='section-header'>Progress Over Attempts</div>", unsafe_allow_html=True)
                df["attempt"] = df.groupby("subject").cumcount() + 1
                pivot = df.pivot_table(index="attempt", columns="subject", values="marks", aggfunc="mean")
                st.line_chart(pivot)

            st.markdown("<div class='section-header'>Detailed Subject Breakdown</div>", unsafe_allow_html=True)
            summary = df.groupby("subject")["marks"].agg(["mean", "max", "min", "count"]).reset_index()
            summary.columns = ["Subject", "Average", "Best", "Lowest", "Attempts"]
            summary["Average"] = summary["Average"].round(1)
            summary["Grade"] = summary["Average"].apply(lambda x: get_grade(x)[0])
            st.dataframe(summary, use_container_width=True)

            st.markdown("<div class='section-header'>Performance Heatmap</div>", unsafe_allow_html=True)
            df2 = df.copy()
            df2["attempt"] = df2.groupby("subject").cumcount() + 1
            pivot2 = df2.pivot_table(index="subject", columns="attempt", values="marks", aggfunc="mean").fillna(0)
            st.dataframe(pivot2.style.background_gradient(cmap="Blues"), use_container_width=True)
        else:
            st.info("No marks available for analysis.")

    # ======== ADD MARKS ========
    elif menu == "Add Marks":
        st.markdown("<h2>➕ Add Marks</h2>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("<div class='section-header'>Manual Entry</div>", unsafe_allow_html=True)
            with st.form("add_marks_form"):
                subject = st.text_input("Subject Name")
                marks = st.number_input("Marks (out of 100)", 0, 100, 0)
                if st.form_submit_button("Add Record"):
                    if subject:
                        marks_col.insert_one({
                            "username": user, "subject": subject,
                            "marks": int(marks),
                            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                        })
                        st.success(f"✅ {subject}: {marks} added!")
                    else:
                        st.warning("Please enter a subject name.")
        with col2:
            st.markdown("<div class='section-header'>Bulk Upload (CSV)</div>", unsafe_allow_html=True)
            st.markdown("<div class='insight-box'>CSV must have columns: <code>subject</code>, <code>marks</code></div>", unsafe_allow_html=True)
            file = st.file_uploader("Upload CSV", type=["csv"])
            if file:
                df_up = pd.read_csv(file)
                if "subject" in df_up.columns and "marks" in df_up.columns:
                    count = 0
                    for _, row in df_up.iterrows():
                        marks_col.insert_one({
                            "username": user, "subject": str(row["subject"]),
                            "marks": int(row["marks"]),
                            "added_at": datetime.now().strftime("%Y-%m-%d")
                        })
                        count += 1
                    st.success(f"✅ {count} records uploaded!")
                else:
                    st.error("CSV must have 'subject' and 'marks' columns.")

        st.markdown("<div class='section-header'>All Recorded Marks</div>", unsafe_allow_html=True)
        data = list(marks_col.find({"username": user}))
        if data:
            df_show = pd.DataFrame(data)[["subject", "marks"]].rename(columns={"subject": "Subject", "marks": "Marks"})
            st.dataframe(df_show, use_container_width=True)
        else:
            st.info("No marks recorded yet.")

    # ======== STUDY PLAN ========
    elif menu == "Study Plan":
        st.markdown("<h2>📅 Smart Study Plan</h2>", unsafe_allow_html=True)
        data = list(marks_col.find({"username": user}))
        if data:
            df = pd.DataFrame(data)
            df_avg = df.groupby("subject")["marks"].mean().reset_index()
            df_avg.columns = ["Subject", "Average"]
            hrs = st.slider("Available Study Hours per Day", 1, 12, 6)
            df_avg["Priority Score"] = (100 - df_avg["Average"]).clip(lower=0)
            total_priority = df_avg["Priority Score"].sum()
            df_avg["Recommended Hours"] = ((df_avg["Priority Score"] / total_priority) * hrs).round(2) if total_priority > 0 else hrs / len(df_avg)
            df_avg["Grade"] = df_avg["Average"].apply(lambda x: get_grade(x)[0])
            df_avg["Average"] = df_avg["Average"].round(1)

            st.markdown("<div class='section-header'>Recommended Daily Schedule</div>", unsafe_allow_html=True)
            for _, row in df_avg.sort_values("Recommended Hours", ascending=False).iterrows():
                g, gc = get_grade(row["Average"])
                pct = row["Recommended Hours"] / hrs * 100
                st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;'><span><strong>{row['Subject']}</strong></span><span style='font-family:Space Mono;color:{gc};'>{row['Recommended Hours']}h &nbsp; Grade: {row['Grade']}</span></div>", unsafe_allow_html=True)
                st.markdown(progress_bar(pct), unsafe_allow_html=True)

            st.markdown("<div class='section-header'>Full Plan</div>", unsafe_allow_html=True)
            st.dataframe(df_avg[["Subject","Average","Grade","Recommended Hours"]].sort_values("Recommended Hours", ascending=False), use_container_width=True)

            weakest = df_avg.sort_values("Average").iloc[0]
            strongest = df_avg.sort_values("Average").iloc[-1]
            st.markdown(f"<div class='insight-box warning'>🔴 Focus most on <strong>{weakest['Subject']}</strong> — avg: {weakest['Average']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='insight-box'>🟢 Maintain <strong>{strongest['Subject']}</strong> — avg: {strongest['Average']}</div>", unsafe_allow_html=True)
        else:
            st.info("Add marks first to generate a study plan.")

    # ======== TAKE QUIZ ========
    elif menu == "Take Quiz":
        st.markdown("<h2>📝 Take a Quiz</h2>", unsafe_allow_html=True)
        quizzes = list(quizzes_col.find())

        if not quizzes:
            st.info("No quizzes available yet. Check back later!")
        else:
            if "quiz_state" not in st.session_state:

                # --- Build subject performance map from marks ---
                marks_data = list(marks_col.find({"username": user}))
                subject_avg = {}
                if marks_data:
                    marks_df = pd.DataFrame(marks_data)
                    subject_avg = marks_df.groupby("subject")["marks"].mean().to_dict()

                def get_priority(subject):
                    avg = subject_avg.get(subject, None)
                    if avg is None:
                        return 1, "default"   # no data → normal
                    elif avg < 50:
                        return 0, "critical"  # very weak
                    elif avg < 70:
                        return 1, "weak"      # below average
                    else:
                        return 2, "strong"    # doing well

                # Sort quizzes: weak subjects first, then strong
                quizzes_sorted = sorted(quizzes, key=lambda q: get_priority(q["subject"])[0])

                # Determine how many quizzes to show per subject
                # Weak subjects: show all; Strong subjects: show up to 1
                subject_quiz_count = {}
                for qz in quizzes_sorted:
                    subj = qz["subject"]
                    subject_quiz_count[subj] = subject_quiz_count.get(subj, 0) + 1

                subject_shown = {}

                # --- Summary banner ---
                if subject_avg:
                    weak_list = [s for s, a in subject_avg.items() if a < 50]
                    avg_list  = [s for s, a in subject_avg.items() if 50 <= a < 70]
                    strong_list = [s for s, a in subject_avg.items() if a >= 70]
                    summary_parts = []
                    if weak_list:
                        summary_parts.append(f"🔴 <strong>Critical:</strong> {', '.join(weak_list)}")
                    if avg_list:
                        summary_parts.append(f"🟡 <strong>Needs Practice:</strong> {', '.join(avg_list)}")
                    if strong_list:
                        summary_parts.append(f"🟢 <strong>Strong:</strong> {', '.join(strong_list)}")
                    if summary_parts:
                        st.markdown(
                            f"<div class='insight-box'>📊 <strong>Quiz Priority based on your marks:</strong><br>"
                            + "<br>".join(summary_parts) +
                            "<br><span style='font-size:0.8rem;color:#64748b;'>Weak subjects are shown first with more quizzes.</span></div>",
                            unsafe_allow_html=True
                        )

                current_group = None
                for qz in quizzes_sorted:
                    subj = qz["subject"]
                    priority_rank, priority_level = get_priority(subj)

                    # Limit strong-subject quizzes to 1 each
                    subject_shown[subj] = subject_shown.get(subj, 0)
                    if priority_level == "strong" and subject_shown[subj] >= 1:
                        continue
                    subject_shown[subj] += 1

                    # Section group header when subject changes
                    if subj != current_group:
                        current_group = subj
                        avg_val = subject_avg.get(subj, None)
                        if priority_level == "critical":
                            color = "#ef4444"
                            tag = f"🔴 CRITICAL — Avg: {round(avg_val,1)}%"
                        elif priority_level == "weak":
                            color = "#f59e0b"
                            tag = f"🟡 NEEDS PRACTICE — Avg: {round(avg_val,1)}%"
                        elif priority_level == "strong":
                            color = "#22c55e"
                            tag = f"🟢 STRONG — Avg: {round(avg_val,1)}%"
                        else:
                            color = "#00d4ff"
                            tag = "🔵 NO DATA YET"
                        st.markdown(
                            f"<div style='margin:20px 0 6px 0;padding:8px 14px;"
                            f"background:#0d1b2e;border-left:4px solid {color};"
                            f"border-radius:8px;font-family:Space Mono;font-size:0.75rem;"
                            f"color:{color};letter-spacing:1px;'>"
                            f"📚 {subj.upper()}  &nbsp;|&nbsp; {tag}</div>",
                            unsafe_allow_html=True
                        )

                    already_taken = quiz_results_col.find_one({"student": user, "quiz_id": str(qz["_id"])})
                    with st.expander(f"📝 {qz['title']}  |  {qz['subject']}  |  {len(qz['questions'])} Questions"):
                        col1, col2 = st.columns(2)
                        col1.markdown(f"**Subject:** {qz['subject']}")
                        col1.markdown(f"**Questions:** {len(qz['questions'])}")
                        col2.markdown(f"**Created:** {qz.get('created_at', 'N/A')}")
                        avg_val = subject_avg.get(subj, None)
                        if avg_val is not None:
                            col2.markdown(f"**Your Avg in {subj}:** {round(avg_val,1)}%")
                        if already_taken:
                            score_pct = round(already_taken["score"] / already_taken["total"] * 100, 1)
                            col2.markdown(f"**Your Score:** {already_taken['score']}/{already_taken['total']} ({score_pct}%)")
                            st.markdown("<span class='badge-green'>✅ Completed</span>", unsafe_allow_html=True)
                            if st.button(f"Retake: {qz['title']}", key=f"retake_{str(qz['_id'])}"):
                                st.session_state.quiz_state = {"quiz": qz, "current_q": 0, "answers": {}, "submitted": False, "score": 0}
                                st.rerun()
                        else:
                            if priority_level == "critical":
                                st.markdown("<span class='badge' style='background:#2d0d0d;color:#ef4444;border:1px solid #ef444444;padding:3px 10px;border-radius:20px;font-size:0.75rem;font-family:Space Mono;'>🔴 HIGH PRIORITY</span>", unsafe_allow_html=True)
                            elif priority_level == "weak":
                                st.markdown("<span class='badge' style='background:#2d1a0a;color:#f59e0b;border:1px solid #f59e0b44;padding:3px 10px;border-radius:20px;font-size:0.75rem;font-family:Space Mono;'>🟡 RECOMMENDED</span>", unsafe_allow_html=True)
                            else:
                                st.markdown("<span class='badge-blue'>🆕 New</span>", unsafe_allow_html=True)
                            if st.button(f"Start: {qz['title']}", key=f"start_{str(qz['_id'])}"):
                                st.session_state.quiz_state = {"quiz": qz, "current_q": 0, "answers": {}, "submitted": False, "score": 0}
                                st.rerun()
            else:
                qs = st.session_state.quiz_state
                qz = qs["quiz"]
                questions = qz["questions"]
                total_q = len(questions)

                if not qs["submitted"]:
                    st.markdown(f"<div class='section-header'>{qz['title']} — {qz['subject']}</div>", unsafe_allow_html=True)
                    progress_val = len(qs["answers"]) / total_q * 100
                    st.markdown(f"<div style='display:flex;justify-content:space-between;margin-bottom:4px;'><span style='font-size:0.8rem;color:#64748b;'>Progress</span><span style='font-family:Space Mono;font-size:0.8rem;'>{len(qs['answers'])}/{total_q}</span></div>", unsafe_allow_html=True)
                    st.markdown(progress_bar(progress_val), unsafe_allow_html=True)

                    for i, q in enumerate(questions):
                        st.markdown(f"<div style='margin:20px 0 8px 0;'><strong>Q{i+1}.</strong> {q['question']}</div>", unsafe_allow_html=True)
                        selected = st.radio(
                            f"Q{i+1}",
                            options=list(q["options"].keys()),
                            format_func=lambda opt, q=q: f"{opt}: {q['options'][opt]}",
                            key=f"q_{i}",
                            label_visibility="collapsed"
                        )
                        qs["answers"][i] = selected

                    st.markdown("<br>", unsafe_allow_html=True)
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        if st.button("Cancel"):
                            del st.session_state["quiz_state"]
                            st.rerun()
                    with col2:
                        if st.button("Submit Quiz", use_container_width=True):
                            score = sum(1 for i, q in enumerate(questions) if qs["answers"].get(i) == q["correct"])
                            qs["score"] = score
                            qs["submitted"] = True
                            quiz_results_col.insert_one({
                                "student": user,
                                "quiz_id": str(qz["_id"]),
                                "quiz_title": qz["title"],
                                "subject": qz["subject"],
                                "score": score,
                                "total": total_q,
                                "answers": qs["answers"],
                                "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                            })
                            st.rerun()
                else:
                    score = qs["score"]
                    pct = round(score / total_q * 100, 1)
                    grade, gcolor = get_grade(pct)
                    st.markdown(f"""
                    <div style='text-align:center;padding:40px;background:linear-gradient(135deg,#0d1b2e,#112240);border-radius:20px;border:1px solid #1e3a5f;margin-bottom:24px;'>
                        <div style='font-family:Space Mono;font-size:3rem;color:{gcolor};'>{grade}</div>
                        <div style='font-size:1.5rem;font-weight:600;margin:8px 0;'>{score} / {total_q} correct</div>
                        <div style='font-size:2rem;font-family:Space Mono;color:#00d4ff;'>{pct}%</div>
                        <div style='color:#64748b;margin-top:8px;'>{qz["title"]} — {qz["subject"]}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.markdown("<div class='section-header'>Answer Review</div>", unsafe_allow_html=True)
                    for i, q in enumerate(questions):
                        user_ans = qs["answers"].get(i, "?")
                        correct_ans = q["correct"]
                        is_correct = user_ans == correct_ans
                        icon = "✅" if is_correct else "❌"
                        bg = "#0d2d1a" if is_correct else "#2d0d0d"
                        bc = "#22c55e" if is_correct else "#ef4444"
                        correct_line = "" if is_correct else f"<div style='color:#22c55e;margin-top:4px;'>Correct: {correct_ans}: {q['options'].get(correct_ans,'')}</div>"
                        st.markdown(f"""
                        <div style='background:{bg};border:1px solid {bc}44;border-radius:10px;padding:14px;margin:8px 0;'>
                            <div><strong>Q{i+1}:</strong> {q['question']}</div>
                            <div style='margin-top:6px;'>Your answer: <span style='color:{bc};font-family:Space Mono;'>{user_ans}: {q['options'].get(user_ans,'')}</span>  {icon}</div>
                            {correct_line}
                        </div>
                        """, unsafe_allow_html=True)

                    if st.button("Back to Quizzes"):
                        del st.session_state["quiz_state"]
                        st.rerun()

    # ======== QUIZ HISTORY ========
    elif menu == "Quiz History":
        st.markdown("<h2>🏆 Quiz History</h2>", unsafe_allow_html=True)
        results = list(quiz_results_col.find({"student": user}))
        if results:
            df = pd.DataFrame(results)
            df["percentage"] = (df["score"] / df["total"] * 100).round(1)
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"<div class='kpi-card'><div class='kpi-value'>{len(df)}</div><div class='kpi-label'>Quizzes Taken</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='kpi-card'><div class='kpi-value'>{round(df['percentage'].mean(),1)}%</div><div class='kpi-label'>Avg Score</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='kpi-card'><div class='kpi-value'>{df['percentage'].max()}%</div><div class='kpi-label'>Best Score</div></div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("<div class='section-header'>Score Over Time</div>", unsafe_allow_html=True)
            st.line_chart(df.set_index("submitted_at")["percentage"])
            st.markdown("<div class='section-header'>All Results</div>", unsafe_allow_html=True)
            show = df[["quiz_title", "subject", "score", "total", "percentage", "submitted_at"]].rename(columns={
                "quiz_title": "Quiz", "subject": "Subject", "score": "Score",
                "total": "Total", "percentage": "Score %", "submitted_at": "Date"
            })
            st.dataframe(show, use_container_width=True)
            st.markdown("<div class='section-header'>Score by Subject</div>", unsafe_allow_html=True)
            if "subject" in df.columns:
                st.bar_chart(df.groupby("subject")["percentage"].mean())
        else:
            st.info("No quiz attempts yet.")

    # ======== MY TASKS ========
    elif menu == "My Tasks":
        st.markdown("<h2>✅ My Tasks</h2>", unsafe_allow_html=True)
        tasks = list(tasks_col.find({"student": user}))
        if tasks:
            st.markdown(f"<div class='insight-box'>📌 You have <strong>{len(tasks)}</strong> task(s).</div>", unsafe_allow_html=True)
            for i, t in enumerate(tasks):
                assigned = f"<div style='font-size:0.75rem;color:#475569;margin-top:6px;'>Assigned: {t.get('assigned_at','N/A')}</div>" if t.get("assigned_at") else ""
                st.markdown(f"""
                <div style='background:#0d1b2e;border:1px solid #1e3a5f;border-left:3px solid #00d4ff;border-radius:10px;padding:14px 18px;margin:8px 0;'>
                    <div style='font-weight:600;'>Task {i+1}</div>
                    <div style='color:#94a3b8;margin-top:4px;'>{t['task']}</div>
                    {assigned}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No tasks assigned.")

    # ======== AI TUTOR ========
    elif menu == "AI Tutor":
        st.markdown("<h2>🤖 AI Study Tutor</h2>", unsafe_allow_html=True)
        data = list(marks_col.find({"username": user}))
        if data:
            df = pd.DataFrame(data)
            weak_subs = df[df["marks"] < 60]["subject"].unique()
            if len(weak_subs) > 0:
                st.markdown(f"<div class='insight-box warning'>💡 Based on your marks, ask about: <strong>{', '.join(weak_subs)}</strong></div>", unsafe_allow_html=True)

        if "chat" not in st.session_state:
            st.session_state.chat = []

        for sender, message in st.session_state.chat:
            if sender == "You":
                st.markdown(f"<div style='text-align:right;margin:8px 0;'><span style='background:#0a1f3a;border:1px solid #1e3a5f;padding:8px 14px;border-radius:12px 12px 2px 12px;display:inline-block;max-width:80%;'>{message}</span></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align:left;margin:8px 0;'><span style='background:#0d2d1a;border:1px solid #22c55e33;padding:8px 14px;border-radius:2px 12px 12px 12px;display:inline-block;max-width:80%;color:#d1fae5;'><strong>AI:</strong> {message}</span></div>", unsafe_allow_html=True)

        col1, col2 = st.columns([5, 1])
        with col1:
            msg = st.text_input("Ask anything...", label_visibility="collapsed", placeholder="e.g. Explain photosynthesis simply...")
        with col2:
            send = st.button("Send", use_container_width=True)

        if send and msg:
            try:
                res = client_groq.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are a helpful, concise student tutor. Explain concepts clearly."},
                        {"role": "user", "content": msg}
                    ]
                )
                reply = res.choices[0].message.content
            except Exception:
                reply = "AI service unavailable. Please check your API key."
            st.session_state.chat.append(("You", msg))
            st.session_state.chat.append(("AI", reply))
            st.rerun()

        if st.button("Clear Chat"):
            st.session_state.chat = []
            st.rerun()


# ============================================================
# ADMIN DASHBOARD
# ============================================================
def admin_dashboard():
    admin_user = st.session_state.user["username"]

    with st.sidebar:
        st.markdown(f"<div style='padding:16px 8px;'><div style='font-family:Space Mono;color:#ff6b6b;font-size:0.8rem;'>ADMIN</div><div style='font-size:1.1rem;font-weight:600;'>{admin_user}</div></div>", unsafe_allow_html=True)
        st.markdown("<hr style='border-color:#1e2d40;margin:0 0 12px 0;'>", unsafe_allow_html=True)

        if "admin_menu" not in st.session_state:
            st.session_state.admin_menu = "Dashboard"

        pages = [
            ("🏠", "Dashboard"),
            ("👤", "Add Student"),
            ("📋", "Manage Students"),
            ("📝", "Manage Quizzes"),
            ("📊", "Student Analytics"),
            ("🏆", "Quiz Performance"),
            ("📌", "Task Manager"),
            ("📧", "Email Settings"),
        ]
        for icon, label in pages:
            if st.button(f"{icon}  {label}", key=f"anav_{label}"):
                st.session_state.admin_menu = label

        st.markdown("<hr style='border-color:#1e2d40;'>", unsafe_allow_html=True)
        if st.button("Logout"):
            st.session_state.clear()
            st.session_state.page = "login"
            st.rerun()

    menu = st.session_state.admin_menu

    # ======== ADMIN DASHBOARD ========
    if menu == "Dashboard":
        st.markdown("<h2>🛠️ Admin Dashboard</h2>", unsafe_allow_html=True)
        total_students = users_col.count_documents({"role": "student"})
        total_quizzes = quizzes_col.count_documents({})
        total_marks = marks_col.count_documents({})
        total_quiz_results = quiz_results_col.count_documents({})
        total_tasks = tasks_col.count_documents({})

        # Clickable KPI cards — each navigates to the relevant page
        st.markdown("""
        <style>
        div[data-testid="stButton"] > button.kpi-nav-btn {
            background: linear-gradient(135deg, #0d1b2e 0%, #112240 100%) !important;
            border: 1px solid #1e3a5f !important;
            border-radius: 16px !important;
            padding: 24px 20px !important;
            text-align: center !important;
            width: 100% !important;
            height: 110px !important;
            cursor: pointer !important;
            transition: all 0.2s !important;
            position: relative !important;
            overflow: hidden !important;
        }
        div[data-testid="stButton"] > button.kpi-nav-btn:hover {
            border-color: #ff6b6b !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 8px 24px rgba(255,107,107,0.15) !important;
        }
        </style>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.markdown(f"""<div class='kpi-card admin' style='cursor:pointer;transition:all 0.2s;'>
                <div class='kpi-value'>{total_students}</div>
                <div class='kpi-label'>Students</div></div>""", unsafe_allow_html=True)
            if st.button("👥 View Students", key="dash_students", use_container_width=True):
                st.session_state.admin_menu = "Manage Students"
                st.rerun()
        with c2:
            st.markdown(f"""<div class='kpi-card admin' style='cursor:pointer;'>
                <div class='kpi-value'>{total_quizzes}</div>
                <div class='kpi-label'>Quizzes</div></div>""", unsafe_allow_html=True)
            if st.button("📝 View Quizzes", key="dash_quizzes", use_container_width=True):
                st.session_state.admin_menu = "Manage Quizzes"
                st.rerun()
        with c3:
            st.markdown(f"""<div class='kpi-card admin' style='cursor:pointer;'>
                <div class='kpi-value'>{total_marks}</div>
                <div class='kpi-label'>Mark Records</div></div>""", unsafe_allow_html=True)
            if st.button("📊 View Analytics", key="dash_marks", use_container_width=True):
                st.session_state.admin_menu = "Student Analytics"
                st.rerun()
        with c4:
            st.markdown(f"""<div class='kpi-card admin' style='cursor:pointer;'>
                <div class='kpi-value'>{total_quiz_results}</div>
                <div class='kpi-label'>Quiz Attempts</div></div>""", unsafe_allow_html=True)
            if st.button("🏆 Quiz Performance", key="dash_attempts", use_container_width=True):
                st.session_state.admin_menu = "Quiz Performance"
                st.rerun()
        with c5:
            st.markdown(f"""<div class='kpi-card admin' style='cursor:pointer;'>
                <div class='kpi-value'>{total_tasks}</div>
                <div class='kpi-label'>Tasks</div></div>""", unsafe_allow_html=True)
            if st.button("📌 View Tasks", key="dash_tasks", use_container_width=True):
                st.session_state.admin_menu = "Task Manager"
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("<div class='section-header'>Subject-wise Class Average</div>", unsafe_allow_html=True)
            all_marks = list(marks_col.find())
            if all_marks:
                df = pd.DataFrame(all_marks)
                st.bar_chart(df.groupby("subject")["marks"].mean())
            else:
                st.info("No marks data yet.")
        with col2:
            st.markdown("<div class='section-header'>Recent Quiz Submissions</div>", unsafe_allow_html=True)
            recent = list(quiz_results_col.find().sort("submitted_at", -1).limit(6))
            if recent:
                for r in recent:
                    pct = round(r["score"] / r["total"] * 100, 1)
                    g, gc = get_grade(pct)
                    st.markdown(f"<div style='display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #1e2d40;font-size:0.85rem;'><span>{r['student']} — {r['quiz_title']}</span><span style='color:{gc};font-family:Space Mono;'>{pct}%</span></div>", unsafe_allow_html=True)
            else:
                st.info("No quiz submissions yet.")
            if total_students > 0 and total_quizzes > 0:
                total_possible = total_students * total_quizzes
                completion_rate = round(total_quiz_results / total_possible * 100, 1)
                st.markdown(f"<br><div class='kpi-card'><div class='kpi-value'>{completion_rate}%</div><div class='kpi-label'>Quiz Completion Rate</div></div>", unsafe_allow_html=True)

    # ======== ADD STUDENT ========
    elif menu == "Add Student":
        st.markdown("<h2>👤 Add Student</h2>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("<div class='section-header'>Create Student Account</div>", unsafe_allow_html=True)
            with st.form("add_student_form"):
                new_u = st.text_input("Username")
                new_p = st.text_input("Password", type="password")
                new_e = st.text_input("Student Email", placeholder="student@email.com (for reminders)")
                if st.form_submit_button("Create Student"):
                    if new_u and new_p:
                        if do_register(new_u, new_p, "student", new_e):
                            st.success(f"✅ Student '{new_u}' created!")
                        else:
                            st.error("Username already exists.")
                    else:
                        st.warning("Fill all fields.")
        with col2:
            st.markdown("<div class='section-header'>Student Directory</div>", unsafe_allow_html=True)
            students = list(users_col.find({"role": "student"}))
            if students:
                for s in students:
                    sname = s["username"]
                    semail = s.get("email", "—")
                    mc = marks_col.count_documents({"username": sname})
                    st.markdown(f"<div style='display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #1e2d40;'><span>👤 {sname} <span style='color:#64748b;font-size:0.8rem;'>({semail})</span></span><span class='badge-blue'>{mc} records</span></div>", unsafe_allow_html=True)
            else:
                st.info("No students yet.")

    # ======== MANAGE STUDENTS ========
    elif menu == "Manage Students":
        st.markdown("<h2>📋 Manage Students</h2>", unsafe_allow_html=True)
        students = list(users_col.find({"role": "student"}))
        if students:
            student_stats = []
            for s in students:
                sname = s["username"]
                marks_data = list(marks_col.find({"username": sname}))
                quiz_data = list(quiz_results_col.find({"student": sname}))
                marks_avg = round(pd.DataFrame(marks_data)["marks"].mean(), 1) if marks_data else 0
                quiz_avg = round(sum(r["score"]/r["total"]*100 for r in quiz_data)/len(quiz_data), 1) if quiz_data else 0
                student_stats.append({"name": sname, "marks_avg": marks_avg, "quiz_avg": quiz_avg, "marks_data": marks_data, "quiz_data": quiz_data})

            st.markdown("<div class='section-header'>Leaderboard</div>", unsafe_allow_html=True)
            for rank, s in enumerate(sorted(student_stats, key=lambda x: x["marks_avg"], reverse=True)):
                medal = ["🥇","🥈","🥉"][rank] if rank < 3 else f"#{rank+1}"
                g, gc = get_grade(s["marks_avg"])
                st.markdown(f"<div style='display:flex;justify-content:space-between;align-items:center;padding:10px 16px;background:#0d1b2e;border-radius:10px;margin:4px 0;border:1px solid #1e3a5f;'><span>{medal} {s['name']}</span><span>Marks: <strong style='color:{gc};font-family:Space Mono;'>{s['marks_avg']}</strong> &nbsp; Quiz: <strong style='color:#00d4ff;font-family:Space Mono;'>{s['quiz_avg']}%</strong></span></div>", unsafe_allow_html=True)

            st.markdown("<div class='section-header'>Student Details</div>", unsafe_allow_html=True)
            for s in student_stats:
                sname = s["name"]
                g, gc = get_grade(s["marks_avg"])
                with st.expander(f"👤 {sname}  |  Marks Avg: {s['marks_avg']}  |  Quiz Avg: {s['quiz_avg']}%"):
                    c1, c2, c3 = st.columns(3)
                    c1.markdown(f"<div class='kpi-card'><div class='kpi-value' style='color:{gc};'>{s['marks_avg']}</div><div class='kpi-label'>Marks Avg</div></div>", unsafe_allow_html=True)
                    c2.markdown(f"<div class='kpi-card'><div class='kpi-value'>{s['quiz_avg']}%</div><div class='kpi-label'>Quiz Avg</div></div>", unsafe_allow_html=True)
                    c3.markdown(f"<div class='kpi-card'><div class='kpi-value'>{len(s['quiz_data'])}</div><div class='kpi-label'>Quizzes Taken</div></div>", unsafe_allow_html=True)
                    if s["marks_data"]:
                        st.markdown("<div class='section-header'>Marks</div>", unsafe_allow_html=True)
                        st.dataframe(pd.DataFrame(s["marks_data"])[["subject","marks"]], use_container_width=True)
                    if s["quiz_data"]:
                        st.markdown("<div class='section-header'>Quiz Results</div>", unsafe_allow_html=True)
                        df_q = pd.DataFrame(s["quiz_data"])[["quiz_title","score","total","submitted_at"]]
                        df_q["Score %"] = (df_q["score"] / df_q["total"] * 100).round(1)
                        st.dataframe(df_q, use_container_width=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(f"Delete {sname}", key=f"del_{sname}"):
                        users_col.delete_one({"username": sname})
                        marks_col.delete_many({"username": sname})
                        tasks_col.delete_many({"student": sname})
                        quiz_results_col.delete_many({"student": sname})
                        st.success(f"'{sname}' deleted.")
                        st.rerun()
        else:
            st.info("No students registered yet.")

    # ======== MANAGE QUIZZES ========
    elif menu == "Manage Quizzes":
        st.markdown("<h2>📝 Manage Quizzes</h2>", unsafe_allow_html=True)
        tab1, tab2, tab3 = st.tabs(["🤖 AI Auto-Generate", "✍️ Create Manually", "📋 All Quizzes"])

        # ---- TAB 1: AI AUTO-GENERATE ----
        with tab1:
            st.markdown("<div class='section-header'>AI Quiz Generator — Based on Student Marks</div>", unsafe_allow_html=True)

            # Analyse all marks to find weak subjects across all students
            all_marks = list(marks_col.find())
            if not all_marks:
                st.warning("⚠️ No marks data found. Add student marks first so AI can detect weak subjects.")
            else:
                marks_df = pd.DataFrame(all_marks)
                subject_class_avg = marks_df.groupby("subject")["marks"].mean().round(1).sort_values()

                # Show subject performance overview
                st.markdown("**📊 Class Subject Averages (determines quiz count per subject):**")
                for subj, avg in subject_class_avg.items():
                    if avg < 50:
                        color = "#ef4444"; tag = "🔴 Critical — 5 quizzes recommended"
                    elif avg < 70:
                        color = "#f59e0b"; tag = "🟡 Weak — 3 quizzes recommended"
                    else:
                        color = "#22c55e"; tag = "🟢 Strong — 1 quiz recommended"
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;align-items:center;"
                        f"padding:8px 12px;background:#0d1b2e;border-left:3px solid {color};"
                        f"border-radius:6px;margin:4px 0;font-size:0.88rem;'>"
                        f"<span><strong>{subj}</strong></span>"
                        f"<span style='color:{color};font-family:Space Mono;'>{avg}% &nbsp;|&nbsp; {tag}</span></div>",
                        unsafe_allow_html=True
                    )

                st.markdown("<br>", unsafe_allow_html=True)
                all_subjects = list(subject_class_avg.index)

                col1, col2 = st.columns(2)
                with col1:
                    gen_subject = st.selectbox("Select Subject to Generate Quiz For", all_subjects, key="gen_subj")
                with col2:
                    avg_for_subj = subject_class_avg.get(gen_subject, 75)
                    if avg_for_subj < 50:
                        default_q = 10
                    elif avg_for_subj < 70:
                        default_q = 7
                    else:
                        default_q = 5
                    gen_num_q = st.number_input("Number of Questions", min_value=3, max_value=15, value=default_q, key="gen_num_q",
                                                help="Auto-set based on weakness: Critical=10, Weak=7, Strong=5")

                gen_difficulty = st.select_slider(
                    "Difficulty Level",
                    options=["Easy", "Medium", "Hard"],
                    value="Hard" if avg_for_subj < 50 else ("Medium" if avg_for_subj < 70 else "Easy"),
                    key="gen_diff"
                )

                st.markdown(
                    f"<div class='insight-box'>🤖 AI will generate <strong>{gen_num_q} {gen_difficulty}</strong> "
                    f"MCQ questions on <strong>{gen_subject}</strong> "
                    f"(Class avg: <strong>{avg_for_subj}%</strong>)</div>",
                    unsafe_allow_html=True
                )

                if st.button("🚀 Generate Quiz with AI", use_container_width=True, key="ai_gen_btn"):
                    with st.spinner(f"AI is generating {gen_num_q} questions on {gen_subject}..."):
                        prompt = f"""Generate exactly {gen_num_q} multiple-choice quiz questions on the subject "{gen_subject}" at {gen_difficulty} difficulty level for students who are scoring poorly in this subject.

Return ONLY valid JSON in this exact format, nothing else:
{{
  "title": "A descriptive quiz title about {gen_subject}",
  "questions": [
    {{
      "question": "Question text here?",
      "options": {{"A": "option1", "B": "option2", "C": "option3", "D": "option4"}},
      "correct": "A"
    }}
  ]
}}

Rules:
- Generate exactly {gen_num_q} questions
- Each question must have exactly 4 options: A, B, C, D
- The "correct" field must be exactly one of: A, B, C, D
- Questions should test conceptual understanding, not just memorization
- Make distractors (wrong options) plausible to challenge weak students
- Return ONLY the JSON, no extra text or markdown"""

                        try:
                            res = client_groq.chat.completions.create(
                                model="llama-3.3-70b-versatile",
                                messages=[
                                    {"role": "system", "content": "You are an expert quiz generator. Always respond with valid JSON only."},
                                    {"role": "user", "content": prompt}
                                ],
                                temperature=0.7
                            )
                            raw = res.choices[0].message.content.strip()
                            # Strip markdown code fences if present
                            if raw.startswith("```"):
                                raw = raw.split("```")[1]
                                if raw.startswith("json"):
                                    raw = raw[4:]
                            import json
                            parsed = json.loads(raw.strip())
                            st.session_state["ai_generated_quiz"] = {
                                "title": parsed["title"],
                                "subject": gen_subject,
                                "questions": parsed["questions"]
                            }
                            st.success(f"✅ Generated {len(parsed['questions'])} questions! Review below and click Save.")
                        except Exception as e:
                            st.error(f"AI generation failed: {e}. Try again.")

                # Show preview + save button if quiz was generated
                if "ai_generated_quiz" in st.session_state:
                    gq = st.session_state["ai_generated_quiz"]
                    st.markdown(f"<div class='section-header'>Preview: {gq['title']}</div>", unsafe_allow_html=True)
                    for idx, q in enumerate(gq["questions"]):
                        with st.expander(f"Q{idx+1}: {q['question'][:80]}..."):
                            for opt, val in q["options"].items():
                                marker = "✅" if opt == q["correct"] else "  •"
                                st.markdown(f"&nbsp;&nbsp;&nbsp;{marker} **{opt}:** {val}")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 Save This Quiz to Database", use_container_width=True, key="save_ai_quiz"):
                            quizzes_col.insert_one({
                                "title": gq["title"],
                                "subject": gq["subject"],
                                "questions": gq["questions"],
                                "created_by": f"{admin_user} (AI)",
                                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "ai_generated": True
                            })
                            # Auto-send email reminders to all students with emails
                            sent, failed, errors = send_bulk_quiz_reminders(gq["title"], gq["subject"])
                            del st.session_state["ai_generated_quiz"]
                            st.success(f"✅ Quiz saved! Students will now see it in 'Take a Quiz'.")
                            if sent > 0:
                                st.info(f"📧 Email reminders sent to {sent} student(s)." + (f" ({failed} failed — see below)" if failed else ""))
                            if errors:
                                with st.expander("⚠️ Email errors"):
                                    for e in errors:
                                        st.error(e)
                            st.rerun()
                    with col2:
                        if st.button("🔄 Regenerate", use_container_width=True, key="regen_quiz"):
                            del st.session_state["ai_generated_quiz"]
                            st.rerun()

        # ---- TAB 2: MANUAL CREATE ----
        with tab2:
            quiz_title = st.text_input("Quiz Title")
            subject = st.text_input("Subject")
            num_q = st.number_input("Number of Questions", 1, 20, 3)
            questions = []
            for i in range(int(num_q)):
                st.markdown(f"<div class='section-header'>Question {i+1}</div>", unsafe_allow_html=True)
                q_text = st.text_input("Question", key=f"qt_{i}")
                c1, c2 = st.columns(2)
                with c1:
                    opt_a = st.text_input("Option A", key=f"oa_{i}")
                    opt_b = st.text_input("Option B", key=f"ob_{i}")
                with c2:
                    opt_c = st.text_input("Option C", key=f"oc_{i}")
                    opt_d = st.text_input("Option D", key=f"od_{i}")
                correct = st.selectbox("Correct Answer", ["A","B","C","D"], key=f"ca_{i}")
                questions.append({"question": q_text, "options": {"A": opt_a, "B": opt_b, "C": opt_c, "D": opt_d}, "correct": correct})

            if st.button("Save Quiz", use_container_width=True):
                if quiz_title and subject and all(q["question"] for q in questions):
                    quizzes_col.insert_one({
                        "title": quiz_title, "subject": subject,
                        "questions": questions, "created_by": admin_user,
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                    })
                    sent, failed, errors = send_bulk_quiz_reminders(quiz_title, subject)
                    st.success(f"Quiz '{quiz_title}' saved!")
                    if sent > 0:
                        st.info(f"📧 Email reminders sent to {sent} student(s)." + (f" ({failed} failed — see below)" if failed else ""))
                    if errors:
                        with st.expander("⚠️ Email errors"):
                            for e in errors:
                                st.error(e)
                else:
                    st.warning("Fill all fields.")

        # ---- TAB 3: ALL QUIZZES ----
        with tab3:
            quizzes = list(quizzes_col.find())
            if quizzes:
                for qz in quizzes:
                    results = list(quiz_results_col.find({"quiz_id": str(qz["_id"])}))
                    attempts = len(results)
                    avg_score = round(sum(r["score"]/r["total"]*100 for r in results)/len(results), 1) if results else 0
                    ai_tag = " 🤖" if qz.get("ai_generated") else ""
                    with st.expander(f"📝 {qz['title']}{ai_tag}  |  {qz['subject']}  |  {attempts} attempts  |  Avg: {avg_score}%"):
                        c1, c2, c3 = st.columns(3)
                        c1.markdown(f"<div class='kpi-card'><div class='kpi-value'>{len(qz['questions'])}</div><div class='kpi-label'>Questions</div></div>", unsafe_allow_html=True)
                        c2.markdown(f"<div class='kpi-card'><div class='kpi-value'>{attempts}</div><div class='kpi-label'>Attempts</div></div>", unsafe_allow_html=True)
                        c3.markdown(f"<div class='kpi-card'><div class='kpi-value'>{avg_score}%</div><div class='kpi-label'>Avg Score</div></div>", unsafe_allow_html=True)
                        for idx, q in enumerate(qz["questions"]):
                            st.markdown(f"**Q{idx+1}:** {q['question']}")
                            for opt, val in q["options"].items():
                                marker = "✅" if opt == q["correct"] else "  •"
                                st.markdown(f"&nbsp;&nbsp;&nbsp;{marker} **{opt}:** {val}")
                        if st.button("Delete Quiz", key=f"dq_{str(qz['_id'])}"):
                            quizzes_col.delete_one({"_id": qz["_id"]})
                            st.success("Quiz deleted.")
                            st.rerun()
                        if st.button("📧 Send Reminder to All Students", key=f"remind_{str(qz['_id'])}"):
                            sent, failed, errors = send_bulk_quiz_reminders(qz["title"], qz["subject"])
                            if sent > 0:
                                st.success(f"✅ Reminder sent to {sent} student(s)!" + (f" ({failed} failed)" if failed else ""))
                            elif failed > 0:
                                st.error(f"All {failed} email(s) failed to send.")
                            else:
                                st.warning("No students with registered emails found.")
                            if errors:
                                with st.expander("⚠️ See error details"):
                                    for e in errors:
                                        st.error(e)
            else:
                st.info("No quizzes yet. Use the AI Auto-Generate tab to create quizzes instantly!")

    # ======== STUDENT ANALYTICS ========
    elif menu == "Student Analytics":
        st.markdown("<h2>📊 Student Analytics</h2>", unsafe_allow_html=True)
        all_marks = list(marks_col.find())
        if all_marks:
            df = pd.DataFrame(all_marks)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<div class='section-header'>Class Average by Subject</div>", unsafe_allow_html=True)
                st.bar_chart(df.groupby("subject")["marks"].mean())
            with col2:
                st.markdown("<div class='section-header'>Per-Student Average</div>", unsafe_allow_html=True)
                st.bar_chart(df.groupby("username")["marks"].mean())

            st.markdown("<div class='section-header'>Grade Distribution</div>", unsafe_allow_html=True)
            student_avgs = df.groupby("username")["marks"].mean()
            grade_counts = {"A+(90+)": 0, "A(80-89)": 0, "B(70-79)": 0, "C(60-69)": 0, "D(50-59)": 0, "F(<50)": 0}
            for avg in student_avgs:
                if avg >= 90: grade_counts["A+(90+)"] += 1
                elif avg >= 80: grade_counts["A(80-89)"] += 1
                elif avg >= 70: grade_counts["B(70-79)"] += 1
                elif avg >= 60: grade_counts["C(60-69)"] += 1
                elif avg >= 50: grade_counts["D(50-59)"] += 1
                else: grade_counts["F(<50)"] += 1
            st.bar_chart(pd.DataFrame(list(grade_counts.items()), columns=["Grade","Students"]).set_index("Grade"))

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<div class='section-header'>Top 5 Students</div>", unsafe_allow_html=True)
                top5 = student_avgs.sort_values(ascending=False).head(5).reset_index()
                top5.columns = ["Student","Average"]
                top5["Average"] = top5["Average"].round(1)
                for i, row in top5.iterrows():
                    medal = ["🥇","🥈","🥉"][i] if i < 3 else "🎖️"
                    g, gc = get_grade(row["Average"])
                    st.markdown(f"<div style='display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #1e2d40;'><span>{medal} {row['Student']}</span><span style='color:{gc};font-family:Space Mono;'>{row['Average']}</span></div>", unsafe_allow_html=True)
            with col2:
                st.markdown("<div class='section-header'>At Risk (Avg < 50)</div>", unsafe_allow_html=True)
                weak = student_avgs[student_avgs < 50].reset_index()
                weak.columns = ["Student","Average"]
                if not weak.empty:
                    for _, row in weak.iterrows():
                        st.markdown(f"<div class='insight-box warning'>❌ {row['Student']} — {round(row['Average'],1)}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='insight-box'>✅ All students above 50!</div>", unsafe_allow_html=True)

            st.markdown("<div class='section-header'>Full Records</div>", unsafe_allow_html=True)
            st.dataframe(df[["username","subject","marks"]].rename(columns={"username":"Student","subject":"Subject","marks":"Marks"}), use_container_width=True)
        else:
            st.info("No marks data yet.")

    # ======== QUIZ PERFORMANCE ========
    elif menu == "Quiz Performance":
        st.markdown("<h2>🏆 Quiz Performance</h2>", unsafe_allow_html=True)
        all_results = list(quiz_results_col.find())
        if all_results:
            df = pd.DataFrame(all_results)
            df["percentage"] = (df["score"] / df["total"] * 100).round(1)

            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"<div class='kpi-card admin'><div class='kpi-value'>{len(df)}</div><div class='kpi-label'>Total Attempts</div></div>", unsafe_allow_html=True)
            c2.markdown(f"<div class='kpi-card admin'><div class='kpi-value'>{round(df['percentage'].mean(),1)}%</div><div class='kpi-label'>Class Avg</div></div>", unsafe_allow_html=True)
            c3.markdown(f"<div class='kpi-card admin'><div class='kpi-value'>{df['percentage'].max()}%</div><div class='kpi-label'>Highest</div></div>", unsafe_allow_html=True)
            c4.markdown(f"<div class='kpi-card admin'><div class='kpi-value'>{df['quiz_title'].nunique()}</div><div class='kpi-label'>Active Quizzes</div></div>", unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<div class='section-header'>Avg Score per Quiz</div>", unsafe_allow_html=True)
                st.bar_chart(df.groupby("quiz_title")["percentage"].mean())
            with col2:
                st.markdown("<div class='section-header'>Avg Score per Student</div>", unsafe_allow_html=True)
                st.bar_chart(df.groupby("student")["percentage"].mean())

            if "subject" in df.columns:
                st.markdown("<div class='section-header'>Subject-wise Quiz Performance</div>", unsafe_allow_html=True)
                st.bar_chart(df.groupby("subject")["percentage"].mean())

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<div class='section-header'>Top Quiz Performers</div>", unsafe_allow_html=True)
                top = df.groupby("student")["percentage"].mean().sort_values(ascending=False).head(5).reset_index()
                for i, row in top.iterrows():
                    medal = ["🥇","🥈","🥉"][i] if i < 3 else "🎖️"
                    g, gc = get_grade(row["percentage"])
                    st.markdown(f"<div style='display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #1e2d40;'><span>{medal} {row['student']}</span><span style='color:{gc};font-family:Space Mono;'>{row['percentage']}%</span></div>", unsafe_allow_html=True)
            with col2:
                st.markdown("<div class='section-header'>Struggling Students (< 50%)</div>", unsafe_allow_html=True)
                struggling = df.groupby("student")["percentage"].mean()
                struggling = struggling[struggling < 50].reset_index()
                if not struggling.empty:
                    for _, row in struggling.iterrows():
                        st.markdown(f"<div class='insight-box warning'>❌ {row['student']} — {round(row['percentage'],1)}%</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='insight-box'>✅ All students above 50%!</div>", unsafe_allow_html=True)

            st.markdown("<div class='section-header'>All Submissions</div>", unsafe_allow_html=True)
            disp_cols = [c for c in ["student","quiz_title","subject","score","total","percentage","submitted_at"] if c in df.columns]
            st.dataframe(df[disp_cols].rename(columns={"student":"Student","quiz_title":"Quiz","subject":"Subject","score":"Score","total":"Total","percentage":"Score %","submitted_at":"Date"}), use_container_width=True)
        else:
            st.info("No quiz results yet.")

    # ======== TASK MANAGER ========
    elif menu == "Task Manager":
        st.markdown("<h2>📌 Task Manager</h2>", unsafe_allow_html=True)
        students = [u["username"] for u in users_col.find({"role": "student"})]
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("<div class='section-header'>Assign New Task</div>", unsafe_allow_html=True)
            if students:
                with st.form("assign_form"):
                    sel_student = st.selectbox("Select Student", students)
                    task_text = st.text_area("Task Description")
                    if st.form_submit_button("Assign Task"):
                        if task_text:
                            tasks_col.insert_one({
                                "student": sel_student, "task": task_text,
                                "assigned_by": admin_user,
                                "assigned_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                            })
                            st.success(f"Task assigned to {sel_student}!")
                        else:
                            st.warning("Enter a task description.")
            else:
                st.info("No students available.")
        with col2:
            st.markdown("<div class='section-header'>All Assigned Tasks</div>", unsafe_allow_html=True)
            all_tasks = list(tasks_col.find())
            if all_tasks:
                for t in all_tasks:
                    st.markdown(f"""
                    <div style='background:#0d1b2e;border:1px solid #1e3a5f;border-left:3px solid #f59e0b;border-radius:10px;padding:12px 16px;margin:6px 0;'>
                        <div style='display:flex;justify-content:space-between;'><strong>{t['student']}</strong><span style='font-size:0.75rem;color:#64748b;'>{t.get('assigned_at','')}</span></div>
                        <div style='color:#94a3b8;margin-top:4px;font-size:0.88rem;'>{t['task']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No tasks assigned yet.")

    # ======== EMAIL SETTINGS ========
    elif menu == "Email Settings":
        st.markdown("<h2>📧 Email Settings</h2>", unsafe_allow_html=True)

        # ---- STEP 1: CREDENTIALS ----
        st.markdown("<div class='section-header'>Step 1 — Enter Gmail Credentials</div>", unsafe_allow_html=True)
        st.markdown("""
        <div class='insight-box'>
        <strong>How to get a Gmail App Password (takes 2 minutes):</strong><br><br>
        1. Open <a href='https://myaccount.google.com/security' target='_blank' style='color:#00d4ff;'>myaccount.google.com/security</a><br>
        2. Scroll to <strong>How you sign in to Google</strong> → click <strong>2-Step Verification</strong> and enable it<br>
        3. Go back to Security → scroll down → click <strong>App Passwords</strong><br>
        4. Under "Select app" choose <strong>Mail</strong>, click <strong>Generate</strong><br>
        5. Copy the <strong>16-character code</strong> (e.g. <code>abcd efgh ijkl mnop</code>) — paste it below without spaces
        </div>
        """, unsafe_allow_html=True)

        current_sender   = st.session_state.get("email_sender",   EMAIL_SENDER)
        current_password = st.session_state.get("email_password", EMAIL_PASSWORD)

        col1, col2 = st.columns(2)
        with col1:
            inp_sender = st.text_input("Your Gmail Address", value=current_sender, placeholder="yourname@gmail.com")
        with col2:
            inp_password = st.text_input("Gmail App Password (16 chars, no spaces)", value=current_password, type="password", placeholder="abcdefghijklmnop")

        if st.button("💾 Save Credentials", use_container_width=True):
            inp_password_clean = inp_password.replace(" ", "")
            if not inp_sender or "@" not in inp_sender:
                st.error("Enter a valid Gmail address.")
            elif len(inp_password_clean) != 16:
                st.error(f"App Password must be exactly 16 characters (you entered {len(inp_password_clean)}). Copy it directly from Google — no spaces.")
            else:
                st.session_state["email_sender"]   = inp_sender
                st.session_state["email_password"]  = inp_password_clean
                st.success("✅ Credentials saved for this session!")
                st.info("To make this permanent, create a file called `.env` in the same folder as app.py with:\n\n```\nEMAIL_SENDER=" + inp_sender + "\nEMAIL_PASSWORD=" + inp_password_clean + "\n```")

        # Show current status
        cred_ok = bool(st.session_state.get("email_sender") and st.session_state.get("email_password"))
        if cred_ok:
            st.markdown(f"<div class='insight-box'>✅ Credentials loaded: <strong>{st.session_state['email_sender']}</strong></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='insight-box warning'>⚠️ No credentials saved yet — emails will not send until you fill in Step 1 above.</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ---- STEP 2: TEST ----
        st.markdown("<div class='section-header'>Step 2 — Send a Test Email</div>", unsafe_allow_html=True)
        st.markdown("Send a test email to yourself first to confirm everything works before relying on reminders.")
        test_to = st.text_input("Send test to:", placeholder="youremail@gmail.com")
        if st.button("🧪 Send Test Email", use_container_width=True):
            if not test_to or "@" not in test_to:
                st.warning("Enter a valid email address.")
            else:
                with st.spinner("Sending..."):
                    ok, err = send_email(
                        test_to,
                        "[Study Planner] Test Email",
                        "<div style='font-family:Arial;padding:20px;'><h2 style='color:#0d1b2e;'>Test successful! ✅</h2><p>Your email reminder system is working correctly. Students will now receive quiz reminders.</p></div>"
                    )
                if ok:
                    st.success(f"✅ Test email sent to {test_to}! Check your inbox (and spam folder).")
                else:
                    st.error(f"❌ Failed: {err}")

        st.markdown("<br>", unsafe_allow_html=True)

        # ---- STEP 3: FIX MISSING STUDENT EMAILS ----
        st.markdown("<div class='section-header'>Step 3 — Fix Students Missing an Email</div>", unsafe_allow_html=True)

        all_students       = list(users_col.find({"role": "student"}))
        with_email         = [s for s in all_students if s.get("email", "").strip()]
        without_email      = [s for s in all_students if not s.get("email", "").strip()]

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='kpi-card'><div class='kpi-value'>{len(all_students)}</div><div class='kpi-label'>Total Students</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='kpi-card'><div class='kpi-value' style='color:#22c55e;'>{len(with_email)}</div><div class='kpi-label'>Have Email ✅</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='kpi-card admin'><div class='kpi-value'>{len(without_email)}</div><div class='kpi-label'>Missing Email ⚠️</div></div>", unsafe_allow_html=True)

        if without_email:
            st.markdown("**These students have no email — add one so they receive reminders:**")
            for s in without_email:
                col_name, col_input, col_btn = st.columns([2, 3, 1])
                col_name.markdown(f"<div style='padding-top:8px;'>👤 <strong>{s['username']}</strong></div>", unsafe_allow_html=True)
                new_email = col_input.text_input("", key=f"fix_{s['username']}", placeholder="student@example.com", label_visibility="collapsed")
                if col_btn.button("Save", key=f"saveemail_{s['username']}"):
                    if new_email and "@" in new_email:
                        users_col.update_one({"username": s["username"]}, {"$set": {"email": new_email}})
                        st.success(f"✅ Email saved for {s['username']}!")
                        st.rerun()
                    else:
                        st.warning("Enter a valid email.")
        else:
            st.markdown("<div class='insight-box'>✅ All students have an email address registered.</div>", unsafe_allow_html=True)

        if with_email:
            with st.expander(f"View {len(with_email)} student(s) with email"):
                for s in with_email:
                    st.markdown(f"<div style='padding:5px 0;border-bottom:1px solid #1e2d40;'>✅ <strong>{s['username']}</strong> — {s['email']}</div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ---- SEND BULK REMINDER NOW ----
        st.markdown("<div class='section-header'>Send Reminder for an Existing Quiz</div>", unsafe_allow_html=True)
        quizzes = list(quizzes_col.find())
        if quizzes:
            quiz_options = {f"{q['title']} ({q['subject']})": q for q in quizzes}
            selected_quiz_label = st.selectbox("Select quiz to remind students about:", list(quiz_options.keys()))
            if st.button("📧 Send Reminder to All Students Now", use_container_width=True):
                qz = quiz_options[selected_quiz_label]
                with st.spinner("Sending emails..."):
                    sent, failed, errors = send_bulk_quiz_reminders(qz["title"], qz["subject"])
                if sent > 0:
                    st.success(f"✅ Reminder sent to {sent} student(s)!")
                if failed > 0:
                    st.error(f"❌ {failed} email(s) failed.")
                if errors:
                    with st.expander("See error details"):
                        for e in errors:
                            st.error(e)
                if sent == 0 and failed == 0:
                    st.warning("No students with registered emails found. Add emails in Step 3 above.")
        else:
            st.info("No quizzes created yet.")



# ============================================================
# ROUTER
# ============================================================
if st.session_state.page == "login":
    login_page()
elif st.session_state.page == "student":
    student_dashboard()
elif st.session_state.page == "admin":
    admin_dashboard()