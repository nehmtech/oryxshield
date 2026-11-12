const T = {
  bg: '#0a0f1e', surface: '#111827', surfaceHigh: '#151e2e',
  border: '#1f2937', accent: '#3b82f6', text: '#f9fafb', textSub: '#9ca3af',
}
const FONTS = {
  heading: "'Bebas Neue', sans-serif",
  mono:    "'Space Mono', monospace",
  body:    "'IBM Plex Sans', sans-serif",
}

const CAPABILITIES = [
  {
    label: 'Disease Surveillance',
    desc: 'Ingest structured health data from authorised field workers and facilities. Automated anomaly detection flags unusual case patterns within minutes of data submission.',
  },
  {
    label: 'Risk Assessment',
    desc: 'Location- and disease-specific risk scores are computed continuously. Configurable thresholds trigger alerts when scores cross critical levels.',
  },
  {
    label: 'Alert Management',
    desc: 'Multi-tier alert lifecycle — ACTIVE → ACKNOWLEDGED → INVESTIGATING → RESOLVED → CLOSED — with audit trails, bulk operations, and escalation tracking.',
  },
  {
    label: 'Response Coordination',
    desc: 'Activate formal response protocols, assign action items across agencies, and track completion. Coordination teams are linked directly to active response activations.',
  },
  {
    label: 'Contact Tracing & Case Management',
    desc: 'Record confirmed cases, map exposure contacts, schedule follow-up appointments, and manage quarantine facility assignments and transfers.',
  },
  {
    label: 'Vaccination Tracking',
    desc: 'Define vaccination campaigns, log individual dose records, and monitor coverage progress in real time against target populations.',
  },
  {
    label: 'Communications',
    desc: 'Send templated messages via SMS, email, or push notification. Manage broadcast campaigns, public announcements, and collect field feedback.',
  },
  {
    label: 'Analytics & Forecasting',
    desc: 'SIR/SEIR epidemiological models, ARIMA time-series forecasting, spatial hotspot detection, cluster identification, and configurable dashboards.',
  },
  {
    label: 'External Integrations',
    desc: 'Bidirectional data exchange with DHIS2, SORMAS, Africa CDC, and WHO EIOS via a managed integration job engine with webhook support.',
  },
]


export default function About() {
  return (
    <>
      <style>{`
        @keyframes ab-fadeUp { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
        @media (max-width: 700px) {
          .ab-cap-grid  { grid-template-columns: 1fr !important; }
          .ab-mission-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>

      {/* Hero */}
      <section style={{ maxWidth: 1160, margin: '0 auto', padding: '80px 24px 60px', animation: 'ab-fadeUp 0.4s ease' }}>
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase', color: T.textSub, marginBottom: 10 }}>
          About the Platform
        </div>
        <h1 style={{ fontFamily: FONTS.heading, fontSize: 'clamp(44px, 7vw, 80px)', color: T.text, margin: '0 0 24px', letterSpacing: '0.03em', lineHeight: 1 }}>
          ORYXSHIELD<br /><span style={{ color: T.accent }}>PROTOCOL</span>
        </h1>
        <p style={{ fontFamily: FONTS.body, fontSize: 16, color: T.textSub, lineHeight: 1.8, maxWidth: 660, margin: 0 }}>
          OryxShield is an integrated public health surveillance and outbreak response platform developed by NEHMTECH Innovations Limited. The system is designed to give public health authorities the tools to detect disease events early, assess risk, coordinate multi-agency responses, and communicate with the field — all within a single platform. It is currently in active development.
        </p>
      </section>

      {/* Mission / Approach */}
      <section style={{ background: T.surface, borderTop: `1px solid ${T.border}`, borderBottom: `1px solid ${T.border}` }}>
        <div className="ab-mission-grid" style={{ maxWidth: 1160, margin: '0 auto', padding: '64px 24px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 48 }}>
          <div>
            <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.16em', textTransform: 'uppercase', color: T.textSub, marginBottom: 12 }}>Mission</div>
            <h2 style={{ fontFamily: FONTS.heading, fontSize: 30, color: T.text, margin: '0 0 16px', letterSpacing: '0.04em' }}>ZERO PREVENTABLE OUTBREAK DEATHS</h2>
            <p style={{ fontFamily: FONTS.body, fontSize: 14, color: T.textSub, lineHeight: 1.8, margin: 0 }}>
              With the right information infrastructure, public health teams can detect and contain outbreaks before they become crises. Every feature in this platform traces directly to that goal — from sub-minute anomaly detection to cross-agency task coordination.
            </p>
          </div>
          <div>
            <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.16em', textTransform: 'uppercase', color: T.textSub, marginBottom: 12 }}>Scope</div>
            <h2 style={{ fontFamily: FONTS.heading, fontSize: 30, color: T.text, margin: '0 0 16px', letterSpacing: '0.04em' }}>END-TO-END RESPONSE PIPELINE</h2>
            <p style={{ fontFamily: FONTS.body, fontSize: 14, color: T.textSub, lineHeight: 1.8, margin: 0 }}>
              OryxShield covers the full outbreak response lifecycle: data ingestion, surveillance, risk scoring, alerting, response activation, coordination, contact tracing, vaccination, communications, analytics, and external system integration — built as a unified system, not a collection of disconnected tools.
            </p>
          </div>
        </div>
      </section>

      {/* Capabilities */}
      <section style={{ maxWidth: 1160, margin: '0 auto', padding: '72px 24px' }}>
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase', color: T.textSub, marginBottom: 8 }}>What It Does</div>
        <h2 style={{ fontFamily: FONTS.heading, fontSize: 38, color: T.text, margin: '0 0 40px', letterSpacing: '0.04em' }}>PLATFORM CAPABILITIES</h2>

        <div className="ab-cap-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14 }}>
          {CAPABILITIES.map((item, i) => (
            <div key={i} style={{ background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 5, padding: '20px 20px' }}>
              <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.accent, marginBottom: 10 }}>{item.label}</div>
              <p style={{ fontFamily: FONTS.body, fontSize: 13, color: T.textSub, lineHeight: 1.7, margin: 0 }}>{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

    </>
  )
}
