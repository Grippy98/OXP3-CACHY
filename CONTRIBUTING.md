# Contributing

Keep each fix independently understandable and reversible. Include a README and WRITEUP describing the trigger, supported hardware, implementation, installation, verification, rollback and upstream target. Distinguish an original hardware test from a new packaging change or an untested build.

Run the [development checks](docs/DEVELOPMENT.md). Add meaningful regression coverage for state/rollback changes. Keep root services and executables root-owned, use argument arrays instead of shell evaluation, and preserve unrelated user settings.

Commit source, patches, source pins, licenses and reusable tests. Do not commit hardware captures, validation dumps, logs, backups, private EDIDs, credentials, signing keys or compiled artifacts. Keep experimental display changes opt-in and preserve the stock recovery path.

Retain upstream licenses and attribution. Before proposing an upstream change, read that project's contribution policy. In particular, Limine's human DCO and AI-assistance requirements apply to a Limine submission; importing its unmodified source/patch here does not create an upstream submission or a human certification.
