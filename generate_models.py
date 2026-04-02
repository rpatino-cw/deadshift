#!/usr/bin/env python3
"""Generate OBJ model files for DEADSHIFT game assets."""

import math
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "assets", "models")


class OBJBuilder:
    def __init__(self):
        self.verts = []
        self.normals = []
        self.faces = []

    def add_vert(self, x, y, z):
        self.verts.append((x, y, z))
        return len(self.verts)

    def add_normal(self, x, y, z):
        self.normals.append((x, y, z))
        return len(self.normals)

    def add_face(self, v_indices, n_indices=None):
        if n_indices:
            self.faces.append(list(zip(v_indices, n_indices)))
        else:
            self.faces.append([(v,) for v in v_indices])

    def add_box(self, cx, cy, cz, sx, sy, sz):
        """Add a box centered at (cx, cy, cz) with size (sx, sy, sz)."""
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        corners = [
            (cx - hx, cy - hy, cz - hz), (cx + hx, cy - hy, cz - hz),
            (cx + hx, cy + hy, cz - hz), (cx - hx, cy + hy, cz - hz),
            (cx - hx, cy - hy, cz + hz), (cx + hx, cy - hy, cz + hz),
            (cx + hx, cy + hy, cz + hz), (cx - hx, cy + hy, cz + hz),
        ]
        base = len(self.verts)
        for c in corners:
            self.add_vert(*c)
        b = base + 1  # OBJ is 1-indexed
        # 6 faces (quads split into 2 triangles each)
        quads = [
            (0, 1, 2, 3, (0, 0, -1)),  (5, 4, 7, 6, (0, 0, 1)),
            (4, 0, 3, 7, (-1, 0, 0)),  (1, 5, 6, 2, (1, 0, 0)),
            (3, 2, 6, 7, (0, 1, 0)),   (4, 5, 1, 0, (0, -1, 0)),
        ]
        for i0, i1, i2, i3, n in quads:
            ni = self.add_normal(*n)
            self.add_face([b + i0, b + i1, b + i2], [ni, ni, ni])
            self.add_face([b + i0, b + i2, b + i3], [ni, ni, ni])

    def add_cylinder(self, cx, cy, cz, radius, height, slices=12):
        """Add a cylinder from (cx, cy, cz) up to (cx, cy+height, cz)."""
        base_v = len(self.verts)
        # Bottom and top ring vertices
        for ring in range(2):
            y = cy + ring * height
            for i in range(slices):
                angle = 2 * math.pi * i / slices
                self.add_vert(cx + radius * math.cos(angle), y, cz + radius * math.sin(angle))

        b = base_v + 1
        # Side faces
        for i in range(slices):
            i_next = (i + 1) % slices
            bl = b + i
            br = b + i_next
            tl = b + slices + i
            tr = b + slices + i_next
            angle = 2 * math.pi * (i + 0.5) / slices
            ni = self.add_normal(math.cos(angle), 0, math.sin(angle))
            self.add_face([bl, br, tr], [ni, ni, ni])
            self.add_face([bl, tr, tl], [ni, ni, ni])

        # Top cap
        top_center = self.add_vert(cx, cy + height, cz)
        ni_top = self.add_normal(0, 1, 0)
        for i in range(slices):
            i_next = (i + 1) % slices
            self.add_face([top_center, b + slices + i, b + slices + i_next],
                          [ni_top, ni_top, ni_top])

        # Bottom cap
        bot_center = self.add_vert(cx, cy, cz)
        ni_bot = self.add_normal(0, -1, 0)
        for i in range(slices):
            i_next = (i + 1) % slices
            self.add_face([bot_center, b + i_next, b + i],
                          [ni_bot, ni_bot, ni_bot])

    def add_hemisphere(self, cx, cy, cz, radius, stacks=6, slices=12):
        """Add a hemisphere (top half of sphere) at (cx, cy, cz)."""
        base_v = len(self.verts)
        for i in range(stacks + 1):
            lat = (math.pi / 2) * i / stacks
            y = cy + radius * math.sin(lat)
            r = radius * math.cos(lat)
            for j in range(slices):
                angle = 2 * math.pi * j / slices
                self.add_vert(cx + r * math.cos(angle), y, cz + r * math.sin(angle))

        b = base_v + 1
        for i in range(stacks):
            for j in range(slices):
                j_next = (j + 1) % slices
                v0 = b + i * slices + j
                v1 = b + i * slices + j_next
                v2 = b + (i + 1) * slices + j_next
                v3 = b + (i + 1) * slices + j
                ni = self.add_normal(0, 1, 0)  # simplified normal
                self.add_face([v0, v1, v2], [ni, ni, ni])
                self.add_face([v0, v2, v3], [ni, ni, ni])

    def write(self, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            f.write(f"# DEADSHIFT generated model\n")
            f.write(f"# Vertices: {len(self.verts)} Faces: {len(self.faces)}\n\n")
            for v in self.verts:
                f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
            f.write("\n")
            for n in self.normals:
                f.write(f"vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}\n")
            f.write("\n")
            for face in self.faces:
                parts = []
                for entry in face:
                    if len(entry) == 2:
                        parts.append(f"{entry[0]}//{entry[1]}")
                    else:
                        parts.append(str(entry[0]))
                f.write(f"f {' '.join(parts)}\n")
        print(f"  {os.path.basename(filepath)}: {len(self.verts)} verts, {len(self.faces)} faces")


def generate_crewmate():
    """Among Us style bean character — body + visor + backpack."""
    obj = OBJBuilder()
    # Body: cylinder
    obj.add_cylinder(0, 0, 0, 5, 18, slices=14)
    # Head: hemisphere on top
    obj.add_hemisphere(0, 18, 0, 5, stacks=5, slices=14)
    # Visor: flat box on front
    obj.add_box(0, 16, -5.5, 7, 4, 1.5)
    # Backpack: box on back
    obj.add_box(0, 10, 5, 6, 10, 4)
    # Legs: two small cylinders
    obj.add_cylinder(-2.2, -4, 0, 2, 4, slices=8)
    obj.add_cylinder(2.2, -4, 0, 2, 4, slices=8)
    obj.write(os.path.join(OUT_DIR, "crewmate.obj"))


def generate_rack():
    """Server rack — tall box with front panel detail."""
    obj = OBJBuilder()
    # Main cabinet body
    obj.add_box(0, 40, 0, 26, 80, 46)
    # Front panel (slightly recessed, thinner)
    obj.add_box(0, 40, -22, 22, 72, 2)
    # Horizontal drive bays (6 ventilation slots on front)
    for i in range(6):
        y = 12 + i * 11
        obj.add_box(0, y, -24, 20, 1.5, 0.5)
    # Top handles
    obj.add_box(-10, 79, -20, 2, 2, 6)
    obj.add_box(10, 79, -20, 2, 2, 6)
    # Status LED area (small box at top front)
    obj.add_box(0, 75, -24, 4, 3, 0.5)
    obj.write(os.path.join(OUT_DIR, "rack.obj"))


def generate_meeting_button():
    """Emergency meeting button — pedestal + dome."""
    obj = OBJBuilder()
    # Pedestal base (wide cylinder)
    obj.add_cylinder(0, 0, 0, 14, 5, slices=16)
    # Pedestal column
    obj.add_cylinder(0, 5, 0, 8, 15, slices=12)
    # Button dome
    obj.add_hemisphere(0, 20, 0, 10, stacks=6, slices=14)
    # Button ring
    obj.add_cylinder(0, 18, 0, 11, 3, slices=14)
    obj.write(os.path.join(OUT_DIR, "meeting_btn.obj"))


def generate_sab_terminal():
    """Sabotage terminal — angled console with screen."""
    obj = OBJBuilder()
    # Base box
    obj.add_box(0, 7.5, 0, 14, 15, 10)
    # Angled top (box tilted via position hack — slightly offset)
    obj.add_box(0, 17, -1.5, 12, 4, 8)
    # Screen (thin bright panel on angled face)
    obj.add_box(0, 17.5, -5.5, 8, 2.5, 0.5)
    # Warning stripes (small boxes on sides)
    obj.add_box(-7.5, 10, 0, 1, 10, 8)
    obj.add_box(7.5, 10, 0, 1, 10, 8)
    obj.write(os.path.join(OUT_DIR, "sab_terminal.obj"))


if __name__ == "__main__":
    print("Generating DEADSHIFT models...")
    generate_crewmate()
    generate_rack()
    generate_meeting_button()
    generate_sab_terminal()
    print("Done! Models saved to assets/models/")
