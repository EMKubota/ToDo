from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import datetime
from plyer import notification
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build  # Added import for build
import os.path

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///example.sqlite"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100))
    notes = db.Column(db.Text)
    priority = db.Column(db.String(50))
    due_date = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return "<Task %r>" % self.id

def get_google_calendar_service():
    """Shows basic usage of the Google Calendar API.
    Returns service for interacting with the Google Calendar API.
    """
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build_calendar_service(creds)
    pass

def build_calendar_service(creds):
    return build('calendar', 'v3', credentials=creds)
    pass

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        task = request.form['task']
        category = request.form['category']
        notes = request.form['notes']
        due_date_str = request.form['due_date']
        due_date = datetime.datetime.strptime(due_date_str, "%Y-%m-%d %H:%M") if due_date_str else None

        new_task = Task(task=task, category=category, notes=notes, due_date=due_date)
        db.session.add(new_task)
        db.session.commit()

        send_notification(task, due_date)

        add_event_to_calendar(task, due_date)

    tasks = Task.query.all()  # Fetch all tasks from the database
    return render_template('index.html', tasks=tasks)  # Pass tasks as tasks=tasks
    pass

@app.route('/search', methods=['GET'])
def search():
    search_category = request.args.get('search_category', '').lower()
    if search_category:
        filtered_tasks = Task.query.filter(Task.category.ilike(f'%{search_category}%')).all()
        return render_template('index.html', tasks=filtered_tasks)
    return redirect(url_for('index'))
    pass

def send_notification(task, due_date):
    if due_date:
        notification_title = f"Task Reminder: {task}"
        notification_message = f"Due on {due_date.strftime('%Y-%m-%d %H:%M')}"
        notification.notify(title=notification_title,
            message=notification_message,
            app_name='Todo App',
        )
        pass

def add_event_to_calendar(task, due_date):
    if due_date:
        service = get_google_calendar_service()
        event = {
            'summary': task.task,
            'description': f"Category: {task.category}\nNotes: {task.notes}",
            'start': {
                'dateTime': due_date.strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': (due_date + datetime.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%S'),
                'timeZone': 'UTC',
            },
        }
        service.events().insert(calendarId='primary', body=event).execute()
        pass

@app.route('/update/<int:id>', methods=['POST'])
def update_task(id):
    task = Task.query.get_or_404(id)
    if request.method == 'POST':
        status = request.form.get('status')
        if status == 'complete':
            task.completed = True
        elif status == 'not_completed':
            task.completed = False
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>', methods=['POST'])
def delete_task(id):
    task = Task.query.get_or_404(id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('index'))
    pass

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
