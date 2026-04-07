import json
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    
    scores = db.relationship('Score', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_average_score(self):
        scores_list = self.scores.all()
        if not scores_list: return 0
        return round(sum(s.score for s in scores_list) / len(scores_list), 1)

    def get_high_score(self):
        scores_list = self.scores.all()
        if not scores_list: return 0
        return max(s.score for s in scores_list)

    def get_total_quizzes(self):
        return self.scores.count()

    def get_recent_scores(self, limit=5):
        return self.scores.order_by(Score.completed_at.desc()).limit(limit).all()

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    option1 = db.Column(db.String(200), nullable=False)
    option2 = db.Column(db.String(200), nullable=False)
    option3 = db.Column(db.String(200), nullable=False)
    option4 = db.Column(db.String(200), nullable=False)
    correct_answer = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    difficulty = db.Column(db.String(20), default='medium')
    category = db.Column(db.String(50), default='general')

    def is_correct(self, answer):
        return answer.strip().lower() == self.correct_answer.strip().lower()

class Score(db.Model):
    __tablename__ = 'scores'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    score = db.Column(db.Float, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    correct_answers = db.Column(db.Integer, nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

class QuizSession(db.Model):
    __tablename__ = 'quiz_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    current_question_index = db.Column(db.Integer, default=0)
    question_ids = db.Column(db.Text, nullable=False) 
    answers = db.Column(db.Text, default='[]') 
    is_completed = db.Column(db.Boolean, default=False)

    def get_question_ids(self):
        return json.loads(self.question_ids)

    def get_answers(self):
        return json.loads(self.answers)

    def add_answer(self, answer):
        ans_list = self.get_answers()
        ans_list.append(answer)
        self.answers = json.dumps(ans_list)
        self.current_question_index += 1

    def get_current_question_id(self):
        ids = self.get_question_ids()
        return ids[self.current_question_index] if self.current_question_index < len(ids) else None

    def calculate_score(self):
        ids = self.get_question_ids()
        ans = self.get_answers()
        correct = 0
        for qid, u_ans in zip(ids, ans):
            q = Question.query.get(qid)
            if q and q.is_correct(u_ans):
                correct += 1
        total = len(ids)
        return {'score': round((correct/total*100), 1), 'correct': correct, 'total': total}