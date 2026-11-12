import { Link } from 'react-router-dom'

const T = { accent: '#3b82f6', text: '#f9fafb', textSub: '#9ca3af', border: '#1f2937' }
const FONTS = {
  heading: "'Bebas Neue', sans-serif",
  mono:    "'Space Mono', monospace",
  body:    "'IBM Plex Sans', sans-serif",
}

export default function NotFound() {
  return (
    <>
      <style>{`@keyframes nf-fadeUp { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }`}</style>
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', minHeight: '60vh', padding: '60px 24px',
        animation: 'nf-fadeUp 0.4s ease', textAlign: 'center',
      }}>
        <div style={{ fontFamily: FONTS.heading, fontSize: 'clamp(80px, 16vw, 160px)', color: 'rgba(59,130,246,0.1)', lineHeight: 1, letterSpacing: '0.04em' }}>
          404
        </div>
        <div style={{ fontFamily: FONTS.heading, fontSize: 30, color: T.text, letterSpacing: '0.06em', marginBottom: 12 }}>PAGE NOT FOUND</div>
        <p style={{ fontFamily: FONTS.body, fontSize: 14, color: T.textSub, lineHeight: 1.7, maxWidth: 380, marginBottom: 36 }}>
          The route you requested does not exist or you may not have permission to access it.
        </p>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
          <Link to="/" style={{
            fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase',
            padding: '10px 22px', borderRadius: 3, background: T.accent, color: '#fff',
            textDecoration: 'none', border: `1px solid ${T.accent}`,
          }}>Go Home</Link>
          <Link to="/login" style={{
            fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase',
            padding: '10px 22px', borderRadius: 3, background: 'transparent', color: T.textSub,
            textDecoration: 'none', border: `1px solid ${T.border}`,
          }}>Sign In</Link>
        </div>
      </div>
    </>
  )
}