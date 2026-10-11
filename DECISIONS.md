# Decisions log

A running log of choices, dead ends and the reasoning behind them, written as the
work happened. Counts quoted here were read from the generated outputs at the
time (`reports/audit_report.md`, `reports/metrics.json`); those files are the
authoritative values and are regenerated on every pipeline run.

---

## 2026-10-10 - Stage 0: setup

- Python 3.11+ with pinned versions. The newest numpy release requires Python
  3.12, which would break the "3.11+" requirement, so I pinned numpy to the 2.3 line
  (supports 3.11). All other pins are the latest versions that installed cleanly.
- Schema guard before anything else. `src/audit.py` compares the raw file's
  columns with the exact published Telco schema and stops with a clear message if
  the file is missing or different. I chose to fail loudly rather than try to map
  unexpected columns, because a silent mismatch would make every downstream number
  wrong.
- Generated README and memo. The brief says every number in the README, memo
  and dashboard must be computed by code. Rather than paste numbers in by hand, I
  write `templates/README.template.md` and `templates/memo.template.md` with
  placeholders, and `run_pipeline.py` fills them from the computed metrics. The
  renderer fails if any placeholder is left unfilled. Qualitative claims in the
  text ("month-to-month churns most") are checked by `tests/test_claims.py`, so if
  the data changed and a claim stopped being true, the tests would fail.

## 2026-10-10 - Stage 1: audit

Read the raw CSV with every column as text, so type problems show up instead of
being silently coerced.

- TotalCharges is text, with 11 blank strings. pandas would have read the
  column as `object` because of them. Every blank belongs to a customer with
  tenure 0, and those are the only tenure-0 customers.
- No true NaN values. "Missing" in this file means blank strings, not NaN.
- customerID is unique. There are 22 rows identical on every column except the ID.
- No outliers under the 1.5 x IQR rule on tenure, MonthlyCharges or
  TotalCharges. The value ranges are plausible (tenure 0 to 72 months, monthly
  charge roughly 18 to 119).
- TotalCharges roughly equals tenure x MonthlyCharges. The median ratio is
  close to 1, with a spread consistent with price changes over time. So the
  columns agree with each other, and I found no sign of corrupted rows.
- Categorical encodings mix three states. Add-on columns carry
  "Yes / No / No internet service", and MultipleLines carries "No phone service".
  SeniorCitizen is 0/1 while every other flag is Yes/No.

## 2026-10-10 - Stage 2: cleaning

- Blank TotalCharges set to 0, not dropped and not imputed. These customers
  have tenure 0: they joined but have not completed a billing cycle, so 0 is the
  true value, not a guess. Dropping them would remove real customers from the
  counts. Imputing MonthlyCharges (a common Kaggle fix) would invent a payment
  that never happened. The cleaning step asserts that the rule still holds, so if
  a blank ever appears for tenure > 0, the pipeline stops.
- Kept the 22 rows that repeat except for the ID. IDs are unique. I checked
  the repeated profiles: every one is a month-to-month customer at tenure 1 on a
  basic plan (most are phone-only), where identical bills are expected. Treating them as duplicates would delete real
  customers and bias the churn rate.
- No outlier removal or capping. Nothing fell outside the fences, and the
  extremes are legitimate (72 months is the dataset's maximum tenure).
- Kept "No internet service" as recorded. It means the customer lacks the
  base service, which is informative. For add-on analysis I restrict to internet
  customers rather than recoding it to "No", which would mix "chose not to buy"
  with "could not buy".
- SeniorCitizen kept as a 0/1 integer; added a `churned` 0/1 flag next to
  the original Yes/No label so SQL can use `AVG(churned)` directly.
- snake_case column names so the SQL reads cleanly (`tenure_months`, `monthly_charges`).
- gender is kept in the table but excluded from modelling and segmentation.
  See Stage 5.

## 2026-10-10 - Stage 3: SQL analysis

- One file per business question, each with a header comment stating the
  question, in `queries/`. The pipeline runs all of them, saves each result to
  `reports/query_results/`, and fails if any returns zero rows.
- Derived fields live in one view (`src/schema.sql` -> `customer_profile`):
  service counts and segment labels. Every query reads the same definitions, so
  "number of services" cannot mean different things in two places.
- Revenue at risk definition: monthly charges of churned customers x 12. It
  is simple and explainable in one sentence. I considered using model-predicted
  probabilities x charges for current customers. I rejected that for the headline
  KPI because it would put a baseline model's uncertainty into the dashboard's
  biggest number. The model stays a supporting tool.
- Add-on churn is computed among internet customers only (see Stage 2), and
  the query header says this is association, not effect.
- Payment method: I added a Manual vs Automatic grouping, because "automatic
  payment" is the lever a business can actually pull.

## 2026-10-10 - Stage 4: cohort retention

- Dead end: a "period life table" built from the churn flag. The dataset's
  documentation says Churn means "left within the last month". Taken literally,
  the monthly churn rate at each tenure month = churners at that tenure / all
  customers at that tenure, and chaining those rates gives a synthetic cohort.
  I computed it: the monthly rates in the first year come out between roughly
  31% and 62%, which implies almost nobody survives a year. The same file holds
  hundreds of customers at 72 months tenure, so the literal reading contradicts
  the data itself. I rejected it.
- Chosen: Kaplan-Meier. Each row is treated as one customer's history:
  churners left at their recorded tenure; active customers are censored at their
  tenure. This is the standard survival estimate and it gives plausible curves.
  Its assumption (that churners and stayers come from comparable joining cohorts)
  is stated on the Retention page.
- Written in SQL with a recursive CTE, which chains the survival
  probabilities month by month (`queries/08`, `queries/09`). This avoids
  `LN`/`EXP`, which not every SQLite build includes.
- Python mirror for filters. The dashboard lets you filter by internet
  service, payment method and segment. Writing dynamic SQL for every combination
  would be fragile, so `src/retention.py` repeats the same calculation in pandas,
  and a test asserts it matches the SQL output exactly.
- Curves are cut where fewer than 30 customers remain at risk. Without the
  cut, the month-to-month curve ends with 2 customers at 72 months, and one-year
  contracts show a fake cliff at month 72 from 17 customers. A single churner
  there moves the line by several points, which reads as signal but is noise.

## 2026-10-10 - Stage 5: segmentation

- Rejected: NTILE-based RFM scores. Classic RFM splits each axis into
  quantiles with `NTILE`. Tenure has heavy ties (over 600 customers at
  1 month), so NTILE would split identical customers into different tiers based
  on row order. That is arbitrary and not reproducible across databases.
- Chosen: three readable business thresholds, one per RFM-style axis:
  - Loyalty: first year (tenure under 12 months) vs established. A natural
    business boundary, and churn falls sharply after it.
  - Value: monthly charge of $70 or more. Close to the median charge, rounded so
    it can be said out loud.
  - Engagement: 5 or more of the 9 possible services.
- Engagement is used only among established high-spenders. That is where
  it separates churn most: a customer paying $70+ with a thin bundle is paying a
  lot for little. For new customers and low spenders it added segments without
  adding a different action, so I kept the count at five.
- Rules live in SQL (`src/schema.sql`) and are mirrored as constants in
  `src/config.py` for display; a test checks the two agree.
- gender excluded. It is a protected attribute with no business case for
  targeting offers, and it shows no churn difference here anyway.

## 2026-10-10 - Stage 6: baseline model

- Logistic regression only, default L2 regularisation, stratified 75/25
  split, fixed seed. No tuning: the model's job is to confirm which factors
  matter together, not to win on accuracy.
- Metric: ROC AUC. It measures how well the model ranks customers by risk,
  which is how a retention team would use it (who to call first). It is
  insensitive to the 26.5% / 73.5% class imbalance. I also report accuracy
  against the "predict nobody churns" baseline, precision and recall at 0.5, and
  churn in the top-10% risk group, because AUC alone means little to a manager.
- Compared against a one-line rule ("month-to-month = high risk") so the
  model's added value is visible, not assumed.
- Dropped TotalCharges: it is close to tenure x monthly charge.
- Dropped MonthlyCharges after trying it. With it in, the model said "each
  extra $10 on the bill lowers churn odds" while streaming add-ons raised them.
  That is a collinearity artefact. I regressed monthly charge on the service
  flags: R-squared is 0.999, so the bill is almost exactly the sum of the
  services. With it removed, AUC is unchanged and the coefficients are
  interpretable. The R-squared is recomputed on every run and shown in the README.
- Plain-English drivers. Coefficients are converted to odds ratios with
  meaningful units (per 12 months of tenure, has vs does not have). Effects
  within +/-10% are reported as "little difference" rather than over-read,
  since this baseline has no confidence intervals.

## 2026-10-10 - Stage 7: money layer and calculator

- The calculator charges the discount to customers who would have stayed
  anyway. A retention offer cannot be aimed only at future churners, because
  we do not know who they are. Leaving this subsidy out changes the answer. The "Established Full
  Bundle" segment has the most revenue at risk, but a blanket discount there
  loses money, because most of its customers would have stayed.
- Stayer uptake is an adjustable assumption (default 100%: everyone eligible
  takes a discount they are offered). This is conservative.
- Added a "month-to-month only" targeting option after seeing the result
  above. Narrowing the top revenue-at-risk segment to its month-to-month
  customers brings the default scenario to roughly break-even. That is useful
  to show: better targeting matters more than the size of the discount.
- Break-even save rate is reported for every scenario, because the save rate
  is the most uncertain input. "This works if at least X% of would-be churners
  stay" is a more honest claim than a single net-benefit figure.
- Gross revenue, not margin. The data has no cost information, so "net
  benefit" means revenue kept minus discount given. This is stated on screen.

## 2026-10-10 - Stage 8: dashboard

- Four pages through `st.navigation`, with styling and the disclaimer in `app.py`,
  so every page gets the same frame and the disclaimer cannot be forgotten on a new page.
- Custom HTML for KPI tiles and segment cards instead of `st.metric`. That gives
  monospace tabular numerals, an amber state for risk, and 1px borders without
  fighting Streamlit's defaults.
- One shared Plotly template (`src/theme.py`): navy accent, grey everything else,
  amber only for risk (above-average churn, a negative net benefit). Legends are off;
  every chart uses direct labels plus hover.
- Comparing more than three groups switches to highlight mode. Navy, mid-blue and
  light-blue shades pass a colour-separation check for three ordered groups (contract
  length). For five segments the shades become too close to tell apart, even with
  full colour vision. So one group is drawn in navy, the rest in grey, and the user
  picks which to highlight.
- Fixed after looking at screenshots. Bar labels clipped at the right edge (moved
  customer counts into hover). Waterfall labels rotated and collided (shortened, set
  horizontal). Segment cards were cramped in a three-column grid (changed to
  full-width rows). Tables showed cents and two-decimal percentages (whole dollars,
  one decimal). Negative axis ticks read "$-100,000" (now "-$100,000").
- Cache keys include the database file's modification time, so re-running the
  pipeline while the app is open refreshes the numbers.

## 2026-10-10 - Stage 9: memo and README

- Both are generated from templates and `metrics.json`. A test re-renders them
  and fails if the committed files differ, so a hand-edited number cannot slip in.
- Claim guards. Wording such as "only one segment returns more than it costs" or
  "roughly break-even" is backed by an assertion in `tests/test_claims.py`.
- The memo recommends a test, not a rollout. The save rate is assumed, and the
  break-even rate is the honest headline: the offer pays if a small share of would-be
  churners stay. The memo also states that it gives no extra credit for the longer
  contract, to avoid double-counting the upside.
- Memo wording fix: "would lose -$173,121" read as a double negative. Losses are
  now rendered as positive amounts after the word "lose".

## 2026-10-10 - Stage 10: verification

- AppTest limitation. `AppTest.switch_page` runs a page file without the `app.py`
  frame, so the disclaimer check failed for pages 2 to 4 even though it shows in the
  browser. I kept the AppTest page-load tests (no exceptions, header present) and moved
  the per-page disclaimer check to the real-browser script `scripts/take_screenshots.py`.
- Google Fonts is not reachable in my build sandbox, so the screenshots use the
  fallback system sans-serif. On a normal connection the app loads Inter and IBM Plex Mono.

## 2026-10-10 - Stage 11: canary check

- Added `scripts/canary.py`, a single command for "is everything still working?".
  It copies the repo without generated files, runs the pipeline and tests, checks
  that the committed README and memo match a fresh render, then starts the
  dashboard and drives it in a headless browser. It clicks every breakdown,
  every retention comparison, every calculator segment, the month-to-month toggle
  and a slider. It fails on page exceptions, JavaScript errors, server tracebacks,
  a missing disclaimer, or on-screen numbers that differ from `metrics.json`.
- First run: 15 of 15 checks passed. Nothing was broken.
- Proved it can fail. I added a deliberate error to the Segments page and re-ran
  it: three checks failed (tests, browser, server log) and the exit code was 1.
  Then I restored the file.

## 2026-10-10 - Stage 12: redesign to black and white

The brief changed: dark, black and white only, simple charts first, technical
detail further down the page. This replaces the navy and amber design from Stage 8.

- True black (#000000) and white, with three greys. No accent colour. White marks
  are what to look at; grey marks are context. Costs and losses use a diagonal hatch,
  since there is no red to lean on. Greys were chosen with the palette checker:
  the three line shades separate clearly on black, and context bars use #6B6B6B,
  which clears 3:1 contrast.
- Each page opens with its answer as one plain sentence, then one simple chart.
  Where it helps, numbers are given as people ("59 in 100") rather than percentages.
  Every headline is computed, and the qualitative parts ("heaviest at the start",
  "where most customers stay") have guard tests in `tests/test_claims.py`.
- "Behind the numbers" holds the technical layer: filters, survival curves,
  hazard rates, model odds ratios, the waterfall and sensitivity charts, tables,
  assumptions and method notes. A reader who wants only the answer can stop at the
  white rule; anyone checking the work keeps scrolling.
- One typeface, Atkinson Hyperlegible Next, designed by the Braille Institute for
  legibility. That suits a page whose job is to be easy to understand. It is bundled
  in `static/fonts` from the npm Fontsource package (OFL licence), so there is no
  Google Fonts call and screenshots match what users see. Numbers use its tabular
  figures rather than a monospace face.
- Removed the templated look: no all-caps labels, no boxed KPI cards, no coloured
  left borders, no card grid. Figures sit in a row under a rule; segments are rows
  in a list.
- Calculator: the headline sentence changes with the inputs ("keeps 143 customers
  and brings in..." vs "costs ... more than it brings back"). The advanced
  assumptions moved down into the technical section. Their values are read from
  session state at the top, so the headline still reflects them.
- Fixed after screenshots: gaps under charts without an x-axis; dollar amounts
  wrapping in segment rows; a chained Styler `.format()` that silently dropped the
  other columns' formatting (now one formatter dict); scatter and annotation labels
  colliding.

## 2026-10-11 - Stage 13: rework to my taste

New direction: dark and matte, warm near-black, brushed silver, one small red. Before changing
anything I listed what read as template or AI and got an okay. Then I changed one thing at a time.

- Palette. Warm near-black #121110 instead of pure black, silver text in three steps, 1px
  hairlines, and a fine grain over the page for a matte finish. Chart backgrounds are
  transparent so the grain runs through them. One red, #C8342C, a matte rosso that clears
  3.5:1 on the background. It marks the single most important thing on a page and appears at
  most twice per page. Widgets use silver, not red, so the red doesn't spread.
- Type. Bodoni Moda for headlines and chart titles: sharp, high contrast. Helvetica Neue for
  everything else, as asked. It's a paid font, so it isn't bundled. TeX Gyre Heros, a free
  Helvetica-style face, is the bundled fallback, shipped as the original .otf files under its
  licence. The Atkinson files are gone.
- Layout. The four pages had become one template repeated. Each page now has its own single
  lead visual: Overview, one bar showing where the money went; Retention, three survival lines;
  Segments, a dot plot; Calculator, the controls beside a statement. The row of big numbers is
  now a spec sheet: label left, value right, hairlines between. Space is uneven on purpose,
  with more before a section than after it.
- Controls. Segmented buttons became quiet text tabs with a silver underline. The sidebar
  marks the current page with a short silver line. The duplicate disclaimer in the sidebar is gone.
- Motion. One slow entrance for each headline (1.6s, heavy ease-out). Nothing else moves. The
  calculator opts out because its headline changes with every input. Reduced motion turns it off.
- Copy. Rewritten in my voice: short sentences, "I did", problem then what I did then result. I
  took out the bold lead-ins, the aphorisms and the "not X, but Y" lines. The headings now say
  what is under them.
- Invented details removed. The memo's recipient and author, the length of the test, and when
  to make the offer are now [PLACEHOLDER]. "Margins are thin" is gone because there's no cost
  data. The calculator says plainly that its starting values are my guesses.
- One personal line, "I did this for fun.", set in italic Bodoni at the bottom of the sidebar.
- Fixed along the way. The disclaimer's apostrophe was HTML-escaped, which broke a test once the
  sidebar copy was removed. It now escapes with quote=False and renders the same.
- Canary fix. After the rework the canary failed to open the Retention "Compare by"
  select. I checked whether my CSS broke it: with the grain layer switched off it still
  missed sometimes, so it wasn't the styling. The heavier pages were still drawing charts
  when the script clicked, so the field moved under the cursor. A person waits for the
  page to settle. The canary now does too: it waits until every chart has drawn, clicks
  the field itself rather than the middle of the whole block, and retries a missed click
  up to three times. Two clean runs in a row after that.
