//! # rules-engine
//!
//! The deterministic rules evaluator for a prop firm platform (doc §6).
//!
//! Design invariants (each one is pinned by a property test in `tests/property.rs`):
//!
//! 1. **Purity** — `apply(&mut state, &event, &pack)` does no I/O, reads no clock,
//!    has no randomness. Rule time is the *broker-attested* `broker_ts` carried by
//!    events; "trading day" boundaries are injected as `Rollover` events (the cron
//!    in the tenant's timezone computes the date — the engine is timezone-free).
//! 2. **Replayability** — any event-stream prefix re-applied from the initial state
//!    reconstructs the exact state. Verdicts are proofs (full decimal inputs), so a
//!    dispute is settled by replay, not by discussion.
//! 3. **Idempotency** — at-least-once delivery is safe: `deal_id` is the natural
//!    idempotency key for trade events; duplicates are no-ops.
//! 4. **Decimal exactness** — all money is `rust_decimal::Decimal` (never f64).
//!    Wire format carries money as decimal *strings* (see `events.rs`).
//! 5. **Platform is right about business, broker is right about markets** — reported
//!    PnL is *recomputed* from stored entry + broker exit price; a mismatch beyond
//!    `pnl_tolerance` emits an integrity alert and the recomputed value wins.
//!
//! What this engine deliberately does NOT do (see doc §6.5 — three enforcement layers):
//! it does not reject orders in real time (that is bridge L1 / EA L0), and it does not
//! enforce spread/volume/symbol caps (L1 checks from the compiled pack). It is the
//! financial truth: drawdowns, targets, min-days, news policy, rollovers.

pub mod events;
pub mod eval;
pub mod pack;
pub mod replay;
pub mod state;
pub mod verdict;

pub use events::{CanonicalEvent, Side};
pub use eval::{apply, ApplyResult, Engine, IntegrityAlert};
pub use pack::{CompiledPack, RulePack};
pub use replay::replay;
pub use state::{AccountState, DayState};
pub use verdict::{RuleId, Verdict, VerdictStatus};
