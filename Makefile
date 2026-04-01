.PHONY: play host admin dev test

play:
	@bash play.sh

host:
	@bash play.sh host

admin:
	@bash play.sh admin

test:
	@node --test test/*.test.js
	@python3 test/test_minimap.py

dev:
	@echo "Starting DEADSHIFT dev mode..."
	@lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
	@node server.js & SERVER_PID=$$!; \
	sleep 1; \
	echo "Server PID: $$SERVER_PID"; \
	trap "kill $$SERVER_PID 2>/dev/null" EXIT; \
	python3 game.py --admin --server localhost:3000; \
	kill $$SERVER_PID 2>/dev/null
