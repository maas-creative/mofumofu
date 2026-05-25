# mofumofu 0.1.0 Release Notes

Release date: 2026-05-24

## Summary

This release packages mofumofu as a provider-neutral coding-agent control plane that wraps the vendored pi coding-agent runtime while keeping mofumofu-owned spec, audit, validation, security, and gate workflows.

## Verification

- `python3 -m unittest discover -s tests -v`: PASS
- `npm --prefix vendor/pi run build --workspace @mofumofu/coding-agent`: PASS
- `MOFUMOFU_LOCAL_BASE_URL=http://localhost:1234/v1 python3 -m mofu provider e2e --local-model qwen/qwen3.6-27b --json`: local OpenAI-compatible provider E2E PASS
- `python3 -m mofu security scan --json`: PASS
- `python3 -m mofu wrapper status --json`: PASS
- `npm --prefix vendor/pi audit --omit=dev --json`: 0 production vulnerabilities

## Packaging

Release artifacts are built with:

```sh
python3 -m build
```

Expected artifacts:

- `dist/mofumofu-0.1.0.tar.gz`
- `dist/mofumofu-0.1.0-py3-none-any.whl`

The wheel includes the built coding-agent runtime under `mofu/agent_runtime`, so a user can run:

```sh
python -m pip install dist/mofumofu-0.1.0-py3-none-any.whl
mofu agent --help
```

Node.js 20+ must be installed on the machine because the embedded runtime executes with Node.

## Uninstall

```sh
python -m pip uninstall mofumofu
```

To remove local settings, sessions, and project state as well:

```sh
rm -rf ~/.config/mofumofu ~/.local/state/mofumofu ~/.mofumofu
```

## Clean Install Smoke Test

The Docker smoke test command is:

```sh
docker build -f docker/release-smoke.Dockerfile --build-arg WHEEL=dist/mofumofu-0.1.0-py3-none-any.whl .
```

If Docker is unavailable on the release machine, use a fresh virtual environment as a local fallback and record Docker as blocked by missing runtime.
