"""
MEDIRED - Seguridad: hash de contraseñas, tokens firmados y control de roles.

Solo usa la librería estándar (hashlib / hmac), así no hay dependencias nuevas.
  * Contraseñas: PBKDF2-HMAC-SHA256 con sal aleatoria (formato
    "pbkdf2_sha256$iteraciones$sal$hash").
  * Sesión: token firmado con HMAC-SHA256 que expira (formato "payload.firma").
    Se envía en la cabecera:  Authorization: Bearer <token>
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from config import SECRET_KEY, TOKEN_HORAS
from database import get_db
from models import Usuario

ITERACIONES = 200_000
ROLES = ("paciente", "operador_inventario", "administrador", "analista")
ROLES_STAFF = ("operador_inventario", "administrador", "analista")
ROLES_OPERACION = ("operador_inventario", "administrador")

_bearer = HTTPBearer(auto_error=False, description="Pega aquí el token que devuelve /api/auth/login")


# ---------------------------------------------------------------- contraseñas
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), sal, ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${_b64(sal)}${_b64(h)}"


def verify_password(password: str, almacenado: Optional[str]) -> bool:
    try:
        algo, iters, sal, h = (almacenado or "").split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(sal), int(iters))
        return hmac.compare_digest(calc, _unb64(h))
    except Exception:
        return False  # p. ej. el 'HASH_SINTETICO' del seed: no permite iniciar sesión


# -------------------------------------------------------------------- tokens
def crear_token(usuario: Usuario) -> str:
    payload = {"sub": usuario.id_usuario, "rol": usuario.rol,
               "exp": int(time.time() + TOKEN_HORAS * 3600)}
    cuerpo = _b64(json.dumps(payload, separators=(",", ":")).encode())
    firma = _b64(hmac.new(SECRET_KEY.encode(), cuerpo.encode(), hashlib.sha256).digest())
    return f"{cuerpo}.{firma}"


def leer_token(token: str) -> Optional[dict]:
    try:
        cuerpo, firma = token.split(".")
        esperada = _b64(hmac.new(SECRET_KEY.encode(), cuerpo.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(firma, esperada):
            return None
        payload = json.loads(_unb64(cuerpo))
        return payload if payload.get("exp", 0) > time.time() else None
    except Exception:
        return None


# -------------------------------------------------------------- dependencias
def usuario_actual(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    """Exige sesión iniciada. 401 si falta el token o expiró."""
    payload = leer_token(cred.credentials) if cred else None
    if not payload:
        raise HTTPException(status_code=401, detail="Sesión no válida o expirada. Inicia sesión de nuevo.")
    u = db.get(Usuario, payload["sub"])
    if not u or not u.activo:
        raise HTTPException(status_code=401, detail="Usuario no disponible.")
    return u


def requiere_roles(*roles: str):
    """Dependencia: exige sesión y que el rol esté en la lista."""
    def _dep(u: Usuario = Depends(usuario_actual)) -> Usuario:
        if u.rol not in roles:
            raise HTTPException(status_code=403, detail="Tu rol no tiene permiso para esta acción.")
        return u
    return _dep
