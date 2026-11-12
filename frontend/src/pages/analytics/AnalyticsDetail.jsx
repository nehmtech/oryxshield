/**
 * AnalyticsDetail — OryxShield
 * ======================================
 * Detail view for a single EpidemiologicalModel.
 * Three tabs:
 *   TIME_SERIES  — listTimeSeriesAnalyses({ disease_code }) + Recharts line chart
 *                  fields: id, name, analysis_type_display, disease_name,
 *                          location_name, trend_direction, has_seasonality,
 *                          mae, rmse, mape, has_forecast, forecast_horizon,
 *                          start_date, end_date
 *   SPATIAL      — listSpatialAnalyses({ disease_code }) + hotspot table
 *                  fields: id, name, analysis_type_display, disease_name,
 *                          location_name, morans_i, p_value, z_score,
 *                          is_significant, hotspot_count, cluster_count,
 *                          hotspots[], start_date, end_date
 *   REPORTS      — listStatisticalReports() + paginated table
 *                  (StatisticalReportListSerializer):
 *                  id, title, report_type, author_username,
 *                  is_published, published_at, start_date, end_date, created_at
 *
 * Full model detail (EpidemiologicalModelSerializer):
 *   id, name, model_type, model_type_display,
 *   disease_name, disease_code, location_name,
 *   basic_reproduction_number, r0_status, attack_rate,
 *   peak_day, peak_infections, simulation_days,
 *   simulation_completed_at, is_validated, validated_at,
 *   model_fit_score, rmse, initial_susceptible, initial_infected,
 *   initial_recovered, initial_exposed, total_population,
 *   simulation_results {days[], susceptible[], exposed?, infected[], recovered[]}
 */
import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { analyticsApi, extractError } from "../../services/api";
import { useToast } from "../../context/ToastContext";
import Breadcrumb from "../../components/ui/Breadcrumb";

// ─── keyframes ────────────────────────────────────────────────────────────────
const GLOBAL_STYLES = `
  @keyframes ad-fadeUp  { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
  @keyframes ad-shimmer { 0% { background-position:200% 0; } 100% { background-position:-200% 0; } }
`;
const fadeUp = (d = 0) => ({ opacity: 0, animation: `ad-fadeUp 0.3s ease-out ${d}s forwards` });

// ─── Shared sub-components ────────────────────────────────────────────────────
const Badge = ({ children, color = "#3b82f6" }) => (
  <span style={{
    fontFamily: "Space Mono, monospace", fontSize: 9, letterSpacing: "0.12em",
    textTransform: "uppercase", color, background: color + "18",
    border: `1px solid ${color}30`, borderRadius: 2, padding: "2px 8px", whiteSpace: "nowrap",
  }}>{children}</span>
);

const Shimmer = ({ height = 14 }) => (
  <div style={{
    background:     "linear-gradient(90deg,#111827 0%,#151e2e 50%,#111827 100%)",
    backgroundSize: "200%",
    animation:      "ad-shimmer 1.5s infinite",
    borderRadius:   4, height, marginBottom: 8,
  }} />
);

// ─── Color maps ───────────────────────────────────────────────────────────────
const MODEL_COLORS = {
  SIR: "#3b82f6", SEIR: "#9ca3af", SIRS: "#f59e0b",
  SEIRS: "#10b981", SIS: "#6b7280", CUSTOM: "#a78bfa",
};
const TREND_COLORS = {
  INCREASING: "#ef4444", DECREASING: "#10b981",
  STABLE: "#f59e0b", UNKNOWN: "#6b7280",
};
const R0_COLORS = { epidemic: "#ef4444", endemic: "#f59e0b", declining: "#10b981" };

// ─── Table styles ─────────────────────────────────────────────────────────────
const thS = {
  fontFamily: "Space Mono, monospace", fontSize: 9, letterSpacing: "0.12em",
  textTransform: "uppercase", color: "#6b7280", padding: "10px 14px",
  textAlign: "left", borderBottom: "1px solid #1f2937", whiteSpace: "nowrap",
};
const tdS = {
  padding: "12px 14px", fontSize: 13, color: "#f9fafb",
  fontFamily: "IBM Plex Sans, sans-serif", borderBottom: "1px solid #1f2937",
};

const TABS = ["TIME_SERIES", "SPATIAL", "REPORTS"];
const TAB_LABELS = { TIME_SERIES: "Time Series", SPATIAL: "Spatial", REPORTS: "Reports" };
const PAGE_SIZE = 20;

// ─── Metric card ──────────────────────────────────────────────────────────────
function MetricCard({ label, value, color = "#f9fafb", sub }) {
  return (
    <div style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 6, padding: "16px 20px" }}>
      <div style={{ fontFamily: "Space Mono, monospace", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b7280", marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 30, color, lineHeight: 1 }}>
        {value ?? "—"}
      </div>
      {sub && <div style={{ fontSize: 11, color: "#6b7280", marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

// ─── Tooltip for recharts ─────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 4, padding: "10px 14px", fontSize: 12, fontFamily: "IBM Plex Sans, sans-serif" }}>
      <div style={{ color: "#6b7280", marginBottom: 6, fontFamily: "Space Mono, monospace", fontSize: 10 }}>
        Day {label}
      </div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color, lineHeight: 1.6 }}>
          {p.name}: {typeof p.value === "number" ? Math.round(p.value).toLocaleString() : p.value}
        </div>
      ))}
    </div>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function AnalyticsDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();

  // ── Main model record ──────────────────────────────────────────────────────
  const [model, setModel]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  // ── Tab state ──────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState("TIME_SERIES");

  // ── Time Series tab ────────────────────────────────────────────────────────
  const [tsAnalyses, setTsAnalyses]     = useState([]);
  const [tsLoading, setTsLoading]       = useState(false);
  const [tsError, setTsError]           = useState(null);
  const [selectedTs, setSelectedTs]     = useState(null);  // expanded row

  // ── Spatial tab ────────────────────────────────────────────────────────────
  const [spatialList, setSpatialList]   = useState([]);
  const [spatLoading, setSpatLoading]   = useState(false);
  const [spatError, setSpatError]       = useState(null);
  const [selectedSpat, setSelectedSpat] = useState(null);

  // ── Reports tab ────────────────────────────────────────────────────────────
  const [reports, setReports]             = useState([]);
  const [rLoading, setRLoading]           = useState(false);
  const [rError, setRError]               = useState(null);
  const [rPage, setRPage]                 = useState(1);
  const [rTotal, setRTotal]               = useState(0);

  // ── Simulation action ──────────────────────────────────────────────────────
  const [simRunning, setSimRunning] = useState(false);
  const [simMsg, setSimMsg]         = useState(null);

  // ── Fetch model ───────────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      setLoading(true); setError(null);
      try {
        const res = await analyticsApi.getEpidemiologicalModel(id);
        setModel(res.data);
      } catch (err) {
        setError(extractError(err));
      } finally {
        setLoading(false);
      }
    })();
  }, [id]);

  // ── Fetch time series (scoped by disease_code once model loads) ───────────
  const fetchTimeSeries = useCallback(async () => {
    if (!model) return;
    setTsLoading(true); setTsError(null);
    try {
      const params = { page_size: 50 };
      if (model.disease_code) params.disease_code = model.disease_code;
      const res = await analyticsApi.listTimeSeriesAnalyses(params);
      setTsAnalyses(res.data.results ?? res.data ?? []);
    } catch (err) {
      setTsError(extractError(err));
    } finally {
      setTsLoading(false);
    }
  }, [model]);

  // ── Fetch spatial analyses (scoped by disease_code) ───────────────────────
  const fetchSpatial = useCallback(async () => {
    if (!model) return;
    setSpatLoading(true); setSpatError(null);
    try {
      const params = { page_size: 20 };
      if (model.disease_code) params.disease_code = model.disease_code;
      const res = await analyticsApi.listSpatialAnalyses(params);
      setSpatialList(res.data.results ?? res.data ?? []);
    } catch (err) {
      setSpatError(extractError(err));
    } finally {
      setSpatLoading(false);
    }
  }, [model]);

  // ── Fetch reports ─────────────────────────────────────────────────────────
  const fetchReports = useCallback(async () => {
    setRLoading(true); setRError(null);
    try {
      const params = { page: rPage, page_size: PAGE_SIZE };
      const res = await analyticsApi.listStatisticalReports(params);
      setReports(res.data.results ?? res.data ?? []);
      setRTotal(res.data.count ?? 0);
    } catch (err) {
      setRError(extractError(err));
    } finally {
      setRLoading(false);
    }
  }, [rPage]);

  // ── Tab data loading ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!model) return;
    if (activeTab === "TIME_SERIES") fetchTimeSeries();
    if (activeTab === "SPATIAL")     fetchSpatial();
    if (activeTab === "REPORTS")     fetchReports();
  }, [activeTab, model, fetchTimeSeries, fetchSpatial, fetchReports]);

  // ── Build Recharts data from simulation_results ────────────────────────────
  const simChartData = (() => {
    const sr = model?.simulation_results;
    if (!sr || !sr.days?.length) return [];
    const step = Math.max(1, Math.floor(sr.days.length / 200)); // downsample to ≤200pts
    return sr.days
      .filter((_, i) => i % step === 0)
      .map((day, idx) => {
        const i = idx * step;
        return {
          day: Math.round(day),
          susceptible: Math.round(sr.susceptible?.[i] ?? 0),
          ...(sr.exposed ? { exposed: Math.round(sr.exposed[i] ?? 0) } : {}),
          infected:    Math.round(sr.infected?.[i] ?? 0),
          recovered:   Math.round(sr.recovered?.[i] ?? 0),
        };
      });
  })();

  // ── Run simulation ────────────────────────────────────────────────────────
  async function handleRunSim() {
    if (!model) return;
    setSimRunning(true); setSimMsg(null);
    try {
      const res = await analyticsApi.runSimulation(model.id, {
        simulation_days: model.simulation_days,
      });
      setSimMsg(`Simulation queued — task ${res.data.task_id}`);
    } catch (err) {
      setSimMsg(`Error: ${extractError(err)}`);
    } finally {
      setSimRunning(false);
    }
  }

  // ── Loading / error guards ────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ fontFamily: "IBM Plex Sans, sans-serif" }}>
        <style>{GLOBAL_STYLES}</style>
        {Array.from({ length: 5 }).map((_, i) => <Shimmer key={i} height={22} />)}
      </div>
    );
  }
  if (error) {
    return (
      <div style={{ fontFamily: "IBM Plex Sans, sans-serif" }}>
        <style>{GLOBAL_STYLES}</style>
        <div style={{ color: "#ef4444", fontSize: 13 }}>{error}</div>
        <button onClick={() => navigate(-1)} style={{ marginTop: 12, background: "#1f2937", color: "#f9fafb", border: "none", borderRadius: 4, padding: "8px 16px", fontSize: 12, cursor: "pointer" }}>
          ← Back
        </button>
      </div>
    );
  }

  const r0        = model?.basic_reproduction_number;
  const r0Num     = r0 != null ? Number(r0) : null;
  const r0Color   = r0Num == null ? "#9ca3af" : r0Num > 1 ? "#ef4444" : "#10b981";
  const rTotalPages = Math.ceil(rTotal / PAGE_SIZE);

  return (
    <div style={{ fontFamily: "IBM Plex Sans, sans-serif", color: "#f9fafb", minHeight: "100vh" }}>
      <style>{GLOBAL_STYLES}</style>

      {/* ── Back + heading ─────────────────────────────────────────────────── */}
      <div style={{ marginBottom: 24, ...fadeUp(0) }}>
        <Breadcrumb items={[
          { label: 'Analytics', to: '/dashboard/analytics' },
          { label: model?.name || `Model #${id}` },
        ]} />
        <div style={{ fontFamily: "Space Mono, monospace", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b7280", marginBottom: 4 }}>
          {model.model_type_display || model.model_type} · {model.disease_code}
        </div>
        <h1 style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 32, margin: 0, letterSpacing: "0.04em" }}>
          {model.name}
        </h1>
        <div style={{ fontSize: 13, color: "#9ca3af", marginTop: 4 }}>
          {model.disease_name}{model.location_name ? ` · ${model.location_name}` : ""}
        </div>
      </div>

      {/* ── Model metric strip ─────────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6,1fr)", gap: 12, marginBottom: 24, ...fadeUp(0.05) }}>
        <MetricCard label="R₀" value={r0Num != null ? r0Num.toFixed(2) : "—"} color={r0Color}
          sub={model.r0_status ? <Badge color={R0_COLORS[model.r0_status] || "#6b7280"}>{model.r0_status}</Badge> : undefined}
        />
        <MetricCard label="Attack Rate" value={model.attack_rate != null ? `${Number(model.attack_rate).toFixed(1)}%` : "—"} color="#f9fafb" />
        <MetricCard label="Peak Day"    value={model.peak_day ?? "—"}         color="#f9fafb" />
        <MetricCard label="Peak Cases"  value={model.peak_infections != null ? Number(model.peak_infections).toLocaleString() : "—"} color="#ef4444" />
        <MetricCard label="Population"  value={model.total_population != null ? Number(model.total_population).toLocaleString() : "—"} color="#f9fafb" />
        <MetricCard label="Sim Days"    value={model.simulation_days ?? "—"}   color="#f9fafb"
          sub={model.is_validated ? <Badge color="#10b981">Validated</Badge> : <Badge color="#6b7280">Unvalidated</Badge>}
        />
      </div>

      {/* ── Run simulation button + message ───────────────────────────────── */}
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 24, ...fadeUp(0.08) }}>
        <button
          onClick={handleRunSim}
          disabled={simRunning}
          style={{ background: simRunning ? "#151e2e" : "#3b82f6", color: simRunning ? "#6b7280" : "#fff", border: "none", borderRadius: 4, padding: "9px 20px", fontSize: 13, fontWeight: 500, cursor: simRunning ? "default" : "pointer", fontFamily: "IBM Plex Sans, sans-serif" }}
        >
          {simRunning ? "Queueing…" : "Run Simulation"}
        </button>
        {simMsg && (
          <span style={{ fontSize: 12, color: simMsg.startsWith("Error") ? "#ef4444" : "#10b981" }}>
            {simMsg}
          </span>
        )}
        {model.simulation_completed_at && (
          <span style={{ fontFamily: "Space Mono, monospace", fontSize: 10, color: "#6b7280" }}>
            Last run: {new Date(model.simulation_completed_at).toLocaleString()}
          </span>
        )}
      </div>

      {/* ── Simulation results chart ─────────────────────────────────────── */}
      {simChartData.length > 0 && (
        <div style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 6, padding: "20px 24px", marginBottom: 24, ...fadeUp(0.1) }}>
          <div style={{ fontFamily: "Space Mono, monospace", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b7280", marginBottom: 16 }}>
            Simulation Results — {model.model_type_display || model.model_type}
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={simChartData} margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="day" tick={{ fill: "#6b7280", fontSize: 10 }} tickLine={false} />
              <YAxis tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v} tick={{ fill: "#6b7280", fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Legend wrapperStyle={{ fontFamily: "Space Mono, monospace", fontSize: 10, color: "#9ca3af", paddingTop: 12 }} />
              <Line type="monotone" dataKey="susceptible" stroke="#3b82f6"  dot={false} strokeWidth={1.5} name="Susceptible" />
              {model.model_type?.includes("E") && (
                <Line type="monotone" dataKey="exposed"     stroke="#f59e0b" dot={false} strokeWidth={1.5} name="Exposed" />
              )}
              <Line type="monotone" dataKey="infected"    stroke="#ef4444" dot={false} strokeWidth={2}   name="Infected" />
              <Line type="monotone" dataKey="recovered"   stroke="#10b981" dot={false} strokeWidth={1.5} name="Recovered" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── Tab navigation ───────────────────────────────────────────────── */}
      <div style={{ display: "flex", gap: 0, marginBottom: 20, borderBottom: "1px solid #1f2937", ...fadeUp(0.12) }}>
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              background:     "transparent",
              border:         "none",
              borderBottom:   activeTab === tab ? "2px solid #3b82f6" : "2px solid transparent",
              color:          activeTab === tab ? "#f9fafb" : "#6b7280",
              padding:        "10px 20px",
              fontSize:       13,
              fontFamily:     "IBM Plex Sans, sans-serif",
              cursor:         "pointer",
              fontWeight:     activeTab === tab ? 500 : 400,
              transition:     "color 0.15s, border-color 0.15s",
              marginBottom:   -1,
            }}
          >
            {TAB_LABELS[tab]}
          </button>
        ))}
      </div>

      {/* ────────────────────────────────────────────────────────────────────── */}
      {/* TIME SERIES TAB                                                        */}
      {/* ────────────────────────────────────────────────────────────────────── */}
      {activeTab === "TIME_SERIES" && (
        <div style={fadeUp(0)}>
          {tsError && <div style={{ color: "#ef4444", fontSize: 13, marginBottom: 16 }}>{tsError}</div>}

          <div style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 6, overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Name","Type","Location","Trend","Seasonal","MAE","RMSE","Forecast","Period"].map((h) => (
                    <th key={h} style={thS}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tsLoading
                  ? Array.from({ length: 5 }).map((_, i) => (
                      <tr key={i}>
                        {Array.from({ length: 9 }).map((_, j) => <td key={j} style={tdS}><Shimmer /></td>)}
                      </tr>
                    ))
                  : tsAnalyses.length === 0
                  ? (
                    <tr>
                      <td colSpan={9} style={{ ...tdS, textAlign: "center", color: "#6b7280", padding: 32 }}>
                        No time-series analyses found for disease code <strong>{model.disease_code}</strong>.
                      </td>
                    </tr>
                  )
                  : tsAnalyses.map((ts) => (
                      <tr
                        key={ts.id}
                        onClick={() => setSelectedTs(selectedTs?.id === ts.id ? null : ts)}
                        style={{ cursor: "pointer" }}
                        onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.02)"}
                        onMouseLeave={(e) => e.currentTarget.style.background = selectedTs?.id === ts.id ? "rgba(59,130,246,0.04)" : "transparent"}
                      >
                        <td style={{ ...tdS, fontWeight: 500 }}>{ts.name}</td>
                        <td style={tdS}><Badge color="#9ca3af">{ts.analysis_type_display || ts.analysis_type}</Badge></td>
                        <td style={{ ...tdS, color: "#9ca3af", fontSize: 12 }}>{ts.location_name || "—"}</td>
                        <td style={tdS}>
                          <Badge color={TREND_COLORS[ts.trend_direction] || "#6b7280"}>
                            {ts.trend_direction || "—"}
                          </Badge>
                        </td>
                        <td style={tdS}>
                          {ts.has_seasonality
                            ? <Badge color="#3b82f6">Yes{ts.seasonal_period ? ` (${ts.seasonal_period}d)` : ""}</Badge>
                            : <Badge color="#6b7280">No</Badge>
                          }
                        </td>
                        <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 11 }}>
                          {ts.mae != null ? Number(ts.mae).toFixed(2) : "—"}
                        </td>
                        <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 11 }}>
                          {ts.rmse != null ? Number(ts.rmse).toFixed(2) : "—"}
                        </td>
                        <td style={tdS}>
                          {ts.has_forecast
                            ? <Badge color="#10b981">✓{ts.forecast_horizon ? ` ${ts.forecast_horizon}d` : ""}</Badge>
                            : <Badge color="#6b7280">—</Badge>
                          }
                        </td>
                        <td style={{ ...tdS, color: "#9ca3af", fontSize: 11 }}>
                          {ts.start_date && ts.end_date ? `${ts.start_date} → ${ts.end_date}` : "—"}
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>
          </div>

          {/* Expanded time-series detail */}
          {selectedTs && (
            <div style={{ marginTop: 16, background: "#111827", border: "1px solid #1f2937", borderRadius: 6, padding: 20 }}>
              <div style={{ fontFamily: "Space Mono, monospace", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b7280", marginBottom: 12 }}>
                {selectedTs.name} — Detail
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12 }}>
                {[
                  { label: "MAE",  value: selectedTs.mae  != null ? Number(selectedTs.mae).toFixed(4)  : "—" },
                  { label: "RMSE", value: selectedTs.rmse != null ? Number(selectedTs.rmse).toFixed(4) : "—" },
                  { label: "MAPE", value: selectedTs.mape != null ? `${Number(selectedTs.mape).toFixed(2)}%` : "—" },
                  { label: "Trend Strength", value: selectedTs.trend_strength != null ? Number(selectedTs.trend_strength).toFixed(4) : "—" },
                ].map(({ label, value }) => (
                  <div key={label} style={{ background: "#151e2e", borderRadius: 4, padding: "12px 16px" }}>
                    <div style={{ fontFamily: "Space Mono, monospace", fontSize: 9, textTransform: "uppercase", color: "#6b7280", marginBottom: 6 }}>{label}</div>
                    <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 24, color: "#f9fafb" }}>{value}</div>
                  </div>
                ))}
              </div>
              {selectedTs.description && (
                <div style={{ marginTop: 14, fontSize: 13, color: "#9ca3af", lineHeight: 1.6 }}>
                  {selectedTs.description}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ────────────────────────────────────────────────────────────────────── */}
      {/* SPATIAL TAB                                                             */}
      {/* ────────────────────────────────────────────────────────────────────── */}
      {activeTab === "SPATIAL" && (
        <div style={fadeUp(0)}>
          {spatError && <div style={{ color: "#ef4444", fontSize: 13, marginBottom: 16 }}>{spatError}</div>}

          {spatLoading ? (
            <div style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 6, padding: 24 }}>
              {Array.from({ length: 4 }).map((_, i) => <Shimmer key={i} height={24} />)}
            </div>
          ) : spatialList.length === 0 ? (
            <div style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 6, padding: 32, textAlign: "center", color: "#6b7280", fontSize: 13 }}>
              No spatial analyses found for disease code <strong>{model.disease_code}</strong>.
            </div>
          ) : (
            <>
              {/* Spatial Analysis List */}
              <div style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 6, overflow: "hidden", marginBottom: 16 }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      {["Name","Type","Location","Moran's I","P-Value","Significant","Hotspots","Clusters","Period"].map((h) => (
                        <th key={h} style={thS}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {spatialList.map((s) => (
                      <tr
                        key={s.id}
                        onClick={() => setSelectedSpat(selectedSpat?.id === s.id ? null : s)}
                        style={{ cursor: "pointer" }}
                        onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.02)"}
                        onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                      >
                        <td style={{ ...tdS, fontWeight: 500 }}>{s.name}</td>
                        <td style={tdS}><Badge color="#9ca3af">{s.analysis_type_display || s.analysis_type}</Badge></td>
                        <td style={{ ...tdS, color: "#9ca3af", fontSize: 12 }}>{s.location_name || "—"}</td>
                        <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 11, color: s.morans_i != null && Number(s.morans_i) >= 0 ? "#3b82f6" : "#ef4444" }}>
                          {s.morans_i != null ? Number(s.morans_i).toFixed(4) : "—"}
                        </td>
                        <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 11 }}>
                          {s.p_value != null ? Number(s.p_value).toFixed(4) : "—"}
                        </td>
                        <td style={tdS}>
                          {s.is_significant === true
                            ? <Badge color="#10b981">Yes</Badge>
                            : s.is_significant === false
                            ? <Badge color="#6b7280">No</Badge>
                            : <Badge color="#6b7280">—</Badge>
                          }
                        </td>
                        <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 12 }}>{s.hotspot_count ?? "—"}</td>
                        <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 12 }}>{s.cluster_count ?? "—"}</td>
                        <td style={{ ...tdS, color: "#9ca3af", fontSize: 11 }}>
                          {s.start_date && s.end_date ? `${s.start_date} → ${s.end_date}` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Selected spatial — hotspot detail */}
              {selectedSpat && (
                <div style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 6, padding: 20 }}>
                  <div style={{ fontFamily: "Space Mono, monospace", fontSize: 9, letterSpacing: "0.12em", textTransform: "uppercase", color: "#6b7280", marginBottom: 16 }}>
                    {selectedSpat.name} — Hotspot Detail
                  </div>

                  {/* Moran's I hero + metrics */}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 16 }}>
                    <div style={{ background: "#151e2e", borderRadius: 4, padding: "16px 20px" }}>
                      <div style={{ fontFamily: "Space Mono, monospace", fontSize: 9, textTransform: "uppercase", color: "#6b7280", marginBottom: 8 }}>Moran's I</div>
                      <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 36, color: selectedSpat.morans_i != null && Number(selectedSpat.morans_i) >= 0 ? "#3b82f6" : "#ef4444" }}>
                        {selectedSpat.morans_i != null ? Number(selectedSpat.morans_i).toFixed(4) : "—"}
                      </div>
                    </div>
                    {[
                      { label: "Z-Score",  value: selectedSpat.z_score  != null ? Number(selectedSpat.z_score).toFixed(4)  : "—" },
                      { label: "Hotspots", value: selectedSpat.hotspot_count ?? "—" },
                      { label: "Clusters", value: selectedSpat.cluster_count  ?? "—" },
                    ].map(({ label, value }) => (
                      <div key={label} style={{ background: "#151e2e", borderRadius: 4, padding: "16px 20px" }}>
                        <div style={{ fontFamily: "Space Mono, monospace", fontSize: 9, textTransform: "uppercase", color: "#6b7280", marginBottom: 8 }}>{label}</div>
                        <div style={{ fontFamily: "Bebas Neue, sans-serif", fontSize: 36, color: "#f9fafb" }}>{value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Hotspots table */}
                  {Array.isArray(selectedSpat.hotspots) && selectedSpat.hotspots.length > 0 && (
                    <div style={{ border: "1px solid #1f2937", borderRadius: 4, overflow: "hidden" }}>
                      <div style={{ padding: "10px 14px", borderBottom: "1px solid #1f2937" }}>
                        <span style={{ fontFamily: "Space Mono, monospace", fontSize: 9, textTransform: "uppercase", color: "#6b7280" }}>
                          Hotspot Points ({selectedSpat.hotspots.length})
                        </span>
                      </div>
                      <table style={{ width: "100%", borderCollapse: "collapse" }}>
                        <thead>
                          <tr>
                            {["Index","Coordinates","Value","Z-Score","P-Value"].map((h) => <th key={h} style={thS}>{h}</th>)}
                          </tr>
                        </thead>
                        <tbody>
                          {selectedSpat.hotspots.slice(0, 20).map((hs, i) => (
                            <tr key={i}>
                              <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 11 }}>{hs.index ?? i}</td>
                              <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 11, color: "#9ca3af" }}>
                                {Array.isArray(hs.coordinates) ? hs.coordinates.map((c) => Number(c).toFixed(4)).join(", ") : "—"}
                              </td>
                              <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 11 }}>
                                {hs.value != null ? Number(hs.value).toFixed(2) : "—"}
                              </td>
                              <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 11, color: "#ef4444" }}>
                                {hs.z_score != null ? Number(hs.z_score).toFixed(4) : "—"}
                              </td>
                              <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 11 }}>
                                {hs.p_value != null ? Number(hs.p_value).toFixed(4) : "—"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ────────────────────────────────────────────────────────────────────── */}
      {/* REPORTS TAB                                                             */}
      {/* ────────────────────────────────────────────────────────────────────── */}
      {activeTab === "REPORTS" && (
        <div style={fadeUp(0)}>
          {rError && <div style={{ color: "#ef4444", fontSize: 13, marginBottom: 16 }}>{rError}</div>}

          <div style={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 6, overflow: "hidden" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Title","Type","Author","Period","Status","Published At",""].map((h) => (
                    <th key={h} style={thS}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rLoading
                  ? Array.from({ length: 5 }).map((_, i) => (
                      <tr key={i}>
                        {Array.from({ length: 7 }).map((_, j) => <td key={j} style={tdS}><Shimmer /></td>)}
                      </tr>
                    ))
                  : reports.length === 0
                  ? (
                    <tr>
                      <td colSpan={7} style={{ ...tdS, textAlign: "center", color: "#6b7280", padding: 32 }}>
                        No statistical reports found.
                      </td>
                    </tr>
                  )
                  : reports.map((r) => (
                      <tr
                        key={r.id}
                        onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.02)"}
                        onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                      >
                        <td style={{ ...tdS, fontWeight: 500 }}>{r.title || "—"}</td>
                        <td style={tdS}><Badge color="#9ca3af">{r.report_type || "—"}</Badge></td>
                        <td style={{ ...tdS, color: "#9ca3af", fontSize: 12 }}>{r.author_username || "—"}</td>
                        <td style={{ ...tdS, fontFamily: "Space Mono, monospace", fontSize: 11, color: "#9ca3af" }}>
                          {r.start_date && r.end_date ? `${r.start_date} – ${r.end_date}` : "—"}
                        </td>
                        <td style={tdS}>
                          {r.is_published
                            ? <Badge color="#10b981">Published</Badge>
                            : <Badge color="#6b7280">Draft</Badge>
                          }
                        </td>
                        <td style={{ ...tdS, fontSize: 12, color: "#9ca3af" }}>
                          {r.published_at ? new Date(r.published_at).toLocaleDateString() : "—"}
                        </td>
                        <td style={tdS}>
                          <button
                            type="button"
                            onClick={() => analyticsApi.downloadStatReport(r.id)
                              .then((res) => {
                                const url = URL.createObjectURL(new Blob([res.data]));
                                const a   = document.createElement("a");
                                a.href    = url;
                                a.download = `${r.title || "report"}.pdf`;
                                a.click();
                                URL.revokeObjectURL(url);
                              })
                              .catch(e => { if (import.meta.env.DEV) console.error('[AnalyticsDetail] Download failed:', e); toast.error('Download failed. Please try again.') })
                            }
                            style={{ background: "#1f2937", color: "#f9fafb", border: "none", borderRadius: 4, padding: "5px 12px", fontSize: 12, cursor: "pointer", fontFamily: "IBM Plex Sans, sans-serif" }}
                          >
                            Download
                          </button>
                        </td>
                      </tr>
                    ))}
              </tbody>
            </table>

            {/* Pagination */}
            {rTotalPages > 1 && (
              <div style={{ padding: "12px 20px", borderTop: "1px solid #1f2937", display: "flex", gap: 8, alignItems: "center", justifyContent: "flex-end" }}>
                <button
                  disabled={rPage === 1}
                  onClick={() => setRPage((p) => p - 1)}
                  style={{ background: rPage === 1 ? "#151e2e" : "#1f2937", color: rPage === 1 ? "#6b7280" : "#f9fafb", border: "none", borderRadius: 4, padding: "6px 14px", fontSize: 12, cursor: rPage === 1 ? "default" : "pointer", fontFamily: "IBM Plex Sans, sans-serif" }}
                >
                  Prev
                </button>
                <span style={{ fontFamily: "Space Mono, monospace", fontSize: 10, color: "#6b7280" }}>
                  {rPage} / {rTotalPages}
                </span>
                <button
                  disabled={rPage === rTotalPages}
                  onClick={() => setRPage((p) => p + 1)}
                  style={{ background: rPage === rTotalPages ? "#151e2e" : "#1f2937", color: rPage === rTotalPages ? "#6b7280" : "#f9fafb", border: "none", borderRadius: 4, padding: "6px 14px", fontSize: 12, cursor: rPage === rTotalPages ? "default" : "pointer", fontFamily: "IBM Plex Sans, sans-serif" }}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}