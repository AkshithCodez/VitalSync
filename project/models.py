from flask_login import UserMixin
from . import db
from datetime import datetime

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(50))
    condition = db.Column(db.String(100))
    ai_report = db.Column(db.Text, nullable=True)
    items = db.relationship('PlannerItem', backref='owner', lazy=True)
    vitals = db.relationship('VitalsLog', backref='owner', lazy=True)
    meals = db.relationship('Meal', backref='owner', lazy=True) # <-- NEW RELATIONSHIP

class PlannerItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    appointment_date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class VitalsLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    metric_name = db.Column(db.String(100), nullable=False)
    metric_value = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# NEW MODEL for diet entries
class Meal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    meal_type = db.Column(db.String(50), nullable=False) # e.g., Breakfast, Lunch
    food_item = db.Column(db.String(200), nullable=False)
    calories = db.Column(db.Integer, default=0)
    protein = db.Column(db.Integer, default=0)
    carbs = db.Column(db.Integer, default=0)
    fats = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)