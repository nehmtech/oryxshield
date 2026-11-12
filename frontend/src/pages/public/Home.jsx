import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { communicationsApi } from '../../services/api'
import { useAuth } from '../../context/AuthContext'

const T = {
  bg: '#0a0f1e', surface: '#111827', surfaceHigh: '#151e2e',
  border: '#1f2937', accent: '#3b82f6', danger: '#ef4444',
  warning: '#f59e0b', success: '#10b981', text: '#f9fafb', textSub: '#9ca3af',
}
const FONTS = {
  heading: "'Bebas Neue', sans-serif",
  mono:    "'Space Mono', monospace",
  body:    "'IBM Plex Sans', sans-serif",
}

const STATS = [
  { value: '14',    unit: 'Regions',     label: 'Nationwide coverage across all Namibian regions'    },
  { value: '2.4M',  unit: 'Data Points',  label: 'Epidemiological records processed daily'            },
  { value: '< 90s', unit: 'Alert Time',   label: 'From anomaly detection to first responder notify'  },
  { value: '99.7%', unit: 'Uptime',       label: 'System availability over trailing 12 months'        },
]

const FEATURES = [
  { icon: '⬡', title: 'Real-Time Surveillance',   body: 'Continuous ingestion from hospitals, labs, and community health workers. Anomaly detection fires before outbreaks escalate.' },
  { icon: '◈', title: 'Predictive Risk Scoring',   body: 'SIR/SEIR epidemiological models with ML overlays. Risk scores updated every two minutes across geographic clusters.' },
  { icon: '▣', title: 'Multi-Agency Coordination', body: 'Unified task management, meeting scheduling, and information products across health agencies and response teams.' },
  { icon: '◉', title: 'Multi-Channel Alerts',       body: 'SMS, email, push, and social media broadcasts — in English, Afrikaans, Oshiwambo, Herero, Damara/Nama, and Kavango.' },
  { icon: '⬘', title: 'Resource Intelligence',      body: 'Live inventory tracking, demand forecasting, and automated procurement requests across all linked facilities.' },
  { icon: '◧', title: 'Field Operations',            body: 'Case management, contact tracing, vaccination campaigns, and quarantine facility management in a single workflow.' },
]

const INTEGRATIONS = ['DHIS2', 'SORMAS', 'WHO EIOS', 'Africa CDC', 'OpenFDA', 'Mapbox', "Africa's Talking"]

const ANN_COLORS = {
  ALERT:   { color: '#ef4444', bg: 'rgba(239,68,68,0.1)',   border: 'rgba(239,68,68,0.25)'   },
  WARNING: { color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',  border: 'rgba(245,158,11,0.25)'  },
  INFO:    { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)',  border: 'rgba(59,130,246,0.25)'  },
  ADVISORY:{ color: '#a78bfa', bg: 'rgba(167,139,250,0.1)', border: 'rgba(167,139,250,0.25)' },
  PRESS:   { color: '#34d399', bg: 'rgba(52,211,153,0.1)',  border: 'rgba(52,211,153,0.25)'  },
  default: { color: '#9ca3af', bg: 'rgba(156,163,175,0.1)', border: 'rgba(156,163,175,0.25)' },
}
function annColor(type) { return ANN_COLORS[type] || ANN_COLORS.default }

function AnnouncementBanner({ announcements }) {
  if (!announcements.length) return null
  return (
    <div style={{ background: T.surface, borderBottom: `1px solid ${T.border}`, padding: '10px 0' }}>
      <div style={{ maxWidth: 1160, margin: '0 auto', padding: '0 24px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {announcements.slice(0, 3).map(ann => {
          const c = annColor(ann.announcement_type)
          return (
            <div key={ann.id} style={{
              display: 'flex', alignItems: 'flex-start', gap: 10,
              background: c.bg, border: `1px solid ${c.border}`,
              borderRadius: 3, padding: '9px 14px',
            }}>
              <span style={{ fontFamily: FONTS.mono, fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: c.color, paddingTop: 2, whiteSpace: 'nowrap' }}>
                {ann.announcement_type || 'NOTICE'}
              </span>
              <span style={{ fontFamily: FONTS.body, fontSize: 13, color: T.text, lineHeight: 1.5 }}>
                <strong>{ann.title}</strong>{ann.summary ? ` — ${ann.summary}` : ''}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function Home() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  const [announcements, setAnnouncements] = useState([])
  const [annLoading,    setAnnLoading]    = useState(true)

  useEffect(() => {
    ;(async () => {
      try {
        const res = await communicationsApi.publishedAnnouncements({ page_size: 3 })
        setAnnouncements(res.data.results ?? [])
      } catch {
        // Non-critical — page renders without announcements
      } finally {
        setAnnLoading(false)
      }
    })()
  }, [])

  // ── Auth-aware hero CTA ────────────────────────────────────────────────────
  // While loading, show nothing to avoid button flash
  const heroCTA = loading ? null : user ? (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      <Link to="/dashboard" style={{
        fontFamily: FONTS.mono, fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase',
        padding: '13px 28px', borderRadius: 3, background: T.accent, color: '#fff',
        textDecoration: 'none', fontWeight: 600, border: `1px solid ${T.accent}`,
      }}>
        Go to Dashboard →
      </Link>
      <Link to="/about" className="hp-btn-sec" style={{
        fontFamily: FONTS.mono, fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase',
        padding: '13px 28px', borderRadius: 3, background: 'transparent', color: T.textSub,
        textDecoration: 'none', border: `1px solid ${T.border}`, transition: 'all 0.15s',
      }}>
        Learn More
      </Link>
    </div>
  ) : (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      <Link to="/login" style={{
        fontFamily: FONTS.mono, fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase',
        padding: '13px 28px', borderRadius: 3, background: T.accent, color: '#fff',
        textDecoration: 'none', fontWeight: 600, border: `1px solid ${T.accent}`,
      }}>
        Access Platform
      </Link>
      <Link to="/about" className="hp-btn-sec" style={{
        fontFamily: FONTS.mono, fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase',
        padding: '13px 28px', borderRadius: 3, background: 'transparent', color: T.textSub,
        textDecoration: 'none', border: `1px solid ${T.border}`, transition: 'all 0.15s',
      }}>
        Learn More
      </Link>
    </div>
  )

  // ── Auth-aware bottom CTA ──────────────────────────────────────────────────
  const bottomCTA = loading ? null : user ? (
    <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
      <Link to="/dashboard" style={{
        fontFamily: FONTS.mono, fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase',
        padding: '13px 28px', borderRadius: 3, background: T.accent, color: '#fff',
        textDecoration: 'none', border: `1px solid ${T.accent}`, fontWeight: 600,
      }}>
        Open Dashboard →
      </Link>
      <Link to="/contact" className="hp-btn-sec" style={{
        fontFamily: FONTS.mono, fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase',
        padding: '13px 28px', borderRadius: 3, background: 'transparent', color: T.textSub,
        textDecoration: 'none', border: `1px solid ${T.border}`, transition: 'all 0.15s',
      }}>
        Contact Us
      </Link>
    </div>
  ) : (
    <div style={{ display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap' }}>
      <Link to="/login" style={{
        fontFamily: FONTS.mono, fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase',
        padding: '13px 28px', borderRadius: 3, background: T.accent, color: '#fff',
        textDecoration: 'none', border: `1px solid ${T.accent}`, fontWeight: 600,
      }}>
        Sign In
      </Link>
      <Link to="/contact" className="hp-btn-sec" style={{
        fontFamily: FONTS.mono, fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase',
        padding: '13px 28px', borderRadius: 3, background: 'transparent', color: T.textSub,
        textDecoration: 'none', border: `1px solid ${T.border}`, transition: 'all 0.15s',
      }}>
        Contact Us
      </Link>
    </div>
  )

  return (
    <>
      <style>{`
        @keyframes hp-fadeUp { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }
        @keyframes hp-pulse  { 0%,100%{opacity:1} 50%{opacity:0.4} }
        .hp-feat:hover  { border-color: rgba(59,130,246,0.35) !important; background: #151e2e !important; }
        .hp-btn-sec:hover { border-color: rgba(255,255,255,0.3) !important; color: #f9fafb !important; }
        @media (max-width: 700px) {
          .hp-stats-grid   { grid-template-columns: 1fr 1fr !important; }
          .hp-feature-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>

      {/* Live announcements */}
      {!annLoading && <AnnouncementBanner announcements={announcements} />}

      {/* ── Hero ── */}
      <section style={{ maxWidth: 1160, margin: '0 auto', padding: '96px 24px 72px', animation: 'hp-fadeUp 0.5s ease' }}>
        {/* Welcome back banner for authenticated users */}
        {!loading && user && (
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)',
            borderRadius: 3, padding: '6px 14px', marginBottom: 24,
          }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: T.success }} />
            <span style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.14em', textTransform: 'uppercase', color: T.success }}>
              Welcome back, {user.first_name || user.username || 'operator'}
            </span>
          </div>
        )}

  

        <h1 style={{
          fontFamily: FONTS.heading, fontSize: 'clamp(52px, 8vw, 96px)',
          color: T.text, margin: '0 0 14px', letterSpacing: '0.03em', lineHeight: 1, maxWidth: 820,
        }}>
          PANDEMIC RESPONSE<br /><span style={{ color: T.accent }}>INFRASTRUCTURE</span>
        </h1>

        <p style={{ fontFamily: FONTS.body, fontSize: 16, color: T.textSub, lineHeight: 1.8, maxWidth: 560, margin: '0 0 40px' }}>
          End-to-end surveillance, risk assessment, and multi-agency coordination for public health authorities. Built for Africa, deployed in Namibia.
        </p>

        {heroCTA}
      </section>

      {/* ── Stats ── */}
      <section style={{ borderTop: `1px solid ${T.border}`, borderBottom: `1px solid ${T.border}`, background: T.surface }}>
        <div className="hp-stats-grid" style={{
          maxWidth: 1160, margin: '0 auto', padding: '0 24px',
          display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        }}>
          {STATS.map((s, i) => (
            <div key={i} style={{ padding: '32px 20px', borderRight: i < 3 ? `1px solid ${T.border}` : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 6 }}>
                <span style={{ fontFamily: FONTS.heading, fontSize: 40, color: T.accent, letterSpacing: '0.03em' }}>{s.value}</span>
                <span style={{ fontFamily: FONTS.mono, fontSize: 8, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub }}>{s.unit}</span>
              </div>
              <p style={{ fontFamily: FONTS.body, fontSize: 12, color: T.textSub, margin: 0, lineHeight: 1.65 }}>{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Features ── */}
      <section style={{ maxWidth: 1160, margin: '0 auto', padding: '80px 24px' }}>
        <div style={{ marginBottom: 48 }}>
          <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase', color: T.textSub, marginBottom: 10 }}>Platform Capabilities</div>
          <h2 style={{ fontFamily: FONTS.heading, fontSize: 42, color: T.text, margin: 0, letterSpacing: '0.03em' }}>BUILT FOR OUTBREAK SPEED</h2>
        </div>
        <div className="hp-feature-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
          {FEATURES.map((f, i) => (
            <div key={i} className="hp-feat" style={{
              background: T.surface, border: `1px solid ${T.border}`,
              borderRadius: 5, padding: '28px 24px', transition: 'all 0.2s',
            }}>
              <div style={{ fontFamily: FONTS.mono, fontSize: 18, color: T.accent, marginBottom: 14 }}>{f.icon}</div>
              <div style={{ fontFamily: FONTS.heading, fontSize: 20, color: T.text, letterSpacing: '0.04em', marginBottom: 10 }}>{f.title}</div>
              <p style={{ fontFamily: FONTS.body, fontSize: 13, color: T.textSub, lineHeight: 1.7, margin: 0 }}>{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Integrations ── */}
      <section style={{ background: T.surface, borderTop: `1px solid ${T.border}`, borderBottom: `1px solid ${T.border}` }}>
        <div style={{ maxWidth: 1160, margin: '0 auto', padding: '48px 24px', textAlign: 'center' }}>
          <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase', color: T.textSub, marginBottom: 24 }}>Integrated With</div>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
            {INTEGRATIONS.map(name => (
              <span key={name} style={{
                fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.1em', textTransform: 'uppercase',
                padding: '8px 16px', borderRadius: 3, border: `1px solid ${T.border}`,
                color: T.textSub, background: T.surfaceHigh,
              }}>{name}</span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Bottom CTA ── */}
      <section style={{ maxWidth: 1160, margin: '0 auto', padding: '80px 24px', textAlign: 'center' }}>
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase', color: T.textSub, marginBottom: 16 }}>
          {user ? 'Operations Platform' : 'Authorized Access Only'}
        </div>
        <h2 style={{ fontFamily: FONTS.heading, fontSize: 48, color: T.text, margin: '0 0 16px', letterSpacing: '0.03em' }}>
          {user ? 'READY TO RESPOND?' : 'READY TO RESPOND?'}
        </h2>
        <p style={{ fontFamily: FONTS.body, fontSize: 15, color: T.textSub, lineHeight: 1.7, maxWidth: 500, margin: '0 auto 36px' }}>
          {user
            ? 'Your session is active. Access the operations platform to monitor and respond.'
            : 'Contact your agency administrator to request credentials, or sign in if you already have an account.'
          }
        </p>
        {bottomCTA}
      </section>
    </>
  )
}