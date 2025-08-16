from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User
from . import db
from flask_login import login_user, logout_user, login_required
import threading # Import the threading library
from .main import generate_report_in_background # Import our new background function

auth = Blueprint('auth', __name__)

@auth.route('/login')
def login():
    return render_template('login.html')

@auth.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')
    
    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password, password):
        flash('Please check your login details and try again.')
        return redirect(url_for('auth.login'))
    
    login_user(user)
    return redirect(url_for('main.home'))

@auth.route('/register')
def register():
    return render_template('register.html')

@auth.route('/register', methods=['POST'])
def register_post():
    username = request.form.get('username')
    name = request.form.get('name')
    age = request.form.get('age')
    gender = request.form.get('gender')
    condition = request.form.get('condition')
    password = request.form.get('password')

    user = User.query.filter_by(username=username).first()
    if user:
        flash('Username already exists.')
        return redirect(url_for('auth.register'))

    new_user = User(
        username=username,
        name=name,
        age=age,
        gender=gender,
        condition=condition,
        password=generate_password_hash(password, method='pbkdf2:sha256')
    )
    
    db.session.add(new_user)
    db.session.commit()

    login_user(new_user)

    # Start the AI report generation in a background thread
    thread = threading.Thread(target=generate_report_in_background, args=(new_user.id,))
    thread.start()

    # Immediately redirect to the dashboard
    return redirect(url_for('main.home'))

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.home'))