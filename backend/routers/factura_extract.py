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
from routers.config_ia import get_active_openai_key_and_model

logger = logging.getLogger(__name__)
router = APIRouter()


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
    """Convierte bytes de imagen a data URL para OpenAI.

    OpenAI Vision soporta JPEG, PNG, GIF, WebP. NO soporta HEIC/HEIF (iPhone).
    Si recibimos HEIC o una imagen muy grande, la normalizamos a JPEG y la
    reescalamos a max 2000px del lado mayor.
    """
    needs_convert = (
        mime in ("image/heic", "image/heif", "image/x-heic", "image/x-heif")
        or len(image_bytes) > 4 * 1024 * 1024  # > 4MB siempre re-comprime
    )
    if needs_convert:
        try:
            from PIL import Image
            from io import BytesIO
            # Registrar opener HEIC si está disponible
            try:
                from pillow_heif import register_heif_opener
                register_heif_opener()
            except ImportError:
                pass
            img = Image.open(BytesIO(image_bytes))
            # Convertir a RGB (HEIC suele venir en otros modos)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            # Reescalar si el lado mayor > 2000px (no necesitamos más para Vision)
            max_side = 2000
            if max(img.size) > max_side:
                ratio = max_side / max(img.size)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85, optimize=True)
            image_bytes = buf.getvalue()
            mime = "image/jpeg"
            logger.info(f"Imagen convertida/reescalada → {len(image_bytes)//1024}KB")
        except Exception as e:
            logger.warning(f"No se pudo convertir imagen ({e}), enviando original")
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"


# Precios OpenAI (por 1M tokens) — actualizar si cambia tarifa
PRECIOS_USD = {
    "gpt-4o-mini": {"input": 0.150, "output": 0.600},
    "gpt-4o":      {"input": 2.500, "output": 10.000},
}


def _calcular_costo(model: str, tokens_in: int, tokens_out: int) -> float:
    p = PRECIOS_USD.get(model, PRECIOS_USD["gpt-4o-mini"])
    return round((tokens_in / 1_000_000) * p["input"] + (tokens_out / 1_000_000) * p["output"], 6)


async def _registrar_uso(model: str, fuente: str, tokens_in: int, tokens_out: int, ok: bool, error: str = None, empresa_id: int = None):
    """Guarda el uso de la API en cont_uso_ia para tracking."""
    try:
        costo = _calcular_costo(model, tokens_in, tokens_out)
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO finanzas2.cont_uso_ia
                  (modelo, tokens_input, tokens_output, costo_usd, fuente, ok, error, empresa_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """, model, tokens_in, tokens_out, costo, fuente, ok, error, empresa_id)
    except Exception as e:
        logger.warning(f"No se pudo registrar uso de IA: {e}")


async def _extract_with_openai(image_data_url: str, fuente: str = "image", empresa_id: int = None) -> dict:
    """Llama a OpenAI Vision y devuelve el JSON extraído.

    La API key y modelo se resuelven en este orden:
      1. cont_config_ia (BD)  ← configurable desde el frontend
      2. OPENAI_API_KEY del .env (fallback)

    Registra el uso en cont_uso_ia (tokens, costo) para tracking.
    """
    api_key, model = await get_active_openai_key_and_model()
    if not api_key:
        raise HTTPException(
            400,
            "No hay API key de OpenAI configurada. Ve a Configuración → IA y pega tu API key."
        )
    try:
        from openai import OpenAI
    except ImportError:
        raise HTTPException(500, "Librería openai no instalada")
    # Timeout amplio porque Vision puede tardar 20-40s con imágenes grandes
    client = OpenAI(api_key=api_key, timeout=90.0)
    try:
        resp = client.chat.completions.create(
            model=model,
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
        # Registrar uso (tokens del response)
        usage = getattr(resp, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", 0) if usage else 0
        tokens_out = getattr(usage, "completion_tokens", 0) if usage else 0
        await _registrar_uso(model, fuente, tokens_in, tokens_out, True, None, empresa_id)

        content = resp.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        await _registrar_uso(model, fuente, 0, 0, False, str(e)[:500], empresa_id)
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
    """Extrae datos de factura desde imagen (jpg, png, heic, webp).

    Si recibimos HEIC (iPhone) o imagen >4MB, se convierte a JPEG y se reescala
    automáticamente antes de mandar a OpenAI Vision.
    """
    fname = (file.filename or "").lower()
    is_image = (file.content_type or "").startswith("image/") or any(
        fname.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif")
    )
    if not is_image:
        raise HTTPException(400, "El archivo debe ser una imagen (jpg, png, heic, webp)")
    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(400, "Imagen demasiado grande (máx 20MB)")
    # Inferir mime correcto desde extensión si content_type viene vacío o genérico
    mime = file.content_type or "image/jpeg"
    if fname.endswith((".heic", ".heif")):
        mime = "image/heic"
    elif fname.endswith(".jpg") or fname.endswith(".jpeg"):
        mime = "image/jpeg"
    elif fname.endswith(".png"):
        mime = "image/png"
    elif fname.endswith(".webp"):
        mime = "image/webp"
    data_url = _image_to_base64(contents, mime)
    extraccion = await _extract_with_openai(data_url, fuente="image", empresa_id=empresa_id)
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
    extraccion = await _extract_with_openai(data_url, fuente="pdf", empresa_id=empresa_id)
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
