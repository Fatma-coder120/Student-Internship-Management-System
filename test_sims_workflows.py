"""Local HTTP workflow smoke test using a temporary SQLite test double.

This verifies Python page flow independently of MySQL; it does not replace
required testing against the specified MySQL database on the user's computer.
"""
import http.cookiejar
import re
import sqlite3
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import sims_server as app


def run():
    con = sqlite3.connect(':memory:', check_same_thread=False)
    lock = threading.Lock()
    con.executescript('''
    CREATE TABLE students(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT,password_hash TEXT);
    CREATE TABLE employers(id INTEGER PRIMARY KEY AUTOINCREMENT,company_name TEXT,email TEXT,password_hash TEXT);
    CREATE TABLE coordinators(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT,password_hash TEXT);
    CREATE TABLE internships(id INTEGER PRIMARY KEY AUTOINCREMENT,employer_id INT,title TEXT,description TEXT,status TEXT DEFAULT 'open',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE applications(id INTEGER PRIMARY KEY AUTOINCREMENT,internship_id INT,student_id INT,status TEXT DEFAULT 'submitted',applied_at TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
    def fake_query(sql,params=(),many=False,write=False):
        with lock:
            cur = con.execute(sql.replace('%s','?'),params)
            if write:con.commit();return cur.lastrowid
            return cur.fetchall() if many else cur.fetchone()
    con.row_factory=sqlite3.Row
    app.query=fake_query
    srv=ThreadingHTTPServer(('127.0.0.1',0),app.SIMSHandler)
    thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    base=f'http://127.0.0.1:{srv.server_port}'
    def get(path):
        with opener.open(base+path) as r:return r.read().decode('utf8')
    def post(path,fields):
        html=get(path) if path in ['/register','/login','/internships/new'] else get('/internships')
        csrf_match=re.search(r'name="csrf" value="([^"]+)"',html)
        assert csrf_match, f'No CSRF token for {path}'
        fields['csrf']=csrf_match.group(1)
        data=urllib.parse.urlencode(fields).encode()
        with opener.open(urllib.request.Request(base+path,data=data,method='POST')) as r:return r.read().decode('utf8')
    try:
        post('/register',{'name':'Acme Internships','email':'acme@example.test','password':'StrongDemo123','role':'employer'})
        post('/login',{'email':'acme@example.test','password':'StrongDemo123'})
        post('/internships/new',{'title':'Software Internship','description':'Learn backend engineering'})
        assert 'Software Internship' in get('/internships')
        # Log out using CSRF token on dashboard navigation.
        html=get('/dashboard'); token=re.search(r'name="csrf" value="([^"]+)"',html).group(1)
        opener.open(urllib.request.Request(base+'/logout',data=urllib.parse.urlencode({'csrf':token}).encode(),method='POST')).read()
        post('/register',{'name':'Student Example','email':'student@example.test','password':'StudentPass123','role':'student'})
        post('/login',{'email':'student@example.test','password':'StudentPass123'})
        details=get('/internships/1');assert 'Software Internship' in details
        token=re.search(r'name="csrf" value="([^"]+)"',details).group(1)
        opener.open(urllib.request.Request(base+'/apply/1',data=urllib.parse.urlencode({'csrf':token}).encode(),method='POST')).read()
        assert 'Software Internship' in get('/dashboard')
        html=get('/dashboard'); token=re.search(r'name="csrf" value="([^"]+)"',html).group(1)
        opener.open(urllib.request.Request(base+'/logout',data=urllib.parse.urlencode({'csrf':token}).encode(),method='POST')).read()
        post('/login',{'email':'acme@example.test','password':'StrongDemo123'})
        applicants=get('/applicants?internship_id=1')
        assert 'Student Example' in applicants
        print('PASS: HTTP workflow: register, log in, post, browse, apply and view applicants')
    finally:
        srv.shutdown();srv.server_close();con.close()


if __name__=='__main__':run()
