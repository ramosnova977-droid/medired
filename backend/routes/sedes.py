"""
MEDIRED - Gestión de sedes y EPS.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Sede
from schemas import SedeOut

router = APIRouter(prefix="/api/sedes", tags=["sedes"])


def convertir_sede(sede):
    datos = {
        "id_sede": sede.id_sede,
        "id_eps": sede.id_eps,
        "eps": sede.eps.nombre if sede.eps else None,
        "codigo_eps": sede.eps.codigo if sede.eps else None,
        "nombre": sede.nombre,
        "localidad": sede.localidad,
        "direccion": sede.direccion,
        "telefono": sede.telefono,
        "horario": sede.horario,
        "latitud": sede.latitud,
        "longitud": sede.longitud,
        "activo": sede.activo,
    }

    return SedeOut.model_validate(datos)


@router.get("", response_model=list[SedeOut])
def listar_sedes(
    localidad: str | None = Query(
        None, description="Filtrar por localidad de Bogotá"
    ),
    solo_activas: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(Sede).options(joinedload(Sede.eps))

    if solo_activas:
        query = query.filter(Sede.activo.is_(True))

    if localidad:
        query = query.filter(Sede.localidad.ilike(f"%{localidad}%"))

    sedes = query.order_by(Sede.nombre).all()

    return [convertir_sede(sede) for sede in sedes]


@router.get("/{id_sede}", response_model=SedeOut)
def obtener_sede(id_sede: int, db: Session = Depends(get_db)):
    sede = (
        db.query(Sede)
        .options(joinedload(Sede.eps))
        .filter(Sede.id_sede == id_sede)
        .first()
    )

    if not sede:
        raise HTTPException(
            status_code=404,
            detail="Sede no encontrada"
        )

    return convertir_sede(sede)