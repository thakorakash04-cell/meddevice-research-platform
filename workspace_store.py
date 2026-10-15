"""Compatibility imports for existing tests and integrations."""
from meddevice_accounts.store import (
    Store, Actor, AccessDenied, ITERATIONS, DEFAULT_PERMISSIONS,
    normalize_username, password_record, password_matches, permissions_for,
)
