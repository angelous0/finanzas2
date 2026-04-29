from pydantic import BaseModel, Field
from typing import Optional, List, Union
from datetime import datetime, date
from decimal import Decimal

# =====================
# EMPRESA
# =====================
class EmpresaBase(BaseModel):
    nombre: str
    ruc: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    logo_url: Optional[str] = None
    activo: bool = True

class EmpresaCreate(EmpresaBase):
    pass

class EmpresaUpdate(BaseModel):
    nombre: Optional[str] = None
    ruc: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    logo_url: Optional[str] = None
    activo: Optional[bool] = None

class Empresa(EmpresaBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================
# MONEDA
# =====================
class MonedaBase(BaseModel):
    codigo: str
    nombre: str
    simbolo: str
    es_principal: bool = False
    activo: bool = True

class MonedaCreate(MonedaBase):
    pass

class Moneda(MonedaBase):
    id: int
    created_at: Optional[datetime] = None

# =====================
# CATEGORIA
# =====================
class CategoriaBase(BaseModel):
    codigo: Optional[str] = None
    nombre: str
    tipo: str  # ingreso, egreso
    padre_id: Optional[int] = None
    descripcion: Optional[str] = None
    cuenta_gasto_id: Optional[int] = None
    activo: bool = True

class CategoriaCreate(CategoriaBase):
    pass

class CategoriaUpdate(BaseModel):
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    padre_id: Optional[int] = None
    descripcion: Optional[str] = None
    cuenta_gasto_id: Optional[int] = None
    activo: Optional[bool] = None

class Categoria(CategoriaBase):
    id: int
    empresa_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================
# CUENTA CONTABLE
# =====================
class CuentaContableBase(BaseModel):
    codigo: str
    nombre: str
    tipo: str  # ACTIVO, PASIVO, GASTO, INGRESO, IMPUESTO, OTRO
    es_activa: bool = True

class CuentaContableCreate(CuentaContableBase):
    pass

class CuentaContableUpdate(BaseModel):
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    es_activa: Optional[bool] = None

class CuentaContable(CuentaContableBase):
    id: int
    empresa_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ConfigEmpresaContable(BaseModel):
    empresa_id: Optional[int] = None
    cta_gastos_default_id: Optional[int] = None
    cta_igv_default_id: Optional[int] = None
    cta_xpagar_default_id: Optional[int] = None
    cta_otrib_default_id: Optional[int] = None

# =====================
# CENTRO COSTO
# =====================
class CentroCostoBase(BaseModel):
    codigo: Optional[str] = None
    nombre: str
    descripcion: Optional[str] = None
    activo: bool = True

class CentroCostoCreate(CentroCostoBase):
    pass

class CentroCosto(CentroCostoBase):
    id: int
    created_at: Optional[datetime] = None

# =====================
# LINEA NEGOCIO
# =====================
class LineaNegocioBase(BaseModel):
    codigo: Optional[str] = None
    nombre: str
    descripcion: Optional[str] = None
    activo: bool = True
    odoo_linea_negocio_id: Optional[int] = None
    odoo_linea_negocio_nombre: Optional[str] = None

class LineaNegocioCreate(LineaNegocioBase):
    pass

class LineaNegocio(LineaNegocioBase):
    id: int
    created_at: Optional[datetime] = None

# =====================
# CUENTA FINANCIERA
# =====================
class CuentaFinancieraBase(BaseModel):
    nombre: str
    tipo: str  # banco, caja
    banco: Optional[str] = None
    numero_cuenta: Optional[str] = None
    cci: Optional[str] = None
    moneda_id: Optional[int] = None
    saldo_actual: float = 0
    saldo_inicial: float = 0
    activo: bool = True
    cuenta_contable_id: Optional[int] = None

class CuentaFinancieraCreate(CuentaFinancieraBase):
    pass

class CuentaFinancieraUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    banco: Optional[str] = None
    numero_cuenta: Optional[str] = None
    cci: Optional[str] = None
    moneda_id: Optional[int] = None
    saldo_inicial: Optional[float] = None
    activo: Optional[bool] = None
    cuenta_contable_id: Optional[int] = None

class CuentaFinanciera(CuentaFinancieraBase):
    id: int
    empresa_id: Optional[int] = None
    moneda_codigo: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================
# TERCERO (Cliente/Proveedor/Personal)
# =====================
class TerceroBase(BaseModel):
    tipo_documento: Optional[str] = None
    numero_documento: Optional[str] = None
    nombre: str
    nombre_comercial: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    es_cliente: bool = False
    es_proveedor: bool = False
    es_personal: bool = False
    terminos_pago_dias: int = 0
    limite_credito: float = 0
    notas: Optional[str] = None
    activo: bool = True
    tipo_persona: Optional[str] = None
    tip_doc_iden: Optional[str] = None
    apellido1: Optional[str] = None
    apellido2: Optional[str] = None
    nombres: Optional[str] = None

class TerceroCreate(TerceroBase):
    pass

class TerceroUpdate(BaseModel):
    tipo_documento: Optional[str] = None
    numero_documento: Optional[str] = None
    nombre: Optional[str] = None
    nombre_comercial: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    es_cliente: Optional[bool] = None
    es_proveedor: Optional[bool] = None
    es_personal: Optional[bool] = None
    terminos_pago_dias: Optional[int] = None
    limite_credito: Optional[float] = None
    notas: Optional[str] = None
    activo: Optional[bool] = None
    tipo_persona: Optional[str] = None
    tip_doc_iden: Optional[str] = None
    apellido1: Optional[str] = None
    apellido2: Optional[str] = None
    nombres: Optional[str] = None

class Tercero(TerceroBase):
    id: int
    empresa_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================
# EMPLEADO DETALLE
# =====================
class EmpleadoDetalleBase(BaseModel):
    tercero_id: Optional[int] = None  # Optional in Create, set from URL path
    fecha_ingreso: Optional[date] = None
    cargo: Optional[str] = None
    salario_base: Optional[float] = None
    cuenta_bancaria: Optional[str] = None
    banco: Optional[str] = None
    centro_costo_id: Optional[int] = None
    linea_negocio_id: Optional[int] = None
    activo: bool = True

class EmpleadoDetalleCreate(BaseModel):
    # tercero_id comes from URL path, not body
    fecha_ingreso: Optional[date] = None
    cargo: Optional[str] = None
    salario_base: Optional[float] = None
    cuenta_bancaria: Optional[str] = None
    banco: Optional[str] = None
    centro_costo_id: Optional[int] = None
    linea_negocio_id: Optional[int] = None
    activo: bool = True

class EmpleadoDetalle(EmpleadoDetalleBase):
    id: int
    created_at: Optional[datetime] = None

# =====================
# ARTICULO REF
# =====================
class ArticuloRefBase(BaseModel):
    prod_inventario_id: Optional[str] = None
    codigo: Optional[str] = None
    nombre: str
    descripcion: Optional[str] = None
    precio_referencia: Optional[float] = None
    activo: bool = True

class ArticuloRefCreate(ArticuloRefBase):
    pass

class ArticuloRef(ArticuloRefBase):
    id: Union[int, str]
    created_at: Optional[datetime] = None

# =====================
# ORDEN DE COMPRA
# =====================
class OCLineaBase(BaseModel):
    articulo_id: Optional[str] = None  # Changed to str to support UUID from prod_inventario
    descripcion: Optional[str] = None
    cantidad: float
    precio_unitario: float
    igv_aplica: bool = True

class OCLineaCreate(OCLineaBase):
    pass

class OCLinea(OCLineaBase):
    id: int
    oc_id: int
    subtotal: float = 0
    created_at: Optional[datetime] = None

class OCBase(BaseModel):
    fecha: date
    proveedor_id: Optional[int] = None
    moneda_id: Optional[int] = None
    notas: Optional[str] = None

class OCCreate(OCBase):
    lineas: List[OCLineaCreate] = []
    igv_incluido: bool = False

class OCUpdate(BaseModel):
    fecha: Optional[date] = None
    proveedor_id: Optional[int] = None
    moneda_id: Optional[int] = None
    estado: Optional[str] = None
    notas: Optional[str] = None
    lineas: Optional[List[OCLineaCreate]] = None
    igv_incluido: Optional[bool] = None

class OC(OCBase):
    id: int
    empresa_id: Optional[int] = None
    numero: str
    estado: str = "borrador"
    subtotal: float = 0
    igv: float = 0
    total: float = 0
    proveedor_nombre: Optional[str] = None
    moneda_codigo: Optional[str] = None
    lineas: List[OCLinea] = []
    factura_generada_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================
# FACTURA PROVEEDOR
# =====================
class FacturaLineaBase(BaseModel):
    categoria_id: Optional[int] = None
    articulo_id: Optional[str] = None
    servicio_id: Optional[str] = None
    servicio_detalle: Optional[str] = None
    tipo_linea: Optional[str] = None
    descripcion: Optional[str] = None
    linea_negocio_id: Optional[int] = None
    centro_costo_id: Optional[int] = None
    importe: float
    igv_aplica: bool = True
    cantidad: Optional[float] = None
    precio_unitario: Optional[float] = None
    modelo_corte_id: Optional[str] = None
    unidad_interna_id: Optional[int] = None

class FacturaLineaCreate(FacturaLineaBase):
    pass

class FacturaLinea(FacturaLineaBase):
    id: int
    factura_id: int
    categoria_nombre: Optional[str] = None
    categoria_padre_id: Optional[int] = None
    categoria_padre_nombre: Optional[str] = None
    linea_negocio_nombre: Optional[str] = None
    centro_costo_nombre: Optional[str] = None
    unidad_interna_nombre: Optional[str] = None
    created_at: Optional[datetime] = None

class FacturaProveedorBase(BaseModel):
    proveedor_id: Optional[int] = None
    beneficiario_nombre: Optional[str] = None
    moneda_id: Optional[int] = None
    fecha_factura: date
    fecha_contable: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    terminos_dias: int = 0
    tipo_documento: str = "factura"
    impuestos_incluidos: bool = False
    tipo_comprobante_sunat: Optional[str] = None
    base_gravada: float = 0
    igv_sunat: float = 0
    base_no_gravada: float = 0
    isc: float = 0
    notas: Optional[str] = None

class FacturaProveedorCreate(FacturaProveedorBase):
    numero: Optional[str] = None
    tipo_cambio: Optional[float] = None
    lineas: List[FacturaLineaCreate] = []

class FacturaProveedorUpdate(BaseModel):
    proveedor_id: Optional[int] = None
    beneficiario_nombre: Optional[str] = None
    moneda_id: Optional[int] = None
    fecha_factura: Optional[date] = None
    fecha_contable: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    terminos_dias: Optional[int] = None
    tipo_documento: Optional[str] = None
    impuestos_incluidos: Optional[bool] = None
    tipo_comprobante_sunat: Optional[str] = None
    base_gravada: Optional[float] = None
    igv_sunat: Optional[float] = None
    base_no_gravada: Optional[float] = None
    isc: Optional[float] = None
    tipo_cambio: Optional[float] = None
    notas: Optional[str] = None
    lineas: Optional[list] = None

class FacturaProveedor(FacturaProveedorBase):
    id: int
    empresa_id: Optional[int] = None
    numero: str
    estado: str = "pendiente"
    subtotal: float = 0
    igv: float = 0
    total: float = 0
    saldo_pendiente: float = 0
    proveedor_nombre: Optional[str] = None
    moneda_codigo: Optional[str] = None
    moneda_simbolo: Optional[str] = None
    lineas: List[FacturaLinea] = []
    oc_origen_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================
# PAGO
# =====================
class PagoDetalleBase(BaseModel):
    cuenta_financiera_id: int
    medio_pago: str  # efectivo, transferencia, cheque, tarjeta
    monto: float
    referencia: Optional[str] = None

class PagoDetalleCreate(PagoDetalleBase):
    pass

class PagoDetalle(PagoDetalleBase):
    id: int
    pago_id: Optional[int] = None
    movimiento_tesoreria_id: Optional[int] = None
    cuenta_nombre: Optional[str] = None
    created_at: Optional[datetime] = None

class PagoAplicacionBase(BaseModel):
    tipo_documento: str  # factura, letra, gasto, planilla, adelanto, cxc
    documento_id: int
    monto_aplicado: float

class PagoAplicacionCreate(PagoAplicacionBase):
    pass

class PagoAplicacion(PagoAplicacionBase):
    id: int
    pago_id: Optional[int] = None
    movimiento_tesoreria_id: Optional[int] = None
    created_at: Optional[datetime] = None

class PagoBase(BaseModel):
    tipo: str  # ingreso, egreso
    fecha: date
    cuenta_financiera_id: Optional[int] = None
    moneda_id: Optional[int] = None
    referencia: Optional[str] = None
    notas: Optional[str] = None

class PagoCreate(PagoBase):
    monto_total: float
    detalles: List[PagoDetalleCreate] = []
    aplicaciones: List[PagoAplicacionCreate] = []

class Pago(PagoBase):
    id: int
    empresa_id: Optional[int] = None
    numero: str
    monto_total: float
    cuenta_nombre: Optional[str] = None
    moneda_codigo: Optional[str] = None
    conciliado: Optional[bool] = False
    detalles: List[PagoDetalle] = []
    aplicaciones: List[PagoAplicacion] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================
# LETRA
# =====================
class LetraBase(BaseModel):
    factura_id: int
    proveedor_id: Optional[int] = None
    monto: float
    fecha_emision: date
    fecha_vencimiento: date
    notas: Optional[str] = None

class LetraCreate(LetraBase):
    pass

class LetraUpdate(BaseModel):
    monto: Optional[float] = None
    fecha_vencimiento: Optional[date] = None
    estado: Optional[str] = None
    notas: Optional[str] = None

class Letra(LetraBase):
    id: int
    empresa_id: Optional[int] = None
    numero: str
    numero_unico: Optional[str] = None
    estado: str = "pendiente"
    saldo_pendiente: float
    proveedor_nombre: Optional[str] = None
    factura_numero: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class LetraPersonalizada(BaseModel):
    fecha_vencimiento: date
    monto: float

class GenerarLetrasRequest(BaseModel):
    factura_id: int
    cantidad_letras: int
    monto_por_letra: Optional[float] = None
    dias_entre_letras: int = 30
    letras_personalizadas: Optional[List[LetraPersonalizada]] = None  # Para edición manual

# =====================
# GASTO
# =====================
class GastoLineaBase(BaseModel):
    categoria_id: Optional[int] = None
    descripcion: Optional[str] = None
    linea_negocio_id: Optional[int] = None
    centro_costo_id: Optional[int] = None
    unidad_interna_id: Optional[int] = None
    importe: float
    igv_aplica: bool = True

class GastoLineaCreate(GastoLineaBase):
    pass

class GastoLinea(GastoLineaBase):
    id: int
    gasto_id: int
    categoria_nombre: Optional[str] = None
    categoria_padre_id: Optional[int] = None
    categoria_padre_nombre: Optional[str] = None
    unidad_interna_nombre: Optional[str] = None
    created_at: Optional[datetime] = None

class GastoBase(BaseModel):
    fecha: date
    fecha_contable: Optional[date] = None
    proveedor_id: Optional[int] = None
    beneficiario_nombre: Optional[str] = None
    moneda_id: Optional[int] = None
    tipo_documento: Optional[str] = None
    numero_documento: Optional[str] = None
    tipo_comprobante_sunat: Optional[str] = None
    base_gravada: float = 0
    igv_sunat: float = 0
    base_no_gravada: float = 0
    isc: float = 0
    notas: Optional[str] = None
    categoria_gasto_id: Optional[int] = None
    tipo_asignacion: str = "directo"
    centro_costo_id: Optional[int] = None
    linea_negocio_id: Optional[int] = None
    unidad_interna_id: Optional[int] = None
    impuestos_incluidos: bool = True  # Si True, los importes de líneas YA incluyen IGV

class GastoPagoDetalle(BaseModel):
    cuenta_financiera_id: int
    medio_pago: str = "efectivo"
    monto: float
    referencia: Optional[str] = None

class GastoCreate(GastoBase):
    tipo_cambio: Optional[float] = None
    cuenta_pago_id: Optional[int] = None
    lineas: List[GastoLineaCreate] = []
    pagos: List[GastoPagoDetalle] = []  # Multiple payments that must sum to total

class Gasto(GastoBase):
    id: int
    empresa_id: Optional[int] = None
    numero: str
    subtotal: float = 0
    igv: float = 0
    total: float = 0
    es_cif: Optional[bool] = None  # derivado: TRUE si alguna línea tiene categoría CIF
    proveedor_nombre: Optional[str] = None
    moneda_codigo: Optional[str] = None
    moneda_simbolo: Optional[str] = None
    categoria_gasto_nombre: Optional[str] = None
    centro_costo_nombre: Optional[str] = None
    marca_nombre: Optional[str] = None
    linea_negocio_nombre: Optional[str] = None
    unidad_interna_nombre: Optional[str] = None
    cuenta_pago_id: Optional[int] = None
    cuenta_pago_nombre: Optional[str] = None
    lineas: List[GastoLinea] = []
    pago_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================
# PLANILLA
# =====================
class PlanillaDetalleBase(BaseModel):
    empleado_id: int
    salario_base: float = 0
    bonificaciones: float = 0
    adelantos: float = 0
    otros_descuentos: float = 0

class PlanillaDetalleCreate(PlanillaDetalleBase):
    pass

class PlanillaDetalle(PlanillaDetalleBase):
    id: int
    planilla_id: int
    neto_pagar: float = 0
    empleado_nombre: Optional[str] = None
    created_at: Optional[datetime] = None

class PlanillaBase(BaseModel):
    periodo: str
    fecha_inicio: date
    fecha_fin: date
    notas: Optional[str] = None

class PlanillaCreate(PlanillaBase):
    detalles: List[PlanillaDetalleCreate] = []

class Planilla(PlanillaBase):
    id: int
    empresa_id: Optional[int] = None
    total_bruto: float = 0
    total_adelantos: float = 0
    total_descuentos: float = 0
    total_neto: float = 0
    estado: str = "borrador"
    detalles: List[PlanillaDetalle] = []
    pago_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================
# ADELANTO EMPLEADO
# =====================
class AdelantoBase(BaseModel):
    empleado_id: int
    fecha: date
    monto: float
    motivo: Optional[str] = None

class AdelantoCreate(AdelantoBase):
    pagar: bool = False
    cuenta_financiera_id: Optional[int] = None
    medio_pago: str = "efectivo"

class Adelanto(AdelantoBase):
    id: int
    empresa_id: Optional[int] = None
    pagado: bool = False
    descontado: bool = False
    planilla_id: Optional[int] = None
    pago_id: Optional[int] = None
    empleado_nombre: Optional[str] = None
    created_at: Optional[datetime] = None

# =====================
# VENTA POS (desde Odoo)
# =====================
class VentaPOS(BaseModel):
    id: int
    odoo_id: Optional[int] = None
    date_order: Optional[datetime] = None
    name: Optional[str] = None
    tipo_comp: Optional[str] = None
    num_comp: Optional[str] = None
    partner_id: Optional[int] = None
    partner_name: Optional[str] = None
    tienda_id: Optional[int] = None
    tienda_name: Optional[str] = None
    x_tienda: Optional[str] = None
    vendedor_id: Optional[int] = None
    vendedor_name: Optional[str] = None
    company_id: Optional[int] = None
    company_name: Optional[str] = None
    x_pagos: Optional[str] = None
    quantity_pos_order: Optional[float] = None
    quantity_total: Optional[float] = None
    amount_total: Optional[float] = None
    state: Optional[str] = None
    reserva_pendiente: Optional[float] = 0
    reserva_facturada: Optional[float] = 0
    x_reserva_pendientes: bool = False
    x_reserva_facturada: bool = False
    is_cancel: bool = False
    order_cancel: Optional[str] = None
    reserva: bool = False
    is_credit: bool = False
    reserva_use_id: Optional[int] = None
    estado_local: str = "pendiente"
    cxc_id: Optional[int] = None
    pagos_asignados: Optional[float] = 0
    num_pagos: Optional[int] = 0
    pagos_oficiales: Optional[float] = 0
    num_pagos_oficiales: Optional[int] = 0
    synced_at: Optional[datetime] = None

# =====================
# CXC (Cuentas por Cobrar)
# =====================
class CXCBase(BaseModel):
    venta_pos_id: Optional[int] = None
    cliente_id: Optional[int] = None
    monto_original: float
    saldo_pendiente: float
    fecha_vencimiento: Optional[date] = None
    notas: Optional[str] = None

class CXCCreate(CXCBase):
    pass

class CXC(CXCBase):
    id: int
    estado: str = "pendiente"
    cliente_nombre: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================
# PRESUPUESTO
# =====================
class PresupuestoLineaBase(BaseModel):
    categoria_id: Optional[int] = None
    centro_costo_id: Optional[int] = None
    linea_negocio_id: Optional[int] = None
    mes: int
    monto_presupuestado: float = 0

class PresupuestoLineaCreate(PresupuestoLineaBase):
    pass

class PresupuestoLinea(PresupuestoLineaBase):
    id: int
    presupuesto_id: int
    monto_real: float = 0
    categoria_nombre: Optional[str] = None
    created_at: Optional[datetime] = None

class PresupuestoBase(BaseModel):
    nombre: str
    anio: int
    notas: Optional[str] = None

class PresupuestoCreate(PresupuestoBase):
    lineas: List[PresupuestoLineaCreate] = []

class Presupuesto(PresupuestoBase):
    id: int
    version: int = 1
    estado: str = "borrador"
    lineas: List[PresupuestoLinea] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================
# CONCILIACION BANCARIA
# =====================
class BancoMovRaw(BaseModel):
    id: int
    cuenta_financiera_id: Optional[int] = None
    banco: Optional[str] = None
    banco_excel: Optional[str] = None
    fecha: Optional[date] = None
    descripcion: Optional[str] = None
    referencia: Optional[str] = None
    monto: Optional[float] = None
    cargo: Optional[float] = None  # Keep for backward compatibility
    abono: Optional[float] = None  # Keep for backward compatibility
    saldo: Optional[float] = None  # Keep for backward compatibility
    procesado: bool = False
    created_at: Optional[datetime] = None

class BancoMov(BaseModel):
    id: int
    raw_id: Optional[int] = None
    cuenta_financiera_id: Optional[int] = None
    fecha: date
    tipo: str
    monto: float
    descripcion: Optional[str] = None
    referencia: Optional[str] = None
    conciliado: bool = False
    created_at: Optional[datetime] = None

class ConciliacionLineaBase(BaseModel):
    banco_mov_id: Optional[int] = None
    pago_id: Optional[int] = None
    tipo: Optional[str] = None
    documento_id: Optional[int] = None
    monto: Optional[float] = None
    conciliado: bool = False

class ConciliacionLinea(ConciliacionLineaBase):
    id: int
    conciliacion_id: int
    created_at: Optional[datetime] = None

class ConciliacionBase(BaseModel):
    cuenta_financiera_id: int
    fecha_inicio: date
    fecha_fin: date
    saldo_inicial: Optional[float] = None
    saldo_final: Optional[float] = None
    notas: Optional[str] = None

class ConciliacionCreate(ConciliacionBase):
    pass

class Conciliacion(ConciliacionBase):
    id: int
    diferencia: Optional[float] = None
    estado: str = "borrador"
    cuenta_nombre: Optional[str] = None
    lineas: List[ConciliacionLinea] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================
# REPORTES
# =====================
class FlujoCajaItem(BaseModel):
    fecha: date
    concepto: str
    tipo: str
    monto: float
    saldo_acumulado: float

class EstadoResultadosItem(BaseModel):
    categoria: str
    tipo: str
    monto: float

class BalanceGeneralItem(BaseModel):
    cuenta: str
    tipo: str
    monto: float

# =====================
# DASHBOARD KPIs
# =====================
class DashboardKPIs(BaseModel):
    total_cxp: float = 0
    total_cxc: float = 0
    total_letras_pendientes: float = 0
    saldo_bancos: float = 0
    ventas_mes: float = 0
    gastos_mes: float = 0
    facturas_pendientes: int = 0
    letras_por_vencer: int = 0


# ── Contabilidad: Asientos ──
class AsientoLineaCreate(BaseModel):
    cuenta_id: int
    tercero_id: Optional[int] = None
    centro_costo_id: Optional[int] = None
    presupuesto_id: Optional[int] = None
    debe: float = 0
    haber: float = 0
    glosa: Optional[str] = None

class AsientoLinea(AsientoLineaCreate):
    id: int
    asiento_id: int
    empresa_id: int
    debe_base: float = 0
    haber_base: float = 0
    cuenta_codigo: Optional[str] = None
    cuenta_nombre: Optional[str] = None

class AsientoCreate(BaseModel):
    fecha_contable: date
    origen_tipo: str
    origen_id: int
    origen_numero: Optional[str] = None
    glosa: Optional[str] = None
    moneda: str = 'PEN'
    tipo_cambio: float = 1
    lineas: List[AsientoLineaCreate] = []

class Asiento(BaseModel):
    id: int
    empresa_id: int
    fecha_contable: date
    origen_tipo: str
    origen_id: int
    origen_numero: Optional[str] = None
    glosa: Optional[str] = None
    moneda: str
    tipo_cambio: float
    estado: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    lineas: List[AsientoLinea] = []
    total_debe: Optional[float] = None
    total_haber: Optional[float] = None

class GenerarAsientoRequest(BaseModel):
    origen_tipo: str
    origen_id: int

class RetencionDetalle(BaseModel):
    r_doc: Optional[str] = None
    r_numero: Optional[str] = None
    r_fecha: Optional[date] = None
    d_numero: Optional[str] = None
    d_fecha: Optional[date] = None
    retencion_01: Optional[int] = None
    pdb_ndes: Optional[str] = None
    codtasa: Optional[str] = None
    ind_ret: Optional[str] = None
    b_imp: Optional[float] = None
    igv_ret: Optional[float] = None
