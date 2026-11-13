"""End-to-end local test of the ten documented SIMS core use cases.

Uses an in-memory SQLite test double to exercise the real Python HTTP handlers.
This does NOT replace the required local XAMPP/MySQL demonstration.
"""
import contextlib
import http.cookiejar
import re
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import sims_server as app
from dashboard_patterns import DashboardFactory, Dashboard, StudentDashboard, EmployerDashboard, CoordinatorDashboard
from notification_patterns import NotificationAdapter, NotificationInterface


def check_core_design_patterns():
    assert isinstance(DashboardFactory.createDashboard('student'), StudentDashboard)
    assert isinstance(DashboardFactory.createDashboard('employer'), EmployerDashboard)
    assert isinstance(DashboardFactory.createDashboard('coordinator'), CoordinatorDashboard)
    assert all(isinstance(DashboardFactory.createDashboard(r), Dashboard) for r in ('student','employer','coordinator'))
    assert isinstance(NotificationAdapter(), NotificationInterface)
    assert 'accepted' in NotificationAdapter().sendStatusUpdate('Internship A', 'accepted')
    try:
        DashboardFactory.createDashboard('administrator')
        raise AssertionError('Unrecognized actor should be rejected')
    except ValueError:
        pass


def run():
    check_core_design_patterns()
    conn = sqlite3.connect(':memory:', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    lock = threading.Lock()
    conn.executescript('''
      CREATE TABLE students(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT,password_hash TEXT);
      CREATE TABLE employers(id INTEGER PRIMARY KEY AUTOINCREMENT,company_name TEXT,email TEXT,password_hash TEXT);
      CREATE TABLE coordinators(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT,password_hash TEXT);
      CREATE TABLE internships(id INTEGER PRIMARY KEY AUTOINCREMENT,employer_id INT,title TEXT,description TEXT,status TEXT DEFAULT 'open',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
      CREATE TABLE applications(id INTEGER PRIMARY KEY AUTOINCREMENT,internship_id INT,student_id INT,status TEXT DEFAULT 'submitted',applied_at TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')

    def test_query(sql, params=(), many=False, write=False):
        with lock:
            cursor = conn.execute(sql.replace('%s', '?'), params)
            if write:
                conn.commit()
                return cursor.lastrowid
            return cursor.fetchall() if many else cursor.fetchone()

    app.query = test_query
    app.SESSIONS.clear()
    server = ThreadingHTTPServer(('127.0.0.1', 0), app.SIMSHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    url = f'http://127.0.0.1:{server.server_port}'

    def client():
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(opener, path):
        try:
            with opener.open(url+path) as response:
                return response.status, response.read().decode('utf8')
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode('utf8')

    def post(opener, endpoint, form_endpoint, values):
        _, form_page = get(opener, form_endpoint)
        token = re.search(r'name="csrf" value="([^"]+)"', form_page)
        assert token is not None, f'No CSRF found for {form_endpoint}'
        fields = {**values, 'csrf': token.group(1)}
        request = urllib.request.Request(url+endpoint, data=urllib.parse.urlencode(fields).encode('utf8'), method='POST')
        try:
            with opener.open(request) as response:
                return response.status, response.read().decode('utf8')
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode('utf8')

    def logout(opener):
        status, _ = post(opener, '/logout', '/dashboard', {})
        assert status == 200

    def register_login(opener, name, email, role):
        status, _ = post(opener, '/register', '/register', {'name':name,'email':email,'password':'StrongPassword123','role':role})
        assert status == 200
        status, page = post(opener, '/login', '/login', {'email':email,'password':'StrongPassword123'})
        assert status == 200 and f'{role.title()} dashboard' in page

    employer = client()
    student = client()
    another_employer = client()
    coordinator = client()

    try:
        # UC01, UC02, UC06: Account registration, login, internship publication.
        register_login(employer, 'Acme Limited', 'acme@demo.test', 'employer')
        assert post(employer, '/internships/new', '/internships/new',
                    {'title':'Junior Software Internship','description':'Build a class project'})[0] == 200
        assert 'Junior Software Internship' in get(employer, '/dashboard')[1]

        # UC07: Existing employer edits its own posting.
        edit_path = '/internships/1/edit'
        assert 'Junior Software Internship' in get(employer, edit_path)[1]
        status, page = post(employer, edit_path, edit_path,
                            {'title':'Software Developer Internship','description':'Build applications','status':'open'})
        assert status == 200 and 'Software Developer Internship' in page

        # UC03, UC04, UC05: Student browses, applies, tracks status.
        register_login(student, 'Example Student', 'student@demo.test', 'student')
        assert 'Software Developer Internship' in get(student, '/internships')[1]
        assert post(student, '/apply/1', '/internships/1', {})[0] == 200
        page = get(student, '/dashboard')[1]
        assert 'Software Developer Internship' in page and 'submitted' in page and 'awaiting review' in page
        assert post(student, '/apply/1', '/internships/1', {})[0] == 409

        # Permission checks: students do not edit employer records or read applicants.
        assert get(student, edit_path)[0] == 403
        assert get(student, '/applicants?internship_id=1')[0] == 403

        register_login(another_employer, 'Other Employer', 'other@demo.test', 'employer')
        assert get(another_employer, edit_path)[0] == 403
        assert get(another_employer, '/applicants?internship_id=1')[0] == 403

        # UC08: Employer views applicants and their current status.
        applicants_url = '/applicants?internship_id=1'
        assert 'Example Student' in get(employer, applicants_url)[1]
        # Original report additionally permits employers to update application decisions.
        assert post(another_employer, '/applications/decision', '/dashboard',
                    {'application_id':'1','decision':'accepted'})[0] == 403
        assert post(employer, '/applications/decision', applicants_url,
                    {'application_id':'1','decision':'accepted'})[0] == 200
        page = get(student, '/dashboard')[1]
        assert 'accepted' in page and 'Application for Software Developer Internship' in page

        # UC09, UC10: Coordinator monitors participation and views activities.
        register_login(coordinator, 'Internship Coordinator', 'coordinator@demo.test', 'coordinator')
        dashboard = get(coordinator, '/dashboard')[1]
        assert 'Students: 1' in dashboard and 'Employers: 2' in dashboard and 'Applications: 1' in dashboard
        activities = get(coordinator, '/coordinator/activities')[1]
        assert 'Example Student' in activities and 'accepted' in activities
        assert get(student, '/coordinator/activities')[0] == 403

        # Ensure real SQLite test tables retain the expected application state.
        saved = conn.execute('SELECT status FROM applications WHERE id=1').fetchone()['status']
        assert saved == 'accepted'
        assert conn.execute('SELECT COUNT(*) AS n FROM internships').fetchone()['n'] == 1
        print('PASS: 10 documented core SIMS use cases (UC01–UC10), dashboard factory,')
        print('      dashboard polymorphism, notification adapter, ownership checks,')
        print('      and employer application decisions (SQLite-based HTTP test).')
    finally:
        server.shutdown()
        server.server_close()
        conn.close()
        app.SESSIONS.clear()


if __name__ == '__main__':
    run()
