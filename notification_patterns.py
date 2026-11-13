"""Adapter (GoF): application-status notifications via the existing web interface.

The Phase 2 diagram defines sendStatusUpdate(), with no external delivery
provider selected.  Here, the adapter maps the status of an Application to
an in-app notification. There is no email/SMS integration or new database table.
"""
from abc import ABC, abstractmethod


class NotificationInterface(ABC):
    @abstractmethod
    def sendStatusUpdate(self, internship_title, status):
        """Return text suitable for the existing HTML notification area."""


class ApplicationStatusText:
    """Existing system status vocabulary, not an external delivery service."""
    def describe(self, internship_title, status):
        labels = {
            "submitted": "submitted and awaiting review",
            "accepted": "accepted",
            "declined": "declined",
        }
        if status not in labels:
            raise ValueError("Unknown application status")
        return f"Application for {internship_title}: {labels[status]}."


class NotificationAdapter(NotificationInterface):
    """GoF Adapter: implements sendStatusUpdate using a differently named API."""
    def __init__(self, status_text=None):
        self._adaptee = status_text or ApplicationStatusText()

    def sendStatusUpdate(self, internship_title, status):
        return self._adaptee.describe(internship_title, status)
