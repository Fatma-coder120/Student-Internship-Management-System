"""Student Internship Management System — Python implementation of the documented
Elaboration 1/2 core use cases, UML domain model, and design-pattern examples.

Technologies: Python's standard-library HTTP server, HTML/CSS and MySQL.
The original five MySQL tables and their existing data are preserved.
"""
import hashlib
import hmac
import html
import os
import secrets
from datetime import datetime
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# The application uses documented domain classes, role-specific dashboards,
# and an in-app notification adapter; it retains the working account adapters.
from user_account_patterns import AccountAdapterFactory
from dashboard_patterns import DashboardFactory
from internship_models import Student, Employer, Coordinator, Internship

ACTOR_TYPES = {"student": Student, "employer": Employer, "coordinator": Coordinator}

try:
    import mysql.connector
except ImportError:
    mysql = None

HOST = "127.0.0.1"
PORT = int(os.environ.get("SIMS_PORT", "8000"))
SESSIONS = {}  # Local classroom prototype: sessions reset when server stops.


def escape(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def _esc_plain(value):
    return escape(value)


def pw_hash(password):
    salt = secrets.token_hex(16)
    iterations = 200_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def pw_verify(password, encoded):
    try:
        method, iters, salt, value = encoded.split("$")
        if method != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(actual, bytes.fromhex(value))
    except (AttributeError, TypeError, ValueError):
        return False


def db():
    if mysql is None:
        raise RuntimeError("Install the MySQL driver: pip install -r requirements.txt")
    return mysql.connector.connect(
        host=os.environ.get("SIMS_DB_HOST", "127.0.0.1"),
        user=os.environ.get("SIMS_DB_USER", "root"),
        password=os.environ.get("SIMS_DB_PASSWORD", ""),
        database=os.environ.get("SIMS_DB_NAME", "sims"),
        autocommit=False,
    )


CSS = "/static/sims_styles.css"


def layout(title, content, user=None, csrf="", message=""):
    links = '<a href="/internships">Internships</a>'
    if user:
        links += ' <a href="/dashboard">Dashboard</a>'
        if user["role"] == "employer":
            links += ' <a href="/internships/new">Post internship</a>'
        links += (f'<form method="post" action="/logout" class="inline"><input type="hidden" name="csrf" '
                  f'value="{escape(csrf)}"><button class="nav-button">Log out</button></form>')
    else:
        links += ' <a href="/register">Register</a> <a href="/login">Log in</a>'
    alert = f'<div class="alert">{escape(message)}</div>' if message else ""
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} — SIMS</title><link rel="stylesheet" href="{CSS}"></head><body><header><div class="wrap header"><strong>SIMS</strong><nav>{links}</nav></div></header><main class="wrap"><h1>{escape(title)}</h1>{alert}{content}</main><footer class="wrap">Student Internship Management System</footer></body></html>'''


def form_field(name, label, typ="text", required=True, extra=""):
    return f'<label>{escape(label)}<input name="{escape(name)}" type="{escape(typ)}" {"required" if required else ""} {extra}></label>'


def csrf_field(session):
    return f'<input type="hidden" name="csrf" value="{escape(session["csrf"])}">'


def query(sql, params=(), many=False, write=False):
    conn = db()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        result = cur.fetchall() if many else (None if write else cur.fetchone())
        if write:
            last_id = cur.lastrowid
            conn.commit()
            return last_id
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class SIMSHandler(BaseHTTPRequestHandler):
    def _session(self):
        jar = cookies.SimpleCookie()
        try:
            jar.load(self.headers.get("Cookie", ""))
        except cookies.CookieError:
            jar = cookies.SimpleCookie()
        token = jar["sims_session"].value if "sims_session" in jar else ""
        if token not in SESSIONS:
            token = secrets.token_urlsafe(32)
            SESSIONS[token] = {"user": None, "csrf": secrets.token_urlsafe(24)}
        self.sid = token
        return SESSIONS[token]

    def _send(self, title, body, status=200, message=""):
        session = SESSIONS[self.sid]
        output = layout(title, body, session["user"], session["csrf"], message).encode("utf8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(output)))
        self.send_header("Set-Cookie", f"sims_session={self.sid}; Path=/; HttpOnly; SameSite=Lax")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(output)

    def _redirect(self, where):
        self.send_response(303)
        self.send_header("Location", where)
        self.send_header("Set-Cookie", f"sims_session={self.sid}; Path=/; HttpOnly; SameSite=Lax")
        self.end_headers()

    def _get_form(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 64_000:
            raise ValueError("Request too large")
        data = parse_qs(self.rfile.read(length).decode("utf8"), keep_blank_values=True)
        return {key: value[0].strip() for key, value in data.items()}

    def _require(self, *roles):
        user = SESSIONS[self.sid]["user"]
        if not user:
            self._redirect("/login")
            return None
        if roles and user["role"] not in roles:
            self._send("Access denied", "<p>This page is not available to your role.</p>", 403)
            return None
        return user

    def do_GET(self):
        session = self._session()
        path = urlparse(self.path).path
        try:
            if path == "/static/sims_styles.css":
                with open(os.path.join(os.path.dirname(__file__), "static", "sims_styles.css"), "rb") as f:
                    b = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/css")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers(); self.wfile.write(b); return
            if path == "/":
                return self._redirect("/internships")
            if path == "/register":
                content = ('<p>Create a Student, Employer, or Coordinator account.</p><form method="post" action="/register">'
                           + csrf_field(session) + form_field("name", "Full name / company name")
                           + form_field("email", "Email", "email")
                           + form_field("password", "Password", "password", extra='minlength="8"')
                           + '<label>Role<select name="role"><option value="student">Student</option><option value="employer">Employer</option><option value="coordinator">Coordinator</option></select></label>'
                           + '<button>Create account</button></form>')
                return self._send("Register", content)
            if path == "/login":
                content = ('<form method="post" action="/login">' + csrf_field(session)
                           + form_field("email", "Email", "email") + form_field("password", "Password", "password")
                           + '<button>Log in</button></form>')
                return self._send("Log in", content)
            if path == "/dashboard":
                user = self._require()
                if user is None: return
                # FACTORY (GoF example): documented role-specific dashboard selection.
                # POLYMORPHISM (GRASP): render() dispatches to the actual role subclass.
                title, content = DashboardFactory.createDashboard(user["role"]).render(user, query)
                return self._send(title, content)
            if path == "/internships":
                actor = session["user"]
                if actor and actor["role"] == "student":
                    jobs = Student(actor["id"], actor["name"], actor.get("email", ""), query).browseInternships()
                else:
                    jobs = query("SELECT i.id,i.title,i.description,u.company_name employer FROM internships i JOIN employers u ON u.id=i.employer_id WHERE i.status='open' ORDER BY i.id DESC", many=True)
                cards = ''.join(f'<article class="card"><h2>{escape(j["title"])}</h2><p>{escape(j["description"])}</p><p class="muted">Employer: {escape(j["employer"])}</p><a href="/internships/{j["id"]}">View opportunity</a></article>' for j in jobs)
                return self._send("Internship opportunities", cards or "<p>No internship opportunities have been posted.</p>")
            if path == "/internships/new":
                user = self._require("employer")
                if user is None: return
                content = ('<form method="post" action="/internships/new">' + csrf_field(session)
                           + form_field("title", "Internship title")
                           + '<label>Description<textarea name="description" rows="6" required></textarea></label>'
                           + '<button>Publish opportunity</button></form>')
                return self._send("Post internship", content)
            if path.startswith("/internships/") and path.endswith("/edit") and path.split("/")[-2].isdigit():
                user = self._require("employer")
                if user is None: return
                job_id = int(path.split("/")[-2])
                j = query("SELECT id,title,description,status FROM internships WHERE id=%s AND employer_id=%s", (job_id, user["id"]))
                if not j:
                    return self._send("Access denied", "<p>This internship does not belong to your account.</p>", 403)
                options = ''.join(
                    f'<option value="{status}" {"selected" if status == j["status"] else ""}>{status.title()}</option>'
                    for status in ("open", "closed")
                )
                content = (f'<form method="post" action="/internships/{job_id}/edit">' + csrf_field(session)
                    + f'<label>Internship title<input name="title" required value="{escape(j["title"])}"></label>'
                    + f'<label>Description<textarea name="description" rows="6" required>{escape(j["description"])}</textarea></label>'
                    + f'<label>Status<select name="status">{options}</select></label>'
                    + '<button>Save changes</button></form>')
                return self._send("Edit internship", content)
            if path.startswith("/internships/") and path.split("/")[-1].isdigit():
                job_id = int(path.rsplit("/", 1)[1])
                j = Internship.displayDetails(query, job_id)
                if not j: return self._send("Not found", "<p>Internship not found.</p>", 404)
                content = f'<article class="card"><h2>{escape(j["title"])}</h2><p>{escape(j["description"])}</p><p>Employer: {escape(j["employer"])}</p><p>Status: {escape(j["status"])}</p></article>'
                if session["user"] and session["user"]["role"] == "student" and j["status"] == "open":
                    content += f'<form method="post" action="/apply/{job_id}">' + csrf_field(session) + '<button>Apply for internship</button></form>'
                return self._send("Internship details", content)
            if path == "/applicants":
                user = self._require("employer")
                if user is None: return
                raw = parse_qs(urlparse(self.path).query).get("internship_id", [""])[0]
                if not raw.isdigit(): return self._send("Invalid internship", "<p>Choose a posting from the dashboard.</p>", 400)
                job_id = int(raw)
                employer = Employer(user["id"], user["name"], user.get("email", ""), query)
                try:
                    job, rows = employer.viewApplicants(job_id)
                except PermissionError:
                    return self._send("Access denied", "<p>This posting is not yours.</p>", 403)
                list_items = ''
                for r in rows:
                    choices = ''.join(
                        f'<option value="{v}">{v.title()}</option>' for v in ("accepted", "declined")
                    )
                    decision_form = (
                        '<form method="post" action="/applications/decision" class="decision-form">'
                        + csrf_field(session)
                        + f'<input type="hidden" name="application_id" value="{r["id"]}">'
                        + f'<select name="decision" aria-label="Decision for {_esc_plain(r["full_name"])}">{choices}</select>'
                        + '<button>Update decision</button></form>'
                    )
                    list_items += (f'<tr><td>{escape(r["full_name"])}</td><td>{escape(r["email"])}</td>'
                                   f'<td>{escape(r["applied_at"])}</td><td>{escape(r["status"])}</td>'
                                   f'<td>{decision_form}</td></tr>')
                table = ('<table><thead><tr><th>Student</th><th>Email</th><th>Applied</th>'
                         '<th>Status</th><th>Update</th></tr></thead><tbody>' + list_items + '</tbody></table>') if rows else '<p>No applications received yet.</p>'
                return self._send("Applicants — " + job["title"], table)
            if path == "/coordinator/activities":
                user = self._require("coordinator")
                if user is None: return
                c = Coordinator(user["id"], user["name"], user.get("email", ""), query)
                activities = c.viewActivities()
                rows = ''.join(
                    f'<tr><td>{escape(a["student_name"])}</td><td>{escape(a["title"])}</td>'
                    f'<td>{escape(a["status"])}</td><td>{escape(a["applied_at"])}</td></tr>'
                    for a in activities
                )
                output = ('<table><thead><tr><th>Student</th><th>Internship</th><th>Status</th>'
                          '<th>Applied</th></tr></thead><tbody>' + rows + '</tbody></table>') if rows else '<p>No activities to display.</p>'
                return self._send("Internship activities", output)
            return self._send("Not found", "<p>The page was not found.</p>", 404)
        except Exception as exc:
            self.log_error("SIMS GET failed: %s", exc)
            self._send("Application error", "<p>Check that MySQL is running and the database has been created. See README.md for setup instructions.</p>", 500)

    def do_POST(self):
        session = self._session()
        path = urlparse(self.path).path
        try:
            form = self._get_form()
            if not hmac.compare_digest(form.get("csrf", ""), session["csrf"]):
                return self._send("Invalid request", "<p>Refresh the form and try again.</p>", 403)
            if path == "/register":
                name, email, password, role = form.get("name", ""), form.get("email", "").lower(), form.get("password", ""), form.get("role", "")
                if not name or "@" not in email or len(password) < 8 or role not in ("student", "employer", "coordinator"):
                    return self._send("Register", '<p>Provide a name, valid email, password (at least 8 characters), and role.</p><a href="/register">Try again</a>', 400)
                factory = AccountAdapterFactory(query)
                if any(adapter.find_by_email(email) for adapter in factory.all_adapters()):
                    return self._send("Register", '<p>Email is already registered.</p><a href="/login">Log in</a>', 409)
                ACTOR_TYPES[role].register(factory, name, email, pw_hash(password))
                return self._redirect("/login")
            if path == "/login":
                email, password = form.get("email", "").lower(), form.get("password", "")
                factory = AccountAdapterFactory(query)
                user = None
                for actor_type in ACTOR_TYPES.values():
                    user = actor_type.login(factory, email)
                    if user:
                        break
                if not user or not pw_verify(password, user["password_hash"]):
                    return self._send("Log in", '<p>Invalid email or password.</p><a href="/login">Try again</a>', 401)
                session["user"] = {"id": user["id"], "name": user["display_name"], "email": user["email"], "role": user["role"]}
                session["csrf"] = secrets.token_urlsafe(24)
                return self._redirect("/dashboard")
            if path == "/logout":
                session["user"] = None
                session["csrf"] = secrets.token_urlsafe(24)
                return self._redirect("/login")
            if path == "/internships/new":
                user = self._require("employer")
                if user is None: return
                title, description = form.get("title", ""), form.get("description", "")
                if not title or not description: return self._send("Invalid posting", "<p>Title and description are required.</p>", 400)
                employer = Employer(user["id"], user["name"], user.get("email", ""), query)
                try:
                    employer.postInternship(title, description)
                except ValueError as err:
                    return self._send("Invalid posting", f"<p>{escape(err)}</p>", 400)
                return self._redirect("/dashboard")
            if path.startswith("/internships/") and path.endswith("/edit") and path.split("/")[-2].isdigit():
                user = self._require("employer")
                if user is None: return
                employer = Employer(user["id"], user["name"], user.get("email", ""), query)
                job_id = int(path.split("/")[-2])
                try:
                    employer.editInternship(job_id, form.get("title", ""), form.get("description", ""), form.get("status", ""))
                except PermissionError as err:
                    return self._send("Access denied", f"<p>{escape(err)}</p>", 403)
                except ValueError as err:
                    return self._send("Invalid posting", f"<p>{escape(err)}</p>", 400)
                return self._redirect("/dashboard")
            if path == "/applications/decision":
                user = self._require("employer")
                if user is None: return
                raw = form.get("application_id", "")
                if not raw.isdigit():
                    return self._send("Invalid application", "<p>Choose a valid application.</p>", 400)
                app_id = int(raw)
                employer = Employer(user["id"], user["name"], user.get("email", ""), query)
                try:
                    employer.updateApplicationDecision(app_id, form.get("decision", ""))
                except PermissionError as err:
                    return self._send("Access denied", f"<p>{escape(err)}</p>", 403)
                except ValueError as err:
                    return self._send("Invalid decision", f"<p>{escape(err)}</p>", 400)
                job = query("SELECT internship_id FROM applications WHERE id=%s", (app_id,))
                return self._redirect(f'/applicants?internship_id={job["internship_id"]}')
            if path.startswith("/apply/") and path.rsplit("/",1)[1].isdigit():
                user = self._require("student")
                if user is None: return
                job_id = int(path.rsplit("/",1)[1])
                student = Student(user["id"], user["name"], user.get("email", ""), query)
                try:
                    student.applyForInternship(job_id)
                except FileExistsError:
                    return self._send("Already applied", '<p>You already applied for this internship.</p><a href="/dashboard">View applications</a>', 409)
                except ValueError:
                    return self._send("Unavailable", "<p>This internship is no longer accepting applications.</p>", 400)
                return self._redirect("/dashboard")
            return self._send("Not found", "<p>Unknown action.</p>", 404)
        except Exception as exc:
            self.log_error("SIMS POST failed: %s", exc)
            self._send("Application error", "<p>Check your MySQL connection and database schema. See README.md.</p>", 500)


if __name__ == "__main__":
    print(f"SIMS local prototype: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), SIMSHandler).serve_forever()
