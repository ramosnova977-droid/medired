"""
MEDIRED - Crear o actualizar usuarios desde la terminal (útil para el primer administrador).

Uso (desde la carpeta backend, con el venv activo):

  python crear_usuario.py --demo
      Crea/actualiza 3 cuentas de DEMOSTRACIÓN con la contraseña  Medired2026
        admin@medired.test     (administrador)
        operador@medired.test  (operador de inventario)
        analista@medired.test  (analista)
      Úsalo solo en desarrollo: son credenciales públicas.

  python crear_usuario.py --rol administrador --documento 1020304050 \
         --nombre "Tu Nombre" --email tu@correo.com
      Te pide la contraseña por teclado (no queda en el historial).
"""

import argparse
import getpass
import sys

from sqlalchemy import func

from database import SessionLocal
from models import EPS, Usuario
from schemas import RegistroIn
from security import ROLES, hash_password

DEMO = [
    ("administrador", "DEMO-ADMIN", "Administrador MEDIRED", "admin@medired.test"),
    ("operador_inventario", "DEMO-OPER", "Operador de Inventario", "operador@medired.test"),
    ("analista", "DEMO-ANAL", "Analista de Datos", "analista@medired.test"),
]


def guardar(db, rol, documento, nombre, email, password):
    u = db.query(Usuario).filter(func.lower(Usuario.email) == email.lower()).first() \
        or db.query(Usuario).filter(func.lower(Usuario.documento) == documento.lower()).first()
    eps = db.query(EPS).order_by(EPS.id_eps).first()
    if not u:
        u = Usuario(documento=documento, nombre=nombre, email=email.lower(), rol=rol,
                    id_eps=eps.id_eps if eps else None, password_hash="x", activo=True)
        db.add(u)
    u.rol, u.activo, u.password_hash = rol, True, hash_password(password)
    db.commit()
    print(f"  ✔ {u.rol:<20} {u.email}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--rol", choices=ROLES)
    ap.add_argument("--documento")
    ap.add_argument("--nombre")
    ap.add_argument("--email")
    a = ap.parse_args()
    db = SessionLocal()
    if a.demo:
        for rol, doc, nom, mail in DEMO:
            guardar(db, rol, doc, nom, mail, "Medired2026")
        print("Contraseña de las cuentas demo: Medired2026")
        return
    if not (a.rol and a.documento and a.nombre and a.email):
        sys.exit("Faltan datos. Usa --demo o indica --rol --documento --nombre --email")
    pw = getpass.getpass("Contraseña (mín. 8, con letra y número): ")
    RegistroIn(documento=a.documento, nombre=a.nombre, email=a.email, password=pw)  # valida formato
    guardar(db, a.rol, a.documento, a.nombre, a.email, pw)


if __name__ == "__main__":
    main()
