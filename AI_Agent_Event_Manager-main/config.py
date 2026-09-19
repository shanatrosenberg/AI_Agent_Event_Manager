import os
from urllib.parse import quote_plus, urlparse

SOMEE_SITE_URL = "http://AiEvents.somee.com"
DEFAULT_DATABASE_HOST = "AiEventsDB.mssql.somee.com"
DEFAULT_DATABASE_NAME = "AiEventsDB"
DEFAULT_DATABASE_USER = "Avishag10_SQLLogin_1"
DEFAULT_DATABASE_PORT = "1433"
DEFAULT_DATABASE_DRIVER = "pyodbc"
DEFAULT_ODBC_DRIVER = "ODBC Driver 17 for SQL Server"


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _parse_ado_net(connection_string: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for item in connection_string.split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[key.strip().lower()] = value.strip()
    return parts


def _is_ado_net(value: str) -> bool:
    lowered = value.lower()
    return any(
        token in lowered
        for token in ("data source=", "initial catalog=", "workstation id=")
    )


def _normalize_somee_host(host: str) -> str:
    """Map a Somee website host to the MS SQL host used by that account."""
    if not host:
        return DEFAULT_DATABASE_HOST

    stripped = host.strip()
    lowered = stripped.lower()
    if lowered.endswith(".mssql.somee.com"):
        return stripped
    # The public website host is not the SQL Server address.
    if lowered.endswith(".somee.com"):
        return DEFAULT_DATABASE_HOST
    return stripped


def _odbc_driver() -> str:
    configured = _env("DATABASE_ODBC_DRIVER")
    if configured:
        return configured
    try:
        import pyodbc

        installed = pyodbc.drivers()
        for preferred in (
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "ODBC Driver 13 for SQL Server",
            "SQL Server",
        ):
            if preferred in installed:
                return preferred
    except Exception:
        pass
    return DEFAULT_ODBC_DRIVER


def _mssql_uri(host: str, database: str, user: str, password: str, port: str) -> str:
    driver = _env("DATABASE_DRIVER", DEFAULT_DATABASE_DRIVER).lower()
    port = port or DEFAULT_DATABASE_PORT
    if driver == "pymssql":
        userinfo = ""
        if user:
            userinfo = quote_plus(user)
            if password:
                userinfo += f":{quote_plus(password)}"
            userinfo += "@"
        return f"mssql+pymssql://{userinfo}{host}:{port}/{database}"

    odbc = (
        f"DRIVER={{{_odbc_driver()}}};"
        f"SERVER={host},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
        "Connection Timeout=30;"
    )
    return f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc)}"


def database_uri() -> str:
    """Build a SQLAlchemy URI for Somee MS SQL, Postgres, or an explicit driver URL."""
    raw = _env("DATABASE_URL")
    if raw:
        if raw.startswith("postgres://"):
            return raw.replace("postgres://", "postgresql://", 1)

        scheme = urlparse(raw).scheme.lower()
        if scheme and scheme not in {"http", "https"} and "://" in raw:
            return raw

        if _is_ado_net(raw):
            parts = _parse_ado_net(raw)
            host = (
                parts.get("data source")
                or parts.get("server")
                or parts.get("workstation id")
                or DEFAULT_DATABASE_HOST
            )
            database = (
                parts.get("initial catalog")
                or parts.get("database")
                or _env("DATABASE_NAME", DEFAULT_DATABASE_NAME)
            )
            user = parts.get("user id") or parts.get("uid") or _env("DATABASE_USER", DEFAULT_DATABASE_USER)
            password = parts.get("pwd") or parts.get("password") or _env("DATABASE_PASSWORD")
            port = _env("DATABASE_PORT", DEFAULT_DATABASE_PORT)
            return _mssql_uri(host, database, user, password, port)

        parsed = urlparse(raw)
        if parsed.scheme in {"http", "https"}:
            netloc = parsed.netloc.split("@")[-1]
            host = _normalize_somee_host(netloc.split(":")[0] or parsed.hostname or "")
            return _mssql_uri(
                host,
                _env("DATABASE_NAME", DEFAULT_DATABASE_NAME),
                _env("DATABASE_USER", parsed.username or DEFAULT_DATABASE_USER),
                _env("DATABASE_PASSWORD", parsed.password or ""),
                _env("DATABASE_PORT", DEFAULT_DATABASE_PORT),
            )

    return _mssql_uri(
        _normalize_somee_host(_env("DATABASE_HOST", DEFAULT_DATABASE_HOST)),
        _env("DATABASE_NAME", DEFAULT_DATABASE_NAME),
        _env("DATABASE_USER", DEFAULT_DATABASE_USER),
        _env("DATABASE_PASSWORD"),
        _env("DATABASE_PORT", DEFAULT_DATABASE_PORT),
    )


def sqlalchemy_engine_options(uri: str) -> dict:
    if not uri.startswith("mssql"):
        return {}
    return {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
