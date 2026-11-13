"""Small, isolated tests of the three design patterns (no MySQL required).

Run: py test_patterns.py
"""
import sqlite3
import unittest

from user_account_patterns import (
    AccountAdapter, AccountAdapterFactory,
    StudentAccountAdapter, EmployerAccountAdapter, CoordinatorAccountAdapter,
)


class DesignPatternTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, email TEXT, password_hash TEXT);
            CREATE TABLE employers (id INTEGER PRIMARY KEY, company_name TEXT, email TEXT, password_hash TEXT);
            CREATE TABLE coordinators (id INTEGER PRIMARY KEY, name TEXT, email TEXT, password_hash TEXT);
        """)

        def query_function(sql, params=(), many=False, write=False):
            cursor = self.conn.execute(sql.replace("%s", "?"), params)
            if write:
                self.conn.commit()
                return cursor.lastrowid
            rows = cursor.fetchall() if many else cursor.fetchone()
            return rows

        self.factory = AccountAdapterFactory(query_function)

    def tearDown(self):
        self.conn.close()

    def test_factory_creates_correct_adapter(self):
        self.assertIsInstance(self.factory.create("student"), StudentAccountAdapter)
        self.assertIsInstance(self.factory.create("employer"), EmployerAccountAdapter)
        self.assertIsInstance(self.factory.create("coordinator"), CoordinatorAccountAdapter)
        with self.assertRaises(ValueError):
            self.factory.create("administrator")  # Not in the original 3-role prototype.

    def test_polymorphism_same_methods_different_tables(self):
        examples = [
            ("student", "Student Example", "student@example.test"),
            ("employer", "Acme Company", "employer@example.test"),
            ("coordinator", "Coordinator Example", "coord@example.test"),
        ]
        for role, name, email in examples:
            adapter = self.factory.create(role)
            self.assertIsInstance(adapter, AccountAdapter)
            new_id = adapter.register(name, email, "test-hash")
            self.assertGreater(new_id, 0)
            # Polymorphism: same call works for each concrete adapter.
            found = adapter.find_by_email(email)
            self.assertEqual(found["display_name"], name)
            self.assertEqual(found["role"], role)
            self.assertEqual(found["password_hash"], "test-hash")

        for table in ("students", "employers", "coordinators"):
            self.assertEqual(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 1)

    def test_adapter_hides_employer_company_name_difference(self):
        employer = self.factory.create("employer")
        employer.register("Northstar Motors", "northstar@example.test", "test-hash")
        raw = self.conn.execute(
            "SELECT company_name FROM employers WHERE email=?", ("northstar@example.test",)
        ).fetchone()
        self.assertEqual(raw["company_name"], "Northstar Motors")

        account = employer.find_by_email("northstar@example.test")
        self.assertEqual(account["display_name"], "Northstar Motors")
        self.assertNotIn("company_name", account)


if __name__ == "__main__":
    unittest.main(verbosity=2)
