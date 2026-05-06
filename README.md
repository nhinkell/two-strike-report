# Two-Strike Hitter Report Card

A long-term project examining whether MLB hitters correctly calibrate
their two-strike approach using bat tracking data.

The eventual deliverable: a public site, updated regularly, grading every
MLB hitter on whether they over-adjust, under-adjust, or correctly
calibrate their swing with two strikes — and how many runs that's worth.

## Status

**v0.1 — First look.** Confirmed bat tracking data shows the expected
phenomenon: league-wide, hitters slow down (~2.6 mph drop in bat speed)
and shorten up with two strikes. Variance also tightens, suggesting a
league consensus on two-strike approach.

## Stack

- pybaseball for Statcast ingestion
- pandas / matplotlib for analysis and viz
- More to come: Bayesian hierarchical modeling, Airflow orchestration,
  public dashboard

## Roadmap

- [x] v0.1 — First look at bat tracking by count state
- [ ] v1.0 — Frequentist mixed-effects model
- [ ] v2.0 — Bayesian hierarchical with partial pooling
- [ ] v3.0 — Live system with nightly updates