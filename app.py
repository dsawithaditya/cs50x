import os
import random
import string
from functools import wraps
from flask import Flask, flash, redirect, render_template, request, session, url_for, send_from_directory
from flask_session import Session
from cs50 import SQL
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///classconnect.db")

# Ensure faculty_directory table exists (for existing databases)
db.execute("""
    CREATE TABLE IF NOT EXISTS faculty_directory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subject TEXT,
        phone TEXT,
        cabinet TEXT,
        email TEXT,
        created_by INTEGER,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(created_by) REFERENCES users(id)
    )
""")

# Setup upload folder
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

def login_required(f):
    """
    Decorate routes to require login.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    """
    Decorate routes to require teacher role.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != 'teacher':
            flash("You must be a teacher to access this page.", "danger")
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
@login_required
def index():
    now = datetime.now()
    default_academic_year = f"{now.year}-{now.year + 1}"
    default_date = now.strftime("%Y-%m-%d")
    current_day = now.strftime("%A")

    if session["role"] == "teacher":
        # Teacher dashboard - load classes with enrollment count
        classes = db.execute("""
            SELECT classes.*, COUNT(enrollments.student_id) AS student_count
            FROM classes
            LEFT JOIN enrollments ON classes.id = enrollments.class_id
            WHERE classes.teacher_id = ?
            GROUP BY classes.id
            ORDER BY classes.id DESC
        """, session["user_id"])

        # Fetch pending ungraded submissions across teacher's classes
        pending_submissions = db.execute("""
            SELECT submissions.id, submissions.submitted_at, users.name AS student_name, users.username AS student_username,
                   assignments.title AS assignment_title, assignments.id AS assignment_id, classes.name AS class_name
            FROM submissions
            JOIN assignments ON submissions.assignment_id = assignments.id
            JOIN classes ON assignments.class_id = classes.id
            JOIN users ON submissions.student_id = users.id
            WHERE classes.teacher_id = ? AND submissions.grade IS NULL
            ORDER BY submissions.submitted_at ASC
            LIMIT 6
        """, session["user_id"])

        # Fetch today's schedule slots for teacher
        today_schedule = db.execute("""
            SELECT timetable.*, classes.name AS class_name, classes.subject, classes.room
            FROM timetable
            JOIN classes ON timetable.class_id = classes.id
            WHERE classes.teacher_id = ? AND timetable.day_of_week = ?
            ORDER BY timetable.start_time ASC
        """, session["user_id"], current_day)

        # Assignment and Quiz counts
        stats = {
            "total_classes": len(classes),
            "pending_grading": len(pending_submissions),
            "today_slots": len(today_schedule)
        }

        return render_template("teacher_dashboard.html", 
                               classes=classes, 
                               default_academic_year=default_academic_year, 
                               default_date=default_date,
                               pending_submissions=pending_submissions,
                               today_schedule=today_schedule,
                               current_day=current_day,
                               stats=stats)
    else:
        # Student dashboard - load classes with teacher details
        classes = db.execute("""
            SELECT classes.*, users.name AS teacher_name, users.username AS teacher_username
            FROM classes
            JOIN enrollments ON classes.id = enrollments.class_id
            JOIN users ON classes.teacher_id = users.id
            WHERE enrollments.student_id = ?
            ORDER BY classes.id DESC
        """, session["user_id"])

        # Fetch upcoming assignments with student's submission status
        upcoming_assignments = db.execute("""
            SELECT assignments.*, classes.name AS class_name,
                   submissions.id AS submission_id, submissions.grade, submissions.submitted_at
            FROM assignments
            JOIN classes ON assignments.class_id = classes.id
            JOIN enrollments ON classes.id = enrollments.class_id
            LEFT JOIN submissions ON assignments.id = submissions.assignment_id AND submissions.student_id = ?
            WHERE enrollments.student_id = ?
            ORDER BY CASE WHEN assignments.due_date IS NULL THEN 1 ELSE 0 END, assignments.due_date ASC
            LIMIT 6
        """, session["user_id"], session["user_id"])

        # Fetch today's schedule slots for student
        today_schedule = db.execute("""
            SELECT timetable.*, classes.name AS class_name, classes.subject, classes.room
            FROM timetable
            JOIN classes ON timetable.class_id = classes.id
            JOIN enrollments ON classes.id = enrollments.class_id
            WHERE enrollments.student_id = ? AND timetable.day_of_week = ?
            ORDER BY timetable.start_time ASC
        """, session["user_id"], current_day)

        return render_template("student_dashboard.html", 
                               classes=classes,
                               upcoming_assignments=upcoming_assignments,
                               today_schedule=today_schedule,
                               current_day=current_day)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
            flash("Must provide username", "warning")
            return render_template("login.html")
        elif not password:
            flash("Must provide password", "warning")
            return render_template("login.html")

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            flash("Invalid username and/or password", "danger")
            return render_template("login.html")

        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]
        session["role"] = rows[0]["role"]

        return redirect("/")

    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        role = request.form.get("role")

        if not username or not password or not confirmation or not role:
            flash("All fields are required.", "warning")
            return render_template("register.html")
        if password != confirmation:
            flash("Passwords must match.", "warning")
            return render_template("register.html")
        if role not in ["teacher", "student"]:
            flash("Invalid role selected.", "danger")
            return render_template("register.html")

        hash_pw = generate_password_hash(password)
        try:
            user_id = db.execute("INSERT INTO users (username, hash, role) VALUES (?, ?, ?)", username, hash_pw, role)
        except ValueError:
            flash("Username already taken.", "danger")
            return render_template("register.html")

        session["user_id"] = user_id
        session["username"] = username
        session["role"] = role
        flash("Registered successfully!", "success")
        return redirect("/")
    else:
        return render_template("register.html")

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    """Reset forgotten password"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        role = request.form.get("role", "").strip()
        new_password = request.form.get("new_password", "")
        confirmation = request.form.get("confirmation", "")

        if not username or not role or not new_password or not confirmation:
            flash("All fields are required.", "warning")
            return render_template("forgot_password.html")

        if new_password != confirmation:
            flash("Passwords must match.", "warning")
            return render_template("forgot_password.html")

        if role not in ["teacher", "student"]:
            flash("Please select a valid account role.", "danger")
            return render_template("forgot_password.html")

        # Verify account exists
        user = db.execute("SELECT * FROM users WHERE username = ? AND role = ?", username, role)
        if len(user) != 1:
            flash("No account found with matching username and role.", "danger")
            return render_template("forgot_password.html")

        # Hash and update new password
        hash_pw = generate_password_hash(new_password)
        db.execute("UPDATE users SET hash = ? WHERE id = ?", hash_pw, user[0]["id"])

        flash("Password reset successfully! Please log in with your new password.", "success")
        return redirect("/login")
    else:
        return render_template("forgot_password.html")

@app.route("/create_class", methods=["POST"])
@login_required
@teacher_required
def create_class():
    class_name = request.form.get("class_name", "").strip()
    subject = request.form.get("subject", "").strip()
    semester = request.form.get("semester", "").strip()
    academic_year = request.form.get("academic_year", "").strip()
    created_at = request.form.get("created_at", "").strip()
    section = request.form.get("section", "").strip()
    room = request.form.get("room", "").strip()

    if not class_name:
        flash("Must provide a class name.", "warning")
        return redirect("/")
    
    if not created_at:
        created_at = datetime.now().strftime("%Y-%m-%d")
        
    if not academic_year:
        year = datetime.now().year
        academic_year = f"{year}-{year + 1}"

    # Generate unique random 6 character code
    while True:
        join_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        existing = db.execute("SELECT id FROM classes WHERE join_code = ?", join_code)
        if not existing:
            break
    
    db.execute(
        """
        INSERT INTO classes (name, teacher_id, join_code, subject, semester, academic_year, created_at, section, room)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        class_name, session["user_id"], join_code, subject, semester, academic_year, created_at, section, room
    )
    flash(f"Class '{class_name}' created successfully! Join code: {join_code}", "success")
    return redirect("/")

@app.route("/join_class", methods=["POST"])
@login_required
def join_class():
    if session["role"] != "student":
        flash("Only students can join classes.", "danger")
        return redirect("/")
        
    join_code = request.form.get("join_code")
    if not join_code:
        flash("Must provide a join code.", "warning")
        return redirect("/")
        
    # Find class
    class_info = db.execute("SELECT * FROM classes WHERE join_code = ?", join_code)
    if len(class_info) == 0:
        flash("Invalid join code.", "danger")
        return redirect("/")
        
    class_id = class_info[0]["id"]
    
    # Check if already enrolled
    enrolled = db.execute("SELECT * FROM enrollments WHERE student_id = ? AND class_id = ?", session["user_id"], class_id)
    if len(enrolled) > 0:
        flash("Already enrolled in this class.", "info")
        return redirect("/")
        
    db.execute("INSERT INTO enrollments (student_id, class_id) VALUES (?, ?)", session["user_id"], class_id)
    flash("Successfully joined class!", "success")
    return redirect("/")

@app.route("/class/<int:class_id>")
@login_required
def class_view(class_id):
    # Verify access
    if session["role"] == "teacher":
        class_info = db.execute("SELECT * FROM classes WHERE id = ? AND teacher_id = ?", class_id, session["user_id"])
        if len(class_info) == 0:
            flash("Class not found or unauthorized.", "danger")
            return redirect("/")
    else:
        class_info = db.execute("SELECT classes.* FROM classes JOIN enrollments ON classes.id = enrollments.class_id WHERE classes.id = ? AND enrollments.student_id = ?", class_id, session["user_id"])
        if len(class_info) == 0:
            flash("Class not found or unauthorized.", "danger")
            return redirect("/")
            
    c_info = class_info[0]

    # Fetch announcements with their nested comments
    announcements = db.execute("SELECT * FROM announcements WHERE class_id = ? ORDER BY timestamp DESC", class_id)
    for a in announcements:
        a["comments"] = db.execute("""
            SELECT comments.*, users.username, users.name, users.role
            FROM comments
            JOIN users ON comments.user_id = users.id
            WHERE comments.announcement_id = ?
            ORDER BY comments.created_at ASC
        """, a["id"])

    # Fetch materials
    materials = db.execute("SELECT * FROM materials WHERE class_id = ? ORDER BY upload_time DESC", class_id)

    # Fetch assignments
    if session["role"] == "teacher":
        assignments = db.execute("""
            SELECT assignments.*,
                   COUNT(submissions.id) AS submission_count,
                   SUM(CASE WHEN submissions.grade IS NOT NULL THEN 1 ELSE 0 END) AS graded_count
            FROM assignments
            LEFT JOIN submissions ON assignments.id = submissions.assignment_id
            WHERE assignments.class_id = ?
            GROUP BY assignments.id
            ORDER BY assignments.created_at DESC
        """, class_id)
    else:
        assignments = db.execute("""
            SELECT assignments.*,
                   submissions.id AS submission_id, submissions.grade, submissions.submitted_at, submissions.feedback
            FROM assignments
            LEFT JOIN submissions ON assignments.id = submissions.assignment_id AND submissions.student_id = ?
            WHERE assignments.class_id = ?
            ORDER BY assignments.created_at DESC
        """, session["user_id"], class_id)

    # Fetch quizzes
    if session["role"] == "teacher":
        quizzes = db.execute("""
            SELECT quizzes.*,
                   COUNT(quiz_attempts.id) AS attempt_count,
                   (SELECT COUNT(*) FROM quiz_questions WHERE quiz_questions.quiz_id = quizzes.id) AS question_count
            FROM quizzes
            LEFT JOIN quiz_attempts ON quizzes.id = quiz_attempts.quiz_id
            WHERE quizzes.class_id = ?
            GROUP BY quizzes.id
            ORDER BY quizzes.created_at DESC
        """, class_id)
    else:
        quizzes = db.execute("""
            SELECT quizzes.*,
                   quiz_attempts.id AS attempt_id, quiz_attempts.score, quiz_attempts.total_points, quiz_attempts.submitted_at,
                   (SELECT COUNT(*) FROM quiz_questions WHERE quiz_questions.quiz_id = quizzes.id) AS question_count
            FROM quizzes
            LEFT JOIN quiz_attempts ON quizzes.id = quiz_attempts.quiz_id AND quiz_attempts.student_id = ?
            WHERE quizzes.class_id = ?
            ORDER BY quizzes.created_at DESC
        """, session["user_id"], class_id)

    # Fetch timetable slots for this class
    timetable_slots = db.execute("""
        SELECT * FROM timetable WHERE class_id = ? ORDER BY 
        CASE day_of_week
            WHEN 'Monday' THEN 1
            WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3
            WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5
            WHEN 'Saturday' THEN 6
            WHEN 'Sunday' THEN 7
            ELSE 8
        END, start_time ASC
    """, class_id)

    # Enrolled students count & list
    students = db.execute("""
        SELECT users.id, users.username, users.name, users.application_number, users.branch, users.classroom
        FROM users
        JOIN enrollments ON users.id = enrollments.student_id
        WHERE enrollments.class_id = ?
        ORDER BY COALESCE(users.name, users.username) ASC
    """, class_id)

    active_tab = request.args.get("tab", "stream")

    return render_template("class_view.html", 
                           class_info=c_info, 
                           announcements=announcements, 
                           materials=materials,
                           assignments=assignments,
                           quizzes=quizzes,
                           timetable_slots=timetable_slots,
                           students=students,
                           active_tab=active_tab)

@app.route("/class/<int:class_id>/announce", methods=["POST"])
@login_required
@teacher_required
def announce(class_id):
    # Verify ownership
    class_info = db.execute("SELECT * FROM classes WHERE id = ? AND teacher_id = ?", class_id, session["user_id"])
    if len(class_info) == 0:
        return redirect("/")
        
    text = request.form.get("text")
    if text:
        db.execute("INSERT INTO announcements (class_id, text) VALUES (?, ?)", class_id, text)
        flash("Announcement posted.", "success")
    
    return redirect(url_for('class_view', class_id=class_id, tab='stream'))

@app.route("/class/<int:class_id>/upload", methods=["POST"])
@login_required
@teacher_required
def upload(class_id):
    # Verify ownership
    class_info = db.execute("SELECT * FROM classes WHERE id = ? AND teacher_id = ?", class_id, session["user_id"])
    if len(class_info) == 0:
        return redirect("/")
        
    if 'material' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('class_view', class_id=class_id, tab='materials'))
        
    file = request.files['material']
    if file.filename == '':
        flash('No selected file', 'warning')
        return redirect(url_for('class_view', class_id=class_id, tab='materials'))
        
    if file:
        filename = secure_filename(file.filename)
        # Make a unique filename to avoid overwrites
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        db.execute("INSERT INTO materials (class_id, filename, file_path) VALUES (?, ?, ?)", class_id, filename, unique_filename)
        flash("Material uploaded successfully.", "success")
        
    return redirect(url_for('class_view', class_id=class_id, tab='materials'))

@app.route("/class/<int:class_id>/attendance", methods=["GET", "POST"])
@login_required
@teacher_required
def attendance(class_id):
    class_info = db.execute("SELECT * FROM classes WHERE id = ? AND teacher_id = ?", class_id, session["user_id"])
    if len(class_info) == 0:
        return redirect("/")
        
    if request.method == "POST":
        date = request.form.get("date")
        if not date:
            flash("Must provide a date.", "warning")
            return redirect(url_for('attendance', class_id=class_id))
            
        students = db.execute("SELECT users.id FROM users JOIN enrollments ON users.id = enrollments.student_id WHERE enrollments.class_id = ?", class_id)
        
        for student in students:
            status = request.form.get(f"status_{student['id']}")
            if status in ['Present', 'Absent', 'Late']:
                # Upsert basically: delete existing for that date then insert
                db.execute("DELETE FROM attendance WHERE class_id = ? AND student_id = ? AND date = ?", class_id, student["id"], date)
                db.execute("INSERT INTO attendance (class_id, student_id, date, status) VALUES (?, ?, ?, ?)", class_id, student["id"], date, status)
                
        flash(f"Attendance for {date} saved successfully.", "success")
        return redirect(url_for('attendance', class_id=class_id, date=date))
        
    else:
        selected_date = request.args.get("date", datetime.today().strftime('%Y-%m-%d'))
        students = db.execute(
            "SELECT users.id, users.username, users.name, users.application_number, users.branch, users.classroom, users.mobile_no "
            "FROM users JOIN enrollments ON users.id = enrollments.student_id "
            "WHERE enrollments.class_id = ? "
            "ORDER BY COALESCE(users.name, users.username) ASC", 
            class_id
        )
        
        # Fetch existing attendance for selected date
        records = db.execute("SELECT student_id, status FROM attendance WHERE class_id = ? AND date = ?", class_id, selected_date)
        status_map = {r["student_id"]: r["status"] for r in records}
        for s in students:
            s["status"] = status_map.get(s["id"], "")
            
        # Fetch dates where attendance was taken
        dates_rows = db.execute("SELECT DISTINCT date FROM attendance WHERE class_id = ? ORDER BY date DESC", class_id)
        return render_template("attendance.html", class_info=class_info[0], students=students, dates=dates_rows, selected_date=selected_date)

@app.route("/class/<int:class_id>/add_student", methods=["POST"])
@login_required
@teacher_required
def add_student(class_id):
    # Verify ownership
    class_info = db.execute("SELECT * FROM classes WHERE id = ? AND teacher_id = ?", class_id, session["user_id"])
    if len(class_info) == 0:
        return redirect("/")
        
    name = request.form.get("name", "").strip()
    application_number = request.form.get("application_number", "").strip()
    branch = request.form.get("branch", "").strip()
    classroom = request.form.get("classroom", "").strip()
    mobile_no_raw = request.form.get("mobile_no", "").strip()
    
    if not name or not application_number:
        flash("Student Name and Application Number are required.", "warning")
        return redirect(url_for('attendance', class_id=class_id))
        
    mobile_no = None
    if mobile_no_raw:
        digits = ''.join(c for c in mobile_no_raw if c.isdigit())
        if digits:
            try:
                mobile_no = int(digits)
            except ValueError:
                mobile_no = None
                
    # Check if student exists in users table
    existing_user = db.execute("SELECT * FROM users WHERE application_number = ? OR username = ?", application_number, application_number)
    
    if len(existing_user) > 0:
        student_id = existing_user[0]["id"]
        db.execute(
            "UPDATE users SET name = ?, application_number = ?, branch = ?, classroom = ?, mobile_no = ? WHERE id = ?",
            name, application_number, branch, classroom, mobile_no, student_id
        )
    else:
        # Default password hash for new student
        default_hash = generate_password_hash(application_number)
        student_id = db.execute(
            "INSERT INTO users (username, hash, role, name, application_number, branch, classroom, mobile_no) VALUES (?, ?, 'student', ?, ?, ?, ?, ?)",
            application_number, default_hash, name, application_number, branch, classroom, mobile_no
        )
        
    # Check if enrolled
    enrolled = db.execute("SELECT * FROM enrollments WHERE student_id = ? AND class_id = ?", student_id, class_id)
    if len(enrolled) == 0:
        db.execute("INSERT INTO enrollments (student_id, class_id) VALUES (?, ?)", student_id, class_id)
        flash(f"Student '{name}' (App No: {application_number}) added to class attendance roster!", "success")
    else:
        flash(f"Student '{name}' (App No: {application_number}) details updated.", "info")
        
    return redirect(url_for('attendance', class_id=class_id))

@app.route("/class/<int:class_id>/remove_student/<int:student_id>", methods=["POST"])
@login_required
@teacher_required
def remove_student(class_id, student_id):
    # Verify ownership
    class_info = db.execute("SELECT * FROM classes WHERE id = ? AND teacher_id = ?", class_id, session["user_id"])
    if len(class_info) == 0:
        return redirect("/")
        
    db.execute("DELETE FROM enrollments WHERE student_id = ? AND class_id = ?", student_id, class_id)
    db.execute("DELETE FROM attendance WHERE student_id = ? AND class_id = ?", student_id, class_id)
    flash("Student removed from class attendance roster.", "info")
    return redirect(url_for('attendance', class_id=class_id))


@app.route("/class/<int:class_id>/my_attendance")
@login_required
def my_attendance(class_id):
    if session["role"] != "student":
        return redirect("/")
        
    class_info = db.execute("SELECT classes.* FROM classes JOIN enrollments ON classes.id = enrollments.class_id WHERE classes.id = ? AND enrollments.student_id = ?", class_id, session["user_id"])
    if len(class_info) == 0:
        return redirect("/")
        
    records = db.execute("SELECT date, status FROM attendance WHERE class_id = ? AND student_id = ? ORDER BY date DESC", class_id, session["user_id"])
    
    total = len(records)
    present = sum(1 for r in records if r["status"] == "Present")
    late = sum(1 for r in records if r["status"] == "Late")
    # Let's count Late as Present or half? Let's just show counts.
    
    return render_template("student_attendance.html", class_info=class_info[0], records=records, total=total, present=present, late=late)

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session["user_id"]
    if request.method == "POST":
        action = request.form.get("action")
        if action == "update_profile":
            name = request.form.get("name", "").strip()
            branch = request.form.get("branch", "").strip()
            classroom = request.form.get("classroom", "").strip()
            mobile_no_raw = request.form.get("mobile_no", "").strip()
            
            mobile_no = None
            if mobile_no_raw:
                digits = ''.join(c for c in mobile_no_raw if c.isdigit())
                if digits:
                    try:
                        mobile_no = int(digits)
                    except ValueError:
                        mobile_no = None
            
            db.execute(
                "UPDATE users SET name = ?, branch = ?, classroom = ?, mobile_no = ? WHERE id = ?",
                name, branch, classroom, mobile_no, user_id
            )
            flash("Profile updated successfully!", "success")
            return redirect(url_for('profile'))
            
        elif action == "change_password":
            current_password = request.form.get("current_password")
            new_password = request.form.get("new_password")
            confirmation = request.form.get("confirmation")
            
            user = db.execute("SELECT hash FROM users WHERE id = ?", user_id)
            if not current_password or not new_password or not confirmation:
                flash("All password fields are required.", "warning")
                return redirect(url_for('profile'))
            if not check_password_hash(user[0]["hash"], current_password):
                flash("Incorrect current password.", "danger")
                return redirect(url_for('profile'))
            if new_password != confirmation:
                flash("New passwords do not match.", "warning")
                return redirect(url_for('profile'))
            if len(new_password) < 4:
                flash("Password must be at least 4 characters long.", "warning")
                return redirect(url_for('profile'))
                
            new_hash = generate_password_hash(new_password)
            db.execute("UPDATE users SET hash = ? WHERE id = ?", new_hash, user_id)
            flash("Password changed successfully!", "success")
            return redirect(url_for('profile'))
            
        return redirect(url_for('profile'))
    else:
        user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
        if session["role"] == "teacher":
            classes = db.execute("SELECT * FROM classes WHERE teacher_id = ?", user_id)
        else:
            classes = db.execute("SELECT classes.* FROM classes JOIN enrollments ON classes.id = enrollments.class_id WHERE enrollments.student_id = ?", user_id)
        return render_template("profile.html", user=user, classes=classes)

@app.route("/announcements", methods=["GET", "POST"])
@login_required
def announcements_feed():
    user_id = session["user_id"]
    role = session["role"]
    
    if role == "teacher":
        user_classes = db.execute("SELECT * FROM classes WHERE teacher_id = ? ORDER BY name ASC", user_id)
    else:
        user_classes = db.execute("SELECT classes.* FROM classes JOIN enrollments ON classes.id = enrollments.class_id WHERE enrollments.student_id = ? ORDER BY classes.name ASC", user_id)
        
    class_ids = [c["id"] for c in user_classes]
    
    if request.method == "POST":
        if role != "teacher":
            flash("Only teachers can post announcements.", "danger")
            return redirect(url_for('announcements_feed'))
            
        target_class_id = request.form.get("class_id")
        text = request.form.get("text", "").strip()
        
        if not text:
            flash("Announcement text cannot be empty.", "warning")
            return redirect(url_for('announcements_feed'))
            
        if target_class_id == "all":
            for c in user_classes:
                db.execute("INSERT INTO announcements (class_id, text) VALUES (?, ?)", c["id"], text)
            flash(f"Announcement posted to all {len(user_classes)} classes!", "success")
        else:
            try:
                cid = int(target_class_id)
                owned = [c for c in user_classes if c["id"] == cid]
                if owned:
                    db.execute("INSERT INTO announcements (class_id, text) VALUES (?, ?)", cid, text)
                    flash(f"Announcement posted to {owned[0]['name']}.", "success")
            except (ValueError, TypeError):
                flash("Invalid class selected.", "warning")
                
        return redirect(url_for('announcements_feed'))
        
    else:
        filter_class = request.args.get("class_id")
        if not class_ids:
            all_announcements = []
        elif filter_class and filter_class.isdigit() and int(filter_class) in class_ids:
            all_announcements = db.execute(
                "SELECT announcements.*, classes.name AS class_name "
                "FROM announcements JOIN classes ON announcements.class_id = classes.id "
                "WHERE announcements.class_id = ? "
                "ORDER BY announcements.timestamp DESC",
                int(filter_class)
            )
        else:
            placeholders = ",".join("?" for _ in class_ids)
            all_announcements = db.execute(
                f"SELECT announcements.*, classes.name AS class_name "
                f"FROM announcements JOIN classes ON announcements.class_id = classes.id "
                f"WHERE announcements.class_id IN ({placeholders}) "
                f"ORDER BY announcements.timestamp DESC",
                *class_ids
            )
            
        return render_template("announcements.html", announcements=all_announcements, classes=user_classes, selected_class=filter_class or "all")

@app.route("/announcement/<int:announcement_id>/delete", methods=["POST"])
@login_required
@teacher_required
def delete_announcement(announcement_id):
    announcement = db.execute(
        "SELECT announcements.id FROM announcements JOIN classes ON announcements.class_id = classes.id WHERE announcements.id = ? AND classes.teacher_id = ?",
        announcement_id, session["user_id"]
    )
    if len(announcement) > 0:
        db.execute("DELETE FROM announcements WHERE id = ?", announcement_id)
        flash("Announcement deleted.", "info")
    else:
        flash("Announcement not found or unauthorized.", "danger")
        
    return redirect(request.referrer or url_for('announcements_feed'))

# ==========================================
# ASSIGNMENTS & SUBMISSIONS
# ==========================================
@app.route("/class/<int:class_id>/assignments/create", methods=["POST"])
@login_required
@teacher_required
def create_assignment(class_id):
    # Verify ownership
    class_info = db.execute("SELECT * FROM classes WHERE id = ? AND teacher_id = ?", class_id, session["user_id"])
    if len(class_info) == 0:
        return redirect("/")
        
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    max_points_raw = request.form.get("max_points", "100").strip()
    due_date = request.form.get("due_date", "").strip()
    
    if not title:
        flash("Assignment title is required.", "warning")
        return redirect(url_for('class_view', class_id=class_id, tab='assignments'))
        
    try:
        max_points = int(max_points_raw)
    except ValueError:
        max_points = 100
        
    unique_filename = None
    if 'assignment_file' in request.files:
        file = request.files['assignment_file']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            unique_filename = f"assign_{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
    db.execute("""
        INSERT INTO assignments (class_id, title, description, max_points, due_date, file_path)
        VALUES (?, ?, ?, ?, ?, ?)
    """, class_id, title, description, max_points, due_date if due_date else None, unique_filename)
    
    flash(f"Assignment '{title}' created successfully.", "success")
    return redirect(url_for('class_view', class_id=class_id, tab='assignments'))

@app.route("/assignment/<int:assignment_id>")
@login_required
def assignment_view(assignment_id):
    assignment_rows = db.execute("""
        SELECT assignments.*, classes.name AS class_name, classes.teacher_id, classes.id AS class_id,
               classes.subject, classes.section
        FROM assignments
        JOIN classes ON assignments.class_id = classes.id
        WHERE assignments.id = ?
    """, assignment_id)
    
    if len(assignment_rows) == 0:
        flash("Assignment not found.", "danger")
        return redirect("/")
        
    assignment = assignment_rows[0]
    class_id = assignment["class_id"]
    
    if session["role"] == "teacher":
        if assignment["teacher_id"] != session["user_id"]:
            flash("Unauthorized access.", "danger")
            return redirect("/")
            
        # Get all enrolled students with their submission records
        students = db.execute("""
            SELECT users.id AS student_id, users.name, users.username, users.application_number,
                   submissions.id AS submission_id, submissions.submission_text, submissions.file_path,
                   submissions.submitted_at, submissions.grade, submissions.feedback, submissions.graded_at
            FROM users
            JOIN enrollments ON users.id = enrollments.student_id
            LEFT JOIN submissions ON submissions.assignment_id = ? AND submissions.student_id = users.id
            WHERE enrollments.class_id = ?
            ORDER BY COALESCE(users.name, users.username) ASC
        """, assignment_id, class_id)
        
        submitted_count = sum(1 for s in students if s["submission_id"] is not None)
        graded_count = sum(1 for s in students if s["grade"] is not None)
        
        return render_template("assignment_view.html",
                               assignment=assignment,
                               students=students,
                               submitted_count=submitted_count,
                               graded_count=graded_count,
                               total_students=len(students))
    else:
        # Check enrollment
        enrolled = db.execute("SELECT * FROM enrollments WHERE student_id = ? AND class_id = ?", session["user_id"], class_id)
        if len(enrolled) == 0:
            flash("You are not enrolled in this class.", "danger")
            return redirect("/")
            
        submission = db.execute("""
            SELECT * FROM submissions WHERE assignment_id = ? AND student_id = ?
        """, assignment_id, session["user_id"])
        
        my_submission = submission[0] if submission else None
        
        return render_template("assignment_view.html",
                               assignment=assignment,
                               my_submission=my_submission)

@app.route("/assignment/<int:assignment_id>/submit", methods=["POST"])
@login_required
def submit_assignment(assignment_id):
    if session["role"] != "student":
        flash("Only students can submit assignments.", "danger")
        return redirect("/")
        
    assignment = db.execute("SELECT * FROM assignments WHERE id = ?", assignment_id)
    if len(assignment) == 0:
        flash("Assignment not found.", "danger")
        return redirect("/")
        
    class_id = assignment[0]["class_id"]
    enrolled = db.execute("SELECT * FROM enrollments WHERE student_id = ? AND class_id = ?", session["user_id"], class_id)
    if len(enrolled) == 0:
        flash("Not enrolled in this class.", "danger")
        return redirect("/")
        
    submission_text = request.form.get("submission_text", "").strip()
    
    unique_filename = None
    if 'submission_file' in request.files:
        file = request.files['submission_file']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            unique_filename = f"sub_{session['user_id']}_{timestamp}_{filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            
    existing = db.execute("SELECT * FROM submissions WHERE assignment_id = ? AND student_id = ?", assignment_id, session["user_id"])
    if existing:
        # Update submission
        if not unique_filename:
            unique_filename = existing[0]["file_path"]
        db.execute("""
            UPDATE submissions
            SET submission_text = ?, file_path = ?, submitted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, submission_text, unique_filename, existing[0]["id"])
        flash("Assignment resubmitted successfully!", "success")
    else:
        db.execute("""
            INSERT INTO submissions (assignment_id, student_id, submission_text, file_path)
            VALUES (?, ?, ?, ?)
        """, assignment_id, session["user_id"], submission_text, unique_filename)
        flash("Assignment submitted successfully!", "success")
        
    return redirect(url_for('assignment_view', assignment_id=assignment_id))

@app.route("/submission/<int:submission_id>/grade", methods=["POST"])
@login_required
@teacher_required
def grade_submission(submission_id):
    sub = db.execute("""
        SELECT submissions.*, assignments.class_id, classes.teacher_id, assignments.id AS assignment_id
        FROM submissions
        JOIN assignments ON submissions.assignment_id = assignments.id
        JOIN classes ON assignments.class_id = classes.id
        WHERE submissions.id = ?
    """, submission_id)
    
    if len(sub) == 0 or sub[0]["teacher_id"] != session["user_id"]:
        flash("Submission not found or unauthorized.", "danger")
        return redirect("/")
        
    grade_raw = request.form.get("grade", "").strip()
    feedback = request.form.get("feedback", "").strip()
    
    try:
        grade = float(grade_raw) if grade_raw else None
    except ValueError:
        flash("Invalid grade value.", "warning")
        return redirect(url_for('assignment_view', assignment_id=sub[0]["assignment_id"]))
        
    db.execute("""
        UPDATE submissions
        SET grade = ?, feedback = ?, graded_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, grade, feedback, submission_id)
    
    flash("Grade and feedback saved successfully.", "success")
    return redirect(url_for('assignment_view', assignment_id=sub[0]["assignment_id"]))

@app.route("/assignment/<int:assignment_id>/delete", methods=["POST"])
@login_required
@teacher_required
def delete_assignment(assignment_id):
    assignment = db.execute("""
        SELECT assignments.*, classes.teacher_id
        FROM assignments
        JOIN classes ON assignments.class_id = classes.id
        WHERE assignments.id = ? AND classes.teacher_id = ?
    """, assignment_id, session["user_id"])
    
    if len(assignment) == 0:
        flash("Assignment not found or unauthorized.", "danger")
        return redirect("/")
        
    class_id = assignment[0]["class_id"]
    db.execute("DELETE FROM submissions WHERE assignment_id = ?", assignment_id)
    db.execute("DELETE FROM assignments WHERE id = ?", assignment_id)
    flash("Assignment deleted.", "info")
    return redirect(url_for('class_view', class_id=class_id, tab='assignments'))

# ==========================================
# DISCUSSION / ANNOUNCEMENT COMMENTS
# ==========================================
@app.route("/announcement/<int:announcement_id>/comment", methods=["POST"])
@login_required
def add_comment(announcement_id):
    announcement = db.execute("SELECT * FROM announcements WHERE id = ?", announcement_id)
    if len(announcement) == 0:
        flash("Announcement not found.", "danger")
        return redirect("/")
        
    class_id = announcement[0]["class_id"]
    # Check access
    if session["role"] == "teacher":
        c_check = db.execute("SELECT * FROM classes WHERE id = ? AND teacher_id = ?", class_id, session["user_id"])
    else:
        c_check = db.execute("SELECT * FROM enrollments WHERE class_id = ? AND student_id = ?", class_id, session["user_id"])
        
    if len(c_check) == 0:
        flash("Unauthorized.", "danger")
        return redirect("/")
        
    text = request.form.get("comment_text", "").strip()
    if text:
        db.execute("INSERT INTO comments (announcement_id, user_id, text) VALUES (?, ?, ?)", announcement_id, session["user_id"], text)
        flash("Comment added.", "success")
        
    return redirect(request.referrer or url_for('class_view', class_id=class_id, tab='stream'))

@app.route("/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    comment = db.execute("""
        SELECT comments.*, announcements.class_id, classes.teacher_id
        FROM comments
        JOIN announcements ON comments.announcement_id = announcements.id
        JOIN classes ON announcements.class_id = classes.id
        WHERE comments.id = ?
    """, comment_id)
    
    if len(comment) == 0:
        flash("Comment not found.", "danger")
        return redirect("/")
        
    c = comment[0]
    # Authorized if commenter or class teacher
    if c["user_id"] == session["user_id"] or (session["role"] == "teacher" and c["teacher_id"] == session["user_id"]):
        db.execute("DELETE FROM comments WHERE id = ?", comment_id)
        flash("Comment deleted.", "info")
    else:
        flash("Unauthorized.", "danger")
        
    return redirect(request.referrer or url_for('class_view', class_id=c["class_id"], tab='stream'))

# ==========================================
# TIMETABLE & SCHEDULE
# ==========================================
@app.route("/timetable")
@login_required
def timetable_view():
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    
    if session["role"] == "teacher":
        classes = db.execute("SELECT * FROM classes WHERE teacher_id = ? ORDER BY name ASC", session["user_id"])
        slots = db.execute("""
            SELECT timetable.*, classes.name AS class_name, classes.subject, classes.room
            FROM timetable
            JOIN classes ON timetable.class_id = classes.id
            WHERE classes.teacher_id = ?
            ORDER BY timetable.start_time ASC
        """, session["user_id"])
    else:
        classes = db.execute("""
            SELECT classes.* FROM classes
            JOIN enrollments ON classes.id = enrollments.class_id
            WHERE enrollments.student_id = ?
            ORDER BY classes.name ASC
        """, session["user_id"])
        slots = db.execute("""
            SELECT timetable.*, classes.name AS class_name, classes.subject, classes.room,
                   users.name AS teacher_name, users.username AS teacher_username
            FROM timetable
            JOIN classes ON timetable.class_id = classes.id
            JOIN users ON classes.teacher_id = users.id
            JOIN enrollments ON classes.id = enrollments.class_id
            WHERE enrollments.student_id = ?
            ORDER BY timetable.start_time ASC
        """, session["user_id"])
        
    # Group slots by day
    timetable_by_day = {day: [] for day in days}
    for s in slots:
        if s["day_of_week"] in timetable_by_day:
            timetable_by_day[s["day_of_week"]].append(s)
            
    return render_template("timetable.html", 
                           days=days, 
                           timetable_by_day=timetable_by_day, 
                           classes=classes)

@app.route("/timetable/add", methods=["POST"])
@login_required
@teacher_required
def add_timetable_slot():
    class_id = request.form.get("class_id")
    day_of_week = request.form.get("day_of_week")
    start_time = request.form.get("start_time", "").strip()
    end_time = request.form.get("end_time", "").strip()
    room_override = request.form.get("room_override", "").strip()
    
    if not class_id or not day_of_week or not start_time or not end_time:
        flash("All schedule fields are required.", "warning")
        return redirect(request.referrer or url_for('timetable_view'))
        
    # Verify class ownership
    c_check = db.execute("SELECT * FROM classes WHERE id = ? AND teacher_id = ?", class_id, session["user_id"])
    if len(c_check) == 0:
        flash("Unauthorized.", "danger")
        return redirect(request.referrer or url_for('timetable_view'))
        
    db.execute("""
        INSERT INTO timetable (class_id, day_of_week, start_time, end_time, room_override)
        VALUES (?, ?, ?, ?, ?)
    """, class_id, day_of_week, start_time, end_time, room_override if room_override else None)
    
    flash("Class schedule slot added successfully.", "success")
    return redirect(request.referrer or url_for('timetable_view'))

@app.route("/timetable/delete/<int:slot_id>", methods=["POST"])
@login_required
@teacher_required
def delete_timetable_slot(slot_id):
    slot = db.execute("""
        SELECT timetable.*, classes.teacher_id
        FROM timetable
        JOIN classes ON timetable.class_id = classes.id
        WHERE timetable.id = ? AND classes.teacher_id = ?
    """, slot_id, session["user_id"])
    
    if len(slot) == 0:
        flash("Slot not found or unauthorized.", "danger")
        return redirect(request.referrer or url_for('timetable_view'))
        
    db.execute("DELETE FROM timetable WHERE id = ?", slot_id)
    flash("Schedule slot removed.", "info")
    return redirect(request.referrer or url_for('timetable_view'))

# ==========================================
# QUIZZES & EXAM MODULE
# ==========================================
@app.route("/class/<int:class_id>/quizzes/create", methods=["POST"])
@login_required
@teacher_required
def create_quiz(class_id):
    class_info = db.execute("SELECT * FROM classes WHERE id = ? AND teacher_id = ?", class_id, session["user_id"])
    if len(class_info) == 0:
        return redirect("/")
        
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    time_limit_raw = request.form.get("time_limit_minutes", "15").strip()
    
    if not title:
        flash("Quiz title is required.", "warning")
        return redirect(url_for('class_view', class_id=class_id, tab='quizzes'))
        
    try:
        time_limit = int(time_limit_raw)
    except ValueError:
        time_limit = 15
        
    quiz_id = db.execute("""
        INSERT INTO quizzes (class_id, title, description, time_limit_minutes)
        VALUES (?, ?, ?, ?)
    """, class_id, title, description, time_limit)
    
    # Process dynamic questions
    q_index = 1
    questions_added = 0
    while True:
        q_text = request.form.get(f"q_{q_index}_text", "").strip()
        if not q_text:
            if q_index > 1:
                break
            # Check if there are more
            if f"q_{q_index+1}_text" in request.form:
                q_index += 1
                continue
            break
            
        opt_a = request.form.get(f"q_{q_index}_a", "").strip()
        opt_b = request.form.get(f"q_{q_index}_b", "").strip()
        opt_c = request.form.get(f"q_{q_index}_c", "").strip()
        opt_d = request.form.get(f"q_{q_index}_d", "").strip()
        correct = request.form.get(f"q_{q_index}_correct", "A").upper()
        points_raw = request.form.get(f"q_{q_index}_points", "1").strip()
        
        try:
            points = int(points_raw)
        except ValueError:
            points = 1
            
        if opt_a and opt_b:
            db.execute("""
                INSERT INTO quiz_questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option, points)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, quiz_id, q_text, opt_a, opt_b, opt_c or "N/A", opt_d or "N/A", correct, points)
            questions_added += 1
            
        q_index += 1
        
    flash(f"Quiz '{title}' created with {questions_added} questions!", "success")
    return redirect(url_for('class_view', class_id=class_id, tab='quizzes'))

@app.route("/quiz/<int:quiz_id>")
@login_required
def quiz_view(quiz_id):
    quiz_rows = db.execute("""
        SELECT quizzes.*, classes.name AS class_name, classes.teacher_id, classes.id AS class_id
        FROM quizzes
        JOIN classes ON quizzes.class_id = classes.id
        WHERE quizzes.id = ?
    """, quiz_id)
    
    if len(quiz_rows) == 0:
        flash("Quiz not found.", "danger")
        return redirect("/")
        
    quiz = quiz_rows[0]
    class_id = quiz["class_id"]
    questions = db.execute("SELECT * FROM quiz_questions WHERE quiz_id = ? ORDER BY id ASC", quiz_id)
    
    if session["role"] == "teacher":
        if quiz["teacher_id"] != session["user_id"]:
            flash("Unauthorized access.", "danger")
            return redirect("/")
            
        attempts = db.execute("""
            SELECT quiz_attempts.*, users.name, users.username, users.application_number
            FROM quiz_attempts
            JOIN users ON quiz_attempts.student_id = users.id
            WHERE quiz_attempts.quiz_id = ?
            ORDER BY quiz_attempts.score DESC
        """, quiz_id)
        
        return render_template("quiz_view.html", quiz=quiz, questions=questions, attempts=attempts)
    else:
        # Check enrollment
        enrolled = db.execute("SELECT * FROM enrollments WHERE student_id = ? AND class_id = ?", session["user_id"], class_id)
        if len(enrolled) == 0:
            flash("Not enrolled in this class.", "danger")
            return redirect("/")
            
        attempt = db.execute("SELECT * FROM quiz_attempts WHERE quiz_id = ? AND student_id = ?", quiz_id, session["user_id"])
        my_attempt = attempt[0] if attempt else None
        
        return render_template("quiz_view.html", quiz=quiz, questions=questions, my_attempt=my_attempt)

@app.route("/quiz/<int:quiz_id>/submit", methods=["POST"])
@login_required
def submit_quiz(quiz_id):
    if session["role"] != "student":
        flash("Only students can take quizzes.", "danger")
        return redirect("/")
        
    quiz = db.execute("SELECT * FROM quizzes WHERE id = ?", quiz_id)
    if len(quiz) == 0:
        flash("Quiz not found.", "danger")
        return redirect("/")
        
    # Check if already submitted
    existing = db.execute("SELECT * FROM quiz_attempts WHERE quiz_id = ? AND student_id = ?", quiz_id, session["user_id"])
    if existing:
        flash("You have already completed this quiz.", "info")
        return redirect(url_for('quiz_view', quiz_id=quiz_id))
        
    questions = db.execute("SELECT * FROM quiz_questions WHERE quiz_id = ?", quiz_id)
    score = 0
    total_points = 0
    
    for q in questions:
        total_points += q["points"]
        student_ans = request.form.get(f"question_{q['id']}", "").upper()
        if student_ans == q["correct_option"]:
            score += q["points"]
            
    db.execute("""
        INSERT INTO quiz_attempts (quiz_id, student_id, score, total_points)
        VALUES (?, ?, ?, ?)
    """, quiz_id, session["user_id"], score, total_points)
    
    pct = round((score / total_points * 100) if total_points > 0 else 0, 1)
    flash(f"Quiz submitted! Your score: {score}/{total_points} ({pct}%)", "success")
    return redirect(url_for('quiz_view', quiz_id=quiz_id))

@app.route("/quiz/<int:quiz_id>/delete", methods=["POST"])
@login_required
@teacher_required
def delete_quiz(quiz_id):
    quiz = db.execute("""
        SELECT quizzes.*, classes.teacher_id
        FROM quizzes
        JOIN classes ON quizzes.class_id = classes.id
        WHERE quizzes.id = ? AND classes.teacher_id = ?
    """, quiz_id, session["user_id"])
    
    if len(quiz) == 0:
        flash("Quiz not found or unauthorized.", "danger")
        return redirect("/")
        
    class_id = quiz[0]["class_id"]
    db.execute("DELETE FROM quiz_attempts WHERE quiz_id = ?", quiz_id)
    db.execute("DELETE FROM quiz_questions WHERE quiz_id = ?", quiz_id)
    db.execute("DELETE FROM quizzes WHERE id = ?", quiz_id)
    flash("Quiz deleted.", "info")
    return redirect(url_for('class_view', class_id=class_id, tab='quizzes'))

# ==========================================
# GLOBAL SEARCH
# ==========================================
@app.route("/search")
@login_required
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return render_template("search_results.html", query="", classes=[], materials=[], announcements=[], assignments=[])
        
    search_term = f"%{query}%"
    user_id = session["user_id"]
    
    if session["role"] == "teacher":
        classes = db.execute("""
            SELECT * FROM classes
            WHERE teacher_id = ? AND (name LIKE ? OR subject LIKE ? OR join_code LIKE ?)
        """, user_id, search_term, search_term, search_term)
        
        materials = db.execute("""
            SELECT materials.*, classes.name AS class_name
            FROM materials
            JOIN classes ON materials.class_id = classes.id
            WHERE classes.teacher_id = ? AND materials.filename LIKE ?
        """, user_id, search_term)
        
        announcements = db.execute("""
            SELECT announcements.*, classes.name AS class_name
            FROM announcements
            JOIN classes ON announcements.class_id = classes.id
            WHERE classes.teacher_id = ? AND announcements.text LIKE ?
        """, user_id, search_term)
        
        assignments = db.execute("""
            SELECT assignments.*, classes.name AS class_name
            FROM assignments
            JOIN classes ON assignments.class_id = classes.id
            WHERE classes.teacher_id = ? AND (assignments.title LIKE ? OR assignments.description LIKE ?)
        """, user_id, search_term, search_term)
    else:
        classes = db.execute("""
            SELECT classes.* FROM classes
            JOIN enrollments ON classes.id = enrollments.class_id
            WHERE enrollments.student_id = ? AND (classes.name LIKE ? OR classes.subject LIKE ?)
        """, user_id, search_term, search_term)
        
        materials = db.execute("""
            SELECT materials.*, classes.name AS class_name
            FROM materials
            JOIN classes ON materials.class_id = classes.id
            JOIN enrollments ON classes.id = enrollments.class_id
            WHERE enrollments.student_id = ? AND materials.filename LIKE ?
        """, user_id, search_term)
        
        announcements = db.execute("""
            SELECT announcements.*, classes.name AS class_name
            FROM announcements
            JOIN classes ON announcements.class_id = classes.id
            JOIN enrollments ON classes.id = enrollments.class_id
            WHERE enrollments.student_id = ? AND announcements.text LIKE ?
        """, user_id, search_term)
        
        assignments = db.execute("""
            SELECT assignments.*, classes.name AS class_name
            FROM assignments
            JOIN classes ON assignments.class_id = classes.id
            JOIN enrollments ON classes.id = enrollments.class_id
            WHERE enrollments.student_id = ? AND (assignments.title LIKE ? OR assignments.description LIKE ?)
        """, user_id, search_term, search_term)
        
    return render_template("search_results.html",
                           query=query,
                           classes=classes,
                           materials=materials,
                           announcements=announcements,
                           assignments=assignments)

# ==========================================
# FACULTY DIRECTORY
# ==========================================
@app.route("/faculty")
@login_required
def faculty_directory():
    entries = db.execute("""
        SELECT faculty_directory.*, users.name AS added_by_name
        FROM faculty_directory
        LEFT JOIN users ON faculty_directory.created_by = users.id
        ORDER BY faculty_directory.name ASC
    """)
    return render_template("faculty_directory.html", entries=entries)

@app.route("/faculty/add", methods=["POST"])
@login_required
@teacher_required
def faculty_add():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Faculty name is required.", "warning")
        return redirect(url_for("faculty_directory"))
    subject = request.form.get("subject", "").strip()
    phone = request.form.get("phone", "").strip()
    cabinet = request.form.get("cabinet", "").strip()
    email = request.form.get("email", "").strip()
    db.execute("""
        INSERT INTO faculty_directory (name, subject, phone, cabinet, email, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
    """, name, subject or None, phone or None, cabinet or None, email or None, session["user_id"])
    flash(f"Faculty member '{name}' added.", "success")
    return redirect(url_for("faculty_directory"))

@app.route("/faculty/edit/<int:entry_id>", methods=["POST"])
@login_required
@teacher_required
def faculty_edit(entry_id):
    name = request.form.get("name", "").strip()
    if not name:
        flash("Faculty name is required.", "warning")
        return redirect(url_for("faculty_directory"))
    subject = request.form.get("subject", "").strip()
    phone = request.form.get("phone", "").strip()
    cabinet = request.form.get("cabinet", "").strip()
    email = request.form.get("email", "").strip()
    db.execute("""
        UPDATE faculty_directory
        SET name=?, subject=?, phone=?, cabinet=?, email=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, name, subject or None, phone or None, cabinet or None, email or None, entry_id)
    flash(f"Faculty member updated.", "success")
    return redirect(url_for("faculty_directory"))

@app.route("/faculty/delete/<int:entry_id>", methods=["POST"])
@login_required
@teacher_required
def faculty_delete(entry_id):
    db.execute("DELETE FROM faculty_directory WHERE id = ?", entry_id)
    flash("Faculty member removed.", "info")
    return redirect(url_for("faculty_directory"))


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

