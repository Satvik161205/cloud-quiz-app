import os
import json
from urllib.parse import urlparse
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from config import config
from models import db, User, Question, Score, QuizSession

def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    db.init_app(app)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        db.create_all()
        # AUTO-ADMIN: admin / admin123
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@quiz.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

    @app.route('/')
    def index():
        return render_template('index.html')

    # --- NEW: REGISTER ROUTE ---
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            
            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'danger')
            elif User.query.filter_by(email=email).first():
                flash('Email already registered', 'danger')
            else:
                new_user = User(username=username, email=email)
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            user = User.query.filter_by(username=request.form.get('username')).first()
            if user and user.check_password(request.form.get('password')):
                login_user(user)
                next_page = request.args.get('next')
                if not next_page or urlparse(next_page).netloc != '':
                    next_page = url_for('dashboard')
                return redirect(next_page)
            flash('Invalid username or password', 'danger')
        return render_template('login.html')

    @app.route('/logout', methods=['GET', 'POST']) # Add methods here
    @login_required
    def logout():
        logout_user()
        return redirect(url_for('index'))

    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html', 
                               total_quizzes=current_user.get_total_quizzes(),
                               avg_score=current_user.get_average_score(),
                               high_score=current_user.get_high_score(),
                               recent_scores=current_user.get_recent_scores())

    @app.route('/quiz', methods=['GET', 'POST'])
    @login_required
    def quiz():
        sess = QuizSession.query.filter_by(user_id=current_user.id, is_completed=False).first()
        
        if request.method == 'POST':
            ans = request.form.get('answer')
            if sess and ans:
                sess.add_answer(ans)
                db.session.commit()
                if sess.current_question_index >= len(sess.get_question_ids()):
                    res = sess.calculate_score()
                    score_obj = Score(
                        user_id=current_user.id, 
                        score=res['score'], 
                        total_questions=res['total'], 
                        correct_answers=res['correct']
                    )
                    db.session.add(score_obj)
                    db.session.delete(sess)
                    db.session.commit()
                    return redirect(url_for('result', score_id=score_obj.id))

        if not sess:
            qs = Question.query.order_by(db.func.random()).limit(app.config['QUESTIONS_PER_QUIZ']).all()
            if len(qs) < app.config['QUESTIONS_PER_QUIZ']:
                flash(f'Add at least {app.config["QUESTIONS_PER_QUIZ"]} questions in Admin first!', 'warning')
                return redirect(url_for('dashboard'))
            sess = QuizSession(user_id=current_user.id, question_ids=json.dumps([q.id for q in qs]))
            db.session.add(sess)
            db.session.commit()

        q_id = sess.get_current_question_id()
        question = Question.query.get(q_id)
        return render_template('quiz.html', question=question, current=sess.current_question_index + 1, total=len(sess.get_question_ids()))

    @app.route('/result/<int:score_id>')
    @login_required
    def result(score_id):
        s = Score.query.get_or_404(score_id)
        if s.user_id != current_user.id and not current_user.is_admin:
            return redirect(url_for('dashboard'))
        return render_template('result.html', score=s)

    @app.route('/admin', methods=['GET', 'POST'])
    @login_required
    def admin():
        if not current_user.is_admin:
            flash('Unauthorized access!', 'danger')
            return redirect(url_for('dashboard'))
        if request.method == 'POST':
            new_q = Question(
                question_text=request.form.get('question_text'),
                option1=request.form.get('option1'), option2=request.form.get('option2'),
                option3=request.form.get('option3'), option4=request.form.get('option4'),
                correct_answer=request.form.get('correct_answer'),
                difficulty=request.form.get('difficulty', 'medium'),
                category=request.form.get('category', 'general')
            )
            db.session.add(new_q)
            db.session.commit()
            flash('Question added!', 'success')
        return render_template('admin.html', questions=Question.query.all())

    @app.route('/admin/delete/<int:qid>', methods=['POST'])
    @login_required
    def delete_question(qid):
        if current_user.is_admin:
            db.session.delete(Question.query.get_or_404(qid))
            db.session.commit()
        return redirect(url_for('admin'))

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)