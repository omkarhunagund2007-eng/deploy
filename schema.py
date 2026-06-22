from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    emoji = db.Column(db.String(20), nullable=False, default="Book")
    description = db.Column(db.Text, nullable=True)
    difficulty_range = db.Column(db.String(50), default="Mixed")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    attempts = db.relationship("QuizAttempt", back_populates="user", cascade="all, delete-orphan")


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(80), nullable=False, index=True)
    difficulty = db.Column(db.String(20), nullable=False, default="Medium")
    text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)
    explanation = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_quiz_dict(self):
        return {
            "id": self.id,
            "subject": self.subject,
            "difficulty": self.difficulty,
            "text": self.text,
            "option_a": self.option_a,
            "option_b": self.option_b,
            "option_c": self.option_c,
            "option_d": self.option_d,
        }


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    subject = db.Column(db.String(80), nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    correct_answers = db.Column(db.Integer, nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    time_taken = db.Column(db.Integer, nullable=False, default=0)
    date_taken = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="attempts")
    answers = db.relationship("AttemptAnswer", back_populates="attempt", cascade="all, delete-orphan")

    @property
    def username(self):
        return self.user.username if self.user else "Unknown"


class AttemptAnswer(db.Model):
    __tablename__ = "attempt_answers"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("quiz_attempts.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False, index=True)
    selected_option = db.Column(db.String(1), nullable=True)
    correct_option = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)

    attempt = db.relationship("QuizAttempt", back_populates="answers")
    question = db.relationship("Question")

    @property
    def subject(self):
        return self.question.subject if self.question else "Unknown"

    @property
    def difficulty(self):
        return self.question.difficulty if self.question else "Medium"

    @property
    def text(self):
        return self.question.text if self.question else "[Deleted Question]"

    @property
    def option_a(self):
        return self.question.option_a if self.question else "[Deleted]"

    @property
    def option_b(self):
        return self.question.option_b if self.question else "[Deleted]"

    @property
    def option_c(self):
        return self.question.option_c if self.question else "[Deleted]"

    @property
    def option_d(self):
        return self.question.option_d if self.question else "[Deleted]"

    @property
    def explanation(self):
        return self.question.explanation if self.question else ""
