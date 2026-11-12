"""Shared test constants. The password is random per run, never hardcoded."""
import secrets

TEST_PASSWORD = "Tp1!" + secrets.token_urlsafe(18)
WRONG_PASSWORD = TEST_PASSWORD + "-wrong"
