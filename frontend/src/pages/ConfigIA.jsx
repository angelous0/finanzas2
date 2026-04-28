import React, { useEffect, useState } from 'react';
import { Sparkles, Eye, EyeOff, CheckCircle2, XCircle, Loader2, Trash2, ExternalLink, Save, Zap, DollarSign, Activity, TrendingUp } from 'lucide-react';
import { toast } from 'sonner';
import { getConfigIA, saveConfigIA, testConfigIA, getUsageIA } from '../services/api';

/**
 * Configuración global de IA (OpenAI) para extracción de facturas.
 * Hay UNA sola configuración compartida entre todas las empresas del sistema.
 */
export default function ConfigIA() {
  const [config, setConfig] = useState(null);
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');  // string vacío = no cambiar
  const [model, setModel] = useState('gpt-4o-mini');
  const [keyTouched, setKeyTouched] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [r1, r2] = await Promise.all([getConfigIA(), getUsageIA().catch(() => null)]);
      setConfig(r1.data);
      setModel(r1.data.openai_model || 'gpt-4o-mini');
      setApiKeyInput('');
      setKeyTouched(false);
      if (r2) setUsage(r2.data);
    } catch (e) {
      toast.error('Error cargando configuración');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const payload = { openai_model: model };
      if (keyTouched) payload.openai_api_key = apiKeyInput;  // "" para borrar
      await saveConfigIA(payload);
      toast.success('Configuración guardada');
      await load();
    } catch (e) {
      toast.error('Error al guardar');
    } finally { setSaving(false); }
  };

  const handleTest = async () => {
    if (testing) return;
    setTesting(true);
    try {
      // Si el usuario tipeó una key nueva, primero guarda
      if (keyTouched) {
        await saveConfigIA({ openai_api_key: apiKeyInput, openai_model: model });
      }
      const r = await testConfigIA();
      toast.success(`Conexión OK con ${r.data.model}`);
      await load();
    } catch (e) {
      const msg = e.response?.data?.detail || 'Error en la prueba';
      toast.error(typeof msg === 'string' ? msg : 'Error en la prueba');
      await load();  // refrescar estado
    } finally { setTesting(false); }
  };

  const handleClearKey = async () => {
    if (!window.confirm('¿Eliminar la API key guardada en BD? Quedará el .env como fallback (si está configurado).')) return;
    setSaving(true);
    try {
      await saveConfigIA({ openai_api_key: '' });
      toast.success('API key eliminada');
      await load();
    } catch {
      toast.error('Error al eliminar');
    } finally { setSaving(false); }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4rem' }}>
        <Loader2 className="animate-spin" />
      </div>
    );
  }

  const tieneKey = config?.tiene_key_bd || config?.tiene_key_env;
  const fuente = config?.tiene_key_bd ? 'BD' : (config?.tiene_key_env ? '.env (servidor)' : 'no configurada');

  return (
    <div className="page" style={{ padding: '1.5rem', maxWidth: 760, margin: '0 auto' }}>
      <div className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Sparkles size={22} /> Configuración de IA
        </h1>
        <p className="page-subtitle">
          Configurar la API key de OpenAI para extracción automática de facturas (foto/PDF).
        </p>
      </div>

      {/* Estado actual */}
      <div className="card" style={{ padding: '1rem 1.25rem', marginBottom: '1rem', background: tieneKey ? 'rgba(34,197,94,0.05)' : 'rgba(245,158,11,0.05)', borderLeft: `3px solid ${tieneKey ? '#22C55E' : '#f59e0b'}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, marginBottom: '0.5rem' }}>
          {tieneKey ? <CheckCircle2 size={18} color="#22C55E" /> : <XCircle size={18} color="#f59e0b" />}
          {tieneKey ? 'IA configurada' : 'IA no configurada'}
        </div>
        <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
          Fuente activa: <strong>{fuente}</strong>
          {config?.openai_api_key_masked && <> · Key: <code style={{ fontSize: '0.75rem' }}>{config.openai_api_key_masked}</code></>}
        </div>
        {config?.last_test_at && (
          <div style={{ fontSize: '0.78rem', marginTop: '0.5rem', color: config.last_test_ok ? '#15803d' : '#b91c1c' }}>
            {config.last_test_ok ? '✓' : '✗'} Última prueba: {new Date(config.last_test_at).toLocaleString('es-PE')}
            {!config.last_test_ok && config.last_test_error && (
              <div style={{ fontSize: '0.7rem', marginTop: '0.25rem', fontFamily: 'monospace' }}>{config.last_test_error}</div>
            )}
          </div>
        )}
      </div>

      {/* Formulario */}
      <div className="card" style={{ padding: '1.25rem' }}>
        <h3 style={{ marginTop: 0, marginBottom: '1rem', fontSize: '1rem', fontWeight: 600 }}>OpenAI</h3>

        {/* API Key */}
        <div className="form-group">
          <label className="form-label">API Key</label>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <input
                type={showKey ? 'text' : 'password'}
                className="form-input"
                value={apiKeyInput}
                onChange={(e) => { setApiKeyInput(e.target.value); setKeyTouched(true); }}
                placeholder={config?.openai_api_key_masked || 'sk-proj-...'}
                style={{ paddingRight: '2.5rem', fontFamily: 'monospace', fontSize: '0.85rem' }}
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                style={{ position: 'absolute', right: '0.5rem', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)' }}
                title={showKey ? 'Ocultar' : 'Mostrar'}
              >
                {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {config?.tiene_key_bd && (
              <button type="button" className="btn btn-outline" onClick={handleClearKey} title="Eliminar key guardada">
                <Trash2 size={14} />
              </button>
            )}
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: '0.375rem' }}>
            Empieza con <code>sk-proj-</code> o <code>sk-</code>. Si dejas el campo vacío, no se modifica.
            <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer" style={{ marginLeft: '0.5rem', color: 'var(--primary)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
              Conseguir API key <ExternalLink size={11} />
            </a>
          </p>
        </div>

        {/* Modelo */}
        <div className="form-group" style={{ marginTop: '1rem' }}>
          <label className="form-label">Modelo de visión</label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.375rem' }}>
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', padding: '0.625rem 0.75rem', border: `1px solid ${model === 'gpt-4o-mini' ? 'var(--primary)' : 'var(--border)'}`, borderRadius: 6, cursor: 'pointer', background: model === 'gpt-4o-mini' ? 'rgba(99,102,241,0.05)' : undefined }}>
              <input type="radio" name="model" value="gpt-4o-mini" checked={model === 'gpt-4o-mini'} onChange={() => setModel('gpt-4o-mini')} />
              <div>
                <div style={{ fontWeight: 500 }}>gpt-4o-mini <span style={{ background: '#dbeafe', color: '#1e40af', padding: '1px 6px', borderRadius: 4, fontSize: '0.65rem', marginLeft: '0.375rem' }}>RECOMENDADO</span></div>
                <div style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>Rápido y barato. ~$0.003 USD por factura. Suficiente para facturas claras.</div>
              </div>
            </label>
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem', padding: '0.625rem 0.75rem', border: `1px solid ${model === 'gpt-4o' ? 'var(--primary)' : 'var(--border)'}`, borderRadius: 6, cursor: 'pointer', background: model === 'gpt-4o' ? 'rgba(99,102,241,0.05)' : undefined }}>
              <input type="radio" name="model" value="gpt-4o" checked={model === 'gpt-4o'} onChange={() => setModel('gpt-4o')} />
              <div>
                <div style={{ fontWeight: 500 }}>gpt-4o</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--muted)' }}>Más preciso. ~$0.015 USD por factura. Úsalo si las imágenes son borrosas o manuscritas.</div>
              </div>
            </label>
          </div>
        </div>

        {/* Acciones */}
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1.25rem', justifyContent: 'flex-end' }}>
          <button type="button" className="btn btn-outline" onClick={handleTest} disabled={testing || saving}>
            {testing ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
            {testing ? 'Probando...' : 'Probar conexión'}
          </button>
          <button type="button" className="btn btn-primary" onClick={handleSave} disabled={saving || testing}>
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {saving ? 'Guardando...' : 'Guardar'}
          </button>
        </div>
      </div>

      {/* Uso y costos */}
      {usage && (
        <div className="card" style={{ padding: '1.25rem', marginTop: '1rem' }}>
          <h3 style={{ marginTop: 0, marginBottom: '0.875rem', fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
            <Activity size={18} /> Uso y costos
          </h3>

          {/* KPIs mes actual */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
            <div style={{ padding: '0.75rem', background: 'rgba(34,197,94,0.05)', border: '1px solid rgba(34,197,94,0.2)', borderRadius: 8 }}>
              <div style={{ fontSize: '0.7rem', color: '#15803d', fontWeight: 600, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <DollarSign size={12} /> Gasto este mes
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#15803d', marginTop: '0.25rem' }}>
                ${usage.mes_actual.costo_usd.toFixed(4)}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>
                S/ {(usage.mes_actual.costo_usd * 3.75).toFixed(2)} aprox
              </div>
            </div>
            <div style={{ padding: '0.75rem', background: 'rgba(99,102,241,0.05)', border: '1px solid rgba(99,102,241,0.2)', borderRadius: 8 }}>
              <div style={{ fontSize: '0.7rem', color: '#4f46e5', fontWeight: 600, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <Sparkles size={12} /> Facturas mes
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#4f46e5', marginTop: '0.25rem' }}>
                {usage.mes_actual.llamadas_ok}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>
                {usage.mes_actual.llamadas_error > 0 ? `${usage.mes_actual.llamadas_error} con error` : 'sin errores'}
              </div>
            </div>
            <div style={{ padding: '0.75rem', background: 'var(--card-bg-hover)', border: '1px solid var(--border)', borderRadius: 8 }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--muted)', fontWeight: 600, textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                <TrendingUp size={12} /> Promedio
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: '0.25rem' }}>
                ${usage.mes_actual.llamadas_ok > 0 ? (usage.mes_actual.costo_usd / usage.mes_actual.llamadas_ok).toFixed(4) : '0.0000'}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>por factura</div>
            </div>
          </div>

          {/* Detalle por modelo */}
          {usage.por_modelo_mes.length > 0 && (
            <div style={{ fontSize: '0.78rem', marginBottom: '0.75rem' }}>
              <strong style={{ display: 'block', marginBottom: '0.375rem' }}>Por modelo (mes actual):</strong>
              {usage.por_modelo_mes.map(m => (
                <div key={m.modelo} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0', borderBottom: '1px dashed var(--border)' }}>
                  <span><code>{m.modelo}</code> · {m.llamadas} llamada{m.llamadas !== 1 ? 's' : ''}</span>
                  <span style={{ fontFamily: 'monospace', color: '#15803d', fontWeight: 600 }}>${m.costo_usd.toFixed(4)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Total histórico */}
          <div style={{ fontSize: '0.78rem', color: 'var(--muted)', padding: '0.625rem 0.75rem', background: 'var(--card-bg-hover)', borderRadius: 6 }}>
            <strong>Total histórico:</strong> {usage.total.llamadas_ok} facturas procesadas · ${usage.total.costo_usd.toFixed(4)} USD
            {usage.total.primera_llamada && <> · desde {new Date(usage.total.primera_llamada).toLocaleDateString('es-PE')}</>}
          </div>

          {/* Link al dashboard oficial */}
          <div style={{ marginTop: '0.75rem', textAlign: 'right' }}>
            <a
              href="https://platform.openai.com/usage"
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: '0.78rem', color: 'var(--primary)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}
            >
              Ver saldo y dashboard oficial OpenAI <ExternalLink size={11} />
            </a>
          </div>
        </div>
      )}

      {/* Notas */}
      <div style={{ fontSize: '0.78rem', color: 'var(--muted)', marginTop: '1rem', padding: '0.75rem 1rem', background: 'var(--card-bg-hover)', borderRadius: 6 }}>
        💡 <strong>Cómo funciona:</strong> El sistema lee primero la API key guardada aquí (BD).
        Si no hay, cae a la variable de entorno <code>OPENAI_API_KEY</code> del servidor.
        Esto permite cambiar la key desde el frontend sin tocar el servidor. El saldo real lo ves en el dashboard de OpenAI (link arriba).
      </div>
    </div>
  );
}
