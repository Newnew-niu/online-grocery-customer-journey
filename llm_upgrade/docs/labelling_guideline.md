# Labelling guideline: customer journey stages

**Version 1, 2026-11-17.** For anyone who labels grocery-app reviews or checks a vendor's labels.

The definitions come from the frozen LLM prompt `prompts/journey_stage_v2.md`. The examples and edge cases
come from the 100 test reviews that a person blind-labelled (`reports/test_recheck_labels_100.csv`).
Reviews are named by `val_id` only. Review text is not stored in the repo
(`../.gitignore`: "privacy / store terms"); the description after each ID is a short summary.

This guideline was written **after** those 100 labels were made. It is for future labelling rounds. It does not
change any existing label.

## 1. General rules

1. **Label problems only.** Tag a stage only when the review reports a problem, complaint or missing feature at that
   stage. Praise gets no stage.
2. **Tag where the problem happens.** Do not tag a stage that is only background, such as "when I got to the checkout".
3. **General complaints get no stage.** "Awful app" alone gets nothing, however strong.
4. **Physical stores get no stage**, unless it is clearly a loyalty card or voucher problem (PL) or a login problem (AL).
5. **A review can have several stages, or none.** Write `NONE` when no stage applies. Do not leave the cell blank.
6. **Unsure? Pick your best reading and write a note.** Notes feed the edge-case list in section 4.

## 2. Stages

Counts are person / AI-made labels on the 100 test reviews. Source: `reports/label_recheck_agreement_100.json`
(`per_stage_treating_person_as_truth`, person = tp + fn, AI = tp + fp).

| Code | Stage | Tag when the review reports a problem with... | Person / AI labels |
|---|---|---|---|
| AL | Account & login | signing in or out, being logged out, passwords, registering, verifying an account, linking a card to an account | 19 / 23 |
| SB | Search & browse | finding products in the app: search, filters, categories, menus, layout, favourites, lists, product information. Not an item the shop does not sell | 7 / 8 |
| BA | Basket | adding or removing items, quantities, the basket emptying or changing | 2 / 2 |
| SL | Delivery slot | finding, booking or changing a delivery or collection time slot | 1 / 2 |
| CP | Checkout & payment | completing an online order or payment, saved cards, bank approval, wallet payment, entering an address when ordering. Not a store till | 11 / 15 |
| SM | Substitutions & missing items | substituted, missing, wrong, damaged or out-of-stock items, poor freshness or short dates | 3 / 6 |
| DC | Delivery / collection | the delivery or collection service itself: late or failed delivery, drivers, where the order was left, choosing a collection store. Delivery fees are PL. Damaged items are SM | 5 / 5 |
| RS | Refunds & customer service | refunds, overcharges to resolve, contacting support, slow or missing replies, no way to contact anyone | 6 / 9 |
| AP | App performance | a technical fault: crashes, slowness, freezing, loading failures, error messages, the app not opening, bugs after an update | 26 / 32 |
| PL | Pricing, promotions & loyalty | prices, fees (including delivery fees and plans), offers, vouchers, coupons, points, loyalty cards such as Clubcard | 23 / 32 |

**AP with another stage:** if a failure belongs to one stage, such as login or payment, tag that stage. Add AP only
when the review also describes a technical fault (crash, freeze, error, slowness). "Problems with the app" alone is
not AP.

## 3. Examples

A **positive** example should get the stage. A **negative** example mentions the topic but should not get the stage.
Positive examples are reviews where the person, the AI-made labels and the LLM all gave the stage.
Negative examples are reviews where the person did not give the stage but a tagger did.

| Code | Positive | Negative |
|---|---|---|
| AL | #30: login often fails with a "wrong email or password" message | #7: vouchers vanished from the account. The problem is vouchers (PL), not the account. The rules tagged AL |
| SB | #12: hard to search through the menus, results stuck on one default list | #28: cannot scroll to confirm on the payment screen. The rules tagged SB because of the scrolling |
| BA | #37: cannot fill the cart without booking a slot first (person and AI gave BA; the LLM did not) | NOT AVAILABLE: no review in the 100 has a clean basket negative |
| SL | NOT AVAILABLE: no review where all three agree on SL | NOT AVAILABLE |
| CP | #81: cannot pay; wants a wallet payment option | #56: charged money for an order the reviewer did not place. The person gave no stage, the AI gave CP, the LLM gave RS. See section 4 |
| SM | #75: many usual items out of stock online | #40: complains that some items sold in store cannot be bought online. That is a product-range complaint, not a missing or out-of-stock item in an order. Person: no SM. AI: SM |
| DC | #29: the order did not arrive | #40: says they get on well with the drivers (praise). The rules tagged DC |
| RS | #29: support blamed the customer and gave no help | #96: had to call the helpline, but says the person on the phone was helpful. Person: no RS. AI: RS |
| AP | #12: very slow, stalls, blank screen, reloads | #30: features open in a web browser instead of the app. A design complaint, not a technical fault. The rules tagged AP |
| PL | #61: prices in the app do not match the store | #73: says they are a Clubcard user, but the problem is login (AL). The rules and the LLM tagged PL |

## 4. Edge cases from real disagreements

Each case below is a review where the person's labels and the AI-made labels or a tagger's labels differ
(`reports/test_recheck_labels_100.csv`, `reports/llm_disagreements.csv`). The decision is the rule to use from now on.

| # | Reviews | What happened | Decision |
|---|---|---|---|
| 1 | #28, #77, #5 | Payment or order completion fails. Person: AP. AI: CP. LLM: AP+CP, AP and CP+RS | Tag CP for a failure to complete payment or the order. Add AP only if a crash, freeze, error or slowness is described. For #5 (bank validation keeps failing, long calls to support), tag CP and RS |
| 2 | #26, #20 | Repeated sign-in trouble ("keeps making me sign in"), or slow set-up. Person: AP (#26), AL+PL (#20). AI: AL (#26), AL+AP (#20) | Being asked to sign in again and again is AL. Slowness is AP. Tag both when both are described |
| 3 | #3, #62 | Loyalty card cannot be authorised or keeps needing re-authorising. Person: AL. AI and LLM: AL+PL | Linking or authorising a card is AL. Add PL only if points, vouchers or prices are the problem |
| 4 | #31 | Cannot look up foods or deals in the app. Person: PL. LLM: SB. AI: PL+SB | Not finding things in the app is SB. Add PL only if the deal itself is wrong or missing |
| 5 | #93, #79 | Items missing or found unavailable at checkout. Person: BA (#93), PL (#79). AI: SM in both | Missing or unavailable items are SM. BA is only for adding, removing or changing items in the basket |
| 6 | #39 | Changing quantities is very slow. Person: AP. AI and LLM: AP+BA | The basket works but slowly: AP only. Tag BA only if the basket does the wrong thing |
| 7 | #37, #45 | Slot problems. #37: cannot fill the cart without first booking a slot (AI: SL; person: no SL). #45: failure to update orders (person: SL; AI: no SL) | Tag SL only when finding, booking or changing a time slot is the problem. A required booking step that blocks shopping is SL |
| 8 | #96, #40 | Support is mentioned; the person gave RS to neither. #96: called the helpline and says the agent was helpful (AI: RS). #40: rang support about crashes and was told the problem was on their side (AI and LLM: RS) | Tag RS only when support itself is a problem: no reply, unhelpful, blames the customer, refuses a refund. So #96 is not RS, and #40 is RS (plus AP for the crashes) |
| 9 | #68 | The delivery came earlier than the booked window, and emails get no reply. Person: RS. AI and LLM: DC+RS | Late, early or failed delivery is DC. Tag both DC and RS here |
| 10 | #61 | In-store prices differ from the app. Person: DC+PL. AI and LLM: PL | There is no delivery problem in the review, so DC does not apply. Tag PL. A possible slip in the person's labels; kept as it was |
| 11 | #56 | Charged money for an order the reviewer did not place. Person: none. AI: CP. LLM: RS | An unexplained charge to be resolved is RS ("overcharges to resolve") |

**Most common type of disagreement:** the person gave 103 labels and the AI-made labels 134
(`reports/label_recheck_agreement_100.json`, `labels_given`). Comparing the label sets review by review in
`reports/test_recheck_labels_100.csv`: 52 reviews match exactly. On 28 the AI labels contain all of the person's
labels plus at least one more stage. On 7 the AI labels have fewer. On 13 they differ in other ways. So the most
common problem is an extra stage, as in cases 3 and 6. The rule "tag where the problem happens" (section 1, rule 2)
is the main fix.

## 5. How to use this guideline

- New labellers: read sections 1-2, then label 10 reviews and compare them with a second labeller before starting.
- QA checkers: use section 4 when deciding whether a vendor's label is wrong. Log new cases in `docs/issue_log.csv`
  and add them here with a new version number.
- Changes to this guideline do not change existing labels. If a definition changes, rescore with both versions.
