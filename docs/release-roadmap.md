# Applicant Zero release roadmap

This roadmap keeps the product focused on compliant, high-coverage job
discovery and candidate-controlled applications. A listing always links to its
original source; Applicant Zero does not submit applications automatically.

## 1. Discovery Scale Foundation

- Store a large raw discovery inventory separately from the review queue.
- Normalise provider fields and retain first/last-seen timestamps.
- Expand the role and location vocabulary while keeping the daily queue
  candidate-relevant.
- Define one adapter contract for broad feeds, licensed providers and public
  employer ATS feeds.

## 2. Licensed Aggregator Trial

- Add an optional JobDataLake adapter behind a local `JOBDATALAKE_API_KEY`.
- Run a small Australia/Sydney coverage trial with a strict credit cap.
- Measure new, relevant, duplicate and stale listings before enabling a
  recurring provider schedule.

## 3. Employer Coverage Expansion

- Maintain a larger employer universe and research queue.
- Monitor only verified, public company career feeds automatically.
- Track source health and direct-source contribution.

## 4. Discovery Orchestration

- Add freshness windows, expiry, canonical cross-source deduplication and
  scheduled source budgets.
- Retain source provenance even when one preferred job card is shown.

## 5. Job Intelligence

- Improve Sydney/NSW/suburb, hybrid, remote-Australia, seniority and work-right
  checks.
- Place jobs into clear fit tiers with explanations and preparation blockers.

## 6. Truthful Preparation

- Generate candidate-reviewed, evidence-grounded résumé and cover-letter
  drafts with downloadable materials and requirement flags.

## 7. Tracker and Email Reconciliation

- Improve application stages, follow-ups and optional read-only Gmail matching.

## 8. Dashboard Consolidation

- Present the inventory, shortlist, coverage, preparation and outcomes as one
  coherent workspace after the discovery pipeline is reliable.

## 9. Hardening and Deployment

- Test backups/recovery, protect private files, add monitoring and deploy the
  private single-user app using Docker.

## Deferred inputs

These do not block other releases: a licensed provider API key, Google OAuth
credentials for read-only Gmail, and final deployment credentials.
