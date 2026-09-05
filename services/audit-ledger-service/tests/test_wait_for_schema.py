import pytest

from app.wait_for_schema import psycopg_database_url


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "postgresql://ledger:secret@postgres:5432/crimelens",
            "postgresql://ledger:secret@postgres:5432/crimelens",
        ),
        (
            "postgresql+psycopg2://ledger:secret@postgres:5432/crimelens",
            "postgresql://ledger:secret@postgres:5432/crimelens",
        ),
    ],
)
def test_psycopg_database_url_accepts_render_and_compose_formats(source, expected):
    assert psycopg_database_url(source) == expected


def test_psycopg_database_url_rejects_non_postgresql_urls():
    with pytest.raises(ValueError, match="PostgreSQL"):
        psycopg_database_url("sqlite:///ledger.db")
