# Screen 30 — Profile & settings · `/profile` · F9 · V2.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the profile and settings screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). Everything the trader controls about their own
account, with the sensitive actions clearly separated and protected.

LAYOUT — a left nav (Profile, Security, Notifications, Verification, Data) that
becomes a top tab bar on mobile, and the selected panel on the right. Max-w-5xl.

PROFILE PANEL — display name, email (read-only with a "Change" button), and a
summary card: member since, tenant/firm name, verification status with a link to
the KYC screen. A "Change email" flow is a sensitive action: it runs through the
shared `SensitiveDialog` and requires verifying **both** the old and the new
address before it takes effect, with a clear "We've sent a link to { new } —
click it to finish the change" state in between.

SECURITY PANEL — links into: password change (current password + new password with
the policy checklist), 2FA management (enrolment, backup codes, removal), and
"Where you're signed in" (the sessions screen). Each row shows its current state
("2FA: on — TOTP", "Password: changed 3 months ago") and an action button. A note
explains that changing the password signs out every other device.

NOTIFICATIONS PANEL — the preferences matrix from the notification centre
(channels × categories, quiet hours, digest), with transactional rows locked on
and explained.

VERIFICATION PANEL — the KYC status summary with a link to the full KYC screen;
the verified name is shown masked ("Ali K.").

DATA PANEL (V2, GDPR) — a "Export my data" button that requests a full export of
the personal data the platform holds, with an explanation of what is included, an
email delivery promise ("we'll email you a link within 24 hours"), and a list of
previous exports with their status and download links. Plus an "Activity log" link
showing the trader's own recent account activity (logins, changes, actions) so
they can spot anything suspicious.

BEHAVIOUR — every mutation is optimistic with a revert-and-retry on failure;
successes show a toast; sensitive mutations additionally emit a critical audit row
(the trader is told: "For your security we've emailed you about this change").

ERROR & EDGE STATES — a stale step-up (`authz.step_up_required`, 403) re-prompts
inside the dialog without losing context; a conflict on a concurrent edit shows
"Your profile was changed elsewhere — here's the latest" with a reload action; a
429 shows "Too many attempts — try again in { n }s".

ACCESSIBILITY & MOBILE — the nav is a real tablist with arrow keys, form fields
are labelled with inline validation, the panels are semantic sections with
headings, and everything works from 320 px. No dark/light toggle in V1.
```
