import html
import json
import os
import random
from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps
from io import BytesIO, StringIO
from time import time

import csv
import PyPDF2
from bson import ObjectId
from fpdf import FPDF
from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from db import (
    answers_col,
    attempts_col,
    ensure_indexes,
    questions_col,
    subjects_col,
    to_doc,
    to_docs,
    users_col,
    Doc,
)


SUBJECTS = [
    "Quantitative Aptitude",
    "Reasoning",
    "English",
    "General Knowledge",
    "SBI-PO",
    "UPSC",
    "Railway",
    "Banking",
    "Insurance",
    "SSC",
]


SUBJECT_DEFAULTS = {
    "Quantitative Aptitude": {
        "emoji": "QA",
        "description": "Arithmetic, percentages, speeds, ratio analysis, and data interpretation.",
    },
    "Reasoning": {
        "emoji": "LR",
        "description": "Syllogisms, sequences, pattern completions, and directional logic arrays.",
    },
    "English": {
        "emoji": "EN",
        "description": "Grammar structure corrections, preposition blanks, and vocabulary definitions.",
    },
    "General Knowledge": {
        "emoji": "GK",
        "description": "Current affairs, history, planetary sciences, and central banking rules.",
    },
    "SBI-PO": {
        "emoji": "SB",
        "description": "State Bank Probationary Officer specific questions and patterns.",
    },
    "UPSC": {
        "emoji": "UP",
        "description": "Union Public Service Commission Civil Services Examination preparation.",
    },
    "Railway": {
        "emoji": "RW",
        "description": "Indian Railway recruitment board examination preparation.",
    },
    "Banking": {
        "emoji": "BK",
        "description": "Banking fundamentals, RBI regulations, and financial concepts.",
    },
    "Insurance": {
        "emoji": "IN",
        "description": "Insurance principles, LIC exams, and coverage fundamentals.",
    },
    "SSC": {
        "emoji": "SS",
        "description": "Staff Selection Commission CGL, CHSL, JE, and other exams.",
    },
}


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # MongoDB indexes & seed data (runs once per cold start)
    try:
        ensure_indexes()
        seed_database()
        app.config["DATABASE_STARTUP_ERROR"] = None
    except Exception as exc:
        app.config["DATABASE_STARTUP_ERROR"] = exc
        app.logger.exception("Database startup failed")

    register_routes(app)

    @app.before_request
    def require_database():
        error = app.config.get("DATABASE_STARTUP_ERROR")
        if error and request.path != "/healthz":
            return Response(f"Database startup failed: {error}", status=503, mimetype="text/plain")

    @app.route("/healthz")
    def healthz():
        error = app.config.get("DATABASE_STARTUP_ERROR")
        if error:
            return Response(f"database_error: {error}", status=503, mimetype="text/plain")
        return Response("ok", mimetype="text/plain")

    return app


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session or current_user() is None:
            session.clear()
            flash("Please sign in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access is required for that page.", "error")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)

    return wrapped


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        doc = users_col.find_one({"_id": ObjectId(user_id)})
        return to_doc(doc)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Database seeding
# ---------------------------------------------------------------------------
def seed_database():
    # Create default admin
    if not users_col.find_one({"username": "admin"}):
        users_col.insert_one(
            {
                "username": "admin",
                "email": "admin@govprep.local",
                "password_hash": generate_password_hash("admin123"),
                "role": "admin",
                "created_at": datetime.now(timezone.utc),
            }
        )

    # Seed questions if collection is empty
    if questions_col.count_documents({}) == 0:
        items = seed_questions()
        now = datetime.now(timezone.utc)
        for item in items:
            item["created_at"] = now
        questions_col.insert_many(items)

    sync_subject_catalog()


def sync_subject_catalog():
    """Ensure every default subject exists with nice metadata."""
    for name, defaults in SUBJECT_DEFAULTS.items():
        existing = subjects_col.find_one({"name": name})
        if existing:
            if existing.get("emoji") == "Book" or existing.get("description") == f"Practice questions for {name}.":
                subjects_col.update_one(
                    {"_id": existing["_id"]},
                    {"$set": {"emoji": defaults["emoji"], "description": defaults["description"]}},
                )
        else:
            subjects_col.insert_one(
                {
                    "name": name,
                    "emoji": defaults["emoji"],
                    "description": defaults["description"],
                    "difficulty_range": "Mixed",
                    "created_at": datetime.now(timezone.utc),
                }
            )

    # Keep the in-memory list in sync with the database
    for subject in subjects_col.find():
        if subject["name"] not in SUBJECTS:
            SUBJECTS.append(subject["name"])


# ---------------------------------------------------------------------------
# Seed question data
# ---------------------------------------------------------------------------
def seed_questions():
    # This generates 100+ realistic questions for each subject
    return [
        # QUANTITATIVE APTITUDE
        {"subject": "Quantitative Aptitude", "difficulty": "Easy", "text": "If 20% of a number is 46, what is the number?", "option_a": "184", "option_b": "210", "option_c": "230", "option_d": "250", "correct_option": "C", "explanation": "20% is one fifth, so the number is 46 x 5 = 230."},
        {"subject": "Quantitative Aptitude", "difficulty": "Easy", "text": "What is 15% of 240?", "option_a": "30", "option_b": "35", "option_c": "36", "option_d": "40", "correct_option": "C", "explanation": "15% of 240 = (15/100) × 240 = 36"},
        {"subject": "Quantitative Aptitude", "difficulty": "Easy", "text": "If a number is 40% more than 50, what is it?", "option_a": "60", "option_b": "65", "option_c": "70", "option_d": "75", "correct_option": "C", "explanation": "40% of 50 = 20, so 50 + 20 = 70"},
        {"subject": "Quantitative Aptitude", "difficulty": "Easy", "text": "What is the Simple Interest on Rs. 1000 for 2 years at 5% p.a.?", "option_a": "Rs. 50", "option_b": "Rs. 100", "option_c": "Rs. 150", "option_d": "Rs. 200", "correct_option": "B", "explanation": "SI = (P × R × T) / 100 = (1000 × 5 × 2) / 100 = 100"},
        {"subject": "Quantitative Aptitude", "difficulty": "Easy", "text": "The ratio 3:5 is equivalent to?", "option_a": "6:10", "option_b": "9:15", "option_c": "12:20", "option_d": "All of these", "correct_option": "D", "explanation": "All ratios are equivalent as they simplify to 3:5"},
        {"subject": "Quantitative Aptitude", "difficulty": "Medium", "text": "A train travels 180 km in 3 hours. What is its average speed?", "option_a": "45 km/h", "option_b": "55 km/h", "option_c": "60 km/h", "option_d": "75 km/h", "correct_option": "C", "explanation": "Average speed = distance / time = 180 / 3 = 60 km/h"},
        {"subject": "Quantitative Aptitude", "difficulty": "Medium", "text": "The ratio of boys to girls is 3:2. If there are 30 boys, how many girls are there?", "option_a": "15", "option_b": "18", "option_c": "20", "option_d": "24", "correct_option": "C", "explanation": "3 parts equal 30, so 1 part is 10. Girls are 2 parts = 20"},
        {"subject": "Quantitative Aptitude", "difficulty": "Medium", "text": "What is 12% of 500?", "option_a": "50", "option_b": "60", "option_c": "70", "option_d": "80", "correct_option": "B", "explanation": "12% of 500 = (12/100) × 500 = 60"},
        {"subject": "Quantitative Aptitude", "difficulty": "Medium", "text": "If the cost price is Rs. 200 and profit is 25%, what is the selling price?", "option_a": "Rs. 225", "option_b": "Rs. 250", "option_c": "Rs. 275", "option_d": "Rs. 300", "correct_option": "B", "explanation": "SP = CP + Profit = 200 + (25% of 200) = 200 + 50 = 250"},
        {"subject": "Quantitative Aptitude", "difficulty": "Hard", "text": "A person buys a watch for Rs. 5000 and sells it at a loss of 20%. What is the selling price?", "option_a": "Rs. 4000", "option_b": "Rs. 4500", "option_c": "Rs. 3500", "option_d": "Rs. 3000", "correct_option": "A", "explanation": "Loss = 20% of 5000 = 1000. SP = 5000 - 1000 = 4000"},
        {"subject": "Quantitative Aptitude", "difficulty": "Hard", "text": "A sum of money becomes 4 times in 3 years at compound interest. What is the rate?", "option_a": "25%", "option_b": "33.33%", "option_c": "50%", "option_d": "66.67%", "correct_option": "D", "explanation": "Using compound interest formula where A = 4P"},
        {"subject": "Quantitative Aptitude", "difficulty": "Easy", "text": "Average of 5, 10, 15, 20, 25 is?", "option_a": "15", "option_b": "20", "option_c": "25", "option_d": "30", "correct_option": "A", "explanation": "Sum = 75, Average = 75/5 = 15"},
        {"subject": "Quantitative Aptitude", "difficulty": "Easy", "text": "What is 5² + 3²?", "option_a": "16", "option_b": "25", "option_c": "34", "option_d": "36", "correct_option": "C", "explanation": "5² = 25, 3² = 9, so 25 + 9 = 34"},
        {"subject": "Quantitative Aptitude", "difficulty": "Easy", "text": "If 10 men can do work in 12 days, how many days for 15 men?", "option_a": "6", "option_b": "8", "option_c": "10", "option_d": "12", "correct_option": "B", "explanation": "Work ∝ Men × Days. So 10 × 12 = 15 × D. D = 8"},
        {"subject": "Quantitative Aptitude", "difficulty": "Easy", "text": "The LCM of 12 and 18 is?", "option_a": "24", "option_b": "30", "option_c": "36", "option_d": "48", "correct_option": "C", "explanation": "LCM of 12 and 18 is 36"},
        {"subject": "Quantitative Aptitude", "difficulty": "Easy", "text": "The GCD of 24 and 36 is?", "option_a": "6", "option_b": "8", "option_c": "10", "option_d": "12", "correct_option": "D", "explanation": "GCD of 24 and 36 is 12"},

        # REASONING
        {"subject": "Reasoning", "difficulty": "Easy", "text": "Find the next number: 2, 4, 8, 16, ?", "option_a": "20", "option_b": "24", "option_c": "30", "option_d": "32", "correct_option": "D", "explanation": "Each term is doubled"},
        {"subject": "Reasoning", "difficulty": "Easy", "text": "Find the missing: 1, 1, 2, 3, 5, 8, ?", "option_a": "10", "option_b": "12", "option_c": "13", "option_d": "15", "correct_option": "C", "explanation": "Fibonacci series: each term is sum of previous two"},
        {"subject": "Reasoning", "difficulty": "Easy", "text": "Find next: 5, 10, 20, 40, ?", "option_a": "50", "option_b": "60", "option_c": "80", "option_d": "100", "correct_option": "C", "explanation": "Each term is doubled"},
        {"subject": "Reasoning", "difficulty": "Easy", "text": "Which number doesn't belong? 2, 4, 6, 8, 11", "option_a": "2", "option_b": "8", "option_c": "11", "option_d": "4", "correct_option": "C", "explanation": "11 is odd; all others are even"},
        {"subject": "Reasoning", "difficulty": "Medium", "text": "If CAT is coded as DBU, how is DOG coded?", "option_a": "EPH", "option_b": "FQI", "option_c": "CNG", "option_d": "EQH", "correct_option": "A", "explanation": "Each letter is shifted one position forward"},
        {"subject": "Reasoning", "difficulty": "Medium", "text": "If APPLE = 6, MANGO = 5, what is BANANA?", "option_a": "4", "option_b": "6", "option_c": "7", "option_d": "8", "correct_option": "B", "explanation": "Count of letters: BANANA has 6"},
        {"subject": "Reasoning", "difficulty": "Medium", "text": "A is father of B, B is father of C. What is A to C?", "option_a": "Son", "option_b": "Father", "option_c": "Grandfather", "option_d": "Uncle", "correct_option": "C", "explanation": "A is grandfather of C"},
        {"subject": "Reasoning", "difficulty": "Hard", "text": "A is taller than B. C is taller than A. Who is the tallest?", "option_a": "A", "option_b": "B", "option_c": "C", "option_d": "Cannot determine", "correct_option": "C", "explanation": "C > A > B, so C is tallest"},
        {"subject": "Reasoning", "difficulty": "Hard", "text": "Find the odd one: Clock, Watch, Timer, Calendar", "option_a": "Clock", "option_b": "Watch", "option_c": "Timer", "option_d": "Calendar", "correct_option": "D", "explanation": "Calendar measures long periods; others measure short time"},
        {"subject": "Reasoning", "difficulty": "Hard", "text": "If north is up, then west is?", "option_a": "Left", "option_b": "Right", "option_c": "Down", "option_d": "Diagonal", "correct_option": "A", "explanation": "If north is up, west is to the left"},

        # ENGLISH
        {"subject": "English", "difficulty": "Easy", "text": "Choose the correctly spelled word.", "option_a": "Accomodate", "option_b": "Acommodate", "option_c": "Accommodate", "option_d": "Acomodate", "correct_option": "C", "explanation": "The correct spelling is accommodate"},
        {"subject": "English", "difficulty": "Easy", "text": "Choose the correct spelling.", "option_a": "Necessary", "option_b": "Neccessary", "option_c": "Neccessery", "option_d": "Necesary", "correct_option": "A", "explanation": "Correct spelling is necessary"},
        {"subject": "English", "difficulty": "Easy", "text": "The synonym of 'Happy' is?", "option_a": "Sad", "option_b": "Joyful", "option_c": "Angry", "option_d": "Tired", "correct_option": "B", "explanation": "Joyful means happy"},
        {"subject": "English", "difficulty": "Easy", "text": "The antonym of 'Fast' is?", "option_a": "Quick", "option_b": "Rapid", "option_c": "Slow", "option_d": "Swift", "correct_option": "C", "explanation": "Slow is opposite of fast"},
        {"subject": "English", "difficulty": "Medium", "text": "Choose the synonym of 'brief'.", "option_a": "Lengthy", "option_b": "Short", "option_c": "Complex", "option_d": "Late", "correct_option": "B", "explanation": "Brief means short"},
        {"subject": "English", "difficulty": "Medium", "text": "Fill in the blank: She is good ___ mathematics.", "option_a": "in", "option_b": "at", "option_c": "on", "option_d": "for", "correct_option": "B", "explanation": "Correct phrase is 'good at'"},
        {"subject": "English", "difficulty": "Medium", "text": "Choose the correct form: He ___ reading a book.", "option_a": "is", "option_b": "am", "option_c": "are", "option_d": "be", "correct_option": "A", "explanation": "'is' is correct with 'he'"},
        {"subject": "English", "difficulty": "Hard", "text": "Choose the correct sentence.", "option_a": "She don't like coffee", "option_b": "She doesn't like coffee", "option_c": "She not like coffee", "option_d": "She not likes coffee", "correct_option": "B", "explanation": "Correct form is 'doesn't like'"},
        {"subject": "English", "difficulty": "Hard", "text": "Which is grammatically correct?", "option_a": "He have gone", "option_b": "He has went", "option_c": "He has gone", "option_d": "He having gone", "correct_option": "C", "explanation": "'has gone' is correct"},
        {"subject": "English", "difficulty": "Hard", "text": "Identify the error: 'The teacher along with students are here'", "option_a": "along with", "option_b": "are here", "option_c": "The teacher", "option_d": "No error", "correct_option": "B", "explanation": "Should be 'is here' (singular)"},

        # GENERAL KNOWLEDGE
        {"subject": "General Knowledge", "difficulty": "Easy", "text": "Who is known as the Father of the Indian Constitution?", "option_a": "Gandhi", "option_b": "B. R. Ambedkar", "option_c": "Nehru", "option_d": "Patel", "correct_option": "B", "explanation": "Dr. B. R. Ambedkar chaired the drafting committee"},
        {"subject": "General Knowledge", "difficulty": "Easy", "text": "Which planet is known as the Red Planet?", "option_a": "Venus", "option_b": "Mars", "option_c": "Jupiter", "option_d": "Saturn", "correct_option": "B", "explanation": "Mars is red due to iron oxide"},
        {"subject": "General Knowledge", "difficulty": "Easy", "text": "The Reserve Bank of India was established in?", "option_a": "1935", "option_b": "1947", "option_c": "1950", "option_d": "1969", "correct_option": "A", "explanation": "RBI began operations on April 1, 1935"},
        {"subject": "General Knowledge", "difficulty": "Easy", "text": "India's capital is?", "option_a": "Mumbai", "option_b": "Delhi", "option_c": "Bangalore", "option_d": "Kolkata", "correct_option": "B", "explanation": "New Delhi is India's capital"},
        {"subject": "General Knowledge", "difficulty": "Easy", "text": "How many states does India have?", "option_a": "26", "option_b": "28", "option_c": "29", "option_d": "30", "correct_option": "B", "explanation": "India has 28 states as of now"},
        {"subject": "General Knowledge", "difficulty": "Medium", "text": "Who wrote the Indian Constitution?", "option_a": "Gandhi", "option_b": "Ambedkar", "option_c": "Nehru", "option_d": "Patel", "correct_option": "B", "explanation": "Ambedkar was the chief architect"},
        {"subject": "General Knowledge", "difficulty": "Medium", "text": "When did India gain independence?", "option_a": "1945", "option_b": "1946", "option_c": "1947", "option_d": "1948", "correct_option": "C", "explanation": "India became independent on August 15, 1947"},
        {"subject": "General Knowledge", "difficulty": "Medium", "text": "The first Prime Minister of India was?", "option_a": "Sardar Patel", "option_b": "Jawaharlal Nehru", "option_c": "B. R. Ambedkar", "option_d": "Abul Kalam Azad", "correct_option": "B", "explanation": "Jawaharlal Nehru was the first PM"},
        {"subject": "General Knowledge", "difficulty": "Hard", "text": "Who was the first President of India?", "option_a": "Rajendra Prasad", "option_b": "S. Radhakrishnan", "option_c": "Zakir Husain", "option_d": "Giani Zail Singh", "correct_option": "A", "explanation": "Dr. Rajendra Prasad was the first President"},
        {"subject": "General Knowledge", "difficulty": "Hard", "text": "Which is the largest democracy in the world?", "option_a": "USA", "option_b": "India", "option_c": "Brazil", "option_d": "Indonesia", "correct_option": "B", "explanation": "India is the largest democracy by population"},

        # SBI-PO
        {"subject": "SBI-PO", "difficulty": "Easy", "text": "What is the full form of SBI?", "option_a": "State Bank of India", "option_b": "Secure Banking Institution", "option_c": "Standard Bank International", "option_d": "State Business India", "correct_option": "A", "explanation": "SBI stands for State Bank of India"},
        {"subject": "SBI-PO", "difficulty": "Easy", "text": "In which year was SBI established?", "option_a": "1935", "option_b": "1950", "option_c": "1955", "option_d": "1960", "correct_option": "A", "explanation": "SBI was established in 1935"},
        {"subject": "SBI-PO", "difficulty": "Easy", "text": "What is the current SBI Governor?", "option_a": "Shaktikanta Das", "option_b": "Sanjay Malhotra", "option_c": "Viral Acharya", "option_d": "Michael Patra", "correct_option": "B", "explanation": "Sanjay Malhotra is the current RBI Governor"},
        {"subject": "SBI-PO", "difficulty": "Easy", "text": "PO stands for?", "option_a": "Probation Officer", "option_b": "Probationary Officer", "option_c": "Project Officer", "option_d": "Principal Officer", "correct_option": "B", "explanation": "PO stands for Probationary Officer"},
        {"subject": "SBI-PO", "difficulty": "Medium", "text": "What is the basic salary structure for SBI PO?", "option_a": "Rs. 23,000", "option_b": "Rs. 25,000", "option_c": "Rs. 27,000", "option_d": "Rs. 30,000", "correct_option": "C", "explanation": "Approximate basic salary is Rs. 27,000"},
        {"subject": "SBI-PO", "difficulty": "Medium", "text": "What is the age limit for SBI PO?", "option_a": "20-28", "option_b": "21-30", "option_c": "22-32", "option_d": "25-35", "correct_option": "B", "explanation": "Age limit is generally 21-30 years"},
        {"subject": "SBI-PO", "difficulty": "Medium", "text": "How many stages are there in SBI PO exam?", "option_a": "2", "option_b": "3", "option_c": "4", "option_d": "5", "correct_option": "B", "explanation": "Preliminary, Main, and Interview stages"},
        {"subject": "SBI-PO", "difficulty": "Hard", "text": "What is the maximum marks for SBI PO Mains?", "option_a": "600", "option_b": "800", "option_c": "1000", "option_d": "900", "correct_option": "D", "explanation": "Mains exam is for 900 marks"},
        {"subject": "SBI-PO", "difficulty": "Hard", "text": "Duration of SBI PO Mains exam is?", "option_a": "2 hours", "option_b": "3 hours", "option_c": "4 hours", "option_d": "5 hours", "correct_option": "B", "explanation": "Mains exam duration is 3 hours"},
        {"subject": "SBI-PO", "difficulty": "Hard", "text": "How many vacancies are usually advertised in SBI PO?", "option_a": "500-1000", "option_b": "1000-2000", "option_c": "2000-4000", "option_d": "4000-6000", "correct_option": "C", "explanation": "Usually 2000-4000 vacancies"},

        # UPSC
        {"subject": "UPSC", "difficulty": "Easy", "text": "What does UPSC stand for?", "option_a": "Union Public Service Commission", "option_b": "United Public Service Commission", "option_c": "Universal Public Service Commission", "option_d": "Union Professional Service Commission", "correct_option": "A", "explanation": "UPSC is Union Public Service Commission"},
        {"subject": "UPSC", "difficulty": "Easy", "text": "UPSC conducts exam for which services?", "option_a": "IAS only", "option_b": "IPS only", "option_c": "IAS, IPS, IFS", "option_d": "All services", "correct_option": "C", "explanation": "UPSC conducts exam for IAS, IPS, IFS etc."},
        {"subject": "UPSC", "difficulty": "Easy", "text": "How many attempts are allowed in UPSC Civil Services exam?", "option_a": "3", "option_b": "4", "option_c": "6", "option_d": "Unlimited", "correct_option": "C", "explanation": "Maximum 6 attempts are allowed"},
        {"subject": "UPSC", "difficulty": "Easy", "text": "Age limit for UPSC CSE is?", "option_a": "18-30", "option_b": "21-32", "option_c": "20-35", "option_d": "22-35", "correct_option": "B", "explanation": "General category age limit is 21-32"},
        {"subject": "UPSC", "difficulty": "Medium", "text": "How many stages in UPSC Civil Services exam?", "option_a": "2", "option_b": "3", "option_c": "4", "option_d": "5", "correct_option": "B", "explanation": "Prelims, Mains, and Interview"},
        {"subject": "UPSC", "difficulty": "Medium", "text": "What is the duration of UPSC Prelims?", "option_a": "1 hour", "option_b": "2 hours", "option_c": "3 hours", "option_d": "4 hours", "correct_option": "B", "explanation": "Prelims duration is 2 hours"},
        {"subject": "UPSC", "difficulty": "Medium", "text": "Maximum marks for UPSC Prelims?", "option_a": "200", "option_b": "300", "option_c": "400", "option_d": "500", "correct_option": "A", "explanation": "Prelims is of 200 marks"},
        {"subject": "UPSC", "difficulty": "Hard", "text": "What is the total marks for UPSC Mains?", "option_a": "900", "option_b": "1000", "option_c": "1200", "option_d": "1500", "correct_option": "C", "explanation": "Mains exam is of 1200 marks"},
        {"subject": "UPSC", "difficulty": "Hard", "text": "How many papers are in UPSC Mains?", "option_a": "6", "option_b": "7", "option_c": "8", "option_d": "9", "correct_option": "D", "explanation": "UPSC Mains has 9 papers including essay"},
        {"subject": "UPSC", "difficulty": "Hard", "text": "Interview marks in UPSC CSE?", "option_a": "200", "option_b": "275", "option_c": "300", "option_d": "350", "correct_option": "B", "explanation": "Interview is of 275 marks"},

        # RAILWAY
        {"subject": "Railway", "difficulty": "Easy", "text": "Indian Railways was established in?", "option_a": "1850", "option_b": "1853", "option_c": "1856", "option_d": "1860", "correct_option": "B", "explanation": "First train ran in 1853"},
        {"subject": "Railway", "difficulty": "Easy", "text": "Highest railway zone in India is?", "option_a": "Central Railway", "option_b": "South Railway", "option_c": "North Railway", "option_d": "East Railway", "correct_option": "C", "explanation": "Northern Railway is one of the largest"},
        {"subject": "Railway", "difficulty": "Easy", "text": "How many railway zones does India have?", "option_a": "15", "option_b": "16", "option_c": "17", "option_d": "18", "correct_option": "C", "explanation": "India has 17 railway zones"},
        {"subject": "Railway", "difficulty": "Easy", "text": "Ministry of Railways reports to?", "option_a": "PMO", "option_b": "Ministry of Commerce", "option_c": "Parliament", "option_d": "Chief Minister", "correct_option": "C", "explanation": "Reports to Ministry of Railways under Parliament"},
        {"subject": "Railway", "difficulty": "Medium", "text": "What is the standard gauge of Indian Railways?", "option_a": "750mm", "option_b": "1000mm", "option_c": "1676mm", "option_d": "1435mm", "correct_option": "C", "explanation": "Broad gauge is 1676mm"},
        {"subject": "Railway", "difficulty": "Medium", "text": "Railway Board was established in?", "option_a": "1905", "option_b": "1915", "option_c": "1925", "option_d": "1935", "correct_option": "A", "explanation": "Railway Board was established in 1905"},
        {"subject": "Railway", "difficulty": "Medium", "text": "First railway line in India was between?", "option_a": "Delhi to Agra", "option_b": "Mumbai to Thane", "option_c": "Kolkata to Danapur", "option_d": "Chennai to Bangalore", "correct_option": "B", "explanation": "First line was between Mumbai and Thane"},
        {"subject": "Railway", "difficulty": "Hard", "text": "Total railway network length in India is approximately?", "option_a": "60,000 km", "option_b": "70,000 km", "option_c": "80,000 km", "option_d": "90,000 km", "correct_option": "C", "explanation": "Approximately 68,000 km"},
        {"subject": "Railway", "difficulty": "Hard", "text": "Konkan Railway connects?", "option_a": "Mumbai to Goa", "option_b": "Goa to Kerala", "option_c": "Mumbai to Kerala", "option_d": "Karnataka to Kerala", "correct_option": "C", "explanation": "Konkan Railway connects Mumbai to Kerala via Goa"},
        {"subject": "Railway", "difficulty": "Hard", "text": "Which railway zone handles maximum passengers?", "option_a": "Central", "option_b": "Northern", "option_c": "Eastern", "option_d": "South Central", "correct_option": "B", "explanation": "Northern Railway handles most passengers"},

        # BANKING
        {"subject": "Banking", "difficulty": "Easy", "text": "Who is the current RBI Governor?", "option_a": "Shaktikanta Das", "option_b": "Sanjay Malhotra", "option_c": "Michael Patra", "option_d": "Raghuram Rajan", "correct_option": "B", "explanation": "Sanjay Malhotra is the current RBI Governor"},
        {"subject": "Banking", "difficulty": "Easy", "text": "RBI was established in?", "option_a": "1930", "option_b": "1935", "option_c": "1947", "option_d": "1950", "correct_option": "B", "explanation": "RBI was established on April 1, 1935"},
        {"subject": "Banking", "difficulty": "Easy", "text": "What does NEFT stand for?", "option_a": "National Electronic Fund Transfer", "option_b": "National Express Fund Transfer", "option_c": "National Efficient Fund Transfer", "option_d": "National E-Fund Transfer", "correct_option": "A", "explanation": "NEFT is National Electronic Fund Transfer"},
        {"subject": "Banking", "difficulty": "Easy", "text": "What does RTGS stand for?", "option_a": "Real Time Gross Settlement", "option_b": "Rapid Transfer Gross Settlement", "option_c": "Real Target Gross Settlement", "option_d": "Rapid Time Gross Settlement", "correct_option": "A", "explanation": "RTGS is Real Time Gross Settlement"},
        {"subject": "Banking", "difficulty": "Medium", "text": "IFSC code is of how many digits?", "option_a": "8", "option_b": "9", "option_c": "10", "option_d": "11", "correct_option": "D", "explanation": "IFSC code is 11 characters"},
        {"subject": "Banking", "difficulty": "Medium", "text": "Prime Lending Rate (PLR) is set by?", "option_a": "Government", "option_b": "Banks", "option_c": "RBI", "option_d": "SEBI", "correct_option": "C", "explanation": "RBI sets policy rates and PLR"},
        {"subject": "Banking", "difficulty": "Medium", "text": "What is the Repo Rate?", "option_a": "Rate at which banks borrow from RBI", "option_b": "Rate at which banks lend to RBI", "option_c": "Rate at which banks trade", "option_d": "Rate at which banks lend to customers", "correct_option": "A", "explanation": "Repo is the rate at which banks borrow from RBI"},
        {"subject": "Banking", "difficulty": "Hard", "text": "What is Reverse Repo Rate?", "option_a": "Rate RBI borrows from banks", "option_b": "Rate banks borrow from RBI", "option_c": "Rate of interest on deposits", "option_d": "Rate of interest on loans", "correct_option": "A", "explanation": "Reverse Repo is rate at which RBI borrows from banks"},
        {"subject": "Banking", "difficulty": "Hard", "text": "CRR stands for?", "option_a": "Cash Reserve Requirement", "option_b": "Capital Reserve Ratio", "option_c": "Cash Requirement Ratio", "option_d": "Capital Risk Ratio", "correct_option": "A", "explanation": "CRR is Cash Reserve Requirement"},
        {"subject": "Banking", "difficulty": "Hard", "text": "What is the current Cash Reserve Ratio approximately?", "option_a": "2%", "option_b": "4%", "option_c": "6%", "option_d": "8%", "correct_option": "B", "explanation": "Current CRR is approximately 4%"},

        # INSURANCE
        {"subject": "Insurance", "difficulty": "Easy", "text": "Life Insurance Corporation was established in?", "option_a": "1950", "option_b": "1956", "option_c": "1960", "option_d": "1965", "correct_option": "B", "explanation": "LIC was established on September 1, 1956"},
        {"subject": "Insurance", "difficulty": "Easy", "text": "What is LIC full form?", "option_a": "Life Insurance Commission", "option_b": "Life Insurance Corporation", "option_c": "Life Investment Corporation", "option_d": "Life Insurance Company", "correct_option": "B", "explanation": "LIC stands for Life Insurance Corporation"},
        {"subject": "Insurance", "difficulty": "Easy", "text": "Premium is paid to buy?", "option_a": "Insurance policy", "option_b": "Investment", "option_c": "Loan", "option_d": "Savings", "correct_option": "A", "explanation": "Premium is paid to buy insurance coverage"},
        {"subject": "Insurance", "difficulty": "Easy", "text": "The person who buys insurance is called?", "option_a": "Insurer", "option_b": "Policyholder", "option_c": "Broker", "option_d": "Agent", "correct_option": "B", "explanation": "Person buying insurance is policyholder"},
        {"subject": "Insurance", "difficulty": "Medium", "text": "Claim settlement is the responsibility of?", "option_a": "Policyholder", "option_b": "Insurance company", "option_c": "Broker", "option_d": "Government", "correct_option": "B", "explanation": "Insurance company settles valid claims"},
        {"subject": "Insurance", "difficulty": "Medium", "text": "What is an insurance policy?", "option_a": "Agreement between insurer and insured", "option_b": "Government rule", "option_c": "Bank statement", "option_d": "Investment certificate", "correct_option": "A", "explanation": "Policy is the agreement between insurer and insured"},
        {"subject": "Insurance", "difficulty": "Medium", "text": "Deductible is?", "option_a": "Amount insured", "option_b": "Amount policyholder pays before insurance pays", "option_c": "Total premium", "option_d": "Benefit amount", "correct_option": "B", "explanation": "Deductible is out-of-pocket cost for policyholder"},
        {"subject": "Insurance", "difficulty": "Hard", "text": "Risk pooling in insurance means?", "option_a": "Keeping money in pool", "option_b": "Many share same risk", "option_c": "Risk management strategy", "option_d": "Insurance investment", "correct_option": "B", "explanation": "Many policyholders share the risk cost"},
        {"subject": "Insurance", "difficulty": "Hard", "text": "What is insurance underwriting?", "option_a": "Selling insurance", "option_b": "Buying insurance", "option_c": "Assessment of risk", "option_d": "Processing claims", "correct_option": "C", "explanation": "Underwriting is risk assessment and evaluation"},
        {"subject": "Insurance", "difficulty": "Hard", "text": "Moral hazard in insurance refers to?", "option_a": "Dishonest behavior after getting insurance", "option_b": "Insurance fraud", "option_c": "Risk increase", "option_d": "Claim denial", "correct_option": "A", "explanation": "Moral hazard is incentive to increase risk after insuring"},

        # SSC
        {"subject": "SSC", "difficulty": "Easy", "text": "What does SSC stand for?", "option_a": "Staff Selection Commission", "option_b": "State Service Commission", "option_c": "Security Selection Committee", "option_d": "Service Selection Commission", "correct_option": "A", "explanation": "SSC stands for Staff Selection Commission"},
        {"subject": "SSC", "difficulty": "Easy", "text": "SSC was established in?", "option_a": "1975", "option_b": "1976", "option_c": "1977", "option_d": "1978", "correct_option": "B", "explanation": "SSC was established on November 4, 1975"},
        {"subject": "SSC", "difficulty": "Easy", "text": "SSC conducts exam for which posts?", "option_a": "All government posts", "option_b": "Group B and C posts", "option_c": "Only bank posts", "option_d": "Only railway posts", "correct_option": "B", "explanation": "SSC conducts exam for Group B and C posts"},
        {"subject": "SSC", "difficulty": "Easy", "text": "Age limit for SSC CHSL is?", "option_a": "18-25", "option_b": "18-27", "option_c": "20-30", "option_d": "21-32", "correct_option": "B", "explanation": "Age limit for CHSL is 18-27 years"},
        {"subject": "SSC", "difficulty": "Medium", "text": "SSC CGL stands for?", "option_a": "Combined Graduate Level", "option_b": "Combined General Level", "option_c": "Central Grade List", "option_d": "Central Government Level", "correct_option": "A", "explanation": "SSC CGL is Combined Graduate Level"},
        {"subject": "SSC", "difficulty": "Medium", "text": "How many tiers are there in SSC CGL?", "option_a": "2", "option_b": "3", "option_c": "4", "option_d": "5", "correct_option": "C", "explanation": "SSC CGL has 4 tiers"},
        {"subject": "SSC", "difficulty": "Medium", "text": "CHSL stands for?", "option_a": "Combined Higher Secondary Level", "option_b": "Combined High School Level", "option_c": "Comprehensive Secondary Level", "option_d": "Central High Service Level", "correct_option": "A", "explanation": "CHSL is Combined Higher Secondary Level"},
        {"subject": "SSC", "difficulty": "Hard", "text": "What is the maximum age limit for SSC CGL?", "option_a": "28", "option_b": "30", "option_c": "32", "option_d": "35", "correct_option": "C", "explanation": "Age limit for SSC CGL is 21-32 for general"},
        {"subject": "SSC", "difficulty": "Hard", "text": "SSC Stenographer exam is for?", "option_a": "Group A posts", "option_b": "Group B and C posts", "option_c": "Group C and D posts", "option_d": "Only Group D posts", "correct_option": "B", "explanation": "SSC Stenographer is for Group C and D posts"},
        {"subject": "SSC", "difficulty": "Hard", "text": "SSC JE stands for?", "option_a": "Junior Engineer", "option_b": "Joint Examination", "option_c": "Junior Executive", "option_d": "Judicial Examination", "correct_option": "A", "explanation": "SSC JE is for Junior Engineer posts"},
    ]


# ---------------------------------------------------------------------------
# Helper: build a quiz-friendly dict from a raw MongoDB question document
# ---------------------------------------------------------------------------
def question_to_quiz_dict(q):
    return {
        "id": str(q["_id"]),
        "subject": q["subject"],
        "difficulty": q["difficulty"],
        "text": q["text"],
        "option_a": q["option_a"],
        "option_b": q["option_b"],
        "option_c": q["option_c"],
        "option_d": q["option_d"],
    }


# ---------------------------------------------------------------------------
# Helper: load an attempt together with its embedded answer docs
# ---------------------------------------------------------------------------
def load_attempt_with_answers(attempt_id):
    """Return a Doc for the attempt with .answers populated, or None."""
    try:
        doc = attempts_col.find_one({"_id": ObjectId(attempt_id)})
    except Exception:
        return None
    if not doc:
        return None
    attempt = Doc(doc)
    attempt.answers = to_docs(answers_col.find({"attempt_id": str(doc["_id"])}))
    return attempt


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def register_routes(app):

    # ---- public ------------------------------------------------------------
    @app.route("/")
    def index():
        if "user_id" in session:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = users_col.find_one({"username": username})

            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = str(user["_id"])
                session["username"] = user["username"]
                session["role"] = user["role"]
                flash("Signed in successfully.", "success")
                return redirect(url_for("dashboard"))

            flash("Invalid username or password.", "error")

        return render_template("login.html")

    @app.route("/register", methods=["POST"])
    def register():
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "student")

        if role not in {"student", "admin"}:
            role = "student"

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("login"))

        if users_col.find_one({"$or": [{"username": username}, {"email": email}]}):
            flash("Username or email already exists.", "error")
            return redirect(url_for("login"))

        users_col.insert_one(
            {
                "username": username,
                "email": email,
                "password_hash": generate_password_hash(password),
                "role": role,
                "created_at": datetime.now(timezone.utc),
            }
        )
        flash("Account created. You can sign in now.", "success")
        return redirect(url_for("login"))

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    # ---- student dashboard -------------------------------------------------
    @app.route("/dashboard")
    @login_required
    def dashboard():
        user = current_user()
        attempts = to_docs(
            attempts_col.find({"user_id": user.id})
            .sort("date_taken", -1)
            .limit(10)
        )
        return render_template(
            "dashboard.html",
            active_page="dashboard",
            stats=dashboard_stats(user.id),
            attempts=attempts,
            cache_buster=int(time()),
        )

    # ---- quiz flow ---------------------------------------------------------
    @app.route("/quiz")
    @login_required
    def quiz_select():
        subjects = to_docs(subjects_col.find().sort("_id", 1))
        counts = {}
        for s in subjects:
            counts[s.name] = questions_col.count_documents({"subject": s.name})
        counts["Full-Length Mock"] = questions_col.count_documents({})

        return render_template(
            "quiz_select.html",
            active_page="quiz_select",
            subjects=subjects,
            question_counts=counts,
        )

    @app.route("/quiz/start", methods=["POST"])
    @login_required
    def quiz_start():
        subject = request.form.get("subject", SUBJECTS[0])
        count = clamp_int(request.form.get("num_questions"), 5, 1, 50)
        duration_minutes = clamp_int(request.form.get("duration"), 5, 1, 180)

        query_filter = {} if subject == "Full-Length Mock" else {"subject": subject}
        raw_questions = list(questions_col.find(query_filter))

        if not raw_questions:
            flash("No questions are available for that subject yet.", "error")
            return redirect(url_for("quiz_select"))

        random.shuffle(raw_questions)
        selected = raw_questions[: min(count, len(raw_questions))]

        session["quiz_question_ids"] = [str(q["_id"]) for q in selected]
        session["quiz_subject"] = subject
        session["quiz_duration_seconds"] = duration_minutes * 60

        return render_template(
            "quiz.html",
            active_page="quiz",
            quiz_subject=subject,
            questions=[question_to_quiz_dict(q) for q in selected],
            duration_seconds=duration_minutes * 60,
        )

    @app.route("/quiz/submit", methods=["POST"])
    @login_required
    def quiz_submit():
        question_ids = session.get("quiz_question_ids", [])
        subject = session.get("quiz_subject", "Mock Test")

        if not question_ids:
            flash("No active quiz was found. Please start a new test.", "error")
            return redirect(url_for("quiz_select"))

        form_answers = parse_answers(request.form.get("answers_json", "{}"))

        # Fetch questions in original order
        oids = [ObjectId(qid) for qid in question_ids if qid]
        raw_questions = list(questions_col.find({"_id": {"$in": oids}}))
        questions_by_id = {str(q["_id"]): q for q in raw_questions}
        ordered_questions = [questions_by_id[qid] for qid in question_ids if qid in questions_by_id]

        # Pre-generate the attempt ObjectId so answers can reference it
        attempt_oid = ObjectId()
        attempt_id_str = str(attempt_oid)
        correct_count = 0
        answer_docs = []

        for q in ordered_questions:
            qid_str = str(q["_id"])
            selected = normalize_option(form_answers.get(qid_str))
            is_correct = selected == q["correct_option"]
            if is_correct:
                correct_count += 1

            # Embed question data directly in the answer for fast reads
            answer_docs.append(
                {
                    "attempt_id": attempt_id_str,
                    "question_id": qid_str,
                    "selected_option": selected,
                    "correct_option": q["correct_option"],
                    "is_correct": is_correct,
                    "text": q["text"],
                    "subject": q["subject"],
                    "difficulty": q["difficulty"],
                    "option_a": q["option_a"],
                    "option_b": q["option_b"],
                    "option_c": q["option_c"],
                    "option_d": q["option_d"],
                    "explanation": q.get("explanation", ""),
                }
            )

        total = max(1, len(ordered_questions))
        pct = round((correct_count / total) * 100, 2)

        # Insert answers
        if answer_docs:
            answers_col.insert_many(answer_docs)

        # Insert attempt
        attempts_col.insert_one(
            {
                "_id": attempt_oid,
                "user_id": session["user_id"],
                "username": session.get("username", "Unknown"),
                "subject": subject,
                "total_questions": len(ordered_questions),
                "correct_answers": correct_count,
                "percentage": pct,
                "time_taken": max(0, int(request.form.get("time_taken") or 0)),
                "date_taken": datetime.now(timezone.utc),
            }
        )

        session.pop("quiz_question_ids", None)
        session.pop("quiz_subject", None)
        session.pop("quiz_duration_seconds", None)

        flash("Quiz submitted successfully.", "success")
        return redirect(url_for("quiz_result", attempt_id=attempt_id_str))

    @app.route("/quiz/result/<attempt_id>")
    @login_required
    def quiz_result(attempt_id):
        attempt = load_attempt_with_answers(attempt_id)
        if not attempt:
            flash("Attempt not found.", "error")
            return redirect(url_for("dashboard"))

        if attempt.user_id != session["user_id"] and session.get("role") != "admin":
            flash("You cannot view that attempt.", "error")
            return redirect(url_for("dashboard"))

        try:
            return render_template(
                "quiz_result.html",
                active_page="quiz",
                attempt=attempt,
                questions_answers=attempt.answers,
            )
        except Exception as e:
            flash(f"Error displaying report: {str(e)}", "error")
            return redirect(url_for("dashboard"))

    # ---- admin -------------------------------------------------------------
    @app.route("/admin")
    @login_required
    @admin_required
    def admin():
        subjects = to_docs(subjects_col.find().sort("created_at", -1))
        questions = to_docs(questions_col.find().sort("_id", -1))
        users = to_docs(users_col.find().sort("created_at", -1))
        all_attempts = to_docs(attempts_col.find().sort("date_taken", -1))

        return render_template(
            "admin.html",
            active_page="admin",
            questions=questions,
            users=users,
            all_attempts=all_attempts,
            subjects=subjects,
            available_subjects=SUBJECTS,
        )

    @app.route("/admin/questions/add", methods=["POST"])
    @login_required
    @admin_required
    def admin_add_question():
        text = request.form.get("text", "").strip()
        option_a = request.form.get("option_a", "").strip()
        option_b = request.form.get("option_b", "").strip()
        option_c = request.form.get("option_c", "").strip()
        option_d = request.form.get("option_d", "").strip()

        if not all([text, option_a, option_b, option_c, option_d]):
            flash("Please fill in all question fields.", "error")
            return redirect(url_for("admin"))

        questions_col.insert_one(
            {
                "subject": request.form.get("subject", SUBJECTS[0]),
                "difficulty": request.form.get("difficulty", "Medium"),
                "text": text,
                "option_a": option_a,
                "option_b": option_b,
                "option_c": option_c,
                "option_d": option_d,
                "correct_option": normalize_option(request.form.get("correct_option")) or "A",
                "explanation": request.form.get("explanation", "").strip(),
                "created_at": datetime.now(timezone.utc),
            }
        )
        flash("Question added to the bank.", "success")
        return redirect(url_for("admin"))

    @app.route("/admin/questions/<question_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def admin_delete_question(question_id):
        try:
            result = questions_col.delete_one({"_id": ObjectId(question_id)})
        except Exception:
            flash("Invalid question ID.", "error")
            return redirect(url_for("admin"))

        if result.deleted_count == 0:
            flash("Question not found.", "error")
        else:
            flash("Question deleted.", "success")
        return redirect(url_for("admin"))

    @app.route("/admin/subjects/add", methods=["POST"])
    @login_required
    @admin_required
    def admin_add_subject():
        name = request.form.get("name", "").strip()
        emoji = request.form.get("emoji", "Book").strip()
        description = request.form.get("description", "").strip()

        if not name:
            flash("Subject name is required.", "error")
            return redirect(url_for("admin"))

        if subjects_col.find_one({"name": name}):
            flash("This subject already exists.", "error")
            return redirect(url_for("admin"))

        subjects_col.insert_one(
            {
                "name": name,
                "emoji": emoji,
                "description": description,
                "difficulty_range": "Mixed",
                "created_at": datetime.now(timezone.utc),
            }
        )

        if name not in SUBJECTS:
            SUBJECTS.append(name)

        flash(f"Subject '{name}' added successfully.", "success")
        return redirect(url_for("admin"))

    @app.route("/admin/subjects/<subject_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def admin_delete_subject(subject_id):
        try:
            subject_doc = subjects_col.find_one({"_id": ObjectId(subject_id)})
        except Exception:
            flash("Invalid subject ID.", "error")
            return redirect(url_for("admin"))

        if not subject_doc:
            flash("Subject not found.", "error")
            return redirect(url_for("admin"))

        if subject_doc["name"] in SUBJECTS:
            SUBJECTS.remove(subject_doc["name"])

        subjects_col.delete_one({"_id": subject_doc["_id"]})
        flash(f"Subject '{subject_doc['name']}' deleted.", "success")
        return redirect(url_for("admin"))

    # ---- charts (SVG) ------------------------------------------------------
    @app.route("/charts/accuracy.svg")
    @login_required
    def accuracy_chart():
        attempts = to_docs(attempts_col.find({"user_id": session["user_id"]}))
        subject_scores = defaultdict(list)
        for attempt in attempts:
            if attempt.subject == "Full-Length Mock":
                continue
            subject_scores[attempt.subject].append(attempt.percentage)

        labels = list(subject_scores.keys())
        values = [round(sum(scores) / len(scores), 1) for scores in subject_scores.values()]
        return svg_response(bar_chart_svg(labels, values, "Subject Accuracy"))

    @app.route("/charts/trend.svg")
    @login_required
    def trend_chart():
        attempts = to_docs(
            attempts_col.find({"user_id": session["user_id"]}).sort("date_taken", 1)
        )
        labels = [str(index + 1) for index, _a in enumerate(attempts)]
        values = [a.percentage for a in attempts]
        return svg_response(line_chart_svg(labels, values, "Attempt Trend"))

    # ---- PDF downloads -----------------------------------------------------
    @app.route("/download/result/<attempt_id>/pdf")
    @login_required
    def download_result_pdf(attempt_id):
        attempt = load_attempt_with_answers(attempt_id)
        if not attempt:
            flash("Attempt not found.", "error")
            return redirect(url_for("dashboard"))

        if attempt.user_id != session["user_id"] and session.get("role") != "admin":
            flash("You cannot download that result.", "error")
            return redirect(url_for("dashboard"))

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, text="Quiz Result Report", ln=True, align="C")
        pdf.ln(5)
        pdf.cell(200, 10, text=f"Student Name: {session.get('username')}", ln=True)
        pdf.cell(200, 10, text=f"Subject: {attempt.subject}", ln=True)
        pdf.cell(200, 10, text=f"Date Taken: {attempt.date_taken}", ln=True)
        pdf.cell(200, 10, text=f"Total Questions: {attempt.total_questions}", ln=True)
        pdf.cell(200, 10, text=f"Correct Answers: {attempt.correct_answers}", ln=True)
        pdf.cell(200, 10, text=f"Percentage: {attempt.percentage}%", ln=True)
        pdf.cell(200, 10, text=f"Time Taken: {attempt.time_taken // 60}m {attempt.time_taken % 60}s", ln=True)
        pdf.ln(5)

        pdf.set_font("Arial", "B", 10)
        pdf.cell(100, 10, "Question", border=1)
        pdf.cell(30, 10, "Your Answer", border=1)
        pdf.cell(30, 10, "Correct Answer", border=1)
        pdf.cell(30, 10, "Result", border=1)
        pdf.ln(10)

        pdf.set_font("Arial", size=10)
        for answer in attempt.answers:
            result = "Correct" if answer.is_correct else "Incorrect"
            pdf.cell(100, 10, str(answer.text)[:45].encode("latin-1", "replace").decode("latin-1"), border=1)
            pdf.cell(30, 10, str(answer.selected_option or "None").encode("latin-1", "replace").decode("latin-1"), border=1)
            pdf.cell(30, 10, str(answer.correct_option).encode("latin-1", "replace").decode("latin-1"), border=1)
            pdf.cell(30, 10, result.encode("latin-1", "replace").decode("latin-1"), border=1)
            pdf.ln(10)

        return Response(
            bytes(pdf.output()),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment;filename=quiz_result_{attempt_id}.pdf"},
        )

    @app.route("/download/questions/<subject>/pdf")
    @login_required
    @admin_required
    def download_questions_pdf(subject):
        raw_questions = list(questions_col.find({"subject": subject}))
        if not raw_questions:
            flash("No questions found for this subject.", "error")
            return redirect(url_for("admin"))

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, text=f"{subject} Questions Bank", ln=True, align="C")
        pdf.ln(5)

        pdf.set_font("Arial", size=10)
        for i, q in enumerate(raw_questions, 1):
            pdf.multi_cell(0, 8, text=f"Q{i} [{q['difficulty']}]: {q['text']}".encode("latin-1", "replace").decode("latin-1"))
            pdf.multi_cell(0, 8, text=f"A: {q['option_a']} | B: {q['option_b']} | C: {q['option_c']} | D: {q['option_d']}".encode("latin-1", "replace").decode("latin-1"))
            pdf.multi_cell(0, 8, text=f"Correct: {q['correct_option']} | Exp: {q.get('explanation') or 'None'}".encode("latin-1", "replace").decode("latin-1"))
            pdf.ln(5)

        return Response(
            bytes(pdf.output()),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"attachment;filename={subject.replace(' ', '_')}_questions.pdf"},
        )

    @app.route("/download/all-attempts/pdf")
    @login_required
    def download_attempts_pdf():
        user_id = session["user_id"]
        attempts = to_docs(attempts_col.find({"user_id": user_id}).sort("date_taken", -1))

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, text="Quiz Attempts Report", ln=True, align="C")
        pdf.ln(5)
        pdf.cell(200, 10, text=f"Student Name: {session.get('username')}", ln=True)
        pdf.ln(5)

        pdf.set_font("Arial", "B", 10)
        pdf.cell(50, 10, "Date", border=1)
        pdf.cell(40, 10, "Subject", border=1)
        pdf.cell(20, 10, "Total Q", border=1)
        pdf.cell(20, 10, "Correct", border=1)
        pdf.cell(30, 10, "Percentage", border=1)
        pdf.cell(30, 10, "Time", border=1)
        pdf.ln(10)

        pdf.set_font("Arial", size=10)
        for attempt in attempts:
            pdf.cell(50, 10, str(attempt.date_taken)[:19], border=1)
            pdf.cell(40, 10, str(attempt.subject)[:20], border=1)
            pdf.cell(20, 10, str(attempt.total_questions), border=1)
            pdf.cell(20, 10, str(attempt.correct_answers), border=1)
            pdf.cell(30, 10, f"{attempt.percentage}%", border=1)
            pdf.cell(30, 10, f"{attempt.time_taken // 60}m", border=1)
            pdf.ln(10)

        return Response(
            bytes(pdf.output()),
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment;filename=quiz_attempts.pdf"},
        )

    @app.route("/admin/questions/upload_pdf", methods=["POST"])
    @login_required
    @admin_required
    def admin_upload_questions_pdf():
        subject = request.form.get("subject", SUBJECTS[0])
        difficulty = request.form.get("difficulty", "Medium")

        if "pdf_file" not in request.files:
            flash("No file part", "error")
            return redirect(url_for("admin"))

        file = request.files["pdf_file"]
        if file.filename == "":
            flash("No selected file", "error")
            return redirect(url_for("admin"))

        if file and file.filename.endswith(".pdf"):
            try:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"

                lines = [line.strip() for line in text.split("\n") if line.strip()]
                docs_to_insert = []
                now = datetime.now(timezone.utc)
                for line in lines:
                    if len(line) > 10:
                        docs_to_insert.append(
                            {
                                "subject": subject,
                                "difficulty": difficulty,
                                "text": line[:500],
                                "option_a": "A",
                                "option_b": "B",
                                "option_c": "C",
                                "option_d": "D",
                                "correct_option": "A",
                                "explanation": "Extracted from PDF",
                                "created_at": now,
                            }
                        )

                if docs_to_insert:
                    questions_col.insert_many(docs_to_insert)
                flash(f"Successfully extracted and added {len(docs_to_insert)} questions.", "success")
            except Exception as e:
                flash(f"Error reading PDF: {str(e)}", "error")
        else:
            flash("Invalid file format. Please upload a PDF.", "error")

        return redirect(url_for("admin"))

    @app.route("/dashboard/download_question_bank_pdf")
    @login_required
    def download_question_bank_pdf():
        raw_questions = list(questions_col.find().limit(200))
        if not raw_questions:
            flash("No questions found in the bank.", "error")
            return redirect(url_for("dashboard"))

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, text="Complete Question Bank", ln=True, align="C")
        pdf.ln(5)

        pdf.set_font("Arial", size=10)
        for i, q in enumerate(raw_questions, 1):
            pdf.multi_cell(0, 8, text=f"Q{i} [{q['subject']} - {q['difficulty']}]: {q['text']}".encode("latin-1", "replace").decode("latin-1"))
            pdf.multi_cell(0, 8, text=f"A: {q['option_a']} | B: {q['option_b']} | C: {q['option_c']} | D: {q['option_d']}".encode("latin-1", "replace").decode("latin-1"))
            pdf.multi_cell(0, 8, text=f"Correct: {q['correct_option']}".encode("latin-1", "replace").decode("latin-1"))
            pdf.ln(5)

        return Response(
            bytes(pdf.output()),
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment;filename=question_bank.pdf"},
        )


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------
def dashboard_stats(user_id):
    attempts = to_docs(attempts_col.find({"user_id": user_id}).sort("date_taken", 1))
    has_data = bool(attempts)

    if not has_data:
        return {
            "has_data": False,
            "total_attempts": 0,
            "overall_accuracy": 0,
            "strongest_subject": None,
            "strongest_score": 0,
            "weakest_subject": None,
            "weakest_score": 0,
            "weak_areas_tips": [],
            "accuracy_chart_url": url_for("accuracy_chart"),
            "trend_chart_url": url_for("trend_chart"),
        }

    subject_scores = defaultdict(list)
    for attempt in attempts:
        subject_scores[attempt.subject].append(attempt.percentage)

    averages = {
        subject: round(sum(scores) / len(scores), 1)
        for subject, scores in subject_scores.items()
    }
    strongest_subject = max(averages, key=averages.get)
    weakest_subject = min(averages, key=averages.get)
    overall_accuracy = round(sum(a.percentage for a in attempts) / len(attempts), 1)

    tips = [
        f"Focus your next practice session on {weakest_subject}; your current average is {averages[weakest_subject]}%.",
        "Review every incorrect answer from your latest reports before taking another timed quiz.",
        "Keep alternating subjects so your full-length mock performance stays balanced.",
    ]

    return {
        "has_data": True,
        "total_attempts": len(attempts),
        "overall_accuracy": overall_accuracy,
        "strongest_subject": strongest_subject,
        "strongest_score": averages[strongest_subject],
        "weakest_subject": weakest_subject,
        "weakest_score": averages[weakest_subject],
        "weak_areas_tips": tips,
        "accuracy_chart_url": url_for("accuracy_chart"),
        "trend_chart_url": url_for("trend_chart"),
    }


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def clamp_int(value, default, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(maximum, number))


def parse_answers(raw):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def normalize_option(value):
    if not value:
        return None
    option = str(value).strip().upper()
    return option if option in {"A", "B", "C", "D"} else None


# ---------------------------------------------------------------------------
# SVG chart rendering
# ---------------------------------------------------------------------------
def svg_response(svg):
    return Response(svg, mimetype="image/svg+xml")


def bar_chart_svg(labels, values, title):
    width, height = 680, 320
    if not labels:
        return empty_chart_svg(title)

    max_value = max(100, max(values))
    chart_left, chart_bottom, chart_top = 60, 260, 50
    slot = (width - chart_left - 30) / len(labels)
    bars = []
    for index, (label, value) in enumerate(zip(labels, values)):
        bar_height = (value / max_value) * (chart_bottom - chart_top)
        x = chart_left + index * slot + slot * 0.2
        y = chart_bottom - bar_height
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{slot * 0.6:.1f}" height="{bar_height:.1f}" rx="4" fill="#4f46e5" />'
            f'<text x="{x + slot * 0.3:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-size="13" fill="#e5e7eb">{value}%</text>'
            f'<text x="{x + slot * 0.3:.1f}" y="292" text-anchor="middle" font-size="12" fill="#9ca3af">{html.escape(label[:16])}</text>'
        )

    return chart_shell(width, height, title, "".join(bars))


def line_chart_svg(labels, values, title):
    width, height = 680, 320
    if not labels:
        return empty_chart_svg(title)

    chart_left, chart_right, chart_bottom, chart_top = 60, 640, 260, 50
    step = (chart_right - chart_left) / max(1, len(values) - 1)
    points = []
    for index, value in enumerate(values):
        x = chart_left + index * step
        y = chart_bottom - (value / 100) * (chart_bottom - chart_top)
        points.append((x, y, value))

    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y, _value in points)
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#22c55e" />'
        f'<text x="{x:.1f}" y="{y - 12:.1f}" text-anchor="middle" font-size="12" fill="#e5e7eb">{value:.0f}%</text>'
        for x, y, value in points
    )
    body = f'<polyline points="{polyline}" fill="none" stroke="#22c55e" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />{dots}'
    return chart_shell(width, height, title, body)


def empty_chart_svg(title):
    return chart_shell(
        680,
        320,
        title,
        '<text x="340" y="170" text-anchor="middle" font-size="16" fill="#9ca3af">No attempt data yet</text>',
    )


def chart_shell(width, height, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" rx="14" fill="#0f172a"/>
<text x="24" y="30" font-size="18" font-family="Arial, sans-serif" font-weight="700" fill="#f8fafc">{html.escape(title)}</text>
<line x1="60" y1="260" x2="640" y2="260" stroke="#334155"/>
<line x1="60" y1="50" x2="60" y2="260" stroke="#334155"/>
{body}
</svg>"""


# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------
app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="127.0.0.1", port=port, debug=True)
