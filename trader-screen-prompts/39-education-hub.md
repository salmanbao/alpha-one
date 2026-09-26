# Screen 39 — Education hub · `/academy` · F10 · V2.0/V3.0

> Copy-able UI prompt for the Alpha One trader portal.
> Extracted from `trader-flows-and-screen-prompts.md` (Part 3).
> Source spec: `alpha-one/docs/16-trader-dashboard.md` and the owning module docs.

```prompt
Build the education hub screen for the Alpha One trader portal (Next.js 15,
TypeScript, Tailwind, shadcn/ui). Lessons and courses that help traders understand
the rules they are judged on — with completion tracking that is honest rather than
gamified into meaninglessness.

LAYOUT — a header "Academy", a "Continue where you left off" strip, a course grid,
and (V2) a recommended-lessons widget on the dashboard that links here.

COURSE CARD — title, a one-line description, the lesson count, the estimated
duration, a difficulty badge, the completion state (Not started / In progress 3 of
8 / Completed with the date), and a primary "Start" / "Continue" / "Review" button.
Cards are grouped by track (Getting started, Risk management, Trading psychology,
Platform guides).

LESSON VIEWER — a two-pane layout: the lesson content on the left and a lesson
sidebar on the right showing the course outline with completion ticks. Content
supports text, images, and video delivered through short-lived signed URLs (video
is streamed from object storage, never embedded from a third party). A "Mark as
complete" button advances the outline and updates the course progress bar.

COMPLETION HONESTY — a lesson is complete only when its stated criteria are met:
for a video lesson, watched to at least 90%; for a quiz lesson, passed at the
configured threshold; for a reading lesson, explicitly marked. Show the criterion
on the lesson ("Watch 90% to complete") and, where it is not yet met, show the
progress toward it ("78% watched"). Never auto-complete on page view, and never
show a completion tick that the criteria don't support.

QUIZZES — multiple-choice with immediate per-question feedback, a pass threshold
shown up front, unlimited retakes, and a results panel listing which questions were
missed with a link back to the relevant lesson section.

PROGRESS — a per-track progress bar and a "certificates of completion" list (V3)
where the tenant awards them. Progress is visible on the dashboard widget
(recommended lessons and course progress) and in the profile.

EMPTY STATE — "No courses published yet by your firm." (the hub is
tenant-populated), rather than a generic empty state.
ERROR — per-pane retry; a video that fails to load shows "This video couldn't
load — try again" with a retry, never a black rectangle.

ACCESSIBILITY & MOBILE — the outline is a proper navigation list with
aria-current, the video player has captions support and keyboard controls, quiz
options are real radio groups with feedback announced via aria-live, and the
two-pane layout stacks under 1024 px. No dark/light toggle in V1.
```
