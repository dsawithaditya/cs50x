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
        return render_template("teacher_dashboard.html", 
                               classes=classes, 
                               default_academic_year=default_academic_year, 
                               default_date=default_date)
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
        return render_template("student_dashboard.html", classes=classes)

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
    announcements = db.execute("SELECT * FROM announcements WHERE class_id = ? ORDER BY timestamp DESC", class_id)
    materials = db.execute("SELECT * FROM materials WHERE class_id = ? ORDER BY upload_time DESC", class_id)
    
    return render_template("class_view.html", class_info=c_info, announcements=announcements, materials=materials)

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
    
    return redirect(url_for('class_view', class_id=class_id))

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
        return redirect(url_for('class_view', class_id=class_id))
        
    file = request.files['material']
    if file.filename == '':
        flash('No selected file', 'warning')
        return redirect(url_for('class_view', class_id=class_id))
        
    if file:
        filename = secure_filename(file.filename)
        # Make a unique filename to avoid overwrites
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        db.execute("INSERT INTO materials (class_id, filename, file_path) VALUES (?, ?, ?)", class_id, filename, unique_filename)
        flash("Material uploaded successfully.", "success")
        
    return redirect(url_for('class_view', class_id=class_id))

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

if __name__ == '__main__':
    app.run(debug=True)

