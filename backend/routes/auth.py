"""
MEDIRED - Cuentas de usuario: registro, inicio de sesión y perfil.

  POST  /api/auth/registro          crea una cuenta de PACIENTE y abre sesión
  POST  /api/auth/login             correo o documento + contraseña -> token
  GET   /api/auth/me                datos del usuario con sesión
  PATCH /api/auth/me                actualizar nombre / teléfono
  POST  /api/auth/cambiar-password
  GET   /api/auth/usuarios          (administrador) listar usuarios
  PATCH /api/auth/usuarios/{id}     (administrador) cambiar rol / activar

Por seguridad nadie puede registrarse con un rol distinto de "paciente":
los operadores y analistas los asigna un administrador.
"""

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import get_db
from models import EPS, Usuario
from schemas import (CambioPassword, LoginIn, PerfilUpdate, RegistroIn, SesionOut,
                     UsuarioAdminUpdate, UsuarioOut)
from security import (crear_token, hash_password, requiere_roles, usuario_actual,
                      verify_password)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Freno básico a la fuerza bruta: 6 intentos fallidos / 10 min por identificador
_fallos: dict[str, list[float]] = defaultdict(list)
_VENTANA, _MAX = 600, 6
_HASH_FALSO = hash_password("no-existe-este-usuario")


def _bloqueado(clave: str) -> bool:
    ahora = time.time()
    _fallos[clave] = [t for t in _fallos[clave] if ahora - t < _VENTANA]
    return len(_fallos[clave]) >= _MAX


@router.post("/registro", response_model=SesionOut, status_code=201)
def registro(payload: RegistroIn, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(func.lower(Usuario.documento) == payload.documento.lower()).first():
        raise HTTPException(409, "Ya existe una cuenta con ese documento.")
    if db.query(Usuario).filter(func.lower(Usuario.email) == payload.email).first():
        raise HTTPException(409, "Ya existe una cuenta con ese correo.")
    eps = db.query(EPS).filter(EPS.activo.is_(True)).order_by(EPS.id_eps).first()
    u = Usuario(
        id_eps=eps.id_eps if eps else None,
        documento=payload.documento, nombre=payload.nombre, email=payload.email,
        telefono=payload.telefono, rol="paciente",
        password_hash=hash_password(payload.password), activo=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return SesionOut(token=crear_token(u), usuario=u)


@router.post("/login", response_model=SesionOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    ident = payload.identificador.strip().lower()
    clave = ident + "|" + (request.client.host if request.client else "")
    if _bloqueado(clave):
        raise HTTPException(429, "Demasiados intentos fallidos. Espera unos minutos e inténtalo de nuevo.")
    u = (db.query(Usuario)
           .filter(or_(func.lower(Usuario.email) == ident, func.lower(Usuario.documento) == ident))
           .first())
    ok = verify_password(payload.password, u.password_hash if u else _HASH_FALSO)
    if not (u and ok):
        _fallos[clave].append(time.time())
        raise HTTPException(401, "Correo/documento o contraseña incorrectos.")
    if not u.activo:
        raise HTTPException(403, "Esta cuenta está desactivada. Contacta al administrador.")
    _fallos.pop(clave, None)
    return SesionOut(token=crear_token(u), usuario=u)


@router.get("/me", response_model=UsuarioOut)
def me(u: Usuario = Depends(usuario_actual)):
    return u


@router.patch("/me", response_model=UsuarioOut)
def actualizar_perfil(payload: PerfilUpdate, u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if payload.nombre:
        u.nombre = " ".join(payload.nombre.split())
    if payload.telefono is not None:
        u.telefono = payload.telefono.strip() or None
    db.commit()
    db.refresh(u)
    return u


@router.post("/cambiar-password", status_code=204)
def cambiar_password(payload: CambioPassword, u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if not verify_password(payload.actual, u.password_hash):
        raise HTTPException(400, "La contraseña actual no es correcta.")
    u.password_hash = hash_password(payload.nueva)
    db.commit()


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(_: Usuario = Depends(requiere_roles("administrador")), db: Session = Depends(get_db)):
    return db.query(Usuario).order_by(Usuario.id_usuario).all()


@router.patch("/usuarios/{id_usuario}", response_model=UsuarioOut)
def modificar_usuario(id_usuario: int, payload: UsuarioAdminUpdate,
                      admin: Usuario = Depends(requiere_roles("administrador")), db: Session = Depends(get_db)):
    u = db.get(Usuario, id_usuario)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    if u.id_usuario == admin.id_usuario and (payload.rol not in (None, "administrador") or payload.activo is False):
        raise HTTPException(400, "No puedes quitarte tu propio rol de administrador ni desactivarte.")
    if payload.rol:
        u.rol = payload.rol
    if payload.activo is not None:
        u.activo = payload.activo
    db.commit()
    db.refresh(u)
    return u
