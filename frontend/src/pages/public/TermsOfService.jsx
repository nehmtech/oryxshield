const T = {
  bg: '#0a0f1e', surface: '#111827', border: '#1f2937',
  accent: '#3b82f6', text: '#f9fafb', textSub: '#9ca3af', danger: '#ef4444',
}
const FONTS = {
  heading: "'Bebas Neue', sans-serif",
  mono:    "'Space Mono', monospace",
  body:    "'IBM Plex Sans', sans-serif",
}

const SECTIONS = [
  {
    title: '1. Acceptance of Terms',
    body: `By accessing or using the OryxShield platform ("Platform"), you confirm that you are an authorised user of a participating public health agency and that you accept these Terms of Service in full. If you do not accept these terms, you must not use the Platform.\n\nUse of this Platform is restricted to personnel with a valid account issued by an authorised agency administrator. Sharing credentials or attempting to access the Platform without authorisation is strictly prohibited and may result in criminal liability under the Namibia Cybercrime Act.`,
  },
  {
    title: '2. Authorised Use',
    body: `You are authorised to use the Platform solely for official public health surveillance, response coordination, and related functions within the scope of your designated role. Roles include: admin, analyst, coordinator, field_officer, and public. Each role carries defined access permissions enforced at the API level.\n\nAuthorised uses include:\n\n• Entering and reviewing epidemiological and case data within your jurisdiction.\n• Coordinating response activities with other authorised agencies.\n• Accessing analytics and reports relevant to your role.\n• Managing resources and operational tasks assigned to you.\n\nAny use beyond the above, including bulk data extraction without authorisation, automated scraping, or use for commercial purposes, is prohibited.`,
  },
  {
    title: '3. User Responsibilities',
    body: `You are responsible for:\n\n• Maintaining the confidentiality of your login credentials and not sharing them with any other person.\n• Ensuring that data you enter is accurate, timely, and within your jurisdiction to report.\n• Immediately reporting any suspected unauthorised access or breach to your agency administrator and to security@oryxshield.gov.na.\n• Complying with all applicable laws, including the Namibia Personal Information Protection Act and the Health Act.\n• Using the Platform only on secured, approved devices and networks.\n\nYou must not attempt to circumvent authentication mechanisms, access data outside your role permissions, or interfere with Platform operations.`,
  },
  {
    title: '4. Data Accuracy and Liability',
    body: `OryxShield provides a platform for data entry, analysis, and coordination. The accuracy of surveillance data depends on inputs from authorised users. The Platform operators do not warrant the accuracy, completeness, or fitness for any particular purpose of data submitted by users.\n\nPublic health decisions made on the basis of Platform data remain the sole responsibility of the relevant health authority. The Platform operators accept no liability for decisions made using Platform outputs.`,
  },
  {
    title: '5. Intellectual Property',
    body: `All software, design, analytical models, documentation, and other materials comprising the Platform are the intellectual property of the Ministry of Health and Social Services, Republic of Namibia, and NEHMTECH Innovations Limited. You are granted a non-exclusive, non-transferable licence to use the Platform for the purposes set out in these Terms.\n\nYou may not copy, modify, distribute, reverse-engineer, or create derivative works of any part of the Platform without prior written consent.`,
  },
  {
    title: '6. Availability and Maintenance',
    body: `We aim to maintain Platform availability of 99.5% or above, excluding scheduled maintenance windows. Scheduled maintenance will be communicated to registered users at least 24 hours in advance where possible. Emergency maintenance may occur without prior notice.\n\nWe do not guarantee uninterrupted access and accept no liability for losses arising from unavailability.`,
  },
  {
    title: '7. Suspension and Termination',
    body: `Your access may be suspended or terminated:\n\n• By your agency administrator, for any operational reason.\n• By Platform administrators, if you breach these Terms, misuse the Platform, or present a security risk.\n• Automatically, upon termination of your employment or engagement with an authorised agency.\n\nUpon termination, your access is revoked immediately. Attempting to access the Platform following termination is a violation of these Terms and may constitute a criminal offence.`,
  },
  {
    title: '8. Limitation of Liability',
    body: `To the maximum extent permitted by law, the Platform operators shall not be liable for any indirect, incidental, consequential, or punitive damages arising from your use of the Platform, including but not limited to loss of data, loss of revenue, or harm resulting from public health decisions based on Platform data.\n\nOur total liability in any circumstance shall not exceed KES 50,000.`,
  },
  {
    title: '9. Governing Law',
    body: `These Terms are governed by the laws of the Republic of Namibia. Any disputes arising from or related to these Terms or your use of the Platform shall be submitted to the exclusive jurisdiction of the courts of Windhoek, Namibia.`,
  },
  {
    title: '10. Changes to Terms',
    body: `We reserve the right to update these Terms at any time. Material changes will be communicated by email to registered users at least 14 days before taking effect. Continued use of the Platform after that date constitutes acceptance of the revised Terms.\n\nFor questions about these Terms, contact legal@oryxshield.gov.na.`,
  },
]

export default function TermsOfService() {
  return (
    <>
      <style>{`@keyframes tos-fadeUp { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }`}</style>
      <div style={{ maxWidth: 800, margin: '0 auto', padding: '72px 24px 96px', animation: 'tos-fadeUp 0.4s ease' }}>
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase', color: T.textSub, marginBottom: 10 }}>Legal</div>
        <h1 style={{ fontFamily: FONTS.heading, fontSize: 52, color: T.text, margin: '0 0 14px', letterSpacing: '0.03em' }}>TERMS OF SERVICE</h1>
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, marginBottom: 32 }}>
          Effective Date: 1 January 2024 &nbsp;·&nbsp; Last Updated: 1 March 2025
        </div>

        <div style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 4, padding: '16px 20px', marginBottom: 48 }}>
          <p style={{ fontFamily: FONTS.body, fontSize: 13, color: T.textSub, lineHeight: 1.75, margin: 0 }}>
            These Terms of Service govern your access to and use of the OryxShield pandemic surveillance platform. This platform is restricted to authorised public health personnel. Unauthorised access is a criminal offence under the Namibia Cybercrime Act.
          </p>
        </div>

        {SECTIONS.map((s, i) => (
          <div key={i} style={{ marginBottom: 40, paddingBottom: 40, borderBottom: i < SECTIONS.length - 1 ? `1px solid ${T.border}` : 'none' }}>
            <h2 style={{ fontFamily: FONTS.heading, fontSize: 22, color: T.text, margin: '0 0 14px', letterSpacing: '0.04em' }}>{s.title}</h2>
            {s.body.split('\n\n').map((para, j) => (
              <p key={j} style={{ fontFamily: FONTS.body, fontSize: 14, color: T.textSub, lineHeight: 1.85, margin: '0 0 12px', whiteSpace: 'pre-line' }}>{para}</p>
            ))}
          </div>
        ))}
      </div>
    </>
  )
}