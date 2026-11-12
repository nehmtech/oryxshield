/**
 * Surveillance.jsx — OryxShield
 * ========================================
 * Company : NEHMTECH INNOVATIONS LIMITED
 * Author  : Nehemiah
 *
 * Full surveillance hub: anomaly detections, case clusters, hotspots,
 * disease profiles, data sources, health data, reports, data quality.
 * Aligns 1-to-1 with Django surveillance app models & serializers.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { surveillanceApi, extractError } from '../../services/api';
import { useToast } from '../../context/ToastContext';
import { useAlertStream } from '../../hooks/ws/useAlertStream';

// ─── Animation helper ────────────────────────────────────────────────────────
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
  teal:        '#2dd4bf',
  text:        '#f9fafb',
  textSub:     '#9ca3af',
  textMuted:   '#6b7280',
};

// ─── Constants ────────────────────────────────────────────────────────────────
const SEVERITY_CFG = {
  LOW:      { color: '#10b981', label: 'LOW' },
  MEDIUM:   { color: '#f59e0b', label: 'MED' },
  HIGH:     { color: '#f97316', label: 'HIGH' },
  CRITICAL: { color: '#ef4444', label: 'CRIT' },
};

const RISK_LEVEL_CFG = {
  LOW:      { color: '#10b981' },
  MEDIUM:   { color: '#f59e0b' },
  HIGH:     { color: '#f97316' },
  CRITICAL: { color: '#ef4444' },
};

const ANOMALY_TYPE_LABELS = {
  SPIKE:    'Spike',
  TREND:    'Trend',
  CLUSTER:  'Cluster',
  OUTBREAK: 'Outbreak',
  PATTERN:  'Pattern',
  SEASONAL: 'Seasonal',
};

const CHECK_TYPE_LABELS = {
  COMPLETENESS: 'Completeness',
  CONSISTENCY:  'Consistency',
  ACCURACY:     'Accuracy',
  TIMELINESS:   'Timeliness',
  DUPLICATION:  'Duplication',
};

const SOURCE_TYPE_LABELS = {
  HOSPITAL:    'Hospital',
  LABORATORY:  'Laboratory',
  CLINIC:      'Clinic',
  PHARMACY:    'Pharmacy',
  COMMUNITY:   'Community',
  DHIS2:       'DHIS2',
  SORMAS:      'SORMAS',
  EMR:         'EMR',
  LIS:         'LIS',
  MANUAL:      'Manual',
  API:         'API',
  OTHER:       'Other',
};

const PAGE_SIZE = 20;

// ─── Small shared components ──────────────────────────────────────────────────
function Badge({ label, color }) {
  return (
    <span style={{
      background: color + '18',
      border: `1px solid ${color}30`,
      borderRadius: 2,
      padding: '2px 8px',
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

function ShimmerRow({ cols = 7 }) {
  const widths = [200, 100, 80, 100, 120, 80, 90];
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} style={{ padding: '12px 16px' }}>
          <div style={{ ...shimmerStyle, height: 14, width: widths[i] || 80 }} />
        </td>
      ))}
    </tr>
  );
}

function StatCard({ label, value, color = T.accent, sub, loading }) {
  return (
    <div style={{
      background: T.surface,
      border: `1px solid ${T.border}`,
      borderRadius: 6,
      padding: '18px 20px',
      flex: 1,
      minWidth: 120,
    }}>
      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.15em', color: T.textMuted, textTransform: 'uppercase', marginBottom: 6 }}>{label}</div>
      {loading
        ? <div style={{ ...shimmerStyle, height: 32, width: 60, marginBottom: 4 }} />
        : <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 34, color, lineHeight: 1 }}>{value ?? '—'}</div>
      }
      {sub && <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: T.textMuted, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function FilterPill({ label, active, onClick, color }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? (color || T.accent) + '22' : 'transparent',
        border: `1px solid ${active ? (color || T.accent) + '60' : T.border}`,
        borderRadius: 20,
        padding: '4px 12px',
        fontFamily: 'Space Mono, monospace',
        fontSize: 9,
        letterSpacing: '0.1em',
        color: active ? (color || T.accent) : T.textSub,
        cursor: 'pointer',
        transition: 'all 0.15s',
        textTransform: 'uppercase',
        whiteSpace: 'nowrap',
      }}
    >{label}</button>
  );
}

function SectionHeader({ title, count, action, actionLabel }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 0 }}>
      <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 17, color: T.text, letterSpacing: '0.05em' }}>
        {title}
        {count != null && (
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted, marginLeft: 10 }}>
            {count}
          </span>
        )}
      </div>
      {action && (
        <button onClick={action} style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.accent, background: 'transparent', border: 'none', cursor: 'pointer', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          {actionLabel || 'View All →'}
        </button>
      )}
    </div>
  );
}

function EmptyState({ msg }) {
  return (
    <div style={{ padding: '36px 20px', textAlign: 'center', color: T.textSub, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13 }}>
      {msg}
    </div>
  );
}

function ErrorState({ msg, onRetry }) {
  return (
    <div style={{ padding: '28px 20px', textAlign: 'center' }}>
      <div style={{ color: T.danger, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, marginBottom: 12 }}>{msg}</div>
      {onRetry && (
        <button onClick={onRetry} style={{ background: T.accent, color: '#fff', border: 'none', borderRadius: 4, padding: '7px 16px', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, cursor: 'pointer' }}>
          Retry
        </button>
      )}
    </div>
  );
}

// ─── Icons ────────────────────────────────────────────────────────────────────
function Ico({ children, size = 14 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {children}
    </svg>
  );
}
const IcoSearch  = () => <Ico><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></Ico>;
const IcoRefresh = () => <Ico><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></Ico>;
const IcoPrev    = () => <Ico><polyline points="15 18 9 12 15 6"/></Ico>;
const IcoNext    = () => <Ico><polyline points="9 18 15 12 9 6"/></Ico>;
const IcoEye     = () => <Ico size={13}><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></Ico>;
const IcoSync    = () => <Ico size={13}><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></Ico>;
const IcoCheck   = () => <Ico size={13}><polyline points="20 6 9 17 4 12"/></Ico>;
const IcoX       = () => <Ico size={13}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></Ico>;
const IcoRun     = () => <Ico size={13}><polygon points="5 3 19 12 5 21 5 3"/></Ico>;
const IcoMap      = () => <Ico size={13}><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></Ico>;
const IcoDownload = () => <Ico size={13}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></Ico>;

// ─── Tab definitions ──────────────────────────────────────────────────────────
const TABS = [
  { key: 'anomalies',    label: 'Anomalies' },
  { key: 'clusters',     label: 'Clusters' },
  { key: 'hotspots',     label: 'Hotspots' },
  { key: 'diseases',     label: 'Disease Profiles' },
  { key: 'sources',      label: 'Data Sources' },
  { key: 'health',       label: 'Health Data' },
  { key: 'reports',      label: 'Reports' },
  { key: 'quality',      label: 'Data Quality' },
];

// ─── Shared table chrome ──────────────────────────────────────────────────────
function TableCard({ children, toolbar }) {
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, overflow: 'hidden' }}>
      {toolbar && (
        <div style={{ padding: '14px 18px', borderBottom: `1px solid ${T.border}` }}>
          {toolbar}
        </div>
      )}
      <div style={{ overflowX: 'auto' }}>
        {children}
      </div>
    </div>
  );
}

function Th({ children, style, sortKey, currentSort, sortDir, onSort }) {
  const active = sortKey && currentSort === sortKey;
  return (
    <th
      onClick={sortKey && onSort ? () => onSort(sortKey) : undefined}
      style={{
        padding: '10px 16px',
        textAlign: 'left',
        fontFamily: 'Space Mono, monospace',
        fontSize: 9,
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        color: active ? T.accent : T.textMuted,
        fontWeight: active ? 700 : 400,
        borderBottom: `1px solid ${T.border}`,
        whiteSpace: 'nowrap',
        background: T.surfaceHigh,
        cursor: sortKey ? 'pointer' : 'default',
        userSelect: 'none',
        transition: 'color 0.15s',
        ...style,
      }}
    >
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        {children}
        {sortKey && (
          <span style={{ fontSize: 9, opacity: active ? 1 : 0.3 }}>
            {active ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}
          </span>
        )}
      </span>
    </th>
  );
}

function Td({ children, style }) {
  return (
    <td style={{ padding: '11px 16px', borderBottom: `1px solid ${T.border}`, ...style }}>
      {children}
    </td>
  );
}

function Pagination({ page, totalPages, totalCount, onPrev, onNext, pageSize, onPageSize }) {
  if (totalPages <= 1 && !onPageSize) return null;
  return (
    <div style={{ padding: '12px 18px', borderTop: `1px solid ${T.border}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
        <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted }}>
          Page {page} / {totalPages || 1} · {totalCount} records
        </span>
        {onPageSize && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>Show:</span>
            {[10, 20, 50].map(n => (
              <button
                key={n}
                onClick={() => onPageSize(n)}
                style={{
                  background: pageSize === n ? T.accent + '22' : 'transparent',
                  border: `1px solid ${pageSize === n ? T.accent + '60' : T.border}`,
                  borderRadius: 3,
                  padding: '2px 8px',
                  fontFamily: 'Space Mono, monospace',
                  fontSize: 8,
                  color: pageSize === n ? T.accent : T.textSub,
                  cursor: 'pointer',
                  transition: 'all 0.12s',
                }}
              >{n}</button>
            ))}
          </div>
        )}
      </div>
      {totalPages > 1 && (
        <div style={{ display: 'flex', gap: 6 }}>
          <button disabled={page === 1} onClick={onPrev} style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'transparent', border: `1px solid ${T.border}`, borderRadius: 4, padding: '5px 12px', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: page === 1 ? T.border : T.textSub, cursor: page === 1 ? 'not-allowed' : 'pointer' }}>
            <IcoPrev /> Prev
          </button>
          <button disabled={page === totalPages} onClick={onNext} style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'transparent', border: `1px solid ${T.border}`, borderRadius: 4, padding: '5px 12px', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: page === totalPages ? T.border : T.textSub, cursor: page === totalPages ? 'not-allowed' : 'pointer' }}>
            Next <IcoNext />
          </button>
        </div>
      )}
    </div>
  );
}

function SearchBox({ value, onChange, placeholder = 'Search…' }) {
  const [local, setLocal] = useState(value);
  const timerRef = useRef(null);

  useEffect(() => { setLocal(value); }, [value]);
  useEffect(() => () => clearTimeout(timerRef.current), []);

  const handleChange = (v) => {
    setLocal(v);
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => onChange(v), 300);
  };
  const handleClear = () => {
    clearTimeout(timerRef.current);
    setLocal('');
    onChange('');
  };

  return (
    <div style={{ position: 'relative' }}>
      <span style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: T.textSub }}>
        <IcoSearch />
      </span>
      <input
        value={local}
        onChange={e => handleChange(e.target.value)}
        placeholder={placeholder}
        style={{
          background: T.surfaceHigh,
          border: `1px solid ${T.border}`,
          borderRadius: 4,
          padding: '7px 12px 7px 32px',
          paddingRight: local ? 28 : 12,
          fontFamily: 'IBM Plex Sans, sans-serif',
          fontSize: 13,
          color: T.text,
          outline: 'none',
          width: '100%',
          maxWidth: 240,
          minWidth: 160,
        }}
      />
      {local && (
        <button
          onClick={handleClear}
          aria-label="Clear search"
          style={{
            position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)',
            background: 'none', border: 'none', cursor: 'pointer',
            color: T.textSub, fontSize: 16, padding: '0 2px',
            display: 'flex', alignItems: 'center', lineHeight: 1,
          }}
        >×</button>
      )}
    </div>
  );
}

function ActionBtn({ onClick, children, icon, variant = 'ghost', disabled, small }) {
  const base = {
    display: 'inline-flex', alignItems: 'center', gap: 5,
    border: `1px solid ${T.border}`,
    borderRadius: 4,
    padding: small ? '3px 9px' : '5px 12px',
    fontFamily: 'IBM Plex Sans, sans-serif',
    fontSize: small ? 10 : 11,
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 0.15s',
    opacity: disabled ? 0.5 : 1,
    whiteSpace: 'nowrap',
  };
  const styles = {
    ghost:   { background: 'transparent', color: T.textSub },
    accent:  { background: T.accent + '18', border: `1px solid ${T.accent}40`, color: T.accent },
    success: { background: T.success + '18', border: `1px solid ${T.success}40`, color: T.success },
    danger:  { background: T.danger + '18', border: `1px solid ${T.danger}40`, color: T.danger },
    warning: { background: T.warning + '18', border: `1px solid ${T.warning}40`, color: T.warning },
    solid:   { background: T.accent, border: `1px solid ${T.accent}`, color: '#fff' },
  };
  return (
    <button onClick={disabled ? undefined : onClick} style={{ ...base, ...styles[variant] }}>
      {icon} {children}
    </button>
  );
}

function fmtDate(dt) {
  if (!dt) return '—';
  return new Date(dt).toLocaleDateString('en-NA', { day: '2-digit', month: 'short', year: 'numeric' });
}
function fmtDateShort(dt) {
  if (!dt) return '—';
  return new Date(dt).toLocaleDateString('en-NA', { day: '2-digit', month: 'short' });
}
function timeAgo(date) {
  if (!date) return null;
  const diff = (Date.now() - new Date(date).getTime()) / 1000;
  if (diff < 10)   return 'just now';
  if (diff < 60)   return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}
function downloadCSV(rows, filename = 'export.csv') {
  if (!rows?.length) return;
  const headers = Object.keys(rows[0]);
  const escape  = (v) => {
    const s = (v == null ? '' : String(v)).replace(/"/g, '""');
    return /[,"\n]/.test(s) ? `"${s}"` : s;
  };
  const lines = [headers.join(','), ...rows.map(r => headers.map(h => escape(r[h])).join(','))];
  const blob  = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url   = URL.createObjectURL(blob);
  const a     = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ─── Score bar ────────────────────────────────────────────────────────────────
function ScoreBar({ score, max = 100, color }) {
  const pct = Math.min(100, ((score || 0) / max) * 100);
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 52, height: 5, background: T.border, borderRadius: 3, overflow: 'hidden', flexShrink: 0 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color || T.accent, borderRadius: 3 }} />
      </div>
      <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted }}>
        {score != null ? Number(score).toFixed(1) : '—'}
      </span>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// TAB: ANOMALY DETECTIONS
// ──────────────────────────────────────────────────────────────────────────────
function AnomaliesTab({ navigate, wsMessages }) {
  const { error: toastError, success: toastSuccess } = useToast();
  const [data, setData]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [err, setErr]           = useState(null);
  const [page, setPage]         = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [totalCount, setTotal]  = useState(0);
  const [search, setSearch]     = useState('');
  const [sevFilter, setSev]     = useState('ALL');
  const [typeFilter, setType]   = useState('ALL');
  const [verifiedFilter, setVer] = useState('ALL');
  const [hovered, setHovered]   = useState(null);
  const [verifying, setVerifying] = useState(null);
  const [sortBy, setSortBy]     = useState('detected_at');
  const [sortDir, setSortDir]   = useState('desc');
  const [lastFetched, setLastFetched] = useState(null);

  const handleSort = (key) => {
    if (sortBy === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(key); setSortDir('asc'); }
    setPage(1);
  };

  const fetch = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const params = { page, page_size: pageSize, ordering: sortDir === 'asc' ? sortBy : `-${sortBy}` };
      if (search) params.search = search;
      if (sevFilter !== 'ALL') params.severity = sevFilter;
      if (typeFilter !== 'ALL') params.anomaly_type = typeFilter;
      if (verifiedFilter === 'VERIFIED') params.is_verified = true;
      if (verifiedFilter === 'UNVERIFIED') params.is_verified = false;
      if (verifiedFilter === 'FALSE_POS') params.is_false_positive = true;
      const res = await surveillanceApi.listAnomalies(params);
      setData(res.data.results ?? res.data);
      setTotal(res.data.count ?? 0);
      setLastFetched(new Date());
    } catch (e) { const m = extractError(e); setErr(m); toastError(m); }
    finally { setLoading(false); }
  }, [page, pageSize, search, sevFilter, typeFilter, verifiedFilter, sortBy, sortDir]);

  useEffect(() => { fetch(); }, [fetch]);
  useEffect(() => { setPage(1); }, [search, sevFilter, typeFilter, verifiedFilter, pageSize]);

  // WS auto-refresh
  useEffect(() => {
    const last = wsMessages[wsMessages.length - 1];
    if (last?.type === 'anomaly') fetch();
  }, [wsMessages]);

  const handleVerify = async (id, isVerified, isFalsePos) => {
    setVerifying(id);
    try {
      await surveillanceApi.confirmAnomaly(id);
      toastSuccess('Anomaly verified');
      fetch();
    } catch (e) { toastError(extractError(e)); }
    finally { setVerifying(null); }
  };

  const handleDismiss = async (id) => {
    setVerifying(id);
    try {
      await surveillanceApi.dismissAnomaly(id, { is_false_positive: true, notes: 'Dismissed via UI' });
      toastSuccess('Anomaly dismissed as false positive');
      fetch();
    } catch (e) { toastError(extractError(e)); }
    finally { setVerifying(null); }
  };

  const handleRunDetection = async () => {
    try {
      await surveillanceApi.runAnomalyDetection({});
      toastSuccess('Anomaly detection queued');
    } catch (e) { toastError(extractError(e)); }
  };

  const totalPages = Math.ceil(totalCount / pageSize);
  const hasFilters = !!search || sevFilter !== 'ALL' || typeFilter !== 'ALL' || verifiedFilter !== 'ALL';
  const resetFilters = () => { setSearch(''); setSev('ALL'); setType('ALL'); setVer('ALL'); };
  const handleExport = () => downloadCSV(data.map(a => ({
    disease: a.disease_name, code: a.disease_code, type: a.anomaly_type,
    severity: a.severity, location: a.location_name,
    expected: a.expected_cases, actual: a.actual_cases,
    confidence: a.confidence_score, detected: fmtDate(a.detected_at),
    status: a.is_false_positive ? 'false_pos' : a.is_verified ? 'verified' : 'pending',
  })), 'anomalies.csv');

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <SectionHeader title="ANOMALY DETECTIONS" count={totalCount} />
          {lastFetched && <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>Updated {timeAgo(lastFetched)}</span>}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <ActionBtn onClick={handleRunDetection} icon={<IcoRun />} variant="accent">Run Detection</ActionBtn>
          <ActionBtn onClick={fetch} icon={<IcoRefresh />}>Refresh</ActionBtn>
          <ActionBtn onClick={handleExport} icon={<IcoDownload />}>Export</ActionBtn>
          {hasFilters && <ActionBtn onClick={resetFilters}>Clear filters ×</ActionBtn>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <SearchBox value={search} onChange={setSearch} placeholder="Search diseases…" />
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>Severity:</span>
          {['ALL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(s => (
            <FilterPill key={s} label={s === 'ALL' ? 'All' : s} active={sevFilter === s}
              onClick={() => setSev(s)} color={s !== 'ALL' ? SEVERITY_CFG[s]?.color : T.accent} />
          ))}
        </div>
        <div style={{ width: 1, height: 14, background: T.border }} />
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>Type:</span>
          {['ALL', ...Object.keys(ANOMALY_TYPE_LABELS)].map(t => (
            <FilterPill key={t} label={t === 'ALL' ? 'All' : ANOMALY_TYPE_LABELS[t]} active={typeFilter === t} onClick={() => setType(t)} />
          ))}
        </div>
        <div style={{ width: 1, height: 14, background: T.border }} />
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>Status:</span>
          {[['ALL','All'], ['UNVERIFIED','Unverified'], ['VERIFIED','Verified'], ['FALSE_POS','False Pos']].map(([k, l]) => (
            <FilterPill key={k} label={l} active={verifiedFilter === k} onClick={() => setVer(k)} />
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <TableCard toolbar={toolbar}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <Th sortKey="disease_name" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Disease</Th>
            <Th>Type</Th>
            <Th sortKey="severity" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Sev</Th>
            <Th>Location</Th>
            <Th sortKey="actual_cases" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Expected vs Actual</Th>
            <Th sortKey="confidence_score" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Confidence</Th>
            <Th sortKey="detected_at" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Detected</Th>
            <Th>Status</Th>
            <Th></Th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 8 }).map((_, i) => <ShimmerRow key={i} cols={9} />)
            : err
              ? <tr><td colSpan={9}><ErrorState msg={err} onRetry={fetch} /></td></tr>
              : data.length === 0
                ? <tr><td colSpan={9}><EmptyState msg="No anomalies for current filters." /></td></tr>
                : data.map(a => {
                  const sev = SEVERITY_CFG[a.severity] || { color: T.textSub, label: a.severity };
                  const isHov = hovered === a.id;
                  return (
                    <tr key={a.id}
                      onMouseEnter={() => setHovered(a.id)}
                      onMouseLeave={() => setHovered(null)}
                      onClick={() => navigate(`/dashboard/surveillance/${a.id}`)}
                      style={{ background: isHov ? 'rgba(255,255,255,0.02)' : 'transparent', cursor: 'pointer', transition: 'background 0.1s' }}
                    >
                      <Td>
                        <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text, fontWeight: 500 }}>
                          {a.disease_name || '—'}
                        </div>
                        <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, marginTop: 2 }}>
                          {a.disease_code}
                        </div>
                      </Td>
                      <Td><Badge label={ANOMALY_TYPE_LABELS[a.anomaly_type] || a.anomaly_type} color={T.accent} /></Td>
                      <Td><Badge label={sev.label} color={sev.color} /></Td>
                      <Td style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>{a.location_name || '—'}</Td>
                      <Td>
                        <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>
                          {a.expected_cases ?? '—'} → <span style={{ color: sev.color, fontWeight: 600 }}>{a.actual_cases ?? '—'}</span>
                        </div>
                        {a.percentage_increase != null && Number(a.percentage_increase) !== 0 && (
                          <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: sev.color }}>
                            +{Number(a.percentage_increase).toFixed(1)}%
                          </div>
                        )}
                      </Td>
                      <Td><ScoreBar score={a.confidence_score} max={100} color={sev.color} /></Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, whiteSpace: 'nowrap' }}>
                        {fmtDate(a.detected_at)}
                      </Td>
                      <Td>
                        {a.is_false_positive
                          ? <Badge label="False Pos" color={T.textMuted} />
                          : a.is_verified
                            ? <Badge label="Verified" color={T.success} />
                            : <Badge label="Pending" color={T.warning} />
                        }
                      </Td>
                      <Td>
                        <div style={{ display: 'flex', gap: 5 }} onClick={e => e.stopPropagation()}>
                          <ActionBtn onClick={() => navigate(`/dashboard/surveillance/${a.id}`)} icon={<IcoEye />}>View</ActionBtn>
                          {!a.is_verified && !a.is_false_positive && (
                            <>
                              <ActionBtn
                                onClick={() => handleVerify(a.id)}
                                icon={<IcoCheck />}
                                variant="success"
                                disabled={verifying === a.id}
                              >Confirm</ActionBtn>
                              <ActionBtn
                                onClick={() => handleDismiss(a.id)}
                                icon={<IcoX />}
                                variant="danger"
                                disabled={verifying === a.id}
                              >Dismiss</ActionBtn>
                            </>
                          )}
                        </div>
                      </Td>
                    </tr>
                  );
                })
          }
        </tbody>
      </table>
      <Pagination page={page} totalPages={totalPages} totalCount={totalCount}
        onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)}
        pageSize={pageSize} onPageSize={(n) => { setPageSize(n); setPage(1); }} />
    </TableCard>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// TAB: CASE CLUSTERS
// ──────────────────────────────────────────────────────────────────────────────
function ClustersTab({ navigate }) {
  const { error: toastError } = useToast();
  const [data, setData]        = useState([]);
  const [loading, setLoading]  = useState(true);
  const [err, setErr]          = useState(null);
  const [page, setPage]        = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [totalCount, setTotal] = useState(0);
  const [search, setSearch]    = useState('');
  const [activeFilter, setActive] = useState('ALL');
  const [hovered, setHovered]  = useState(null);
  const [sortBy, setSortBy]    = useState('start_date');
  const [sortDir, setSortDir]  = useState('desc');
  const [lastFetched, setLastFetched] = useState(null);

  const handleSort = (key) => {
    if (sortBy === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(key); setSortDir('asc'); }
    setPage(1);
  };

  const fetch = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const params = { page, page_size: pageSize, ordering: sortDir === 'asc' ? sortBy : `-${sortBy}` };
      if (search) params.search = search;
      if (activeFilter === 'ACTIVE') params.is_active = true;
      if (activeFilter === 'INACTIVE') params.is_active = false;
      const res = await surveillanceApi.listClusters(params);
      setData(res.data.results ?? res.data);
      setTotal(res.data.count ?? 0);
      setLastFetched(new Date());
    } catch (e) { const m = extractError(e); setErr(m); toastError(m); }
    finally { setLoading(false); }
  }, [page, pageSize, search, activeFilter, sortBy, sortDir]);

  useEffect(() => { fetch(); }, [fetch]);
  useEffect(() => { setPage(1); }, [search, activeFilter, pageSize]);

  const totalPages = Math.ceil(totalCount / pageSize);
  const hasFilters = !!search || activeFilter !== 'ALL';
  const resetFilters = () => { setSearch(''); setActive('ALL'); };
  const handleExport = () => downloadCSV(data.map(c => ({
    name: c.name, disease: c.disease_name, location: c.location_name,
    cases: c.case_count, attack_rate: c.attack_rate, radius_km: c.radius_km,
    algorithm: c.detection_algorithm, start: fmtDate(c.start_date), end: fmtDate(c.end_date),
    status: c.is_active ? 'active' : 'closed',
  })), 'clusters.csv');

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <SectionHeader title="CASE CLUSTERS" count={totalCount} />
          {lastFetched && <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>Updated {timeAgo(lastFetched)}</span>}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <ActionBtn onClick={fetch} icon={<IcoRefresh />}>Refresh</ActionBtn>
          <ActionBtn onClick={handleExport} icon={<IcoDownload />}>Export</ActionBtn>
          {hasFilters && <ActionBtn onClick={resetFilters}>Clear filters ×</ActionBtn>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <SearchBox value={search} onChange={setSearch} placeholder="Search clusters…" />
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>Status:</span>
          {[['ALL','All'], ['ACTIVE','Active'], ['INACTIVE','Inactive']].map(([k, l]) => (
            <FilterPill key={k} label={l} active={activeFilter === k} onClick={() => setActive(k)}
              color={k === 'ACTIVE' ? T.success : k === 'INACTIVE' ? T.textMuted : T.accent} />
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <TableCard toolbar={toolbar}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <Th sortKey="name" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Cluster Name</Th>
            <Th sortKey="disease_name" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Disease</Th>
            <Th>Location</Th>
            <Th sortKey="case_count" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Cases</Th>
            <Th>Attack Rate</Th>
            <Th>Radius</Th>
            <Th>Algorithm</Th>
            <Th sortKey="start_date" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Period</Th>
            <Th>Status</Th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 6 }).map((_, i) => <ShimmerRow key={i} cols={9} />)
            : err
              ? <tr><td colSpan={9}><ErrorState msg={err} onRetry={fetch} /></td></tr>
              : data.length === 0
                ? <tr><td colSpan={9}><EmptyState msg="No case clusters found." /></td></tr>
                : data.map(c => (
                  <tr key={c.id}
                    onMouseEnter={() => setHovered(c.id)}
                    onMouseLeave={() => setHovered(null)}
                    style={{ background: hovered === c.id ? 'rgba(255,255,255,0.02)' : 'transparent', transition: 'background 0.1s' }}
                  >
                    <Td>
                      <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text, fontWeight: 500 }}>{c.name}</div>
                    </Td>
                    <Td>
                      <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>{c.disease_name}</div>
                      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>{c.disease_code}</div>
                    </Td>
                    <Td style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>{c.location_name || '—'}</Td>
                    <Td>
                      <span style={{
                        fontFamily: 'Bebas Neue, sans-serif',
                        fontSize: 20,
                        color: (c.case_count || 0) > 50 ? T.danger : (c.case_count || 0) > 20 ? T.warning : T.success,
                      }}>{c.case_count ?? '—'}</span>
                    </Td>
                    <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>
                      {c.attack_rate != null ? `${Number(c.attack_rate).toFixed(2)}%` : '—'}
                    </Td>
                    <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>
                      {c.radius_km != null ? `${Number(c.radius_km).toFixed(1)} km` : '—'}
                    </Td>
                    <Td><Badge label={c.detection_algorithm || 'SaTScan'} color={T.accent} /></Td>
                    <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, whiteSpace: 'nowrap' }}>
                      {fmtDateShort(c.start_date)}{c.end_date ? ` → ${fmtDateShort(c.end_date)}` : ' → ongoing'}
                    </Td>
                    <Td>
                      <Badge label={c.is_active ? 'Active' : 'Closed'} color={c.is_active ? T.success : T.textMuted} />
                    </Td>
                  </tr>
                ))
          }
        </tbody>
      </table>
      <Pagination page={page} totalPages={totalPages} totalCount={totalCount}
        onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)}
        pageSize={pageSize} onPageSize={(n) => { setPageSize(n); setPage(1); }} />
    </TableCard>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// TAB: HOTSPOTS
// ──────────────────────────────────────────────────────────────────────────────
function HotspotsTab() {
  const { error: toastError } = useToast();
  const [data, setData]        = useState([]);
  const [loading, setLoading]  = useState(true);
  const [err, setErr]          = useState(null);
  const [page, setPage]        = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [totalCount, setTotal] = useState(0);
  const [riskFilter, setRisk]  = useState('ALL');
  const [hovered, setHovered]  = useState(null);
  const [sortBy, setSortBy]    = useState('case_count');
  const [sortDir, setSortDir]  = useState('desc');
  const [lastFetched, setLastFetched] = useState(null);

  const handleSort = (key) => {
    if (sortBy === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(key); setSortDir('asc'); }
    setPage(1);
  };

  const fetch = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const params = { page, page_size: pageSize, is_active: true, ordering: sortDir === 'asc' ? sortBy : `-${sortBy}` };
      if (riskFilter !== 'ALL') params.risk_level = riskFilter;
      const res = await surveillanceApi.listHotspots(params);
      setData(res.data.results ?? res.data);
      setTotal(res.data.count ?? 0);
      setLastFetched(new Date());
    } catch (e) { const m = extractError(e); setErr(m); toastError(m); }
    finally { setLoading(false); }
  }, [page, pageSize, riskFilter, sortBy, sortDir]);

  useEffect(() => { fetch(); }, [fetch]);
  useEffect(() => { setPage(1); }, [riskFilter, pageSize]);
  const totalPages = Math.ceil(totalCount / pageSize);
  const hasFilters = riskFilter !== 'ALL';
  const resetFilters = () => setRisk('ALL');
  const handleExport = () => downloadCSV(data.map(h => ({
    location: h.location_name, disease: h.disease_name, code: h.disease_code,
    risk: h.risk_level, cases: h.case_count, incidence_rate: h.incidence_rate,
    gi_statistic: h.gi_statistic, z_score: h.z_score, radius_km: h.radius_km,
    lat: h.latitude, lng: h.longitude, start: fmtDate(h.start_date),
  })), 'hotspots.csv');

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <SectionHeader title="GEOGRAPHIC HOTSPOTS" count={totalCount} />
          {lastFetched && <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>Updated {timeAgo(lastFetched)}</span>}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <ActionBtn onClick={fetch} icon={<IcoRefresh />}>Refresh</ActionBtn>
          <ActionBtn onClick={handleExport} icon={<IcoDownload />}>Export</ActionBtn>
          {hasFilters && <ActionBtn onClick={resetFilters}>Clear filters ×</ActionBtn>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>Risk:</span>
        {['ALL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map(r => (
          <FilterPill key={r} label={r === 'ALL' ? 'All' : r} active={riskFilter === r}
            onClick={() => setRisk(r)} color={r !== 'ALL' ? RISK_LEVEL_CFG[r]?.color : T.accent} />
        ))}
      </div>
    </div>
  );

  return (
    <TableCard toolbar={toolbar}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <Th sortKey="location_name" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Location</Th>
            <Th sortKey="disease_name" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Disease</Th>
            <Th sortKey="risk_level" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Risk</Th>
            <Th sortKey="case_count" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Cases</Th>
            <Th sortKey="incidence_rate" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Incidence Rate</Th>
            <Th><abbr title="Getis-Ord Gi* spatial autocorrelation statistic and Z-score — measures geographic clustering intensity" style={{ textDecoration: 'underline dotted #6b7280', cursor: 'help' }}>Spatial Score</abbr></Th>
            <Th>Radius</Th>
            <Th>Coordinates</Th>
            <Th sortKey="start_date" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Period</Th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 6 }).map((_, i) => <ShimmerRow key={i} cols={9} />)
            : err
              ? <tr><td colSpan={9}><ErrorState msg={err} onRetry={fetch} /></td></tr>
              : data.length === 0
                ? <tr><td colSpan={9}><EmptyState msg="No active hotspots found." /></td></tr>
                : data.map(h => {
                  const rc = RISK_LEVEL_CFG[h.risk_level] || { color: T.textMuted };
                  return (
                    <tr key={h.id}
                      onMouseEnter={() => setHovered(h.id)}
                      onMouseLeave={() => setHovered(null)}
                      style={{ background: hovered === h.id ? 'rgba(255,255,255,0.02)' : 'transparent', transition: 'background 0.1s' }}
                    >
                      <Td>
                        <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text, fontWeight: 500 }}>{h.location_name || '—'}</div>
                      </Td>
                      <Td>
                        <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>{h.disease_name}</div>
                        <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>{h.disease_code}</div>
                      </Td>
                      <Td><Badge label={h.risk_level} color={rc.color} /></Td>
                      <Td>
                        <span style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 20, color: rc.color }}>{h.case_count ?? '—'}</span>
                      </Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>
                        {h.incidence_rate != null ? Number(h.incidence_rate).toFixed(2) : '—'}
                      </Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>
                        {h.gi_statistic != null ? Number(h.gi_statistic).toFixed(3) : '—'}
                        {h.z_score != null && <div style={{ fontSize: 8, color: T.textMuted }}>z={Number(h.z_score).toFixed(2)}</div>}
                      </Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>
                        {h.radius_km != null ? `${Number(h.radius_km).toFixed(1)} km` : '—'}
                      </Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted }}>
                        {h.latitude != null ? `${Number(h.latitude).toFixed(4)}, ${Number(h.longitude).toFixed(4)}` : '—'}
                      </Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, whiteSpace: 'nowrap' }}>
                        {fmtDateShort(h.start_date)}
                      </Td>
                    </tr>
                  );
                })
          }
        </tbody>
      </table>
      <Pagination page={page} totalPages={totalPages} totalCount={totalCount}
        onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)}
        pageSize={pageSize} onPageSize={(n) => { setPageSize(n); setPage(1); }} />
    </TableCard>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// TAB: DISEASE PROFILES
// ──────────────────────────────────────────────────────────────────────────────
function DiseasesTab() {
  const { error: toastError, success: toastSuccess } = useToast();
  const [data, setData]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr]         = useState(null);
  const [page, setPage]       = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [totalCount, setTotal]= useState(0);
  const [search, setSearch]   = useState('');
  const [notif, setNotif]     = useState('ALL');
  const [hovered, setHovered] = useState(null);
  const [sortBy, setSortBy]   = useState('disease_name');
  const [sortDir, setSortDir] = useState('asc');
  const [lastFetched, setLastFetched] = useState(null);

  const [formOpen, setFormOpen]     = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [form, setForm]             = useState({ disease_code:'', disease_name:'', category:'', alert_threshold:'', epidemic_threshold:'', incubation_period_min:'', incubation_period_max:'', is_notifiable:false, requires_laboratory_confirmation:false });
  const [saving, setSaving]         = useState(false);
  const [deleting, setDeleting]     = useState(null);

  const handleSort = (key) => {
    if (sortBy === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(key); setSortDir('asc'); }
    setPage(1);
  };

  const fetch = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const params = { page, page_size: pageSize, ordering: sortDir === 'asc' ? sortBy : `-${sortBy}` };
      if (search) params.search = search;
      if (notif === 'NOTIFIABLE') params.is_notifiable = true;
      if (notif === 'NON') params.is_notifiable = false;
      const res = await surveillanceApi.listDiseaseProfiles(params);
      setData(res.data.results ?? res.data);
      setTotal(res.data.count ?? 0);
      setLastFetched(new Date());
    } catch (e) { const m = extractError(e); setErr(m); toastError(m); }
    finally { setLoading(false); }
  }, [page, pageSize, search, notif, sortBy, sortDir]);

  useEffect(() => { fetch(); }, [fetch]);
  useEffect(() => { setPage(1); }, [search, notif, pageSize]);
  const totalPages = Math.ceil(totalCount / pageSize);
  const hasFilters = !!search || notif !== 'ALL';
  const resetFilters = () => { setSearch(''); setNotif('ALL'); };
  const handleExport = () => downloadCSV(data.map(d => ({
    code: d.disease_code, name: d.disease_name, category: d.category,
    alert_threshold: d.alert_threshold, epidemic_threshold: d.epidemic_threshold,
    incubation_min: d.incubation_period_min, incubation_max: d.incubation_period_max,
    notifiable: d.is_notifiable, lab_confirm: d.requires_laboratory_confirmation,
    status: d.is_active ? 'active' : 'inactive',
  })), 'diseases.csv');

  const openNew = () => {
    setEditTarget(null);
    setForm({ disease_code:'', disease_name:'', category:'', alert_threshold:'', epidemic_threshold:'', incubation_period_min:'', incubation_period_max:'', is_notifiable:false, requires_laboratory_confirmation:false });
    setFormOpen(true);
  };
  const openEdit = (d) => {
    setEditTarget(d);
    setForm({
      disease_code: d.disease_code, disease_name: d.disease_name, category: d.category || '',
      alert_threshold: d.alert_threshold ?? '', epidemic_threshold: d.epidemic_threshold ?? '',
      incubation_period_min: d.incubation_period_min ?? '', incubation_period_max: d.incubation_period_max ?? '',
      is_notifiable: d.is_notifiable ?? false, requires_laboratory_confirmation: d.requires_laboratory_confirmation ?? false,
    });
    setFormOpen(true);
  };
  const handleSave = async () => {
    if (!form.disease_code.trim() || !form.disease_name.trim()) { toastError('Code and Name are required'); return; }
    setSaving(true);
    try {
      const payload = {
        disease_code: form.disease_code.trim().toUpperCase(),
        disease_name: form.disease_name.trim(), category: form.category,
        alert_threshold: form.alert_threshold !== '' ? Number(form.alert_threshold) : null,
        epidemic_threshold: form.epidemic_threshold !== '' ? Number(form.epidemic_threshold) : null,
        incubation_period_min: form.incubation_period_min !== '' ? Number(form.incubation_period_min) : null,
        incubation_period_max: form.incubation_period_max !== '' ? Number(form.incubation_period_max) : null,
        is_notifiable: form.is_notifiable, requires_laboratory_confirmation: form.requires_laboratory_confirmation,
      };
      if (editTarget) {
        await surveillanceApi.updateDiseaseProfile(editTarget.id, payload);
        toastSuccess('Disease profile updated');
      } else {
        await surveillanceApi.createDiseaseProfile(payload);
        toastSuccess('Disease profile created');
      }
      setFormOpen(false);
      fetch();
    } catch (e) { toastError(extractError(e)); }
    finally { setSaving(false); }
  };
  const handleDelete = async (d) => {
    if (deleting !== d.id) { setDeleting(d.id); return; }
    try {
      await surveillanceApi.deleteDiseaseProfile(d.id);
      toastSuccess('Disease profile deleted');
      setDeleting(null);
      fetch();
    } catch (e) { toastError(extractError(e)); setDeleting(null); }
  };

  const setF = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const inpStyle = { background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '8px 10px', color: T.text, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, outline: 'none', width: '100%', boxSizing: 'border-box' };
  const lblStyle = { fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 };

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <SectionHeader title="DISEASE PROFILES" count={totalCount} />
          {lastFetched && <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>Updated {timeAgo(lastFetched)}</span>}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <ActionBtn onClick={openNew} variant="solid">+ New Disease</ActionBtn>
          <ActionBtn onClick={fetch} icon={<IcoRefresh />}>Refresh</ActionBtn>
          <ActionBtn onClick={handleExport} icon={<IcoDownload />}>Export</ActionBtn>
          {hasFilters && <ActionBtn onClick={resetFilters}>Clear filters ×</ActionBtn>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <SearchBox value={search} onChange={setSearch} placeholder="Search diseases…" />
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>Notification:</span>
          {[['ALL','All'], ['NOTIFIABLE','Notifiable'], ['NON','Non-notifiable']].map(([k, l]) => (
            <FilterPill key={k} label={l} active={notif === k} onClick={() => setNotif(k)}
              color={k === 'NOTIFIABLE' ? T.danger : T.accent} />
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <>
      {formOpen && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.65)', zIndex:1000, display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
          <div style={{ background:T.surface, border:`1px solid ${T.border}`, borderRadius:8, width:'100%', maxWidth:580, padding:28, maxHeight:'90vh', overflowY:'auto' }}>
            <div style={{ fontFamily:'Bebas Neue, sans-serif', fontSize:22, color:T.text, marginBottom:22, letterSpacing:'0.05em' }}>
              {editTarget ? 'EDIT DISEASE PROFILE' : 'NEW DISEASE PROFILE'}
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginBottom:14 }}>
              <div>
                <label style={lblStyle}>Disease Code *</label>
                <input style={inpStyle} value={form.disease_code} onChange={e => setF('disease_code', e.target.value.toUpperCase())} placeholder="e.g. CHOLERA" />
              </div>
              <div>
                <label style={lblStyle}>Category</label>
                <input style={inpStyle} value={form.category} onChange={e => setF('category', e.target.value)} placeholder="e.g. Gastrointestinal" />
              </div>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={lblStyle}>Disease Name *</label>
                <input style={inpStyle} value={form.disease_name} onChange={e => setF('disease_name', e.target.value)} placeholder="Full disease name" />
              </div>
              <div>
                <label style={lblStyle}>Alert Threshold (cases)</label>
                <input style={inpStyle} type="number" min="0" value={form.alert_threshold} onChange={e => setF('alert_threshold', e.target.value)} placeholder="e.g. 10" />
              </div>
              <div>
                <label style={lblStyle}>Epidemic Threshold (cases)</label>
                <input style={inpStyle} type="number" min="0" value={form.epidemic_threshold} onChange={e => setF('epidemic_threshold', e.target.value)} placeholder="e.g. 50" />
              </div>
              <div>
                <label style={lblStyle}>Incubation Min (days)</label>
                <input style={inpStyle} type="number" min="0" value={form.incubation_period_min} onChange={e => setF('incubation_period_min', e.target.value)} placeholder="e.g. 1" />
              </div>
              <div>
                <label style={lblStyle}>Incubation Max (days)</label>
                <input style={inpStyle} type="number" min="0" value={form.incubation_period_max} onChange={e => setF('incubation_period_max', e.target.value)} placeholder="e.g. 14" />
              </div>
              <div style={{ display:'flex', alignItems:'center', gap:10, paddingTop:10 }}>
                <input type="checkbox" id="notifiable" checked={form.is_notifiable} onChange={e => setF('is_notifiable', e.target.checked)} style={{ width:16, height:16, cursor:'pointer' }} />
                <label htmlFor="notifiable" style={{ ...lblStyle, marginBottom:0, cursor:'pointer' }}>Notifiable Disease</label>
              </div>
              <div style={{ display:'flex', alignItems:'center', gap:10, paddingTop:10 }}>
                <input type="checkbox" id="lab_req" checked={form.requires_laboratory_confirmation} onChange={e => setF('requires_laboratory_confirmation', e.target.checked)} style={{ width:16, height:16, cursor:'pointer' }} />
                <label htmlFor="lab_req" style={{ ...lblStyle, marginBottom:0, cursor:'pointer' }}>Requires Lab Confirmation</label>
              </div>
            </div>
            <div style={{ display:'flex', gap:10, justifyContent:'flex-end' }}>
              <ActionBtn onClick={() => setFormOpen(false)}>Cancel</ActionBtn>
              <ActionBtn variant="solid" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : editTarget ? 'Save Changes' : 'Create Profile'}
              </ActionBtn>
            </div>
          </div>
        </div>
      )}
      <TableCard toolbar={toolbar}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <Th sortKey="disease_code" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Code</Th>
              <Th sortKey="disease_name" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Disease Name</Th>
              <Th>Category</Th>
              <Th>Alert / Epidemic</Th>
              <Th>Incubation (days)</Th>
              <Th>Notifiable</Th>
              <Th>Lab Confirm</Th>
              <Th>Status</Th>
              <Th>Actions</Th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 6 }).map((_, i) => <ShimmerRow key={i} cols={9} />)
              : err
                ? <tr><td colSpan={9}><ErrorState msg={err} onRetry={fetch} /></td></tr>
                : data.length === 0
                  ? <tr><td colSpan={9}><EmptyState msg="No disease profiles found." /></td></tr>
                  : data.map(d => (
                    <tr key={d.id}
                      onMouseEnter={() => setHovered(d.id)}
                      onMouseLeave={() => setHovered(null)}
                      style={{ background: hovered === d.id ? 'rgba(255,255,255,0.02)' : 'transparent', transition: 'background 0.1s' }}
                    >
                      <Td><Badge label={d.disease_code} color={T.accent} /></Td>
                      <Td><div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text, fontWeight: 500 }}>{d.disease_name}</div></Td>
                      <Td style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>{d.category || '—'}</Td>
                      <Td>
                        <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>
                          <span style={{ color: T.warning }}>{d.alert_threshold}</span>
                          {' / '}
                          <span style={{ color: T.danger }}>{d.epidemic_threshold}</span>
                        </div>
                      </Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>
                        {d.incubation_period_min != null ? `${d.incubation_period_min}–${d.incubation_period_max ?? '?'}` : '—'}
                      </Td>
                      <Td><Badge label={d.is_notifiable ? 'Yes' : 'No'} color={d.is_notifiable ? T.danger : T.textMuted} /></Td>
                      <Td><Badge label={d.requires_laboratory_confirmation ? 'Required' : 'Optional'} color={d.requires_laboratory_confirmation ? T.warning : T.textMuted} /></Td>
                      <Td><Badge label={d.is_active ? 'Active' : 'Inactive'} color={d.is_active ? T.success : T.textMuted} /></Td>
                      <Td>
                        <div style={{ display:'flex', gap:5 }}>
                          <ActionBtn small onClick={() => openEdit(d)}>Edit</ActionBtn>
                          {deleting === d.id ? (
                            <>
                              <ActionBtn small variant="danger" onClick={() => handleDelete(d)}>Confirm</ActionBtn>
                              <ActionBtn small onClick={() => setDeleting(null)}>Cancel</ActionBtn>
                            </>
                          ) : (
                            <ActionBtn small variant="danger" onClick={() => handleDelete(d)}>Delete</ActionBtn>
                          )}
                        </div>
                      </Td>
                    </tr>
                  ))
            }
          </tbody>
        </table>
        <Pagination page={page} totalPages={totalPages} totalCount={totalCount}
          onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)}
          pageSize={pageSize} onPageSize={(n) => { setPageSize(n); setPage(1); }} />
      </TableCard>
    </>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// TAB: DATA SOURCES
// ──────────────────────────────────────────────────────────────────────────────
function DataSourcesTab() {
  const { error: toastError, success: toastSuccess } = useToast();
  const [data, setData]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [err, setErr]           = useState(null);
  const [page, setPage]         = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [totalCount, setTotal]  = useState(0);
  const [search, setSearch]     = useState('');
  const [typeFilter, setType]   = useState('ALL');
  const [activeFilter, setActive] = useState('ALL');
  const [hovered, setHovered]   = useState(null);
  const [syncing, setSyncing]   = useState(null);
  const [sortBy, setSortBy]     = useState('name');
  const [sortDir, setSortDir]   = useState('asc');
  const [lastFetched, setLastFetched] = useState(null);

  const [formOpen, setFormOpen]     = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [form, setForm]             = useState({ name:'', source_type:'HOSPITAL', sync_frequency:3600, contact_person:'', contact_email:'', description:'' });
  const [saving, setSaving]         = useState(false);
  const [deleting, setDeleting]     = useState(null);

  const handleSort = (key) => {
    if (sortBy === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(key); setSortDir('asc'); }
    setPage(1);
  };

  const fetch = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const params = { page, page_size: pageSize, ordering: sortDir === 'asc' ? sortBy : `-${sortBy}` };
      if (search) params.search = search;
      if (typeFilter !== 'ALL') params.source_type = typeFilter;
      if (activeFilter === 'ACTIVE') params.is_active = true;
      if (activeFilter === 'INACTIVE') params.is_active = false;
      const res = await surveillanceApi.listDataSources(params);
      setData(res.data.results ?? res.data);
      setTotal(res.data.count ?? 0);
      setLastFetched(new Date());
    } catch (e) { const m = extractError(e); setErr(m); toastError(m); }
    finally { setLoading(false); }
  }, [page, pageSize, search, typeFilter, activeFilter, sortBy, sortDir]);

  useEffect(() => { fetch(); }, [fetch]);
  useEffect(() => { setPage(1); }, [search, typeFilter, activeFilter, pageSize]);

  const handleSync = async (id, name) => {
    setSyncing(id);
    try {
      await surveillanceApi.syncDataSource(id);
      toastSuccess(`Sync queued for ${name}`);
    } catch (e) { toastError(extractError(e)); }
    finally { setSyncing(null); }
  };

  const openNew = () => {
    setEditTarget(null);
    setForm({ name:'', source_type:'HOSPITAL', sync_frequency:3600, contact_person:'', contact_email:'', description:'' });
    setFormOpen(true);
  };
  const openEdit = (s) => {
    setEditTarget(s);
    setForm({
      name: s.name, source_type: s.source_type, sync_frequency: s.sync_frequency ?? 3600,
      contact_person: s.contact_person ?? '', contact_email: s.contact_email ?? '', description: s.description ?? '',
    });
    setFormOpen(true);
  };
  const handleSave = async () => {
    if (!form.name.trim()) { toastError('Name is required'); return; }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(), source_type: form.source_type,
        sync_frequency: Number(form.sync_frequency) || 3600,
        contact_person: form.contact_person, contact_email: form.contact_email, description: form.description,
      };
      if (editTarget) {
        await surveillanceApi.updateDataSource(editTarget.id, payload);
        toastSuccess('Data source updated');
      } else {
        await surveillanceApi.createDataSource(payload);
        toastSuccess('Data source created');
      }
      setFormOpen(false);
      fetch();
    } catch (e) { toastError(extractError(e)); }
    finally { setSaving(false); }
  };
  const handleDelete = async (s) => {
    if (deleting !== s.id) { setDeleting(s.id); return; }
    try {
      await surveillanceApi.deleteDataSource(s.id);
      toastSuccess('Data source deleted');
      setDeleting(null);
      fetch();
    } catch (e) { toastError(extractError(e)); setDeleting(null); }
  };

  const totalPages = Math.ceil(totalCount / pageSize);
  const hasFilters = !!search || typeFilter !== 'ALL' || activeFilter !== 'ALL';
  const resetFilters = () => { setSearch(''); setType('ALL'); setActive('ALL'); };
  const handleExport = () => downloadCSV(data.map(s => ({
    name: s.name, type: s.source_type, location: s.location_name,
    last_sync: s.last_sync ? fmtDate(s.last_sync) : 'never',
    sync_frequency: s.sync_frequency, contact: s.contact_person,
    email: s.contact_email, status: s.is_active ? 'active' : 'inactive',
  })), 'data_sources.csv');

  const setF = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const inpStyle = { background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '8px 10px', color: T.text, fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, outline: 'none', width: '100%', boxSizing: 'border-box' };
  const lblStyle = { fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: 5 };

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <SectionHeader title="DATA SOURCES" count={totalCount} />
          {lastFetched && <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>Updated {timeAgo(lastFetched)}</span>}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <ActionBtn onClick={openNew} variant="solid">+ New Source</ActionBtn>
          <ActionBtn onClick={fetch} icon={<IcoRefresh />}>Refresh</ActionBtn>
          <ActionBtn onClick={handleExport} icon={<IcoDownload />}>Export</ActionBtn>
          {hasFilters && <ActionBtn onClick={resetFilters}>Clear filters ×</ActionBtn>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <SearchBox value={search} onChange={setSearch} placeholder="Search sources…" />
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>Type:</span>
          {['ALL', 'HOSPITAL', 'LABORATORY', 'DHIS2', 'SORMAS', 'EMR', 'LIS', 'API', 'MANUAL'].map(t => (
            <FilterPill key={t} label={t === 'ALL' ? 'All' : (SOURCE_TYPE_LABELS[t] || t)} active={typeFilter === t} onClick={() => setType(t)} />
          ))}
        </div>
        <div style={{ width: 1, height: 14, background: T.border }} />
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {[['ALL','All'], ['ACTIVE','Active'], ['INACTIVE','Inactive']].map(([k, l]) => (
            <FilterPill key={k} label={l} active={activeFilter === k} onClick={() => setActive(k)}
              color={k === 'ACTIVE' ? T.success : T.accent} />
          ))}
        </div>
      </div>
    </div>
  );

  const SOURCE_TYPES = ['HOSPITAL','LABORATORY','DHIS2','SORMAS','EMR','LIS','API','MANUAL'];

  return (
    <>
      {formOpen && (
        <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.65)', zIndex:1000, display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
          <div style={{ background:T.surface, border:`1px solid ${T.border}`, borderRadius:8, width:'100%', maxWidth:520, padding:28, maxHeight:'90vh', overflowY:'auto' }}>
            <div style={{ fontFamily:'Bebas Neue, sans-serif', fontSize:22, color:T.text, marginBottom:22, letterSpacing:'0.05em' }}>
              {editTarget ? 'EDIT DATA SOURCE' : 'NEW DATA SOURCE'}
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginBottom:14 }}>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={lblStyle}>Name *</label>
                <input style={inpStyle} value={form.name} onChange={e => setF('name', e.target.value)} placeholder="Source name" />
              </div>
              <div>
                <label style={lblStyle}>Source Type</label>
                <select style={inpStyle} value={form.source_type} onChange={e => setF('source_type', e.target.value)}>
                  {SOURCE_TYPES.map(t => <option key={t} value={t}>{SOURCE_TYPE_LABELS[t] || t}</option>)}
                </select>
              </div>
              <div>
                <label style={lblStyle}>Sync Frequency (seconds)</label>
                <input style={inpStyle} type="number" min="60" value={form.sync_frequency} onChange={e => setF('sync_frequency', e.target.value)} placeholder="3600" />
              </div>
              <div>
                <label style={lblStyle}>Contact Person</label>
                <input style={inpStyle} value={form.contact_person} onChange={e => setF('contact_person', e.target.value)} placeholder="Full name" />
              </div>
              <div>
                <label style={lblStyle}>Contact Email</label>
                <input style={inpStyle} type="email" value={form.contact_email} onChange={e => setF('contact_email', e.target.value)} placeholder="email@example.com" />
              </div>
              <div style={{ gridColumn:'1/-1' }}>
                <label style={lblStyle}>Description</label>
                <textarea style={{ ...inpStyle, minHeight:70, resize:'vertical' }} value={form.description} onChange={e => setF('description', e.target.value)} placeholder="Source description…" />
              </div>
            </div>
            <div style={{ display:'flex', gap:10, justifyContent:'flex-end' }}>
              <ActionBtn onClick={() => setFormOpen(false)}>Cancel</ActionBtn>
              <ActionBtn variant="solid" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving…' : editTarget ? 'Save Changes' : 'Create Source'}
              </ActionBtn>
            </div>
          </div>
        </div>
      )}
      <TableCard toolbar={toolbar}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <Th sortKey="name" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Name</Th>
              <Th sortKey="source_type" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Type</Th>
              <Th>Location</Th>
              <Th sortKey="last_sync" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Last Sync</Th>
              <Th>Freq (s)</Th>
              <Th>Contact</Th>
              <Th>Status</Th>
              <Th>Actions</Th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 6 }).map((_, i) => <ShimmerRow key={i} cols={8} />)
              : err
                ? <tr><td colSpan={8}><ErrorState msg={err} onRetry={fetch} /></td></tr>
                : data.length === 0
                  ? <tr><td colSpan={8}><EmptyState msg="No data sources found." /></td></tr>
                  : data.map(s => (
                    <tr key={s.id}
                      onMouseEnter={() => setHovered(s.id)}
                      onMouseLeave={() => setHovered(null)}
                      style={{ background: hovered === s.id ? 'rgba(255,255,255,0.02)' : 'transparent', transition: 'background 0.1s' }}
                    >
                      <Td><div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text, fontWeight: 500 }}>{s.name}</div></Td>
                      <Td><Badge label={SOURCE_TYPE_LABELS[s.source_type] || s.source_type} color={T.accent} /></Td>
                      <Td style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>{s.location_name || '—'}</Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, whiteSpace: 'nowrap' }}>
                        {s.last_sync ? fmtDate(s.last_sync) : 'Never'}
                      </Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textMuted }}>{s.sync_frequency ?? '—'}</Td>
                      <Td>
                        {s.contact_person
                          ? <div>
                              <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.text }}>{s.contact_person}</div>
                              {s.contact_email && <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>{s.contact_email}</div>}
                            </div>
                          : <span style={{ color: T.textMuted, fontSize: 12 }}>—</span>
                        }
                      </Td>
                      <Td><Badge label={s.is_active ? 'Active' : 'Inactive'} color={s.is_active ? T.success : T.textMuted} /></Td>
                      <Td onClick={e => e.stopPropagation()}>
                        <div style={{ display:'flex', gap:5 }}>
                          <ActionBtn small onClick={() => handleSync(s.id, s.name)} icon={<IcoSync />} variant="accent" disabled={syncing === s.id || !s.is_active}>
                            {syncing === s.id ? '…' : 'Sync'}
                          </ActionBtn>
                          <ActionBtn small onClick={() => openEdit(s)}>Edit</ActionBtn>
                          {deleting === s.id ? (
                            <>
                              <ActionBtn small variant="danger" onClick={() => handleDelete(s)}>Confirm</ActionBtn>
                              <ActionBtn small onClick={() => setDeleting(null)}>Cancel</ActionBtn>
                            </>
                          ) : (
                            <ActionBtn small variant="danger" onClick={() => handleDelete(s)}>Delete</ActionBtn>
                          )}
                        </div>
                      </Td>
                    </tr>
                  ))
            }
          </tbody>
        </table>
        <Pagination page={page} totalPages={totalPages} totalCount={totalCount}
          onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)}
          pageSize={pageSize} onPageSize={(n) => { setPageSize(n); setPage(1); }} />
      </TableCard>
    </>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// TAB: HEALTH DATA
// ──────────────────────────────────────────────────────────────────────────────
function HealthDataTab() {
  const { error: toastError } = useToast();
  const [data, setData]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr]         = useState(null);
  const [page, setPage]       = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [totalCount, setTotal]= useState(0);
  const [search, setSearch]   = useState('');
  const [typeFilter, setType] = useState('ALL');
  const [hovered, setHovered] = useState(null);
  const [sortBy, setSortBy]   = useState('date_recorded');
  const [sortDir, setSortDir] = useState('desc');
  const [lastFetched, setLastFetched] = useState(null);

  const DATA_TYPES = ['CASE', 'LAB_RESULT', 'SYMPTOM', 'ADMISSION', 'DEATH', 'VACCINATION', 'PHARMACY', 'SYNDROMIC'];

  const handleSort = (key) => {
    if (sortBy === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(key); setSortDir('asc'); }
    setPage(1);
  };

  const fetch = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const params = { page, page_size: pageSize, ordering: sortDir === 'asc' ? sortBy : `-${sortBy}` };
      if (search) params.search = search;
      if (typeFilter !== 'ALL') params.data_type = typeFilter;
      const res = await surveillanceApi.listHealthData(params);
      setData(res.data.results ?? res.data);
      setTotal(res.data.count ?? 0);
      setLastFetched(new Date());
    } catch (e) { const m = extractError(e); setErr(m); toastError(m); }
    finally { setLoading(false); }
  }, [page, pageSize, search, typeFilter, sortBy, sortDir]);

  useEffect(() => { fetch(); }, [fetch]);
  useEffect(() => { setPage(1); }, [search, typeFilter, pageSize]);
  const totalPages = Math.ceil(totalCount / pageSize);
  const hasFilters = !!search || typeFilter !== 'ALL';
  const resetFilters = () => { setSearch(''); setType('ALL'); };
  const handleExport = () => downloadCSV(data.map(h => ({
    type: h.data_type, disease: h.disease_name, code: h.disease_code,
    location: h.location_name, source: h.data_source_name,
    date_recorded: fmtDate(h.date_recorded), severity: h.severity,
    outcome: h.outcome, processed: h.processed ? 'yes' : 'no',
  })), 'health_data.csv');

  const DATA_TYPE_COLORS = {
    CASE: T.danger, LAB_RESULT: T.accent, SYMPTOM: T.warning,
    ADMISSION: T.purple, DEATH: '#6b7280', VACCINATION: T.success,
    PHARMACY: T.teal, SYNDROMIC: '#f97316',
  };

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <SectionHeader title="HEALTH DATA" count={totalCount} />
          {lastFetched && <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>Updated {timeAgo(lastFetched)}</span>}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <ActionBtn onClick={fetch} icon={<IcoRefresh />}>Refresh</ActionBtn>
          <ActionBtn onClick={handleExport} icon={<IcoDownload />}>Export</ActionBtn>
          {hasFilters && <ActionBtn onClick={resetFilters}>Clear filters ×</ActionBtn>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <SearchBox value={search} onChange={setSearch} placeholder="Search by disease…" />
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>Type:</span>
          <FilterPill label="All" active={typeFilter === 'ALL'} onClick={() => setType('ALL')} />
          {DATA_TYPES.map(t => (
            <FilterPill key={t} label={t.replace('_', ' ')} active={typeFilter === t} onClick={() => setType(t)}
              color={DATA_TYPE_COLORS[t]} />
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <TableCard toolbar={toolbar}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <Th sortKey="data_type" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Type</Th>
            <Th sortKey="disease_name" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Disease</Th>
            <Th>Location</Th>
            <Th>Source</Th>
            <Th sortKey="date_recorded" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Date Recorded</Th>
            <Th>Severity</Th>
            <Th>Outcome</Th>
            <Th>Processed</Th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 8 }).map((_, i) => <ShimmerRow key={i} cols={8} />)
            : err
              ? <tr><td colSpan={8}><ErrorState msg={err} onRetry={fetch} /></td></tr>
              : data.length === 0
                ? <tr><td colSpan={8}><EmptyState msg="No health data records found." /></td></tr>
                : data.map(h => (
                  <tr key={h.id}
                    onMouseEnter={() => setHovered(h.id)}
                    onMouseLeave={() => setHovered(null)}
                    style={{ background: hovered === h.id ? 'rgba(255,255,255,0.02)' : 'transparent', transition: 'background 0.1s' }}
                  >
                    <Td><Badge label={h.data_type?.replace('_', ' ')} color={DATA_TYPE_COLORS[h.data_type] || T.accent} /></Td>
                    <Td>
                      <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text }}>{h.disease_name}</div>
                      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>{h.disease_code}</div>
                    </Td>
                    <Td style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>{h.location_name || '—'}</Td>
                    <Td style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>{h.data_source_name || '—'}</Td>
                    <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, whiteSpace: 'nowrap' }}>
                      {fmtDate(h.date_recorded)}
                    </Td>
                    <Td>
                      {h.severity
                        ? <Badge label={h.severity} color={h.severity === 'CRITICAL' ? T.danger : h.severity === 'SEVERE' ? T.warning : T.success} />
                        : <span style={{ color: T.textMuted, fontSize: 12 }}>—</span>
                      }
                    </Td>
                    <Td style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>
                      {h.outcome || '—'}
                    </Td>
                    <Td>
                      <Badge label={h.processed ? 'Done' : 'Pending'} color={h.processed ? T.success : T.warning} />
                    </Td>
                  </tr>
                ))
          }
        </tbody>
      </table>
      <Pagination page={page} totalPages={totalPages} totalCount={totalCount}
        onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)}
        pageSize={pageSize} onPageSize={(n) => { setPageSize(n); setPage(1); }} />
    </TableCard>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// TAB: REPORTS
// ──────────────────────────────────────────────────────────────────────────────
function ReportsTab() {
  const { error: toastError, success: toastSuccess } = useToast();
  const [data, setData]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [err, setErr]           = useState(null);
  const [page, setPage]         = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [totalCount, setTotal]  = useState(0);
  const [typeFilter, setType]   = useState('ALL');
  const [pubFilter, setPub]     = useState('ALL');
  const [downloading, setDl]    = useState(null);
  const [hovered, setHovered]   = useState(null);
  const [sortBy, setSortBy]     = useState('generated_at');
  const [sortDir, setSortDir]   = useState('desc');
  const [lastFetched, setLastFetched] = useState(null);

  const REPORT_TYPES = ['DAILY', 'WEEKLY', 'MONTHLY', 'OUTBREAK', 'SPECIAL'];

  const handleSort = (key) => {
    if (sortBy === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(key); setSortDir('asc'); }
    setPage(1);
  };

  const fetch = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const params = { page, page_size: pageSize, ordering: sortDir === 'asc' ? sortBy : `-${sortBy}` };
      if (typeFilter !== 'ALL') params.report_type = typeFilter;
      if (pubFilter === 'PUBLISHED') params.is_published = true;
      if (pubFilter === 'DRAFT') params.is_published = false;
      const res = await surveillanceApi.listSurvReports(params);
      setData(res.data.results ?? res.data);
      setTotal(res.data.count ?? 0);
      setLastFetched(new Date());
    } catch (e) { const m = extractError(e); setErr(m); toastError(m); }
    finally { setLoading(false); }
  }, [page, pageSize, typeFilter, pubFilter, sortBy, sortDir]);

  useEffect(() => { fetch(); }, [fetch]);
  useEffect(() => { setPage(1); }, [typeFilter, pubFilter, pageSize]);

  const handleDownload = async (id, title) => {
    setDl(id);
    try {
      const res = await surveillanceApi.downloadSurvReport(id);
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a'); a.href = url; a.download = `${title}.pdf`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { toastError(extractError(e)); }
    finally { setDl(null); }
  };

  const totalPages = Math.ceil(totalCount / pageSize);
  const hasFilters = typeFilter !== 'ALL' || pubFilter !== 'ALL';
  const resetFilters = () => { setType('ALL'); setPub('ALL'); };
  const REPORT_TYPE_COLORS = { DAILY: T.accent, WEEKLY: T.teal, MONTHLY: T.purple, OUTBREAK: T.danger, SPECIAL: T.warning };
  const handleExport = () => downloadCSV(data.map(r => ({
    title: r.title, type: r.report_type, location: r.location_name,
    period: `${fmtDate(r.start_date)} - ${fmtDate(r.end_date)}`,
    total_cases: r.total_cases, new_cases: r.new_cases,
    anomalies: r.anomalies_detected, status: r.is_published ? 'published' : 'draft',
  })), 'reports.csv');

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <SectionHeader title="SURVEILLANCE REPORTS" count={totalCount} />
          {lastFetched && <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>Updated {timeAgo(lastFetched)}</span>}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <ActionBtn onClick={fetch} icon={<IcoRefresh />}>Refresh</ActionBtn>
          <ActionBtn onClick={handleExport} icon={<IcoDownload />}>Export</ActionBtn>
          {hasFilters && <ActionBtn onClick={resetFilters}>Clear filters ×</ActionBtn>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>Type:</span>
          <FilterPill label="All" active={typeFilter === 'ALL'} onClick={() => setType('ALL')} />
          {REPORT_TYPES.map(t => (
            <FilterPill key={t} label={t} active={typeFilter === t} onClick={() => setType(t)} color={REPORT_TYPE_COLORS[t]} />
          ))}
        </div>
        <div style={{ width: 1, height: 14, background: T.border }} />
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          {[['ALL','All'], ['PUBLISHED','Published'], ['DRAFT','Draft']].map(([k, l]) => (
            <FilterPill key={k} label={l} active={pubFilter === k} onClick={() => setPub(k)}
              color={k === 'PUBLISHED' ? T.success : T.accent} />
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <TableCard toolbar={toolbar}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <Th sortKey="title" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Title</Th>
            <Th sortKey="report_type" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Type</Th>
            <Th>Location</Th>
            <Th sortKey="start_date" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Period</Th>
            <Th sortKey="total_cases" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Cases (total/new)</Th>
            <Th sortKey="anomalies_detected" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Anomalies</Th>
            <Th>Status</Th>
            <Th></Th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 6 }).map((_, i) => <ShimmerRow key={i} cols={8} />)
            : err
              ? <tr><td colSpan={8}><ErrorState msg={err} onRetry={fetch} /></td></tr>
              : data.length === 0
                ? <tr><td colSpan={8}><EmptyState msg="No reports found." /></td></tr>
                : data.map(r => (
                  <tr key={r.id}
                    onMouseEnter={() => setHovered(r.id)}
                    onMouseLeave={() => setHovered(null)}
                    style={{ background: hovered === r.id ? 'rgba(255,255,255,0.02)' : 'transparent', transition: 'background 0.1s' }}
                  >
                    <Td>
                      <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text, fontWeight: 500, maxWidth: 260 }}>
                        {r.title}
                      </div>
                    </Td>
                    <Td><Badge label={r.report_type} color={REPORT_TYPE_COLORS[r.report_type] || T.accent} /></Td>
                    <Td style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>{r.location_name || '—'}</Td>
                    <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, whiteSpace: 'nowrap' }}>
                      {fmtDateShort(r.start_date)} → {fmtDateShort(r.end_date)}
                    </Td>
                    <Td>
                      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>
                        <span style={{ color: T.text }}>{r.total_cases ?? '—'}</span> / <span style={{ color: T.warning }}>{r.new_cases ?? '—'}</span>
                      </div>
                    </Td>
                    <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: r.anomalies_detected > 0 ? T.danger : T.textMuted }}>
                      {r.anomalies_detected ?? '—'}
                    </Td>
                    <Td>
                      <Badge label={r.is_published ? 'Published' : 'Draft'} color={r.is_published ? T.success : T.textMuted} />
                    </Td>
                    <Td onClick={e => e.stopPropagation()}>
                      {r.report_file && (
                        <ActionBtn
                          onClick={() => handleDownload(r.id, r.title)}
                          variant="accent"
                          disabled={downloading === r.id}
                        >
                          {downloading === r.id ? 'Downloading…' : '↓ PDF'}
                        </ActionBtn>
                      )}
                    </Td>
                  </tr>
                ))
          }
        </tbody>
      </table>
      <Pagination page={page} totalPages={totalPages} totalCount={totalCount}
        onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)}
        pageSize={pageSize} onPageSize={(n) => { setPageSize(n); setPage(1); }} />
    </TableCard>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// TAB: DATA QUALITY
// ──────────────────────────────────────────────────────────────────────────────
function QualityTab() {
  const { error: toastError } = useToast();
  const [data, setData]        = useState([]);
  const [loading, setLoading]  = useState(true);
  const [err, setErr]          = useState(null);
  const [page, setPage]        = useState(1);
  const [pageSize, setPageSize] = useState(PAGE_SIZE);
  const [totalCount, setTotal] = useState(0);
  const [typeFilter, setType]  = useState('ALL');
  const [statusFilter, setStat]= useState('ALL');
  const [hovered, setHovered]  = useState(null);
  const [sortBy, setSortBy]    = useState('check_date');
  const [sortDir, setSortDir]  = useState('desc');
  const [lastFetched, setLastFetched] = useState(null);

  const handleSort = (key) => {
    if (sortBy === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(key); setSortDir('asc'); }
    setPage(1);
  };

  const fetch = useCallback(async () => {
    setLoading(true); setErr(null);
    try {
      const params = { page, page_size: pageSize, ordering: sortDir === 'asc' ? sortBy : `-${sortBy}` };
      if (typeFilter !== 'ALL') params.check_type = typeFilter;
      if (statusFilter !== 'ALL') params.status = statusFilter;
      const res = await surveillanceApi.listDataQuality(params);
      setData(res.data.results ?? res.data);
      setTotal(res.data.count ?? 0);
      setLastFetched(new Date());
    } catch (e) { const m = extractError(e); setErr(m); toastError(m); }
    finally { setLoading(false); }
  }, [page, pageSize, typeFilter, statusFilter, sortBy, sortDir]);

  useEffect(() => { fetch(); }, [fetch]);
  useEffect(() => { setPage(1); }, [typeFilter, statusFilter, pageSize]);
  const totalPages = Math.ceil(totalCount / pageSize);
  const hasFilters = typeFilter !== 'ALL' || statusFilter !== 'ALL';
  const resetFilters = () => { setType('ALL'); setStat('ALL'); };
  const handleExport = () => downloadCSV(data.map(c => ({
    source: c.data_source_name, check_type: c.check_type,
    date: fmtDate(c.check_date), checked: c.records_checked,
    passed: c.records_passed, failed: c.records_failed,
    pass_rate: c.pass_rate, status: c.status,
  })), 'quality_checks.csv');

  const toolbar = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <SectionHeader title="DATA QUALITY CHECKS" count={totalCount} />
          {lastFetched && <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>Updated {timeAgo(lastFetched)}</span>}
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <ActionBtn onClick={fetch} icon={<IcoRefresh />}>Refresh</ActionBtn>
          <ActionBtn onClick={handleExport} icon={<IcoDownload />}>Export</ActionBtn>
          {hasFilters && <ActionBtn onClick={resetFilters}>Clear filters ×</ActionBtn>}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>Check:</span>
          <FilterPill label="All" active={typeFilter === 'ALL'} onClick={() => setType('ALL')} />
          {Object.entries(CHECK_TYPE_LABELS).map(([k, l]) => (
            <FilterPill key={k} label={l} active={typeFilter === k} onClick={() => setType(k)} />
          ))}
        </div>
        <div style={{ width: 1, height: 14, background: T.border }} />
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <span style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase' }}>Status:</span>
          {[['ALL','All'], ['COMPLETED','Completed'], ['FAILED','Failed'], ['PARTIAL','Partial']].map(([k, l]) => (
            <FilterPill key={k} label={l} active={statusFilter === k} onClick={() => setStat(k)}
              color={k === 'COMPLETED' ? T.success : k === 'FAILED' ? T.danger : T.accent} />
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <TableCard toolbar={toolbar}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <Th sortKey="data_source_name" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Data Source</Th>
            <Th sortKey="check_type" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Check Type</Th>
            <Th sortKey="check_date" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Date</Th>
            <Th sortKey="records_checked" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Checked</Th>
            <Th>Passed</Th>
            <Th>Failed</Th>
            <Th sortKey="pass_rate" currentSort={sortBy} sortDir={sortDir} onSort={handleSort}>Pass Rate</Th>
            <Th>Status</Th>
          </tr>
        </thead>
        <tbody>
          {loading
            ? Array.from({ length: 6 }).map((_, i) => <ShimmerRow key={i} cols={8} />)
            : err
              ? <tr><td colSpan={8}><ErrorState msg={err} onRetry={fetch} /></td></tr>
              : data.length === 0
                ? <tr><td colSpan={8}><EmptyState msg="No quality checks found." /></td></tr>
                : data.map(c => {
                  const passRate = Number(c.pass_rate || 0);
                  const rateColor = passRate >= 95 ? T.success : passRate >= 80 ? T.warning : T.danger;
                  return (
                    <tr key={c.id}
                      onMouseEnter={() => setHovered(c.id)}
                      onMouseLeave={() => setHovered(null)}
                      style={{ background: hovered === c.id ? 'rgba(255,255,255,0.02)' : 'transparent', transition: 'background 0.1s' }}
                    >
                      <Td>
                        <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.text }}>{c.data_source_name || '—'}</div>
                      </Td>
                      <Td><Badge label={CHECK_TYPE_LABELS[c.check_type] || c.check_type} color={T.accent} /></Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, color: T.textMuted, whiteSpace: 'nowrap' }}>
                        {fmtDate(c.check_date)}
                      </Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.textSub }}>{c.records_checked ?? '—'}</Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: T.success }}>{c.records_passed ?? '—'}</Td>
                      <Td style={{ fontFamily: 'Space Mono, monospace', fontSize: 10, color: c.records_failed > 0 ? T.danger : T.textMuted }}>{c.records_failed ?? '—'}</Td>
                      <Td>
                        <ScoreBar score={passRate} max={100} color={rateColor} />
                      </Td>
                      <Td>
                        <Badge
                          label={c.status}
                          color={c.status === 'COMPLETED' ? T.success : c.status === 'FAILED' ? T.danger : T.warning}
                        />
                      </Td>
                    </tr>
                  );
                })
          }
        </tbody>
      </table>
      <Pagination page={page} totalPages={totalPages} totalCount={totalCount}
        onPrev={() => setPage(p => p - 1)} onNext={() => setPage(p => p + 1)}
        pageSize={pageSize} onPageSize={(n) => { setPageSize(n); setPage(1); }} />
    </TableCard>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// LIVE FEED SIDEBAR
// ──────────────────────────────────────────────────────────────────────────────
function LiveFeed({ wsMessages }) {
  const msgs = wsMessages.slice(-8).reverse();
  const typeColors = { anomaly: T.danger, cluster: T.warning, hotspot: T.purple };

  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '14px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: T.success, boxShadow: `0 0 8px ${T.success}`, animation: 'pulse 2s infinite' }} />
        <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 13, color: T.text, letterSpacing: '0.05em' }}>LIVE FEED</div>
      </div>
      {msgs.length === 0
        ? <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: T.textMuted }}>Awaiting events…</div>
        : msgs.map((m, i) => (
          <div key={i} style={{ padding: '7px 0', borderBottom: i < msgs.length - 1 ? `1px solid ${T.border}` : 'none' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 5, height: 5, borderRadius: '50%', background: typeColors[m.type] || T.textMuted, flexShrink: 0 }} />
              <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: T.text }}>
                {m.type === 'anomaly' ? `${m.severity} anomaly: ${m.disease}` :
                 m.type === 'cluster' ? `Cluster: ${m.name}` :
                 m.type === 'hotspot' ? `${m.risk_level} hotspot: ${m.disease}` :
                 m.event_type || 'event'}
              </div>
            </div>
            {m.location && (
              <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, marginTop: 2, marginLeft: 11 }}>
                📍 {m.location}
              </div>
            )}
            <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, marginTop: 1, marginLeft: 11 }}>
              {m.timestamp ? new Date(m.timestamp).toLocaleTimeString('en-NA') : 'now'}
            </div>
          </div>
        ))
      }
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// MAIN EXPORT
// ──────────────────────────────────────────────────────────────────────────────
export default function Surveillance() {
  const navigate = useNavigate();
  const { data: wsMessages } = useAlertStream();

  const [activeTab, setActiveTab]     = useState('anomalies');
  const [stats, setStats]             = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const tabsRef = useRef(null);

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const res = await surveillanceApi.surveillanceDashboard();
      setStats(res.data);
    } catch (_) {}
    finally { setStatsLoading(false); }
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);

  const STAT_CARDS = [
    { label: 'Active Anomalies', value: stats?.active_anomalies, color: T.danger,   sub: 'Unverified' },
    { label: 'Case Clusters',    value: stats?.active_clusters,  color: T.warning,  sub: 'Active' },
    { label: 'Hotspots',         value: stats?.active_hotspots,  color: T.purple,   sub: 'Geographic' },
    { label: 'Cases Today',      value: stats?.total_cases_today,color: T.accent,   sub: 'New records' },
    { label: 'Cases This Week',  value: stats?.total_cases_week, color: T.teal,     sub: '7-day total' },
  ];

  return (
    <div style={{ minHeight: '100vh', background: T.bg }}>
      <style>{`
        @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        * { box-sizing: border-box; }
        input::placeholder { color: #6b7280; }
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: #111827; }
        ::-webkit-scrollbar-thumb { background: #1f2937; border-radius: 3px; }
        .surv-tabs-wrap { position: relative; }
        .surv-tabs-wrap::after {
          content: '';
          position: absolute;
          right: 0; top: 0; bottom: 1px;
          width: 48px;
          background: linear-gradient(to right, transparent, #0a0f1e);
          pointer-events: none;
        }
      `}</style>

      <div style={{ padding: 'clamp(16px, 3vw, 28px)' }}>

        {/* ── Header ── */}
        <motion.div {...fadeUp(0)} style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 9, letterSpacing: '0.2em', color: T.accent, textTransform: 'uppercase', marginBottom: 6 }}>
                Intelligence / Surveillance
              </div>
              <h1 style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 'clamp(28px, 5vw, 44px)', color: T.text, margin: 0, letterSpacing: '0.04em', lineHeight: 1 }}>
                SURVEILLANCE
              </h1>
              <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.textSub, marginTop: 4 }}>
                Anomaly detection · Case clusters · Hotspots · Health data · Reporting
              </div>
            </div>
            <button
              onClick={fetchStats}
              style={{ display: 'flex', alignItems: 'center', gap: 7, background: 'transparent', border: `1px solid ${T.border}`, borderRadius: 4, padding: '8px 16px', fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 13, color: T.textSub, cursor: 'pointer' }}
              onMouseEnter={e => e.currentTarget.style.color = T.text}
              onMouseLeave={e => e.currentTarget.style.color = T.textSub}
            >
              <IcoRefresh /> Refresh Stats
            </button>
          </div>
        </motion.div>

        {/* ── Stat cards ── */}
        <motion.div {...fadeUp(0.05)} style={{ display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' }}>
          {STAT_CARDS.map(c => (
            <StatCard key={c.label} {...c} loading={statsLoading} />
          ))}
        </motion.div>

        {/* Trending diseases inline */}
        {stats?.trending_diseases?.length > 0 && (
          <motion.div {...fadeUp(0.08)} style={{ marginBottom: 20 }}>
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '12px 16px' }}>
              <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted, textTransform: 'uppercase', letterSpacing: '0.15em', marginBottom: 10 }}>Trending Diseases (7 days)</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {stats.trending_diseases.map((d, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 4, padding: '5px 10px' }}>
                    <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.text }}>{d.disease_name}</span>
                    <span style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 16, color: T.danger }}>{d.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {/* ── Main layout: tabs + live feed ── */}
        <div style={{ display: 'flex', gap: 18, alignItems: 'flex-start' }}>
          <div style={{ flex: 1, minWidth: 0 }}>

            {/* Tab bar — scrollable on small screens */}
            <motion.div {...fadeUp(0.1)}>
              <div className="surv-tabs-wrap">
              <div ref={tabsRef} style={{
                display: 'flex',
                gap: 0,
                marginBottom: 16,
                borderBottom: `1px solid ${T.border}`,
                overflowX: 'auto',
                msOverflowStyle: 'none',
                scrollbarWidth: 'none',
              }}>
                {TABS.map(t => (
                  <button
                    key={t.key}
                    onClick={() => setActiveTab(t.key)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      borderBottom: activeTab === t.key ? `2px solid ${T.accent}` : '2px solid transparent',
                      padding: '10px 16px',
                      fontFamily: 'IBM Plex Sans, sans-serif',
                      fontSize: 13,
                      color: activeTab === t.key ? T.text : T.textSub,
                      cursor: 'pointer',
                      fontWeight: activeTab === t.key ? 500 : 400,
                      transition: 'all 0.15s',
                      marginBottom: -1,
                      whiteSpace: 'nowrap',
                      flexShrink: 0,
                    }}
                  >{t.label}</button>
                ))}
              </div>
              </div>
            </motion.div>

            {/* Tab content */}
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.2 }}
              >
                {activeTab === 'anomalies' && <AnomaliesTab navigate={navigate} wsMessages={wsMessages} />}
                {activeTab === 'clusters'  && <ClustersTab navigate={navigate} />}
                {activeTab === 'hotspots'  && <HotspotsTab />}
                {activeTab === 'diseases'  && <DiseasesTab />}
                {activeTab === 'sources'   && <DataSourcesTab />}
                {activeTab === 'health'    && <HealthDataTab />}
                {activeTab === 'reports'   && <ReportsTab />}
                {activeTab === 'quality'   && <QualityTab />}
              </motion.div>
            </AnimatePresence>
          </div>

          {/* ── Right sidebar (hidden on very small screens via CSS) ── */}
          <motion.div
            {...fadeUp(0.12)}
            className="surv-sidebar"
            style={{ width: 260, flexShrink: 0 }}
          >
            {/* High-risk locations */}
            {stats?.high_risk_locations?.length > 0 && (
              <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '14px 16px', marginBottom: 14 }}>
                <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 13, color: T.text, letterSpacing: '0.05em', marginBottom: 10 }}>HIGH-RISK LOCATIONS</div>
                {stats.high_risk_locations.map((loc, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 0', borderBottom: i < stats.high_risk_locations.length - 1 ? `1px solid ${T.border}` : 'none' }}>
                    <div style={{ width: 5, height: 5, borderRadius: '50%', background: T.danger, flexShrink: 0 }} />
                    <span style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 12, color: T.textSub }}>{loc}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Recent critical alerts */}
            {stats?.recent_alerts?.length > 0 && (
              <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 6, padding: '14px 16px', marginBottom: 14 }}>
                <div style={{ fontFamily: 'Bebas Neue, sans-serif', fontSize: 13, color: T.text, letterSpacing: '0.05em', marginBottom: 10 }}>RECENT CRITICAL ALERTS</div>
                {stats.recent_alerts.map((a, i) => {
                  const sev = SEVERITY_CFG[a.severity] || { color: T.textMuted };
                  return (
                    <div key={i} style={{ padding: '7px 0', borderBottom: i < stats.recent_alerts.length - 1 ? `1px solid ${T.border}` : 'none' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
                        <div style={{ fontFamily: 'IBM Plex Sans, sans-serif', fontSize: 11, color: T.text }}>{a.disease_name}</div>
                        <Badge label={a.severity} color={sev.color} />
                      </div>
                      <div style={{ fontFamily: 'Space Mono, monospace', fontSize: 8, color: T.textMuted }}>
                        {a['location__name']} · {fmtDateShort(a.detected_at)}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <LiveFeed wsMessages={wsMessages} />
          </motion.div>
        </div>
      </div>

      {/* Responsive: hide sidebar on narrow screens */}
      <style>{`
        @media (max-width: 900px) {
          .surv-sidebar { display: none !important; }
        }
      `}</style>
    </div>
  );
}