from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required, current_user
from .models import DailyTask, PlannerItem, User
from . import db
import google.generativeai as genai
import os

main = Blueprint('main', __name__)

genai.configure(api_key=os.getenv("Enter API KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

@main.route('/')
@login_required
def home():
    tasks = DailyTask.query.filter_by(user_id=current_user.id).all()
    items = PlannerItem.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', user=current_user, tasks=tasks, items=items)

@main.route('/disclaimer')
@login_required
def disclaimer():
    return render_template('disclaimer.html')

@main.route('/generate_report')
@login_required
def generate_report():
    user = current_user
    if not user.ai_report and user.condition:
        prompt = f"""
        You are a helpful health information assistant. Your goal is to provide a general, supportive summary of a health condition for a user who has already been diagnosed by a doctor.

        **IMPORTANT RULES:**
        1.  **DO NOT** provide medical advice.
        2.  **DO NOT** prescribe, mention, or recommend any specific medications or dosages.
        3.  **DO NOT** suggest specific treatments. You can only speak about general treatment approaches (e.g., 'management often involves...').
        4.  You **CAN** recommend general vitamins, nutrients, and healthy lifestyle choices (like diet and exercise) that are known to support the management of the condition.
        5.  Use simple, clear, and encouraging language. The output should be formatted as plain text.

        The user's diagnosed condition is: "{user.condition}"

        Please generate a report with three sections titled "Understanding Your Condition", "Potential Consequences", and "Supporting Your Health".
        """
        try:
            response = model.generate_content(prompt)
            user.ai_report = response.text
            db.session.commit()
        except Exception as e:
            user.ai_report = f"Sorry, there was an error generating the report. Please try again later. Error: {e}"
            db.session.commit()
    return render_template('report.html', user=user)

@main.route('/add_item', methods=['POST'])
@login_required
def add_item():
    item_text = request.form.get('item')
    if item_text.strip():
        new_item = PlannerItem(text=item_text, owner=current_user)
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