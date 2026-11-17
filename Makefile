.PHONY: up test demo payment-test validate-log
up:            ; docker compose up
test:          ; python -m pytest -q tests
demo:          ; python -m app.cli run briefs/study-notes.json
payment-test:  ; python -m app.cli payment-test
validate-log:  ; python -m app.cli validate-log
