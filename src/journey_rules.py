"""Keyword rules that tag a review with customer journey stages.

One review can have more than one stage (multi-label).
Each rule is a list of regular expressions. We match on lower-case text
(title + body). A review matches a stage if ANY pattern matches.

How the rules were built:
- Version 1 was written after reading a sample of negative reviews.
- It was checked on 100 hand-labelled reviews (the "development" sample).
- The mistakes were used to write this version 2.
- Version 2 is scored on a NEW sample of 100 hand-labelled reviews
  (the "test" sample) that was not used to write the rules.
"""
import re

STAGES = {
    "account_login": [
        r"\blog ?(in|on|out)\b", r"\blogg(ed|ing|s)? (me |you )?(in|out)\b", r"\blogin\b",
        r"\blogs? (me|you) out\b", r"\bsign(ed|ing|s)? ?(in|up|on|out)\b",
        r"\bregist(er|ered|ering|ration)\b", r"\bpassword",
        r"(?<!bank )\baccount\b", r"\bverif(y|ication|ied) (my |your )?(email|account|identity)",
        r"\bre-?authori[sz]e (my |your |the )?(club ?card|account|app)", r"\bre-?authenticat",
    ],
    "search_browse": [
        r"\bsearch", r"\bfilter", r"\bcategor", r"\bbrows(e|ing)\b",
        r"\bnavigat", r"\bscroll", r"\blayout\b", r"\bmenu\b",
        r"\b(un)?intuitive\b", r"\bconfus", r"\bhard to (find|use|understand)\b",
        r"\bfavou?rites?\b", r"\busuals\b", r"\bshopping list",
        r"\bfind (the |an |any |what )?(item|product|you)", r"\bproduct (info|description|image|picture)",
        r"\b(way|how) (the )?(offers|products|items) (are|is) (shown|displayed)",
    ],
    "basket_add_to_cart": [
        r"\b(add|adding|added|remove|removing|removed)\b.{0,25}\b(basket|cart|trolley)\b",
        r"\b(basket|cart|trolley)\b.{0,15}\b(keeps|won'?t|doesn'?t|empt|disappear|clear|lost|reset)",
        r"\badd (one|an|a single|more) (item|product|thing)", r"\bquantit",
        r"\bput (right )?back in (the )?basket",
    ],
    "delivery_slot_booking": [
        r"\bslots?\b", r"\bbook(ing|ed)? (a |my )?(delivery|collection|time)\b",
        r"\btime ?window",
    ],
    "checkout_payment": [
        r"(?<!at the )(?<!at )(?<!scan )(?<!self )\bcheck ?out\b",
        r"\bpayments?\b", r"\b(can'?t|cannot|couldn'?t|unable to|won'?t let me) pay\b",
        r"\bcard details\b", r"\b(my|the) bank\b", r"\bbank (app|card|approval)", r"\bapple ?pay\b",
        r"\bgoogle ?pay\b", r"\bvalidat", r"\b3d ?secure\b", r"\bdebit\b", r"\bcredit card\b",
        r"\bpaypal\b", r"\b(can'?t|cannot|unable to) (complete|place|submit) (my |the |an )?(order|purchase)",
        r"\border (won'?t|wouldn'?t|didn'?t|doesn'?t|still doesn'?t) go through", r"\borders? fail",
        r"\b(cannot|can'?t) order online", r"\b(input|enter|add)(ing)? (my |the )?address",
        r"\bcharged (much |me )?(more|extra|twice|double)",
    ],
    "substitutions_missing_items": [
        r"\bsubstitut", r"\bsubs\b", r"\breplace(d|ment)s?\b",
        r"\bmissing\b(?! (apple|google|feature|option|function))", r"\bleft (me )?short\b",
        r"\bout of stock\b", r"\bnot (in stock|available)\b", r"\bunavailable\b",
        r"\bwrong (item|product)s?\b", r"\bincorrect (item|order|product|delivery)",
        r"\bshort[- ]dated?\b", r"\bbest before\b", r"\buse[- ]by\b",
        r"\bdamaged\b", r"\bdented\b", r"\bsquashed\b", r"\brotten\b", r"\bmouldy\b",
        r"\bnot (very )?fresh\b", r"\bquality of (the )?(fresh|fruit|veg|meat|produce)",
    ],
    "delivery_collection": [
        r"\bdeliver(ed|y|ies)? (late|early|hours|to the wrong)", r"\b(hours|very|always|was|were|arrived) late\b",
        r"\blate deliver", r"\bnot delivered\b", r"\bnever (arrived|delivered|came|turned up)",
        r"\bdriver", r"\bclick (and|&|n) collect\b", r"\bcollection (point|time|order)",
        r"\bdoorstep\b", r"\bporch\b", r"\bdelivery (service|was|is|man|guy|person|team|company)",
        r"\b(issues?|problems?) with (the |my )?deliver", r"\bleft (my )?(shopping|order|bags)",
        r"\b(didn'?t|did not|don'?t) (ring|phone|call) (the|before)",
    ],
    "refunds_customer_service": [
        r"\brefund", r"\bcustomers? (service|care|support)", r"\bsupport\b",
        r"\bcomplain", r"\bcontact(ed|ing)? (them|customer|support|tesco|dunnes|supervalu|you|the store)",
        r"\bwho to contact\b", r"\bphon(e|ed|ing) (them|tesco|dunnes|supervalu|customer)",
        r"\b(no ?one|nobody) (answers|replied|responded|got back)", r"\bno (reply|response)\b",
        r"\bmoney back\b", r"\bget back to me\b", r"\bhelpline\b", r"\blive chat\b",
        r"\bovercharg", r"\bcharged (me )?(twice|double)\b", r"\bemail(s|ed)? (to|them)\b",
        r"\bhelp desk\b",
    ],
    "app_performance": [
        r"\bcrash", r"\bslow", r"\bfreez", r"\bfroze", r"\bglitch", r"\bbugs?\b", r"\bbuggy\b",
        r"\bspool", r"\bload(s|ing)?\b", r"\bnot working\b",
        r"\b(doesn'?t|does not|won'?t|wont|didn'?t|isn'?t|will not) (work|open|load|connect|download)",
        r"\b(can'?t|cannot|unable to) open\b", r"\bstopped working\b",
        r"\b(since|after) (the |an |last |latest |recent |every )?updat", r"\bkeeps? asking .{0,10}updat",
        r"\bupdate option\b", r"\berror", r"\bbuffer", r"\blag(s|gy|ging)?\b", r"\bstuck\b",
        r"\breinstall", r"\bconnect(ion|ivity)\b", r"\bnetwork (issue|error|problem)",
        r"\bwi-?fi\b", r"\btimes? out\b", r"\bblank screen\b", r"\bkeeps? (closing|shutting)",
        r"\bsomething (went|gone|has gone|is always) wrong",
    ],
    "pricing_promotions_loyalty": [
        r"\bpric(e|es|ed|ing)\b", r"\boverpriced\b", r"\bexpensive\b", r"\bdear(er)?\b",
        r"\bcost of\b", r"\b(delivery|service) costs?\b", r"\bcosts? (too|so) much\b",
        r"\bvouchers?\b", r"\bcoupons?\b", r"\bclub ?card\b", r"\bvalue ?(club|card)\b",
        r"\bloy?a?l?a?ty card", r"\bloyalty\b", r"\breal rewards\b", r"\brewards?\b", r"\bpoints\b",
        r"\boffers\b", r"\b(special|weekly|personal) offer", r"\bdeals?\b",
        r"\bdiscount", r"\bpromo(tion)?s?\b", r"\bfees?\b", r"\b(delivery|service) charges?\b",
        r"\b(delivery|subscription) (plan|pass|package|saver)", r"\bvalue for money\b",
        r"€\s?\d+(?![\dk])", r"\d\s?(euro|eur)\b", r"\bfob\b", r"\bbarcode\b",
    ],
}

STAGE_LABELS = {
    "account_login": "Account & login",
    "search_browse": "Search & browse",
    "basket_add_to_cart": "Basket / add to cart",
    "delivery_slot_booking": "Delivery slot booking",
    "checkout_payment": "Checkout & payment",
    "substitutions_missing_items": "Substitutions & missing items",
    "delivery_collection": "Delivery / collection",
    "refunds_customer_service": "Refunds & customer service",
    "app_performance": "App performance (crashes, speed)",
    "pricing_promotions_loyalty": "Pricing, promotions & loyalty",
}

_COMPILED = {s: [re.compile(p) for p in pats] for s, pats in STAGES.items()}


def tag_text(text):
    """Return a dict {stage: 0/1} for one review text."""
    t = str(text).lower().replace("\u2019", "'")
    return {s: int(any(p.search(t) for p in pats)) for s, pats in _COMPILED.items()}
