# Google Colab P0.0 smoke runbook

- [Open notebook through Colab](https://colab.research.google.com/github/ngluonghoa/swing-trading-1-8/blob/main/notebooks/p0_foundation_smoke.ipynb). Because the repository is Private, you may need to sign in through Colab's GitHub tab and enable **Include private repos** first.
- Open Colab's left sidebar **Secrets**. Add `GITHUB_READ_TOKEN` using a **fine-grained PAT** with Contents: Read-only access ONLY for `ngluonghoa/swing-trading-1-8`. Enable notebook access. Do not paste token into a code cell or print it.
- Run cells top to bottom. GitHub source is fetched by authenticated GitHub API and pinned to the resolved `main` commit SHA. No push occurs from the notebook.
- Test output is engineering-only: fixture and fail-closed checks. A PASS proves neither source correctness nor historical trading value. Every execution on a new Colab runtime reinstalls code; Colab VM is ephemeral.
- **Security:** Avoid mounting Drive unless a separately approved data task needs it. Never commit notebook outputs, raw data, secrets or tokens. Revoke the token if no longer needed. For production execution, do not depend on a user Colab runtime.

This notebook **has not been run in Google Colab from ChatGPT**; CI checks only the JSON format and unit tests in GitHub Actions.
