# Utility Bill Decoder

An AI assistant that reads Pakistani electricity bills (K-Electric, LESCO, IESCO) from a photo or scan, pulls out the billing details as structured JSON, and answers customer questions about the bill in plain English.

I built it in a 3-hour timed challenge at Women Tech Quest 2026 (Build with AI track, Lahore).

## What it does

- **Level 1, extraction:** reads one bill image and returns a JSON object with the provider, tariff, dates, meter readings, charge lines, tax lines, arrears and payable amounts. Personal details (names, addresses, account numbers) are never returned.
- **Level 2, questions:** answers a list of customer questions per bill ("How much of my bill is taxes?", "How many months went above 200 units?"). Answers use only what is printed on the bill, and estimates are labelled.

Bills can be tilted, partly in Urdu, and have grey boxes over personal details.

## How it works

1. **Two reads per bill.** The bill is read twice in parallel with a vision model. If the reads disagree, a third call looks at the image again and decides the disputed fields.
2. **Cleaning and checks.** The output is forced into the exact schema (numbers as numbers, ISO dates, credits as negatives, allowed charge and tax types). Consistency checks run on top: readings against units, charge lines against the subtotal, charges plus taxes against the current bill. A failed check triggers one re-read. Code never edits bill values itself.
3. **Narrow second look.** Sanctioned load is read again with a focused prompt because models often mix it up with nearby digits.
4. **History tables.** A separate call copies the monthly usage and billing history.
5. **Answers with exact maths.** The model writes any calculation as `{{expression}}` and Python evaluates it with a small safe calculator. Common figures (tax share, cost per unit, extra cost after the due date, history average, highest and lowest) are computed in code and given to the model to quote.
6. **No empty cells.** If a call fails after retries, the bill still gets a valid row.

## Project structure

```
source/
  main.py          command line entry point
  config.py        reads settings from .env
  llm.py           model API wrapper with retries
  prompts.py       all prompts
  extract.py       Level 1 pipeline
  validate.py      schema cleaning and consistency checks
  qa.py            Level 2 pipeline and safe calculator
  csv_io.py        CSV reading and writing
  examples/        one worked example bill used in the prompt
make_zip.py        checks outputs and builds a submission ZIP
```

## Setup

Python 3.11 or later (built with 3.12).

```
cd source
python -m venv .venv
.venv\Scripts\activate          # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # Mac/Linux: cp .env.example .env
```

Open `.env` and add your own API key:

```
MODEL_PROVIDER=openai
MODEL_NAME=gpt-5-mini
API_KEY=your-api-key-here
WORKERS=10
```

## Run

With a folder of bill images and the two CSV templates (`level1.csv` and `level2.csv`):

```
python main.py --bills path/to/bills --csv path/to/csv --out path/to/output
```

To try it on bills without templates, add `--dev`. It uses three sample questions:

```
python main.py --bills path/to/bills --out dev_output --dev
```

The CSV format follows the challenge: `level1.csv` has `bill_id, json` and `level2.csv` has `bill_id, question_id, question, answer`.

## Models and services

- Model: GPT-5 mini through the OpenAI API
- Local OCR: none
- Other services: none

## Known limits

- Bills with several meter rows (net metering, peak and off-peak) have no single clear reading, so the readings are set to null unless one row matches the billed units.
- The model gives slightly different results between runs. The two-read and adjudication step reduces this but does not remove it.
- Only tested on a handful of sample bills, so new layouts may need prompt changes.

## Data

The bill images from the challenge are not included in this repository.