# Contributing

Thanks for taking a look at mofumofu.

## Development Setup

```sh
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
```

Node.js 20+ must be available on `PATH` when working on `mofu agent`.

## Pull Requests

- Keep changes focused and explain the user-facing behavior.
- Update tests when changing CLI behavior, schemas, gates, or security checks.
- Do not commit local `.mofumofu/` project state, secrets, generated wheels, or virtual environments.
- Preserve upstream notices for vendored code under `vendor/pi`.

Before submitting:

```sh
python3 -m unittest discover -s tests -v
python3 -m mofu security scan --json
```
