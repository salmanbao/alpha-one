//! Replay (doc §6.7, §7.2): re-apply an event stream from the initial state.
//!
//! Same `apply`, different entry point — which is exactly the point: the dispute
//! path, the backfill path, and the live path are ONE code path (doc §6.7:
//! "because evaluation is pure, migration verification is a batch job, not a
//! migration script").

use crate::events::CanonicalEvent;
use crate::eval::{apply, ApplyResult};
use crate::pack::CompiledPack;
use crate::state::AccountState;
use crate::verdict::Verdict;

/// Re-apply `events` (in the given order) to a fresh state.
/// Returns the final state and all verdicts, in apply order.
pub fn replay(
    account: &str,
    pack: &CompiledPack,
    initial_day: &str,
    events: &[CanonicalEvent],
) -> (AccountState, Vec<Verdict>, Vec<crate::eval::IntegrityAlert>) {
    let mut state = AccountState::new(account, pack, initial_day);
    let mut verdicts = Vec::new();
    let mut alerts = Vec::new();
    for ev in events {
        let ApplyResult {
            verdicts: v,
            integrity_alerts: a,
            ..
        } = apply(&mut state, pack, ev);
        verdicts.extend(v);
        alerts.extend(a);
    }
    (state, verdicts, alerts)
}

/// Replay to a point: apply the first `n` events. Used by properties to compare
/// "incremental at prefix n" vs "replay from zero to n" (doc §13.2-2).
pub fn replay_prefix(
    account: &str,
    pack: &CompiledPack,
    initial_day: &str,
    events: &[CanonicalEvent],
    n: usize,
) -> AccountState {
    let mut state = AccountState::new(account, pack, initial_day);
    for ev in &events[..n] {
        apply(&mut state, pack, ev);
    }
    state
}
