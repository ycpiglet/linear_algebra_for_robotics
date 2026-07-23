DEV := ./scripts/bootstrap-tools.sh

# Static publication contract mirror; execution lives in scripts/dev.py:
# verify_outputs.py _book "$$epub" "$$pdf"
# verify_outputs.py _proof "$$pdf"

.PHONY: bootstrap sync artifact-audit validate test lint workflow-lint web review book proof all preview clean

bootstrap:
	$(DEV) bootstrap

sync:
	$(DEV) sync

artifact-audit:
	$(DEV) artifact-audit

validate:
	$(DEV) validate

test:
	$(DEV) test

lint:
	$(DEV) lint

workflow-lint:
	$(DEV) workflow-lint

web:
	$(DEV) web

review:
	$(DEV) review

book:
	$(DEV) book

proof:
	$(DEV) proof

all:
	$(DEV) all

preview:
	$(DEV) preview

clean:
	$(DEV) clean
