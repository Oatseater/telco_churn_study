<!-- GENERATED FILE. Edit templates/README.template.md, then run `python run_pipeline.py`.
     Every number below is filled in by code from reports/metrics.json. -->

# Telco churn

Who leaves a phone company, how much money leaves with them, and whether paying to keep them is worth it.

> {{disclaimer}}

```bash
pip install -r requirements.txt && python run_pipeline.py && streamlit run app.py
```

![Overview page](assets/screenshots/overview.png)

## The problem

{{churn_rate}} of the customers in this data left. Between them they were paying
{{monthly_revenue_churned}} a month, which is {{annual_revenue_at_risk}} a year.

The obvious move is a discount to keep people. The catch is that nobody knows in advance who
is about to leave, so the discount also goes to people who were staying anyway. I wanted to
know where an offer still pays for itself once you count that.

## What I did

I used the public IBM Telco Customer Churn sample
([Kaggle mirror](https://www.kaggle.com/datasets/blastchar/telco-customer-churn)):
{{n_rows}} customers, {{n_cols}} columns, one row each. It's a teaching dataset, not a real
company's books.

I checked the data before touching it ([full report](reports/audit_report.md)):

| What I found | What I did about it |
|---|---|
| `TotalCharges` stored as text, with {{n_blank_total_charges}} blanks, all for customers at 0 months | Set them to 0. They hadn't been billed yet |
| No real nulls. "Missing" meant blank text | Read every column as text first so blanks showed up |
| {{n_dup_ids}} duplicate IDs, {{n_dup_profiles}} rows identical apart from the ID | Kept them. All new basic-plan customers with the same bill |
| {{n_outliers}} values outside 1.5 x IQR | Removed nothing |
| {{share_totals_consistent}} of customers have `TotalCharges` within 20% of tenure x monthly charge | The columns agree with each other |
| Add-ons coded Yes / No / "No internet service" | Kept as is. Add-on numbers only count internet customers |

Then I loaded it into SQLite and did the core work in SQL, one file per question:

{{query_table}}

On top of that:

| Step | How | Where |
|---|---|---|
| Retention | Kaplan-Meier survival by month, written as a recursive CTE | `queries/08`, `queries/09` |
| Segments | Five rule-based groups from tenure, monthly bill and number of services | `src/schema.sql`, `queries/10` |
| Model | Plain logistic regression, stratified {{test_size}} test split, scored on ROC AUC | `src/model.py` |
| Money | Revenue at risk, and a calculator for discount offers | `src/economics.py` |
| Dashboard | Four pages in Streamlit. This README and the memo are generated from the numbers | `app.py`, `pages/`, `src/report.py` |

Every choice and every dead end is in [DECISIONS.md](DECISIONS.md).

How I counted: churn rate is the share of customers marked as gone. Revenue at risk is what
the people who left were paying each month, times 12. Money is billing, not profit, and I'm
assuming US dollars because the data doesn't say.

## What happened

{{n_churned}} of {{n_customers}} customers left. That's {{share_revenue_churned}} of monthly billing.

Contract length matters most. Month-to-month customers left at {{mtm_churn}}. One-year, {{one_year_churn}}.
Two-year, {{two_year_churn}}. That's {{mtm_vs_two_year_x}} times as often on month-to-month, and those
customers are {{mtm_share_customers}} of the base and {{mtm_share_risk}} of the revenue at risk.

The first year is where it happens. Churn is {{first_bucket_churn}} at {{first_bucket_label}} and
{{last_bucket_churn}} at {{last_bucket_label}}. Customers with 12 months or less are
{{first_year_share_customers}} of the base and {{first_year_share_risk}} of the money at risk. Overall,
{{ret_12}} are still here after a year and {{ret_60}} after five. After two years, {{ret_mtm_24}} of
month-to-month customers remain, against {{ret_one_24}} on one-year and {{ret_two_24}} on two-year contracts.

Fiber is the expensive product, and it leaks. Fiber customers left at {{fiber_churn}}, against
{{dsl_churn}} on DSL and {{no_internet_churn}} with no internet. They pay {{fiber_avg_charge}} a month on
average and carry {{fiber_share_risk}} of the revenue at risk from {{fiber_share_customers}} of customers.

Paying by {{top_payment_method}} goes with leaving: {{top_payment_churn}}, against {{auto_payment_churn_low}}
to {{auto_payment_churn_high}} on automatic payment. Among internet customers, those without {{top_addon}}
left at {{top_addon_without}}, against {{top_addon_with}} with it. For {{second_addon}} it's
{{second_addon_without}} against {{second_addon_with}}. Streaming add-ons move it by {{streaming_gap_max_pts}}
points at most.

The segments split risk hard, and the biggest pot of money is not the place to spend.

{{segment_table}}

In {{seg_top_churn_name}}, {{seg_top_churn_rate}} left. They're {{seg_top_churn_share_customers}}
of customers and {{seg_top_churn_share_risk}} of the revenue at risk. {{seg_top_risk_name}} has the most money
at risk, {{seg_top_risk_amount}}, only because it's {{seg_top_risk_share_revenue}} of all revenue. Its churn is
{{seg_top_risk_churn}}.

The model backs this up. A plain logistic regression scores a test ROC AUC of {{model_auc}}. The one-line
rule "month-to-month means at risk" scores {{model_auc_rule}}. In the model's riskiest 10%,
{{model_top_decile_rate}} actually left, against {{model_test_churn}} on average. The strongest links,
holding the rest equal:

{{drivers_list}}

![Segments page](assets/screenshots/segments.png)

## What I'd do

Test a contract-upgrade offer on {{rec_segment}}, against a holdout group that gets nothing.

With my starting guesses ({{default_discount}} off for {{horizon_months}} months, {{default_save_rate}} of
would-be leavers kept, everyone offered takes it):

| {{rec_segment}}: {{rec_customers}} customers, {{rec_churn}} churn | |
|---|---:|
| Customers kept | {{rec_saved}} |
| Billing kept over {{horizon_months}} months | {{rec_revenue_saved}} |
| Spent on the discount ({{rec_cost_stayers}} of it to people staying anyway) | {{rec_cost}} |
| Net result | {{rec_net}} |
| Break-even share who must stay | {{rec_break_even}} |

The same offer on every segment:

{{scenario_table}}

Only {{n_segments_positive}} segment makes money. In {{seg_top_risk_name}}, the discount handed to people
who were staying anyway comes to {{top_risk_blanket_cost_stayers}}, which sinks it to {{top_risk_blanket_net}}.
It would need {{top_risk_blanket_break_even}} of would-be leavers to stay just to break even. Aiming at its
{{top_risk_mtm_customers}} month-to-month customers only gets it to roughly break-even ({{top_risk_mtm_net}}).
For that group I'd skip the discount and look after them instead.

![Retention calculator](assets/screenshots/calculator.png)

## What this can't tell you

- It's a public teaching sample. The patterns show the method, not a real market.
- It shows what goes together, not what causes what. Moving someone onto a longer contract may not keep
  them the way it keeps people who chose one.
- It's one snapshot with no dates. The retention curve assumes people who joined years ago behaved like
  people who joined last month. Read literally, the churn flag ("left within the last month") doesn't fit
  the tenure numbers. DECISIONS.md, Stage 4, has the detail.
- The save rate is a guess, and the recommendation leans on it. The break-even rate shows the margin for
  error. Only a test gives the real number.
- It's billing, not profit. There's no cost data, so both sides of the sum would shrink with real margins.
- The model is a baseline. No tuning, no confidence intervals, one split. I left monthly charge out because
  the services held explain it almost entirely (R-squared {{model_r2}}).

## With more data

- Join, churn and plan-change dates, to follow real groups of customers over time.
- A proper test: offer against holdout, to measure the save rate instead of guessing it.
- Margin and cost to serve by product, so the calculator gives profit.
- Support tickets, outages and price changes, to see why fiber customers leave.
- Once there's test data, rank people by how much the offer changes what they do, not just by risk.

## Running it

```
run_pipeline.py      audit, clean, SQLite, SQL, retention, segments, model, money, docs
app.py, pages/       the dashboard: Overview, Retention, Segments, Retention calculator
queries/             one SQL file per question
src/                 pipeline code; schema.sql holds the segment rules
templates/           README and memo templates, numbers filled in by code
reports/             audit report, metrics.json, every query result as CSV
tests/               data checks, SQL checks, money maths, claim checks, page loads
assets/style.css     the look; assets/screenshots/ for this README
static/fonts/        Bodoni Moda (OFL) and TeX Gyre Heros (GUST), the Helvetica Neue fallback
scripts/canary.py    one command that checks the whole thing from a clean copy
DECISIONS.md         what I chose, what I dropped, and why
memo.md              one page for a manager
```

`pytest -q` runs the tests. `python scripts/canary.py` copies the repo without generated files, runs the
pipeline and tests, then clicks through every dashboard page in a headless browser and checks the numbers
on screen against `reports/metrics.json`. `python scripts/take_screenshots.py` refreshes the screenshots
while the app is running. Both scripts need Playwright, which I kept out of `requirements.txt`
(`pip install playwright && playwright install chromium`). Generated {{generated_at}}.

## Talking points

### The question
I asked where a retention offer pays for itself, not just who's likely to leave. A churn score
doesn't tell you what to spend.

### The audit
`TotalCharges` was text with blanks, and every blank was a customer at zero months, so I set them to zero
instead of dropping or guessing. I read everything as text first and put a schema check in front, so bad
input stops the pipeline.

### The SQL
Each question is its own SQL file with the question written at the top, using CTEs, CASE buckets and window
functions. Every split is tested to add back up to the totals.

### Retention
I used Kaplan-Meier, written as a recursive CTE, after the literal reading of the churn flag said almost
nobody lasts a year. Curves stop where fewer than {{min_at_risk}} customers are left, so noise doesn't pass
for a trend.

### Segments
I adapted RFM to tenure, monthly bill and number of services, using plain thresholds instead of quantiles,
because ties in tenure made quantile cuts arbitrary. Five segments, each with one rule and one action.

### The model
A plain logistic regression scored {{model_auc}} against {{model_auc_rule}} for a one-line contract rule,
and I show both so the gain is clear. I dropped monthly charge once I saw it was nearly the sum of the
services and was flipping signs.

### The money
The calculator charges the discount to everyone in the group, including people who were staying anyway,
because that's how offers work. That one detail is why the segment with the most money at risk is the wrong
place to discount.

### What I'd do and where it's weak
I'd test a contract-upgrade offer on {{rec_segment}} against a holdout, because it breaks even at
{{rec_break_even}}. It's a public sample, the save rate is a guess, and none of it proves cause.
