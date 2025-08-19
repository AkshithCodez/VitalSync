from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from .models import PlannerItem, User, VitalsLog, Meal
from . import db
import google.generativeai as genai
import os
import re
import requests
import json
from . import create_app
from flask_weasyprint import HTML, render_pdf
from datetime import datetime, date

main = Blueprint('main', __name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def generate_report_in_background(user_id):
    app = create_app()
    with app.app_context():
        user = User.query.get(user_id)
        if user and not user.ai_report and user.condition:
            prompt = f"Generate a supportive health summary for a user diagnosed with {user.condition}. Include sections on understanding the condition, potential consequences, supportive non-prescription measures, and beneficial nutrients. Do NOT give medical advice or mention specific medications. Format section titles with markdown bolding (e.g., **Title**)."
            try:
                response = model.generate_content(prompt)
                user.ai_report = response.text
                db.session.commit()
            except Exception as e:
                user.ai_report = f"Sorry, there was an error generating the report. Error: {e}"
                db.session.commit()

def get_nutrition_data(food_item):
    api_key = os.getenv('USDA_API_KEY')
    calories, protein, carbs, fats = 0, 0, 0, 0
    if not api_key:
        print("USDA API KEY not found.")
        return 0, 0, 0, 0
    try:
        search_url = f"https://api.nal.usda.gov/fdc/v1/foods/search?api_key={api_key}&query={food_item}"
        search_response = requests.get(search_url)
        search_response.raise_for_status()
        search_data = search_response.json()
        if not search_data.get('foods'): return 0, 0, 0, 0
        fdc_id = search_data['foods'][0]['fdcId']
        details_url = f"https://api.nal.usda.gov/fdc/v1/food/{fdc_id}?api_key={api_key}"
        details_response = requests.get(details_url)
        details_response.raise_for_status()
        details_data = details_response.json()
        for nutrient in details_data.get('foodNutrients', []):
            if nutrient['nutrient']['id'] == 1008: calories = int(nutrient.get('amount', 0))
            elif nutrient['nutrient']['id'] == 1003: protein = int(nutrient.get('amount', 0))
            elif nutrient['nutrient']['id'] == 1005: carbs = int(nutrient.get('amount', 0))
            elif nutrient['nutrient']['id'] == 1004: fats = int(nutrient.get('amount', 0))
    except requests.exceptions.RequestException as e:
        print(f"USDA API Error: {e}")
    return calories, protein, carbs, fats

def add_meal_from_ai(food_item, meal_type, user):
    calories, protein, carbs, fats = get_nutrition_data(food_item)
    new_meal = Meal(
        meal_type=meal_type, food_item=food_item,
        calories=calories, protein=protein, carbs=carbs, fats=fats,
        owner=user, date=date.today(), is_eaten=False
    )
    db.session.add(new_meal)

@main.route('/')
@login_required
def home():
    items = PlannerItem.query.filter_by(user_id=current_user.id).order_by(PlannerItem.appointment_date.asc()).all()
    return render_template('index.html', user=current_user, items=items)

@main.route('/tracking')
@login_required
def tracking():
    vitals = VitalsLog.query.filter_by(user_id=current_user.id).order_by(VitalsLog.date.desc()).all()
    return render_template('tracking.html', user=current_user, vitals=vitals)

@main.route('/assistant')
@login_required
def assistant():
    return render_template('assistant.html', user=current_user)

@main.route('/diet')
@login_required
def diet():
    today = date.today()
    meals = Meal.query.filter_by(owner=current_user, date=today).all()
    totals = {
        'calories': sum(m.calories for m in meals if m.is_eaten),
        'protein': sum(m.protein for m in meals if m.is_eaten),
        'carbs': sum(m.carbs for m in meals if m.is_eaten),
        'fats': sum(m.fats for m in meals if m.is_eaten)
    }
    return render_template('diet.html', user=current_user, meals=meals, totals=totals, today=today)

@main.route('/api/events')
@login_required
def api_events():
    items = PlannerItem.query.filter_by(user_id=current_user.id).all()
    events = [{'title': item.text, 'start': item.appointment_date.isoformat()} for item in items]
    return jsonify(events)

@main.route('/api/vitals_data')
@login_required
def api_vitals_data():
    metric = request.args.get('metric', 'Weight')
    logs = VitalsLog.query.filter_by(user_id=current_user.id, metric_name=metric).order_by(VitalsLog.date.asc()).all()
    ranges = {"Blood Sugar": {"high": 180, "low": 70}, "Blood Pressure": {"high": 130, "low": 90}, "Heart Rate": {"high": 100, "low": 60}, "Sleep": {"high": 9, "low": 7}}
    labels = [log.date.strftime('%Y-%m-%d') for log in logs]
    datasets = []
    if metric == "Blood Pressure":
        systolic_data, diastolic_data = [], []
        for log in logs:
            try:
                parts = re.split(r'[/ ]', log.metric_value)
                if len(parts) >= 2:
                    systolic_data.append(float(parts[0]))
                    diastolic_data.append(float(parts[1]))
            except (ValueError, TypeError, IndexError): continue
        datasets.append({'label': 'Systolic', 'data': systolic_data, 'borderColor': '#e53e3e'})
        datasets.append({'label': 'Diastolic', 'data': diastolic_data, 'borderColor': '#3182ce'})
    else:
        data = []
        for log in logs:
            try: data.append(float(log.metric_value))
            except (ValueError, TypeError): continue
        datasets.append({'label': metric, 'data': data, 'borderColor': '#3182ce'})
    return jsonify({'labels': labels, 'datasets': datasets, 'ranges': ranges.get(metric, {"high": None, "low": None})})

@main.route('/chat', methods=['POST'])
@login_required
def chat():
    user_message = request.json['message']
    prompt = f"You are 'VitalSync Assistant,' a supportive AI health companion for a user with {current_user.condition}. **RULES:** NEVER provide medical advice or diagnoses. NEVER mention medications. ALWAYS end with a disclaimer to consult a doctor. The user's question is: '{user_message}'"
    try:
        response = model.generate_content(prompt)
        ai_reply = response.text
    except Exception:
        ai_reply = "Sorry, I'm having trouble connecting right now."
    return jsonify({'reply': ai_reply})

@main.route('/download_report')
@login_required
def download_report():
    report_text = current_user.ai_report or ""
    report_html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', report_text)
    html = render_template('report_pdf.html', user=current_user, report_html=report_html)
    return render_pdf(HTML(string=html))

@main.route('/download_planner')
@login_required
def download_planner():
    items = PlannerItem.query.filter_by(user_id=current_user.id).order_by(PlannerItem.appointment_date.asc()).all()
    html = render_template('planner_pdf.html', user=current_user, items=items)
    return render_pdf(HTML(string=html))

@main.route('/generate_meal_plan', methods=['POST'])
@login_required
def generate_meal_plan():
    Meal.query.filter_by(owner=current_user, date=date.today()).delete()
    calories = request.form.get('calories', '2000')
    diet_pref = request.form.get('diet_pref', 'a balanced')
    prompt = f"""
    Generate a simple, one-day {diet_pref} meal plan for a user with {current_user.condition}.
    The total calories should be around {calories}.
    Your response MUST be a valid JSON object. Do not include markdown backticks.
    The format should be:
    {{
      "Breakfast": ["item 1", "item 2"],
      "Lunch": ["item 1", "item 2"],
      "Dinner": ["item 1", "item 2"]
    }}
    """
    try:
        print("--- Sending meal plan prompt to AI... ---")
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip()
        print(f"--- AI Response Received:\n{cleaned_text}\n---")
        meal_plan = json.loads(cleaned_text)
        for meal_type, food_items in meal_plan.items():
            for item in food_items:
                add_meal_from_ai(item, meal_type, current_user)
        db.session.commit()
        print("--- Meal plan successfully parsed and saved. ---")
    except Exception as e:
        db.session.rollback()
        print(f"!!! MEAL PLAN GENERATION FAILED: {e} !!!")
        flash("Sorry, there was an error generating the meal plan. Please try again.")
    return redirect(url_for('main.diet'))

@main.route('/grocery_list')
@login_required
def grocery_list():
    meals = Meal.query.filter_by(owner=current_user, date=date.today()).all()
    ingredients = [meal.food_item for meal in meals]
    if not ingredients:
        return render_template('grocery_list.html', grocery_list="Your meal plan for today is empty.")
    prompt = f"Consolidate the following meal items into a simple, categorized grocery list: {', '.join(ingredients)}"
    try:
        response = model.generate_content(prompt)
        grocery_list_text = response.text
    except Exception as e:
        grocery_list_text = f"Could not generate grocery list. Error: {e}"
    return render_template('grocery_list.html', grocery_list=grocery_list_text)

@main.route('/add_meal', methods=['POST'])
@login_required
def add_meal():
    meal_type = request.form.get('meal_type')
    food_item = request.form.get('food_item')
    calories, protein, carbs, fats = get_nutrition_data(food_item)
    new_meal = Meal(meal_type=meal_type, food_item=food_item, calories=calories, protein=protein, carbs=carbs, fats=fats, owner=current_user, date=date.today())
    db.session.add(new_meal)
    db.session.commit()
    return redirect(url_for('main.diet'))

@main.route('/delete_meal/<int:meal_id>')
@login_required
def delete_meal(meal_id):
    meal = Meal.query.filter_by(id=meal_id, user_id=current_user.id).first_or_404()
    db.session.delete(meal)
    db.session.commit()
    return redirect(url_for('main.diet'))

@main.route('/toggle_meal/<int:meal_id>')
@login_required
def toggle_meal(meal_id):
    meal = Meal.query.filter_by(id=meal_id, user_id=current_user.id).first_or_404()
    meal.is_eaten = not meal.is_eaten
    db.session.commit()
    return redirect(url_for('main.diet'))

@main.route('/add_item', methods=['POST'])
@login_required
def add_item():
    item_text = request.form.get('item')
    date_str = request.form.get('date')
    if item_text.strip() and date_str:
        item_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        new_item = PlannerItem(text=item_text, appointment_date=item_date, owner=current_user)
        db.session.add(new_item)
        db.session.commit()
    return redirect(url_for('main.home'))

@main.route('/delete_item/<int:item_id>')
@login_required
def delete_item(item_id):
    item = PlannerItem.query.filter_by(id=item_id, user_id=current_user.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('main.home'))

@main.route('/add_vital', methods=['POST'])
@login_required
def add_vital():
    metric_name = request.form.get('metric_name')
    metric_value = request.form.get('metric_value')
    if metric_name and metric_value.strip():
        new_vital = VitalsLog(metric_name=metric_name, metric_value=metric_value, owner=current_user)
        db.session.add(new_vital)
        db.session.commit()
    return redirect(url_for('main.tracking'))

@main.route('/delete_vital/<int:vital_id>')
@login_required
def delete_vital(vital_id):
    vital = VitalsLog.query.filter_by(id=vital_id, user_id=current_user.id).first_or_404()
    db.session.delete(vital)
    db.session.commit()
    return redirect(url_for('main.tracking'))