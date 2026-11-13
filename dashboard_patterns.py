"""Documented Factory and GRASP Polymorphism: role-specific SIMS dashboards."""
from abc import ABC, abstractmethod
from internship_models import Student, Employer, Coordinator
from notification_patterns import NotificationAdapter


def _esc(value):
    from html import escape
    return escape(str(value if value is not None else ""), quote=True)


class Dashboard(ABC):
    @abstractmethod
    def render(self, user, query):
        """Render a role-specific dashboard through one common interface."""


class StudentDashboard(Dashboard):
    def render(self, user, query):
        student = Student(user["id"], user["name"], user.get("email", ""), query)
        items = student.trackStatus()
        adapter = NotificationAdapter()
        rows = "".join(
            f'<tr><td>{_esc(a["title"])}</td><td>{_esc(a["status"])}</td>'
            f'<td>{_esc(a["applied_at"])}</td><td>{_esc(adapter.sendStatusUpdate(a["title"],a["status"]))}</td></tr>'
            for a in items
        )
        if not rows:
            return "Student dashboard", '<p>No applications yet. <a href="/internships">Browse internships</a>.</p>'
        return "Student dashboard", (
            '<h2>Your applications and status notifications</h2>'
            '<table><thead><tr><th>Internship</th><th>Status</th><th>Applied</th><th>Notification</th></tr>'
            '</thead><tbody>' + rows + '</tbody></table>'
        )


class EmployerDashboard(Dashboard):
    def render(self, user, query):
        employer = Employer(user["id"], user["name"], user.get("email", ""), query)
        jobs = employer.myPostings()
        rows = "".join(
            f'<li><strong>{_esc(j["title"])}</strong> ({_esc(j["status"])}) — '
            f'<a href="/applicants?internship_id={j["id"]}">View applicants</a> · '
            f'<a href="/internships/{j["id"]}/edit">Edit posting</a></li>' for j in jobs
        )
        return "Employer dashboard", (
            '<p><a href="/internships/new">Post a new internship</a></p>'
            '<h2>Your postings</h2><ul>' + (rows or '<li>No postings yet.</li>') + '</ul>'
        )


class CoordinatorDashboard(Dashboard):
    def render(self, user, query):
        coordinator = Coordinator(user["id"], user["name"], user.get("email", ""), query)
        counts = coordinator.monitorParticipation()
        values = "".join(f'<li>{_esc(label.title())}: {_esc(value)}</li>' for label,value in counts.items())
        return "Coordinator dashboard", (
            '<h2>Internship participation</h2><ul>' + values + '</ul>'
            '<p><a href="/coordinator/activities">View internship activities</a></p>'
        )


class DashboardFactory:
    """Simple Factory matching the Phase 2 diagram: createDashboard(role)."""
    _TYPES = {
        "student": StudentDashboard,
        "employer": EmployerDashboard,
        "coordinator": CoordinatorDashboard,
    }

    @classmethod
    def createDashboard(cls, role):
        concrete_class = cls._TYPES.get(role)
        if concrete_class is None:
            raise ValueError("Unsupported SIMS dashboard role")
        return concrete_class()
