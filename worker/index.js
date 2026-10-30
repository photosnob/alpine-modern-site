// Cloudflare Worker for alpinemoderncabin.com: static files from public/, plus the contact form at /api/contact.
import { handleContact } from './contact.js';
export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname === '/api/contact') {
      if (request.method !== 'POST') return new Response('Method not allowed', { status: 405, headers: { Allow: 'POST' } });
      return handleContact(request, env);
    }
    return env.ASSETS.fetch(request);
  },
};
