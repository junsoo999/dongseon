"""Allow ``python -m dongseon`` (used to start background CLI jobs from the API)."""

from dongseon.cli import app

app(prog_name="dongseon")
