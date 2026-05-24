# mofumofu

mofumofu is a coding-agent project focused on long-horizon autonomy and specification-code consistency.

## Install

From a release artifact:

```sh
python -m pip install mofumofu-0.1.0-py3-none-any.whl
mofu --version
mofu agent --help
```

From this source tree:

```sh
python -m pip install .
mofu status --json
```

The wheel includes the built mofumofu coding-agent runtime. Node.js 20+ must be available on `PATH` for `mofu agent` because the embedded runtime executes with Node.

To uninstall:

```sh
python -m pip uninstall mofumofu
rm -rf ~/.config/mofumofu ~/.local/state/mofumofu ~/.mofumofu
```

The `rm -rf` line removes user and project state. Skip it when you want to keep sessions, settings, specs, and evidence.

## Release Verification

The release gate is the source of truth:

```sh
python -m unittest discover -s tests -v
python -m mofu gate status --spec product-release-baseline --json
python -m mofu security scan --spec product-release-baseline --json
```

For local model E2E with LM Studio:

```sh
MOFUMOFU_LOCAL_BASE_URL=http://172.17.30.209:1234/v1 \
  python -m mofu provider e2e --local-model qwen/qwen3.6-27b --json
```

Canonical implementation specs:

- [Specification Index](docs/spec-index.md)
- [Product Philosophy](docs/product-philosophy.md)
- [Requirements](docs/requirements.md)
- [Data Schemas](docs/data-schemas.md)
- [CLI Reference](docs/cli-reference.md)
- [Tool Contracts](docs/tool-contracts.md)
- [Implementation Plan](docs/implementation-plan.md)
- [Security Requirements](docs/security-requirements.md)
- [Architecture Principles](docs/architecture-principles.md)

Reference research and design notes:

- [Implementation Research](docs/implementation-research.md)
- [Technology Candidates](docs/technology-candidates.md)
- [Research Basis](docs/research-basis.md)
- [Fork Methodology](docs/pi-customization-methodology.md)
- [Coding-Agent Pain Points](docs/competitor-pain-points.md)
- [Implementation Readiness Research](docs/implementation-readiness-research.md)
