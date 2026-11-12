import { useState, useEffect, useRef } from "react";

/* ─────────────────────────────────────────
   DATA
───────────────────────────────────────── */
const PILLARS = [
  {
    icon: "📡",
    tag: "SURVEILLANCE",
    title: "Real-Time Disease Tracking",
    desc: "Continuous monitoring of disease spread, hospitalisations, and mortality across national and global networks. Early signals are detected automatically — before outbreaks become crises.",
    color: "#00FFB2",
  },
  {
    icon: "🛡️",
    tag: "PUBLIC GUIDANCE",
    title: "Preventive Action for Everyone",
    desc: "Clear, actionable everyday guidance delivered to citizens — proper hygiene protocols, mask use, isolation practices, and community-level containment steps that actually work.",
    color: "#FF6B35",
  },
  {
    icon: "🔧",
    tag: "TOOLKITS",
    title: "Preparedness & Infection Control",
    desc: "Operational toolkits for small businesses, healthcare facilities, and field workers. From infection control checklists to surge capacity playbooks — built for the front line.",
    color: "#4ECDC4",
  },
  {
    icon: "⚖️",
    tag: "POLICY & LAW",
    title: "Legal & Regulatory Compliance",
    desc: "Designed around IHR 2005 and international health law. Every protocol is enforceable, auditable, and institutionally compliant — from local clinics to sovereign governments.",
    color: "#FFD93D",
  },
  {
    icon: "🤖",
    tag: "AUTOMATION",
    title: "Intelligent Response Orchestration",
    desc: "Tiered escalation protocols, multi-agency coordination, and AI-driven risk scoring — fully automated. Human oversight where it matters; machine speed everywhere else.",
    color: "#C77DFF",
  },
  {
    icon: "🌍",
    tag: "GLOBAL REACH",
    title: "Cross-Border Coordination",
    desc: "Connected to WHO, Africa CDC, and international reporting pipelines. Built to serve both emerging and developed markets — no health system left without infrastructure.",
    color: "#74B9FF",
  },
];

const STATS = [
  { value: "195", label: "WHO Member States", suffix: "+" },
  { value: "72", label: "Hour Outbreak Detection Window", suffix: "hr" },
  { value: "40", label: "Response Time Reduction", suffix: "%" },
  { value: "0", label: "Tolerance for Systemic Failure", suffix: "%" },
];

const TIMELINE = [
  { phase: "Phase 01", title: "DEPLOY", desc: "Sovereign deployment across national health ministries, public health agencies, and emergency response organisations worldwide." },
  { phase: "Phase 02", title: "LICENCE", desc: "Institutional licensing frameworks built for governments, intergovernmental bodies, NGOs, and international health organisations." },
  { phase: "Phase 03", title: "INSTITUTIONALISE", desc: "OryxShield becomes permanent national health infrastructure for Namibia — not a project with an end date, but a standing sovereign capability." },
];

const WHO_WE_SERVE = [
  { icon: "🏛️", title: "Governments & Ministries", desc: "National health ministries, departments of emergency management, and public health agencies seeking automated, enforceable pandemic response infrastructure." },
  { icon: "🌐", title: "International Organisations", desc: "WHO member bodies, Africa CDC, regional health bodies, and intergovernmental organisations requiring cross-border coordination and IHR-compliant reporting." },
  { icon: "🏥", title: "Healthcare Systems", desc: "Hospitals, clinic networks, and healthcare facility operators needing real-time capacity monitoring, infection control toolkits, and surge planning support." },
  { icon: "🏢", title: "Businesses & Institutions", desc: "Small businesses, schools, and private sector organisations requiring preparedness toolkits, legal compliance guidance, and workforce protection protocols." },
];

const PROBLEMS = [
  { stat: "~$12.5 Trillion", label: "Cost of COVID-19 to the global economy", color: "#FF6B35" },
  { stat: "Millions", label: "Deaths attributable to delayed institutional response", color: "#FFD93D" },
  { stat: "< 30%", label: "WHO member states with adequate IHR core capacities", color: "#C77DFF" },
  { stat: "Weeks", label: "Typical government response lag after initial outbreak signal", color: "#FF6B35" },
];

const PRINCIPLES = [
  { num: "01", title: "Automation over hesitation", desc: "Political delay costs lives. OryxShield removes human bottlenecks from time-critical escalation decisions." },
  { num: "02", title: "Enforceability over guidance", desc: "Recommendations are ignored in a crisis. We build systems that activate protocols automatically, with full legal accountability." },
  { num: "03", title: "Sovereignty over dependency", desc: "Every nation deserves infrastructure it owns and controls. We licence, deploy, and institutionalise — not lock in." },
  { num: "04", title: "Equity over exclusivity", desc: "A health crisis anywhere is a threat everywhere. Our systems are designed to serve Lagos and London equally." },
];

/* ─────────────────────────────────────────
   ANIMATED COUNTER
───────────────────────────────────────── */
function Counter({ target, suffix = "" }) {
  const [val, setVal] = useState(0);
  const ref = useRef(null);
  const done = useRef(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !done.current) {
        done.current = true;
        const n = parseInt(target);
        let c = 0;
        const inc = n / 60;
        const t = setInterval(() => {
          c += inc;
          if (c >= n) { setVal(n); clearInterval(t); }
          else setVal(Math.floor(c));
        }, 30);
      }
    }, { threshold: 0.5 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [target]);
  return <span ref={ref}>{val}{suffix}</span>;
}

/* ─────────────────────────────────────────
   MAIN COMPONENT
───────────────────────────────────────── */
export default function OryxShield() {
  const [scrollY, setScrollY]       = useState(0);
  const [menuOpen, setMenuOpen]     = useState(false);
  const [activePillar, setActivePillar] = useState(null);
  const [activePrinciple, setActivePrinciple] = useState(null);

  useEffect(() => {
    const h = () => setScrollY(window.scrollY);
    window.addEventListener("scroll", h, { passive: true });
    return () => window.removeEventListener("scroll", h);
  }, []);

  const go = (id) => { document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }); setMenuOpen(false); };

  const NAV = ["about", "system", "vision", "who-we-serve", "contact"];

  return (
    <div style={{ background: "#020408", color: "#E8E8E0", overflowX: "hidden", fontFamily: "sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Space+Mono:wght@400;700&family=IBM+Plex+Sans:ital,wght@0,300;0,400;0,500;0,600;1,300&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }

        .bb  { font-family: 'Bebas Neue', sans-serif; }
        .mn  { font-family: 'Space Mono', monospace; }
        .sn  { font-family: 'IBM Plex Sans', sans-serif; }

        /* scanlines */
        #root::before {
          content: '';
          position: fixed; inset: 0; pointer-events: none; z-index: 9998;
          background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,255,178,0.008) 2px, rgba(0,255,178,0.008) 4px);
        }

        /* ticker */
        .tk-wrap { overflow: hidden; background: #00FFB2; padding: 7px 0; }
        .tk-inner { display: inline-flex; gap: 64px; animation: tk 40s linear infinite; white-space: nowrap; }
        @keyframes tk { from{transform:translateX(0)} to{transform:translateX(-50%)} }

        /* nav */
        .nav { position: sticky; top: 0; z-index: 200; display: flex; align-items: center; justify-content: space-between; height: 62px; padding: 0 clamp(16px,4vw,48px); transition: background .3s, border-color .3s; }
        .nav.on { background: rgba(2,4,8,.97); border-bottom: 1px solid rgba(0,255,178,.1); backdrop-filter: blur(12px); }
        .nl  { display: flex; gap: 26px; }
        .nb  { font-family:'Space Mono',monospace; font-size:10px; letter-spacing:.15em; text-transform:uppercase; color:rgba(232,232,224,.88); background:none; border:none; cursor:pointer; transition:color .2s; padding: 4px 0; }
        .nb:hover { color:#00FFB2; }

        /* hamburger */
        .hb { display:none; flex-direction:column; gap:5px; background:none; border:none; cursor:pointer; padding:6px; z-index:201; }
        .hb span { display:block; width:22px; height:2px; background:#E8E8E0; border-radius:1px; transition: transform .3s, opacity .3s; }
        .mm { display:none; flex-direction:column; background:rgba(2,4,8,.99); border-bottom:1px solid rgba(0,255,178,.1); position:sticky; top:62px; z-index:199; }
        .mm.open { display:flex; }
        .ml { font-family:'Space Mono',monospace; font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:rgba(232,232,224,.80); background:none; border:none; border-bottom:1px solid rgba(255,255,255,.05); cursor:pointer; padding:18px clamp(16px,4vw,48px); text-align:left; transition:color .2s, background .2s; }
        .ml:hover { color:#00FFB2; background:rgba(0,255,178,.03); }

        /* grid bg */
        .gbg { background-image: linear-gradient(rgba(0,255,178,.022) 1px, transparent 1px), linear-gradient(90deg, rgba(0,255,178,.022) 1px, transparent 1px); background-size: 60px 60px; }

        /* pill */
        .pill { font-family:'Space Mono',monospace; font-size:9px; letter-spacing:.18em; text-transform:uppercase; padding:3px 11px; border-radius:2px; display:inline-block; }

        /* glow text */
        .glow { text-shadow: 0 0 28px rgba(0,255,178,.5), 0 0 56px rgba(0,255,178,.22); }

        /* pulse dot */
        .pulse { animation: pls 2.2s ease-out infinite; }
        @keyframes pls { 0%{box-shadow:0 0 0 0 rgba(0,255,178,.5)} 70%{box-shadow:0 0 0 12px rgba(0,255,178,0)} 100%{box-shadow:0 0 0 0 rgba(0,255,178,0)} }

        /* blink */
        .blk { animation: blk 1.1s step-end infinite; }
        @keyframes blk { 50%{opacity:0} }

        /* dev badge */
        .dev-badge { display:inline-flex; align-items:center; gap:8px; background:rgba(255,107,53,.1); border:1px solid rgba(255,107,53,.3); padding:5px 14px; border-radius:2px; }

        /* pillar card */
        .pc { border:1px solid rgba(255,255,255,.06); background:#020408; padding:clamp(22px,3vw,38px) clamp(18px,2.5vw,30px); transition: border-color .25s, background .25s, transform .25s; cursor:default; }
        .pc:hover { border-color:rgba(0,255,178,.25); background:rgba(0,255,178,.022); transform:translateY(-3px); }

        /* principle card */
        .prc { border:1px solid rgba(255,255,255,.05); padding:clamp(24px,3vw,36px) clamp(20px,2.5vw,32px); transition: border-color .25s, background .25s; cursor:default; }
        .prc:hover { border-color:rgba(0,255,178,.2); background:rgba(0,255,178,.018); }

        /* serve card */
        .sc { padding:clamp(24px,3vw,36px) clamp(20px,2.5vw,32px); border:1px solid rgba(255,255,255,.05); transition: border-color .25s, background .25s; }
        .sc:hover { border-color:rgba(0,255,178,.2); background:rgba(0,255,178,.018); }

        /* contact link */
        .cl { display:flex; align-items:center; gap:18px; padding:clamp(18px,2.5vw,26px) clamp(18px,3vw,30px); border:1px solid rgba(0,255,178,.12); background:rgba(0,255,178,.016); text-decoration:none; color:inherit; transition: border-color .2s, background .2s; }
        .cl:hover { border-color:rgba(0,255,178,.38); background:rgba(0,255,178,.045); }

        /* divider */
        .div { height:1px; background:rgba(255,255,255,.06); }
        .div-g { height:1px; background:linear-gradient(to right, rgba(0,255,178,.3), transparent); }

        /* section padding */
        .sp { padding: clamp(56px,9vw,110px) clamp(16px,4vw,48px); }
        .mw { max-width:1240px; margin:0 auto; }

        /* scrollbar */
        ::-webkit-scrollbar { width:3px; }
        ::-webkit-scrollbar-track { background:#020408; }
        ::-webkit-scrollbar-thumb { background:#00FFB2; border-radius:2px; }

        /* ── TABLET ≤ 960px ── */
        @media(max-width:960px){
          .nl  { display:none; }
          .hb  { display:flex; }
          .h-2col { grid-template-columns:1fr !important; gap:clamp(28px,5vw,44px) !important; }
          .h-right { border-left:none !important; border-top:1px solid rgba(0,255,178,.12) !important; padding-left:0 !important; padding-top:28px !important; }
          .stats-4 { grid-template-columns:repeat(2,1fr) !important; }
          .p-3col  { grid-template-columns:repeat(2,1fr) !important; }
          .vm-2col { grid-template-columns:1fr !important; gap:44px !important; }
          .phase-3 { grid-template-columns:1fr !important; }
          .phase-3 > div { border-left:none !important; border-top:1px solid rgba(0,255,178,.1) !important; padding-left:0 !important; padding-top:clamp(20px,3vw,28px) !important; }
          .why-2col { grid-template-columns:1fr !important; gap:44px !important; }
          .serve-4 { grid-template-columns:repeat(2,1fr) !important; }
          .contact-2 { grid-template-columns:1fr !important; gap:44px !important; }
          .footer-row { flex-direction:column !important; gap:10px !important; text-align:center; align-items:center !important; }
          .prc-grid { grid-template-columns:repeat(2,1fr) !important; }
        }

        /* ── MOBILE ≤ 560px ── */
        @media(max-width:560px){
          .p-3col  { grid-template-columns:1fr !important; }
          .serve-4 { grid-template-columns:1fr !important; }
          .prc-grid{ grid-template-columns:1fr !important; }
          .stats-4 { grid-template-columns:repeat(2,1fr) !important; }
          .h-btns  { flex-direction:column !important; }
          .h-btns button { width:100% !important; }
          .why-row { flex-wrap:wrap; }
        }
      `}</style>

      {/* ── TICKER ── */}
      <div className="tk-wrap">
        <div className="tk-inner">
          {Array(4).fill(null).map((_,i)=>(
            <span key={i} style={{fontFamily:"'Space Mono',monospace",fontSize:"10px",fontWeight:700,letterSpacing:"0.15em",color:"#020408"}}>
              ◆ ORYXSHIELD — IN DEVELOPMENT &nbsp; ◆ NAMIBIA GOVERNMENT &nbsp; ◆ IHR 2005 ALIGNED &nbsp; ◆ AUTOMATED OUTBREAK RESPONSE &nbsp; ◆ NATIONAL HEALTH INFRASTRUCTURE &nbsp; ◆ AFRICA CDC READY &nbsp; ◆ SOVEREIGN DIGITAL HEALTH &nbsp;
            </span>
          ))}
        </div>
      </div>

      {/* ── NAV ── */}
      <nav className={`nav${scrollY>40?" on":""}`}>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <div className="pulse" style={{width:8,height:8,borderRadius:"50%",background:"#00FFB2",flexShrink:0}} />
          <span className="bb" style={{fontSize:"clamp(13px,2.2vw,19px)",letterSpacing:"0.14em",color:"#00FFB2"}}>ORYXSHIELD</span>
        </div>
        <div className="nl">
          {NAV.map(s=>(
            <button key={s} className="nb" onClick={()=>go(s)}>
              {s==="who-we-serve"?"Who We Serve":s.charAt(0).toUpperCase()+s.slice(1)}
            </button>
          ))}
        </div>
        <button className="hb" onClick={()=>setMenuOpen(o=>!o)} aria-label="Menu">
          <span style={{transform:menuOpen?"rotate(45deg) translateY(7px)":"none"}}/>
          <span style={{opacity:menuOpen?0:1}}/>
          <span style={{transform:menuOpen?"rotate(-45deg) translateY(-7px)":"none"}}/>
        </button>
      </nav>

      {/* ── MOBILE MENU ── */}
      <div className={`mm${menuOpen?" open":""}`}>
        {NAV.map(s=>(
          <button key={s} className="ml" onClick={()=>go(s)}>
            {s==="who-we-serve"?"Who We Serve":s.charAt(0).toUpperCase()+s.slice(1)}
          </button>
        ))}
      </div>

      {/* ══════════════════════
          HERO
      ══════════════════════ */}
      <section id="about" className="gbg" style={{minHeight:"100svh",display:"flex",flexDirection:"column",justifyContent:"center",padding:"clamp(60px,9vw,110px) clamp(16px,4vw,48px) 60px",position:"relative",overflow:"hidden"}}>
        {/* decorative circles */}
        <div style={{position:"absolute",right:"-10%",top:"50%",transform:"translateY(-50%)",width:"clamp(280px,45vw,560px)",height:"clamp(280px,45vw,560px)",borderRadius:"50%",border:"1px solid rgba(0,255,178,.04)",pointerEvents:"none"}}/>
        <div style={{position:"absolute",right:"-4%",top:"50%",transform:"translateY(-50%)",width:"clamp(180px,28vw,360px)",height:"clamp(180px,28vw,360px)",borderRadius:"50%",border:"1px solid rgba(0,255,178,.07)",pointerEvents:"none"}}/>

        <div className="mw" style={{width:"100%"}}>
          {/* dev badge */}
          <div style={{marginBottom:"clamp(20px,3vw,32px)",display:"flex",alignItems:"center",gap:12,flexWrap:"wrap"}}>
            <div className="dev-badge">
              <span className="blk" style={{color:"#FF6B35",fontSize:10}}>●</span>
              <span className="mn" style={{fontSize:"9px",letterSpacing:"0.18em",color:"#FF6B35",textTransform:"uppercase"}}>System In Development</span>
            </div>
            <span className="pill" style={{background:"rgba(0,255,178,.08)",color:"#00FFB2",border:"1px solid rgba(0,255,178,.18)"}}>Coming Soon</span>
          </div>

          {/* headline */}
          <h1 className="bb" style={{fontSize:"clamp(52px,13vw,164px)",lineHeight:0.88,color:"#E8E8E0"}}>ORYX</h1>
          <h1 className="bb glow" style={{fontSize:"clamp(52px,13vw,164px)",lineHeight:0.88,color:"#00FFB2",marginBottom:"clamp(8px,1.5vw,16px)"}}>SHIELD</h1>
          <p className="bb" style={{fontSize:"clamp(18px,3.5vw,40px)",color:"rgba(232,232,224,.80)",letterSpacing:"0.08em",marginBottom:"clamp(24px,4vw,48px)"}}>NAMIBIA GOVERNMENT HEALTH SURVEILLANCE</p>

          {/* two col */}
          <div className="h-2col" style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"clamp(28px,6vw,64px)",alignItems:"start"}}>
            <div>
              <p className="sn" style={{fontSize:"clamp(14px,1.8vw,18px)",lineHeight:1.78,color:"rgba(232,232,224,.85)",fontWeight:300,maxWidth:520}}>
                OryxShield is Namibia's national health surveillance platform — built to eliminate the systemic failures that turn disease outbreaks into national crises. It automates the decisions that save lives and institutionalises the protocols that keep communities safe.
              </p>
              <div className="h-btns" style={{display:"flex",gap:12,marginTop:"clamp(22px,3.5vw,36px)",flexWrap:"wrap"}}>
                <button onClick={()=>go("system")} style={{background:"#00FFB2",color:"#020408",padding:"13px clamp(18px,3vw,32px)",fontFamily:"'Space Mono',monospace",fontSize:"10px",letterSpacing:"0.15em",textTransform:"uppercase",border:"none",cursor:"pointer",fontWeight:700,whiteSpace:"nowrap"}}>
                  Explore System →
                </button>
                <button onClick={()=>go("contact")} style={{background:"transparent",color:"#E8E8E0",padding:"13px clamp(18px,3vw,32px)",fontFamily:"'Space Mono',monospace",fontSize:"10px",letterSpacing:"0.15em",textTransform:"uppercase",border:"1px solid rgba(232,232,224,.74)",cursor:"pointer",whiteSpace:"nowrap"}}>
                  Get In Touch
                </button>
              </div>
            </div>
            <div className="h-right" style={{borderLeft:"1px solid rgba(0,255,178,.12)",paddingLeft:"clamp(22px,4vw,56px)"}}>
              <p className="mn" style={{fontSize:"9px",letterSpacing:"0.18em",color:"rgba(0,255,178,.4)",marginBottom:20,textTransform:"uppercase"}}>// About the Company</p>
              <p className="sn" style={{fontSize:"clamp(13px,1.5vw,15px)",lineHeight:1.82,color:"rgba(232,232,224,.80)",fontWeight:300,marginBottom:24}}>
                OryxShield is the national public health surveillance and outbreak response platform developed by NEHMTECH INNOVATIONS LIMITED for the Government of Namibia. Built to automate disease detection, risk assessment, and coordinated emergency response at the national level.
              </p>
              <div style={{display:"flex",flexDirection:"column",gap:12}}>
                {[
                  {label:"Headquarters", val:"Windhoek, Namibia"},
                  {label:"Coverage Scope", val:"Namibia — 14 Regions"},
                  {label:"Regulatory Alignment", val:"IHR 2005 · Africa CDC · WHO"},
                  {label:"System Status", val:"In Active Development"},
                ].map((r,i)=>(
                  <div key={i} style={{display:"flex",justifyContent:"space-between",gap:12,paddingBottom:10,borderBottom:"1px solid rgba(255,255,255,.05)",flexWrap:"wrap"}}>
                    <span className="mn" style={{fontSize:"9px",color:"rgba(232,232,224,.60)",letterSpacing:"0.1em",textTransform:"uppercase"}}>{r.label}</span>
                    <span className="sn" style={{fontSize:"12px",color:"rgba(232,232,224,.7)",fontWeight:500}}>{r.val}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* scroll cue */}
        <div style={{position:"absolute",bottom:28,left:"50%",transform:"translateX(-50%)",display:"flex",flexDirection:"column",alignItems:"center",gap:6,opacity:.28}}>
          <span className="mn" style={{fontSize:"8px",letterSpacing:"0.2em"}}>SCROLL</span>
          <div style={{width:1,height:34,background:"linear-gradient(to bottom,#00FFB2,transparent)"}}/>
        </div>
      </section>

      {/* ══════════════════════
          STATS
      ══════════════════════ */}
      <div style={{background:"rgba(0,255,178,.025)",borderTop:"1px solid rgba(0,255,178,.1)",borderBottom:"1px solid rgba(0,255,178,.1)",padding:"clamp(28px,5vw,52px) clamp(16px,4vw,48px)"}}>
        <div className="stats-4 mw" style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:"clamp(8px,2vw,24px)"}}>
          {STATS.map((s,i)=>(
            <div key={i} style={{textAlign:"center",padding:"clamp(16px,2vw,20px) 8px"}}>
              <div className="bb glow" style={{fontSize:"clamp(38px,6.5vw,68px)",color:"#00FFB2",lineHeight:1}}>
                <Counter target={s.value} suffix={s.suffix}/>
              </div>
              <p className="mn" style={{fontSize:"9px",letterSpacing:"0.14em",color:"rgba(232,232,224,.62)",textTransform:"uppercase",marginTop:8,lineHeight:1.5}}>{s.label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ══════════════════════
          THE PROBLEM
      ══════════════════════ */}
      <section style={{padding:"clamp(56px,9vw,110px) clamp(16px,4vw,48px)",background:"rgba(255,107,53,.018)",borderBottom:"1px solid rgba(255,107,53,.08)"}}>
        <div className="mw">
          <div className="why-2col" style={{display:"grid",gridTemplateColumns:"5fr 7fr",gap:"clamp(36px,7vw,88px)",alignItems:"center"}}>
            <div>
              <span className="pill" style={{background:"rgba(255,107,53,.1)",color:"#FF6B35",marginBottom:20,display:"inline-block"}}>// The Problem</span>
              <h2 className="bb" style={{fontSize:"clamp(36px,6.5vw,72px)",lineHeight:0.94,marginBottom:20}}>
                THE WORLD KEEPS<br/><span style={{color:"#FF6B35"}}>FAILING FORWARD</span>
              </h2>
              <div style={{width:48,height:3,background:"#FF6B35",marginBottom:20}}/>
              <p className="sn" style={{fontSize:"clamp(13px,1.5vw,15px)",lineHeight:1.82,color:"rgba(232,232,224,.78)",fontWeight:300}}>
                Every major pandemic in modern history — from SARS to Ebola to COVID-19 — has exposed the same architectural failure: health systems built on manual processes, political gatekeeping, and disconnected agencies. The result is always the same. Lives lost. Economies shattered. And the same promises made to do better next time.
              </p>
              <p className="sn" style={{fontSize:"clamp(13px,1.5vw,15px)",lineHeight:1.82,color:"rgba(232,232,224,.78)",fontWeight:300,marginTop:16}}>
                OryxShield exists because "next time" is not a strategy.
              </p>
            </div>
            <div style={{display:"flex",flexDirection:"column",gap:0}}>
              {PROBLEMS.map((p,i)=>(
                <div key={i} className="why-row" style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"clamp(14px,2vw,22px) 0",borderBottom:"1px solid rgba(255,255,255,.06)",gap:16,flexWrap:"wrap"}}>
                  <span className="sn" style={{fontSize:"clamp(11px,1.3vw,13px)",color:"rgba(232,232,224,.73)",fontWeight:300,flex:1,minWidth:160}}>{p.label}</span>
                  <span className="bb" style={{fontSize:"clamp(22px,3.2vw,32px)",color:p.color,whiteSpace:"nowrap"}}>{p.stat}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════
          SIX PILLARS
      ══════════════════════ */}
      <section id="system" className="sp">
        <div className="mw">
          <div style={{marginBottom:"clamp(36px,6vw,60px)"}}>
            <span className="pill" style={{background:"rgba(255,255,255,.04)",color:"rgba(232,232,224,.62)",marginBottom:14,display:"inline-block"}}>// What We Build</span>
            <h2 className="bb" style={{fontSize:"clamp(36px,7vw,82px)",lineHeight:0.94}}>
              SIX PILLARS OF<br/><span style={{color:"#00FFB2"}}>TOTAL RESPONSE</span>
            </h2>
          </div>
          <div className="p-3col" style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:1,background:"rgba(255,255,255,.055)"}}>
            {PILLARS.map((f,i)=>(
              <div key={i} className="pc" onMouseEnter={()=>setActivePillar(i)} onMouseLeave={()=>setActivePillar(null)}>
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:18,flexWrap:"wrap",gap:8}}>
                  <span style={{fontSize:"clamp(20px,2.5vw,26px)"}}>{f.icon}</span>
                  <span className="pill" style={{background:`${f.color}16`,color:f.color,border:`1px solid ${f.color}28`}}>{f.tag}</span>
                </div>
                <h3 className="sn" style={{fontSize:"clamp(13px,1.5vw,16px)",fontWeight:600,marginBottom:10,color:"#E8E8E0",lineHeight:1.3}}>{f.title}</h3>
                <p className="sn" style={{fontSize:"clamp(11px,1.1vw,13px)",lineHeight:1.78,color:"rgba(232,232,224,.72)",fontWeight:300}}>{f.desc}</p>
                <div style={{marginTop:20,height:2,background:`linear-gradient(to right,${f.color},transparent)`,opacity:activePillar===i?1:0.14,transition:"opacity .3s"}}/>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════
          OUR PRINCIPLES
      ══════════════════════ */}
      <section style={{padding:"clamp(56px,9vw,110px) clamp(16px,4vw,48px)",background:"rgba(0,255,178,.016)",borderTop:"1px solid rgba(0,255,178,.07)",borderBottom:"1px solid rgba(0,255,178,.07)"}}>
        <div className="mw">
          <div style={{marginBottom:"clamp(36px,6vw,60px)",display:"flex",justifyContent:"space-between",alignItems:"flex-end",flexWrap:"wrap",gap:20}}>
            <div>
              <span className="pill" style={{background:"rgba(0,255,178,.08)",color:"#00FFB2",marginBottom:14,display:"inline-block"}}>// Our Principles</span>
              <h2 className="bb" style={{fontSize:"clamp(34px,6vw,72px)",lineHeight:0.94}}>
                HOW WE<br/><span style={{color:"#00FFB2"}}>THINK</span>
              </h2>
            </div>
            <p className="sn" style={{fontSize:"clamp(12px,1.4vw,14px)",lineHeight:1.8,color:"rgba(232,232,224,.72)",fontWeight:300,maxWidth:420}}>
              These are not values on a wall. They are the architectural decisions embedded into every system we build.
            </p>
          </div>
          <div className="prc-grid" style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:1,background:"rgba(255,255,255,.05)"}}>
            {PRINCIPLES.map((p,i)=>(
              <div key={i} className="prc" style={{background:"#020408"}} onMouseEnter={()=>setActivePrinciple(i)} onMouseLeave={()=>setActivePrinciple(null)}>
                <p className="mn" style={{fontSize:"clamp(28px,4vw,48px)",color:activePrinciple===i?"#00FFB2":"rgba(0,255,178,.22)",marginBottom:18,transition:"color .25s",lineHeight:1}}>{p.num}</p>
                <h4 className="sn" style={{fontSize:"clamp(13px,1.4vw,15px)",fontWeight:600,marginBottom:12,color:"#E8E8E0",lineHeight:1.3}}>{p.title}</h4>
                <p className="sn" style={{fontSize:"clamp(11px,1.1vw,13px)",lineHeight:1.75,color:"rgba(232,232,224,.88)",fontWeight:300}}>{p.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════
          VISION & MISSION
      ══════════════════════ */}
      <section id="vision" className="sp">
        <div className="mw">
          <div className="vm-2col" style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"clamp(36px,7vw,88px)"}}>
            <div>
              <span className="pill" style={{background:"rgba(0,255,178,.08)",color:"#00FFB2",marginBottom:20,display:"inline-block"}}>// Vision</span>
              <div style={{borderLeft:"3px solid #00FFB2",paddingLeft:"clamp(18px,3vw,30px)"}}>
                <h3 className="bb" style={{fontSize:"clamp(36px,5.5vw,56px)",color:"#00FFB2",marginBottom:16}}>VISION</h3>
                <p className="sn" style={{fontSize:"clamp(14px,1.6vw,17px)",lineHeight:1.85,color:"rgba(232,232,224,.86)",fontWeight:300,marginBottom:20}}>
                  To eliminate systemic failure in pandemic response by embedding enforceable automation into national and global health infrastructures — making catastrophic unpreparedness structurally impossible.
                </p>
                <p className="sn" style={{fontSize:"clamp(12px,1.3vw,14px)",lineHeight:1.78,color:"rgba(232,232,224,.88)",fontWeight:300,fontStyle:"italic"}}>
                  A world where no government can be caught unprepared. Where the question is never "why didn't anyone act?" but always "how fast can the system respond?"
                </p>
              </div>
            </div>
            <div>
              <span className="pill" style={{background:"rgba(255,107,53,.1)",color:"#FF6B35",marginBottom:20,display:"inline-block"}}>// Mission</span>
              <div style={{borderLeft:"3px solid #FF6B35",paddingLeft:"clamp(18px,3vw,30px)"}}>
                <h3 className="bb" style={{fontSize:"clamp(36px,5.5vw,56px)",color:"#FF6B35",marginBottom:16}}>MISSION</h3>
                <p className="sn" style={{fontSize:"clamp(14px,1.6vw,17px)",lineHeight:1.85,color:"rgba(232,232,224,.86)",fontWeight:300,marginBottom:20}}>
                  To deploy and institutionalise OryxShield as Namibia's sovereign national digital health infrastructure — providing automated pandemic surveillance, risk assessment, and coordinated outbreak response.
                </p>
                <p className="sn" style={{fontSize:"clamp(12px,1.3vw,14px)",lineHeight:1.78,color:"rgba(232,232,224,.88)",fontWeight:300,fontStyle:"italic"}}>
                  Not a consultancy. Not a software vendor. A sovereign infrastructure partner — the same way a national grid is not a recommendation, it is essential.
                </p>
              </div>
            </div>
          </div>

          {/* roadmap */}
          <div style={{marginTop:"clamp(48px,8vw,88px)"}}>
            <div className="div-g" style={{marginBottom:"clamp(28px,4vw,44px)"}}/>
            <p className="mn" style={{fontSize:"9px",letterSpacing:"0.2em",color:"rgba(0,255,178,.38)",marginBottom:32,textTransform:"uppercase"}}>// Deployment Roadmap</p>
            <div className="phase-3" style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:0}}>
              {TIMELINE.map((t,i)=>(
                <div key={i} style={{padding:`clamp(20px,3vw,30px) ${i>0?"clamp(20px,3vw,40px)":0} clamp(20px,3vw,30px) ${i>0?"clamp(20px,3vw,40px)":0}`,borderLeft:i>0?"1px solid rgba(0,255,178,.08)":"none"}}>
                  <p className="mn" style={{fontSize:"9px",letterSpacing:"0.18em",color:"rgba(0,255,178,.38)",marginBottom:10}}>{t.phase}</p>
                  <h4 className="bb" style={{fontSize:"clamp(28px,4vw,44px)",color:"#00FFB2",marginBottom:10}}>{t.title}</h4>
                  <p className="sn" style={{fontSize:"clamp(11px,1.2vw,13px)",lineHeight:1.78,color:"rgba(232,232,224,.72)",fontWeight:300}}>{t.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════
          WHO WE SERVE
      ══════════════════════ */}
      <section id="who-we-serve" style={{padding:"clamp(56px,9vw,110px) clamp(16px,4vw,48px)",background:"rgba(0,255,178,.016)",borderTop:"1px solid rgba(0,255,178,.07)",borderBottom:"1px solid rgba(0,255,178,.07)"}}>
        <div className="mw">
          <div style={{marginBottom:"clamp(36px,6vw,60px)"}}>
            <span className="pill" style={{background:"rgba(0,255,178,.08)",color:"#00FFB2",marginBottom:14,display:"inline-block"}}>// Our Partners & Clients</span>
            <h2 className="bb" style={{fontSize:"clamp(34px,6.5vw,76px)",lineHeight:0.94}}>
              WHO WE<br/><span style={{color:"#00FFB2"}}>SERVE</span>
            </h2>
          </div>
          <div className="serve-4" style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:1,background:"rgba(255,255,255,.05)",marginBottom:"clamp(36px,5vw,60px)"}}>
            {WHO_WE_SERVE.map((s,i)=>(
              <div key={i} className="sc" style={{background:"#020408"}}>
                <span style={{fontSize:"clamp(24px,3vw,32px)",display:"block",marginBottom:18}}>{s.icon}</span>
                <h4 className="sn" style={{fontSize:"clamp(13px,1.5vw,15px)",fontWeight:600,marginBottom:12,color:"#E8E8E0",lineHeight:1.3}}>{s.title}</h4>
                <p className="sn" style={{fontSize:"clamp(11px,1.1vw,13px)",lineHeight:1.78,color:"rgba(232,232,224,.88)",fontWeight:300}}>{s.desc}</p>
              </div>
            ))}
          </div>

          {/* CTA strip */}
          <div style={{background:"rgba(0,255,178,.04)",border:"1px solid rgba(0,255,178,.12)",padding:"clamp(24px,3.5vw,40px) clamp(20px,4vw,48px)",display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:20}}>
            <div>
              <p className="bb" style={{fontSize:"clamp(22px,3.5vw,36px)",color:"#00FFB2",lineHeight:1,marginBottom:6}}>INTERESTED IN EARLY ACCESS?</p>
              <p className="sn" style={{fontSize:"clamp(12px,1.3vw,14px)",color:"rgba(232,232,224,.74)",fontWeight:300}}>We are currently in development and onboarding institutional partners for pilot deployment.</p>
            </div>
            <button onClick={()=>go("contact")} style={{background:"#00FFB2",color:"#020408",padding:"13px 32px",fontFamily:"'Space Mono',monospace",fontSize:"10px",letterSpacing:"0.15em",textTransform:"uppercase",border:"none",cursor:"pointer",fontWeight:700,whiteSpace:"nowrap",flexShrink:0}}>
              Contact Us →
            </button>
          </div>
        </div>
      </section>

      {/* ══════════════════════
          DEVELOPMENT STATUS
      ══════════════════════ */}
      <section style={{padding:"clamp(56px,9vw,110px) clamp(16px,4vw,48px)"}}>
        <div className="mw">
          <div style={{display:"flex",flexDirection:"column",alignItems:"center",textAlign:"center",gap:"clamp(20px,3vw,32px)"}}>
            <div className="dev-badge" style={{padding:"8px 20px"}}>
              <span className="blk" style={{color:"#FF6B35",fontSize:10}}>●</span>
              <span className="mn" style={{fontSize:"9px",letterSpacing:"0.18em",color:"#FF6B35",textTransform:"uppercase"}}>Active Development</span>
            </div>
            <h2 className="bb" style={{fontSize:"clamp(38px,7vw,84px)",lineHeight:0.94,maxWidth:900}}>
              THE SYSTEM IS BEING<br/><span style={{color:"#00FFB2"}}>BUILT RIGHT NOW</span>
            </h2>
            <p className="sn" style={{fontSize:"clamp(13px,1.6vw,17px)",lineHeight:1.82,color:"rgba(232,232,224,.78)",fontWeight:300,maxWidth:680}}>
              OryxShield is under active development. The engineering team is building the core surveillance, risk assessment, and automated response modules for Namibia's national health system.
            </p>
            <div style={{display:"flex",gap:0,flexWrap:"wrap",justifyContent:"center",marginTop:8,width:"100%",maxWidth:800}}>
              {[
                {label:"Core Infrastructure",pct:65,color:"#00FFB2"},
                {label:"Surveillance Engine",pct:55,color:"#4ECDC4"},
                {label:"Risk & Alert Module",pct:45,color:"#FFD93D"},
                {label:"Response Protocols",pct:40,color:"#C77DFF"},
              ].map((b,i)=>(
                <div key={i} style={{flex:"1 1 180px",padding:"clamp(18px,2.5vw,28px) clamp(14px,2vw,20px)",textAlign:"left",borderRight:i<3?"1px solid rgba(255,255,255,.06)":"none",borderBottom:"1px solid rgba(255,255,255,.06)"}}>
                  <p className="mn" style={{fontSize:"9px",letterSpacing:"0.14em",color:"rgba(232,232,224,.60)",marginBottom:12,textTransform:"uppercase"}}>{b.label}</p>
                  <div style={{height:3,background:"rgba(255,255,255,.06)",borderRadius:2,overflow:"hidden",marginBottom:8}}>
                    <div style={{height:"100%",width:`${b.pct}%`,background:b.color,borderRadius:2,transition:"width 1s ease"}}/>
                  </div>
                  <p className="bb" style={{fontSize:"clamp(22px,3vw,30px)",color:b.color}}>{b.pct}%</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════
          CONTACT
      ══════════════════════ */}
      <section id="contact" style={{padding:"clamp(56px,9vw,110px) clamp(16px,4vw,48px)",borderTop:"1px solid rgba(0,255,178,.07)",background:"rgba(0,255,178,.012)"}}>
        <div className="mw">
          <div className="contact-2" style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"clamp(36px,7vw,88px)",alignItems:"center"}}>
            <div>
              <span className="pill" style={{background:"rgba(0,255,178,.08)",color:"#00FFB2",marginBottom:20,display:"inline-block"}}>// Reach Out</span>
              <h2 className="bb" style={{fontSize:"clamp(50px,9vw,104px)",lineHeight:0.88,marginBottom:24}}>
                LET'S<br/><span style={{color:"#00FFB2"}}>CONNECT</span>
              </h2>
              <p className="sn" style={{fontSize:"clamp(13px,1.5vw,15px)",lineHeight:1.82,color:"rgba(232,232,224,.78)",fontWeight:300,maxWidth:400,marginBottom:28}}>
                Whether you represent a government ministry, international health body, NGO, healthcare network, or private sector institution — we want to hear from you.
              </p>
              <div style={{display:"flex",flexDirection:"column",gap:10}}>
                {[
                  "Pilot deployment partnerships",
                  "Institutional licensing enquiries",
                  "Research & academic collaborations",
                  "Media & press enquiries",
                ].map((item,i)=>(
                  <div key={i} style={{display:"flex",alignItems:"center",gap:10}}>
                    <div style={{width:4,height:4,borderRadius:"50%",background:"#00FFB2",flexShrink:0}}/>
                    <span className="sn" style={{fontSize:"clamp(12px,1.3vw,13px)",color:"rgba(232,232,224,.78)",fontWeight:300}}>{item}</span>
                  </div>
                ))}
              </div>
            </div>

            <div style={{display:"flex",flexDirection:"column",gap:12}}>
              {[
                {label:"Primary Contact", val:"+264 61 203 2720", icon:"📞"},
                {label:"Secondary Contact", val:"+264 81 234 5678", icon:"📱"},
              ].map((c,i)=>(
                <a key={i} href={`tel:${c.val.replace(/\s/g,"")}`} className="cl">
                  <span style={{fontSize:"clamp(18px,2.5vw,24px)",flexShrink:0}}>{c.icon}</span>
                  <div>
                    <p className="mn" style={{fontSize:"8px",letterSpacing:"0.18em",color:"rgba(0,255,178,.38)",marginBottom:5,textTransform:"uppercase"}}>{c.label}</p>
                    <p className="sn" style={{fontSize:"clamp(15px,2.2vw,20px)",fontWeight:500,color:"#E8E8E0"}}>{c.val}</p>
                  </div>
                  <span style={{marginLeft:"auto",color:"#00FFB2",opacity:0.35,fontSize:18}}>→</span>
                </a>
              ))}
              <div style={{padding:"clamp(16px,2.5vw,24px) clamp(18px,3vw,28px)",border:"1px solid rgba(255,255,255,.06)",display:"flex",flexDirection:"column",gap:14,marginTop:4}}>
                <div>
                  <p className="mn" style={{fontSize:"8px",letterSpacing:"0.18em",color:"rgba(232,232,224,.80)",marginBottom:8,textTransform:"uppercase"}}>Headquarters</p>
                  <p className="sn" style={{fontSize:"clamp(12px,1.3vw,14px)",color:"rgba(232,232,224,.82)",fontWeight:400}}>Windhoek, Namibia — Southern Africa</p>
                </div>
                <div className="div"/>
                <div style={{display:"flex",alignItems:"center",gap:10}}>
                  <div className="pulse" style={{width:7,height:7,borderRadius:"50%",background:"#FF6B35",flexShrink:0}}/>
                  <span className="mn" style={{fontSize:"9px",color:"#FF6B35",letterSpacing:"0.1em",textTransform:"uppercase"}}>System In Development</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer style={{padding:"clamp(18px,3vw,28px) clamp(16px,4vw,48px)",borderTop:"1px solid rgba(255,255,255,.05)"}}>
        <div className="footer-row" style={{display:"flex",justifyContent:"space-between",alignItems:"center",flexWrap:"wrap",gap:10}}>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <div style={{width:6,height:6,borderRadius:"50%",background:"#00FFB2",flexShrink:0}}/>
            <span className="bb" style={{fontSize:"clamp(11px,1.6vw,14px)",letterSpacing:"0.14em",color:"#00FFB2"}}>ORYXSHIELD</span>
          </div>
          <p className="mn" style={{fontSize:"8px",letterSpacing:"0.12em",color:"rgba(232,232,224,.68)",textTransform:"uppercase"}}>© 2026 · Windhoek, Namibia · IHR 2005 Aligned</p>
          <p className="mn" style={{fontSize:"8px",letterSpacing:"0.12em",color:"rgba(255,107,53,.35)",textTransform:"uppercase"}}>System In Development</p>
        </div>
      </footer>
    </div>
  );
}