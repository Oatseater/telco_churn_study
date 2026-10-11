<!-- GENERATED FILE. Edit templates/memo.template.md, then run `python run_pipeline.py`. -->

# Where to spend the retention budget

To: [PLACEHOLDER: name and role]
From: [PLACEHOLDER: your name]

*{{disclaimer}}*

## The problem

{{churn_rate}} of our {{n_customers}} customers left. They were paying {{monthly_revenue_churned}} a month
between them, which is {{annual_revenue_at_risk}} a year. We want one way to keep people that pays for itself.

## What I found

Short contracts leave. Month-to-month customers left at {{mtm_churn}}, against {{two_year_churn}} on
two-year contracts. They account for {{mtm_share_risk}} of the money at risk.

The first year decides it. In the {{first_bucket_label}} band, {{first_bucket_churn}} left. Customers with
12 months or less are {{first_year_share_customers}} of the base and {{first_year_share_risk}} of the money at risk.

New customers on big bills are the sharpest problem. In the {{seg_top_churn_name}} group, under a year with
us and paying a lot, {{seg_top_churn_rate}} left. They're {{seg_top_churn_share_customers}} of customers and
{{seg_top_churn_share_risk}} of the money at risk.

## What I'd do

Offer {{rec_segment}} customers {{default_discount}} off for {{horizon_months}} months if they move to a
one-year contract. Test it against a group that gets no offer before rolling it out.

| | Over {{horizon_months}} months |
|---|---:|
| Customers offered | {{rec_customers}} |
| Kept who would have left | {{rec_saved}} |
| Billing kept | {{rec_revenue_saved}} |
| Cost of the discount | {{rec_cost}} |
| Net result | {{rec_net}} |

That assumes {{default_save_rate}} of would-be leavers stay because of the offer, and that everyone offered
takes it, including people who were staying anyway. Both numbers are my guesses. It breaks even if
{{rec_break_even}} stay. I gave no extra credit for the longer contract itself. If that helps, it's upside.

Don't put a blanket discount on our biggest group at risk, {{seg_top_risk_name}}. Most of them stay anyway,
so the same offer there loses {{top_risk_blanket_loss}}. Look after them instead.

## The risk

The save rate is a guess. If fewer people are persuaded than I assumed, or the offer mostly rewards people
who were staying anyway, the return shrinks. A test over [PLACEHOLDER: test length] measures it before we
commit the budget. All figures are billing, not profit, and they show patterns in the data, not proof that
the offer makes people stay.
