# Screen 01 — Sign-in / register · `/login` · F1 · V1.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the trader sign-in / register screen for "Alpha One", a white-label prop-firm
platform (Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui). This screen is
tenant-branded: logo, colours and product wording come from the tenant context so it
feels like the firm's own product, not a generic SaaS.

LAYOUT — centred auth card, max-w-md, on a neutral background with a subtle brand
gradient. Two tabs at the top: "Sign in" (default) and "Create account". Below the
card: a footer line with links to Terms, Privacy and "Contact support".

SIGN-IN TAB — email field (type=email, autocomplete=username, required), password
field with show/hide toggle, "Forgot password?" link to /reset-password, a
"Sign in" primary button (full width, loading state on submit), and an optional
row of SSO buttons if the tenant has them configured.

CREATE-ACCOUNT TAB — email, password, confirm password, a required checkbox
accepting the firm's Terms and Privacy Policy (links open in a new tab), and a
"Create account" button. Show an inline password-policy hint under the password
field: minimum 10 characters, mixed case, a number, and not one of the last 5 used.

BEHAVIOUR — authentication is delegated to the hosted identity provider (ZITADEL
Hosted Login, org-scoped for this firm's domain); render the provider hand-off as
a full-card "Taking you to secure sign-in…" state with a spinner and a "Cancel"
link that returns to the form. On return, exchange the code server-side and
materialise the session. After a successful sign-in, redirect to the `next` query
parameter if present, otherwise to the account home `/`.

ERROR & EDGE STATES (all inline, never a raw dialog):
- Invalid credentials: inline red text under the form, "Those details don't match an account. Try again." — never reveal whether the email exists.
- Rate limited (429): amber inline banner "Too many attempts. Try again in {n} seconds." with a countdown.
- Account locked: "This account is temporarily locked after too many attempts. Reset your password or contact support."
- Tenant not found (404 on the host): a full-page "Site not found" state — 404, not 403 — with a support link.
- Session expired (401 on any call while on another page): a full-screen re-login card that preserves the page the trader was on and restores their form input afterwards.
- Idle timeout (30 minutes for traders): a modal "You've been signed out for security. Sign in to continue." with a single "Sign in" button.

2FA — if the identity has a second factor, after the password step show a 6-digit
code screen: six separate single-character inputs with auto-advance and
paste-support, a "Use a backup code instead" link, a "Verify" button, and a
"Resend / having trouble?" link to support. Show a 30-second cooldown on resend.

ACCESSIBILITY & MOBILE — fully keyboard navigable with a visible focus ring, all
inputs labelled, error text tied to inputs with aria-describedby, the tabs are a
proper tablist with arrow-key support, and the layout is single-column and
thumb-friendly from 320 px up. Do not add a dark/light toggle (out of scope for V1).
```
