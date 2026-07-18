SHELL := /bin/bash
TOOLS := $(CURDIR)/.tools
QUARTO := $(TOOLS)/quarto/bin/quarto
TYPST := $(TOOLS)/typst/typst
UV := $(TOOLS)/uv/uv

.PHONY: bootstrap sync validate test lint web review book proof all preview clean

bootstrap:
	./scripts/bootstrap-tools.sh

sync: bootstrap
	$(UV) sync --group dev

validate: sync
	$(UV) run python platform/scripts/atlas.py build
	$(UV) run python platform/scripts/atlas.py build --check
	$(UV) run python platform/scripts/glossary.py build
	$(UV) run python platform/scripts/glossary.py build --check
	$(UV) run python platform/scripts/editorial.py lint

test: validate
	$(UV) run pytest

lint: sync
	$(UV) run ruff check platform courseware scripts

web: validate
	rm -rf "$(CURDIR)/_site"
	QUARTO_PYTHON="$(CURDIR)/.venv/bin/python" PATH="$(TOOLS)/typst:$$PATH" $(QUARTO) render --profile web
	rm -rf "$(CURDIR)/_site/_site" "$(CURDIR)/_site/_book" "$(CURDIR)/_site/_proof"
	$(UV) run python scripts/verify_outputs.py _site

review: validate
	rm -rf "$(CURDIR)/_review"
	QUARTO_PYTHON="$(CURDIR)/.venv/bin/python" PATH="$(TOOLS)/typst:$$PATH" $(QUARTO) render --profile web,review
	rm -rf "$(CURDIR)/_review/_site" "$(CURDIR)/_review/_book" "$(CURDIR)/_review/_proof" "$(CURDIR)/_review/_review"
	$(UV) run python scripts/verify_outputs.py _review

book: validate
	rm -rf "$(CURDIR)/_book"
	QUARTO_PYTHON="$(CURDIR)/.venv/bin/python" PATH="$(TOOLS)/typst:$$PATH" $(QUARTO) render --profile book
	rm -rf "$(CURDIR)/_book/_site" "$(CURDIR)/_book/_book" "$(CURDIR)/_book/_proof"
	@epub="$$(find _book -maxdepth 1 -name '*.epub' -print -quit)"; \
	  test -n "$$epub" -a -s "$$epub"; \
	  $(UV) run python scripts/package_epub_assets.py "$$epub"
	@epub="$$(find _book -maxdepth 1 -name '*.epub' -print -quit)"; \
	  pdf="$$(find _book -maxdepth 1 -name '*.pdf' -print -quit)"; \
	  test -n "$$epub" -a -s "$$epub"; \
	  test -n "$$pdf" -a -s "$$pdf"; \
	  $(UV) run python scripts/verify_outputs.py _book "$$epub" "$$pdf"

proof: validate
	rm -rf "$(CURDIR)/_proof"
	QUARTO_PYTHON="$(CURDIR)/.venv/bin/python" PATH="$(TOOLS)/typst:$$PATH" $(QUARTO) render --profile proof
	rm -rf "$(CURDIR)/_proof/_site" "$(CURDIR)/_proof/_book" "$(CURDIR)/_proof/_proof"
	@pdf="$$(find _proof -maxdepth 1 -name '*.pdf' -print -quit)"; \
	  test -n "$$pdf" -a -s "$$pdf"; \
	  $(UV) run python scripts/verify_outputs.py _proof "$$pdf"

all: test lint web book proof

preview: validate
	QUARTO_PYTHON="$(CURDIR)/.venv/bin/python" PATH="$(TOOLS)/typst:$$PATH" $(QUARTO) preview --profile web

clean:
	rm -rf _site _review _book _proof .quarto platform/generated courseware/labs/.jupyter_cache
