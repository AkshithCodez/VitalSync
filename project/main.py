from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from .models import PlannerItem, User, VitalsLog
from . import db
import google.generativeai as genai
import os
import re # Import for text replacement
from . import create_app
from flask_weasyprint import HTML, render_pdf
from datetime import datetime

main = Blueprint('main', __name__)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
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
            5.  Use simple, clear, and encouraging language.
            6.  **Format all section titles with markdown bolding (e.g., **Section Title**).**

            The user's diagnosed condition is: "{user.condition}"

            Please generate a report with the following sections: **Understanding Your Condition**, **Potential Consequences**, **Supportive Measures for Comfort**, and **Beneficial Nutrients & Lifestyle**.
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
    labels = [log.date.strftime('%Y-%m-%d') for log in logs]
    data = [float(log.metric_value) for log in logs if log.metric_value.replace('.', '', 1).isdigit()]
    return jsonify({'labels': labels, 'data': data})

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
        ai_reply = "Sorry, I'm having trouble connecting to my knowledge base right now."
    return jsonify({'reply': ai_reply})

@main.route('/download_report')
@login_required
def download_report():
    report_text = current_user.ai_report or ""
    # Convert markdown bold to HTML strong tags for the PDF
    report_html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', report_text)
    
    html = render_template('report_pdf.html', user=current_user, report_html=report_html)
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