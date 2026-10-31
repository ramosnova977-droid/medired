
"""
MEDIRED - Esquemas Pydantic (contratos de entrada/salida de la API).
"""

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------
# Medicamento
# ---------------------------------------------------------------------
class MedicamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_medicamento: int
    codigo_cum: Optional[str] = None
    codigo_ium: Optional[str] = None
    nombre: str
    principio_activo: str
    forma_farmaceutica: str
    concentracion: Optional[str] = None
    via_administracion: Optional[str] = None
    requiere_formula: bool
    activo: bool


class MedicamentoCreate(BaseModel):
    codigo_cum: Optional[str] = None
    codigo_ium: Optional[str] = None
    nombre: str
    principio_activo: str
    forma_farmaceutica: str
    concentracion: Optional[str] = None
    via_administracion: Optional[str] = None
    requiere_formula: bool = True


# ---------------------------------------------------------------------
# Sede
# ---------------------------------------------------------------------
class SedeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_sede: int
    id_eps: int
    eps: Optional[str] = None
    codigo_eps: Optional[str] = None
    nombre: str
    localidad: str
    direccion: str
    telefono: Optional[str] = None
    horario: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    activo: bool


# ---------------------------------------------------------------------
# Inventario / disponibilidad
# ---------------------------------------------------------------------
class DisponibilidadOut(BaseModel):
    """Respuesta de disponibilidad por sede para un medicamento."""
    medicamento: Optional[str] = None
    id_inventario: int
    id_sede: int
    id_eps: Optional[int] = None
    eps: Optional[str] = None
    codigo_eps: Optional[str] = None
    sede: str
    localidad: str
    cantidad_disponible: int
    stock_minimo: int
    estado: Literal["no_disponible", "critico", "bajo", "disponible"]
    fecha_actualizacion: datetime


class MovimientoEntradaSalida(BaseModel):
    """Body para POST /api/inventario/entrada y /api/inventario/salida."""
    id_medicamento: int
    id_sede: int
    cantidad: int = Field(gt=0)
    id_operador: Optional[int] = None
    fuente: str = "manual"


class MovimientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_movimiento: int
    id_inventario: int
    tipo_movimiento: str
    cantidad: int
    stock_anterior: int
    stock_nuevo: int
    id_operador: Optional[int] = None
    fuente: str
    fecha_hora: datetime


# ---------------------------------------------------------------------
# Autenticación / usuarios
# ---------------------------------------------------------------------
import re as _re
from pydantic import field_validator

_EMAIL_RE = _re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


class RegistroIn(BaseModel):
    documento: str = Field(min_length=5, max_length=20)
    nombre: str = Field(min_length=3, max_length=150)
    email: str = Field(max_length=150)
    telefono: Optional[str] = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=100)

    @field_validator("documento")
    @classmethod
    def _doc(cls, v):
        v = v.strip()
        if not _re.fullmatch(r"[A-Za-z0-9]{5,20}", v):
            raise ValueError("El documento solo puede tener letras y números (5 a 20 caracteres).")
        return v

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v):
        return " ".join(v.split())

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Correo electrónico no válido.")
        return v

    @field_validator("telefono")
    @classmethod
    def _tel(cls, v):
        if v in (None, ""):
            return None
        v = _re.sub(r"[\s-]", "", v)
        if not _re.fullmatch(r"\+?\d{7,15}", v):
            raise ValueError("Teléfono no válido (solo números, 7 a 15 dígitos).")
        return v

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        if not (_re.search(r"[A-Za-z]", v) and _re.search(r"\d", v)):
            raise ValueError("La contraseña debe tener al menos una letra y un número.")
        return v


class LoginIn(BaseModel):
    identificador: str = Field(min_length=3, max_length=150, description="Correo o documento")
    password: str = Field(min_length=1, max_length=100)


class PerfilUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=3, max_length=150)
    telefono: Optional[str] = Field(default=None, max_length=20)


class CambioPassword(BaseModel):
    actual: str
    nueva: str = Field(min_length=8, max_length=100)

    @field_validator("nueva")
    @classmethod
    def _pw(cls, v):
        if not (_re.search(r"[A-Za-z]", v) and _re.search(r"\d", v)):
            raise ValueError("La contraseña debe tener al menos una letra y un número.")
        return v


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_usuario: int
    documento: str
    nombre: str
    email: Optional[str] = None
    telefono: Optional[str] = None
    rol: str
    activo: bool
    fecha_creacion: Optional[datetime] = None


class SesionOut(BaseModel):
    token: str
    usuario: UsuarioOut


class UsuarioAdminUpdate(BaseModel):
    rol: Optional[Literal["paciente", "operador_inventario", "administrador", "analista"]] = None
    activo: Optional[bool] = None


# Inventario completo (una sola consulta para toda la página)
class InventarioFila(DisponibilidadOut):
    id_medicamento: int
