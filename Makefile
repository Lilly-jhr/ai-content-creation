PY := uv run python -m pipeline
ACESTEP_DIR := vendor/ACE-Step-1.5

.PHONY: site help setup film dry-run radio validate schema check smoke clips clips-status clips-fetch music music-setup assemble rough costs audit

help:            ## list targets
	@grep -E '^[a-z-]+:.*## ' Makefile | sed 's/:.*## /\t/'

setup:           ## install the (light) pipeline environment
	uv sync --extra kaggle

film: setup      ## THE one command: full pipeline, reusing every cached asset
	$(PY) film

dry-run:         ## explain what `make film` would generate vs reuse, and why
	$(PY) --dry-run film

radio:           ## radio cut: narration + temp music on black + subtitles
	$(PY) radio

rough:           ## rough cut with unapproved drafts (placeholders where nothing exists yet)
	$(PY) --allow-draft assemble

assemble:        ## re-render the edit from cached assets
	$(PY) assemble

validate:        ## validate storyboard.json against the contract
	$(PY) validate

schema:          ## regenerate schema/storyboard.schema.json from the models
	$(PY) schema

check:           ## lint + tests
	uv run ruff check pipeline tests
	uv run pytest -q

smoke:           ## one tiny call per provider, logged to runs.jsonl
	$(PY) smoke

clips:           ## submit pending Wan 2.2 jobs to Kaggle (async)
	$(PY) video-submit

clips-status:
	$(PY) video-status

clips-fetch:     ## download finished clips and register them in the cache
	$(PY) video-fetch

music-setup:     ## install ACE-Step 1.5 in its own environment (large download)
	test -d $(ACESTEP_DIR) || git clone --depth 1 https://github.com/ace-step/ACE-Step-1.5 $(ACESTEP_DIR)
	cd $(ACESTEP_DIR) && UV_HTTP_TIMEOUT=600 uv sync

music:           ## generate score candidates (local GPU)
	$(PY) music

site:            ## build the showcase site (site/) from storyboard, timeline and runs.jsonl
	$(PY) site

costs:           ## per-stage latency / GPU minutes / list-price table from runs.jsonl
	$(PY) costs

audit:           ## every asset has a sidecar and a runs.jsonl line
	$(PY) audit
