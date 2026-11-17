# SOP: QA sampling and SLA escalation for tagging vendors

**Version 1, 2026-11-17.** Covers the two tagging vendors: the keyword rules and the LLM tagger.

This is a practice SOP for the **simulated** daily monitor (`src/12_simulated_daily_sla.py`). The thresholds, owner
roles and response times are simulated targets, not agreed contract terms. Numbers marked with a file path come from
that file.

## 1. Roles

| Role | Who (simulated) | Does what |
|---|---|---|
| Vendor owner | "Rules tagger owner", "LLM tagger owner" (`config/sla_thresholds_simulated.yaml`, `owners`) | investigates breaches of their vendor and fixes the cause |
| QA checker | a person trained on `docs/labelling_guideline.md` | labels the QA sample blind and records disagreements |
| Ops lead | the person who owns the monitor | reviews open issues, decides escalations, signs off closures |

In Lark Base, each role is a real person in the `Owner` field (`docs/lark_base_setup.md`).

## 2. QA sampling

- **Sample:** each daily batch, draw up to **10** reviews at random for QA (`qa_sample_per_batch`). With batches of
  298-299 reviews (`reports/lark_export/sim_daily_sla_by_batch_vendor.csv`, `output_volume`), that is about 3.3-3.4% of
  each batch.
- **In this simulation** the QA sample can only come from the 100 person-labelled test reviews, so it contained 9-10
  reviews per batch. In a live setup the QA checker would label a fresh random sample each day.
- **Blind labelling:** the QA checker labels the sample without seeing any vendor's labels, then compares.
- **Both vendors on the same sample:** this makes their QA scores directly comparable.
- **Small-sample warning:** with 10 reviews, one or two wrong labels can move QA F1 by more than 0.1. A single QA
  breach is a signal to look closer, not proof that quality fell (see step 4.2).

## 3. What counts as a breach

A batch breaches its SLA for a vendor if any check fails. Thresholds come from `config/sla_thresholds_simulated.yaml`.

| Check | Breach if | Applies to | Severity |
|---|---|---|---|
| Output volume | below 250 reviews | both | High: work not delivered |
| Failure rate | above 0.5% of reviews | both | High |
| Retry rate | above 1% of reviews | both | Low: watch the trend |
| Quote-check failures | above 1% of quotes | LLM | High: possible invented evidence |
| Rules-LLM disagreement | above 40% of reviews | both | Medium: one vendor may have drifted |
| Cost per 1,000 reviews | above $0.30 | both | Medium: check against the bill (`reports/cost_reconciliation.csv`) |
| QA sample size | below 8 | both | Medium: quality unknown |
| QA F1 | below 0.60 | both | Medium on one batch; High on two batches in a row |

## 4. Steps when a breach happens

**4.1 Alert (same day).** Lark sends the vendor owner a message with the batch, vendor and breach reason (automation
rule 1 in `docs/lark_base_setup.md`). `sim_status` becomes `Open`.

**4.2 Triage (within 1 working day).** The vendor owner:
1. Reads `breach_reason`.
2. For a QA F1 breach: label 10 more random reviews from the same batch. If F1 on all 20 is at or above the threshold,
   record "noise, no action" and close. If not, continue.
3. For a quote-check or failure breach: open the failed reviews in the cache or failure log and find the pattern.
4. Sets `sim_status` to `Investigating`.

**4.3 Log (when status becomes Investigating).** Add a row to `docs/issue_log.csv`:
`issue_id, date_found, issue, root_cause, impact, action, status, source`. Put the issue ID in the Lark record
(`Issue log ID`). Use short sentences. Use review IDs, not review text.

**4.4 Escalate** to the ops lead if any of these is true:
- A High severity breach.
- The same vendor breaches on two batches in a row.
- The cause is not found within 2 working days.
- A fix needs a change to the prompt, the rules or the labelling guideline.

**4.5 Fix.** Changes to a frozen prompt or to the rules need a new version, a dev-sample check and a note in the issue
log. Never change a prompt after seeing test results without reporting both runs.

## 5. How to close a breach

Close only when all of these are true:
1. The root cause is written in the issue log, or the breach is recorded as noise after the extra QA sample (step 4.2).
2. The action is done, or the ops lead accepted the risk in writing in the issue log.
3. The next batch passes the same check.
4. The issue log row has `status = Closed`, and the Lark record has `sim_status = Closed` (automation rule 3 sets
   `Closed on`).

## 6. Weekly review

Every week the ops lead reviews:
- breaches per vendor and their reasons
- open issues older than 5 working days
- the QA F1 trend per vendor
- cost against the bill (`src/11_cost_reconciliation.py`; flag a variance above 5%, `config/pricing.yaml`)
- new edge cases to add to `docs/labelling_guideline.md`

## 7. Result of the simulated week

From `reports/lark_export/sim_daily_sla_by_batch_vendor.csv`: 3 of 14 batch x vendor rows breached, all on QA F1
below 0.60 with QA samples of 10 (rules in SIM-B01 and SIM-B04, the LLM in SIM-B01). Every other check passed. Under
this SOP each one would start with step 4.2: an extra QA sample of 10 before any escalation.
