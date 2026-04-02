#!/usr/bin/env python3
"""Generate high-quality OBJ model files for DEADSHIFT game assets.

Creates Among Us-style crewmate, server rack with detail, meeting button,
and sabotage terminal. All models use proper smooth normals.
"""

import math
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "assets", "models")


class OBJBuilder:
    def __init__(self):
        self.verts = []
        self.normals = []
        self.faces = []

    def v(self, x, y, z):
        self.verts.append((x, y, z))
        return len(self.verts)

    def vn(self, x, y, z):
        length = math.sqrt(x*x + y*y + z*z) or 1
        self.normals.append((x/length, y/length, z/length))
        return len(self.normals)

    def f(self, verts_normals):
        """Add face: list of (v_idx, vn_idx) tuples."""
        self.faces.append(verts_normals)

    def tri(self, v1, n1, v2, n2, v3, n3):
        self.faces.append([(v1, n1), (v2, n2), (v3, n3)])

    def quad(self, v1, n1, v2, n2, v3, n3, v4, n4):
        self.tri(v1, n1, v2, n2, v3, n3)
        self.tri(v1, n1, v3, n3, v4, n4)

    def add_lathe(self, profile, slices=16):
        """Revolve a 2D profile (list of (radius, y) pairs) around Y axis.
        Creates smooth normals. Returns (base_v, base_n) offsets."""
        rows = len(profile)
        bv = len(self.verts)
        bn = len(self.normals)

        # Generate vertices and normals
        for i, (r, y) in enumerate(profile):
            # Compute tangent direction for normals
            if i == 0:
                dr = profile[1][0] - r
                dy = profile[1][1] - y
            elif i == rows - 1:
                dr = r - profile[i-1][0]
                dy = y - profile[i-1][1]
            else:
                dr = profile[i+1][0] - profile[i-1][0]
                dy = profile[i+1][1] - profile[i-1][1]
            # Normal is perpendicular to tangent in the profile plane
            nl = math.sqrt(dr*dr + dy*dy) or 1
            nx_base = dy / nl   # perpendicular: swap and negate
            ny_base = -dr / nl

            for j in range(slices):
                angle = 2 * math.pi * j / slices
                ca, sa = math.cos(angle), math.sin(angle)
                self.v(r * ca, y, r * sa)
                self.vn(nx_base * ca, ny_base, nx_base * sa)

        # Generate faces
        for i in range(rows - 1):
            for j in range(slices):
                j_next = (j + 1) % slices
                v0 = bv + 1 + i * slices + j
                v1 = bv + 1 + i * slices + j_next
                v2 = bv + 1 + (i + 1) * slices + j_next
                v3 = bv + 1 + (i + 1) * slices + j
                n0 = bn + 1 + i * slices + j
                n1 = bn + 1 + i * slices + j_next
                n2 = bn + 1 + (i + 1) * slices + j_next
                n3 = bn + 1 + (i + 1) * slices + j
                self.quad(v0, n0, v1, n1, v2, n2, v3, n3)

    def add_box(self, cx, cy, cz, sx, sy, sz):
        hx, hy, hz = sx/2, sy/2, sz/2
        corners = [
            (cx-hx, cy-hy, cz-hz), (cx+hx, cy-hy, cz-hz),
            (cx+hx, cy+hy, cz-hz), (cx-hx, cy+hy, cz-hz),
            (cx-hx, cy-hy, cz+hz), (cx+hx, cy-hy, cz+hz),
            (cx+hx, cy+hy, cz+hz), (cx-hx, cy+hy, cz+hz),
        ]
        b = len(self.verts)
        for c in corners:
            self.v(*c)
        b += 1
        face_defs = [
            (0,1,2,3, (0,0,-1)), (5,4,7,6, (0,0,1)),
            (4,0,3,7, (-1,0,0)), (1,5,6,2, (1,0,0)),
            (3,2,6,7, (0,1,0)), (4,5,1,0, (0,-1,0)),
        ]
        for i0,i1,i2,i3,n in face_defs:
            ni = self.vn(*n)
            self.tri(b+i0, ni, b+i1, ni, b+i2, ni)
            self.tri(b+i0, ni, b+i2, ni, b+i3, ni)

    def add_cylinder(self, cx, cy, cz, radius, height, slices=14):
        """Smooth cylinder with caps."""
        profile = [(radius, cy), (radius, cy + height)]
        self.add_lathe(profile, slices)
        # Top cap
        tc = self.v(cx, cy + height, cz)
        ni = self.vn(0, 1, 0)
        bv = len(self.verts) - slices * 2 - 1  # top ring start
        for j in range(slices):
            j_next = (j + 1) % slices
            self.tri(tc, ni, bv + slices + j + 1, ni, bv + slices + j_next + 1, ni)
        # Bottom cap
        bc = self.v(cx, cy, cz)
        ni2 = self.vn(0, -1, 0)
        for j in range(slices):
            j_next = (j + 1) % slices
            self.tri(bc, ni2, bv + j_next + 1, ni2, bv + j + 1, ni2)

    def write(self, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(f"# DEADSHIFT generated model\n")
            f.write(f"# Vertices: {len(self.verts)} Normals: {len(self.normals)} Faces: {len(self.faces)}\n\n")
            for v in self.verts:
                f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
            f.write("\n")
            for n in self.normals:
                f.write(f"vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}\n")
            f.write("\n")
            for face in self.faces:
                parts = [f"{vi}//{ni}" for vi, ni in face]
                f.write(f"f {' '.join(parts)}\n")
        print(f"  {os.path.basename(filepath)}: {len(self.verts)} verts, {len(self.faces)} faces")


# ── Crewmate (Among Us bean) ──────────────────────────────────────
def generate_crewmate():
    """Smooth bean-shaped crewmate with visor and backpack."""
    obj = OBJBuilder()

    # Bean body: lathe profile (smooth rounded capsule shape)
    # Profile goes from bottom of legs up to top of head
    body_profile = [
        # Legs/feet (slight flare)
        (0.5, -4),
        (2.5, -3.5),
        (2.8, -2),
        # Leg gap (pinch inward)
        (2.0, 0),
        # Body widens
        (4.5, 2),
        (5.2, 5),
        (5.5, 8),
        (5.5, 11),
        (5.3, 14),
        (5.0, 16),
        # Head rounds off
        (4.5, 18),
        (3.8, 20),
        (2.8, 21.5),
        (1.5, 22.5),
        (0.3, 23),
    ]
    obj.add_lathe(body_profile, slices=18)

    # Visor (flat blue panel on front face)
    obj.add_box(0, 17, -5.8, 7, 4.5, 1.2)

    # Backpack (rounded bump on back)
    backpack_profile = [
        (0.2, 6),
        (2.5, 7),
        (3.2, 9),
        (3.2, 13),
        (2.5, 15),
        (0.2, 16),
    ]
    # Offset backpack to back: we'll add it as a half-lathe manually
    # For simplicity, use a box with slight proportions
    obj.add_box(0, 11, 6.5, 6, 10, 4)

    obj.write(os.path.join(OUT_DIR, "crewmate.obj"))


# ── Server Rack ───────────────────────────────────────────────────
def generate_rack():
    """Detailed server rack with drive bays, handles, and LED indicators."""
    obj = OBJBuilder()

    # Main cabinet body (slightly beveled edges via outer shell)
    obj.add_box(0, 40, 0, 26, 80, 46)

    # Front panel (recessed inset)
    obj.add_box(0, 40, -22.5, 22, 72, 1.5)

    # 8 drive bay slots (horizontal lines on front panel)
    for i in range(8):
        y = 8 + i * 9
        obj.add_box(0, y, -23.5, 20, 1.0, 0.3)

    # U-markers (small side ticks every 4.5 units)
    for i in range(16):
        y = 5 + i * 4.5
        obj.add_box(-12.5, y, -23, 1, 0.5, 0.5)
        obj.add_box(12.5, y, -23, 1, 0.5, 0.5)

    # Top handles
    obj.add_box(-9, 80.5, -18, 3, 1.5, 8)
    obj.add_box(9, 80.5, -18, 3, 1.5, 8)

    # Status LED panel (top front)
    obj.add_box(0, 76, -23.5, 6, 2, 0.3)

    # Power strip on back
    obj.add_box(0, 30, 23.5, 4, 50, 1)

    # Feet (4 small pads)
    for x in (-10, 10):
        for z in (-18, 18):
            obj.add_box(x, -0.5, z, 4, 1, 4)

    obj.write(os.path.join(OUT_DIR, "rack.obj"))


# ── Meeting Button ────────────────────────────────────────────────
def generate_meeting_button():
    """Emergency meeting button — pedestal with dome button on top."""
    obj = OBJBuilder()

    # Base platform
    base_profile = [
        (0.5, 0),
        (15, 0.5),
        (15, 2),
        (12, 3),
    ]
    obj.add_lathe(base_profile, slices=20)

    # Pedestal column
    column_profile = [
        (9, 3),
        (8, 5),
        (7, 8),
        (7, 16),
        (8, 18),
        (10, 19),
    ]
    obj.add_lathe(column_profile, slices=16)

    # Button dome (hemisphere)
    dome_profile = []
    for i in range(10):
        angle = (math.pi / 2) * i / 9
        r = 9 * math.cos(angle)
        y = 19 + 6 * math.sin(angle)
        dome_profile.append((max(r, 0.3), y))
    obj.add_lathe(dome_profile, slices=16)

    # Button ring (decorative rim)
    ring_profile = [
        (10.5, 18),
        (11, 19),
        (10.5, 20),
    ]
    obj.add_lathe(ring_profile, slices=16)

    obj.write(os.path.join(OUT_DIR, "meeting_btn.obj"))


# ── Sabotage Terminal ─────────────────────────────────────────────
def generate_sab_terminal():
    """Sabotage console — angled terminal with screen and warning details."""
    obj = OBJBuilder()

    # Base cabinet
    obj.add_box(0, 8, 0, 16, 16, 12)

    # Angled top panel
    obj.add_box(0, 17.5, -1, 14, 3, 10)

    # Screen (recessed bright panel)
    obj.add_box(0, 18, -5, 10, 1.5, 0.5)

    # Keyboard area (lower front)
    obj.add_box(0, 12, -6.5, 10, 1, 1)

    # Warning stripes on sides
    for i in range(3):
        y = 5 + i * 5
        obj.add_box(-8.5, y, 0, 1, 2, 10)
        obj.add_box(8.5, y, 0, 1, 2, 10)

    # Antenna/sensor on top
    obj.add_box(5, 20, 3, 1, 4, 1)

    # Base feet
    obj.add_box(-6, -0.5, -4, 3, 1, 3)
    obj.add_box(6, -0.5, -4, 3, 1, 3)
    obj.add_box(-6, -0.5, 4, 3, 1, 3)
    obj.add_box(6, -0.5, 4, 3, 1, 3)

    obj.write(os.path.join(OUT_DIR, "sab_terminal.obj"))


if __name__ == "__main__":
    print("Generating DEADSHIFT models (v2 — smooth normals)...")
    generate_crewmate()
    generate_rack()
    generate_meeting_button()
    generate_sab_terminal()
    print("Done! Models saved to assets/models/")
