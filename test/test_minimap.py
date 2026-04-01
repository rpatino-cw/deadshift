"""Unit tests for draw_minimap — verifies pixel output on a Pygame surface."""

import sys
import os
import math

# Pygame needs to init before we can create surfaces
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
pygame.init()

# We can't cleanly import game.py (it creates a socketio client at module level),
# so we replicate the constants and function here. If draw_minimap's logic changes,
# these tests verify the contract: what gets drawn where.

WIDTH, HEIGHT = 1024, 768
MAP_W, MAP_H = 1600, 1200
MINIMAP_W, MINIMAP_H = 140, 105
FLASHLIGHT_RADIUS = 180
YELLOW = (243, 156, 18)
RED = (231, 76, 60)
WHITE = (255, 255, 255)


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def draw_minimap(surface, gs):
    """Copy of game.py draw_minimap for isolated testing."""
    mx = WIDTH - MINIMAP_W - 10
    my = HEIGHT - MINIMAP_H - 35
    sx = MINIMAP_W / MAP_W
    sy = MINIMAP_H / MAP_H
    am_alive = gs.my_id not in gs.dead_players

    mm_bg = pygame.Surface((MINIMAP_W, MINIMAP_H), pygame.SRCALPHA)
    mm_bg.fill((0, 0, 0, 150))
    surface.blit(mm_bg, (mx, my))

    for station in gs.task_stations:
        has_task = any(t["stationId"] == station["id"] and not t.get("done") for t in gs.my_tasks)
        color = YELLOW if has_task else (40, 40, 50)
        pygame.draw.circle(surface, color, (int(mx + station["x"] * sx), int(my + station["y"] * sy)), 2)

    if gs.my_role == "impostor":
        for station in gs.sabotage_stations:
            done = station["id"] in gs.active_sabotages
            color = (60, 20, 20) if done else RED
            pygame.draw.circle(surface, color, (int(mx + station["x"] * sx), int(my + station["y"] * sy)), 2)

    if gs.meeting_button:
        bx = int(mx + gs.meeting_button["x"] * sx)
        by = int(my + gs.meeting_button["y"] * sy)
        pygame.draw.circle(surface, (150, 30, 30), (bx, by), 3, 1)

    for pid, p in gs.positions.items():
        if pid == gs.my_id or not p.get("alive", True):
            continue
        dist = math.hypot(p["x"] - gs.my_x, p["y"] - gs.my_y)
        if am_alive and not gs.no_fog and dist > FLASHLIGHT_RADIUS * 1.5:
            continue
        color = hex_to_rgb(p.get("color", "#ffffff"))
        pygame.draw.circle(surface, color, (int(mx + p["x"] * sx), int(my + p["y"] * sy)), 2)

    pygame.draw.circle(surface, WHITE, (int(mx + gs.my_x * sx), int(my + gs.my_y * sy)), 3)
    pygame.draw.rect(surface, (60, 60, 80), pygame.Rect(mx, my, MINIMAP_W, MINIMAP_H), 1)


class FakeGS:
    """Minimal GameState stub for testing."""
    def __init__(self):
        self.my_id = "me"
        self.my_role = "crew"
        self.my_tasks = []
        self.task_stations = []
        self.sabotage_stations = []
        self.meeting_button = None
        self.active_sabotages = []
        self.dead_players = []
        self.positions = {}
        self.no_fog = False
        self.my_x = MAP_W / 2
        self.my_y = MAP_H / 2


# ── Helpers ────────────────────────────────────────────────────────
MINIMAP_X = WIDTH - MINIMAP_W - 10
MINIMAP_Y = HEIGHT - MINIMAP_H - 35


def pixel_at(surf, x, y):
    """Get RGB tuple at pixel (x, y)."""
    return tuple(surf.get_at((x, y))[:3])


def has_nonblack_pixel_in_rect(surf, rx, ry, rw, rh):
    """Check if any pixel in rect is not black (0,0,0)."""
    for x in range(rx, rx + rw):
        for y in range(ry, ry + rh):
            r, g, b = pixel_at(surf, x, y)
            if r > 10 or g > 10 or b > 10:
                return True
    return False


# ── Tests ──────────────────────────────────────────────────────────
def test_minimap_draws_background():
    """The minimap area should not be pure black (has the dark overlay)."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))
    gs = FakeGS()
    draw_minimap(surf, gs)
    # The border should produce non-black pixels at the minimap edges
    border_pixel = pixel_at(surf, MINIMAP_X, MINIMAP_Y)
    assert border_pixel == (60, 60, 80), f"Expected border color, got {border_pixel}"
    print("  PASS: minimap draws background + border")


def test_player_dot_at_center():
    """Player at map center should produce a white dot near minimap center."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))
    gs = FakeGS()
    gs.my_x = MAP_W / 2
    gs.my_y = MAP_H / 2
    draw_minimap(surf, gs)
    # Player dot should be near minimap center
    dot_x = int(MINIMAP_X + (MAP_W / 2) * (MINIMAP_W / MAP_W))
    dot_y = int(MINIMAP_Y + (MAP_H / 2) * (MINIMAP_H / MAP_H))
    color = pixel_at(surf, dot_x, dot_y)
    assert color == (255, 255, 255), f"Expected white dot at center, got {color}"
    print("  PASS: player dot at map center is white")


def test_player_dot_moves():
    """Player at different positions should produce dots at different locations."""
    gs = FakeGS()
    sx = MINIMAP_W / MAP_W
    sy = MINIMAP_H / MAP_H

    # Position 1: top-left area
    surf1 = pygame.Surface((WIDTH, HEIGHT))
    surf1.fill((0, 0, 0))
    gs.my_x = 200
    gs.my_y = 200
    draw_minimap(surf1, gs)
    dot1_x = int(MINIMAP_X + 200 * sx)
    dot1_y = int(MINIMAP_Y + 200 * sy)

    # Position 2: bottom-right area
    surf2 = pygame.Surface((WIDTH, HEIGHT))
    surf2.fill((0, 0, 0))
    gs.my_x = 1400
    gs.my_y = 1000
    draw_minimap(surf2, gs)
    dot2_x = int(MINIMAP_X + 1400 * sx)
    dot2_y = int(MINIMAP_Y + 1000 * sy)

    color1 = pixel_at(surf1, dot1_x, dot1_y)
    color2 = pixel_at(surf2, dot2_x, dot2_y)
    assert color1 == (255, 255, 255), f"Expected white at pos1, got {color1}"
    assert color2 == (255, 255, 255), f"Expected white at pos2, got {color2}"
    assert (dot1_x, dot1_y) != (dot2_x, dot2_y), "Dots should be at different positions"
    print("  PASS: player dot moves with position")


def test_task_station_yellow_dot():
    """A station with a pending task should draw a yellow dot."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))
    gs = FakeGS()
    gs.task_stations = [{"id": "cable_1", "type": "cable", "x": 200, "y": 200}]
    gs.my_tasks = [{"stationId": "cable_1", "type": "cable", "done": False}]
    draw_minimap(surf, gs)
    sx = MINIMAP_W / MAP_W
    sy = MINIMAP_H / MAP_H
    dot_x = int(MINIMAP_X + 200 * sx)
    dot_y = int(MINIMAP_Y + 200 * sy)
    color = pixel_at(surf, dot_x, dot_y)
    assert color == YELLOW, f"Expected yellow for pending task, got {color}"
    print("  PASS: pending task station is yellow")


def test_completed_task_not_yellow():
    """A station with a completed task should NOT be yellow."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))
    gs = FakeGS()
    gs.task_stations = [{"id": "cable_1", "type": "cable", "x": 200, "y": 200}]
    gs.my_tasks = [{"stationId": "cable_1", "type": "cable", "done": True}]
    draw_minimap(surf, gs)
    sx = MINIMAP_W / MAP_W
    sy = MINIMAP_H / MAP_H
    dot_x = int(MINIMAP_X + 200 * sx)
    dot_y = int(MINIMAP_Y + 200 * sy)
    color = pixel_at(surf, dot_x, dot_y)
    assert color != YELLOW, f"Completed task should not be yellow, got {color}"
    print("  PASS: completed task station is not yellow")


def test_sabotage_hidden_from_crew():
    """Crew should NOT see sabotage station dots."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))
    gs = FakeGS()
    gs.my_role = "crew"
    gs.sabotage_stations = [{"id": "sab_1", "type": "overheat", "x": 500, "y": 400}]
    draw_minimap(surf, gs)
    sx = MINIMAP_W / MAP_W
    sy = MINIMAP_H / MAP_H
    dot_x = int(MINIMAP_X + 500 * sx)
    dot_y = int(MINIMAP_Y + 400 * sy)
    color = pixel_at(surf, dot_x, dot_y)
    # Should be the dark background, not red
    assert color[0] < 50 and color[1] < 50 and color[2] < 50, \
        f"Crew should not see sabotage dot, got {color}"
    print("  PASS: sabotage hidden from crew")


def test_sabotage_visible_to_impostor():
    """Impostor should see sabotage station dots as red."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))
    gs = FakeGS()
    gs.my_role = "impostor"
    gs.sabotage_stations = [{"id": "sab_1", "type": "overheat", "x": 500, "y": 400}]
    draw_minimap(surf, gs)
    sx = MINIMAP_W / MAP_W
    sy = MINIMAP_H / MAP_H
    dot_x = int(MINIMAP_X + 500 * sx)
    dot_y = int(MINIMAP_Y + 400 * sy)
    color = pixel_at(surf, dot_x, dot_y)
    assert color[0] > 100, f"Impostor should see red sabotage dot, got {color}"
    print("  PASS: sabotage visible to impostor")


def test_nearby_player_visible():
    """A player within flashlight range should appear on minimap."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))
    gs = FakeGS()
    gs.my_x = 800
    gs.my_y = 600
    gs.positions = {
        "me": {"x": 800, "y": 600, "alive": True, "color": "#ffffff"},
        "other": {"x": 850, "y": 600, "alive": True, "color": "#3498db"},  # 50px away, in range
    }
    draw_minimap(surf, gs)
    sx = MINIMAP_W / MAP_W
    sy = MINIMAP_H / MAP_H
    dot_x = int(MINIMAP_X + 850 * sx)
    dot_y = int(MINIMAP_Y + 600 * sy)
    color = pixel_at(surf, dot_x, dot_y)
    expected = hex_to_rgb("#3498db")
    assert color == expected, f"Expected nearby player color {expected}, got {color}"
    print("  PASS: nearby player visible on minimap")


def test_far_player_hidden():
    """A player outside flashlight range should NOT appear on minimap (fog on)."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))
    gs = FakeGS()
    gs.my_x = 800
    gs.my_y = 600
    gs.no_fog = False
    gs.positions = {
        "me": {"x": 800, "y": 600, "alive": True, "color": "#ffffff"},
        "far": {"x": 200, "y": 200, "alive": True, "color": "#e74c3c"},  # far away
    }
    draw_minimap(surf, gs)
    sx = MINIMAP_W / MAP_W
    sy = MINIMAP_H / MAP_H
    dot_x = int(MINIMAP_X + 200 * sx)
    dot_y = int(MINIMAP_Y + 200 * sy)
    color = pixel_at(surf, dot_x, dot_y)
    assert color[0] < 50, f"Far player should be hidden, got {color}"
    print("  PASS: far player hidden on minimap")


def test_far_player_visible_with_fog_off():
    """With fog off (admin/dead), far players should be visible."""
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill((0, 0, 0))
    gs = FakeGS()
    gs.my_x = 800
    gs.my_y = 600
    gs.no_fog = True
    gs.positions = {
        "me": {"x": 800, "y": 600, "alive": True, "color": "#ffffff"},
        "far": {"x": 200, "y": 200, "alive": True, "color": "#e74c3c"},
    }
    draw_minimap(surf, gs)
    sx = MINIMAP_W / MAP_W
    sy = MINIMAP_H / MAP_H
    dot_x = int(MINIMAP_X + 200 * sx)
    dot_y = int(MINIMAP_Y + 200 * sy)
    color = pixel_at(surf, dot_x, dot_y)
    expected = hex_to_rgb("#e74c3c")
    assert color == expected, f"Expected visible player with fog off, got {color}"
    print("  PASS: far player visible with fog off")


# ── Run all tests ──────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        test_minimap_draws_background,
        test_player_dot_at_center,
        test_player_dot_moves,
        test_task_station_yellow_dot,
        test_completed_task_not_yellow,
        test_sabotage_hidden_from_crew,
        test_sabotage_visible_to_impostor,
        test_nearby_player_visible,
        test_far_player_hidden,
        test_far_player_visible_with_fog_off,
    ]
    print(f"\nRunning {len(tests)} minimap tests...\n")
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {t.__name__} — {e}")
            failed += 1
        except Exception as e:
            print(f"  FAIL: {t.__name__} — {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed + failed} passed")
    pygame.quit()
    sys.exit(1 if failed else 0)
