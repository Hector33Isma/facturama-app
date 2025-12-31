import getpass

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User


def main():
    with SessionLocal() as session:
        existing = session.scalar(select(User.id).limit(1))
        if existing:
            print("Ya existen usuarios. Abortando.")
            return
        username = input("Usuario admin: ").strip()
        email = input("Email: ").strip()
        if not username or not email:
            print("Usuario y email son requeridos.")
            return
        while True:
            password = getpass.getpass("Contraseña: ")
            confirm = getpass.getpass("Confirma contraseña: ")
            if not password or password != confirm:
                print("Las contraseñas no coinciden o están vacías. Intenta de nuevo.")
                continue
            try:
                pwd_hash = hash_password(password)
                break
            except ValueError as exc:
                print(f"Error: {exc}")
                continue
        user = User(
            username=username,
            email=email,
            full_name="Administrador",
            role="admin",
            is_active=True,
            password_hash=pwd_hash,
        )
        session.add(user)
        session.commit()
        print("Usuario admin creado correctamente.")


if __name__ == "__main__":
    main()
