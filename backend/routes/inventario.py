
"""
MEDIRED - Fases 3 y 4: disponibilidad, entradas, salidas y movimientos.

El trigger fn_aplicar_movimiento de PostgreSQL calcula y actualiza
automáticamente las existencias. El backend registra los movimientos,
pero no recalcula el stock manualmente.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from database import get_db
from models import Inventario, MovimientoInventario, Medicamento, Usuario
from schemas import (
    DisponibilidadOut,
    InventarioFila,
    MovimientoEntradaSalida,
    MovimientoOut,
)
from security import ROLES_OPERACION, requiere_roles

router = APIRouter(prefix="/api/inventario", tags=["inventario"])


@router.get("", response_model=list[InventarioFila])
def inventario_completo(db: Session = Depends(get_db)):
    """
    GET /api/inventario

    Consulta todo el inventario de medicamentos y sedes,
    incluyendo la EPS y el nombre del medicamento.
    """

    rows = db.execute(
        text("""
            SELECT
                i.id_inventario,
                i.id_medicamento,
                m.nombre AS medicamento,
                v.id_sede,
                v.sede,
                v.localidad,
                s.id_eps,
                e.nombre AS eps,
                e.codigo AS codigo_eps,
                v.cantidad_disponible,
                v.stock_minimo,
                v.estado,
                i.fecha_actualizacion
            FROM medired.vw_disponibilidad v
            JOIN medired.inventario i
                ON i.id_medicamento = v.id_medicamento
                AND i.id_sede = v.id_sede
            JOIN medired.sede s
                ON s.id_sede = v.id_sede
            JOIN medired.eps e
                ON e.id_eps = s.id_eps
            JOIN medired.medicamento m
                ON m.id_medicamento = i.id_medicamento
            WHERE m.activo
            ORDER BY
                i.id_medicamento,
                v.cantidad_disponible DESC
        """)
    ).mappings().all()

    return list(rows)


@router.get(
    "/{id_medicamento}",
    response_model=list[DisponibilidadOut],
)
def disponibilidad_por_medicamento(
    id_medicamento: int,
    db: Session = Depends(get_db),
):
    """
    GET /api/inventario/{id_medicamento}

    Consulta la disponibilidad del medicamento en todas las sedes,
    mostrando también la EPS correspondiente.
    """

    med = db.get(Medicamento, id_medicamento)

    if not med:
        raise HTTPException(
            status_code=404,
            detail="Medicamento no encontrado",
        )

    rows = db.execute(
        text("""
            SELECT
                i.id_inventario,
                :nombre_medicamento AS medicamento,
                v.id_sede,
                v.sede,
                v.localidad,
                s.id_eps,
                e.nombre AS eps,
                e.codigo AS codigo_eps,
                v.cantidad_disponible,
                v.stock_minimo,
                v.estado,
                i.fecha_actualizacion
            FROM medired.vw_disponibilidad v
            JOIN medired.inventario i
                ON i.id_medicamento = v.id_medicamento
                AND i.id_sede = v.id_sede
            JOIN medired.sede s
                ON s.id_sede = v.id_sede
            JOIN medired.eps e
                ON e.id_eps = s.id_eps
            WHERE v.id_medicamento = :id_medicamento
            ORDER BY v.cantidad_disponible DESC
        """),
        {
            "id_medicamento": id_medicamento,
            "nombre_medicamento": med.nombre,
        },
    ).mappings().all()

    return list(rows)


def _obtener_o_lanzar_inventario(
    db: Session,
    id_medicamento: int,
    id_sede: int,
) -> Inventario:

    inv = (
        db.query(Inventario)
        .filter(
            Inventario.id_medicamento == id_medicamento,
            Inventario.id_sede == id_sede,
        )
        .first()
    )

    if not inv:
        raise HTTPException(
            status_code=404,
            detail=(
                "No existe registro de inventario para ese medicamento "
                "en esa sede. Debe crearse primero."
            ),
        )

    return inv


@router.post(
    "/entrada",
    response_model=MovimientoOut,
    status_code=201,
)
def registrar_entrada(
    payload: MovimientoEntradaSalida,
    db: Session = Depends(get_db),
    operador: Usuario = Depends(requiere_roles(*ROLES_OPERACION)),
):
    """Registrar una entrada de inventario."""

    inv = _obtener_o_lanzar_inventario(
        db,
        payload.id_medicamento,
        payload.id_sede,
    )

    mov = MovimientoInventario(
        id_inventario=inv.id_inventario,
        tipo_movimiento="entrada",
        cantidad=payload.cantidad,
        stock_anterior=0,
        stock_nuevo=0,
        id_operador=operador.id_usuario,
        fuente=payload.fuente,
    )

    db.add(mov)
    db.commit()
    db.refresh(mov)

    return mov


@router.post(
    "/salida",
    response_model=MovimientoOut,
    status_code=201,
)
def registrar_salida(
    payload: MovimientoEntradaSalida,
    db: Session = Depends(get_db),
    operador: Usuario = Depends(requiere_roles(*ROLES_OPERACION)),
):
    """Registrar una salida de inventario."""

    inv = _obtener_o_lanzar_inventario(
        db,
        payload.id_medicamento,
        payload.id_sede,
    )

    mov = MovimientoInventario(
        id_inventario=inv.id_inventario,
        tipo_movimiento="salida",
        cantidad=payload.cantidad,
        stock_anterior=0,
        stock_nuevo=0,
        id_operador=operador.id_usuario,
        fuente=payload.fuente,
    )

    db.add(mov)

    try:
        db.commit()

    except DBAPIError as exc:
        db.rollback()

        detalle = (
            str(exc.orig).strip().splitlines()[0]
            if exc.orig
            else "Movimiento rechazado"
        )

        raise HTTPException(
            status_code=400,
            detail=detalle,
        ) from exc

    db.refresh(mov)

    return mov


@router.get(
    "/movimientos/{id_medicamento}",
    response_model=list[MovimientoOut],
)
def historial_movimientos(
    id_medicamento: int,
    id_sede: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Consultar el historial de movimientos de un medicamento."""

    query = (
        db.query(MovimientoInventario)
        .join(
            Inventario,
            MovimientoInventario.id_inventario
            == Inventario.id_inventario,
        )
        .filter(
            Inventario.id_medicamento == id_medicamento
        )
    )

    if id_sede is not None:
        query = query.filter(
            Inventario.id_sede == id_sede
        )

    return (
        query
        .order_by(MovimientoInventario.fecha_hora.desc())
        .limit(limit)
        .all()
    )
