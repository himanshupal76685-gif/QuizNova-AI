
import json, os, time, hashlib, hmac, secrets
import streamlit as st
from google import genai

DB_FILE = "database.json"
MODEL = "gemini-2.5-flash"

def load_data():
    if not os.path.exists(DB_FILE):
        return {"users": {}, "questions": [], "attempts": []}
    try:
        with open(DB_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for key, default in [("users", {}), ("questions", []), ("attempts", [])]:
            data.setdefault(key, default)
        return data
    except Exception:
        return {"users": {}, "questions": [], "attempts": []}

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def make_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200000).hex()
    return {"salt": salt, "hash": digest}

def check_password(password, stored):
    if isinstance(stored, str):  # compatibility with the old database
        return hmac.compare_digest(password, stored)
    try:
        return hmac.compare_digest(make_hash(password, stored["salt"])["hash"], stored["hash"])
    except Exception:
        return False

def ai_client():
    try:
        key = st.secrets.get("GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        return genai.Client(api_key=key) if key else None
    except Exception:
        return None

def logout():
    st.session_state.clear()
    st.rerun()

st.set_page_config(page_title="QuizNova AI", page_icon="🧠", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] {font-family:Inter,sans-serif;}
.stApp {background:linear-gradient(135deg,#f8faff,#eef2ff,#f8fafc);}
.block-container {max-width:1180px;padding-top:1.8rem;}
[data-testid="stSidebar"] {background:#111827;}
[data-testid="stSidebar"] * {color:#f9fafb!important;}
.hero {padding:1.7rem 2rem;border-radius:22px;color:white;background:linear-gradient(115deg,#4338ca,#7c3aed,#2563eb);margin-bottom:1.2rem;box-shadow:0 12px 30px #4338ca22;}
.hero h1 {color:white;margin:0;font-size:2.2rem;}
.hero p {color:#e0e7ff;margin:.4rem 0 0;}
.stButton>button {border:0;border-radius:10px;font-weight:700;min-height:2.6rem;background:linear-gradient(110deg,#4f46e5,#7c3aed);color:white;}
.stButton>button:hover {color:white;filter:brightness(1.08);border:0;}
div[data-testid="stMetric"] {background:white;border:1px solid #e5e7eb;border-radius:16px;padding:1rem;box-shadow:0 5px 18px #0f172a08;}
</style>
""", unsafe_allow_html=True)

def hero(title, subtitle):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)

st.session_state.setdefault("user", None)
st.session_state.setdefault("role", None)
st.session_state.setdefault("chat_history", [])

def auth_page():
    hero("🧠 QuizNova", "Learn smarter. Practice better. Improve with AI.")
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.markdown("## Your personal learning space")
        st.write("🎯 Topic-wise quizzes")
        st.write("🤖 AI hints and study tutor")
        st.write("📊 Score tracking and result review")
        st.write("🏆 Improve your skills one quiz at a time")
        st.info("New registrations create student accounts only.")
    with right:
        login, register = st.tabs(["🔐 Login", "✨ Register"])
        with login:
            st.subheader("Welcome back")
            username = st.text_input("Username", key="login_name")
            password = st.text_input("Password", type="password", key="login_password")
            if st.button("Login to QuizNova", use_container_width=True):
                data = load_data()
                record = data["users"].get(username)
                if record and check_password(password, record.get("password", "")):
                    if isinstance(record.get("password"), str):
                        record["password"] = make_hash(password)
                        save_data(data)
                    st.session_state.user = username
                    st.session_state.role = record.get("role", "student")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
        with register:
            new_user = st.text_input("Choose username", key="new_username")
            new_pass = st.text_input("Password (minimum 8 characters)", type="password", key="new_password")
            confirm = st.text_input("Confirm password", type="password", key="confirm_password")
            if st.button("Create account", use_container_width=True):
                data = load_data()
                if len(new_user.strip()) < 3:
                    st.warning("Username must have at least 3 characters.")
                elif len(new_pass) < 8:
                    st.warning("Password must have at least 8 characters.")
                elif new_pass != confirm:
                    st.warning("Passwords do not match.")
                elif new_user.strip() in data["users"]:
                    st.error("Username already exists.")
                else:
                    data["users"][new_user.strip()] = {"password": make_hash(new_pass), "role": "student"}
                    save_data(data)
                    st.success("Account created. Please log in.")

def admin_panel():
    data = load_data()
    hero("🛠️ Admin Studio", f"Welcome, {st.session_state.user} — manage your question bank.")
    students = sum(1 for u in data["users"].values() if u.get("role") == "student")
    c1, c2, c3 = st.columns(3)
    c1.metric("Question bank", len(data["questions"]))
    c2.metric("Student accounts", students)
    c3.metric("Quiz attempts", len(data["attempts"]))
    menu = st.sidebar.radio("ADMIN MENU", ["Overview", "Manage Questions", "Add Question", "🤖 AI Generator"])
    if menu == "Overview":
        st.subheader("Welcome to your admin workspace")
        st.write("Add questions manually or generate a set with Gemini AI.")
        if data["questions"]:
            st.write("**Available categories:** " + ", ".join(sorted({q.get("category", "General") for q in data["questions"]})))
        else:
            st.info("Add your first question from the sidebar.")
    elif menu == "Manage Questions":
        st.subheader("📚 Question bank")
        if not data["questions"]:
            st.info("No questions available.")
        for q in data["questions"]:
            with st.expander(f"{q.get('category','General')} · {q.get('question','Question')}"):
                st.write("**Options:** " + " | ".join(q.get("options", [])))
                st.success("Correct answer: " + q.get("answer", ""))
                if st.button("Delete", key=f"del_{q.get('id')}"):
                    data["questions"] = [x for x in data["questions"] if x.get("id") != q.get("id")]
                    save_data(data)
                    st.rerun()
    elif menu == "Add Question":
        st.subheader("➕ Add a question")
        with st.form("manual_question"):
            category = st.text_input("Category", placeholder="Python, Java, DBMS...")
            question = st.text_area("Question")
            options = [st.text_input(f"Option {i}") for i in range(1, 5)]
            correct = st.selectbox("Correct option", range(4), format_func=lambda i: f"Option {i+1}")
            submit = st.form_submit_button("Save question", use_container_width=True)
        if submit:
            if not category.strip() or not question.strip() or any(not x.strip() for x in options):
                st.warning("Please complete all fields.")
            else:
                data = load_data()
                new_id = max([q.get("id", 0) for q in data["questions"]], default=0) + 1
                data["questions"].append({"id": new_id, "category": category.strip(), "question": question.strip(),
                                          "options": options, "answer": options[correct]})
                save_data(data)
                st.success("Question saved.")
    else:
        st.subheader("🤖 AI Question Generator")
        with st.form("ai_generator"):
            topic = st.text_input("Topic", placeholder="Python, DBMS, Computer Networks...")
            level = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"])
            number = st.slider("Number of questions", 1, 10, 5)
            generate = st.form_submit_button("Generate questions", use_container_width=True)
        if generate:
            client = ai_client()
            if not topic.strip():
                st.warning("Enter a topic.")
            elif not client:
                st.error("Gemini API key missing. Configure GEMINI_API_KEY in Streamlit Secrets.")
            else:
                try:
                    prompt = (
                        f"Create {number} {level} MCQs about {topic}. Return only a JSON array. "
                        "Each object must contain question, options (exactly 4 strings), answer (exact match), "
                        "and explanation (short string). No markdown fences."
                    )
                    response = client.models.generate_content(model=MODEL, contents=prompt)
                    raw = (response.text or "").strip()
                    if raw.startswith("```"):
                        raw = raw.split("```", 2)[1]
                        if raw.lower().startswith("json"):
                            raw = raw[4:]
                    items = json.loads(raw.strip())
                    valid = [x for x in items if x.get("question") and len(x.get("options", [])) == 4 and x.get("answer") in x.get("options", [])]
                    if not valid:
                        st.error("No valid questions returned; please try again.")
                    else:
                        st.session_state["ai_preview"] = {"topic": topic.strip(), "items": valid}
                        st.success(f"{len(valid)} questions generated. Review before saving.")
                except Exception as e:
                    st.error(f"AI generation failed: {e}")
        preview = st.session_state.get("ai_preview")
        if preview:
            for i, q in enumerate(preview["items"], 1):
                with st.expander(f"Q{i}. {q['question']}"):
                    st.write(" | ".join(q["options"]))
                    st.write("**Answer:** " + q["answer"])
                    st.caption(q.get("explanation", ""))
            if st.button("✅ Save generated questions", use_container_width=True):
                data = load_data()
                for q in preview["items"]:
                    new_id = max([x.get("id", 0) for x in data["questions"]], default=0) + 1
                    data["questions"].append({"id": new_id, "category": preview["topic"], **q})
                save_data(data)
                del st.session_state["ai_preview"]
                st.success("Questions saved.")
                st.rerun()
    if st.sidebar.button("Logout"):
        logout()

def student_panel():
    data = load_data()
    username = st.session_state.user
    attempts = [a for a in data["attempts"] if a.get("username") == username]
    hero("🎓 Student Learning Hub", f"Welcome back, {username}! Ready to learn something new?")
    menu = st.sidebar.radio("STUDENT MENU", ["Dashboard", "Take a Quiz", "🤖 AI Tutor", "My Results"])
    if menu == "Dashboard":
        average = round(sum(a.get("percentage", 0) for a in attempts) / len(attempts), 1) if attempts else 0
        best = max([a.get("percentage", 0) for a in attempts], default=0)
        a, b, c = st.columns(3)
        a.metric("Quizzes completed", len(attempts))
        b.metric("Average score", f"{average}%")
        c.metric("Personal best", f"{best}%")
        st.markdown("### ✨ Your learning space")
        x, y = st.columns(2)
        x.info("🎯 **Take a Quiz** — practise your subject knowledge.")
        y.info("🤖 **AI Tutor** — ask questions and learn concepts.")
        if not attempts:
            st.caption("Your progress appears here after your first quiz.")
    elif menu == "Take a Quiz":
        questions = data["questions"]
        if not questions:
            st.warning("No quiz available yet. Ask the admin to add questions.")
        else:
            categories = sorted({q.get("category", "General") for q in questions})
            category = st.selectbox("Choose subject", categories)
            available = [q for q in questions if q.get("category", "General") == category]
            count = st.select_slider("Number of questions", options=list(range(1, min(10, len(available)) + 1)), value=min(5, len(available)))
            if st.button("🚀 Start quiz", use_container_width=True):
                pool = available[:]
                secrets.SystemRandom().shuffle(pool)
                st.session_state.active_quiz = pool[:count]
                st.session_state.quiz_answers = {}
                st.session_state.quiz_index = 0
                st.session_state.quiz_submitted = False
                st.session_state.quiz_started = time.time()
                st.session_state.pop("attempt_saved", None)
                st.rerun()
            if st.session_state.get("active_quiz"):
                quiz = st.session_state.active_quiz
                if not st.session_state.get("quiz_submitted"):
                    idx = st.session_state.quiz_index
                    q = quiz[idx]
                    st.progress((idx + 1) / len(quiz), text=f"Question {idx+1} of {len(quiz)}")
                    st.markdown(f"### {q['question']}")
                    options = q.get("options", [])
                    previous = st.session_state.quiz_answers.get(str(q["id"]))
                    selected = st.radio("Choose an answer", options, index=options.index(previous) if previous in options else None, key=f"ans_{q['id']}")
                    st.session_state.quiz_answers[str(q["id"])] = selected
                    with st.expander("💡 Get an AI hint"):
                        if st.button("Get hint", key=f"hint_{q['id']}"):
                            client = ai_client()
                            if not client:
                                st.error("Gemini API key missing in Streamlit Secrets.")
                            else:
                                try:
                                    hint = client.models.generate_content(model=MODEL, contents=f"Give a subtle hint, not the answer, for this question: {q['question']}; options: {options}")
                                    st.info(hint.text or "No hint available.")
                                except Exception as e:
                                    st.error(f"Hint error: {e}")
                    p, n = st.columns(2)
                    with p:
                        if idx > 0 and st.button("⬅️ Previous"):
                            st.session_state.quiz_index -= 1
                            st.rerun()
                    with n:
                        if idx < len(quiz) - 1:
                            if st.button("Next ➡️"):
                                st.session_state.quiz_index += 1
                                st.rerun()
                        elif st.button("✅ Submit quiz"):
                            st.session_state.quiz_submitted = True
                            st.rerun()
                else:
                    score = sum(1 for q in quiz if st.session_state.quiz_answers.get(str(q["id"])) == q.get("answer"))
                    total = len(quiz)
                    pct = round(score / total * 100, 1)
                    elapsed = int(time.time() - st.session_state.quiz_started)
                    st.markdown("## 📊 Quiz result")
                    a, b, c = st.columns(3)
                    a.metric("Score", f"{score}/{total}")
                    b.metric("Percentage", f"{pct}%")
                    c.metric("Time taken", f"{elapsed//60}m {elapsed%60}s")
                    st.progress(pct / 100)
                    st.success("Well done! Keep learning.") if pct >= 50 else st.warning("Keep practising—you can improve!")
                    wrong = []
                    for q in quiz:
                        user_answer = st.session_state.quiz_answers.get(str(q["id"]), "Not answered")
                        correct = user_answer == q.get("answer")
                        with st.expander(("✅ " if correct else "❌ ") + q["question"]):
                            st.write("Your answer: " + user_answer)
                            st.write("Correct answer: " + q.get("answer", ""))
                            if q.get("explanation"):
                                st.info(q["explanation"])
                            if not correct:
                                wrong.append(q["question"])
                    if not st.session_state.get("attempt_saved"):
                        latest = load_data()
                        latest["attempts"].append({"username": username, "category": quiz[0].get("category", "General"),
                                                   "score": score, "total": total, "percentage": pct,
                                                   "timestamp": time.strftime("%Y-%m-%d %H:%M")})
                        save_data(latest)
                        st.session_state.attempt_saved = True
                    if st.button("🤖 Get AI improvement tips"):
                        client = ai_client()
                        if not client:
                            st.error("Gemini API key missing in Streamlit Secrets.")
                        else:
                            try:
                                result = client.models.generate_content(model=MODEL, contents=f"Student scored {score}/{total} ({pct}%) in {quiz[0].get('category')}. Wrong questions: {wrong}. Give 3 short practical improvement tips.")
                                st.info(result.text or "No feedback returned.")
                            except Exception as e:
                                st.error(f"Feedback error: {e}")
                    if st.button("Start another quiz", use_container_width=True):
                        for key in ["active_quiz", "quiz_answers", "quiz_index", "quiz_submitted", "quiz_started", "attempt_saved"]:
                            st.session_state.pop(key, None)
                        st.rerun()
    elif menu == "🤖 AI Tutor":
        st.subheader("💬 Your AI study partner")
        st.caption("Ask about Python, Java, DBMS, networking, maths, or any subject.")
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        query = st.chat_input("Ask your question...")
        if query:
            st.session_state.chat_history.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)
            client = ai_client()
            if not client:
                st.error("Gemini API key missing. Configure GEMINI_API_KEY in Streamlit Secrets.")
            else:
                with st.chat_message("assistant"):
                    with st.spinner("AI Tutor is thinking..."):
                        try:
                            recent = st.session_state.chat_history[-8:]
                            context = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
                            response = client.models.generate_content(model=MODEL, contents="You are a friendly tutor. Explain simply with examples and use the student's language.\n" + context)
                            reply = response.text or "Sorry, no response was generated."
                            st.markdown(reply)
                            st.session_state.chat_history.append({"role": "assistant", "content": reply})
                        except Exception as e:
                            st.error(f"Tutor error: {e}")
        if st.button("Clear chat"):
            st.session_state.chat_history = []
            st.rerun()
    else:
        st.subheader("📈 My quiz history")
        if not attempts:
            st.info("No quiz attempts yet.")
        else:
            st.dataframe([{"Subject": a.get("category"), "Score": f"{a.get('score')}/{a.get('total')}",
                           "Percentage": f"{a.get('percentage')}%", "Date": a.get("timestamp")} for a in reversed(attempts)],
                         use_container_width=True, hide_index=True)
            try:
                import pandas as pd
                chart = pd.DataFrame([{"Attempt": i+1, "Score (%)": a.get("percentage", 0)} for i, a in enumerate(attempts)])
                st.line_chart(chart.set_index("Attempt"))
            except Exception:
                pass
    if st.sidebar.button("Logout"):
        logout()

if st.session_state.user is None:
    auth_page()
elif st.session_state.role == "admin":
    admin_panel()
else:
    student_panel()
