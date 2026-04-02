.PHONY: play host admin dev test map models

play:
	@bash play.sh

host:
	@bash play.sh host

admin:
	@bash play.sh admin

models:
	@python3 generate_models.py

map:
	@python3 -c "from datahall_map import generate_evi01_map; import json; m = generate_evi01_map(); json.dump({'mapSize': m['map_size'], 'taskStations': [{'id': t['id'], 'type': t['type'], 'x': t['x'], 'y': t['z'], 'label': t['label']} for t in m['task_positions']], 'sabotageStations': [{'id': s['id'], 'type': s['type'], 'x': s['x'], 'y': s['z'], 'label': s['label']} for s in m['sabotage_positions']], 'meetingButton': {'x': m['meeting_button']['x'], 'y': m['meeting_button']['z'], 'radius': 40}, 'spawnCenter': {'x': m['spawn_center']['x'], 'y': m['spawn_center']['z']}}, open('map_data.json', 'w'), indent=2); print('Generated map_data.json from', m['layout_name'])"

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
