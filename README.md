# alpinemoderncabin.com

Alpine Modern, moved off WordPress to a static site on Cloudflare Workers. Every push to `main` deploys.

The pages in `public/` are the live WordPress site's own HTML, styles, scripts and images (theme, Elementor and plugin files kept at their WordPress paths, so everything renders and animates as before). Changes made in the move:

- The online booking system (MotoPress + Stripe) and the "Check Availability" buttons were removed; the cart, checkout, account and booking pages redirect to the home page (`public/_redirects`).
- The contact form sends to `/api/contact` (`worker/contact.js`), which emails it through Resend.
- Comment forms were removed (existing comments are still shown).
- `public/sitemap.xml` and `public/robots.txt` replace All in One SEO's.

## Editing

Each page is `public/<url>/index.html` (the home page is `public/index.html`). Edit the HTML directly, or ask Claude to. Images go in `public/wp-content/uploads/`.

## Contact form settings (Cloudflare → Workers & Pages → alpine-modern-site → Settings → Variables and Secrets)

- `RESEND_API_KEY` (secret)
- `CONTACT_TO`: where messages go
- `CONTACT_FROM`: e.g. `Alpine Modern <onboarding@resend.dev>`

## Commands

```
npm install
npx wrangler dev     # run locally the way Cloudflare serves it
```

`build-from-wordpress.py` is the one-time script that produced `public/` from the WordPress mirror; it isn't part of the deploy.

## File size limit

Cloudflare Workers serves files up to 25 MiB. `wp-content/uploads/2025/06/IMG_4896.mov`
(the Tacoma cab-mount video) was re-encoded from 50 MiB to about 10 MiB to fit
(`ffmpeg -c:v libx264 -crf 24 -c:a aac -b:a 128k -movflags +faststart`). If the site is ever
rebuilt from the WordPress mirror, re-encode it again.
