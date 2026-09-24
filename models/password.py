from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class HasPassword:
    """Adds a Werkzeug-hashed password column to a role model."""

    password_hash = db.Column(db.String(255), nullable=True)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, raw_password)
