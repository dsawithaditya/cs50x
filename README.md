# ClassConnect
#### Video Demo: https://youtu.be/c5fJBvW4AAg
#### Description:

**ClassConnect** is a comprehensive, web-based classroom management and digital attendance portal engineered using **Python (Flask)**, **SQLite**, **HTML5/Jinja2**, **Bootstrap 5**, and **JavaScript**. Developed as a capstone project for CS50x, ClassConnect addresses the everyday administrative frictions faced by educational institutions, instructors, and students. In traditional classroom environments, tracking daily attendance, distributing study resources, broadcasting announcements, and maintaining verified student profiles often require disparate tools, spreadsheets, or physical paper rosters. ClassConnect bridges this divide by providing a unified, intuitive, and responsive hub where academic administration and communication happen seamlessly in real-time.

At its core, the platform provides tailored, role-based workflows for two distinct user personas: **Teachers** and **Students**. Instructors can create digital classrooms, generate randomized join codes, post class-wide notices, upload course files, record daily attendance with fine-grained statuses (Present, Late, Absent), and add new student records directly into class rosters with vital academic metadata (such as Application Numbers, Branches, and Classrooms). Concurrently, students can join classrooms, download course materials, track their personal attendance percentages through visual metric cards, and review their full attendance history chronologically.

---

### Project Architecture & File Breakdown

The repository is structured logically to maintain separation of concerns between backend routing, database definitions, frontend rendering templates, and client-side assets:

#### 1. Backend & Configuration
- **`app.py`**: The central application controller containing all Flask route handlers, business logic, session configuration, and database queries. It implements custom authentication decorators (`@login_required` and `@teacher_required`) to secure endpoints against unauthorized access. Major features implemented in `app.py` include:
  - User authentication and session management (registration, login, logout).
  - Classroom creation with automated random join-code generation and student enrollment logic.
  - File upload pipelines utilizing Werkzeug's `secure_filename` with timestamped unique naming to prevent file overwrites.
  - Multi-condition attendance recording with idempotent upsert queries (deleting existing records for a given date before re-inserting updated statuses).
  - Centralized announcements dispatching (with support for broadcasting to individual classes or all instructor classes concurrently).
  - User profile retrieval, profile details modification, and cryptographic password updating.
- **`schema.sql`**: The relational database schema definition. It establishes normalized relational tables (`users`, `classes`, `enrollments`, `announcements`, `materials`, and `attendance`) with primary keys, foreign key constraints, unique constraints on usernames and join codes, and check constraints on role and attendance statuses.
- **`classconnect.db`**: The SQLite database engine storing persistent records across all application modules.

#### 2. Frontend Templates (`templates/`)
- **`layout.html`**: The foundational Jinja2 base template extended by all other views. It includes the responsive navigation menu bar, branding with dynamic role tags, breadcrumb navigation, flash message rendering with auto-dismissal, theme toggle button, and an immediate `<head>` script that executes prior to DOM rendering to prevent light-theme flickering when dark mode is enabled.
- **`login.html`**: Clean, accessible login interface with form validation and redirection back to protected routes upon successful authentication.
- **`register.html`**: New user registration interface supporting role selection (`teacher` or `student`) with matching password confirmation checks.
- **`teacher_dashboard.html`**: The teacher's primary landing view displaying grid cards of all created classes, join codes, fast-action attendance buttons, and a modal for instant class creation.
- **`student_dashboard.html`**: The student portal listing all currently enrolled courses with direct links to class materials and attendance analytics, accompanied by a join-class modal.
- **`class_view.html`**: The detailed view for an individual class featuring a two-column layout: a feed of class announcements on the left and downloadable course materials with a teacher upload interface on the right.
- **`attendance.html`**: The instructor's attendance management center. Features a date switcher, quick bulk-marking buttons ("All Present", "All Late", "All Absent"), an interactive modal to add students directly with full profile details (Name, Application No., Branch, Classroom, Mobile No.), and a live attendance table with radio badges and student removal options.
- **`student_attendance.html`**: The student's personal attendance dashboard, featuring metric summary cards (Total Classes, Present Count, Late Count) and a date-stamped log of past attendance records.
- **`announcements.html`**: The centralized announcements feed aggregating all updates across courses. Allows teachers to post targeted or multi-class broadcasts and delete obsolete notices, while enabling students to filter notices by class.
- **`profile.html`**: A user management center allowing teachers and students to view their account metadata, update academic details (Branch, Classroom, Mobile Number), and securely change their account password.

#### 3. Static Assets (`static/`)
- **`static/css/style.css`**: Custom stylesheet enhancing Bootstrap 5 with custom CSS design tokens (`--bg-main`, `--card-bg`, `--text-main`, `--nav-bg`). It provides complete Light and Dark theme styling, glassmorphic card overlays, smooth hover elevation animations, badge formatting, and theme-adaptive table and modal styling.
- **`static/js/script.js`**: Client-side JavaScript providing theme synchronization with `localStorage` and system `prefers-color-scheme`, SVG theme icon swapping, and automatic dismissal of temporary alert banners.
- **`static/uploads/`**: Secure server storage directory for uploaded class materials and academic documents.

---

### Design Choices & Technical Decisions

During the development of ClassConnect, several architectural and design trade-offs were evaluated:

1. **CS50 SQL Wrapper vs. Heavy ORM**:
   Instead of introducing an ORM like SQLAlchemy, the project utilizes the `cs50.SQL` wrapper. This deliberate decision reinforces raw SQL fluency, maximizes query execution transparency, and avoids the boilerplate and performance overhead of ORMs while still leveraging parameterized queries to guard against SQL injection vulnerabilities.

2. **Filesystem Sessions over Signed Client Cookies**:
   The application configures `Flask-Session` with filesystem storage (`app.config["SESSION_TYPE"] = "filesystem"`). This ensures sensitive session states (such as active `user_id`, `username`, and `role`) reside strictly on the server rather than within client-tamperable cookie payloads, boosting security.

3. **Attendance Upsert Strategy**:
   When an instructor submits attendance for a specific date, the backend executes a clean delete-then-insert transaction for that specific date and class. This approach prevents duplicate key collisions, elegantly handles modifications to previous dates without requiring complex row-by-row state diffing, and guarantees data consistency.

4. **Zero-Flicker Dark Mode Architecture**:
   To ensure a modern user experience, dark mode was implemented using Bootstrap 5.3's `data-bs-theme` attribute combined with CSS variables. An inline JavaScript snippet was placed directly in the `<head>` of `layout.html` before stylesheets and body content are parsed; this prevents the jarring "flash of white" that typically occurs on page reload when dark mode is enabled.

5. **Modal-Driven Administrative Workflows**:
   Actions such as creating classes, joining classes, and adding student details were implemented using Bootstrap modals directly within relevant dashboard pages. This minimizes context switching and avoids unnecessary page redirects, allowing educators to manage rosters and classrooms smoothly.

---

### How to Run Locally

1. **Clone the repository & navigate into the project directory**:
   ```bash
   cd cs50_final_project
   ```

2. **Install Python dependencies**:
   ```bash
   pip install flask flask-session cs50 werkzeug
   ```

3. **Start the Flask development server**:
   ```bash
   flask run
   ```
   *or*
   ```bash
   python app.py
   ```

4. **Access the application**:
   Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your web browser.
