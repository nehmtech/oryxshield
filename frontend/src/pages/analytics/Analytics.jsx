/**
 * Analytics — OryxShield
 * ================================
 * Lists epidemiological models (EpidemiologicalModelListSerializer fields),
 * shows overview stats from GET /analytics/overview/overview/,
 * and recent exports from GET /analytics/exports/.
 *
 * Serializer field map (EpidemiologicalModelListSerializer):
 *   id, name, model_type, model_type_display,
 *   disease_name, disease_code, location_name,
 *   basic_reproduction_number, is_validated,
 *   simulation_completed_at, created_at
 *
 * Overview payload (AnalyticsDashboardSerializer):
 *   total_analyses, total_models, total_reports, total_exports,
 *   active_dashboards, recent_models, recent_exports, key_indicators
 *
 * DataExportSerializer fields used here:
 *   id, name, export_format, status, created_at, file_size_display
 */
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { analyticsApi, extractError } from "../../services/api";

// ─── keyframes injected once ─────────────────────────────────────────────────
const GLOBAL_STYLES = `
  @keyframes an-fadeUp  { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:translateY(0); } }
  @keyframes an-shimmer { 0% { background-position:200% 0; } 100% { background-position:-200% 0; } }
`;

const fadeUp = (delay = 0) => ({
  opacity: 0,
  animation: `an-fadeUp 0.3s ease-out ${delay}s forwards`,
});

// ─── Shared sub-components ────────────────────────────────────────────────────
const Badge = ({ children, color = "#3b82f6" }) => (
  <span style={{
    fontFamily:    "Space Mono, monospace",
    fontSize:      9,
    letterSpacing: "0.12em",
    textTransform: "uppercase",
    color,
    background:    color + "18",
    border:        `1px solid ${color}30`,
    borderRadius:  2,
    padding:       "2px 8px",
    whiteSpace:    "nowrap",
  }}>
    {children}
  </span>
);

const Shimmer = ({ height = 14 }) => (
  <div style={{
    background:     "linear-gradient(90deg,#111827 0%,#151e2e 50%,#111827 100%)",
    backgroundSize: "200%",
    animation:      "an-shimmer 1.5s infinite",
    borderRadius:   4,
    height,
    marginBottom:   8,
  }} />
);

// ─── Color maps ───────────────────────────────────────────────────────────────
const MODEL_COLORS = {
  SIR: "#3b82f6", SEIR: "#9ca3af", SIRS: "#f59e0b",
  SEIRS: "#10b981", SIS: "#6b7280", CUSTOM: "#a78bfa",
};
const EXPORT_STATUS_COLORS = {
  PENDING: "#6b7280", PROCESSING: "#3b82f6",
  COMPLETED: "#10b981", FAILED: "#ef4444", EXPIRED: "#9b1c1c",
};
const EXPORT_FORMAT_COLORS = {
  CSV: "#10b981", JSON: "#3b82f6", XLSX: "#f59e0b", PDF: "#ef4444",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
function relativeTime(dateStr) {
  if (!dateStr) return "—";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)  return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ─── Table header / cell styles ───────────────────────────────────────────────
const thS = {
  fontFamily:    "Space Mono, monospace",
  fontSize:      9,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color:         "#6b7280",
  padding:       "10px 14px",
  textAlign:     "left",
  borderBottom:  "1px solid #1f2937",
  whiteSpace:    "nowrap",
};
const tdS = {
  padding:    "12px 14px",
  fontSize:   13,
  color:      "#f9fafb",
  fontFamily: "IBM Plex Sans, sans-serif",
  borderBottom: "1px solid #1f2937",
};

const PAGE_SIZE = 20;

// ─── Component ────────────────────────────────────────────────────────────────
export default function Analytics() {
  const navigate = useNavigate();

  // Overview stats  (GET /analytics/overview/overview/)
  const [overview, setOverview]       = useState(null);
  const [overviewErr, setOverviewErr] = useState(null);

  // Epi models table  (GET /analytics/epi-models/)
  const [models, setModels]           = useState([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelsError, setModelsError] = useState(null);
  const [page, setPage]               = useState(1);
  const [total, setTotal]             = useState(0);

  // Filters
  const [filterType, setFilterType]   = useState("");
  const [filterSearch, setFilterSearch] = useState("");
  const [filterValidated, setFilterValidated] = useState("");

  // Recent exports sidebar  (GET /analytics/exports/?page_size=8)
  const [exports, setExports]           = useState([]);
  const [exportsLoading, setExportsLoading] = useState(true);

  // ── Fetch overview ──────────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const res = await analyticsApi.getDashboardOverview();
        setOverview(res.data);
      } catch (err) {
        setOverviewErr(extractError(err));
      }
    })();
  }, []);

  // ── Fetch models ────────────────────────────────────────────────────────────
  const fetchModels = useCallback(async () => {
    setModelsLoading(true);
    setModelsError(null);
    try {
      const params = { page, page_size: PAGE_SIZE };
      if (filterType)      params.model_type  = filterType;
      if (filterSearch)    params.search       = filterSearch;
      if (filterValidated) params.is_validated = filterValidated === "yes";
      const res = await analyticsApi.listEpidemiologicalModels(params);
      setModels(res.data.results ?? res.data ?? []);
      setTotal(res.data.count ?? 0);
    } catch (err) {
      setModelsError(extractError(err));
    } finally {
      setModelsLoading(false);
    }
  }, [page, filterType, filterSearch, filterValidated]);

  useEffect(() => { fetchModels(); }, [fetchModels]);

  // ── Fetch recent exports ────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      setExportsLoading(true);
      try {
        const res = await analyticsApi.listDataExports({ page_size: 8 });
        setExports(res.data.results ?? res.data ?? []);
      } catch { /* silent */ } finally {
        setExportsLoading(false);
      }
    })();
  }, []);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  // ── Stat cards from AnalyticsDashboardSerializer ────────────────────────────
  const statCards = [
    { label: "Total Models",      key: "total_models",     color: "#3b82f6" },
    { label: "Total Analyses",    key: "total_analyses",   color: "#10b981" },
    { label: "Published Reports", key: "total_reports",    color: "#f59e0b" },
    { label: "My Exports",        key: "total_exports",    color: "#9ca3af" },
    { label: "Active Dashboards", key: "active_dashboards",color: "#a78bfa" },
  ];

  // ── Run simulation quick action ─────────────────────────────────────────────
  const [runningId, setRunningId] = useState(null);
  async function handleRunSimulation(e, modelId) {
    e.stopPropagation();
    setRunningId(modelId);
    try {
      await analyticsApi.runSimulation(modelId, {});
      // re-fetch to show updated simulation_completed_at
      await fetchModels();
    } catch { /* toast already handled globally */ } finally {
      setRunningId(null);
    }
  }

  return (
    <div style={{ fontFamily: "IBM Plex Sans, sans-serif", color: "#f9fafb", minHeight: "100vh" }}>
      <style>{GLOBAL_STYLES}</style>

      {/* ── Eyebrow / heading ──────────────────────────────────────────────── */}
      <div style={{ marginBottom: 24, ...fadeUp(0) }}>
        <div style={{ fontFamily: "Space Mono, monospace", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b7280", marginBottom: 4 }}>
          Phase 9 / Analytics
        </div>
        <h1 style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 32, color: "#f9fafb", margin: 0, letterSpacing: "0.04em" }}>
          Analytics
        </h1>
        {overviewErr && (
          <div style={{ fontSize: 12, color: "#ef4444", marginTop: 6 }}>{overviewErr}</div>
        )}
      </div>

      {/* ── Stat cards ─────────────────────────────────────────────────────── */}
      <div style={{
        display:             "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 140px), 1fr))",
        gap:                 14,
        marginBottom:        28,
        ...fadeUp(0.05),
      }}>
        {statCards.map(({ label, key, color }) => (
          <div key={key} style={{
            background:  "#111827",
            border:      "1px solid #1f2937",
            borderRadius: 6,
            padding:     "18px 20px",
          }}>
            <div style={{ fontFamily: "Space Mono, monospace", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b7280", marginBottom: 10 }}>
              {label}
            </div>
            {overview ? (
              <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 34, color, lineHeight: 1 }}>
                {overview[key] ?? "—"}
              </div>
            ) : (
              <Shimmer height={28} />
            )}
          </div>
        ))}
      </div>

      {/* ── Filter bar ─────────────────────────────────────────────────────── */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16, ...fadeUp(0.08) }}>
        <input
          placeholder="Search name / disease / code…"
          value={filterSearch}
          onChange={(e) => { setFilterSearch(e.target.value); setPage(1); }}
          style={{ flex: "1 1 200px", minWidth: 180, background: "#111827", border: "1px solid #1f2937", borderRadius: 4, padding: "8px 12px", fontSize: 12, color: "#f9fafb", fontFamily: "IBM Plex Sans, sans-serif", outline: "none" }}
        />
        <select
          value={filterType}
          onChange={(e) => { setFilterType(e.target.value); setPage(1); }}
          style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 4, padding: "8px 12px", fontSize: 12, color: filterType ? "#f9fafb" : "#6b7280", fontFamily: "IBM Plex Sans, sans-serif", cursor: "pointer" }}
        >
          <option value="">All model types</option>
          {["SIR","SEIR","SIRS","SEIRS","SIS","CUSTOM"].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={filterValidated}
          onChange={(e) => { setFilterValidated(e.target.value); setPage(1); }}
          style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 4, padding: "8px 12px", fontSize: 12, color: filterValidated ? "#f9fafb" : "#6b7280", fontFamily: "IBM Plex Sans, sans-serif", cursor: "pointer" }}
        >
          <option value="">Validation — all</option>
          <option value="yes">Validated</option>
          <option value="no">Unvalidated</option>
        </select>
        {(filterSearch || filterType || filterValidated) && (
          <button
            onClick={() => { setFilterSearch(""); setFilterType(""); setFilterValidated(""); setPage(1); }}
            style={{ background: "transparent", border: "1px solid #1f2937", borderRadius: 4, padding: "8px 14px", fontSize: 12, color: "#9ca3af", cursor: "pointer", fontFamily: "IBM Plex Sans, sans-serif" }}
          >
            Clear
          </button>
        )}
      </div>

      {/* ── Main layout: table + exports sidebar ───────────────────────────── */}
      <div style={{ display: "flex", gap: 20, alignItems: "flex-start", ...fadeUp(0.1) }}>

        {/* Epi Models Table */}
        <div style={{ flex: 1, minWidth: 0, background: "#111827", border: "1px solid #1f2937", borderRadius: 6, overflow: "hidden" }}>
          <div style={{ padding: "14px 20px", borderBottom: "1px solid #1f2937", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontFamily: "Space Mono, monospace", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b7280" }}>
              Epidemiological Models
            </span>
            {total > 0 && (
              <span style={{ fontFamily: "Space Mono, monospace", fontSize: 9, color: "#6b7280" }}>
                {total} total
              </span>
            )}
          </div>

          {modelsError && (
            <div style={{ padding: "12px 20px", color: "#ef4444", fontSize: 13 }}>{modelsError}</div>
          )}

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Name","Type","Disease","Location","R₀","Validated","Last Simulation",""].map((h) => (
                    <th key={h} style={thS}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {modelsLoading
                  ? Array.from({ length: 6 }).map((_, i) => (
                      <tr key={i}>
                        {Array.from({ length: 8 }).map((_, j) => (
                          <td key={j} style={tdS}><Shimmer /></td>
                        ))}
                      </tr>
                    ))
                  : models.length === 0
                  ? (
                    <tr>
                      <td colSpan={8} style={{ ...tdS, textAlign: "center", color: "#6b7280", padding: 32 }}>
                        No models found.
                      </td>
                    </tr>
                  )
                  : models.map((m) => {
                      const r0 = m.basic_reproduction_number;
                      const r0Color = r0 == null ? "#9ca3af" : Number(r0) > 1 ? "#ef4444" : "#10b981";
                      return (
                        <tr
                          key={m.id}
                          onClick={() => navigate(`/dashboard/analytics/${m.id}`)}
                          style={{ cursor: "pointer" }}
                          onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.02)"}
                          onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                        >
                          <td style={{ ...tdS, fontWeight: 500 }}>
                            {m.name || "—"}
                          </td>
                          <td style={tdS}>
                            <Badge color={MODEL_COLORS[m.model_type] || "#6b7280"}>
                              {m.model_type || "—"}
                            </Badge>
                          </td>
                          <td style={{ ...tdS, color: "#9ca3af", maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {m.disease_name || "—"}
                          </td>
                          <td style={{ ...tdS, color: "#9ca3af", fontSize: 12 }}>
                            {m.location_name || "—"}
                          </td>
                          <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 12, color: r0Color, fontWeight: 600 }}>
                            {r0 != null ? Number(r0).toFixed(2) : "—"}
                          </td>
                          <td style={tdS}>
                            {m.is_validated
                              ? <Badge color="#10b981">✓ Valid</Badge>
                              : <Badge color="#6b7280">Pending</Badge>
                            }
                          </td>
                          <td style={{ ...tdS, color: "#9ca3af", fontSize: 12 }}>
                            {m.simulation_completed_at
                              ? relativeTime(m.simulation_completed_at)
                              : <span style={{ color: "#6b7280" }}>—</span>
                            }
                          </td>
                          <td style={{ ...tdS, whiteSpace: "nowrap" }}>
                            <div style={{ display: "flex", gap: 6 }}>
                              <button
                                onClick={(e) => { e.stopPropagation(); navigate(`/dashboard/analytics/${m.id}`); }}
                                style={{ background: "#1f2937", color: "#f9fafb", border: "none", borderRadius: 4, padding: "5px 12px", fontSize: 12, cursor: "pointer", fontFamily: "IBM Plex Sans, sans-serif" }}
                              >
                                View
                              </button>
                              <button
                                onClick={(e) => handleRunSimulation(e, m.id)}
                                disabled={runningId === m.id}
                                style={{ background: runningId === m.id ? "#151e2e" : "#3b82f6", color: runningId === m.id ? "#6b7280" : "#fff", border: "none", borderRadius: 4, padding: "5px 12px", fontSize: 12, cursor: runningId === m.id ? "default" : "pointer", fontFamily: "IBM Plex Sans, sans-serif" }}
                              >
                                {runningId === m.id ? "…" : "Run"}
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ padding: "12px 20px", borderTop: "1px solid #1f2937", display: "flex", gap: 8, alignItems: "center", justifyContent: "flex-end" }}>
              <button
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
                style={{ background: page === 1 ? "#151e2e" : "#1f2937", color: page === 1 ? "#6b7280" : "#f9fafb", border: "none", borderRadius: 4, padding: "6px 14px", fontSize: 12, cursor: page === 1 ? "default" : "pointer", fontFamily: "IBM Plex Sans, sans-serif" }}
              >
                Prev
              </button>
              <span style={{ fontFamily: "Space Mono, monospace", fontSize: 10, color: "#6b7280" }}>
                {page} / {totalPages}
              </span>
              <button
                disabled={page === totalPages}
                onClick={() => setPage((p) => p + 1)}
                style={{ background: page === totalPages ? "#151e2e" : "#1f2937", color: page === totalPages ? "#6b7280" : "#f9fafb", border: "none", borderRadius: 4, padding: "6px 14px", fontSize: 12, cursor: page === totalPages ? "default" : "pointer", fontFamily: "IBM Plex Sans, sans-serif" }}
              >
                Next
              </button>
            </div>
          )}
        </div>

        {/* ── Exports Sidebar ───────────────────────────────────────────────── */}
        <div style={{ width: 260, flexShrink: 0, background: "#111827", border: "1px solid #1f2937", borderRadius: 6, overflow: "hidden" }}>
          <div style={{ padding: "14px 18px", borderBottom: "1px solid #1f2937", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontFamily: "Space Mono, monospace", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b7280" }}>
              Recent Exports
            </span>
          </div>

          <div style={{ padding: "8px 0" }}>
            {exportsLoading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} style={{ padding: "10px 18px" }}><Shimmer /></div>
                ))
              : exports.length === 0
              ? (
                <div style={{ padding: "20px 18px", fontSize: 13, color: "#6b7280", textAlign: "center" }}>
                  No exports yet.
                </div>
              )
              : exports.map((ex) => (
                  <div key={ex.id} style={{ padding: "12px 18px", borderBottom: "1px solid #1f2937" }}>
                    <div style={{ fontSize: 13, color: "#f9fafb", marginBottom: 6, fontWeight: 500, lineHeight: 1.4 }}>
                      {ex.name || "Export"}
                    </div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
                      <Badge color={EXPORT_FORMAT_COLORS[ex.export_format] || "#6b7280"}>
                        {ex.export_format || "—"}
                      </Badge>
                      <Badge color={EXPORT_STATUS_COLORS[ex.status] || "#6b7280"}>
                        {ex.status || "—"}
                      </Badge>
                    </div>
                    {ex.file_size_display && (
                      <div style={{ fontFamily: "Space Mono, monospace", fontSize: 10, color: "#6b7280", marginBottom: 2 }}>
                        {ex.file_size_display}
                      </div>
                    )}
                    <div style={{ fontFamily: "Space Mono, monospace", fontSize: 10, color: "#6b7280" }}>
                      {relativeTime(ex.created_at)}
                    </div>
                  </div>
                ))}
          </div>

          {/* Key Indicators from overview */}
          {overview?.key_indicators?.length > 0 && (
            <>
              <div style={{ padding: "14px 18px", borderTop: "1px solid #1f2937", borderBottom: "1px solid #1f2937" }}>
                <span style={{ fontFamily: "Space Mono, monospace", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b7280" }}>
                  Key Indicators
                </span>
              </div>
              <div style={{ padding: "8px 0" }}>
                {overview.key_indicators.map((ind) => (
                  <div key={ind.id} style={{ padding: "10px 18px", borderBottom: "1px solid #1f2937" }}>
                    <div style={{ fontSize: 12, color: "#f9fafb", fontWeight: 500 }}>{ind.name}</div>
                    <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                      <Badge color="#6b7280">{ind.code}</Badge>
                      <Badge color="#a78bfa">{ind.indicator_type}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}