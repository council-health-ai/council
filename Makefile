.PHONY: help install lint test build dev-mcp dev-agents clean

help:
	@echo "Council — make targets"
	@echo "  install       Install all deps (pnpm + uv)"
	@echo "  lint          Lint TS + Python"
	@echo "  test          Run all tests"
	@echo "  build         Build TS packages"
	@echo "  dev-mcp       Run MCP server locally on :3001"
	@echo "  dev-agents    Run all 9 A2A agents locally"
	@echo "  clean         Remove build artifacts"

install:
	pnpm install
	uv sync

lint:
	pnpm lint
	uv run ruff check .

test:
	pnpm test
	uv run pytest

build:
	pnpm build

dev-mcp:
	cd packages/specialty-lens-mcp && pnpm dev

dev-agents:
	uv run honcho start

clean:
	rm -rf node_modules .turbo
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
