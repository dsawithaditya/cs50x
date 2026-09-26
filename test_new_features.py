import unittest
import os
import io
from app import app, db
from werkzeug.security import generate_password_hash

class ClassConnectFeatureTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_end_to_end_flow(self):
        # 1. Register Teacher
        teacher_username = "test_teacher_99"
        student_username = "test_student_99"

        # Cleanup prior test data if any
        db.execute("DELETE FROM users WHERE username IN (?, ?)", teacher_username, student_username)
        
        t_resp = self.client.post('/register', data={
            'username': teacher_username,
            'password': 'password123',
            'confirmation': 'password123',
            'role': 'teacher'
        }, follow_redirects=True)
        self.assertEqual(t_resp.status_code, 200)

        # 2. Create Class as Teacher
        create_cls_resp = self.client.post('/create_class', data={
            'class_name': 'Advanced AI & CS',
            'subject': 'Computer Science',
            'semester': 'Semester 5',
            'academic_year': '2026-2027',
            'section': 'Batch A',
            'room': 'Lab 101'
        }, follow_redirects=True)
        self.assertEqual(create_cls_resp.status_code, 200)

        # Retrieve created class
        cls_rows = db.execute("SELECT * FROM classes WHERE name = 'Advanced AI & CS'")
        self.assertTrue(len(cls_rows) > 0)
        class_id = cls_rows[0]['id']
        join_code = cls_rows[0]['join_code']

        # 3. Create Announcement & Discussion
        ann_resp = self.client.post(f'/class/{class_id}/announce', data={
            'text': 'Welcome to Advanced AI! Check your first assignment.'
        }, follow_redirects=True)
        self.assertEqual(ann_resp.status_code, 200)

        ann_rows = db.execute("SELECT * FROM announcements WHERE class_id = ?", class_id)
        self.assertTrue(len(ann_rows) > 0)
        ann_id = ann_rows[0]['id']

        # 4. Create Assignment as Teacher
        asgn_resp = self.client.post(f'/class/{class_id}/assignments/create', data={
            'title': 'Problem Set 1 - Neural Networks',
            'description': 'Implement gradient descent and submit your script or notes.',
            'max_points': '100',
            'due_date': '2026-10-15T23:59'
        }, follow_redirects=True)
        self.assertEqual(asgn_resp.status_code, 200)

        asgn_rows = db.execute("SELECT * FROM assignments WHERE class_id = ?", class_id)
        self.assertTrue(len(asgn_rows) > 0)
        assignment_id = asgn_rows[0]['id']

        # 5. Create Timetable Slot
        tt_resp = self.client.post('/timetable/add', data={
            'class_id': str(class_id),
            'day_of_week': 'Monday',
            'start_time': '09:00',
            'end_time': '10:30',
            'room_override': 'Lab 101'
        }, follow_redirects=True)
        self.assertEqual(tt_resp.status_code, 200)

        # 6. Create Quiz as Teacher
        quiz_resp = self.client.post(f'/class/{class_id}/quizzes/create', data={
            'title': 'AI Fundamentals Quiz',
            'description': 'Basic questions on search algorithms',
            'time_limit_minutes': '10',
            'q_1_text': 'What algorithm guarantees shortest path in unweighted graphs?',
            'q_1_a': 'Breadth-First Search (BFS)',
            'q_1_b': 'Depth-First Search (DFS)',
            'q_1_c': 'Linear Search',
            'q_1_d': 'Random Walk',
            'q_1_correct': 'A',
            'q_1_points': '2'
        }, follow_redirects=True)
        self.assertEqual(quiz_resp.status_code, 200)

        quiz_rows = db.execute("SELECT * FROM quizzes WHERE class_id = ?", class_id)
        self.assertTrue(len(quiz_rows) > 0)
        quiz_id = quiz_rows[0]['id']

        # 7. Register & Login as Student
        self.client.get('/logout', follow_redirects=True)
        s_resp = self.client.post('/register', data={
            'username': student_username,
            'password': 'password123',
            'confirmation': 'password123',
            'role': 'student'
        }, follow_redirects=True)
        self.assertEqual(s_resp.status_code, 200)

        # 8. Student Joins Class
        join_resp = self.client.post('/join_class', data={'join_code': join_code}, follow_redirects=True)
        self.assertEqual(join_resp.status_code, 200)

        # 9. Student Adds Comment on Announcement
        comment_resp = self.client.post(f'/announcement/{ann_id}/comment', data={
            'comment_text': 'Is Python 3.12 required for Problem Set 1?'
        }, follow_redirects=True)
        self.assertEqual(comment_resp.status_code, 200)

        # 10. Student Submits Assignment
        sub_resp = self.client.post(f'/assignment/{assignment_id}/submit', data={
            'submission_text': 'My solution code is ready and tested.'
        }, follow_redirects=True)
        self.assertEqual(sub_resp.status_code, 200)

        sub_rows = db.execute("SELECT * FROM submissions WHERE assignment_id = ?", assignment_id)
        self.assertTrue(len(sub_rows) > 0)
        submission_id = sub_rows[0]['id']

        # 11. Student Takes Quiz
        q_rows = db.execute("SELECT * FROM quiz_questions WHERE quiz_id = ?", quiz_id)
        question_id = q_rows[0]['id']
        quiz_sub_resp = self.client.post(f'/quiz/{quiz_id}/submit', data={
            f'question_{question_id}': 'A'
        }, follow_redirects=True)
        self.assertEqual(quiz_sub_resp.status_code, 200)

        attempt_rows = db.execute("SELECT * FROM quiz_attempts WHERE quiz_id = ?", quiz_id)
        self.assertTrue(len(attempt_rows) > 0)
        self.assertEqual(attempt_rows[0]['score'], 2.0)

        # 12. Login back as Teacher and Grade Submission
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'username': teacher_username, 'password': 'password123'}, follow_redirects=True)

        grade_resp = self.client.post(f'/submission/{submission_id}/grade', data={
            'grade': '95.5',
            'feedback': 'Excellent work and clean structure!'
        }, follow_redirects=True)
        self.assertEqual(grade_resp.status_code, 200)

        updated_sub = db.execute("SELECT * FROM submissions WHERE id = ?", submission_id)[0]
        self.assertEqual(updated_sub['grade'], 95.5)
        self.assertEqual(updated_sub['feedback'], 'Excellent work and clean structure!')

        # 13. Test Search
        search_resp = self.client.get('/search?q=Neural', follow_redirects=True)
        self.assertEqual(search_resp.status_code, 200)
        self.assertIn(b'Problem Set 1 - Neural Networks', search_resp.data)

        # Cleanup test entries
        db.execute("DELETE FROM comments WHERE announcement_id = ?", ann_id)
        db.execute("DELETE FROM announcements WHERE id = ?", ann_id)
        db.execute("DELETE FROM submissions WHERE id = ?", submission_id)
        db.execute("DELETE FROM assignments WHERE id = ?", assignment_id)
        db.execute("DELETE FROM quiz_attempts WHERE quiz_id = ?", quiz_id)
        db.execute("DELETE FROM quiz_questions WHERE quiz_id = ?", quiz_id)
        db.execute("DELETE FROM quizzes WHERE id = ?", quiz_id)
        db.execute("DELETE FROM timetable WHERE class_id = ?", class_id)
        db.execute("DELETE FROM enrollments WHERE class_id = ?", class_id)
        db.execute("DELETE FROM classes WHERE id = ?", class_id)
        db.execute("DELETE FROM users WHERE username IN (?, ?)", teacher_username, student_username)
        print("\nALL FEATURE TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    unittest.main()
