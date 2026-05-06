# Two-Strike Hitter Report Card

A long-term project examining whether MLB hitters correctly calibrate
their two-strike approach using Statcast bat tracking data.

The eventual deliverable: a public site, updated regularly, grading every
MLB hitter on whether they over-adjust, under-adjust, or correctly
calibrate their swing with two strikes — and how many runs that's worth.

## Status

**v0.2 — League-wide exploration.** Pulled the full 2025 regular season
(700K+ pitches), filtered to qualified hitters (≥100 swings in both
0-strike and 2-strike states, n ≈ 315), and computed per-hitter bat speed
adjustment scores.

### Key findings

- League-wide bat speed drops from 72.5 mph (0-strike) to 70.1 mph
  (2-strike) — a clean monotonic decline of ~2.4 mph
- Variance grows with two strikes (std 5.95 → 6.39), suggesting hitters
  diverge in their adjustments rather than converge on a common approach
- 314 of 315 qualified hitters slow down with two strikes; only one
  appears to swing harder, and his sample is small enough to be noise
- Adjustment magnitudes span 0–6 mph across the league — suggesting
  meaningful variation in approach worth examining at the player level
- Sample sizes per hitter (130–500 two-strike swings) vary enough that
  naive rankings will be heavily influenced by sampling noise — motivates
  the Bayesian partial pooling planned for v2.0

## Stack

- pybaseball for Statcast ingestion
- pandas / matplotlib for analysis and viz
- More to come: hierarchical Bayesian modeling, Airflow orchestration,
  public dashboard

## Roadmap

- [x] v0.1 — First look at bat tracking by count state
- [x] v0.2 — Full season league-wide exploration + per-hitter leaderboard
- [ ] v1.0 — Frequentist mixed-effects expected outcomes model
- [ ] v2.0 — Bayesian hierarchical with partial pooling
- [ ] v3.0 — Live system with nightly updates