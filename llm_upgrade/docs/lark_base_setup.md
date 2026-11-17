# Lark Base setup for the simulated daily SLA monitor

This guide sets up a Lark Base that tracks the two tagging vendors day by day. The data comes from
`src/12_simulated_daily_sla.py`. The batches, dates, thresholds and owner roles are **simulated**. The
labels, quotes, tokens and retries behind each row are real.

Lark menu names change between versions. If a name below does not match what you see, look for the
nearest option with the same purpose.

## 1. Files to import

| File | Rows | What it is |
|---|---|---|
| `reports/lark_export/sim_daily_sla_by_batch_vendor.csv` | 14 (7 batches x 2 vendors) | the main table |
| `reports/lark_export/sim_sla_thresholds.csv` | 8 | the thresholds, as a reference table |

Both files are UTF-8, with ISO dates (`YYYY-MM-DD`) and one value per cell.

**Import:** create a new Base, then choose import from a CSV file. Import the main file as table
`SLA daily`, and the thresholds file as table `SLA thresholds`. Then check each field type against
the table below and change it where Lark guessed wrong.

## 2. Fields in `SLA daily`

| Field | Lark field type | Notes |
|---|---|---|
| `sim_batch_id` | Text (primary field) | `SIM-B01` to `SIM-B07` |
| `sim_batch_date` | Date | simulated day of the batch |
| `vendor` | Single option | `rules`, `llm` |
| `sim_owner_role` | Text | role only; see "Owner" below |
| `output_volume` | Number, 0 decimals | reviews tagged in the batch |
| `reviews_with_stage` | Number, 0 decimals | reviews with at least one stage |
| `labels_produced` | Number, 0 decimals | stage labels given |
| `failure_rate` | Number, percent | reviews with no answer after all retries |
| `retry_rate` | Number, percent | reviews that needed a second attempt; cause not logged |
| `quotes_checked` | Number, 0 decimals | LLM only; blank for rules |
| `quote_fail_rate` | Number, percent | LLM only; quotes that are not exact substrings |
| `input_tokens`, `output_tokens` | Number, 0 decimals | 0 for rules |
| `cost_usd` | Currency (USD), 4 decimals | prices are VERIFY, see `config/pricing.yaml` |
| `cost_per_1000_usd` | Currency (USD), 4 decimals | |
| `disagreement_rate` | Number, percent | share of reviews where rules and LLM differ; same on both rows of a batch |
| `person_labelled_in_batch` | Number, 0 decimals | person-labelled reviews that fell in the batch |
| `qa_sample_size` | Number, 0 decimals | QA items checked (up to 10) |
| `qa_precision`, `qa_recall`, `qa_f1` | Number, 2 decimals | on the QA sample only |
| `breach` | Checkbox | the file has `TRUE`/`FALSE`. If Lark imports it as text, add a Checkbox field and fill it with a formula or by hand, or use a Single option field with the values `TRUE` and `FALSE` |
| `breach_reason` | Text (long) | every failed check, separated by `;` |
| `sim_status` | Single option | `Open`, `No action`. Add `Investigating` and `Closed` for the workflow |

**Fields to add by hand:**

| Field | Type | Use |
|---|---|---|
| `Owner` | Person | the real person for each vendor. Fill it from `sim_owner_role` |
| `Issue log ID` | Text | links a breach to a row in `docs/issue_log.csv` |
| `Closed on` | Date | set when `sim_status` becomes `Closed` |
| `Root cause` | Text (long) | filled during the investigation |

## 3. Views

1. **Grid: All batches.** Sort by `sim_batch_date`, then `vendor`. Group by `vendor`.
2. **Grid: Breaches only.** Filter `breach` is checked. Show `sim_batch_id`, `vendor`, `breach_reason`, `Owner`,
   `sim_status`.
3. **Kanban: By status.** Group cards by `sim_status` (`Open` -> `Investigating` -> `Closed`, plus `No action`).
   Card shows `sim_batch_id`, `vendor`, `breach_reason`, `Owner`.
4. **Dashboard** (add a dashboard to the Base):
   - Number: count of records where `breach` is checked.
   - Line chart: `qa_f1` by `sim_batch_date`, one line per `vendor`.
   - Line chart: `disagreement_rate` by `sim_batch_date`.
   - Bar chart: sum of `cost_usd` by `sim_batch_date` (LLM only).
   - Bar chart: count of records by `sim_status`.

## 4. Automation rules

Create these in the Base's automation settings. Test each one on a copy of one row first.

**Rule 1: Alert the owner when a batch breaches.**
1. Trigger: when a record matches conditions. Table `SLA daily`. Condition: `breach` is checked.
2. Action: send a Lark message. Recipient: the `Owner` field.
3. Message text:
   `SLA breach: {sim_batch_id} ({vendor}) on {sim_batch_date}. Reason: {breach_reason}. Please investigate within 1 working day.`
   Insert the field values with the field picker.
4. Second action: update the record. Set `sim_status` to `Open`.

**Rule 2: Ask for an issue log entry.**
1. Trigger: when a record matches conditions. Condition: `sim_status` is `Investigating` and `Issue log ID` is empty.
2. Action: send a Lark message to `Owner`: `Please add an issue log ID for {sim_batch_id} ({vendor}).`

**Rule 3: Record the close date.**
1. Trigger: when a record matches conditions. Condition: `sim_status` is `Closed`.
2. Action: update the record. Set `Closed on` to today.

**Rule 4: Daily reminder for open breaches (optional).**
1. Trigger: at a scheduled time, every working day at 10:00.
2. Action: find records where `sim_status` is `Open`, and send one message to the team group listing them.

These rules follow `docs/qa_escalation_sop.md`.

## 5. What the current data shows

From `reports/lark_export/sim_daily_sla_by_batch_vendor.csv`:
- 3 of 14 rows breach (`breach` = `TRUE`): rules in `SIM-B01` and `SIM-B04`, and the LLM in `SIM-B01`.
- All 3 breaches are `QA F1 below 0.6`. Every other check passes in every batch.
- Each QA sample has only 9-10 reviews, so one or two wrong labels can move QA F1 below 0.6. Read a single
  breach as "check this batch", not as proof that quality dropped.

## 6. Refreshing the data

1. Rerun `python 12_simulated_daily_sla.py` from `llm_upgrade/src`.
2. In Lark, import the new CSV into the existing `SLA daily` table and choose to update existing records,
   matched on `sim_batch_id` + `vendor` if the importer allows it. Otherwise replace the table's rows.
3. Fields you added by hand (`Owner`, `Issue log ID`, `Root cause`, `Closed on`) are not in the CSV. Check
   they survive the update.
