/**
 * SurveillanceDetail.jsx — OryxShield
 * =============================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Detail view for a single AnomalyDetection record.
 * Uses exact model fields from the backend:
 *   disease_code, disease_name, anomaly_type, severity, detected_at,
 *   detection_method, confidence_score, expected_cases, actual_cases,
 *   baseline_cases, percentage_increase, start_date, end_date,
 *   is_verified, is_false_positive, verified_by, verified_at, notes,
 *   location, metadata (z_score, baseline_std, baseline_n)
 *
 * Tabs: Overview | Health Data Trend | Data Quality | Related Clusters | Hotspots
 *
 * Actions: Verify, Dismiss (false positive), Run Detection
 * Responsiveness: stacked layout on < 900 px
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { surveillanceApi, extractError } from '../../services/api';
import { useToast } from '../../context/ToastContext';
import Breadcrumb from '../../components/ui/Breadcrumb';

// ─── Animation ────────────────────────────────────────────────────────────────
const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3, ease: 'easeOut', delay },
});

// ─── Design tokens ────────────────────────────────────────────────────────────
const T = {
  bg:          '#0a0f1e',
  surface:     '#111827',
  surfaceHigh: '#151e2e',
  border:      '#1f2937',
  accent:      '#3b82f6',
  danger:      '#ef4444',
  warning:     '#f59e0b',
  success:     '#10b981',
  purple:      '#a78bfa',
  text:        '#f9fafb',
  textSub:     '#9ca3af',
  textMuted:   '#6b7280',
};

// ─── Maps ─────────────────────────────────────────────────────────────────────
const SEVERITY_CFG = {
  LOW:      { color: '#10b981', label: 'LOW' },
  MEDIUM:   { color: '#f59e0b', label: 'MEDIUM' },
  HIGH:     { color: '#f97316', label: 'HIGH' },
  CRITICAL: { color: '#ef4444', label: 'CRITICAL' },
};

const ANOMALY_TYPE_LABELS = {
  SPIKE:    'Case Spike',
  TREND:    'Unusual Trend',
  CLUSTER:  'Geographic Cluster',
  OUTBREAK: 'Potential Outbreak',
  PATTERN:  'Pattern Change',
  SEASONAL: 'Seasonal Anomaly',
};

const CHECK_TYPE_LABELS = {
  COMPLETENESS: 'Completeness',
  CONSISTENCY:  'Consistency',
  ACCURACY:     'Accuracy',
  TIMELINESS:   'Timeliness',
  DUPLICATION:  'Duplication',
};

const RISK_LEVEL_CFG = {
  LOW:      { color: '#10b981' },
  MEDIUM:   { color: '#f59e0b' },
  HIGH:     { color: '#f97316' },
  CRITICAL: { color: '#ef4444' },
};

// ─── Shared atoms ─────────────────────────────────────────────────────────────
function Badge({ label, color }) {
  return (
    <span style={{
      background: color + '18',
      border: `1px solid ${color}30`,
      borderRadius: 2,
      padding: '2px 9px',
      fontFamily: 'Space Mono, monospace',
      fontSize: 9,
      letterSpacing: '0.15em',
      textTransform: 'uppercase',
      color,
      whiteSpace: 'nowrap',
    }}>{label}</span>
  );
}

const shimmerStyle = {
  background: `linear-gradient(90deg, #111827 25%, #151e2e 50%, #111827 75%)`,
  backgroundSize: '200% 100%',
  animation: 'shimmer 1.5s infinite',
  borderRadius: 4,
};

function InfoRow({ label, value, mono, accent }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      padding: '9px 0',
      borderBottom: `1px solid ${T.border}`,
      gap: 16,
    }}>
      <span style={{
        fontFamily: 'Space Mono, monospace',
        fontSize: 9,
        color: T.textMuted,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        paddingTop: 2,
        flexShrink: 0,
      }}>{label}</span>
      <span style={{
        fontFamily: mono ? 'Space Mono, monospace' : 'IBM Plex Sans, sans-serif',
        fontSize: mono ? 10 : 13,
        color: accent || T.text,
        textAlign: 'right',
        maxWidth: '65%',
        wordBreak: 'break-word',
      }}>
        {value ?? '—'}
      </span>
    </div>
  );
}

function SectionTitle({ children }) {
  return (
    <div style={{
      fontFamily: 'Bebas Neue, sans-serif',
      fontSize: 15,
      color: T.text,
      letterSpacing: '0.05em',
      marginBottom: 16,
    }}>{children}</div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '10px 14px' }}>
      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, marginBottom: 6 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: p.color || T.text }}>
          {p.name}: <strong>{p.value}</strong>
        </div>
      ))}
    </div>
  );
}

function Ico({ children, size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}
const IcoCheck   = () => <Ico><polyline points="20 6 9 17 4 12"/></Ico>;
const IcoX       = () => <Ico><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></Ico>;
const IcoRun     = () => <Ico><polygon points="5 3 19 12 5 21 5 3"/></Ico>;
const IcoRefresh = () => <Ico><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></Ico>;

function ActionBtn({ onClick, children, icon, variant = 'ghost', disabled }) {
  const styles = {
    ghost:   { background: 'transparent', border: `1px solid ${T.border}`, color: T.textSub },
    accent:  { background: T.accent + '18', border: `1px solid ${T.accent}40`, color: T.accent },
    success: { background: T.success + '18', border: `1px solid ${T.success}40`, color: T.success },
    danger:  { background: T.danger + '18', border: `1px solid ${T.danger}40`, color: T.danger },
    warning: { background: T.warning + '18', border: `1px solid ${T.warning}40`, color: T.warning },
  };
  return (
    <button
      onClick={disabled ? undefined : onClick}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        borderRadius: 4, padding: '8px 16px',
        fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'all 0.15s',
        opacity: disabled ? 0.5 : 1,
        ...styles[variant],
      }}
    >
      {icon} {children}
    </button>
  );
}

function fmtDate(dt) {
  if (!dt) return '—';
  return new Date(dt).toLocaleString('en-NA', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}
function fmtDateShort(dt) {
  if (!dt) return '—';
  return new Date(dt).toLocaleDateString('en-NA', { day: '2-digit', month: 'short', year: 'numeric' });
}

// ─── Tabs ─────────────────────────────────────────────────────────────────────
const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'chart',    label: 'Health Data' },
  { key: 'stats',    label: 'Statistics' },
  { key: 'quality',  label: 'Data Quality' },
  { key: 'clusters', label: 'Related Clusters' },
  { key: 'hotspots', label: 'Nearby Hotspots' },
];

// ─── Skeleton ─────────────────────────────────────────────────────────────────
function LoadingSkeleton() {
  return (
    <div style={{ minHeight: '100vh', background: T.bg, padding: 'clamp(16px, 3vw, 28px)' }}>
      <style>{`@keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }`}</style>
      <div style={{ ...shimmerStyle, height: 20, width: 160, marginBottom: 24 }} />
      <div style={{ ...shimmerStyle, height: 44, width: 340, marginBottom: 8 }} />
      <div style={{ ...shimmerStyle, height: 16, width: 260, marginBottom: 32 }} />
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 280 }}>
          {Array.from({ length: 8 }).map((_, i) => <div key={i} style={{ ...shimmerStyle, height: 38, marginBottom: 6 }} />)}
        </div>
        <div style={{ width: 260 }}>
          {Array.from({ length: 4 }).map((_, i) => <div key={i} style={{ ...shimmerStyle, height: 90, marginBottom: 10 }} />)}
        </div>
      </div>
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function SurveillanceDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { error: toastError, success: toastSuccess } = useToast();

  const [anomaly, setAnomaly]       = useState(null);
  const [loading, setLoading]       = useState(true);
  const [fetchErr, setFetchErr]     = useState(null);
  const [tab, setTab]               = useState('overview');
  const [acting, setActing]         = useState(false);

  // Tab data
  const [healthData, setHealthData]       = useState([]);
  const [healthLoading, setHealthLoading] = useState(false);
  const [qualityChecks, setQuality]       = useState([]);
  const [qualityLoading, setQLoading]     = useState(false);
  const [clusters, setClusters]           = useState([]);
  const [clustersLoading, setClLoading]   = useState(false);
  const [hotspots, setHotspots]           = useState([]);
  const [hotspotsLoading, setHotLoading]  = useState(false);

  // Fetch the anomaly record
  const fetchAnomaly = useCallback(async () => {
    setLoading(true); setFetchErr(null);
    try {
      const res = await surveillanceApi.getAnomaly(id);
      setAnomaly(res.data);
    } catch (err) {
      const m = extractError(err);
      setFetchErr(m); toastError(m);
    } finally { setLoading(false); }
  }, [id]);

  useEffect(() => { fetchAnomaly(); }, [fetchAnomaly]);

  // Fetch related health data when chart tab opens
  const fetchHealthData = useCallback(async () => {
    if (!anomaly) return;
    setHealthLoading(true);
    try {
      const params = { page_size: 90, disease_code: anomaly.disease_code };
      if (anomaly.location) params.location = anomaly.location;
      const res = await surveillanceApi.listHealthData(params);
      const raw = res.data.results ?? res.data;
      // Group by date and sum cases
      const byDate = {};
      raw.forEach(d => {
        const date = (d.date_recorded || d.created_at || '').split('T')[0];
        if (!date) return;
        byDate[date] = (byDate[date] || 0) + 1;
      });
      setHealthData(
        Object.entries(byDate)
          .map(([date, cases]) => ({ date, cases }))
          .sort((a, b) => a.date.localeCompare(b.date))
      );
    } catch (_) {}
    finally { setHealthLoading(false); }
  }, [anomaly]);

  // Fetch quality checks
  const fetchQuality = useCallback(async () => {
    if (!anomaly) return;
    setQLoading(true);
    try {
      const res = await surveillanceApi.listDataQuality({ page_size: 20 });
      setQuality(res.data.results ?? res.data);
    } catch (_) {}
    finally { setQLoading(false); }
  }, [anomaly]);

  // Fetch related clusters — same disease
  const fetchClusters = useCallback(async () => {
    if (!anomaly) return;
    setClLoading(true);
    try {
      const res = await surveillanceApi.listClusters({ disease_code: anomaly.disease_code, page_size: 5 });
      setClusters(res.data.results ?? res.data);
    } catch (_) {}
    finally { setClLoading(false); }
  }, [anomaly]);

  // Fetch hotspots — same disease
  const fetchHotspots = useCallback(async () => {
    if (!anomaly) return;
    setHotLoading(true);
    try {
      const res = await surveillanceApi.listHotspots({ disease_code: anomaly.disease_code, is_active: true, page_size: 5 });
      setHotspots(res.data.results ?? res.data);
    } catch (_) {}
    finally { setHotLoading(false); }
  }, [anomaly]);

  // Lazy-load tab data
  useEffect(() => {
    if (!anomaly) return;
    if (tab === 'chart')    fetchHealthData();
    if (tab === 'quality')  fetchQuality();
    if (tab === 'clusters') fetchClusters();
    if (tab === 'hotspots') fetchHotspots();
  }, [tab, anomaly]);

  // Actions
  const handleVerify = async () => {
    setActing(true);
    try {
      await surveillanceApi.confirmAnomaly(id);
      toastSuccess('Anomaly verified');
      fetchAnomaly();
    } catch (e) { toastError(extractError(e)); }
    finally { setActing(false); }
  };

  const handleDismiss = async () => {
    setActing(true);
    try {
      await surveillanceApi.dismissAnomaly(id, { is_false_positive: true, is_verified: false, notes: 'Marked as false positive' });
      toastSuccess('Marked as false positive');
      fetchAnomaly();
    } catch (e) { toastError(extractError(e)); }
    finally { setActing(false); }
  };

  const handleRunDetection = async () => {
    try {
      await surveillanceApi.runAnomalyDetection({});
      toastSuccess('Detection pipeline queued');
    } catch (e) { toastError(extractError(e)); }
  };

  if (loading) return <LoadingSkeleton />;

  if (fetchErr) {
    return (
      <div style={{ minHeight: '100vh', background: T.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: T.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 14, marginBottom: 16 }}>{fetchErr}</div>
          <ActionBtn onClick={() => navigate(-1)} icon={null}>← Go Back</ActionBtn>
        </div>
      </div>
    );
  }

  const sev = anomaly ? (SEVERITY_CFG[anomaly.severity] || { color: T.textSub, label: anomaly.severity }) : null;
  const meta = anomaly?.metadata || {};

  // Compute % deviation
  const deviation = (anomaly?.actual_cases && anomaly?.expected_cases && anomaly.expected_cases > 0)
    ? ((anomaly.actual_cases / anomaly.expected_cases - 1) * 100).toFixed(1)
    : null;

  return (
    <div style={{ minHeight: '100vh', background: T.bg }}>
      <style>{`
        @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 5px; }
        ::-webkit-scrollbar-track { background: #111827; }
        ::-webkit-scrollbar-thumb { background: #1f2937; border-radius: 3px; }
        @media (max-width: 860px) { .detail-sidebar { display: none !important; } }
      `}</style>

      <div style={{ padding: 'clamp(16px, 3vw, 28px)' }}>

        {/* ── Breadcrumb ── */}
        <Breadcrumb items={[
          { label: 'Surveillance', to: '/dashboard/surveillance' },
          { label: anomaly?.disease_name || `Anomaly #${id}` },
        ]} />

        {/* ── Header ── */}
        <motion.div {...fadeUp(0.04)} style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
                {sev && <Badge label={sev.label} color={sev.color} />}
                <Badge label={ANOMALY_TYPE_LABELS[anomaly?.anomaly_type] || anomaly?.anomaly_type || '—'} color={T.accent} />
                {anomaly?.is_false_positive && <Badge label="False Positive" color={T.textMuted} />}
                {anomaly?.is_verified && !anomaly?.is_false_positive && <Badge label="Verified" color={T.success} />}
                {!anomaly?.is_verified && !anomaly?.is_false_positive && <Badge label="Unverified" color={T.warning} />}
              </div>
              <h1 style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 'clamp(26px, 4vw, 40px)', color: T.text, margin: 0, letterSpacing: '0.04em', lineHeight: 1 }}>
                {anomaly?.disease_name || `Anomaly #${id}`}
              </h1>
              <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.textSub, marginTop: 6 }}>
                <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.accent }}>{anomaly?.disease_code}</span>
                {' · '}
                {anomaly?.location_name || 'Unknown location'}
                {' · Detected '}
                {fmtDate(anomaly?.detected_at)}
              </div>
            </div>

            {/* Confidence score pill */}
            {anomaly?.confidence_score != null && (
              <div style={{
                background: T.surface,
                border: `1px solid ${sev?.color || T.border}30`,
                borderRadius: 6,
                padding: '14px 20px',
                textAlign: 'center',
                minWidth: 90,
                flexShrink: 0,
              }}>
                <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>Confidence</div>
                <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 40, color: sev?.color || T.accent, lineHeight: 1 }}>
                  {Number(anomaly.confidence_score).toFixed(0)}
                </div>
                <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 7, color: T.textMuted, marginTop: 2 }}>out of 100</div>
              </div>
            )}
          </div>

          {/* Action buttons */}
          {!anomaly?.is_false_positive && (
            <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
              {!anomaly?.is_verified && (
                <>
                  <ActionBtn onClick={handleVerify} icon={<IcoCheck />} variant="success" disabled={acting}>
                    {acting ? 'Processing…' : 'Verify Anomaly'}
                  </ActionBtn>
                  <ActionBtn onClick={handleDismiss} icon={<IcoX />} variant="danger" disabled={acting}>
                    {acting ? 'Processing…' : 'Mark False Positive'}
                  </ActionBtn>
                </>
              )}
              <ActionBtn onClick={handleRunDetection} icon={<IcoRun />} variant="accent">
                Run Detection
              </ActionBtn>
              <ActionBtn onClick={fetchAnomaly} icon={<IcoRefresh />}>Refresh</ActionBtn>
            </div>
          )}
        </motion.div>

        {/* ── Tabs ── */}
        <motion.div {...fadeUp(0.08)} style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', gap: 0, borderBottom: `1px solid ${T.border}`, overflowX: 'auto', msOverflowStyle: 'none', scrollbarWidth: 'none' }}>
            {TABS.map(t => (
              <button key={t.key} onClick={() => setTab(t.key)} style={{
                background: 'transparent',
                border: 'none',
                borderBottom: tab === t.key ? `2px solid ${T.accent}` : '2px solid transparent',
                padding: '10px 16px',
                fontFamily: 'IBM Plex Sans, sans-serif',
                fontSize: 13,
                color: tab === t.key ? T.text : T.textSub,
                cursor: 'pointer',
                fontWeight: tab === t.key ? 500 : 400,
                transition: 'all 0.15s',
                marginBottom: -1,
                whiteSpace: 'nowrap',
                flexShrink: 0,
              }}>{t.label}</button>
            ))}
          </div>
        </motion.div>

        {/* ── Body: two-column ── */}
        <div style={{ display: 'flex', gap: 18, alignItems: 'flex-start' }}>

          {/* ── Main column ── */}
          <motion.div {...fadeUp(0.12)} style={{ flex: 1, minWidth: 0 }}>

            {/* ──────── OVERVIEW ──────── */}
            {tab === 'overview' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '18px 22px' }}>
                  <SectionTitle>ANOMALY DETAILS</SectionTitle>
                  <InfoRow label="Disease Name"       value={anomaly?.disease_name} />
                  <InfoRow label="Disease Code"       value={anomaly?.disease_code} mono />
                  <InfoRow label="Anomaly Type"       value={ANOMALY_TYPE_LABELS[anomaly?.anomaly_type] || anomaly?.anomaly_type} />
                  <InfoRow label="Severity"           value={sev?.label} accent={sev?.color} />
                  <InfoRow label="Location"           value={anomaly?.location_name} />
                  <InfoRow label="Detection Method"   value={anomaly?.detection_method} />
                  <InfoRow label="Confidence Score"   value={anomaly?.confidence_score != null ? `${Number(anomaly.confidence_score).toFixed(2)} / 100` : null} mono />
                  <InfoRow label="Detected At"        value={fmtDate(anomaly?.detected_at)} mono />
                </div>

                <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '18px 22px' }}>
                  <SectionTitle>CASE STATISTICS</SectionTitle>
                  <InfoRow label="Expected Cases"     value={anomaly?.expected_cases} mono />
                  <InfoRow label="Actual Cases"       value={anomaly?.actual_cases} mono accent={sev?.color} />
                  <InfoRow label="Baseline Cases"     value={anomaly?.baseline_cases} mono />
                  <InfoRow label="% Increase"         value={anomaly?.percentage_increase != null ? `+${Number(anomaly.percentage_increase).toFixed(2)}%` : null} mono accent={sev?.color} />
                  <InfoRow label="Detection Period"   value={anomaly?.start_date ? `${fmtDateShort(anomaly.start_date)} → ${fmtDateShort(anomaly.end_date)}` : null} mono />
                </div>

                {(meta.z_score != null || meta.baseline_std != null || meta.baseline_n != null) && (
                  <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '18px 22px' }}>
                    <SectionTitle>STATISTICAL METADATA</SectionTitle>
                    {meta.z_score != null && <InfoRow label="Z-Score"         value={Number(meta.z_score).toFixed(4)} mono />}
                    {meta.baseline_std != null && <InfoRow label="Baseline Std Dev" value={Number(meta.baseline_std).toFixed(4)} mono />}
                    {meta.baseline_n != null && <InfoRow label="Baseline n"      value={meta.baseline_n} mono />}
                  </div>
                )}

                <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '18px 22px' }}>
                  <SectionTitle>VERIFICATION</SectionTitle>
                  <InfoRow label="Verified"           value={anomaly?.is_verified ? 'Yes' : 'No'} accent={anomaly?.is_verified ? T.success : T.textSub} />
                  <InfoRow label="False Positive"     value={anomaly?.is_false_positive ? 'Yes' : 'No'} accent={anomaly?.is_false_positive ? T.textMuted : T.textSub} />
                  {anomaly?.verified_by_name && <InfoRow label="Verified By"     value={anomaly.verified_by_name} />}
                  {anomaly?.verified_at && <InfoRow label="Verified At"      value={fmtDate(anomaly.verified_at)} mono />}
                  {anomaly?.notes && (
                    <div style={{ marginTop: 14 }}>
                      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>Notes</div>
                      <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text, lineHeight: 1.7, background: T.surfaceHigh, padding: '12px 14px', borderRadius: 4, border: `1px solid ${T.border}` }}>
                        {anomaly.notes}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ──────── HEALTH DATA CHART ──────── */}
            {tab === 'chart' && (
              <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '18px 22px' }}>
                <SectionTitle>HEALTH DATA TREND</SectionTitle>
                <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub, marginBottom: 20 }}>
                  Daily case counts for <strong style={{ color: T.text }}>{anomaly?.disease_name}</strong> at <strong style={{ color: T.text }}>{anomaly?.location_name}</strong>
                </div>
                {healthLoading
                  ? <div style={{ ...shimmerStyle, height: 280, width: '100%' }} />
                  : healthData.length === 0
                    ? <div style={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center', color: T.textSub, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13 }}>
                        No health data found for this disease/location.
                      </div>
                    : (
                      <ResponsiveContainer width="100%" height={300}>
                        <AreaChart data={healthData} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                          <defs>
                            <linearGradient id="caseGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%"  stopColor={sev?.color || T.accent} stopOpacity={0.3} />
                              <stop offset="95%" stopColor={sev?.color || T.accent} stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke={T.border} vertical={false} />
                          <XAxis dataKey="date" tick={{ fontFamily: 'Space Mono, monospace', fontSize: 8, fill: T.textMuted }} tickLine={false} axisLine={{ stroke: T.border }} interval="preserveStartEnd" />
                          <YAxis tick={{ fontFamily: 'Space Mono, monospace', fontSize: 8, fill: T.textMuted }} tickLine={false} axisLine={false} />
                          <Tooltip content={<ChartTooltip />} />
                          {anomaly?.detected_at && (
                            <ReferenceLine
                              x={anomaly.detected_at.split('T')[0]}
                              stroke={sev?.color || T.danger}
                              strokeDasharray="4 4"
                              label={{ value: 'Detected', fill: sev?.color || T.danger, fontFamily: 'Space Mono, monospace', fontSize: 8 }}
                            />
                          )}
                          {/* Baseline reference line */}
                          {anomaly?.expected_cases > 0 && (
                            <ReferenceLine y={anomaly.expected_cases} stroke={T.textMuted} strokeDasharray="4 4"
                              label={{ value: `Baseline (${anomaly.expected_cases})`, fill: T.textMuted, fontFamily: 'Space Mono, monospace', fontSize: 8 }} />
                          )}
                          <Area type="monotone" dataKey="cases" stroke={sev?.color || T.accent} strokeWidth={2} fill="url(#caseGrad)" name="Cases" dot={false} activeDot={{ r: 4 }} />
                        </AreaChart>
                      </ResponsiveContainer>
                    )
                }

                {/* Summary stats below chart */}
                {healthData.length > 0 && (
                  <div style={{ display: 'flex', gap: 12, marginTop: 20, flexWrap: 'wrap' }}>
                    {[
                      { label: 'Total Records', value: healthData.reduce((s, d) => s + d.cases, 0) },
                      { label: 'Peak (single day)', value: Math.max(...healthData.map(d => d.cases)) },
                      { label: 'Days with data', value: healthData.length },
                    ].map(s => (
                      <div key={s.label} style={{ background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '10px 16px', flex: 1 }}>
                        <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>{s.label}</div>
                        <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 24, color: sev?.color || T.accent }}>{s.value}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ──────── STATISTICS (metadata / epi params) ──────── */}
            {tab === 'stats' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* Observed vs Expected visual */}
                <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '18px 22px' }}>
                  <SectionTitle>OBSERVED VS EXPECTED</SectionTitle>
                  <div style={{ display: 'flex', gap: 14, marginBottom: 20, flexWrap: 'wrap' }}>
                    {[
                      { label: 'Actual Cases', value: anomaly?.actual_cases, color: sev?.color || T.danger },
                      { label: 'Expected Cases', value: anomaly?.expected_cases, color: T.textSub },
                      { label: 'Baseline Cases', value: anomaly?.baseline_cases, color: T.accent },
                    ].map(s => (
                      <div key={s.label} style={{ background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '14px 20px', flex: 1, minWidth: 100, textAlign: 'center' }}>
                        <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 6 }}>{s.label}</div>
                        <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 36, color: s.color, lineHeight: 1 }}>{s.value ?? '—'}</div>
                      </div>
                    ))}
                  </div>
                  {deviation != null && (
                    <div style={{ background: (sev?.color || T.danger) + '12', border: `1px solid ${(sev?.color || T.danger)}30`, borderRadius: 4, padding: '10px 16px', textAlign: 'center' }}>
                      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 13, color: sev?.color || T.danger }}>
                        {deviation > 0 ? '+' : ''}{deviation}% deviation from expected
                      </span>
                    </div>
                  )}
                </div>

                {/* Z-score / statistical params */}
                {Object.keys(meta).length > 0 && (
                  <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '18px 22px' }}>
                    <SectionTitle>DETECTION PARAMETERS</SectionTitle>
                    {Object.entries(meta).map(([k, v]) => (
                      <InfoRow key={k}
                        label={k.replace(/_/g, ' ')}
                        value={typeof v === 'number' ? v.toFixed(4) : String(v)}
                        mono
                      />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* ──────── DATA QUALITY ──────── */}
            {tab === 'quality' && (
              <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '18px 22px' }}>
                <SectionTitle>DATA QUALITY CHECKS</SectionTitle>
                <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub, marginBottom: 18 }}>
                  Automated quality assessments from the surveillance pipeline
                </div>
                {qualityLoading
                  ? Array.from({ length: 4 }).map((_, i) => <div key={i} style={{ ...shimmerStyle, height: 56, marginBottom: 8 }} />)
                  : qualityChecks.length === 0
                    ? <div style={{ color: T.textSub, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13 }}>No quality checks found.</div>
                    : qualityChecks.map(c => {
                      const passRate = Number(c.pass_rate || 0);
                      const color = passRate >= 95 ? T.success : passRate >= 80 ? T.warning : T.danger;
                      return (
                        <div key={c.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 14px', background: color + '08', border: `1px solid ${color}20`, borderRadius: 4, marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
                          <div>
                            <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text }}>{c.data_source_name} — {CHECK_TYPE_LABELS[c.check_type] || c.check_type}</div>
                            <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, marginTop: 3 }}>
                              {c.records_checked} checked · {c.records_passed} passed · {c.records_failed} failed
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <span style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 22, color }}>{passRate.toFixed(0)}%</span>
                            <Badge label={c.status} color={c.status === 'COMPLETED' ? T.success : c.status === 'FAILED' ? T.danger : T.warning} />
                          </div>
                        </div>
                      );
                    })
                }
              </div>
            )}

            {/* ──────── RELATED CLUSTERS ──────── */}
            {tab === 'clusters' && (
              <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '18px 22px' }}>
                <SectionTitle>RELATED CASE CLUSTERS</SectionTitle>
                <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub, marginBottom: 18 }}>
                  Case clusters sharing disease code <Badge label={anomaly?.disease_code} color={T.accent} />
                </div>
                {clustersLoading
                  ? Array.from({ length: 3 }).map((_, i) => <div key={i} style={{ ...shimmerStyle, height: 76, marginBottom: 10 }} />)
                  : clusters.length === 0
                    ? <div style={{ color: T.textSub, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13 }}>No related clusters found.</div>
                    : clusters.map(c => (
                      <div key={c.id} style={{ background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '14px 18px', marginBottom: 10 }}
                        onMouseEnter={e => e.currentTarget.style.borderColor = T.accent + '40'}
                        onMouseLeave={e => e.currentTarget.style.borderColor = T.border}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, flexWrap: 'wrap', gap: 6 }}>
                          <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text, fontWeight: 500 }}>{c.name}</div>
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                            <Badge label={`${c.case_count ?? '?'} cases`} color={(c.case_count || 0) > 50 ? T.danger : (c.case_count || 0) > 20 ? T.warning : T.success} />
                            <Badge label={c.is_active ? 'Active' : 'Closed'} color={c.is_active ? T.success : T.textMuted} />
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                          <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted }}>📍 {c.location_name || '—'}</div>
                          <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted }}>🗓 {fmtDateShort(c.start_date)}</div>
                          {c.radius_km != null && <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted }}>⌀ {Number(c.radius_km).toFixed(1)} km</div>}
                          {c.attack_rate != null && <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted }}>AR: {Number(c.attack_rate).toFixed(2)}%</div>}
                          <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted }}>Alg: {c.detection_algorithm || 'SaTScan'}</div>
                        </div>
                      </div>
                    ))
                }
              </div>
            )}

            {/* ──────── NEARBY HOTSPOTS ──────── */}
            {tab === 'hotspots' && (
              <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '18px 22px' }}>
                <SectionTitle>NEARBY HOTSPOTS</SectionTitle>
                <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub, marginBottom: 18 }}>
                  Active geographic hotspots for <Badge label={anomaly?.disease_name} color={T.accent} />
                </div>
                {hotspotsLoading
                  ? Array.from({ length: 3 }).map((_, i) => <div key={i} style={{ ...shimmerStyle, height: 76, marginBottom: 10 }} />)
                  : hotspots.length === 0
                    ? <div style={{ color: T.textSub, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13 }}>No active hotspots found.</div>
                    : hotspots.map(h => {
                      const rc = RISK_LEVEL_CFG[h.risk_level] || { color: T.textMuted };
                      return (
                        <div key={h.id} style={{ background: T.surfaceHigh, border: `1px solid ${rc.color}20`, borderRadius: 4, padding: '14px 18px', marginBottom: 10 }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, flexWrap: 'wrap', gap: 6 }}>
                            <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text, fontWeight: 500 }}>{h.location_name}</div>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <Badge label={h.risk_level} color={rc.color} />
                              <Badge label={`${h.case_count} cases`} color={rc.color} />
                            </div>
                          </div>
                          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                            {h.gi_statistic != null && <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted }}>Gi*: {Number(h.gi_statistic).toFixed(3)}</div>}
                            {h.z_score != null && <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted }}>z: {Number(h.z_score).toFixed(2)}</div>}
                            {h.radius_km != null && <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted }}>⌀ {Number(h.radius_km).toFixed(1)} km</div>}
                            {h.latitude != null && <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted }}>📍 {Number(h.latitude).toFixed(4)}, {Number(h.longitude).toFixed(4)}</div>}
                          </div>
                        </div>
                      );
                    })
                }
              </div>
            )}
          </motion.div>

          {/* ── Right sidebar ── */}
          <motion.div {...fadeUp(0.16)} className="detail-sidebar" style={{ width: 260, flexShrink: 0 }}>

            {/* Case counts card */}
            <div style={{ background: T.surface, border: `1px solid ${sev?.color || T.border}30`, borderRadius: 6, padding: '16px 18px', marginBottom: 14 }}>
              <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 13, color: T.text, letterSpacing: '0.05em', marginBottom: 12 }}>CASE COUNTS</div>
              <div style={{ display: 'flex', gap: 0 }}>
                {[
                  { label: 'Actual', value: anomaly?.actual_cases, color: sev?.color || T.danger },
                  { label: 'Expected', value: anomaly?.expected_cases, color: T.textSub },
                ].map((s, i) => (
                  <div key={s.label} style={{ flex: 1, textAlign: 'center', borderRight: i === 0 ? `1px solid ${T.border}` : 'none', padding: '0 8px' }}>
                    <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, marginBottom: 4 }}>{s.label.toUpperCase()}</div>
                    <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 34, color: s.color, lineHeight: 1 }}>{s.value ?? '—'}</div>
                  </div>
                ))}
              </div>
              {deviation != null && (
                <div style={{ marginTop: 12, padding: '7px 10px', background: (sev?.color || T.danger) + '12', borderRadius: 4, textAlign: 'center' }}>
                  <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 11, color: sev?.color || T.danger }}>
                    {deviation > 0 ? '+' : ''}{deviation}% deviation
                  </span>
                </div>
              )}
            </div>

            {/* % increase */}
            {anomaly?.percentage_increase != null && Number(anomaly.percentage_increase) !== 0 && (
              <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '16px 18px', marginBottom: 14, textAlign: 'center' }}>
                <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>% Increase</div>
                <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 38, color: sev?.color || T.danger, lineHeight: 1 }}>
                  +{Number(anomaly.percentage_increase).toFixed(1)}%
                </div>
              </div>
            )}

            {/* Quick navigation */}
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '16px 18px', marginBottom: 14 }}>
              <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 13, color: T.text, letterSpacing: '0.05em', marginBottom: 12 }}>EXPLORE</div>
              {TABS.map(t => (
                <button key={t.key} onClick={() => setTab(t.key)} style={{
                  display: 'block', width: '100%',
                  background: tab === t.key ? T.accent + '18' : 'transparent',
                  border: `1px solid ${tab === t.key ? T.accent + '40' : T.border}`,
                  borderRadius: 4, padding: '8px 12px',
                  fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12,
                  color: tab === t.key ? T.accent : T.textSub,
                  cursor: 'pointer', textAlign: 'left', marginBottom: 5,
                }}>{t.label}</button>
              ))}
              <div style={{ height: 1, background: T.border, margin: '10px 0' }} />
              <button onClick={() => navigate('/dashboard/alerts')} style={{
                display: 'block', width: '100%', background: 'transparent',
                border: `1px solid ${T.border}`, borderRadius: 4, padding: '8px 12px',
                fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub,
                cursor: 'pointer', textAlign: 'left',
              }}>→ Risk Alerts</button>
              <button onClick={() => navigate('/dashboard/surveillance')} style={{
                display: 'block', width: '100%', background: 'transparent',
                border: `1px solid ${T.border}`, borderRadius: 4, padding: '8px 12px',
                fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub,
                cursor: 'pointer', textAlign: 'left', marginTop: 5,
              }}>← All Anomalies</button>
            </div>

            {/* Detection method info */}
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '16px 18px' }}>
              <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 13, color: T.text, letterSpacing: '0.05em', marginBottom: 12 }}>DETECTION</div>
              <InfoRow label="Method" value={anomaly?.detection_method} />
              <InfoRow label="Period" value={anomaly?.start_date ? `${fmtDateShort(anomaly.start_date)} → ${fmtDateShort(anomaly.end_date)}` : null} mono />
              {meta.z_score != null && <InfoRow label="Z-Score" value={Number(meta.z_score).toFixed(3)} mono accent={sev?.color} />}
              {meta.baseline_std != null && <InfoRow label="Std Dev" value={Number(meta.baseline_std).toFixed(3)} mono />}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}