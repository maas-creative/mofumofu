# Security Policy

## Reporting

Please report suspected security issues privately by opening a GitHub security advisory for this repository.

Do not include live credentials, private keys, access tokens, or sensitive customer data in public issues.

## Supported Versions

mofumofu is currently pre-1.0. Security fixes target the latest `main` branch until tagged release support is formalized.

## Security Expectations

- Do not commit `.env` files, provider credentials, API keys, OAuth tokens, private keys, or local `.mofumofu/` state.
- Run the repository security scan before release:

```sh
python3 -m mofu security scan --json
```

The project also preserves upstream MIT notices for vendored runtime code under `vendor/pi`.
