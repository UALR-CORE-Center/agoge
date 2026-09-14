# Rubric generation failures

Agoge generates a rubric when an instructor opens **Manage Rubric** for a lab without one. Opening the lab page alone does not generate a rubric. The first rubric lookup can therefore return no document; a Firestore message saying that the rubric ID does not exist is expected until generation succeeds.

## No OpenAI API credits

An OpenAI error with `code: credit_balance_exhausted` means the account used by Agoge has no API credits remaining. It can arrive as HTTP 429 with `type: insufficient_quota`. This requires a billing or configuration change; repeating the same request will not restore access. Other `insufficient_quota` errors can indicate a spending or usage limit. See [OpenAI's error guidance](https://developers.openai.com/api/docs/guides/error-codes).

1. Check which OpenAI organization/project owns the key configured for this Agoge deployment.
2. Add credits in [OpenAI API billing](https://platform.openai.com/settings/organization/billing/), or resolve the applicable spending/usage limit.
3. If Agoge should use a different funded account, update the `openai_api_key` secret in the Google Cloud project configured in Agoge's environment. Rubric generation reads the latest version of this secret through `CloudEnv`; keep the key out of logs and issue reports.
4. Return to **Manage Rubric** and select **Retry**, or close and reopen the dialog.

Quota exhaustion returns an actionable HTTP 503 response in Agoge. Ordinary temporary rate limiting returns HTTP 429 with a message to wait and retry. Invalid API credentials return HTTP 503 with instructions to contact an administrator.

## What the application preserves

- Generation errors appear inside the rubric dialog, so the rest of the lab page remains usable.
- The app saves only a complete, validated rubric. A failed AI request does not create or overwrite its Firestore document.
- An existing rubric opens without an AI request. A missing rubric on an expired lab is not generated.
- Save failures preserve the instructor's edits in the open dialog.

The rubric document is stored in the deployment's `agoge-v1` database, under `rubric/<unit-id>`. Generation must succeed before that document appears.

## Deploying the fix

Deploy both the API and frontend after merging the rubric error handling change. Funding the OpenAI API account is a separate configuration step; deploying code does not add credits.

The regression tests use mocked services and require no live API key or cloud credentials:

```bash
PYTHONPATH=.:api python -m pytest api/unit_tests/test_rubric_generation.py -q
```

From `frontend`, run `npm ci` followed by `npm test` to check the rubric service and editor recovery flow.
