from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import date, datetime
from database import get_pool
from dependencies import get_empresa_id

router = APIRouter()


@router.get("/flujo-caja-gerencial")
async def flujo_caja_gerencial(
    fecha_desde: date = Query(...),
    fecha_hasta: date = Query(...),
    agrupacion: str = Query("diario", regex="^(diario|semanal|mensual)$"),
    marca_id: Optional[int] = None,
    proyecto_id: Optional[int] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    """Cash flow report from TREASURY MOVEMENTS (single source of truth)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        date_trunc = {"diario": "day", "semanal": "week", "mensual": "month"}[agrupacion]

        # Build conditions for optional filters
        extra_conds = ""
        params = [empresa_id, fecha_desde, fecha_hasta]
        idx = 4
        if marca_id:
            extra_conds += f" AND marca_id = ${idx}"
            params.append(marca_id)
            idx += 1
        if proyecto_id:
            extra_conds += f" AND proyecto_id = ${idx}"
            params.append(proyecto_id)
            idx += 1

        # Read all treasury movements grouped by period
        rows = await conn.fetch(f"""
            SELECT DATE_TRUNC('{date_trunc}', fecha)::date as periodo,
                   tipo,
                   origen_tipo,
                   COALESCE(SUM(monto), 0) as total
            FROM cont_movimiento_tesoreria
            WHERE empresa_id = $1
              AND fecha BETWEEN $2 AND $3
              {extra_conds}
            GROUP BY periodo, tipo, origen_tipo
            ORDER BY periodo
        """, *params)

        periods = {}
        for r in rows:
            p = r['periodo'].isoformat()
            periods.setdefault(p, {
                "ingresos_ventas": 0, "cobranzas_cxc": 0, "otros_ingresos": 0,
                "pagos_cxp": 0, "pagos_gastos": 0, "otros_egresos": 0
            })
            t = float(r['total'])
            ot = r['origen_tipo']
            if r['tipo'] == 'ingreso':
                if ot == 'venta_pos_confirmada':
                    periods[p]["ingresos_ventas"] += t
                elif ot == 'cobranza_cxc':
                    periods[p]["cobranzas_cxc"] += t
                else:
                    periods[p]["otros_ingresos"] += t
            else:  # egreso
                if ot == 'pago_cxp':
                    periods[p]["pagos_cxp"] += t
                elif ot in ('gasto_directo', 'pago_gasto'):
                    periods[p]["pagos_gastos"] += t
                else:
                    periods[p]["otros_egresos"] += t

        timeline = []
        saldo = 0
        for p in sorted(periods.keys()):
            d = periods[p]
            total_in = d["ingresos_ventas"] + d["cobranzas_cxc"] + d["otros_ingresos"]
            total_out = d["pagos_cxp"] + d["pagos_gastos"] + d["otros_egresos"]
            saldo += total_in - total_out
            timeline.append({
                "periodo": p,
                "ingresos_ventas": d["ingresos_ventas"],
                "cobranzas_cxc": d["cobranzas_cxc"],
                "otros_ingresos": d["otros_ingresos"],
                "total_ingresos": total_in,
                "pagos_cxp": d["pagos_cxp"],
                "pagos_gastos": d["pagos_gastos"],
                "otros_egresos": d["otros_egresos"],
                "total_egresos": total_out,
                "flujo_neto": total_in - total_out,
                "saldo_acumulado": saldo,
            })

        total_ingresos = sum(t["total_ingresos"] for t in timeline)
        total_egresos = sum(t["total_egresos"] for t in timeline)

        return {
            "timeline": timeline,
            "totales": {
                "ingresos": total_ingresos,
                "egresos": total_egresos,
                "flujo_neto": total_ingresos - total_egresos,
            },
            "agrupacion": agrupacion,
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat(),
            "source": "tesoreria",
        }


@router.get("/rentabilidad")
async def rentabilidad(
    fecha_desde: date = Query(...),
    fecha_hasta: date = Query(...),
    dimension: str = Query("marca", regex="^(marca|linea_negocio|centro_costo|proyecto)$"),
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        dim_config = {
            "marca": {"join_table": "cont_marca", "join_col": "marca_id", "name_col": "nombre"},
            "linea_negocio": {"join_table": "cont_linea_negocio", "join_col": "linea_negocio_id", "name_col": "nombre"},
            "centro_costo": {"join_table": "cont_centro_costo", "join_col": "centro_costo_id", "name_col": "nombre"},
            "proyecto": {"join_table": "cont_proyecto", "join_col": "proyecto_id", "name_col": "nombre"},
        }
        cfg = dim_config[dimension]
        # Columns on line tables: linea_negocio_id, centro_costo_id
        line_cols = {"linea_negocio_id", "centro_costo_id"}
        # Columns on cont_gasto header: marca_id, proyecto_id, linea_negocio_id, centro_costo_id
        gasto_header_cols = {"marca_id", "proyecto_id", "linea_negocio_id", "centro_costo_id"}

        # INGRESOS: POS lines from LOCAL tables (desacoplado de Odoo)
        from services.linea_mapping import get_linea_negocio_map, resolve_linea
        ln_map = await get_linea_negocio_map(conn, empresa_id)

        if dimension == 'linea_negocio':
            raw_rows = await conn.fetch("""
                SELECT l.odoo_linea_negocio_id as odoo_ln_id,
                       COALESCE(SUM(l.price_subtotal), 0) as ingreso
                FROM cont_venta_pos_linea l
                JOIN cont_venta_pos v ON l.venta_pos_id = v.id
                JOIN cont_venta_pos_estado e
                    ON e.odoo_order_id = v.odoo_id AND e.empresa_id = $1
                WHERE e.estado_local = 'confirmada'
                  AND v.date_order BETWEEN $2 AND $3
                GROUP BY l.odoo_linea_negocio_id
            """, empresa_id,
                datetime.combine(fecha_desde, datetime.min.time()),
                datetime.combine(fecha_hasta, datetime.max.time()))
            ing_by_name = {}
            for r in raw_rows:
                mapped = resolve_linea(ln_map, r['odoo_ln_id'])
                name = mapped['nombre']
                ing_by_name[name] = ing_by_name.get(name, 0) + float(r['ingreso'])
            ingresos_rows = [{"dimension_name": k, "ingreso": v} for k, v in ing_by_name.items()]
        else:
            ingresos_rows = await conn.fetch(f"""
                SELECT
                    COALESCE(m.{cfg['name_col']}, 'Sin Asignar') as dimension_name,
                    COALESCE(SUM(l.price_subtotal), 0) as ingreso
                FROM cont_venta_pos_linea l
                JOIN cont_venta_pos v ON l.venta_pos_id = v.id
                JOIN cont_venta_pos_estado e
                    ON e.odoo_order_id = v.odoo_id AND e.empresa_id = $1
                LEFT JOIN {cfg['join_table']} m ON m.nombre = l.marca
                WHERE e.estado_local = 'confirmada'
                  AND v.date_order BETWEEN $2 AND $3
                GROUP BY dimension_name
            """, empresa_id,
                datetime.combine(fecha_desde, datetime.min.time()),
                datetime.combine(fecha_hasta, datetime.max.time()))

        # Gastos: prefer line-level, else header-level
        if cfg['join_col'] in line_cols:
            gastos_join = f"LEFT JOIN {cfg['join_table']} m ON gl.{cfg['join_col']} = m.id"
        elif cfg['join_col'] in gasto_header_cols:
            gastos_join = f"LEFT JOIN {cfg['join_table']} m ON g.{cfg['join_col']} = m.id"
        else:
            gastos_join = f"LEFT JOIN {cfg['join_table']} m ON NULL"
        gastos_rows = await conn.fetch(f"""
            SELECT
                COALESCE(m.{cfg['name_col']}, 'Sin Asignar') as dimension_name,
                COALESCE(SUM(gl.importe), 0) as gasto
            FROM cont_gasto g
            JOIN cont_gasto_linea gl ON g.id = gl.gasto_id
            {gastos_join}
            WHERE g.empresa_id = $1 AND g.fecha BETWEEN $2 AND $3
            GROUP BY dimension_name
        """, empresa_id, fecha_desde, fecha_hasta)

        # Costos: facturas proveedor - only line-level joins available
        if cfg['join_col'] in line_cols:
            costos_join = f"LEFT JOIN {cfg['join_table']} m ON fpl.{cfg['join_col']} = m.id"
        else:
            # Dimension not on factura lines, all will be 'Sin Asignar'
            costos_join = f"LEFT JOIN {cfg['join_table']} m ON FALSE"
        costos_rows = await conn.fetch(f"""
            SELECT
                COALESCE(m.{cfg['name_col']}, 'Sin Asignar') as dimension_name,
                COALESCE(SUM(fpl.importe), 0) as costo
            FROM cont_factura_proveedor fp
            JOIN cont_factura_proveedor_linea fpl ON fp.id = fpl.factura_id
            {costos_join}
            WHERE fp.empresa_id = $1 AND fp.fecha_factura BETWEEN $2 AND $3
            GROUP BY dimension_name
        """, empresa_id, fecha_desde, fecha_hasta)

        data = {}
        for r in ingresos_rows:
            name = r['dimension_name']
            data.setdefault(name, {"ingreso": 0, "gasto": 0, "costo": 0})
            data[name]["ingreso"] += float(r['ingreso'])
        for r in gastos_rows:
            name = r['dimension_name']
            data.setdefault(name, {"ingreso": 0, "gasto": 0, "costo": 0})
            data[name]["gasto"] += float(r['gasto'])
        for r in costos_rows:
            name = r['dimension_name']
            data.setdefault(name, {"ingreso": 0, "gasto": 0, "costo": 0})
            data[name]["costo"] += float(r['costo'])

        result = []
        for name, vals in sorted(data.items(), key=lambda x: x[1]["ingreso"] + x[1]["costo"], reverse=True):
            total_egreso = vals["gasto"] + vals["costo"]
            utilidad = vals["ingreso"] - total_egreso
            margen = (utilidad / vals["ingreso"] * 100) if vals["ingreso"] > 0 else 0
            result.append({
                "dimension": name,
                "ingreso": vals["ingreso"],
                "costo": vals["costo"],
                "gasto": vals["gasto"],
                "utilidad": utilidad,
                "margen_pct": round(margen, 1),
            })

        total_ingreso = sum(r["ingreso"] for r in result)
        total_costo = sum(r["costo"] for r in result)
        total_gasto = sum(r["gasto"] for r in result)
        total_utilidad = total_ingreso - total_costo - total_gasto
        total_margen = round((total_utilidad / total_ingreso * 100) if total_ingreso > 0 else 0, 1)

        return {
            "data": result,
            "totales": {
                "ingreso": total_ingreso,
                "costo": total_costo,
                "gasto": total_gasto,
                "utilidad": total_utilidad,
                "margen_pct": total_margen,
            },
            "dimension": dimension,
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat(),
        }


@router.get("/presupuesto-vs-real")
async def presupuesto_vs_real(
    anio: int = Query(...),
    presupuesto_id: Optional[int] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        # Get the budget
        if presupuesto_id:
            pres = await conn.fetchrow(
                "SELECT id, nombre FROM cont_presupuesto WHERE id=$1 AND empresa_id=$2", presupuesto_id, empresa_id)
        else:
            pres = await conn.fetchrow(
                "SELECT id, nombre FROM cont_presupuesto WHERE anio=$1 AND empresa_id=$2 ORDER BY version DESC LIMIT 1",
                anio, empresa_id)

        if not pres:
            return {"presupuesto": None, "data": [], "por_mes": [], "totales": {"presupuestado": 0, "real": 0, "desviacion": 0}}

        # Budget lines by category/month
        budget_lines = await conn.fetch("""
            SELECT pl.mes, pl.monto_presupuestado,
                   COALESCE(c.nombre, 'Sin Categoria') as categoria
            FROM cont_presupuesto_linea pl
            LEFT JOIN cont_categoria c ON pl.categoria_id = c.id
            WHERE pl.presupuesto_id = $1
            ORDER BY pl.mes, c.nombre
        """, pres['id'])

        # Real gastos by category/month for the year
        real_gastos = await conn.fetch("""
            SELECT EXTRACT(MONTH FROM g.fecha)::int as mes,
                   COALESCE(c.nombre, 'Sin Categoria') as categoria,
                   COALESCE(SUM(gl.importe), 0) as monto_real
            FROM cont_gasto g
            JOIN cont_gasto_linea gl ON g.id = gl.gasto_id
            LEFT JOIN cont_categoria c ON gl.categoria_id = c.id
            WHERE g.empresa_id = $1
              AND EXTRACT(YEAR FROM g.fecha) = $2
            GROUP BY mes, categoria
        """, empresa_id, anio)

        # Build by-category comparison
        cat_data = {}
        for bl in budget_lines:
            cat = bl['categoria']
            cat_data.setdefault(cat, {"presupuestado": 0, "real": 0})
            cat_data[cat]["presupuestado"] += float(bl['monto_presupuestado'] or 0)
        for rg in real_gastos:
            cat = rg['categoria']
            cat_data.setdefault(cat, {"presupuestado": 0, "real": 0})
            cat_data[cat]["real"] += float(rg['monto_real'] or 0)

        data_by_cat = []
        for cat, vals in sorted(cat_data.items()):
            desv = vals["presupuestado"] - vals["real"]
            pct = round((vals["real"] / vals["presupuestado"] * 100) if vals["presupuestado"] > 0 else 0, 1)
            data_by_cat.append({
                "categoria": cat,
                "presupuestado": vals["presupuestado"],
                "real": vals["real"],
                "desviacion": desv,
                "ejecucion_pct": pct,
            })

        # Build by-month comparison
        mes_pres = {}
        for bl in budget_lines:
            m = bl['mes']
            mes_pres[m] = mes_pres.get(m, 0) + float(bl['monto_presupuestado'] or 0)
        mes_real = {}
        for rg in real_gastos:
            m = rg['mes']
            mes_real[m] = mes_real.get(m, 0) + float(rg['monto_real'] or 0)

        MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        por_mes = []
        for m in range(1, 13):
            p = mes_pres.get(m, 0)
            r = mes_real.get(m, 0)
            por_mes.append({"mes": m, "mes_nombre": MESES[m - 1], "presupuestado": p, "real": r, "desviacion": p - r})

        total_p = sum(d["presupuestado"] for d in data_by_cat)
        total_r = sum(d["real"] for d in data_by_cat)

        return {
            "presupuesto": {"id": pres['id'], "nombre": pres['nombre']},
            "data": data_by_cat,
            "por_mes": por_mes,
            "totales": {
                "presupuestado": total_p,
                "real": total_r,
                "desviacion": total_p - total_r,
                "ejecucion_pct": round((total_r / total_p * 100) if total_p > 0 else 0, 1),
            },
        }


@router.get("/roi-proyectos")
async def roi_proyectos(
    fecha_desde: date = Query(...),
    fecha_hasta: date = Query(...),
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        # Investment: gastos assigned to projects
        inversiones = await conn.fetch("""
            SELECT p.id, p.nombre,
                   COALESCE(SUM(gl.importe), 0) as inversion
            FROM cont_proyecto p
            LEFT JOIN cont_gasto g ON g.proyecto_id = p.id AND g.empresa_id = $1 AND g.fecha BETWEEN $2 AND $3
            LEFT JOIN cont_gasto_linea gl ON g.id = gl.gasto_id
            WHERE p.estado = 'activo'
            GROUP BY p.id, p.nombre
        """, empresa_id, fecha_desde, fecha_hasta)

        # Returns: We track retorno from CxC abonos linked to projects (cash actually received)
        # and from confirmed POS pago_aplicacion linked to proyecto
        await conn.fetch("""
            SELECT p.id as proyecto_id,
                   COALESCE(SUM(pa.monto_aplicado), 0) as retorno
            FROM cont_proyecto p
            LEFT JOIN cont_pago_aplicacion pa
                ON pa.empresa_id = $1
                AND pa.created_at::date BETWEEN $2 AND $3
            WHERE p.estado = 'activo'
            GROUP BY p.id
        """, empresa_id, fecha_desde, fecha_hasta)

        # Use project budget as expected retorno baseline
        inv_map = {r['id']: {"nombre": r['nombre'], "inversion": float(r['inversion'])} for r in inversiones}

        result = []
        for pid, inv in inv_map.items():
            inversion = inv["inversion"]
            # Get project presupuesto as target
            utilidad = -inversion  # No direct retorno attribution yet
            roi = round((utilidad / inversion * 100) if inversion > 0 else 0, 1)
            result.append({
                "proyecto": inv["nombre"],
                "proyecto_id": pid,
                "inversion": inversion,
                "retorno": 0,
                "utilidad": utilidad,
                "roi_pct": roi,
            })

        result.sort(key=lambda x: x["roi_pct"], reverse=True)
        total_inv = sum(r["inversion"] for r in result)
        total_ret = sum(r["retorno"] for r in result)
        total_util = total_ret - total_inv

        return {
            "data": result,
            "totales": {
                "inversion": total_inv,
                "retorno": total_ret,
                "utilidad": total_util,
                "roi_pct": round((total_util / total_inv * 100) if total_inv > 0 else 0, 1),
            },
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat(),
        }
