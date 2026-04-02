"""DEADSHIFT — 3D Renderer using PyOpenGL.

Replaces the 2D draw_game() with a full 3D scene.
All UI screens (menu, lobby, meeting, voting, gameover) stay 2D
via the blit_surface_to_screen() path.
"""

import math
import time
import os
import pygame
from OpenGL.GL import *
from OpenGL.GLU import *

try:
    import pywavefront
    HAS_PYWAVEFRONT = True
except ImportError:
    HAS_PYWAVEFRONT = False

try:
    from datahall_map import generate_evi01_map
    DATAHALL_MAP = generate_evi01_map()
except Exception:
    DATAHALL_MAP = None

MODELS_DIR = os.path.join(os.path.dirname(__file__), "assets", "models")

# ── Constants ──────────────────────────────────────────────────────────
CAM_ANGLE = 55       # degrees from horizontal
CAM_DISTANCE = 400   # closer for datahall scale
CAM_FOV = 60         # field of view
FLASHLIGHT_RADIUS = 400  # large radius for better visibility
PLAYER_RADIUS = 10   # slightly smaller for datahall scale
INTERACT_RADIUS = 80
CHAR_HEIGHT = 30     # humanoid character height
CHAR_BODY_R = 6      # body radius
CHAR_HEAD_R = 5      # head radius

# Colors (normalized 0-1)
C_FLOOR = (0.04, 0.04, 0.06)
C_GRID = (0.08, 0.08, 0.12)
C_BORDER = (0.16, 0.16, 0.24)
C_YELLOW = (0.95, 0.61, 0.07)
C_DARK_STATION = (0.16, 0.16, 0.20)
C_RED = (0.91, 0.30, 0.24)
C_DARK_RED = (0.39, 0.08, 0.08)
C_SAB_DONE = (0.16, 0.16, 0.16)
C_MEETING_BTN = (0.59, 0.12, 0.12)
C_WHITE = (1.0, 1.0, 1.0)
C_GREEN = (0.18, 0.80, 0.44)
C_AMBER = (1.0, 0.75, 0.0)
C_DIM = (0.47, 0.47, 0.47)

# Pygame colors for HUD
HUD_RED = (231, 76, 60)
HUD_GREEN = (46, 204, 113)
HUD_WHITE = (255, 255, 255)
HUD_AMBER = (255, 191, 0)
HUD_DIM = (120, 120, 120)
HUD_GRAY = (60, 60, 60)
HUD_DARK = (30, 30, 30)


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def hex_to_gl(h):
    r, g, b = hex_to_rgb(h)
    return (r / 255, g / 255, b / 255)


# ── Primitive Builders ─────────────────────────────────────────────────
def _draw_cube_geometry():
    """Draw a unit cube centered at origin (side length 1)."""
    v = [
        (-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
        (-0.5, -0.5,  0.5), (0.5, -0.5,  0.5), (0.5, 0.5,  0.5), (-0.5, 0.5,  0.5),
    ]
    faces = [
        (0, 1, 2, 3, (0, 0, -1)),  # front
        (5, 4, 7, 6, (0, 0, 1)),   # back
        (4, 0, 3, 7, (-1, 0, 0)),  # left
        (1, 5, 6, 2, (1, 0, 0)),   # right
        (3, 2, 6, 7, (0, 1, 0)),   # top
        (4, 5, 1, 0, (0, -1, 0)),  # bottom
    ]
    glBegin(GL_QUADS)
    for i0, i1, i2, i3, n in faces:
        glNormal3f(*n)
        glVertex3f(*v[i0])
        glVertex3f(*v[i1])
        glVertex3f(*v[i2])
        glVertex3f(*v[i3])
    glEnd()


def _draw_sphere_geometry(slices=12, stacks=8):
    """Draw a unit sphere centered at origin (radius 1)."""
    for i in range(stacks):
        lat0 = math.pi * (-0.5 + i / stacks)
        lat1 = math.pi * (-0.5 + (i + 1) / stacks)
        glBegin(GL_QUAD_STRIP)
        for j in range(slices + 1):
            lng = 2 * math.pi * j / slices
            for lat in (lat1, lat0):
                x = math.cos(lat) * math.cos(lng)
                y = math.sin(lat)
                z = math.cos(lat) * math.sin(lng)
                glNormal3f(x, y, z)
                glVertex3f(x, y, z)
        glEnd()


def _draw_cylinder_geometry(slices=10, height=1.0, radius=1.0):
    """Draw a cylinder from y=0 to y=height, radius 1, centered at origin XZ."""
    # Side faces
    glBegin(GL_QUAD_STRIP)
    for i in range(slices + 1):
        angle = 2 * math.pi * i / slices
        x = radius * math.cos(angle)
        z = radius * math.sin(angle)
        glNormal3f(math.cos(angle), 0, math.sin(angle))
        glVertex3f(x, height, z)
        glVertex3f(x, 0, z)
    glEnd()
    # Top cap
    glBegin(GL_TRIANGLE_FAN)
    glNormal3f(0, 1, 0)
    glVertex3f(0, height, 0)
    for i in range(slices + 1):
        angle = 2 * math.pi * i / slices
        glVertex3f(radius * math.cos(angle), height, radius * math.sin(angle))
    glEnd()


def build_display_lists():
    """Compile unit primitives once. Returns dict of display list IDs."""
    lists = {}

    lists["cube"] = glGenLists(1)
    glNewList(lists["cube"], GL_COMPILE)
    _draw_cube_geometry()
    glEndList()

    lists["sphere"] = glGenLists(1)
    glNewList(lists["sphere"], GL_COMPILE)
    _draw_sphere_geometry(12, 8)
    glEndList()

    lists["quad"] = glGenLists(1)
    glNewList(lists["quad"], GL_COMPILE)
    glBegin(GL_QUADS)
    glNormal3f(0, 1, 0)
    glVertex3f(-0.5, 0, -0.5)
    glVertex3f(0.5, 0, -0.5)
    glVertex3f(0.5, 0, 0.5)
    glVertex3f(-0.5, 0, 0.5)
    glEnd()
    glEndList()

    # Humanoid character: cylinder body + sphere head
    lists["character"] = glGenLists(1)
    glNewList(lists["character"], GL_COMPILE)
    # Body (cylinder from y=0 to y=CHAR_HEIGHT-CHAR_HEAD_R*2)
    _draw_cylinder_geometry(8, CHAR_HEIGHT - CHAR_HEAD_R * 2, CHAR_BODY_R)
    # Head (sphere on top)
    glPushMatrix()
    glTranslatef(0, CHAR_HEIGHT - CHAR_HEAD_R, 0)
    _draw_sphere_geometry(8, 6)
    glPopMatrix()
    glEndList()

    # Server rack: tall thin box with front detail
    lists["rack"] = glGenLists(1)
    glNewList(lists["rack"], GL_COMPILE)
    _draw_cube_geometry()
    glEndList()

    return lists


# ── OBJ Model Loader ──────────────────────────────────────────────
def load_obj_as_display_list(filepath):
    """Load an OBJ file with normals and compile into a GL display list."""
    if not os.path.exists(filepath):
        return None

    # Parse OBJ manually for proper v//vn face format
    verts = []
    normals = []
    faces = []

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line.startswith("v "):
                parts = line.split()
                verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif line.startswith("vn "):
                parts = line.split()
                normals.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif line.startswith("f "):
                parts = line.split()[1:]
                face_verts = []
                for p in parts:
                    if "//" in p:
                        vi, ni = p.split("//")
                        face_verts.append((int(vi) - 1, int(ni) - 1))
                    elif "/" in p:
                        segs = p.split("/")
                        vi = int(segs[0]) - 1
                        ni = int(segs[-1]) - 1 if len(segs) >= 3 and segs[2] else -1
                        face_verts.append((vi, ni))
                    else:
                        face_verts.append((int(p) - 1, -1))
                faces.append(face_verts)

    dl = glGenLists(1)
    glNewList(dl, GL_COMPILE)
    glBegin(GL_TRIANGLES)
    for face in faces:
        for vi, ni in face:
            if 0 <= ni < len(normals):
                glNormal3f(*normals[ni])
            else:
                glNormal3f(0, 1, 0)
            if 0 <= vi < len(verts):
                glVertex3f(*verts[vi])
    glEnd()
    glEndList()
    return dl


# Scale factors: Kenney models are ~1 unit tall, our game uses much larger units
# Generated models are pre-scaled to game units (no scaling needed)
MODEL_SCALES = {
    "kenney_crewmate.obj": 38,      # 0.79 * 38 = ~30 (CHAR_HEIGHT)
    "kenney_rack.obj": 133,          # 0.60 * 133 = ~80 (rack height)
    "kenney_meeting_btn.obj": 40,    # 0.64 * 40 = ~25
    "kenney_sab_terminal.obj": 30,   # 0.80 * 30 = ~24
    # Generated models: already at game scale
    "crewmate.obj": 1,
    "rack.obj": 1,
    "meeting_btn.obj": 1,
    "sab_terminal.obj": 1,
}


def load_models():
    """Load all OBJ models. Prefers Kenney CC0 models, falls back to generated."""
    models = {}
    scales = {}
    model_map = {
        "crewmate": ["kenney_crewmate.obj", "crewmate.obj"],
        "rack": ["kenney_rack.obj", "rack.obj"],
        "meeting_btn": ["kenney_meeting_btn.obj", "meeting_btn.obj"],
        "sab_terminal": ["kenney_sab_terminal.obj", "sab_terminal.obj"],
    }
    for name, candidates in model_map.items():
        for filename in candidates:
            path = os.path.join(MODELS_DIR, filename)
            dl = load_obj_as_display_list(path)
            if dl:
                models[name] = dl
                scales[name] = MODEL_SCALES.get(filename, 1)
                break
        else:
            models[name] = None
            scales[name] = 1
    return models, scales


# ── Fog Texture ────────────────────────────────────────────────────────
def build_fog_texture(radius, edge_width, width, height):
    """Build a screen-sized RGBA texture with a transparent circle in the center."""
    fog_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    fog_surf.fill((0, 0, 0, 120))  # lighter fog for more visibility
    cx, cy = width // 2, height // 2
    pygame.draw.circle(fog_surf, (0, 0, 0, 0), (cx, cy), radius)
    for r in range(radius, radius + edge_width):
        alpha = int(120 * (r - radius) / edge_width)
        pygame.draw.circle(fog_surf, (0, 0, 0, alpha), (cx, cy), r, 1)
    return _upload_surface(fog_surf)


def _upload_surface(surface):
    """Upload a Pygame surface as an OpenGL texture. Returns texture ID."""
    tex_data = pygame.image.tostring(surface, "RGBA", True)
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, surface.get_width(),
                 surface.get_height(), 0, GL_RGBA, GL_UNSIGNED_BYTE, tex_data)
    return tex_id


# ── 2D/3D Mode Switching ──────────────────────────────────────────────
def begin_2d_mode(width, height):
    """Switch to orthographic projection for 2D overlays."""
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)


def blit_surface_to_screen(surface, width, height):
    """Upload a Pygame surface as a texture and draw it as a fullscreen quad."""
    begin_2d_mode(width, height)
    tex_data = pygame.image.tostring(surface, "RGBA", True)
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, surface.get_width(),
                 surface.get_height(), 0, GL_RGBA, GL_UNSIGNED_BYTE, tex_data)
    glColor4f(1, 1, 1, 1)
    glBegin(GL_QUADS)
    glTexCoord2f(0, 1); glVertex2f(0, 0)
    glTexCoord2f(1, 1); glVertex2f(width, 0)
    glTexCoord2f(1, 0); glVertex2f(width, height)
    glTexCoord2f(0, 0); glVertex2f(0, height)
    glEnd()
    glDeleteTextures([tex_id])
    glDisable(GL_TEXTURE_2D)


# ── Renderer Class ─────────────────────────────────────────────────────
class Renderer3D:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.dl = build_display_lists()
        self.models, self.model_scales = load_models()
        self.fog_tex = build_fog_texture(FLASHLIGHT_RADIUS, 40, width, height)
        self.hud_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        self.dh_map = DATAHALL_MAP
        self._init_gl()

    def _init_gl(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT0, GL_POSITION, [400, 1000, 600, 1])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.4, 0.4, 0.45, 1])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.85, 1])
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        glClearColor(0, 0, 0, 1)
        glShadeModel(GL_SMOOTH)

    def _setup_camera(self, gs):
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(CAM_FOV, self.width / self.height, 1.0, 5000.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        yaw_rad = math.radians(gs.cam_yaw)
        pitch_rad = math.radians(gs.cam_pitch)
        dist = gs.cam_dist

        eye_x = gs.my_x + dist * math.sin(yaw_rad) * math.cos(pitch_rad)
        eye_y = dist * math.sin(pitch_rad)
        eye_z = gs.my_y + dist * math.cos(yaw_rad) * math.cos(pitch_rad)

        gluLookAt(
            eye_x, eye_y, eye_z,
            gs.my_x, 15, gs.my_y,
            0, 1, 0,
        )

    # ── Main draw entry point ──────────────────────────────────────
    def draw_game(self, gs, font, get_nearby_interactable, get_nearby_kill_target, draw_minimap):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # 3D pass
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        self._setup_camera(gs)

        self._draw_floor(gs)
        self._draw_border(gs)
        self._draw_task_stations(gs)
        self._draw_sabotage_stations(gs)
        self._draw_meeting_button(gs)
        self._draw_effects(gs)
        self._draw_players(gs)
        self._draw_local_player(gs)
        self._draw_bodies(gs)

        # Fog overlay
        am_alive = gs.my_id not in gs.dead_players
        if am_alive and not gs.no_fog:
            self._draw_fog()

        # Blackout effects
        self._draw_blackout(gs)

        # HUD overlay
        self._draw_hud(gs, font, get_nearby_interactable, get_nearby_kill_target, draw_minimap)

    # ── 3D Scene Objects ───────────────────────────────────────────
    def _draw_floor(self, gs):
        mw, mh = gs.map_size
        glDisable(GL_LIGHTING)

        # Concrete floor
        glColor3f(0.12, 0.12, 0.15)
        glPushMatrix()
        glTranslatef(mw / 2, -0.1, mh / 2)
        glScalef(mw, 1, mh)
        glCallList(self.dl["quad"])
        glPopMatrix()

        # Tile pattern lines
        glColor3f(0.15, 0.15, 0.18)
        glBegin(GL_LINES)
        for gx in range(0, int(mw) + 1, 50):
            glVertex3f(gx, 0.05, 0)
            glVertex3f(gx, 0.05, mh)
        for gz in range(0, int(mh) + 1, 50):
            glVertex3f(0, 0.05, gz)
            glVertex3f(mw, 0.05, gz)
        glEnd()

        glEnable(GL_LIGHTING)

        # Draw rack floor outlines from datahall map
        if self.dh_map:
            self._draw_rack_outlines()

    def _draw_rack_outlines(self):
        """Draw flat floor markings where racks would be."""
        glDisable(GL_LIGHTING)
        for rack in self.dh_map["racks"]:
            hw, hd = rack["w"] / 2, rack["d"] / 2
            x, z = rack["x"], rack["z"]
            glColor3f(0.12, 0.12, 0.18)
            glBegin(GL_LINE_LOOP)
            glVertex3f(x - hw, 0.2, z - hd)
            glVertex3f(x + hw, 0.2, z - hd)
            glVertex3f(x + hw, 0.2, z + hd)
            glVertex3f(x - hw, 0.2, z + hd)
            glEnd()
        glEnable(GL_LIGHTING)

    def _draw_border(self, gs):
        mw, mh = gs.map_size

        if self.dh_map:
            # Draw datahall walls
            for wall in self.dh_map["walls"]:
                glColor3f(*C_BORDER)
                glPushMatrix()
                glTranslatef(wall["x"], wall["y"], wall["z"])
                glScalef(wall["sx"], wall["sy"], wall["sz"])
                glCallList(self.dl["cube"])
                glPopMatrix()
        else:
            wall_h = 40
            wall_t = 8
            glColor3f(*C_BORDER)
            walls = [
                (mw / 2, wall_h / 2, -wall_t / 2, mw, wall_h, wall_t),
                (mw / 2, wall_h / 2, mh + wall_t / 2, mw, wall_h, wall_t),
                (-wall_t / 2, wall_h / 2, mh / 2, wall_t, wall_h, mh),
                (mw + wall_t / 2, wall_h / 2, mh / 2, wall_t, wall_h, mh),
            ]
            for x, y, z, sx, sy, sz in walls:
                glPushMatrix()
                glTranslatef(x, y, z)
                glScalef(sx, sy, sz)
                glCallList(self.dl["cube"])
                glPopMatrix()

    def _draw_task_stations(self, gs):
        glDisable(GL_LIGHTING)
        for station in gs.task_stations:
            has_task = any(
                t["stationId"] == station["id"] and not t.get("done")
                for t in gs.my_tasks
            )
            if not has_task:
                continue
            # Yellow floor circle
            glColor3f(0.95, 0.75, 0.1)
            glBegin(GL_LINE_LOOP)
            for i in range(16):
                angle = 2 * math.pi * i / 16
                glVertex3f(station["x"] + 20 * math.cos(angle), 0.3,
                           station["y"] + 20 * math.sin(angle))
            glEnd()
        glEnable(GL_LIGHTING)

    def _draw_sabotage_stations(self, gs):
        if gs.my_role != "impostor":
            return
        glDisable(GL_LIGHTING)
        for station in gs.sabotage_stations:
            done = station["id"] in gs.active_sabotages
            if done:
                continue
            # Red floor circle
            glColor3f(0.9, 0.2, 0.1)
            glBegin(GL_LINE_LOOP)
            for i in range(16):
                angle = 2 * math.pi * i / 16
                glVertex3f(station["x"] + 18 * math.cos(angle), 0.3,
                           station["y"] + 18 * math.sin(angle))
            glEnd()
        glEnable(GL_LIGHTING)

    def _draw_meeting_button(self, gs):
        if not gs.meeting_button:
            return
        bx = gs.meeting_button["x"]
        bz = gs.meeting_button["y"]
        # Red floor circle
        glDisable(GL_LIGHTING)
        glColor3f(0.6, 0.1, 0.1)
        glBegin(GL_LINE_LOOP)
        for i in range(20):
            angle = 2 * math.pi * i / 20
            glVertex3f(bx + 25 * math.cos(angle), 0.3, bz + 25 * math.sin(angle))
        glEnd()
        # Inner dot
        glColor3f(0.9, 0.15, 0.15)
        glPointSize(6)
        glBegin(GL_POINTS)
        glVertex3f(bx, 0.4, bz)
        glEnd()
        glEnable(GL_LIGHTING)

    def _draw_character(self, x, z, facing=0, walk_timer=0, speed_ratio=0):
        """Draw a crewmate with facing rotation and walk animation."""
        crew_model = self.models.get("crewmate")
        t = walk_timer
        sr = speed_ratio

        # Walk animation transforms
        bob_y = abs(math.sin(t)) * 2.0 * sr
        sway_x = math.sin(t * 0.5) * 0.8 * sr
        tilt_z = math.sin(t * 0.5) * 3.0 * sr  # lateral lean
        tilt_x = math.sin(t) * 2.0 * sr  # forward pitch per step

        glPushMatrix()
        glTranslatef(x + sway_x, bob_y, z)
        glRotatef(facing, 0, 1, 0)  # face movement direction
        glRotatef(tilt_z, 0, 0, 1)  # lateral lean
        glRotatef(tilt_x, 1, 0, 0)  # forward pitch
        if crew_model:
            s = self.model_scales.get("crewmate", 1)
            glScalef(s, s, s)
            glCallList(crew_model)
        else:
            glCallList(self.dl["character"])
        glPopMatrix()

    def _draw_players(self, gs):
        am_alive = gs.my_id not in gs.dead_players
        for pid, p in gs.positions.items():
            if pid == gs.my_id:
                continue
            if not p.get("alive", True):
                continue
            dist = math.hypot(p["x"] - gs.my_x, p["y"] - gs.my_y)
            if am_alive and not gs.no_fog and dist > FLASHLIGHT_RADIUS * 1.5:
                continue
            color = hex_to_gl(p.get("color", "#ffffff"))
            glColor3f(*color)
            self._draw_character(p["x"], p["y"])

    def _draw_local_player(self, gs):
        if gs.my_id in gs.positions:
            my_color = hex_to_gl(gs.positions[gs.my_id].get("color", "#ffffff"))
        else:
            my_color = C_WHITE

        glColor3f(*my_color)
        self._draw_character(gs.my_x, gs.my_y, gs.facing, gs.walk_timer, gs.speed_ratio)

        # White ring at base for visibility
        glDisable(GL_LIGHTING)
        glColor3f(*C_WHITE)
        glBegin(GL_LINE_LOOP)
        for i in range(24):
            angle = 2 * math.pi * i / 24
            glVertex3f(
                gs.my_x + CHAR_BODY_R * 1.5 * math.cos(angle),
                0.5,
                gs.my_y + CHAR_BODY_R * 1.5 * math.sin(angle),
            )
        glEnd()
        glEnable(GL_LIGHTING)

    def _draw_bodies(self, gs):
        now = time.time()
        glDisable(GL_LIGHTING)
        for eff in gs.effects:
            if eff["type"] != "body":
                continue
            if now - eff["t"] >= eff["duration"]:
                continue
            ex, ez = eff["x"], eff["y"]
            color = hex_to_gl(eff.get("color", "#ff0000"))

            # Flat disc
            glColor3f(*color)
            glBegin(GL_TRIANGLE_FAN)
            glVertex3f(ex, 1.0, ez)
            for i in range(13):
                angle = 2 * math.pi * i / 12
                glVertex3f(ex + 12 * math.cos(angle), 1.0, ez + 12 * math.sin(angle))
            glEnd()

            # Red X
            glColor3f(*C_RED)
            glLineWidth(2)
            glBegin(GL_LINES)
            glVertex3f(ex - 8, 1.5, ez - 8)
            glVertex3f(ex + 8, 1.5, ez + 8)
            glVertex3f(ex + 8, 1.5, ez - 8)
            glVertex3f(ex - 8, 1.5, ez + 8)
            glEnd()
            glLineWidth(1)

        glEnable(GL_LIGHTING)

    def _draw_effects(self, gs):
        """Draw non-body, non-blackout effects (sparks, etc.)."""
        now = time.time()
        glDisable(GL_LIGHTING)
        for eff in gs.effects:
            if eff["type"] in ("body", "blackout"):
                continue
            if now - eff["t"] >= eff["duration"]:
                continue
            ex, ez = eff["x"], eff["y"]
            alpha = max(0, 1 - (now - eff["t"]) / eff["duration"])
            # Pulsing glow on ground
            glColor3f(1.0 * alpha, 0.3 * alpha, 0.1 * alpha)
            glPushMatrix()
            glTranslatef(ex, 5, ez)
            glScalef(20, 10, 20)
            glCallList(self.dl["sphere"])
            glPopMatrix()
        glEnable(GL_LIGHTING)

    def _draw_blackout(self, gs):
        """Screen-space blackout overlay for sabotage effects."""
        now = time.time()
        for eff in gs.effects:
            if eff["type"] != "blackout":
                continue
            if now - eff["t"] >= eff["duration"]:
                continue
            alpha = max(0, 1 - (now - eff["t"]) / eff["duration"])
            begin_2d_mode(self.width, self.height)
            glDisable(GL_TEXTURE_2D)
            glColor4f(0, 0, 0, 0.78 * alpha)
            glBegin(GL_QUADS)
            glVertex2f(0, 0)
            glVertex2f(self.width, 0)
            glVertex2f(self.width, self.height)
            glVertex2f(0, self.height)
            glEnd()

    # ── Fog overlay ────────────────────────────────────────────────
    def _draw_fog(self):
        begin_2d_mode(self.width, self.height)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.fog_tex)
        glColor4f(1, 1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 1); glVertex2f(0, 0)
        glTexCoord2f(1, 1); glVertex2f(self.width, 0)
        glTexCoord2f(1, 0); glVertex2f(self.width, self.height)
        glTexCoord2f(0, 0); glVertex2f(0, self.height)
        glEnd()
        glDisable(GL_TEXTURE_2D)

    # ── HUD overlay ────────────────────────────────────────────────
    def _draw_hud(self, gs, font, get_nearby_interactable, get_nearby_kill_target, draw_minimap):
        self.hud_surf.fill((0, 0, 0, 0))
        w, h = self.width, self.height

        # Minimap
        draw_minimap(self.hud_surf, gs)

        # Role badge
        role_color = HUD_RED if gs.my_role == "impostor" else HUD_GREEN
        role_text = "IMPOSTOR" if gs.my_role == "impostor" else "CREW"
        badge = font.render(role_text, True, role_color)
        self.hud_surf.blit(badge, (10, 10))

        # Task progress (crew)
        if gs.my_role == "crew":
            my_done = sum(1 for t in gs.my_tasks if t.get("done"))
            my_total = len(gs.my_tasks)
            task_text = font.render(f"Tasks: {my_done}/{my_total}", True, HUD_WHITE)
            self.hud_surf.blit(task_text, (10, 35))

            if gs.total_crew_tasks > 0:
                bar_w, bar_h = 150, 12
                fill = int(gs.completed_tasks / gs.total_crew_tasks * bar_w)
                pygame.draw.rect(self.hud_surf, HUD_GRAY, (10, 58, bar_w, bar_h))
                pygame.draw.rect(self.hud_surf, HUD_GREEN, (10, 58, fill, bar_h))
                pygame.draw.rect(self.hud_surf, HUD_WHITE, (10, 58, bar_w, bar_h), 1)
                pct = font.render(f"Team: {gs.completed_tasks}/{gs.total_crew_tasks}", True, HUD_DIM)
                self.hud_surf.blit(pct, (10, 73))

        # Sabotage count (impostor)
        if gs.my_role == "impostor":
            sab_text = font.render(f"Sabotaged: {gs.sabotages_done}/{gs.sabotages_needed}", True, HUD_RED)
            self.hud_surf.blit(sab_text, (10, 35))
            hint = font.render("[Q] Kill nearby  |  Go to SAB stations", True, HUD_DIM)
            self.hud_surf.blit(hint, (10, 58))

        # Controls hint
        controls = font.render("WASD=move  E=interact  SPACE=meeting  ESC=menu", True, HUD_DIM)
        self.hud_surf.blit(controls, (w // 2 - controls.get_width() // 2, h - 25))

        # Interact prompt
        nearby = get_nearby_interactable()
        if nearby:
            prompt = font.render(f"[E] {nearby['label']}", True, HUD_AMBER)
            self.hud_surf.blit(prompt, (w // 2 - prompt.get_width() // 2, h // 2 + 50))

        # Kill prompt (impostor)
        if gs.my_role == "impostor":
            if gs.kill_cooldown > 0:
                cd_text = font.render(f"Kill cooldown: {int(gs.kill_cooldown)}s", True, HUD_DIM)
                self.hud_surf.blit(cd_text, (w // 2 - cd_text.get_width() // 2, h // 2 + 75))
            else:
                target = get_nearby_kill_target()
                if target:
                    prompt = font.render(f"[Q] Kill {target['name']}", True, HUD_RED)
                    self.hud_surf.blit(prompt, (w // 2 - prompt.get_width() // 2, h // 2 + 75))

        # Blit HUD surface as texture
        blit_surface_to_screen(self.hud_surf, w, h)
