# Student Internship Management System (SIMS)
## Python code aligned with the existing Elaboration 1 and Elaboration 2 documents

**No modifications were made to the submitted reports or PowerPoint.** The original five-table MySQL schema is retained. The application remains a local coursework prototype using HTML/CSS, Python and MySQL, with Python's standard-library HTTP server (no Flask required).

### Local setup (Windows / XAMPP)

1. **Keep the `sims` database and its existing records.** Start **MySQL** in XAMPP. Apache is optional and is only needed to open phpMyAdmin at `http://localhost/phpmyadmin`.
2. Extract the zip and **open the folder containing `sims_server.py`** in VS Code. Do not run commands from the outer ZIP extraction folder.
3. Open VS Code's terminal and run:

   ```powershell
   py -m pip install -r requirements.txt
   py test_patterns.py
   py test_sims_design.py
   py sims_server.py
   ```

4. Open **http://127.0.0.1:8000/** in your browser.
5. If your MySQL root user has a password, set it before running the server:

   ```powershell
   $env:SIMS_DB_PASSWORD="your_mysql_password"
   py sims_server.py
   ```

   Other optional environment variables: `SIMS_DB_USER` (default `root`), `SIMS_DB_HOST` (default `127.0.0.1`), `SIMS_DB_NAME` (default `sims`), and `SIMS_PORT` (default `8000`). Do not store passwords in code.
6. **Only on a new installation** without a `sims` database, import `sims_database.sql` in phpMyAdmin. Avoid dropping existing tables.

### What is implemented

The *ten-item use-case list* is taken from the existing Elaboration 2 report. Each function is implemented against the existing core schema.

| ID | Original use case | How to test | Python implementation |
|----|-------------------|-------------|-----------------------|
| UC01 | Register account | `/register`, choose Student, Employer or Coordinator | `Actor.register()` and `user_account_patterns.py` |
| UC02 | Log in | `/login` | `Actor.login()` and password verification in `sims_server.py` |
| UC03 | Browse internships | `/internships` | `Student.browseInternships()` |
| UC04 | Apply for internship | Select an open internship, click Apply | `Student.applyForInternship()`, `Application.submit()` |
| UC05 | Track application status | Student → Dashboard | `Student.trackStatus()`, `Application.viewStatus()` |
| UC06 | Post internship | Employer → Post internship | `Employer.postInternship()` |
| UC07 | Edit internship | Employer → Dashboard → Edit posting | `Employer.editInternship()` |
| UC08 | View applicants | Employer → Dashboard → View applicants | `Employer.viewApplicants()` |
| UC09 | Monitor participation | Coordinator → Dashboard | `Coordinator.monitorParticipation()` |
| UC10 | View internship activities | Coordinator → Dashboard → View activities | `Coordinator.viewActivities()` |

The Phase 1 document also mentions the employer's **application-decision function**. An employer can change its own applicant's status to **accepted** or **declined** on the View Applicants page; students can see that status on their dashboard. These statuses are *application decisions*, not a separate coordinator-approved placement process.

### Class diagram — where to look

`internship_models.py` contains the same five conceptual classes and main method names shown in the Elaboration 2 UML class diagram: **Student**, **Employer**, **Coordinator**, **Internship**, and **Application**. These classes are *actually called by* `sims_server.py` and `dashboard_patterns.py` rather than merely drawn in UML.

### Software design patterns — where to point during a presentation

| Course concept | Documented example | Actual code |
|---------------|--------------------|-------------|
| **Factory** | `Dashboard Factory.createDashboard(role)` selects a Student, Employer or Coordinator dashboard | `dashboard_patterns.py` → `DashboardFactory.createDashboard()`; used by `sims_server.py` in `GET /dashboard` |
| **GRASP Polymorphism** | Common view behavior for role-specific Student, Employer and Coordinator views | `dashboard_patterns.py` → `Dashboard.render()` abstract method, overridden by `StudentDashboard`, `EmployerDashboard`, and `CoordinatorDashboard` |
| **Adapter (GoF)** | Application status update → notification interface with `sendStatusUpdate()` | `notification_patterns.py` → `NotificationAdapter.sendStatusUpdate()` adapts `ApplicationStatusText.describe()`; used in `StudentDashboard.render()` |
| **Expert / Creator / Controller** | Internship details, application state, responsible user actions, request coordination | `internship_models.py` (`Internship`, `Application`, `Student`, `Employer`), and `sims_server.py` (`SIMSHandler`) |
| **Low Coupling / High Cohesion** | Browser cannot query MySQL; role-specific operations are separated | Presentation logic in `sims_server.py`/dashboards; domain operations in `internship_models.py`; database access via `sims_server.query()` |

`user_account_patterns.py` remains from the earlier working version. It normalizes the three different account tables to a common interface; it is **not** the dashboard Factory or status-notification Adapter illustrated in the Elaboration 2 PowerPoint. Refer to `dashboard_patterns.py` and `notification_patterns.py` when presenting the documented examples.

**Notification boundary:** The original Phase 2 Adapter diagram does *not* select an email, SMS, or external provider. This implementation displays a **local, in-app status message** on the student's dashboard. It does not send messages outside SIMS and does not add a notification table.

### Demonstration sequence

1. Register and log in as an **Employer**. Post an internship and use **Edit posting** to update its title or status.
2. Register and log in as a **Student**. Browse internships, apply, and open **Dashboard** to see the application status and the in-app notification.
3. Log back in as the original **Employer**. Click **View applicants** and change the student's application decision to **Accepted**.
4. Log back in as the **Student**. Verify that **Dashboard** shows **accepted**.
5. Register and log in as a **Coordinator**. Open **Dashboard** to view participation totals and **View internship activities** to see student applications.
6. In phpMyAdmin, inspect the five existing tables (`students`, `employers`, `coordinators`, `internships`, and `applications`) to verify persistent records.

### Testing limitations

- `test_patterns.py` checks the pre-existing account adapter/factory components using SQLite.
- `test_sims_workflows.py` checks the six original milestone workflows using SQLite.
- `test_sims_design.py` checks all ten documented core use cases, the dashboard Factory, view Polymorphism, notification Adapter, and ownership checks using a temporary in-memory SQLite test database. It does **not** test the actual XAMPP MySQL connection.
- Running `py sims_server.py` against your real MySQL database is still required to verify local integration. If your `sims` database already has records, they are preserved.
- Supervisor assignments, placement approval, progress-report submission, and evaluations appear in the **broader project scope** but are **not among the ten core Phase 2 use cases**. They remain outside this core prototype rather than being represented as implemented features.

### File overview

- `sims_server.py` — HTTP controller, route access checks, HTML responses, database connector.
- `internship_models.py` — UML domain classes and use-case operations.
- `dashboard_patterns.py` — role-based Dashboard Factory and Polymorphism.
- `notification_patterns.py` — in-app application-status Adapter.
- `user_account_patterns.py` — account-table compatibility wrappers from the working earlier code.
- `sims_database.sql` — unchanged original five MySQL tables.
- `static/sims_styles.css` — original styling with minor support for the new forms and tables.
- `test_sims_design.py`, `test_sims_workflows.py`, `test_patterns.py` — automated local tests.

### Renamed source files

Project-specific filenames are used throughout the package. Start the server with `py sims_server.py`; import the database once from `sims_database.sql` **only if your existing `sims` database has not been created**. The stylesheet is served automatically from `static/sims_styles.css`. Run `py test_sims_workflows.py` and `py test_sims_design.py` for local automated tests. All Python import statements and file references have been updated; the five MySQL tables and application behavior have not been changed by these renames.
