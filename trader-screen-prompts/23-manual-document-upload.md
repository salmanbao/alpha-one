# Screen 23 — Manual document upload · `/kyc/upload` · F6 · V1.1

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the manual document upload screen for the Alpha One trader portal
(Next.js 15, TypeScript, Tailwind, shadcn/ui). It is the fallback path used when
the verification provider is unavailable or has flagged a case — the guarantee
that compliance never hard-blocks a trader.

LAYOUT — an explanation panel, upload slots, a submit button, and a status panel.
Max-w-2xl.

EXPLANATION PANEL — why the trader is here, in one sentence ("Our verification
provider is unavailable, so we'll review your documents manually"), what is needed,
and the expected turnaround ("usually within 24 hours"). Tone: reassuring, never
implying the trader did something wrong.

UPLOAD SLOTS — one card per required document type, driven by the tenant's
configuration: ID front, ID back, selfie, proof of address. Each slot is a
dropzone plus a "Choose file" button, shows the accepted formats (JPG, PNG, PDF),
the 10 MB maximum, and once a file is chosen shows a thumbnail (for images), the
filename, the size, a remove button, and an "Uploading… 64%" progress bar with a
retry button on failure.

VALIDATION — client-side pre-checks before upload: file type, size under 10 MB,
and a minimum resolution for image documents, each with a specific inline message
("That file is 14 MB — the maximum is 10 MB", "That image is too small — use at
least 1000 px wide"). These exist to catch obvious failures before paying a
provider or a reviewer's time.

SUBMIT — a "Submit for review" button, disabled until all required slots have a
successfully uploaded file. On submit, show a confirmation state: "Documents
submitted — our team will review them and email you the result." with a link back
to the KYC status screen.

STATUS PANEL — after submission, a persistent card on the KYC status screen
showing each uploaded document with its upload date and a "Under review" badge,
plus a "Replace document" action that creates a new version rather than mutating
the old one (the review history must stay answerable).

ERROR & EDGE STATES — upload failure: a retry button on that slot with the error
inline, and the rest of the form preserved. `kyc.upload_failed` (400): "Upload
failed — please try again." Session already in review: "Your documents are
already with our team" with the status panel instead of the form. Provider
recovers mid-flow: a note "You can also finish instantly with { provider }" with a
button that starts a hosted session.

ACCESSIBILITY & MOBILE — dropzones are keyboard-operable (Enter/Space opens the
file picker) with clear focus rings, progress bars use role="progressbar" with
aria-valuenow, errors are announced via aria-live, and the layout is single column
from 320 px with large tap targets. No dark/light toggle in V1.
```
