"""Ventas POS — Orquestador.

Este módulo actúa como punto de entrada único para todos los endpoints de Ventas POS.
La lógica está distribuida en sub-módulos:
  - pos_sync.py    → Config Odoo, sync-local, refresh
  - pos_crud.py    → Listado de ventas, detalle de líneas
  - pos_estados.py → Confirmar, crédito, descartar, desconfirmar, distribución analítica
  - pos_pagos.py   → CRUD de pagos (GET/POST/PUT/DELETE)
  - pos_common.py  → Utilidades compartidas (get_company_key)
"""
from fastapi import APIRouter
from routers.pos_sync import router as pos_sync_router
from routers.pos_crud import router as pos_crud_router
from routers.pos_estados import router as pos_estados_router
from routers.pos_pagos import router as pos_pagos_router

router = APIRouter()
router.include_router(pos_sync_router)
router.include_router(pos_crud_router)
router.include_router(pos_estados_router)
router.include_router(pos_pagos_router)
