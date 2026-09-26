const express = require('express');
const session = require('express-session');
const flash = require('connect-flash');
const nunjucks = require('nunjucks');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const Database = require('better-sqlite3');
const { checkPasswordHash, generatePasswordHash } = require('./auth_utils');

const app = express();
const PORT = process.env.PORT || 5000;

// Connect to SQLite database
const db = new Database(path.join(__dirname, 'classconnect.db'));
db.pragma('foreign_keys = ON');

// Upload directory setup
const UPLOAD_FOLDER = path.join(__dirname, 'static', 'uploads');
fs.mkdirSync(UPLOAD_FOLDER, { recursive: true });

// Configure Multer storage
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, UPLOAD_FOLDER);
  },
  filename: function (req, file, cb) {
    const timestamp = Date.now();
    // Sanitize filename
    const safeName = file.originalname.replace(/[^a-zA-Z0-9._-]/g, '_');
    cb(null, `${timestamp}_${safeName}`);
  }
});
const upload = multer({ storage: storage });

// Static assets
app.use('/static', express.static(path.join(__dirname, 'static')));

// Body parsers
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

// Session setup
app.use(session({
  secret: 'cs50_classconnect_secret_key_2026',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 24 * 60 * 60 * 1000 }
}));

// Flash messages
app.use(flash());

// Response cache headers
app.use((req, res, next) => {
  res.set({
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0'
  });
  next();
});

// Configure Nunjucks
const nunjucksEnv = nunjucks.configure(path.join(__dirname, 'templates'), {
  autoescape: true,
  express: app,
  noCache: true
});

// Nunjucks filters and globals
nunjucksEnv.addFilter('string', (val) => (val == null ? '' : String(val)));
nunjucksEnv.addGlobal('url_for', (endpoint, opts) => {
  if (endpoint === 'static' && opts && opts.filename) {
    return `/static/${opts.filename}`;
  }
  return `/${endpoint || ''}`;
});

// Template context middleware
app.use((req, res, next) => {
  if (req.session) {
    req.session.get = function (key) {
      return this[key];
    };
  }
  res.locals.session = req.session;
  res.locals.get_flashed_messages = function (options) {
    const flashes = req.flash();
    const result = [];
    for (const [cat, msgs] of Object.entries(flashes)) {
      for (const msg of msgs) {
        result.push([cat, msg]);
      }
    }
    return result;
  };
  next();
});

// Authentication middleware
function loginRequired(req, res, next) {
  if (!req.session || !req.session.user_id) {
    return res.redirect('/login');
  }
  next();
}

function teacherRequired(req, res, next) {
  if (!req.session || req.session.role !== 'teacher') {
    req.flash('danger', 'You must be a teacher to access this page.');
    return res.redirect('/');
  }
  next();
}

function generateJoinCode(length = 6) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  let code = '';
  for (let i = 0; i < length; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return code;
}

// ----------------------------------------------------
// ROUTES
// ----------------------------------------------------

// Home / Dashboard
app.get('/', loginRequired, (req, res) => {
  const now = new Date();
  const defaultAcademicYear = `${now.getFullYear()}-${now.getFullYear() + 1}`;
  const defaultDate = now.toISOString().slice(0, 10);

  if (req.session.role === 'teacher') {
    const classes = db.prepare(`
      SELECT classes.*, COUNT(enrollments.student_id) AS student_count
      FROM classes
      LEFT JOIN enrollments ON classes.id = enrollments.class_id
      WHERE classes.teacher_id = ?
      GROUP BY classes.id
      ORDER BY classes.id DESC
    `).all(req.session.user_id);

    return res.render('teacher_dashboard.html', {
      classes,
      default_academic_year: defaultAcademicYear,
      default_date: defaultDate
    });
  } else {
    const classes = db.prepare(`
      SELECT classes.*, users.name AS teacher_name, users.username AS teacher_username
      FROM classes
      JOIN enrollments ON classes.id = enrollments.class_id
      JOIN users ON classes.teacher_id = users.id
      WHERE enrollments.student_id = ?
      ORDER BY classes.id DESC
    `).all(req.session.user_id);

    return res.render('student_dashboard.html', { classes });
  }
});

// Login
app.get('/login', (req, res) => {
  if (req.session.user_id) {
    req.session.destroy(() => { });
  }
  res.render('login.html');
});

app.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    req.flash('danger', 'Must provide username and password.');
    return res.redirect('/login');
  }

  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username.trim());
  if (!user || !checkPasswordHash(user.hash, password)) {
    req.flash('danger', 'Invalid username and/or password.');
    return res.redirect('/login');
  }

  req.session.user_id = user.id;
  req.session.username = user.username;
  req.session.role = user.role;
  req.session.name = user.name;

  req.flash('success', `Welcome back, ${user.name || user.username}!`);
  res.redirect('/');
});

// Register
app.get('/register', (req, res) => {
  res.render('register.html');
});

app.post('/register', (req, res) => {
  const { username, password, confirmation, role, name, branch, classroom, mobile_no } = req.body;

  if (!username || !password || !confirmation || !role) {
    req.flash('danger', 'Please fill in all required fields.');
    return res.redirect('/register');
  }

  if (password !== confirmation) {
    req.flash('danger', 'Passwords do not match.');
    return res.redirect('/register');
  }

  if (password.length < 4) {
    req.flash('danger', 'Password must be at least 4 characters.');
    return res.redirect('/register');
  }

  if (!['teacher', 'student'].includes(role)) {
    req.flash('danger', 'Invalid role selected.');
    return res.redirect('/register');
  }

  const existing = db.prepare('SELECT id FROM users WHERE username = ?').get(username.trim());
  if (existing) {
    req.flash('danger', 'Username already taken.');
    return res.redirect('/register');
  }

  const hash = generatePasswordHash(password);
  let parsedMobile = null;
  if (mobile_no) {
    const digits = mobile_no.replace(/\D/g, '');
    if (digits) parsedMobile = parseInt(digits, 10) || null;
  }

  const info = db.prepare(`
    INSERT INTO users (username, hash, role, name, branch, classroom, mobile_no)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(
    username.trim(),
    hash,
    role,
    (name || '').trim() || null,
    (branch || '').trim() || null,
    (classroom || '').trim() || null,
    parsedMobile
  );

  req.session.user_id = Number(info.lastInsertRowid);
  req.session.username = username.trim();
  req.session.role = role;
  req.session.name = (name || '').trim() || null;

  req.flash('success', 'Account created successfully! Welcome to ClassConnect.');
  res.redirect('/');
});

// Logout
app.get('/logout', (req, res) => {
  req.session.destroy(() => {
    res.redirect('/login');
  });
});

// Forgot Password
app.get('/forgot_password', (req, res) => {
  res.render('forgot_password.html');
});

app.post('/forgot_password', (req, res) => {
  const { username, role, new_password, confirmation } = req.body;
  if (!username || !role || !new_password || !confirmation) {
    req.flash('warning', 'All fields are required.');
    return res.redirect('/forgot_password');
  }
  if (new_password !== confirmation) {
    req.flash('warning', 'Passwords do not match.');
    return res.redirect('/forgot_password');
  }
  if (!['teacher', 'student'].includes(role)) {
    req.flash('danger', 'Please select a valid account role.');
    return res.redirect('/forgot_password');
  }

  const user = db.prepare('SELECT * FROM users WHERE username = ? AND role = ?').get(username.trim(), role);
  if (!user) {
    req.flash('danger', 'No matching account found with that username and role.');
    return res.redirect('/forgot_password');
  }

  const hash = generatePasswordHash(new_password);
  db.prepare('UPDATE users SET hash = ? WHERE id = ?').run(hash, user.id);

  req.flash('success', 'Password reset successfully! Please log in with your new password.');
  return res.redirect('/login');
});

// Create Class (Teacher)
const handleCreateClass = (req, res) => {
  const className = (req.body.class_name || req.body.name || '').trim();
  const subject = (req.body.subject || '').trim();
  const semester = (req.body.semester || '').trim();
  let academicYear = (req.body.academic_year || '').trim();
  let createdAt = (req.body.created_at || '').trim();
  const section = (req.body.section || '').trim();
  const room = (req.body.room || '').trim();

  if (!className) {
    req.flash('warning', 'Must provide a class name.');
    return res.redirect('/');
  }

  if (!createdAt) {
    createdAt = new Date().toISOString().slice(0, 10);
  }
  if (!academicYear) {
    const year = new Date().getFullYear();
    academicYear = `${year}-${year + 1}`;
  }

  let joinCode;
  while (true) {
    joinCode = generateJoinCode();
    const existing = db.prepare('SELECT id FROM classes WHERE join_code = ?').get(joinCode);
    if (!existing) break;
  }

  db.prepare(`
    INSERT INTO classes (name, teacher_id, join_code, subject, semester, academic_year, created_at, section, room)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    className,
    req.session.user_id,
    joinCode,
    subject || null,
    semester || null,
    academicYear || null,
    createdAt || null,
    section || null,
    room || null
  );

  req.flash('success', `Class '${className}' created successfully! Join code: ${joinCode}`);
  res.redirect('/');
};

app.post('/create_class', loginRequired, teacherRequired, handleCreateClass);
app.post('/classes/create', loginRequired, teacherRequired, handleCreateClass);

// Join Class (Student)
const handleJoinClass = (req, res) => {
  if (req.session.role !== 'student') {
    req.flash('danger', 'Only students can join classes.');
    return res.redirect('/');
  }

  const code = (req.body.join_code || req.body.code || '').trim().toUpperCase();
  if (!code) {
    req.flash('warning', 'Must provide a join code.');
    return res.redirect('/');
  }

  const classInfo = db.prepare('SELECT * FROM classes WHERE join_code = ?').get(code);
  if (!classInfo) {
    req.flash('danger', 'Invalid join code. Class not found.');
    return res.redirect('/');
  }

  const enrolled = db.prepare('SELECT * FROM enrollments WHERE class_id = ? AND student_id = ?')
    .get(classInfo.id, req.session.user_id);
  if (enrolled) {
    req.flash('info', 'You are already enrolled in this class.');
    return res.redirect('/');
  }

  db.prepare('INSERT INTO enrollments (class_id, student_id) VALUES (?, ?)')
    .run(classInfo.id, req.session.user_id);

  req.flash('success', `Successfully joined '${classInfo.name}'!`);
  res.redirect('/');
};

app.post('/join_class', loginRequired, handleJoinClass);
app.post('/classes/join', loginRequired, handleJoinClass);

// Class View
app.get('/class/:class_id', loginRequired, (req, res) => {
  const classId = parseInt(req.params.class_id, 10);
  let classInfo;

  if (req.session.role === 'teacher') {
    classInfo = db.prepare('SELECT * FROM classes WHERE id = ? AND teacher_id = ?').get(classId, req.session.user_id);
  } else {
    classInfo = db.prepare(`
      SELECT classes.* FROM classes
      JOIN enrollments ON classes.id = enrollments.class_id
      WHERE classes.id = ? AND enrollments.student_id = ?
    `).get(classId, req.session.user_id);
  }

  if (!classInfo) {
    req.flash('danger', 'Class not found or access denied.');
    return res.redirect('/');
  }

  const announcements = db.prepare('SELECT * FROM announcements WHERE class_id = ? ORDER BY timestamp DESC').all(classId);
  const materials = db.prepare('SELECT * FROM materials WHERE class_id = ? ORDER BY timestamp DESC').all(classId);

  res.render('class_view.html', {
    class_info: classInfo,
    announcements,
    materials
  });
});

// Attendance Management (Teacher)
app.get('/class/:class_id/attendance', loginRequired, teacherRequired, (req, res) => {
  const classId = parseInt(req.params.class_id, 10);
  const classInfo = db.prepare('SELECT * FROM classes WHERE id = ? AND teacher_id = ?').get(classId, req.session.user_id);
  if (!classInfo) {
    req.flash('danger', 'Class not found or access denied.');
    return res.redirect('/');
  }

  const date = req.query.date || new Date().toISOString().slice(0, 10);

  const students = db.prepare(`
    SELECT users.id, users.name, users.username, users.application_number, users.branch, users.classroom, users.mobile_no
    FROM users
    JOIN enrollments ON users.id = enrollments.student_id
    WHERE enrollments.class_id = ?
    ORDER BY users.application_number ASC, users.name ASC
  `).all(classId);

  const records = db.prepare('SELECT student_id, status FROM attendance WHERE class_id = ? AND date = ?').all(classId, date);
  const attendanceMap = {};
  for (const r of records) {
    attendanceMap[r.student_id] = r.status;
  }

  for (const s of students) {
    s.status = attendanceMap[s.id] || 'Present';
  }

  res.render('attendance.html', {
    class_info: classInfo,
    students,
    date
  });
});

// Save Attendance (Teacher)
app.post('/class/:class_id/attendance', loginRequired, teacherRequired, (req, res) => {
  const classId = parseInt(req.params.class_id, 10);
  const classInfo = db.prepare('SELECT * FROM classes WHERE id = ? AND teacher_id = ?').get(classId, req.session.user_id);
  if (!classInfo) {
    return res.redirect('/');
  }

  const date = req.body.date || new Date().toISOString().slice(0, 10);

  const students = db.prepare(`
    SELECT users.id FROM users
    JOIN enrollments ON users.id = enrollments.student_id
    WHERE enrollments.class_id = ?
  `).all(classId);

  const deleteStmt = db.prepare('DELETE FROM attendance WHERE class_id = ? AND date = ?');
  const insertStmt = db.prepare('INSERT INTO attendance (class_id, student_id, date, status) VALUES (?, ?, ?, ?)');

  const saveTx = db.transaction(() => {
    deleteStmt.run(classId, date);
    for (const s of students) {
      const status = req.body[`status_${s.id}`];
      if (status && ['Present', 'Late', 'Absent'].includes(status)) {
        insertStmt.run(classId, s.id, date, status);
      }
    }
  });

  saveTx();

  req.flash('success', `Attendance for ${date} saved successfully!`);
  res.redirect(`/class/${classId}/attendance?date=${date}`);
});

// Add Student to Class (Teacher)
app.post('/class/:class_id/students/add', loginRequired, teacherRequired, (req, res) => {
  const classId = parseInt(req.params.class_id, 10);
  const classInfo = db.prepare('SELECT * FROM classes WHERE id = ? AND teacher_id = ?').get(classId, req.session.user_id);
  if (!classInfo) return res.redirect('/');

  const name = (req.body.name || '').trim();
  const applicationNumber = (req.body.application_number || '').trim().toUpperCase();
  const branch = (req.body.branch || '').trim();
  const classroom = (req.body.classroom || '').trim();
  const mobileRaw = (req.body.mobile_no || '').trim();

  if (!name) {
    req.flash('warning', 'Student name is required.');
    return res.redirect(`/class/${classId}/attendance`);
  }

  let mobileNo = null;
  if (mobileRaw) {
    const digits = mobileRaw.replace(/\D/g, '');
    if (digits) mobileNo = parseInt(digits, 10) || null;
  }

  const targetAppNo = applicationNumber || `APP${Date.now().toString().slice(-6)}`;
  let user = db.prepare('SELECT id FROM users WHERE application_number = ? OR username = ?').get(targetAppNo, targetAppNo);

  let studentId;
  let isNewStudent = false;

  if (!user) {
    isNewStudent = true;
    const defaultPassword = targetAppNo;
    const hash = generatePasswordHash(defaultPassword);

    const info = db.prepare(`
      INSERT INTO users (username, hash, role, name, application_number, branch, classroom, mobile_no)
      VALUES (?, ?, 'student', ?, ?, ?, ?, ?)
    `).run(targetAppNo, hash, name, targetAppNo, branch || null, classroom || null, mobileNo);

    studentId = Number(info.lastInsertRowid);
  } else {
    studentId = user.id;
    db.prepare(`
      UPDATE users SET
        name = COALESCE(NULLIF(?, ''), name),
        branch = COALESCE(NULLIF(?, ''), branch),
        classroom = COALESCE(NULLIF(?, ''), classroom),
        mobile_no = COALESCE(?, mobile_no)
      WHERE id = ?
    `).run(name, branch, classroom, mobileNo, studentId);
  }

  const alreadyEnrolled = db.prepare('SELECT * FROM enrollments WHERE class_id = ? AND student_id = ?').get(classId, studentId);
  if (!alreadyEnrolled) {
    db.prepare('INSERT INTO enrollments (class_id, student_id) VALUES (?, ?)').run(classId, studentId);
    req.flash('success', `Student '${name}' (${targetAppNo}) added to class attendance roster!`);
  } else {
    req.flash('info', `Student '${name}' (${targetAppNo}) details updated.`);
  }

  res.redirect(`/class/${classId}/attendance`);
});

// Remove Student from Class (Teacher)
app.post('/class/:class_id/remove_student/:student_id', loginRequired, teacherRequired, (req, res) => {
  const classId = parseInt(req.params.class_id, 10);
  const studentId = parseInt(req.params.student_id, 10);

  const classInfo = db.prepare('SELECT * FROM classes WHERE id = ? AND teacher_id = ?').get(classId, req.session.user_id);
  if (!classInfo) return res.redirect('/');

  db.prepare('DELETE FROM enrollments WHERE student_id = ? AND class_id = ?').run(studentId, classId);
  db.prepare('DELETE FROM attendance WHERE student_id = ? AND class_id = ?').run(studentId, classId);

  req.flash('info', 'Student removed from class attendance roster.');
  res.redirect(`/class/${classId}/attendance`);
});

// Student Attendance Self-View
app.get('/class/:class_id/my_attendance', loginRequired, (req, res) => {
  if (req.session.role !== 'student') return res.redirect('/');

  const classId = parseInt(req.params.class_id, 10);
  const classInfo = db.prepare(`
    SELECT classes.* FROM classes
    JOIN enrollments ON classes.id = enrollments.class_id
    WHERE classes.id = ? AND enrollments.student_id = ?
  `).get(classId, req.session.user_id);

  if (!classInfo) return res.redirect('/');

  const records = db.prepare('SELECT date, status FROM attendance WHERE class_id = ? AND student_id = ? ORDER BY date DESC')
    .all(classId, req.session.user_id);

  const total = records.length;
  const present = records.filter(r => r.status === 'Present').length;
  const late = records.filter(r => r.status === 'Late').length;

  res.render('student_attendance.html', {
    class_info: classInfo,
    records,
    total,
    present,
    late
  });
});

// Upload Materials (Teacher)
app.post('/class/:class_id/materials/upload', loginRequired, teacherRequired, upload.single('file'), (req, res) => {
  const classId = parseInt(req.params.class_id, 10);
  const classInfo = db.prepare('SELECT * FROM classes WHERE id = ? AND teacher_id = ?').get(classId, req.session.user_id);
  if (!classInfo) return res.redirect('/');

  const title = (req.body.title || '').trim();
  if (!req.file || !title) {
    req.flash('warning', 'Please provide both a title and a file.');
    return res.redirect(`/class/${classId}`);
  }

  const relativePath = path.join('static', 'uploads', req.file.filename);

  db.prepare(`
    INSERT INTO materials (class_id, title, filename, filepath, original_filename)
    VALUES (?, ?, ?, ?, ?)
  `).run(classId, title, req.file.filename, relativePath, req.file.originalname);

  req.flash('success', `File "${req.file.originalname}" uploaded successfully!`);
  res.redirect(`/class/${classId}`);
});

// Download Material
app.get('/download/:material_id', loginRequired, (req, res) => {
  const materialId = parseInt(req.params.material_id, 10);
  const material = db.prepare('SELECT * FROM materials WHERE id = ?').get(materialId);

  if (!material) {
    req.flash('danger', 'File not found.');
    return res.redirect('/');
  }

  // Access check
  if (req.session.role === 'teacher') {
    const classCheck = db.prepare('SELECT id FROM classes WHERE id = ? AND teacher_id = ?')
      .get(material.class_id, req.session.user_id);
    if (!classCheck) {
      req.flash('danger', 'Access denied.');
      return res.redirect('/');
    }
  } else {
    const enrollCheck = db.prepare('SELECT * FROM enrollments WHERE class_id = ? AND student_id = ?')
      .get(material.class_id, req.session.user_id);
    if (!enrollCheck) {
      req.flash('danger', 'Access denied.');
      return res.redirect('/');
    }
  }

  const filePath = path.join(__dirname, 'static', 'uploads', material.filename);
  if (!fs.existsSync(filePath)) {
    req.flash('danger', 'File no longer exists on server.');
    return res.redirect(`/class/${material.class_id}`);
  }

  res.download(filePath, material.original_filename || material.filename);
});

// Announcements Feed
app.get('/announcements', loginRequired, (req, res) => {
  const userId = req.session.user_id;
  const role = req.session.role;

  let userClasses;
  if (role === 'teacher') {
    userClasses = db.prepare('SELECT * FROM classes WHERE teacher_id = ? ORDER BY name ASC').all(userId);
  } else {
    userClasses = db.prepare(`
      SELECT classes.* FROM classes
      JOIN enrollments ON classes.id = enrollments.class_id
      WHERE enrollments.student_id = ?
      ORDER BY classes.name ASC
    `).all(userId);
  }

  const classIds = userClasses.map(c => c.id);
  const filterClass = req.query.class_id;

  let allAnnouncements = [];
  if (classIds.length > 0) {
    if (filterClass && !isNaN(parseInt(filterClass, 10)) && classIds.includes(parseInt(filterClass, 10))) {
      allAnnouncements = db.prepare(`
        SELECT announcements.*, classes.name AS class_name
        FROM announcements JOIN classes ON announcements.class_id = classes.id
        WHERE announcements.class_id = ?
        ORDER BY announcements.timestamp DESC
      `).all(parseInt(filterClass, 10));
    } else {
      const placeholders = classIds.map(() => '?').join(',');
      allAnnouncements = db.prepare(`
        SELECT announcements.*, classes.name AS class_name
        FROM announcements JOIN classes ON announcements.class_id = classes.id
        WHERE announcements.class_id IN (${placeholders})
        ORDER BY announcements.timestamp DESC
      `).all(...classIds);
    }
  }

  res.render('announcements.html', {
    announcements: allAnnouncements,
    classes: userClasses,
    selected_class: filterClass || 'all'
  });
});

// Create Announcement
app.post('/announcements', loginRequired, teacherRequired, (req, res) => {
  const targetClassId = req.body.class_id;
  const text = (req.body.text || '').trim();

  if (!text) {
    req.flash('warning', 'Announcement text cannot be empty.');
    return res.redirect('/announcements');
  }

  const userClasses = db.prepare('SELECT * FROM classes WHERE teacher_id = ?').all(req.session.user_id);
  const insertStmt = db.prepare('INSERT INTO announcements (class_id, text) VALUES (?, ?)');

  if (targetClassId === 'all') {
    const postAllTx = db.transaction(() => {
      for (const c of userClasses) {
        insertStmt.run(c.id, text);
      }
    });
    postAllTx();
    req.flash('success', `Announcement posted to all ${userClasses.length} classes!`);
  } else {
    const cid = parseInt(targetClassId, 10);
    const owned = userClasses.find(c => c.id === cid);
    if (owned) {
      insertStmt.run(cid, text);
      req.flash('success', `Announcement posted to ${owned.name}.`);
    } else {
      req.flash('warning', 'Invalid class selected.');
    }
  }

  res.redirect('/announcements');
});

// Delete Announcement (Teacher)
app.post('/announcement/:announcement_id/delete', loginRequired, teacherRequired, (req, res) => {
  const announcementId = parseInt(req.params.announcement_id, 10);
  const announcement = db.prepare(`
    SELECT announcements.id FROM announcements
    JOIN classes ON announcements.class_id = classes.id
    WHERE announcements.id = ? AND classes.teacher_id = ?
  `).get(announcementId, req.session.user_id);

  if (announcement) {
    db.prepare('DELETE FROM announcements WHERE id = ?').run(announcementId);
    req.flash('info', 'Announcement deleted.');
  } else {
    req.flash('danger', 'Announcement not found or unauthorized.');
  }

  res.redirect(req.get('Referrer') || '/announcements');
});

// Profile Management
app.get('/profile', loginRequired, (req, res) => {
  const userId = req.session.user_id;
  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(userId);

  let classes;
  if (req.session.role === 'teacher') {
    classes = db.prepare('SELECT * FROM classes WHERE teacher_id = ?').all(userId);
  } else {
    classes = db.prepare(`
      SELECT classes.* FROM classes
      JOIN enrollments ON classes.id = enrollments.class_id
      WHERE enrollments.student_id = ?
    `).all(userId);
  }

  res.render('profile.html', { user, classes });
});

app.post('/profile', loginRequired, (req, res) => {
  const userId = req.session.user_id;
  const action = req.body.action;

  if (action === 'update_profile') {
    const name = (req.body.name || '').trim();
    const branch = (req.body.branch || '').trim();
    const classroom = (req.body.classroom || '').trim();
    const mobileRaw = (req.body.mobile_no || '').trim();

    let mobileNo = null;
    if (mobileRaw) {
      const digits = mobileRaw.replace(/\D/g, '');
      if (digits) mobileNo = parseInt(digits, 10) || null;
    }

    db.prepare(`
      UPDATE users SET name = ?, branch = ?, classroom = ?, mobile_no = ? WHERE id = ?
    `).run(name, branch, classroom, mobileNo, userId);

    req.session.name = name;
    req.flash('success', 'Profile updated successfully!');
    return res.redirect('/profile');
  } else if (action === 'change_password') {
    const { current_password, new_password, confirmation } = req.body;
    const user = db.prepare('SELECT hash FROM users WHERE id = ?').get(userId);

    if (!current_password || !new_password || !confirmation) {
      req.flash('warning', 'All password fields are required.');
      return res.redirect('/profile');
    }

    if (!checkPasswordHash(user.hash, current_password)) {
      req.flash('danger', 'Incorrect current password.');
      return res.redirect('/profile');
    }

    if (new_password !== confirmation) {
      req.flash('warning', 'New passwords do not match.');
      return res.redirect('/profile');
    }

    if (new_password.length < 4) {
      req.flash('warning', 'Password must be at least 4 characters long.');
      return res.redirect('/profile');
    }

    const newHash = generatePasswordHash(new_password);
    db.prepare('UPDATE users SET hash = ? WHERE id = ?').run(newHash, userId);

    req.flash('success', 'Password changed successfully!');
    return res.redirect('/profile');
  }

  res.redirect('/profile');
});

// Start Server
app.listen(PORT, () => {
  console.log(`ClassConnect Node.js Server running on http://127.0.0.1:${PORT}`);
});
