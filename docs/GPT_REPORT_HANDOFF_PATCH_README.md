# ICHIBAN INSIGHT — GPT Report Handoff Patch v1

This patch adds the next development step after the governance/Blueprint work: a clean handoff from the Module 4 valuation engine output to a GPT-generated ICHIBAN Insight report.

## Files included

```text
core/report_input_builder.py
core/gpt_prompt_builder.py
app/pages/5_Insight_Report.py
docs/GPT_REPORT_HANDOFF_PATCH_README.md
```

## What this patch does

1. Reads the Module 4 output from:

```text
data/valuation_engine_output.json
```

2. Reads the optional Module 4 input package from:

```text
data/valuation_input_package.json
```

3. Builds a structured GPT handoff file:

```text
data/report_input.json
```

4. Adds a new Streamlit page:

```text
Module 5 — ICHIBAN Insight Report
```

5. Lets the Realtor enter context that should affect the narrative but not change the math:

```text
Recommended range low/high
Recommended list posture / price
Pricing posture
Estimated days until market
Seller goal
Realtor property notes
Buyer Considerations notes
Report mode
```

6. Builds a GPT prompt preview before making an API call.

7. Generates a report only when `OPENAI_API_KEY` is set locally.

## Why this is safer

This keeps the workflow local and avoids direct GitHub website editing. You can copy these files into the repo, test locally, then commit when the app works.

## Install location

Copy the patch files into the matching repo folders:

```text
ICHIBAN-New-Day-V2/
  app/pages/5_Insight_Report.py
  core/report_input_builder.py
  core/gpt_prompt_builder.py
  docs/GPT_REPORT_HANDOFF_PATCH_README.md
```

## Recommended branch

From Git Bash inside the repo:

```bash
git checkout dev
git pull origin dev
git checkout -b feature/gpt-report-handoff-v1
```

Then copy the patch files into the repo.

## Run Streamlit

```bash
streamlit run app/main.py
```

Workflow:

1. Complete Module 2 subject verification.
2. Complete Module 3 market data intake.
3. Run Module 4 valuation engine.
4. Open Module 5 — ICHIBAN Insight Report.
5. Enter the recommended price range and Realtor notes.
6. Click **Build / Refresh Report Input**.
7. Review/download `report_input.json` and the GPT prompt preview.
8. If `OPENAI_API_KEY` is set, click **Generate GPT Insight Report**.

## Local API key setup

Windows CMD:

```cmd
setx OPENAI_API_KEY "your_api_key_here"
```

PowerShell:

```powershell
setx OPENAI_API_KEY "your_api_key_here"
```

Close and reopen the terminal after setting the key.

## Commit commands

```bash
git status
git add app/pages/5_Insight_Report.py core/report_input_builder.py core/gpt_prompt_builder.py docs/GPT_REPORT_HANDOFF_PATCH_README.md
git commit -m "Add GPT report handoff page"
git push -u origin feature/gpt-report-handoff-v1
```

## Important notes

- This patch does not change valuation math.
- It does not alter the existing governance JSON files.
- It does not expose private adjustment logic in the seller report.
- It uses the Boca-style concise seller-friendly report format as the default report mode.
- It keeps Buyer Considerations as marketability and planning context, not automatic dollar-for-dollar adjustment math.
