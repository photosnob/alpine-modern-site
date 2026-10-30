"""Turn the mirrored WordPress site into a static site for Cloudflare Workers (static assets)."""
import os, re, glob, shutil, json, html
from bs4 import BeautifulSoup, Comment
SRC = '/home/claude/src-alpine/alpine-mirror'
OUT = '/home/claude/alpine-site/public'
HOST_RE = re.compile(r'(?:https?:)?(?:\\?/\\?/)(?:www\.)?alpinemoderncabin\.com')
DROP = {'cart', 'checkout', 'my-account', 'booking-confirmation', 'booking-confirmation-3', 'booking-confirmation/booking-canceled',
        'booking-confirmation/transaction-failed', 'booking-confirmation/booking-confirmed', 'search-results', 'xmlrpc.php'}
KEEP_ABS = ('canonical', 'og:url', 'og:image', 'og:image:secure_url', 'twitter:image', 'shortlink')

def rel(s):
    """Make same-site URLs root-relative (works on workers.dev previews and the real domain)."""
    s = re.sub(r'https?:\\/\\/(?:www\.)?alpinemoderncabin\.com', '', s)  # JSON-escaped, inside inline scripts
    return re.sub(r'(?:https?:)?//(?:www\.)?alpinemoderncabin\.com', '', s)

def clean(path, t):
    s = BeautifulSoup(t, 'lxml')
    # WordPress API / feed / pingback links have nothing to serve on a static site
    for l in s.select('link'):
        r = ' '.join(l.get('rel', []))
        if r in ('EditURI', 'wlwmanifest', 'https://api.w.org/', 'pingback', 'shortlink') or (r == 'alternate' and l.get('type') in ('application/json', 'application/rss+xml', 'application/json+oembed', 'text/xml+oembed')):
            l.decompose()
    # comment forms (comments are closed on a static site; existing comments stay visible)
    for e in s.select('#respond, .comment-respond'): e.decompose()
    # "Check Availability" buttons to the old booking site
    for a in s.select('a[href*="sierravacationrentals.com"]'):
        w = a.find_parent(class_='elementor-widget') or a
        sec = w.find_parent(class_='elementor-section')
        if sec is not None and sec.get_text(' ', strip=True) == a.get_text(' ', strip=True): sec.decompose()
        else: w.decompose()
    # MotoPress booking widgets (availability search, calendars)
    for e in s.select('[class*="mphb_sc_"], .mphb_widget_search-form, .mphb-calendar, .widget_mphb_rooms_widget, form.mphb_sc_search-form'):
        if not e.decomposed: e.decompose()
    # menu items pointing at removed pages
    for a in s.select('a[href]'):
        p = rel(a['href']).strip('/').split('?')[0]
        if p in DROP:
            li = a.find_parent('li'); (li or a).decompose()
    # contact form -> Worker endpoint
    for f in s.select('form.frm-show-form'):
        f['action'] = '/api/contact'; f['method'] = 'post'; f['data-static-contact'] = '1'
        for i in f.select('input[type=hidden]'):
            if i.get('name') not in ('form_key',): i.decompose()
    # rewrite same-site URLs, but keep canonical/og absolute for SEO
    for tag in s.find_all(True):
        for k, v in list(tag.attrs.items()):
            if isinstance(v, list): continue
            if tag.name == 'link' and k == 'href' and 'canonical' in tag.get('rel', []): continue
            if tag.name == 'meta' and k == 'content': continue
            if isinstance(v, str) and 'alpinemoderncabin.com' in v: tag[k] = rel(v)
    for c in s.find_all(string=lambda x: isinstance(x, Comment)):
        if 'alpinemoderncabin.com' in c: c.replace_with(Comment(rel(str(c))))
    for sc in s.find_all(['script', 'style']):
        if sc.get('type') == 'application/ld+json': continue
        if sc.string and 'alpinemoderncabin.com' in sc.string: sc.string = rel(sc.string)
    if s.select_one('form[data-static-contact]'):
        js = s.new_tag('script'); js.string = CONTACT_JS; s.body.append(js)
    out = str(s)
    return out

CONTACT_JS = r"""
(function () {
  // Sends the contact form to /api/contact (Cloudflare Worker) instead of WordPress.
  var form = document.querySelector('form[data-static-contact]');
  if (!form) return;
  var map = { 'item_meta[9]': 'name', 'item_meta[10]': 'email', 'item_meta[11]': 'phone', 'item_meta[12]': 'subject', 'item_meta[13]': 'message', 'item_meta[39]': 'website' };
  var msg = document.createElement('div'); msg.className = 'frm_message'; msg.setAttribute('role', 'status'); msg.style.display = 'none';
  form.parentNode.insertBefore(msg, form);
  form.addEventListener('submit', function (e) {
    e.preventDefault(); e.stopImmediatePropagation();
    var fd = new FormData(), raw = new FormData(form);
    raw.forEach(function (v, k) { if (map[k]) fd.append(map[k], v); });
    var btn = form.querySelector('[type=submit]'); var label = btn.value; btn.value = 'Sending…'; btn.disabled = true;
    fetch('/api/contact', { method: 'POST', body: fd, headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.message || r.status); }); })
      .then(function () { form.style.display = 'none'; msg.className = 'frm_message'; msg.textContent = 'Thanks! Your message has been sent. We’ll get back to you soon.'; msg.style.display = 'block'; })
      .catch(function (err) { msg.className = 'frm_error_style'; msg.textContent = err.message && err.message.length < 80 ? err.message : 'Sorry, something went wrong. Please try again.'; msg.style.display = 'block'; })
      .finally(function () { btn.value = label; btn.disabled = false; });
  }, true);
})();
"""

if os.path.exists(OUT): shutil.rmtree(OUT)
# assets keep their WordPress paths, so relative url()s inside the theme/plugin CSS keep working
shutil.copytree(SRC + '/assets/www.alpinemoderncabin.com', OUT)
kept = []
for f in glob.glob(SRC + '/pages/**/*.html', recursive=True):
    p = os.path.relpath(f, SRC + '/pages')[:-5]
    if p in DROP: continue
    t = open(f, encoding='utf-8', errors='replace').read()
    dst = OUT + '/index.html' if p == 'index' else f'{OUT}/{p}/index.html'
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'w').write(clean(p, t))
    kept.append('/' if p == 'index' else f'/{p}/')
# 404 page: site shell with a short message
s = BeautifulSoup(open(OUT + '/explore/index.html').read(), 'lxml')
wrap = s.select_one('div.wrap')
wrap.clear()
wrap.append(BeautifulSoup('<div class="container" style="padding:120px 15px;text-align:center"><h1>Page not found</h1><p>The page you were looking for has moved or no longer exists.</p><p><a href="/">Back to home</a> &middot; <a href="/alpine-modern-blog/">Read the blog</a></p></div>', 'html.parser'))
s.title.string = 'Page not found - Alpine Modern'
for l in s.select('link[rel=canonical], meta[property="og:url"]'): l.decompose()
rob = s.new_tag('meta', attrs={'name': 'robots', 'content': 'noindex'}); s.head.append(rob)
open(OUT + '/404.html', 'w').write(str(s))
# sitemap and robots (All in One SEO served /sitemap.xml; keep that address)
skip = re.compile(r'^/(author|.*?/page/\d+)/')
urls = sorted(u for u in kept if not skip.match(u))
open(OUT + '/sitemap.xml', 'w').write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    ''.join(f'  <url><loc>https://www.alpinemoderncabin.com{u}</loc></url>\n' for u in urls) + '</urlset>\n')
open(OUT + '/robots.txt', 'w').write('User-agent: *\nAllow: /\n\nSitemap: https://www.alpinemoderncabin.com/sitemap.xml\n')
red = ['# Removed WordPress booking/shop pages and endpoints (booking is no longer offered on this site)']
for p in sorted(DROP): red.append(f'/{p}/   /   301' if not p.endswith('.php') else f'/{p}   /   301')
red += ['/author/jshum/page/3/   /alpine-modern-blog/page/3/   301', '/feed/   /   301', '/comments/feed/   /   301', '/wp-login.php   /   301', '/wp-admin/   /   301', '/page-sitemap.xml   /sitemap.xml   301', '/post-sitemap.xml   /sitemap.xml   301', '/category-sitemap.xml   /sitemap.xml   301', '/post_tag-sitemap.xml   /sitemap.xml   301']
open(OUT + '/_redirects', 'w').write('\n'.join(red) + '\n')
print('pages', len(kept), 'sitemap', len(urls))
