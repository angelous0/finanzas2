"""
Extracción automática de facturas desde:
  - Imagen (jpg/png/heic) → OpenAI Vision (gpt-4o-mini)
  - PDF (escaneado o nativo) → conversión a imagen → OpenAI Vision
  - XML SUNAT (factura electrónica oficial) → parser local

Endpoints:
  POST /facturas-proveedor/extract-from-image   (multipart file)
  POST /facturas-proveedor/extract-from-pdf     (multipart file)
  POST /facturas-proveedor/extract-from-xml     (multipart file)

Devuelven el mismo JSON con la estructura del formulario de factura para que
el frontend pre-llene los campos.
"""
import os
import io
import json
import base64
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from database import get_pool
from dependencies import get_empresa_id

logger = logging.getLogger(__name__)
router = APIRouter()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_VISION_MODEL", "gpt-4o-mini")


# ─────────── Prompt para OpenAI Vision ───────────

EXTRACT_PROMPT = """Eres un extractor de datos de facturas peruanas (SUNAT). Analiza esta imagen de factura/boleta/recibo y devuelve un JSON con esta estructura EXACTA. Si un dato no está visible, usa null.

{
  "tipo_documento": "factura" | "boleta" | "recibo" | "nota_credito" | null,
  "tipo_comprobante_sunat": "01" | "03" | "07" | "02" | "12" | null,
  "numero": "F001-00012345" o "B001-00012345",
  "fecha_factura": "YYYY-MM-DD",
  "fecha_vencimiento": "YYYY-MM-DD" o null,
  "terminos_dias": 30,
  "moneda_codigo": "PEN" | "USD",
  "tipo_cambio": null o número,
  "proveedor": {
    "ruc": "20543300064" (11 dígitos) o "12345678" (DNI 8 dígitos),
    "nombre": "RAZÓN SOCIAL O NOMBRE DEL EMISOR",
    "tipo_documento": "RUC" | "DNI" | "CE",
    "direccion": "..." o null
  },
  "totales": {
    "subtotal": 100.00,
    "igv": 18.00,
    "base_gravada": 100.00,
    "base_no_gravada": 0.00,
    "total": 118.00,
    "impuestos_incluidos": false
  },
  "lineas": [
    {
      "descripcion": "...",
      "cantidad": 1,
      "precio_unitario": 100.00,
      "importe": 100.00,
      "igv_aplica": true
    }
  ],
  "notas": "observaciones visibles, condiciones de pago, etc.",
  "confianza": 0.0 a 1.0
}

Reglas:
- Devuelve SOLO el JSON, sin markdown, sin explicaciones.
- Si la factura tiene IGV, base_gravada = subtotal y igv = subtotal * 0.18.
- Si dice "PRECIO INCLUIDO IGV" → impuestos_incluidos: true.
- Para serie+correlativo usa formato F001-00012345 (con guión).
- tipo_comprobante_sunat: 01=Factura, 03=Boleta, 07=Nota crédito, 02=Recibo honorarios, 12=Ticket.
- Fechas en formato ISO YYYY-MM-DD.
- Si solo ves DNI de 8 dígitos, tipo_documento del proveedor es DNI.
- confianza: tu propia evaluación de qué tan claro/legible está el documento (0-1).
"""


def _image_to_base64(image_bytes: bytes, mime: str) -> str:
    """Convierte bytes de imagen a data URL para OpenAI."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


async def _extract_with_openai(image_data_url: str) -> dict:
    """Llama a OpenAI Vision y devuelve el JSON extraído."""
    if not OPENAI_API_KEY:
        raise HTTPException(500, "OPENAI_API_KEY no configurada en el servidor")
    try:
        from openai import OpenAI
    except ImportError:
        raise HTTPException(500, "Librería openai no instalada")
    client = OpenAI(api_key=OPENAI_API_KEY)
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACT_PROMPT},
                    {"type": "image_url", "image_url": {"url": image_data_url, "detail": "high"}},
                ],
            }],
            max_tokens=2000,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        logger.exception("Error en OpenAI Vision")
        raise HTTPException(500, f"Error procesando con OpenAI: {e}")


def _pdf_to_image_data_url(pdf_bytes: bytes) -> str:
    """Convierte la primera página del PDF a imagen y devuelve data URL."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise HTTPException(500, "PyMuPDF no instalado en el servidor")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    if doc.page_count == 0:
        raise HTTPException(400, "PDF vacío")
    # Renderizar primera página a 200 DPI (suficiente para OCR de Vision)
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=200)
    img_bytes = pix.tobytes("png")
    doc.close()
    return _image_to_base64(img_bytes, "image/png")


# ─────────── Match de proveedor en BD ───────────

async def _match_proveedor(conn, empresa_id: int, ruc: Optional[str], nombre: Optional[str]) -> Optional[dict]:
    """Busca proveedor por RUC primero, luego por nombre similar."""
    if ruc:
        row = await conn.fetchrow(
            """SELECT id, nombre, numero_documento FROM finanzas2.cont_tercero
                WHERE empresa_id = $1 AND numero_documento = $2 LIMIT 1""",
            empresa_id, ruc)
        if row:
            return dict(row)
    if nombre:
        row = await conn.fetchrow(
            """SELECT id, nombre, numero_documento FROM finanzas2.cont_tercero
                WHERE empresa_id = $1 AND LOWER(nombre) = LOWER($2) LIMIT 1""",
            empresa_id, nombre)
        if row:
            return dict(row)
        # Match parcial (las primeras 3 palabras)
        partes = nombre.split()
        if partes:
            patron = "%" + "%".join(partes[:3]) + "%"
            row = await conn.fetchrow(
                """SELECT id, nombre, numero_documento FROM finanzas2.cont_tercero
                    WHERE empresa_id = $1 AND nombre ILIKE $2 LIMIT 1""",
                empresa_id, patron)
            if row:
                return dict(row)
    return None


async def _enriquecer_con_bd(extraccion: dict, empresa_id: int) -> dict:
    """Agrega proveedor_id si encontró match, y otros enriquecimientos de BD."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        prov = extraccion.get("proveedor", {}) or {}
        match = await _match_proveedor(conn, empresa_id, prov.get("ruc"), prov.get("nombre"))
        if match:
            extraccion["proveedor"]["id"] = match["id"]
            extraccion["proveedor"]["match"] = "encontrado"
        else:
            extraccion["proveedor"]["match"] = "no_encontrado"
            # Sugerir crear proveedor con los datos extraídos
            extraccion["proveedor"]["sugerencia_crear"] = True
        # Moneda → moneda_id
        codigo = extraccion.get("moneda_codigo") or "PEN"
        m = await conn.fetchrow(
            "SELECT id FROM finanzas2.cont_moneda WHERE codigo=$1 LIMIT 1", codigo)
        if m:
            extraccion["moneda_id"] = m["id"]
    return extraccion


# ─────────── Endpoints ───────────

@router.post("/facturas-proveedor/extract-from-image")
async def extract_from_image(
    file: UploadFile = File(...),
    empresa_id: int = Depends(get_empresa_id),
):
    """Extrae datos de factura desde imagen (jpg, png, heic, webp)."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "El archivo debe ser una imagen")
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(400, "Imagen demasiado grande (máx 10MB)")
    data_url = _image_to_base64(contents, file.content_type)
    extraccion = await _extract_with_openai(data_url)
    extraccion = await _enriquecer_con_bd(extraccion, empresa_id)
    return {"ok": True, "fuente": "image", "data": extraccion}


@router.post("/facturas-proveedor/extract-from-pdf")
async def extract_from_pdf(
    file: UploadFile = File(...),
    empresa_id: int = Depends(get_empresa_id),
):
    """Extrae datos de factura desde PDF (la primera página)."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "El archivo debe ser un PDF")
    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(400, "PDF demasiado grande (máx 20MB)")
    data_url = _pdf_to_image_data_url(contents)
    extraccion = await _extract_with_openai(data_url)
    extraccion = await _enriquecer_con_bd(extraccion, empresa_id)
    return {"ok": True, "fuente": "pdf", "data": extraccion}


# ─────────── XML SUNAT ───────────

def _parse_xml_sunat(xml_bytes: bytes) -> dict:
    """Parser de XML UBL 2.1 (factura electrónica SUNAT)."""
    try:
        from xml.etree import ElementTree as ET
    except ImportError:
        raise HTTPException(500, "ET no disponible")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise HTTPException(400, f"XML inválido: {e}")

    # Namespaces UBL 2.1
    ns = {
        'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
        'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
    }

    def t(elem, path):
        x = elem.find(path, ns)
        return x.text.strip() if x is not None and x.text else None

    def f(elem, path):
        v = t(elem, path)
        try:
            return float(v) if v else None
        except ValueError:
            return None

    # Datos generales
    serie_correlativo = t(root, "cbc:ID")  # Ej: "F001-00012345"
    fecha_emision = t(root, "cbc:IssueDate")
    fecha_venc = t(root, "cbc:DueDate")
    moneda = t(root, "cbc:DocumentCurrencyCode") or "PEN"
    tipo_doc_cod = t(root, "cbc:InvoiceTypeCode") or t(root, "cbc:CreditNoteTypeCode") or "01"

    tipo_doc_map = {"01": "factura", "03": "boleta", "07": "nota_credito", "02": "recibo", "12": "ticket"}
    tipo_documento = tipo_doc_map.get(tipo_doc_cod, "factura")

    # Proveedor (Supplier)
    sup = root.find("cac:AccountingSupplierParty/cac:Party", ns)
    sup_ruc = t(sup, "cac:PartyIdentification/cbc:ID") if sup is not None else None
    sup_nombre = (t(sup, "cac:PartyLegalEntity/cbc:RegistrationName") if sup is not None else None) or \
                 (t(sup, "cac:PartyName/cbc:Name") if sup is not None else None)
    sup_dir = t(sup, "cac:PartyLegalEntity/cac:RegistrationAddress/cbc:StreetName") if sup is not None else None

    # Totales
    monetary_total = root.find("cac:LegalMonetaryTotal", ns)
    subtotal = f(monetary_total, "cbc:LineExtensionAmount") if monetary_total is not None else 0
    total = f(monetary_total, "cbc:PayableAmount") if monetary_total is not None else 0

    igv_total = 0
    for tax in root.findall("cac:TaxTotal", ns):
        for sub in tax.findall("cac:TaxSubtotal", ns):
            cat_id = t(sub, "cac:TaxCategory/cac:TaxScheme/cbc:ID")
            if cat_id == "1000":  # IGV
                v = f(sub, "cbc:TaxAmount")
                if v: igv_total += v

    # Líneas
    lineas = []
    for line in root.findall("cac:InvoiceLine", ns) + root.findall("cac:CreditNoteLine", ns):
        cantidad = f(line, "cbc:InvoicedQuantity") or f(line, "cbc:CreditedQuantity") or 1
        importe = f(line, "cbc:LineExtensionAmount") or 0
        precio_unit = f(line, "cac:Price/cbc:PriceAmount") or (importe / cantidad if cantidad else 0)
        descripcion = t(line, "cac:Item/cbc:Description") or "Item"
        # IGV aplica si hay TaxAmount > 0 en la línea
        igv_aplica = False
        for tax in line.findall("cac:TaxTotal", ns):
            v = f(tax, "cbc:TaxAmount")
            if v and v > 0:
                igv_aplica = True
                break
        lineas.append({
            "descripcion": descripcion,
            "cantidad": cantidad,
            "precio_unitario": round(precio_unit, 4),
            "importe": round(importe, 2),
            "igv_aplica": igv_aplica,
        })

    base_gravada = round(subtotal or 0, 2)
    base_no_gravada = round((total or 0) - (base_gravada + (igv_total or 0)), 2)
    if base_no_gravada < 0:
        base_no_gravada = 0

    return {
        "tipo_documento": tipo_documento,
        "tipo_comprobante_sunat": tipo_doc_cod,
        "numero": serie_correlativo,
        "fecha_factura": fecha_emision,
        "fecha_vencimiento": fecha_venc,
        "terminos_dias": 30,
        "moneda_codigo": moneda,
        "tipo_cambio": None,
        "proveedor": {
            "ruc": sup_ruc,
            "nombre": sup_nombre,
            "tipo_documento": "RUC" if (sup_ruc and len(sup_ruc) == 11) else "DNI",
            "direccion": sup_dir,
        },
        "totales": {
            "subtotal": base_gravada,
            "igv": round(igv_total or 0, 2),
            "base_gravada": base_gravada,
            "base_no_gravada": base_no_gravada,
            "total": round(total or 0, 2),
            "impuestos_incluidos": False,
        },
        "lineas": lineas,
        "notas": None,
        "confianza": 1.0,  # Datos oficiales SUNAT
    }


@router.post("/facturas-proveedor/extract-from-xml")
async def extract_from_xml(
    file: UploadFile = File(...),
    empresa_id: int = Depends(get_empresa_id),
):
    """Extrae datos de factura desde XML SUNAT (UBL 2.1) — datos oficiales y precisos."""
    if not (file.filename or "").lower().endswith(".xml"):
        raise HTTPException(400, "El archivo debe ser un XML")
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(400, "XML demasiado grande (máx 5MB)")
    extraccion = _parse_xml_sunat(contents)
    extraccion = await _enriquecer_con_bd(extraccion, empresa_id)
    return {"ok": True, "fuente": "xml_sunat", "data": extraccion}
