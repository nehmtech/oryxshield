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
    title: '1. Who We Are',
    body: `OryxShield is operated by the Ministry of Health and Social Services, Republic of Namibia, in partnership with NEHMTECH Innovations Limited. The platform collects, processes, and stores epidemiological and operational data for the purpose of public health surveillance and outbreak response management across Namibia.`,
  },
  {
    title: '2. Data We Collect',
    body: `We collect the following categories of data:\n\n• Account data: name, email address, phone number, role designation, and organisation affiliation provided at registration.\n• Health surveillance data: anonymised case reports, symptom clusters, laboratory results, and contact tracing records submitted by authorised health workers.\n• Operational data: event logs, system audit trails, API access records, and session metadata.\n• Device data: IP addresses, browser user-agent strings, and session tokens used for authentication and security monitoring.\n• Feedback and enquiry data: information voluntarily submitted through our public contact form, including name, contact details, and message content.\n\nWe do not collect personally identifiable patient data directly from the public. All patient-level data is de-identified before ingestion.`,
  },
  {
    title: '3. How We Use Your Data',
    body: `Data collected through this platform is used exclusively for:\n\n• Facilitating disease surveillance, risk scoring, and outbreak detection.\n• Coordinating multi-agency response actions and resource allocation.\n• Generating statistical and epidemiological reports for national and international health authorities.\n• Maintaining platform security and access control.\n• Responding to feedback, complaints, and enquiries submitted through the contact form.\n• Sending operational notifications including alerts, reminders, and status updates via SMS, email, or push notification.\n\nWe do not use your data for commercial purposes, advertising, or profiling beyond these operational functions.`,
  },
  {
    title: '4. Data Sharing',
    body: `Your data may be shared with:\n\n• Namibia Red Cross, regional health departments, and other authorised public health agencies within the platform's coordination network.\n• Africa CDC and WHO EIOS for mandatory disease reporting obligations under the International Health Regulations (IHR 2005).\n• DHIS2 and SORMAS systems as part of integrated health information infrastructure.\n• Africa's Talking and Twilio for SMS delivery; Firebase and APNS for push notifications.\n• Third-party cloud infrastructure providers bound by data processing agreements.\n\nWe do not sell or rent your data to any third party.`,
  },
  {
    title: '5. Data Retention',
    body: `Account data is retained for the duration of your authorised access period plus 24 months following account deactivation, in accordance with the Namibia Health Act and public records obligations.\n\nSurveillance and case data is retained for a minimum of 10 years per public health regulatory requirements.\n\nAudit logs and access records are retained for 7 years.\n\nFeedback and enquiry records are retained for 3 years.\n\nYou may request deletion of your personal account data by contacting your agency administrator or emailing privacy@oryxshield.gov.na. Deletion requests for surveillance data are subject to statutory retention obligations.`,
  },
  {
    title: '6. Security',
    body: `We implement industry-standard security measures including AES-256 encryption at rest, TLS 1.3 in transit, JWT-based authentication with short-lived access tokens, configurable multi-factor authentication (TOTP and SMS OTP), role-based access control across six permission tiers (admin, analyst, coordinator, field_officer, public), and continuous audit logging.\n\nAccess to the platform is restricted to authorised personnel only. All access events are logged and reviewable by system administrators.`,
  },
  {
    title: '7. Your Rights',
    body: `Under the Namibia Personal Information Protection Act, you have the right to:\n\n• Access the personal data we hold about you.\n• Rectify inaccurate personal data.\n• Object to processing of your personal data in certain circumstances.\n• Request restriction of processing.\n• Data portability where technically feasible.\n\nTo exercise any of these rights, contact privacy@oryxshield.gov.na. We will respond within 21 days.`,
  },
  {
    title: '8. Cookies and Tracking',
    body: `This platform does not use third-party advertising cookies or tracking pixels. We use strictly necessary session tokens stored in browser sessionStorage (under keys os_access and os_refresh) to maintain authenticated sessions. Tokens are cleared when the browser tab is closed. No analytics or tracking data is shared with external advertising networks.`,
  },
  {
    title: '9. Changes to This Policy',
    body: `We may update this Privacy Policy to reflect changes in our practices or applicable law. Material changes will be communicated to registered users by email at least 14 days before taking effect. Continued use of the platform after that date constitutes acceptance.`,
  },
  {
    title: '10. Contact',
    body: `For privacy enquiries, data subject requests, or to report a suspected data breach:\n\nEmail: privacy@oryxshield.gov.na\nPostal: Data Protection Officer, Ministry of Health, Harvey Street, Windhoek, Namibia\nEmergency (breach reporting): +264 61 203 2720`,
  },
]

export default function PrivacyPolicy() {
  return (
    <>
      <style>{`@keyframes pp-fadeUp { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }`}</style>
      <div style={{ maxWidth: 800, margin: '0 auto', padding: '72px 24px 96px', animation: 'pp-fadeUp 0.4s ease' }}>
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase', color: T.textSub, marginBottom: 10 }}>Legal</div>
        <h1 style={{ fontFamily: FONTS.heading, fontSize: 52, color: T.text, margin: '0 0 14px', letterSpacing: '0.03em' }}>PRIVACY POLICY</h1>
        <div style={{ fontFamily: FONTS.mono, fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase', color: T.textSub, marginBottom: 32 }}>
          Effective Date: 1 January 2024 &nbsp;·&nbsp; Last Updated: 1 March 2025
        </div>

        <div style={{ background: 'rgba(59,130,246,0.07)', border: '1px solid rgba(59,130,246,0.2)', borderRadius: 4, padding: '16px 20px', marginBottom: 48 }}>
          <p style={{ fontFamily: FONTS.body, fontSize: 13, color: T.textSub, lineHeight: 1.75, margin: 0 }}>
            This Privacy Policy describes how OryxShield collects, uses, stores, and protects data in connection with the operation of the pandemic surveillance and response platform. It applies to all authorised users including health officers, field workers, analysts, and system administrators, as well as members of the public who submit feedback through our contact form.
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