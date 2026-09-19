from urllib.parse import quote_plus, unquote_plus

from config import database_uri, sqlalchemy_engine_options


def test_builds_somee_uri_from_discrete_env_vars(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_DRIVER", "pyodbc")
    monkeypatch.setenv("DATABASE_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    monkeypatch.setenv("DATABASE_HOST", "AiEventsDB.mssql.somee.com")
    monkeypatch.setenv("DATABASE_NAME", "AiEventsDB")
    monkeypatch.setenv("DATABASE_USER", "Avishag10_SQLLogin_1")
    monkeypatch.setenv("DATABASE_PASSWORD", "p@ss word")
    monkeypatch.setenv("DATABASE_PORT", "1433")

    uri = database_uri()
    assert uri.startswith("mssql+pyodbc:///?odbc_connect=")
    decoded = unquote_plus(uri.split("odbc_connect=", 1)[1])
    assert "DRIVER={ODBC Driver 17 for SQL Server}" in decoded
    assert "SERVER=AiEventsDB.mssql.somee.com,1433" in decoded
    assert "DATABASE=AiEventsDB" in decoded
    assert "UID=Avishag10_SQLLogin_1" in decoded
    assert "PWD=p@ss word" in decoded
    assert "Encrypt=yes" in decoded


def test_maps_somee_website_url_to_sql_host(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "http://AiEvents.somee.com")
    monkeypatch.setenv("DATABASE_DRIVER", "pyodbc")
    monkeypatch.setenv("DATABASE_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    monkeypatch.setenv("DATABASE_NAME", "AiEventsDB")
    monkeypatch.setenv("DATABASE_USER", "Avishag10_SQLLogin_1")
    monkeypatch.setenv("DATABASE_PASSWORD", "secret")
    monkeypatch.setenv("DATABASE_PORT", "1433")

    decoded = unquote_plus(database_uri().split("odbc_connect=", 1)[1])
    assert "SERVER=AiEventsDB.mssql.somee.com,1433" in decoded
    assert "DATABASE=AiEventsDB" in decoded
    assert "UID=Avishag10_SQLLogin_1" in decoded


def test_parses_somee_ado_net_connection_string(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "workstation id=AiEventsDB.mssql.somee.com;packet size=4096;"
        "user id=Avishag10_SQLLogin_1;pwd=Secret!23;"
        "data source=AiEventsDB.mssql.somee.com;"
        "persist security info=False;initial catalog=AiEventsDB",
    )
    monkeypatch.setenv("DATABASE_DRIVER", "pyodbc")
    monkeypatch.setenv("DATABASE_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    monkeypatch.setenv("DATABASE_PORT", "1433")

    decoded = unquote_plus(database_uri().split("odbc_connect=", 1)[1])
    assert "SERVER=AiEventsDB.mssql.somee.com,1433" in decoded
    assert "DATABASE=AiEventsDB" in decoded
    assert "UID=Avishag10_SQLLogin_1" in decoded
    assert "PWD=Secret!23" in decoded


def test_can_build_pymssql_uri_when_requested(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_DRIVER", "pymssql")
    monkeypatch.setenv("DATABASE_HOST", "AiEventsDB.mssql.somee.com")
    monkeypatch.setenv("DATABASE_NAME", "AiEventsDB")
    monkeypatch.setenv("DATABASE_USER", "Avishag10_SQLLogin_1")
    monkeypatch.setenv("DATABASE_PASSWORD", "p@ss word")
    monkeypatch.setenv("DATABASE_PORT", "1433")

    assert database_uri() == (
        f"mssql+pymssql://Avishag10_SQLLogin_1:{quote_plus('p@ss word')}"
        "@AiEventsDB.mssql.somee.com:1433/AiEventsDB"
    )


def test_keeps_explicit_sqlalchemy_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    assert database_uri() == "sqlite:///:memory:"


def test_rewrites_heroku_style_postgres_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@localhost:5432/app")
    assert database_uri() == "postgresql://user:pass@localhost:5432/app"


def test_engine_options_only_for_mssql():
    assert "pool_pre_ping" in sqlalchemy_engine_options("mssql+pyodbc://localhost/db")
    assert sqlalchemy_engine_options("sqlite:///:memory:") == {}
