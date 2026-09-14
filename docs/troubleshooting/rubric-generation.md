# Optional rubric support

Labs do not use AI rubric generation by default. A specification with no rubric setting needs no OpenAI API key or credits for rubric functionality. Opening a lab, opening **Manage Rubric**, or retrying a rubric lookup never generates a rubric.

Previously, storing an OpenAI key enabled the deployment-wide `rubric_support` flag, which exposed rubric tools even for specifications without rubric configuration. The editor then automatically generated a missing rubric. The deployment flag is no longer used to enable rubrics for a lab, and storing a key no longer sets it.

## Explicitly enabling rubric tools

To enable rubric tools, add the boolean field `"rubric_support": true` at the top level of the lab specification. Omitting the field or setting it to `false` keeps the tools disabled. Strings such as `"true"` are not accepted.

This setting is copied from the saved specification when a unit is built. Existing units without the setting remain disabled, even if the old deployment flag is still true. Updating a catalog specification does not change units that were already built; an existing unit must also be explicitly opted in through its own `rubric_support` field.

For an enabled lab, **Manage Rubric** only loads an existing rubric. If none exists, an instructor can select **Generate with AI** after seeing that it uses OpenAI API credits. This is the only action in the editor that requests generation; reopening the dialog and retrying a lookup do not.

The generation API checks both the saved unit's boolean `rubric_support` field and an explicit boolean `confirm_ai_generation` in the request before constructing the AI generator or reading its credentials. A request without confirmation returns HTTP 400; a confirmed request for a disabled lab returns HTTP 403. Old clients that automatically post generation requests cannot consume credits.

## Errors after choosing AI generation

Only intentionally requested AI generation requires an OpenAI account. An error with `code: credit_balance_exhausted` means that account has no API credits remaining. It can arrive as HTTP 429 with `type: insufficient_quota`. Other `insufficient_quota` errors can indicate a spending or usage limit. See [OpenAI's error guidance](https://developers.openai.com/api/docs/guides/error-codes).

1. Check which OpenAI organization/project owns the key configured for this Agoge deployment.
2. Add credits in [OpenAI API billing](https://platform.openai.com/settings/organization/billing/), or resolve the applicable spending/usage limit.
3. If Agoge should use a different funded account, update the `openai_api_key` secret in the Google Cloud project configured in Agoge's environment. Rubric generation reads the latest version of this secret through `CloudEnv`; keep the key out of logs and issue reports.
4. If AI generation is still wanted, return to **Manage Rubric** and select **Generate with AI**. Closing and reopening the dialog does not retry generation.

Quota exhaustion returns an actionable HTTP 503 response in Agoge. Ordinary temporary rate limiting returns HTTP 429 with a message to wait and retry. Invalid API credentials return HTTP 503 with instructions to contact an administrator.

## What the application preserves

- Generation errors appear inside the rubric dialog, so the rest of the lab page remains usable.
- The app saves only a complete, validated rubric. A failed AI request does not create or overwrite its Firestore document.
- An existing rubric opens without an AI request. A missing rubric on an expired lab is not generated.
- Save failures preserve the instructor's edits in the open dialog.

The rubric document is stored in the deployment's `agoge-v1` database, under `rubric/<unit-id>`. No document is expected for a lab that does not use a rubric. A missing rubric lookup returns `data: null`; it does not trigger AI generation.

## Deploying the fix

Deploy both the API and frontend after merging the change, then reload any open lab pages. Deploying the API first also blocks automatic generation requests from older frontends. Existing labs with no rubric setting require no specification changes, database migration, or OpenAI billing changes.

The regression tests use mocked services and require no live API key or cloud credentials:

```bash
PYTHONPATH=.:api python -m pytest api/unit_tests/test_rubric_generation.py api/unit_tests/test_rubric_opt_in.py -q
```

From `frontend`, run `npm ci` followed by `npm test` to check the per-lab opt-in, explicit generation action, and editor recovery flow.
