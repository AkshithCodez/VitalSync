from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from flask_login import login_required, current_user
from .models import PlannerItem, User, VitalsLog
from . import db
import google.generativeai as genai
import os
import re
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
            prompt = f"Generate a supportive health summary for a user diagnosed with {user.condition}. Include sections on understanding the condition, potential consequences, supportive non-prescription measures, and beneficial nutrients. Do NOT give medical advice or mention specific medications. Format section titles with markdown bolding (e.g., **Title**)."
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

@main.route('/yoga')
@login_required
def yoga():
    # The data now points to our local image files
    yoga_asanas = [
        {'name': 'Downward-Facing Dog (Adho Mukha Svanasana)', 'img': 'downward_dog.jpg', 'desc': 'A foundational pose that calms the brain and energizes the body.'},
        {'name': 'Warrior II (Virabhadrasana II)', 'img': 'warrior_2.jpg', 'desc': 'Strengthens the legs and ankles while increasing stamina.'},
        {'name': 'Triangle Pose (Trikonasana)', 'img': 'triangle_pose.jpg', 'desc': 'Stretches the legs, hips, and spine, while stimulating abdominal organs.'},
        {'name': 'Mountain Pose (Tadasana)', 'img': 'mountain_pose.jpg', 'desc': 'Improves balance, focus, and strengthens the thighs and calves.'},
        {'name': 'Tree Pose (Vrksasana)', 'img': 'tree_pose.jpg', 'desc': 'Stretches the chest, neck, and spine. Calms the body and mind.'},
        {'name': 'Cobra Pose (Bhujangasana)', 'img': 'cobra_pose.jpg', 'desc': 'Increases spinal flexibility and strengthens the back muscles.'},
        {'name': 'Bridge Pose (Setu Bandhasana)', 'img': 'bridge_pose.jpg', 'desc': 'A gentle resting pose that calms the mind and relieves stress.'},
    ]
    return render_template('yoga.html', user=current_user, asanas=yoga_asanas)

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
    
    ranges = {
        "Blood Sugar": {"high": 180, "low": 70},
        "Blood Pressure": {"high": 130, "low": 90},
        "Heart Rate": {"high": 100, "low": 60},
        "Sleep": {"high": 9, "low": 7},
    }
    
    labels = [log.date.strftime('%Y-%m-%d') for log in logs]
    datasets = []
    
    if metric == "Blood Pressure":
        systolic_data = []
        diastolic_data = []
        for log in logs:
            try:
                parts = re.split(r'[/ ]', log.metric_value)
                if len(parts) >= 2:
                    systolic_data.append(float(parts[0]))
                    diastolic_data.append(float(parts[1]))
            except (ValueError, TypeError, IndexError):
                continue
        datasets.append({'label': 'Systolic', 'data': systolic_data, 'borderColor': '#e53e3e'})
        datasets.append({'label': 'Diastolic', 'data': diastolic_data, 'borderColor': '#3182ce'})
    else:
        data = []
        for log in logs:
            try:
                data.append(float(log.metric_value))
            except (ValueError, TypeError):
                continue
        datasets.append({'label': metric, 'data': data, 'borderColor': '#3182ce'})

    return jsonify({
        'labels': labels, 
        'datasets': datasets,
        'ranges': ranges.get(metric, {"high": None, "low": None})
    })

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