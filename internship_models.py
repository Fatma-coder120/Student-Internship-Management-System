"""SIMS domain classes from the Elaboration 1/2 UML class diagram.

Five classes match the documented core entities: Student, Employer,
Coordinator, Internship and Application.  Each method performs its named
responsibility against the existing five-table MySQL schema.  The query
function is supplied by the application layer, preserving the three tiers.
"""
from dataclasses import dataclass


@dataclass
class Actor:
    id: int
    name: str
    email: str
    query: object

    @classmethod
    def register(cls, factory, name, email, password_hash):
        """Delegate registration to the role-specific account adapter."""
        return factory.create(cls.role).register(name, email, password_hash)

    @classmethod
    def login(cls, factory, email):
        """Look up account data; password verification is handled by the controller."""
        return factory.create(cls.role).find_by_email(email)


@dataclass
class Student(Actor):
    role = "student"

    def browseInternships(self):
        return self.query(
            "SELECT i.id,i.title,i.description,u.company_name employer "
            "FROM internships i JOIN employers u ON u.id=i.employer_id "
            "WHERE i.status='open' ORDER BY i.id DESC", many=True,
        )

    def applyForInternship(self, internship_id):
        return Application.submit(self.query, self.id, internship_id)

    def trackStatus(self):
        """Student may see only their own submitted applications and statuses."""
        records = self.query(
            "SELECT a.id AS application_id,a.internship_id,i.title,a.status,a.applied_at "
            "FROM applications a JOIN internships i ON i.id=a.internship_id "
            "WHERE a.student_id=%s ORDER BY a.applied_at DESC,a.id DESC",
            (self.id,), many=True,
        )
        # Apply the documented Application.viewStatus() operation to each row.
        return [
            {**dict(row), "status": Application(row["application_id"], self.id,
                                                 row["internship_id"], row["status"]).viewStatus()}
            for row in records
        ]


@dataclass
class Employer(Actor):
    role = "employer"

    def myPostings(self):
        return self.query(
            "SELECT id,title,status FROM internships WHERE employer_id=%s ORDER BY id DESC",
            (self.id,), many=True,
        )

    def postInternship(self, title, description):
        if not title.strip() or not description.strip():
            raise ValueError("Internship title and description are required")
        return self.query(
            "INSERT INTO internships (employer_id,title,description,status) VALUES (%s,%s,%s,'open')",
            (self.id, title.strip(), description.strip()), write=True,
        )

    def editInternship(self, internship_id, title, description, status):
        if status not in ("open", "closed") or not title.strip() or not description.strip():
            raise ValueError("A title, description and valid status are required")
        # Ownership is checked by a matching employer_id; never update other employers' postings.
        job = self.query(
            "SELECT id FROM internships WHERE id=%s AND employer_id=%s",
            (internship_id, self.id),
        )
        if not job:
            raise PermissionError("Only the employer who posted this internship can edit it")
        return self.query(
            "UPDATE internships SET title=%s,description=%s,status=%s WHERE id=%s AND employer_id=%s",
            (title.strip(), description.strip(), status, internship_id, self.id), write=True,
        )

    def viewApplicants(self, internship_id):
        job = self.query(
            "SELECT id,title FROM internships WHERE id=%s AND employer_id=%s",
            (internship_id, self.id),
        )
        if not job:
            raise PermissionError("Only the posting employer may view applicants")
        applications = self.query(
            "SELECT a.id,u.name AS full_name,u.email,a.applied_at,a.status "
            "FROM applications a JOIN students u ON u.id=a.student_id "
            "WHERE a.internship_id=%s ORDER BY a.applied_at DESC,a.id DESC",
            (internship_id,), many=True,
        )
        return job, applications

    def updateApplicationDecision(self, application_id, decision):
        """Existing documented employer application-decision workflow."""
        if decision not in ("accepted", "declined"):
            raise ValueError("Decision must be accepted or declined")
        owned_application = self.query(
            "SELECT a.id FROM applications a JOIN internships i ON a.internship_id=i.id "
            "WHERE a.id=%s AND i.employer_id=%s",
            (application_id, self.id),
        )
        if not owned_application:
            raise PermissionError("Only the posting employer may review this application")
        return self.query(
            "UPDATE applications SET status=%s WHERE id=%s",
            (decision, application_id), write=True,
        )


@dataclass
class Coordinator(Actor):
    role = "coordinator"

    def monitorParticipation(self):
        """Summary of students, employers, postings and applications."""
        return {
            "students": self.query("SELECT COUNT(*) AS total FROM students")["total"],
            "employers": self.query("SELECT COUNT(*) AS total FROM employers")["total"],
            "internships": self.query("SELECT COUNT(*) AS total FROM internships")["total"],
            "applications": self.query("SELECT COUNT(*) AS total FROM applications")["total"],
        }

    def viewActivities(self):
        """Current internship applications and their statuses (existing records)."""
        return self.query(
            "SELECT a.id,s.name AS student_name,i.title,a.status,a.applied_at "
            "FROM applications a JOIN students s ON s.id=a.student_id "
            "JOIN internships i ON i.id=a.internship_id "
            "ORDER BY a.applied_at DESC,a.id DESC", many=True,
        )


@dataclass
class Internship:
    internshipId: int
    employerId: int
    title: str
    status: str
    description: str

    @classmethod
    def displayDetails(cls, query, internship_id):
        """Details for the selected internship as shown in the UML diagram."""
        return query(
            "SELECT i.*,u.company_name employer FROM internships i "
            "JOIN employers u ON u.id=i.employer_id WHERE i.id=%s",
            (internship_id,),
        )


@dataclass
class Application:
    applicationId: int
    studentId: int
    internshipId: int
    status: str

    @classmethod
    def submit(cls, query, student_id, internship_id):
        internship = query(
            "SELECT id FROM internships WHERE id=%s AND status='open'",
            (internship_id,),
        )
        if not internship:
            raise ValueError("This internship is not accepting applications")
        existing = query(
            "SELECT id FROM applications WHERE internship_id=%s AND student_id=%s",
            (internship_id, student_id),
        )
        if existing:
            raise FileExistsError("You already applied for this internship")
        return query(
            "INSERT INTO applications (internship_id,student_id,status) "
            "VALUES (%s,%s,'submitted')",
            (internship_id, student_id), write=True,
        )

    def viewStatus(self):
        return self.status
