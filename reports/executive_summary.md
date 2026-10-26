# Executive summary - online grocery customer journey

**For:** an online grocery team (e-commerce, CRM, digital product). **Data:** real public data only; none of it is Tesco data (sources at the bottom).

## What we found

1. **The app itself is the biggest source of complaints, more than delivery.** In 2,091 recent reviews of the Tesco Ireland, Dunnes Stores and SuperValu apps, app performance (34% of negative reviews) and pricing/loyalty (32%) lead. Login problems get the lowest ratings (1.65 stars on average), often because users are logged out at the till. Reviews that mention delivery average 4.25 stars, so delivery is mostly praised.
2. **Each retailer has a different problem.** SuperValu: a slow, freezing app (65% of its negative reviews). Dunnes Stores: voucher value and expiry (51%) - a pricing-policy issue. Tesco: app speed, Clubcard/loyalty and login.
3. **Online, most shoppers are lost early, and new users are lost at checkout.** In 360,129 real e-commerce sessions, only 1.35% buy and 81% of carts are abandoned. The largest drop is from viewing a product to adding it to the cart (only 20% continue). Returning visitors convert 4.6 times better than new ones; only 48% of new users get from checkout to payment. Device type makes almost no difference.
4. **A small group drives most revenue.** In a real grocery panel of 2,467 households, the top RFM segment ("Champions", 21% of households) brings 46% of spend. Champions and Loyal together are 40% of households and 71% of spend.
5. **Broad campaigns did not measurably lift spend.** Three large campaigns, each sent to about 1,100 households, show no clear change in weekly spend compared with similar households (difference-in-differences; all 95% confidence intervals include zero).
6. **Coupons do not make customers disloyal.** Coupon users lapse less than non-users (1-2% vs 9%). After allowing for how often people shop, more coupon use goes with slightly more loyalty.

## What we recommend

| Priority | Action | Why | How to measure |
|---|---|---|---|
| 1 | **Make payment one tap** (Apple Pay / Google Pay; keep saved cards working without repeat bank checks). | 11% of negative reviews are about checkout/payment; 29% of sessions that reach payment still do not buy. | A/B test already designed: 2,959 users per group to detect +3 points (76.8% -> 79.8%). |
| 2 | **Stop forced log-outs** (longer sessions, biometric login), especially for loyalty cards at the till. | Login complaints have the lowest ratings; new users struggle most at checkout. | Login error rate; checkout -> payment rate for new users; app rating trend. |
| 3 | **Fix app speed on product lists and the basket.** | App performance is the #1 complaint; view -> cart is the biggest funnel drop. | Page load time; view -> add-to-cart rate. |
| 4 | **Protect top customers with service, not discounts.** | Champions + Loyal = 71% of spend; broad campaigns showed no lift. | Retention and spend of the top segments vs a holdout group. |
| 5 | **Add random holdout groups to every CRM campaign.** | Without them, campaign effects cannot be measured cleanly. | Uplift = targeted vs randomly held-out customers. |
| 6 | **Keep coupons, and target them** at "At risk" and "Big spender" segments. | No evidence that coupons reduce loyalty. | Win-back rate; second-trip rate. |

## Caveats

- Reviews are self-selected and skew negative. They show what kinds of problems exist, not how common they are among all customers.
- The web data is the **Google Merchandise Store** (real e-commerce, not grocery), Nov 2020 - Jan 2021.
- The transaction data is **The Complete Journey (84.51°)**: one anonymised US grocer in 2017. Campaigns were not randomised.
- The A/B test is **designed, not run**.

*Sources: Google Play and App Store reviews (Ireland, Oct 2024 - Oct 2026); BigQuery `ga4_obfuscated_sample_ecommerce`; `completejourney` R package (84.51°). Code and full method: see README.*
