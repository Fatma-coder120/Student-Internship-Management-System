"""GRASP Polymorphism, GoF Adapter, and Simple Factory for SIMS accounts.

The existing SIMS database stores Students, Employers, and Coordinators in
separate tables; an Employer has ``company_name`` while the other roles have
``name``. Each adapter presents the same interface and returns a normalized
account record, so the HTTP code does not need to know those differences.

No schema change is required: adapters use existing tables and columns.
"""

from abc import ABC, abstractmethod


class AccountAdapter(ABC):
    """Common target interface for role-specific accounts (Adapter pattern)."""

    role = ""

    def __init__(self, query_function):
        # Inject the existing app.query function instead of creating new DB code.
        self._query = query_function

    @abstractmethod
    def find_by_email(self, email):
        """Return {id, display_name, email, password_hash, role} or None."""

    @abstractmethod
    def register(self, name, email, password_hash):
        """Create the account in its role-specific database table."""

    def _normalized(self, record):
        # All adapters return the same representation to the application.
        return {**dict(record), "role": self.role} if record else None


class StudentAccountAdapter(AccountAdapter):
    role = "student"

    def find_by_email(self, email):
        record = self._query(
            "SELECT id,name AS display_name,email,password_hash FROM students WHERE email=%s",
            (email,),
        )
        return self._normalized(record)

    def register(self, name, email, password_hash):
        return self._query(
            "INSERT INTO students (name,email,password_hash) VALUES (%s,%s,%s)",
            (name, email, password_hash), write=True,
        )


class EmployerAccountAdapter(AccountAdapter):
    role = "employer"

    def find_by_email(self, email):
        # ADAPTER: the database calls this column company_name, not name.
        record = self._query(
            "SELECT id,company_name AS display_name,email,password_hash FROM employers WHERE email=%s",
            (email,),
        )
        return self._normalized(record)

    def register(self, name, email, password_hash):
        return self._query(
            "INSERT INTO employers (company_name,email,password_hash) VALUES (%s,%s,%s)",
            (name, email, password_hash), write=True,
        )


class CoordinatorAccountAdapter(AccountAdapter):
    role = "coordinator"

    def find_by_email(self, email):
        record = self._query(
            "SELECT id,name AS display_name,email,password_hash FROM coordinators WHERE email=%s",
            (email,),
        )
        return self._normalized(record)

    def register(self, name, email, password_hash):
        return self._query(
            "INSERT INTO coordinators (name,email,password_hash) VALUES (%s,%s,%s)",
            (name, email, password_hash), write=True,
        )


class AccountAdapterFactory:
    """Simple Factory: make the right adapter for a known SIMS account role."""

    _ADAPTER_TYPES = {
        "student": StudentAccountAdapter,
        "employer": EmployerAccountAdapter,
        "coordinator": CoordinatorAccountAdapter,
    }

    def __init__(self, query_function):
        self._query = query_function

    def create(self, role):
        adapter_class = self._ADAPTER_TYPES.get(role)
        if adapter_class is None:
            raise ValueError("Unknown SIMS account role")
        return adapter_class(self._query)

    def all_adapters(self):
        return [self.create(role) for role in self._ADAPTER_TYPES]
