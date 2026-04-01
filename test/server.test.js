const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const {
  makeCode, shuffle, assignTasks, roomSnapshot, fullStateFor, checkWinCondition,
  TASK_STATIONS, SABOTAGE_STATIONS, MAP_W, MAP_H, COLORS,
} = require("../server");

// ── Helper: build a minimal room for testing ──────────────────────
function makeRoom(players = [], overrides = {}) {
  const room = {
    code: "TEST",
    host: players[0]?.id || "p1",
    maxPlayers: 8,
    phase: "playing",
    players: new Map(),
    completedTasks: 0,
    totalCrewTasks: 12,
    sabotagesDone: 0,
    activeSabotages: new Set(),
    votes: new Map(),
    meetingCaller: null,
    meetingTimer: null,
    chatLog: [],
    winner: null,
    tickInterval: null,
    ...overrides,
  };
  for (const p of players) {
    room.players.set(p.id, {
      id: p.id,
      name: p.name || p.id,
      color: COLORS[0],
      ready: true,
      alive: p.alive !== undefined ? p.alive : true,
      role: p.role || "crew",
      tasks: p.tasks || [],
      x: MAP_W / 2,
      y: MAP_H / 2,
      lastKillTime: 0,
      ...p,
    });
  }
  return room;
}

// ── makeCode ──────────────────────────────────────────────────────
describe("makeCode", () => {
  it("returns a 4-character uppercase string", () => {
    const code = makeCode();
    assert.equal(code.length, 4);
    assert.equal(code, code.toUpperCase());
  });

  it("generates different codes on successive calls", () => {
    const codes = new Set(Array.from({ length: 20 }, () => makeCode()));
    assert.ok(codes.size > 1, "Expected multiple unique codes");
  });
});

// ── assignTasks ───────────────────────────────────────────────────
describe("assignTasks", () => {
  it("returns 4 tasks for 4 or fewer players", () => {
    assert.equal(assignTasks(3), 4);
    assert.equal(assignTasks(4), 4);
  });

  it("returns 3 tasks for more than 4 players", () => {
    assert.equal(assignTasks(5), 3);
    assert.equal(assignTasks(8), 3);
  });
});

// ── shuffle ───────────────────────────────────────────────────────
describe("shuffle", () => {
  it("returns array with same elements", () => {
    const arr = [1, 2, 3, 4, 5];
    const result = shuffle([...arr]);
    assert.equal(result.length, arr.length);
    assert.deepEqual(result.sort(), arr.sort());
  });

  it("mutates and returns the same array", () => {
    const arr = [1, 2, 3];
    const result = shuffle(arr);
    assert.equal(result, arr);
  });
});

// ── roomSnapshot ──────────────────────────────────────────────────
describe("roomSnapshot", () => {
  it("returns correct shape", () => {
    const room = makeRoom([
      { id: "p1", name: "Alice", role: "crew" },
      { id: "p2", name: "Bob", role: "impostor" },
    ]);
    const snap = roomSnapshot(room);
    assert.equal(snap.code, "TEST");
    assert.equal(snap.host, "p1");
    assert.equal(snap.maxPlayers, 8);
    assert.equal(snap.phase, "playing");
    assert.equal(snap.players.length, 2);
  });

  it("does not leak role info in snapshot", () => {
    const room = makeRoom([{ id: "p1", role: "impostor" }]);
    const snap = roomSnapshot(room);
    assert.equal(snap.players[0].role, undefined);
  });
});

// ── fullStateFor ──────────────────────────────────────────────────
describe("fullStateFor", () => {
  it("includes role and tasks for the requested player", () => {
    const room = makeRoom([
      { id: "p1", role: "impostor", tasks: [] },
      { id: "p2", role: "crew", tasks: [{ stationId: "cable_1", type: "cable", done: false }] },
    ]);
    const state = fullStateFor(room, "p2");
    assert.equal(state.myRole, "crew");
    assert.equal(state.myTasks.length, 1);
    assert.ok(state.taskStations.length > 0);
    assert.deepEqual(state.sabotageStations, []);
  });

  it("includes sabotage stations for impostor", () => {
    const room = makeRoom([{ id: "p1", role: "impostor" }]);
    const state = fullStateFor(room, "p1");
    assert.equal(state.myRole, "impostor");
    assert.ok(state.sabotageStations.length > 0);
  });

  it("returns null for unknown player", () => {
    const room = makeRoom([{ id: "p1" }]);
    assert.equal(fullStateFor(room, "unknown"), null);
  });
});

// ── checkWinCondition ─────────────────────────────────────────────
describe("checkWinCondition", () => {
  it("impostor wins when impostors >= crew alive", () => {
    const room = makeRoom([
      { id: "p1", role: "impostor", alive: true },
      { id: "p2", role: "crew", alive: true },
    ]);
    const result = checkWinCondition(room);
    assert.equal(result, true);
    assert.equal(room.winner, "impostor");
    assert.equal(room.phase, "gameover");
  });

  it("impostor wins when all sabotages done", () => {
    const room = makeRoom([
      { id: "p1", role: "impostor", alive: true },
      { id: "p2", role: "crew", alive: true },
      { id: "p3", role: "crew", alive: true },
    ], { sabotagesDone: SABOTAGE_STATIONS.length });
    const result = checkWinCondition(room);
    assert.equal(result, true);
    assert.equal(room.winner, "impostor");
  });

  it("crew wins when all impostors dead", () => {
    const room = makeRoom([
      { id: "p1", role: "impostor", alive: false },
      { id: "p2", role: "crew", alive: true },
      { id: "p3", role: "crew", alive: true },
    ]);
    const result = checkWinCondition(room);
    assert.equal(result, true);
    assert.equal(room.winner, "crew");
  });

  it("crew wins when all tasks completed", () => {
    const room = makeRoom([
      { id: "p1", role: "impostor", alive: true },
      { id: "p2", role: "crew", alive: true },
      { id: "p3", role: "crew", alive: true },
      { id: "p4", role: "crew", alive: true },
    ], { completedTasks: 12, totalCrewTasks: 12 });
    const result = checkWinCondition(room);
    assert.equal(result, true);
    assert.equal(room.winner, "crew");
  });

  it("returns false when no win condition met", () => {
    const room = makeRoom([
      { id: "p1", role: "impostor", alive: true },
      { id: "p2", role: "crew", alive: true },
      { id: "p3", role: "crew", alive: true },
      { id: "p4", role: "crew", alive: true },
    ], { completedTasks: 5, totalCrewTasks: 12, sabotagesDone: 1 });
    const result = checkWinCondition(room);
    assert.equal(result, false);
    assert.equal(room.winner, null);
  });

  it("impostor wins even with 1 impostor vs 1 crew", () => {
    const room = makeRoom([
      { id: "p1", role: "impostor", alive: true },
      { id: "p2", role: "crew", alive: false },
      { id: "p3", role: "crew", alive: true },
    ]);
    const result = checkWinCondition(room);
    assert.equal(result, true);
    assert.equal(room.winner, "impostor");
  });
});
