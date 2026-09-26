CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('teacher', 'student')),
    name TEXT,
    application_number TEXT UNIQUE,
    branch TEXT,
    classroom TEXT,
    mobile_no INTEGER
);

CREATE TABLE classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    teacher_id INTEGER NOT NULL,
    join_code TEXT NOT NULL UNIQUE,
    subject TEXT,
    semester TEXT,
    academic_year TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    section TEXT,
    room TEXT,
    FOREIGN KEY(teacher_id) REFERENCES users(id)
);

CREATE TABLE enrollments (
    student_id INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    PRIMARY KEY(student_id, class_id),
    FOREIGN KEY(student_id) REFERENCES users(id),
    FOREIGN KEY(class_id) REFERENCES classes(id)
);

CREATE TABLE announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id)
);

CREATE TABLE materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id)
);

CREATE TABLE attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    date DATE NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'Late')),
    FOREIGN KEY(class_id) REFERENCES classes(id),
    FOREIGN KEY(student_id) REFERENCES users(id)
);

CREATE TABLE assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    max_points INTEGER DEFAULT 100,
    due_date DATETIME,
    file_path TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id)
);

CREATE TABLE submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    submission_text TEXT,
    file_path TEXT,
    submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    grade REAL,
    feedback TEXT,
    graded_at DATETIME,
    FOREIGN KEY(assignment_id) REFERENCES assignments(id),
    FOREIGN KEY(student_id) REFERENCES users(id)
);

CREATE TABLE timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    day_of_week TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    room_override TEXT,
    FOREIGN KEY(class_id) REFERENCES classes(id)
);

CREATE TABLE comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    announcement_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(announcement_id) REFERENCES announcements(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    time_limit_minutes INTEGER DEFAULT 15,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(class_id) REFERENCES classes(id)
);

CREATE TABLE quiz_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option TEXT NOT NULL CHECK(correct_option IN ('A', 'B', 'C', 'D')),
    points INTEGER DEFAULT 1,
    FOREIGN KEY(quiz_id) REFERENCES quizzes(id)
);

CREATE TABLE quiz_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quiz_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    score REAL NOT NULL,
    total_points REAL NOT NULL,
    submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(quiz_id) REFERENCES quizzes(id),
    FOREIGN KEY(student_id) REFERENCES users(id)
);

CREATE TABLE faculty_directory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    subject TEXT,
    phone TEXT,
    cabinet TEXT,
    email TEXT,
    created_by INTEGER,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(created_by) REFERENCES users(id)
);
