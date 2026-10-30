// Handles POST /api/contact from the contact form (called from worker/index.js).
//
// Settings (Cloudflare dashboard > Workers & Pages > matchaseo-site > Settings > Variables and Secrets):
//   RESEND_API_KEY  secret  API key from resend.com, used to send the email
//   CONTACT_TO      text    where submissions go, e.g. you@yourdomain.com
//   CONTACT_FROM    text    verified sender in Resend, e.g. "Alpine Modern <onboarding@resend.dev>"

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export async function handleContact(request, env) {
  const wantsJson = (request.headers.get('accept') || '').includes('application/json');
  const reply = (ok, status, message) =>
    wantsJson
      ? Response.json({ ok, message }, { status })
      : Response.redirect(new URL(ok ? '/contact/?sent=1' : '/contact/?error=1', request.url), 303);

  let form;
  try {
    form = await request.formData();
  } catch {
    return reply(false, 400, 'Invalid form data');
  }

  // Bots fill in the hidden "website" field; humans never see it.
  if (form.get('website')) return reply(true, 200, 'ok');

  const field = (k) => String(form.get(k) || '').trim().slice(0, 5000);
  const name = field('name').slice(0, 256);
  const email = field('email').slice(0, 256);
  const phone = field('phone').slice(0, 64);
  const subject = field('subject').slice(0, 200);
  const message = field('message');
  if (!name || !EMAIL_RE.test(email) || !message) return reply(false, 400, 'Name, a valid email and a message are required');

  if (!env.RESEND_API_KEY || !env.CONTACT_TO || !env.CONTACT_FROM) {
    console.error('Contact form is not configured: set RESEND_API_KEY, CONTACT_TO and CONTACT_FROM');
    return reply(false, 500, 'Form not configured');
  }

  const text = `New message from alpinemoderncabin.com\n\nName: ${name}\nEmail: ${email}\nPhone: ${phone || '(not given)'}\nSubject: ${subject || '(none)'}\n\n${message}\n`;
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { Authorization: `Bearer ${env.RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: env.CONTACT_FROM,
      to: [env.CONTACT_TO],
      reply_to: email,
      subject: `Alpine Modern: ${subject || 'website message'}`,
      text,
    }),
  });
  if (!res.ok) {
    console.error('Resend error', res.status, await res.text());
    return reply(false, 502, 'Could not send');
  }
  return reply(true, 200, 'ok');
}
