# Contributing

- Branch from `develop`; use `feature/<module>/<description>` or `codex/<task>`.
- Never commit `.env`, evidence uploads, rendered reports, or temporary output.
- Keep service APIs under `/api/v1`, use Pydantic response models, and add tests
  for authorization, failure behavior, and source provenance.
- Do not infer criminal relationships from co-occurrence alone. New links must
  include source evidence, confidence, and a plain-language explanation.
- Do not bypass the audit outbox for case/evidence mutations.
- Run frontend tests/build, all service tests, Ruff, dataset validation, and the
  isolated Docker workflow before opening a pull request. CI repeats these gates.
- Preserve unrelated teammate changes. Resolve conflicts in the owning module
  with its lead instead of replacing whole files.
