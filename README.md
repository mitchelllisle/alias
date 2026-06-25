# alias

Pseudonymisation service for Australian financial context.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Docker (for `make docker-*` targets and CI)

## Quickstart

```bash
make install
make serve
```

## Development

```bash
make test    # run tests
make lint    # ruff + mypy
```
