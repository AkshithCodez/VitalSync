from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from .models import DailyTask, PlannerItem, User
from . import db
import google.generativeai as genai
import os
from . import create_app
from flask_weasyprint import HTML, render_pdf
from datetime import datetime

main = Blueprint('main', __name__)

genai.configure(api_key=os.getenv("AIzaSyCp6kXGriq7cyFI787IOJqIlkLfcI4qSrU"))
model = genai.GenerativeModel('gemini-1.5-flash')

def generate_report_in_background(user_id):
    app = create_app()
    with app.app_context():
        user = User.query.get(user_id)
        if user and not user.ai_report and user.condition:
            prompt = f"""
            You are a helpful health information assistant. Your goal is to provide a general, supportive summary of a health condition for a user who has already been diagnosed by a doctor.

            **IMPORTANT RULES:**
            1.  **DO NOT** provide medical advice.
            2.  **DO NOT** prescribe, mention, or recommend any specific pharmaceutical drugs or medications.
            3.  You **CAN** suggest common, safe, non-prescription home-remedy-style actions for temporary relief.
            4.  You **CAN** recommend general vitamins, nutrients, and healthy lifestyle choices.

            The user's diagnosed condition is: "{user.condition}"

            Please generate a report with four sections: "Understanding Your Condition", "Potential Consequences", "Supportive Measures for Comfort", and "Beneficial Nutrients & Lifestyle".
            """
            try:
                response = model.generate_content(prompt)
                user.ai_report = response.text
                db.session.commit()
            except Exception as e:
                user.ai_report = f"Sorry, there was an error generating the report. Error: {e}"
                db.session.commit()

@main.route('/')
@login_required
def home():
    tasks = DailyTask.query.filter_by(user_id=current_user.id).all()
    items = PlannerItem.query.filter_by(user_id=current_user.id).order_by(PlannerItem.appointment_date.asc()).all()
    return render_template('index.html', user=current_user, tasks=tasks, items=items)

@main.route('/api/events')
@login_required
def api_events():
    items = PlannerItem.query.filter_by(user_id=current_user.id).all()
    events = [
        {'title': item.text, 'start': item.appointment_date.isoformat()}
        for item in items
    ]
    return jsonify(events)

@main.route('/chat', methods=['POST'])
@login_required
def chat():
    user_message = request.json['message']
    user_condition = current_user.condition
    prompt = f"""
    You are 'VitalSync Assistant,' a supportive AI health companion for condition '{user_condition}'.
    **RULES:** NEVER provide medical advice. NEVER mention medications. ALWAYS end with a disclaimer to consult a doctor.
    The user's question is: "{user_message}"
    """
    try:
        response = model.generate_content(prompt)
        ai_reply = response.text
    except Exception:
        ai_reply = "Sorry, I'm having trouble connecting right now. Please try again later."
    return jsonify({'reply': ai_reply})

@main.route('/download_report')
@login_required
def download_report():
    html = render_template('report_pdf.html', user=current_user)
    return render_pdf(HTML(string=html))

@main.route('/download_planner')
@login_required
def download_planner():
    items = PlannerItem.query.filter_by(user_id=current_user.id).order_by(PlannerItem.appointment_date.asc()).all()
    html = render_template('planner_pdf.html', user=current_user, items=items)
    return render_pdf(HTML(string=html))

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

@main.route('/add_task', methods=['POST'])
@login_required
def add_task():
    task_text = request.form.get('task')
    if task_text.strip() and DailyTask.query.filter_by(user_id=current_user.id).count() < 15:
        new_task = DailyTask(text=task_text, owner=current_user)
        db.session.add(new_task)
        db.session.commit()
    return redirect(url_for('main.home'))

@main.route('/delete_task/<int:task_id>')
@login_required
def delete_task(task_id):
    task = DailyTask.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('main.home'))

@main.route('/toggle_task/<int:task_id>')
@login_required
def toggle_task(task_id):
    task = DailyTask.query.filter_by(id=task_id, user_id=current_user.id).first_or_404()
    task.done = not task.done
    db.session.commit()
    return redirect(url_for('main.home'))

@main.route('/reset_tasks')
@login_required
def reset_tasks():
    DailyTask.query.filter_by(user_id=current_user.id).update({DailyTask.done: False})
    db.session.commit()
    return redirect(url_for('main.home'))