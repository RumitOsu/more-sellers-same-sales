# More Sellers, Same Sales

A business review of the Brazilian marketplace Olist, written the way I would write it for a company's leadership team. It opens with an executive summary that takes two minutes to read, gives the evidence behind each point, and ends with four recommendations.

**Read it here: https://rumitosu.github.io/projects/more-sellers-same-sales/**

## The question

Olist lets small merchants sell on Brazil's large shopping sites through one shared storefront. In 2018 it published the records of about 100,000 of its orders. I treated that file as if I were the analyst on the inside in September 2018, where the data ends, and asked what a leadership team would need to know: how the business is doing, why, and what to do next.

## What the review found

- **Growth stopped.** Sales more than tripled during 2017 and peaked at R$1.0 million in November. No month in 2018 matched it.
- **More sellers did not help.** By the summer of 2018 there were 27% more active sellers than in the first quarter and 6% less in sales. The 1,238 sellers who were active in both the spring and the summer sold 15% less, so the shortfall is in demand and not in supply.
- **One order in seven ended in a one- or two-star review.** Four kinds of order (never arrived, arrived late, and two kinds of multi-item order) are 18% of orders and 58% of those reviews.
- **Late deliveries come in episodes.** Four of the twenty months produced 55% of all late deliveries, and in those months 30% of the parcels sent to Rio de Janeiro arrived late.
- **Three late customers in four were asked for a rating before their parcel had arrived.**
- **The seller base is top-heavy and it leaks.** 31 sellers bring in 26% of sales, and 35% of new sellers have stopped selling by their fourth month. A seller's first thirty days are a strong sign of whether they will stay.

The page also says what I tested and dropped (a rule for setting delivery promises from recent history did no better than the promise Olist already made) and what the data cannot tell us.

## How it is built

| Step | File | What it does |
| --- | --- | --- |
| 1 | `analysis/00_download.py` | Downloads the nine public tables. No account or key is needed. |
| 2 | `analysis/01_build.py` and `analysis/01_model.sql` | Loads the tables into DuckDB and builds one table with a row for each order, joining items, payments, ratings, customers, sellers and products. |
| 3 | `analysis/02_analysis.py` | Computes every figure and chart series in the report and writes them to `results/results.json`. |
| 4 | `analysis/03_build_page.py` | Fills `site/src.html` with those results and writes `site/index.html`. |

Every number in the report's text is a placeholder in `site/src.html` that the last step fills in, so the wording, the charts and the analysis cannot drift apart. The charts are drawn in plain JavaScript and SVG with no charting library.

## Running it yourself

```bash
python -m venv .venv
.venv/Scripts/python -m pip install duckdb pandas numpy
cd analysis
../.venv/Scripts/python 00_download.py
../.venv/Scripts/python 01_build.py
../.venv/Scripts/python 02_analysis.py
../.venv/Scripts/python 03_build_page.py
```

On macOS or Linux the interpreter is at `.venv/bin/python`. The finished page is `site/index.html`. It expects the fonts of my portfolio site two folders above it, and it falls back to the system fonts when opened on its own.

## The data

The [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), which the company shares under the CC BY-NC-SA 4.0 licence, downloaded from Olist's own [GitHub copy](https://github.com/olist/work-at-olist-data). The raw files are not kept in this repository.

Olist did not say how the published orders were chosen. The review treats the file as the whole business and says so in its notes. If orders were left out, totals and repeat purchases are understated, while rates measured inside each order, such as the share that arrived late, are not affected.

I have never worked for Olist, and this is a portfolio project.
