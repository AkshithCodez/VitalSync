from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from .models import DailyTask, PlannerItem, User
from . import db
import google.generativeai as genai
import os
from . import create_app
from flask_weasyprint import HTML, render_pdf

main = Blueprint('main', __name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

def generate_report_in_background(user_id):
    app = create_app()
    with app.app_context():
        user = User.query.get(user_id)
        if not user.ai_report and user.condition:
            prompt = f"""
            You are a helpful health information assistant. Your goal is to provide a general, supportive summary of a health condition for a user who has already been diagnosed by a doctor.

            **IMPORTANT RULES:**
            1.  **DO NOT** provide medical advice.
            2.  **DO NOT** prescribe, mention, or recommend any specific pharmaceutical drugs, dosages, or brand names.
            3.  You **CAN** mention common, publicly known active ingredients (like 'minoxidil'), but you **MUST** frame them as topics for the user to "discuss with their doctor", not as a direct recommendation.
            4.  You **CAN** suggest common, safe, non-prescription home-remedy-style actions for temporary relief.
            5.  You **CAN** recommend general vitamins, nutrients, and healthy lifestyle choices (like diet and exercise) that are known to support the management of the condition.
            6.  Use simple, clear, and encouraging language. The output should be formatted as plain text.

            The user's diagnosed condition is: "{user.condition}"

            Please generate a report with the following sections: "Understanding Your Condition", "Potential Consequences", "Supportive Measures for Comfort", "Beneficial Nutrients & Lifestyle", and "Topics to Discuss With Your Doctor".
            """
            try:
                response = model.generate_content(prompt)
                user.ai_report = response.text
                db.session.commit()
            except Exception as e:
                user.ai_report = f"Sorry, there was an error generating the report. Please try again later. Error: {e}"
                db.session.commit()

@main.route('/')
@login_required
def home():
    tasks = DailyTask.query.filter_by(user_id=current_user.id).all()
    items = PlannerItem.query.filter_by(user_id=current_user.id).all()
    return render_template('index.html', user=current_user, tasks=tasks, items=items)


# --- THIS IS THE MISSING FUNCTION TO ADD ---
@main.route('/download_report')
@login_required
def download_report():
    html = render_template('report_pdf.html', user=current_user)
    return render_pdf(HTML(string=html))
# --- END OF NEW FUNCTION ---


@main.route('/chat', methods=['POST'])
@login_required
def chat():
    user_message = request.json['message']
    user_condition = current_user.condition

    prompt = f"""
    You are 'VitalSync Assistant,' a supportive and informational AI health companion. 
    Your role is to help a user understand their diagnosed health condition: '{user_condition}'.
    
    **Your most important rules are:**
    1.  **NEVER** provide medical advice.
    2.  **NEVER** suggest, recommend, or mention any specific medications (prescription or over-the-counter), brands, or dosages.
    3.  **NEVER** diagnose any condition.
    4.  **ALWAYS** end your response with a clear disclaimer to consult a healthcare professional for any medical advice.
    5.  You **CAN** explain concepts, symptoms, and general lifestyle/nutrition in relation to their condition.
    
    The user's question is: "{user_message}"
    """

    try:
        response = model.generate_content(prompt)
        ai_reply = response.text
    except Exception:
        ai_reply = "Sorry, I'm having trouble connecting to my knowledge base right now. Please try again later."
    
    return jsonify({'reply': ai_reply})

@main.route('/download_planner')
@login_required
def download_planner():
    items = PlannerItem.query.filter_by(user_id=current_user.id).all()
    html = render_template('planner_pdf.html', user=current_user, items=items)
    return render_pdf(HTML(string=html))

# ... The rest of the file (add_item, delete_item, etc.) remains the same
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