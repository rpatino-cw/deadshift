"""DEADSHIFT — Data Hall Map Generator.

Reads a datahall layout from ~/.datahall/layouts.json and generates
3D geometry positions for racks, aisles, corridors, and game stations.
"""

import os
import json
import math

# ── Layout Loader ──────────────────────────────────────────────────
LAYOUT_PATHS = [
    os.path.expanduser("~/.datahall/layouts.json"),
    os.path.join(os.path.dirname(__file__), "dh_layouts.json"),
]


def load_layouts():
    for p in LAYOUT_PATHS:
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
    return {}


def get_layout(key=None):
    """Get a specific layout or the first available one."""
    layouts = load_layouts()
    if not layouts:
        return None, None
    if key and key in layouts:
        return key, layouts[key]
    # Return first layout
    k = next(iter(layouts))
    return k, layouts[k]


# ── 3D Map Generator ──────────────────────────────────────────────
# Dimensions (game units)
RACK_WIDTH = 30       # width of one rack (X axis)
RACK_DEPTH = 50       # depth of one rack (Z axis)
RACK_HEIGHT = 80      # height of a rack (Y axis)
ROW_GAP = 20          # gap between front-to-front racks in a row pair
AISLE_GAP = 60        # hot/cold aisle between row pairs
CORRIDOR_WIDTH = 120  # main corridor between left and right columns
WALL_HEIGHT = 100     # perimeter wall height
WALL_THICKNESS = 8


def generate_map(layout):
    """Convert a datahall layout to 3D positions and dimensions.

    Returns a dict with:
      - racks: list of {id, x, z, w, d, h, row, col_label, rack_num}
      - floor: {x, z, w, d} (floor plane)
      - walls: list of {x, y, z, sx, sy, sz}
      - corridor: {x, z, w, d} (main corridor area)
      - entrance: {x, z} (entrance position)
      - task_positions: list of {id, type, x, z, label, rack_num}
      - sabotage_positions: list of {id, type, x, z, label}
      - meeting_button: {x, z}
      - spawn_center: {x, z}
      - map_size: {w, h} (total map width and depth)
    """
    columns = layout["columns"]
    rpr = layout["racks_per_row"]
    serpentine = layout.get("serpentine", True)
    entrance = layout.get("entrance", "bottom-right")

    racks = []
    col_positions = []  # track x-offset for each column group

    # Calculate column widths
    x_offset = WALL_THICKNESS + 20  # left margin

    for col_idx, col in enumerate(columns):
        col_rpr = col.get("racks_per_row", rpr)
        col_width = col_rpr * RACK_WIDTH
        col_x_start = x_offset
        col_positions.append({"x_start": col_x_start, "width": col_width})

        # Generate rack positions
        for row in range(col["num_rows"]):
            # Z position: pairs of rows with aisle gaps
            pair = row // 2
            within_pair = row % 2
            z = WALL_THICKNESS + 20 + pair * (2 * RACK_DEPTH + ROW_GAP + AISLE_GAP)
            if within_pair == 1:
                z += RACK_DEPTH + ROW_GAP  # second row in pair faces opposite

            for pos in range(col_rpr):
                # Rack number (serpentine)
                if serpentine and row % 2 == 1:
                    rack_num = col["start"] + (row + 1) * col_rpr - 1 - pos
                else:
                    rack_num = col["start"] + row * col_rpr + pos

                rx = col_x_start + pos * RACK_WIDTH + RACK_WIDTH / 2
                rz = z + RACK_DEPTH / 2

                racks.append({
                    "id": f"R{rack_num}",
                    "rack_num": rack_num,
                    "x": rx, "z": rz,
                    "w": RACK_WIDTH - 4, "d": RACK_DEPTH - 4, "h": RACK_HEIGHT,
                    "row": row,
                    "col_idx": col_idx,
                    "col_label": col["label"],
                })

        x_offset += col_width + CORRIDOR_WIDTH

    # Total map size
    max_rows = max(c["num_rows"] for c in columns)
    num_pairs = (max_rows + 1) // 2
    map_depth = WALL_THICKNESS * 2 + 40 + num_pairs * (2 * RACK_DEPTH + ROW_GAP + AISLE_GAP)
    map_width = x_offset - CORRIDOR_WIDTH + WALL_THICKNESS + 20

    # Floor
    floor = {"x": map_width / 2, "z": map_depth / 2, "w": map_width, "d": map_depth}

    # Corridor center (between columns)
    if len(col_positions) >= 2:
        left_end = col_positions[0]["x_start"] + col_positions[0]["width"]
        right_start = col_positions[1]["x_start"]
        corridor_cx = (left_end + right_start) / 2
        corridor = {"x": corridor_cx, "z": map_depth / 2, "w": CORRIDOR_WIDTH, "d": map_depth}
    else:
        corridor_cx = map_width / 2
        corridor = {"x": corridor_cx, "z": map_depth / 2, "w": CORRIDOR_WIDTH, "d": map_depth}

    # Entrance position
    if "bottom-right" in entrance:
        entrance_pos = {"x": map_width - WALL_THICKNESS - 30, "z": map_depth - WALL_THICKNESS - 10}
    elif "bottom-left" in entrance:
        entrance_pos = {"x": WALL_THICKNESS + 30, "z": map_depth - WALL_THICKNESS - 10}
    elif "top-right" in entrance:
        entrance_pos = {"x": map_width - WALL_THICKNESS - 30, "z": WALL_THICKNESS + 10}
    else:
        entrance_pos = {"x": WALL_THICKNESS + 30, "z": WALL_THICKNESS + 10}

    # Spawn center (in the corridor near entrance)
    spawn = {"x": corridor_cx, "z": entrance_pos["z"] - 60}

    # Perimeter walls
    walls = [
        {"x": map_width / 2, "y": WALL_HEIGHT / 2, "z": 0,
         "sx": map_width, "sy": WALL_HEIGHT, "sz": WALL_THICKNESS},  # north
        {"x": map_width / 2, "y": WALL_HEIGHT / 2, "z": map_depth,
         "sx": map_width, "sy": WALL_HEIGHT, "sz": WALL_THICKNESS},  # south
        {"x": 0, "y": WALL_HEIGHT / 2, "z": map_depth / 2,
         "sx": WALL_THICKNESS, "sy": WALL_HEIGHT, "sz": map_depth},  # west
        {"x": map_width, "y": WALL_HEIGHT / 2, "z": map_depth / 2,
         "sx": WALL_THICKNESS, "sy": WALL_HEIGHT, "sz": map_depth},  # east
    ]

    # Place task stations at specific racks (spread across the hall)
    task_racks = _pick_task_racks(racks, columns, rpr)
    task_positions = []
    task_types = ["cable", "psu", "temp", "badge"]
    for i, rack in enumerate(task_racks):
        task_positions.append({
            "id": f"task_{i}",
            "type": task_types[i % len(task_types)],
            "x": rack["x"],
            "z": rack["z"],
            "label": f"{rack['id']} - {task_types[i % len(task_types)].upper()}",
            "rack_num": rack["rack_num"],
        })

    # Place sabotage stations at infrastructure points
    sabotage_positions = [
        {"id": "sab_1", "type": "overheat", "x": corridor_cx - 40, "z": map_depth * 0.3,
         "label": "Cooling Unit A"},
        {"id": "sab_2", "type": "cut_cable", "x": corridor_cx, "z": map_depth * 0.5,
         "label": "Fiber Trunk"},
        {"id": "sab_3", "type": "trip_power", "x": corridor_cx + 40, "z": map_depth * 0.7,
         "label": "Main Breaker"},
    ]

    # Meeting button at corridor center
    meeting_button = {"x": corridor_cx, "z": map_depth * 0.5}

    return {
        "racks": racks,
        "floor": floor,
        "walls": walls,
        "corridor": corridor,
        "entrance": entrance_pos,
        "task_positions": task_positions,
        "sabotage_positions": sabotage_positions,
        "meeting_button": meeting_button,
        "spawn_center": spawn,
        "map_size": {"w": map_width, "h": map_depth},
        "layout_name": None,  # set by caller
    }


def _pick_task_racks(racks, columns, rpr):
    """Pick 8 racks spread across the hall for task stations."""
    picked = []
    # Pick from each column: 4 per column, spread across rows
    for col_idx, col in enumerate(columns):
        col_racks = [r for r in racks if r["col_idx"] == col_idx]
        if not col_racks:
            continue
        step = max(1, len(col_racks) // 4)
        for i in range(0, len(col_racks), step):
            if len(picked) >= 8:
                break
            picked.append(col_racks[i])
    return picked[:8]


# ── Convenience ────────────────────────────────────────────────────
def generate_evi01_map():
    """Generate the EVI01 DH1 map specifically."""
    key, layout = get_layout("US-EVI01-test-2.DH1")
    if not layout:
        # Fallback: use hardcoded EVI01 layout
        layout = {
            "racks_per_row": 10,
            "columns": [
                {"label": "Left", "start": 1, "num_rows": 14},
                {"label": "Right", "start": 141, "num_rows": 18},
            ],
            "serpentine": True,
            "entrance": "bottom-right",
            "total_racks": 320,
        }
        key = "US-EVI01.DH1"

    result = generate_map(layout)
    result["layout_name"] = key
    return result
