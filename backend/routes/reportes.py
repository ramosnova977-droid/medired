"""
MEDIRED - Reportes y gráficos (inventario y movimientos).

  GET /api/reportes/inventario              resumen de existencias (público, igual que la consulta)
  GET /api/reportes/movimientos/resumen     agregados para gráficos        (operador / analista / admin)
  GET /api/reportes/movimientos             listado detallado + CSV en la página (idem)
"""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from models import Usuario
from security import ROLES_STAFF, requiere_roles

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


@router.get("/inventario")
def reporte_inventario(db: Session = Depends(get_db)):
    """Existencias por sede y por estado, y los medicamentos con más sedes en alerta."""
    por_sede = db.execute(text("""
        SELECT v.id_sede, v.sede, v.localidad,
               COUNT(*) AS registros,
               COALESCE(SUM(v.cantidad_disponible), 0) AS unidades,
               COUNT(*) FILTER (WHERE v.estado = 'disponible')    AS disponible,
               COUNT(*) FILTER (WHERE v.estado = 'bajo')          AS bajo,
               COUNT(*) FILTER (WHERE v.estado = 'critico')       AS critico,
               COUNT(*) FILTER (WHERE v.estado = 'no_disponible') AS no_disponible
        FROM medired.vw_disponibilidad v
        JOIN medired.medicamento m ON m.id_medicamento = v.id_medicamento AND m.activo
        GROUP BY v.id_sede, v.sede, v.localidad ORDER BY v.sede
    """)).mappings().all()
    por_estado = db.execute(text("""
        SELECT v.estado, COUNT(*) AS registros
        FROM medired.vw_disponibilidad v
        JOIN medired.medicamento m ON m.id_medicamento = v.id_medicamento AND m.activo
        GROUP BY v.estado
    """)).mappings().all()
    criticos = db.execute(text("""
        SELECT m.id_medicamento, m.nombre, m.concentracion,
               COUNT(*) FILTER (WHERE v.estado IN ('critico','no_disponible')) AS sedes_en_alerta,
               COUNT(*) AS sedes_con_registro,
               COALESCE(SUM(v.cantidad_disponible), 0) AS unidades
        FROM medired.vw_disponibilidad v
        JOIN medired.medicamento m ON m.id_medicamento = v.id_medicamento AND m.activo
        GROUP BY m.id_medicamento, m.nombre, m.concentracion
        HAVING COUNT(*) FILTER (WHERE v.estado IN ('critico','no_disponible')) > 0
        ORDER BY sedes_en_alerta DESC, unidades ASC LIMIT 10
    """)).mappings().all()
    return {"por_sede": list(por_sede), "por_estado": list(por_estado), "mas_criticos": list(criticos)}


def _filtros(dias: int, id_sede: Optional[int], id_medicamento: Optional[int]):
    where, params = ["mv.tipo_movimiento IN ('entrada','salida')"], {}
    if dias > 0:
        where.append("mv.fecha_hora >= now() - make_interval(days => :dias)")
        params["dias"] = dias
    if id_sede:
        where.append("i.id_sede = :id_sede")
        params["id_sede"] = id_sede
    if id_medicamento:
        where.append("i.id_medicamento = :id_medicamento")
        params["id_medicamento"] = id_medicamento
    return " AND ".join(where), params


@router.get("/movimientos/resumen")
def resumen_movimientos(
    dias: int = Query(30, ge=0, le=3650, description="0 = todo el historial"),
    id_sede: Optional[int] = None,
    id_medicamento: Optional[int] = None,
    _: Usuario = Depends(requiere_roles(*ROLES_STAFF)),
    db: Session = Depends(get_db),
):
    where, p = _filtros(dias, id_sede, id_medicamento)
    base = f"""FROM medired.movimiento_inventario mv
               JOIN medired.inventario i ON i.id_inventario = mv.id_inventario
               JOIN medired.medicamento m ON m.id_medicamento = i.id_medicamento
               JOIN medired.sede s ON s.id_sede = i.id_sede
               WHERE {where}"""
    totales = db.execute(text(f"""
        SELECT COUNT(*) AS movimientos,
               COALESCE(SUM(mv.cantidad) FILTER (WHERE mv.tipo_movimiento = 'entrada'), 0) AS unidades_entrada,
               COALESCE(SUM(mv.cantidad) FILTER (WHERE mv.tipo_movimiento = 'salida'), 0)  AS unidades_salida
        {base}"""), p).mappings().one()
    por_dia = db.execute(text(f"""
        SELECT mv.fecha_hora::date AS fecha,
               COALESCE(SUM(mv.cantidad) FILTER (WHERE mv.tipo_movimiento = 'entrada'), 0) AS entradas,
               COALESCE(SUM(mv.cantidad) FILTER (WHERE mv.tipo_movimiento = 'salida'), 0)  AS salidas
        {base} GROUP BY 1 ORDER BY 1"""), p).mappings().all()
    por_sede = db.execute(text(f"""
        SELECT s.id_sede, s.nombre AS sede,
               COALESCE(SUM(mv.cantidad) FILTER (WHERE mv.tipo_movimiento = 'entrada'), 0) AS entradas,
               COALESCE(SUM(mv.cantidad) FILTER (WHERE mv.tipo_movimiento = 'salida'), 0)  AS salidas
        {base} GROUP BY s.id_sede, s.nombre ORDER BY salidas DESC"""), p).mappings().all()
    top = db.execute(text(f"""
        SELECT m.id_medicamento, m.nombre, m.concentracion,
               COALESCE(SUM(mv.cantidad) FILTER (WHERE mv.tipo_movimiento = 'salida'), 0) AS salidas,
               COALESCE(SUM(mv.cantidad) FILTER (WHERE mv.tipo_movimiento = 'entrada'), 0) AS entradas
        {base} GROUP BY m.id_medicamento, m.nombre, m.concentracion
        ORDER BY salidas DESC LIMIT 10"""), p).mappings().all()
    por_fuente = db.execute(text(f"""
        SELECT mv.fuente, COUNT(*) AS movimientos {base} GROUP BY mv.fuente ORDER BY movimientos DESC"""), p).mappings().all()
    return {"dias": dias, "totales": dict(totales), "por_dia": list(por_dia), "por_sede": list(por_sede),
            "top_salidas": list(top), "por_fuente": list(por_fuente)}


@router.get("/movimientos")
def listar_movimientos(
    dias: int = Query(30, ge=0, le=3650),
    id_sede: Optional[int] = None,
    id_medicamento: Optional[int] = None,
    tipo: Optional[Literal["entrada", "salida"]] = None,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    _: Usuario = Depends(requiere_roles(*ROLES_STAFF)),
    db: Session = Depends(get_db),
):
    where, p = _filtros(dias, id_sede, id_medicamento)
    if tipo:
        where += " AND mv.tipo_movimiento = :tipo"
        p["tipo"] = tipo
    p.update(limit=limit, offset=offset)
    rows = db.execute(text(f"""
        SELECT mv.id_movimiento, mv.fecha_hora, mv.tipo_movimiento, mv.cantidad,
               mv.stock_anterior, mv.stock_nuevo, mv.fuente,
               m.id_medicamento, m.nombre AS medicamento, m.concentracion,
               s.id_sede, s.nombre AS sede, u.nombre AS operador
        FROM medired.movimiento_inventario mv
        JOIN medired.inventario i ON i.id_inventario = mv.id_inventario
        JOIN medired.medicamento m ON m.id_medicamento = i.id_medicamento
        JOIN medired.sede s ON s.id_sede = i.id_sede
        LEFT JOIN medired.usuario u ON u.id_usuario = mv.id_operador
        WHERE {where}
        ORDER BY mv.fecha_hora DESC, mv.id_movimiento DESC
        LIMIT :limit OFFSET :offset"""), p).mappings().all()
    return list(rows)
