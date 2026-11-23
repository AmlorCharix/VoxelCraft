"""
VoxelCraft - a small playable Minecraft-style voxel sandbox.
Requirements: Python 3.10+, pygame, numpy, moderngl
Install: py -m pip install pygame numpy moderngl
Run:     py main.py

Controls:
  WASD move, mouse look, Space jump, Shift descend while flying
  Left click break, right click place, 1-8 select hotbar slot
  Mouse wheel changes selected slot, E inventory, F3 debug, Esc release mouse
  Ctrl+S save, Ctrl+L load, F5 save, F9 load
"""

import json
import math
import os
import random
import time
from pathlib import Path

import moderngl
import numpy as np
import pygame

# ----------------------------- Settings ------------------------------------
WIDTH, HEIGHT = 1100, 700
CHUNK = 16
WORLD_HEIGHT = 64
VIEW_DISTANCE = 2                 # chunks in each direction
SEED = 1337
SAVE_DIR = Path(__file__).with_name("saves")
SAVE_FILE = SAVE_DIR / "world.json"
RENDER_DISTANCE = 90.0
MOUSE_SENS = 0.0022
WALK_SPEED = 6.0
FLY_SPEED = 10.0
GRAVITY = 22.0
JUMP_SPEED = 8.5

# Block IDs
AIR, GRASS, DIRT, STONE, WOOD, LEAVES, SAND, WATER, PLANKS = range(9)
BLOCK_NAMES = {
    GRASS: "Grass", DIRT: "Dirt", STONE: "Stone", WOOD: "Wood",
    LEAVES: "Leaves", SAND: "Sand", WATER: "Water", PLANKS: "Planks"
}
HOTBAR = [GRASS, DIRT, STONE, WOOD, LEAVES, SAND, WATER, PLANKS]
COLORS = {
    GRASS: (0.30, 0.72, 0.24), DIRT: (0.48, 0.30, 0.16),
    STONE: (0.53, 0.55, 0.58), WOOD: (0.48, 0.30, 0.13),
    LEAVES: (0.17, 0.52, 0.18), SAND: (0.78, 0.70, 0.43),
    WATER: (0.12, 0.38, 0.82), PLANKS: (0.68, 0.48, 0.25)
}

# Face corners are wound counter-clockwise when viewed from outside.
FACES = [
    (( 1,0,0), [(1,0,0),(1,1,0),(1,1,1),(1,0,1)]),
    ((-1,0,0), [(0,0,1),(0,1,1),(0,1,0),(0,0,0)]),
    ((0, 1,0), [(0,1,1),(1,1,1),(1,1,0),(0,1,0)]),
    ((0,-1,0), [(0,0,0),(1,0,0),(1,0,1),(0,0,1)]),
    ((0,0, 1), [(1,0,1),(1,1,1),(0,1,1),(0,0,1)]),
    ((0,0,-1), [(0,0,0),(0,1,0),(1,1,0),(1,0,0)])
]
TRI = (0, 1, 2, 0, 2, 3)

# ----------------------------- Math ----------------------------------------
def normalize(v):
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-8 else v

def perspective(fov, aspect, near, far):
    f = 1.0 / math.tan(fov / 2.0)
    m = np.zeros((4, 4), dtype="f4")
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m

def look_at(eye, target, up):
    f = normalize(target - eye)
    s = normalize(np.cross(f, up))
    u = np.cross(s, f)
    m = np.eye(4, dtype="f4")
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[0, 3] = -np.dot(s, eye)
    m[1, 3] = -np.dot(u, eye)
    m[2, 3] = np.dot(f, eye)
    return m

def gl_matrix(m):
    return np.asarray(m, dtype="f4").T.tobytes()

# ----------------------------- World ---------------------------------------
class World:
    def __init__(self, seed=SEED):
        self.seed = int(seed)
        self.chunks = {}
        self.dirty = set()
        self.edits = {}  # "x,y,z" -> block id; AIR means removed block
        self.generated = set()
        self.rng = random.Random(self.seed)

    def height_at(self, x, z):
        # Smooth deterministic rolling terrain with a low shoreline.
        n = (math.sin(x * 0.075) * 3.4 +
             math.cos(z * 0.062) * 3.0 +
             math.sin((x + z) * 0.035) * 4.0 +
             math.cos((x - z) * 0.021) * 2.0)
        return max(3, min(30, int(15 + n)))

    @staticmethod
    def chunk_key(x, z):
        return (math.floor(x / CHUNK), math.floor(z / CHUNK))

    def get_chunk(self, cx, cz):
        key = (cx, cz)
        if key not in self.chunks:
            self.generate_chunk(cx, cz)
        return self.chunks[key]

    def generate_chunk(self, cx, cz):
        key = (cx, cz)
        if key in self.generated:
            return self.chunks.get(key)
        arr = np.zeros((CHUNK, WORLD_HEIGHT, CHUNK), dtype=np.uint8)
        rng = random.Random(self.seed + cx * 928371 + cz * 689287)
        for lx in range(CHUNK):
            for lz in range(CHUNK):
                x, z = cx * CHUNK + lx, cz * CHUNK + lz
                h = self.height_at(x, z)
                top = SAND if h <= 12 else GRASS
                for y in range(h + 1):
                    if y == h:
                        arr[lx, y, lz] = top
                    elif y >= h - 3:
                        arr[lx, y, lz] = SAND if top == SAND else DIRT
                    else:
                        arr[lx, y, lz] = STONE
                # Sea level.
                for y in range(h + 1, 13):
                    arr[lx, y, lz] = WATER

        # Trees are placed only from a deterministic chunk-local random stream.
        for _ in range(5):
            lx, lz = rng.randrange(2, CHUNK - 2), rng.randrange(2, CHUNK - 2)
            x, z = cx * CHUNK + lx, cz * CHUNK + lz
            h = self.height_at(x, z)
            if h <= 13 or arr[lx, h, lz] != GRASS:
                continue
            trunk = rng.randint(3, 5)
            for yy in range(h + 1, min(WORLD_HEIGHT, h + trunk + 1)):
                arr[lx, yy, lz] = WOOD
            crown_y = h + trunk
            for dx in range(-2, 3):
                for dz in range(-2, 3):
                    for dy in range(-1, 2):
                        if abs(dx) + abs(dz) + abs(dy) <= 4:
                            ax, ay, az = lx + dx, crown_y + dy, lz + dz
                            if 0 <= ax < CHUNK and 0 <= az < CHUNK and 0 <= ay < WORLD_HEIGHT:
                                if arr[ax, ay, az] == AIR:
                                    arr[ax, ay, az] = LEAVES

        self.chunks[key] = arr
        self.generated.add(key)
        # Reapply saved edits to this newly generated chunk.
        for k, block in list(self.edits.items()):
            x, y, z = map(int, k.split(","))
            if self.chunk_key(x, z) == key and 0 <= y < WORLD_HEIGHT:
                arr[x % CHUNK, y, z % CHUNK] = block
        self.dirty.add(key)
        return arr

    def get(self, x, y, z):
        if y < 0:
            return STONE
        if y >= WORLD_HEIGHT:
            return AIR
        cx, cz = self.chunk_key(x, z)
        arr = self.get_chunk(cx, cz)
        return int(arr[x % CHUNK, y, z % CHUNK])

    def set(self, x, y, z, block):
        if not (0 <= y < WORLD_HEIGHT):
            return
        cx, cz = self.chunk_key(x, z)
        arr = self.get_chunk(cx, cz)
        arr[x % CHUNK, y, z % CHUNK] = block
        self.edits[f"{x},{y},{z}"] = int(block)
        self.dirty.add((cx, cz))
        if x % CHUNK == 0: self.dirty.add((cx - 1, cz))
        if x % CHUNK == CHUNK - 1: self.dirty.add((cx + 1, cz))
        if z % CHUNK == 0: self.dirty.add((cx, cz - 1))
        if z % CHUNK == CHUNK - 1: self.dirty.add((cx, cz + 1))

    def ensure_area(self, px, pz):
        pcx, pcz = self.chunk_key(int(px), int(pz))
        for cx in range(pcx - VIEW_DISTANCE, pcx + VIEW_DISTANCE + 1):
            for cz in range(pcz - VIEW_DISTANCE, pcz + VIEW_DISTANCE + 1):
                self.get_chunk(cx, cz)

    def save(self):
        SAVE_DIR.mkdir(exist_ok=True)
        data = {"seed": self.seed, "edits": self.edits}
        temp = SAVE_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(data), encoding="utf-8")
        temp.replace(SAVE_FILE)

    def load(self):
        if not SAVE_FILE.exists():
            return False
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
        self.seed = int(data.get("seed", SEED))
        self.edits = data.get("edits", {})
        self.chunks.clear()
        self.generated.clear()
        self.dirty.clear()
        return True

# ----------------------------- Player --------------------------------------
class Player:
    def __init__(self):
        self.pos = np.array([8.0, 24.0, 8.0], dtype="f4")
        self.yaw = 0.0
        self.pitch = 0.0
        self.velocity_y = 0.0
        self.on_ground = False
        self.flying = False

    def direction(self):
        cp = math.cos(self.pitch)
        return normalize(np.array([
            math.sin(self.yaw) * cp,
            math.sin(self.pitch),
            -math.cos(self.yaw) * cp
        ], dtype="f4"))

    def right(self):
        return normalize(np.cross(self.direction(), np.array([0, 1, 0], dtype="f4")))

    def move(self, world, dt, keys):
        forward = np.array([math.sin(self.yaw), 0, -math.cos(self.yaw)], dtype="f4")
        right = np.array([math.cos(self.yaw), 0, math.sin(self.yaw)], dtype="f4")
        wish = np.zeros(3, dtype="f4")
        if keys[pygame.K_w]: wish += forward
        if keys[pygame.K_s]: wish -= forward
        if keys[pygame.K_d]: wish += right
        if keys[pygame.K_a]: wish -= right
        if self.flying:
            if keys[pygame.K_SPACE]: wish[1] += 1
            if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]: wish[1] -= 1
            if np.linalg.norm(wish) > 0: wish = normalize(wish)
            self.pos += wish * FLY_SPEED * dt
            self.pos[1] = max(1.0, min(WORLD_HEIGHT - 1.0, self.pos[1]))
            return
        if np.linalg.norm(wish) > 0:
            wish = normalize(wish)
        self.pos[0] += wish[0] * WALK_SPEED * dt
        self._collide_axis(world, 0)
        self.pos[2] += wish[2] * WALK_SPEED * dt
        self._collide_axis(world, 2)

        if self.on_ground and keys[pygame.K_SPACE]:
            self.velocity_y = JUMP_SPEED
            self.on_ground = False
        self.velocity_y -= GRAVITY * dt
        self.pos[1] += self.velocity_y * dt
        self._collide_axis(world, 1)

    def _collide_axis(self, world, axis):
        # Simple player AABB, height 1.8 blocks, radius 0.3.
        x, y, z = self.pos
        minx, maxx = math.floor(x - .28), math.floor(x + .28)
        minz, maxz = math.floor(z - .28), math.floor(z + .28)
        feet = math.floor(y - 1.65)
        head = math.floor(y + .12)
        collided = False
        for bx in range(minx, maxx + 1):
            for bz in range(minz, maxz + 1):
                for by in range(feet, head + 1):
                    b = world.get(bx, by, bz)
                    if b not in (AIR, WATER, LEAVES):
                        collided = True
                        if axis == 1:
                            if self.velocity_y < 0:
                                self.pos[1] = by + 1 + 1.65
                                self.on_ground = True
                            else:
                                self.pos[1] = by - .13
                            self.velocity_y = 0
        if axis == 1 and not collided:
            self.on_ground = False
        if collided and axis != 1:
            # Back out a small amount along the blocked axis.
            self.pos[axis] -= (0.08 if axis == 0 else 0.08) * (1 if self.pos[axis] >= 0 else -1)

# ----------------------------- Renderer ------------------------------------
VERT_SHADER = """
#version 330
in vec3 in_pos;
in vec3 in_color;
uniform mat4 mvp;
out vec3 color;
out float light_value;
void main() {
    gl_Position = mvp * vec4(in_pos, 1.0);
    color = in_color;
    light_value = 1.0;
}
"""
FRAG_SHADER = """
#version 330
in vec3 color;
in float light_value;
out vec4 fragColor;
uniform float alpha;
void main() {
    fragColor = vec4(color * light_value, alpha);
}
"""

class Renderer:
    def __init__(self, window):
        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        self.program = self.ctx.program(vertex_shader=VERT_SHADER, fragment_shader=FRAG_SHADER)
        self.meshes = {}
        self.window = window

    def build_chunk(self, world, key):
        cx, cz = key
        arr = world.get_chunk(cx, cz)
        vertices = []
        for lx in range(CHUNK):
            for lz in range(CHUNK):
                for y in range(WORLD_HEIGHT):
                    block = int(arr[lx, y, lz])
                    if block == AIR:
                        continue
                    wx, wz = cx * CHUNK + lx, cz * CHUNK + lz
                    base = np.array(COLORS.get(block, (1, 1, 1)), dtype="f4")
                    # Water is translucent-ish blue; render opaque for reliable depth.
                    for normal, corners in FACES:
                        nx, ny, nz = normal
                        neighbor = world.get(wx + nx, y + ny, wz + nz)
                        if neighbor != AIR and not (block == WATER and neighbor != WATER):
                            continue
                        shade = { (0,1,0):1.0, (0,-1,0):.52, (1,0,0):.78,
                                  (-1,0,0):.72, (0,0,1):.86, (0,0,-1):.68}[normal]
                        if block == WATER: shade *= .9
                        col = base * shade
                        points = [(wx + p[0], y + p[1], wz + p[2]) for p in corners]
                        for idx in TRI:
                            vertices.extend((*points[idx], *col))
        if key in self.meshes:
            self.meshes[key].release()
            del self.meshes[key]
        if vertices:
            data = np.array(vertices, dtype="f4")
            vbo = self.ctx.buffer(data.tobytes())
            vao = self.ctx.vertex_array(self.program, [(vbo, "3f 3f", "in_pos", "in_color")])
            self.meshes[key] = (vbo, vao, len(data) // 6)

    def rebuild_dirty(self, world):
        for key in list(world.dirty):
            if key in world.chunks:
                self.build_chunk(world, key)
            world.dirty.discard(key)

    def render(self, player):
        self.ctx.viewport = (0, 0, WIDTH, HEIGHT)
        self.ctx.clear(0.48, 0.70, 0.91, 1.0, depth=1.0)
        eye = player.pos + np.array([0, -0.15, 0], dtype="f4")
        view = look_at(eye, eye + player.direction(), np.array([0, 1, 0], dtype="f4"))
        proj = perspective(math.radians(75), WIDTH / HEIGHT, 0.08, RENDER_DISTANCE)
        mvp = proj @ view
        self.program["mvp"].write(gl_matrix(mvp))
        self.program["alpha"].value = 1.0
        for vbo, vao, count in list(self.meshes.values()):
            vao.render(moderngl.TRIANGLES)

    def close(self):
        for vbo, vao, _ in self.meshes.values():
            vao.release()
            vbo.release()
        self.program.release()

# ----------------------------- Game ----------------------------------------
def raycast(world, origin, direction, max_dist=6.0):
    """Voxel DDA raycast. Returns (hit_block_xyz, previous_empty_xyz)."""
    direction = normalize(direction)
    x, y, z = map(math.floor, origin)
    step = np.sign(direction).astype(int)
    t_delta = np.array([
        abs(1 / direction[0]) if abs(direction[0]) > 1e-8 else 1e30,
        abs(1 / direction[1]) if abs(direction[1]) > 1e-8 else 1e30,
        abs(1 / direction[2]) if abs(direction[2]) > 1e-8 else 1e30
    ])
    t_max = np.array([
        ((x + 1 - origin[0]) if step[0] > 0 else (origin[0] - x)) * t_delta[0],
        ((y + 1 - origin[1]) if step[1] > 0 else (origin[1] - y)) * t_delta[1],
        ((z + 1 - origin[2]) if step[2] > 0 else (origin[2] - z)) * t_delta[2]
    ])
    previous = (x, y, z)
    distance = 0.0
    while distance <= max_dist:
        if world.get(x, y, z) not in (AIR, WATER):
            return (x, y, z), previous
        previous = (x, y, z)
        axis = int(np.argmin(t_max))
        distance = float(t_max[axis])
        if axis == 0: x += step[0]
        elif axis == 1: y += step[1]
        else: z += step[2]
        t_max[axis] += t_delta[axis]
    return None, None

def draw_text(surface, font, text, pos, color=(255,255,255)):
    shadow = font.render(text, True, (20, 20, 20))
    surface.blit(shadow, (pos[0] + 2, pos[1] + 2))
    surface.blit(font.render(text, True, color), pos)

def main():
    pygame.init()
    pygame.display.set_caption("VoxelCraft - Python Voxel Sandbox")
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.OPENGL | pygame.DOUBLEBUF)
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 18)
    small = pygame.font.SysFont("consolas", 14)
    renderer = Renderer(screen)
    world = World()
    player = Player()
    world.ensure_area(player.pos[0], player.pos[2])
    renderer.rebuild_dirty(world)
    pygame.event.set_grab(True)
    pygame.mouse.set_visible(False)
    pygame.mouse.get_rel()

    selected = 0
    inventory_open = False
    debug = False
    message = "Welcome! WASD move | Mouse look | Left break | Right place | F5 save"
    message_until = time.time() + 5
    running = True

    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                if event.key == pygame.K_ESCAPE:
                    pygame.event.set_grab(False)
                    pygame.mouse.set_visible(True)
                elif event.key == pygame.K_RETURN and not pygame.event.get_grab():
                    pygame.event.set_grab(True)
                    pygame.mouse.set_visible(False)
                    pygame.mouse.get_rel()
                elif event.key == pygame.K_F3:
                    debug = not debug
                elif event.key == pygame.K_e:
                    inventory_open = not inventory_open
                elif event.key == pygame.K_f:
                    player.flying = not player.flying
                    message = "Flight " + ("enabled" if player.flying else "disabled")
                    message_until = time.time() + 2
                elif event.key == pygame.K_F5 or (event.key == pygame.K_s and mods & pygame.KMOD_CTRL):
                    world.save()
                    message, message_until = "World saved!", time.time() + 2
                elif event.key == pygame.K_F9 or (event.key == pygame.K_l and mods & pygame.KMOD_CTRL):
                    if world.load():
                        world.ensure_area(player.pos[0], player.pos[2])
                        renderer.rebuild_dirty(world)
                        message = "World loaded!"
                    else:
                        message = "No save file found."
                    message_until = time.time() + 2
                elif pygame.K_1 <= event.key <= pygame.K_8:
                    selected = event.key - pygame.K_1
            elif event.type == pygame.MOUSEMOTION and pygame.event.get_grab() and not inventory_open:
                dx, dy = event.rel
                player.yaw += dx * MOUSE_SENS
                player.pitch -= dy * MOUSE_SENS
                player.pitch = max(-1.52, min(1.52, player.pitch))
            elif event.type == pygame.MOUSEWHEEL:
                selected = (selected - event.y) % len(HOTBAR)
            elif event.type == pygame.MOUSEBUTTONDOWN and pygame.event.get_grab() and not inventory_open:
                if event.button in (1, 3):
                    hit, place = raycast(world, player.pos + np.array([0, -0.15, 0]), player.direction())
                    if hit:
                        if event.button == 1:
                            world.set(*hit, AIR)
                        elif place and world.get(*place) == AIR:
                            # Avoid placing a block inside the player's body.
                            px, py, pz = player.pos
                            if not (place[0] <= px + .3 and place[0] + 1 >= px - .3 and
                                    place[1] <= py + .1 and place[1] + 1 >= py - 1.7 and
                                    place[2] <= pz + .3 and place[2] + 1 >= pz - .3):
                                world.set(*place, HOTBAR[selected])

        if pygame.event.get_grab() and not inventory_open:
            keys = pygame.key.get_pressed()
            player.move(world, dt, keys)

        world.ensure_area(player.pos[0], player.pos[2])
        renderer.rebuild_dirty(world)
        renderer.render(player)

        # Pygame's 2D overlay is drawn after the OpenGL scene.
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # Crosshair.
        pygame.draw.line(overlay, (255,255,255,230), (WIDTH//2-9, HEIGHT//2), (WIDTH//2+9, HEIGHT//2), 2)
        pygame.draw.line(overlay, (255,255,255,230), (WIDTH//2, HEIGHT//2-9), (WIDTH//2, HEIGHT//2+9), 2)

        # Hotbar.
        slot_w, slot_h = 58, 54
        start_x = WIDTH//2 - (slot_w * 8)//2
        ybar = HEIGHT - 70
        for i, block in enumerate(HOTBAR):
            x = start_x + i * slot_w
            pygame.draw.rect(overlay, (25,25,25,210), (x, ybar, slot_w-4, slot_h), border_radius=5)
            pygame.draw.rect(overlay, (245,245,245,255) if i == selected else (100,100,100,255),
                             (x, ybar, slot_w-4, slot_h), 3 if i == selected else 1, border_radius=5)
            c = tuple(int(v*255) for v in COLORS[block])
            pygame.draw.rect(overlay, c, (x+16, ybar+8, 22, 22), border_radius=3)
            draw_text(overlay, small, str(i+1), (x+5, ybar+35))
        draw_text(overlay, small, BLOCK_NAMES[HOTBAR[selected]], (WIDTH//2-45, ybar-22))

        if inventory_open:
            panel = pygame.Rect(WIDTH//2-230, HEIGHT//2-150, 460, 300)
            pygame.draw.rect(overlay, (25,25,35,235), panel, border_radius=12)
            pygame.draw.rect(overlay, (220,220,220,255), panel, 2, border_radius=12)
            draw_text(overlay, font, "INVENTORY - press 1-8 to select, E to close",
                      (panel.x+22, panel.y+20))
            for i, block in enumerate(HOTBAR):
                col, row = i % 4, i // 4
                x, y = panel.x+35+col*105, panel.y+85+row*85
                pygame.draw.rect(overlay, tuple(int(v*255) for v in COLORS[block]), (x,y,32,32))
                draw_text(overlay, small, f"{i+1}. {BLOCK_NAMES[block]}", (x+40,y+7))

        if debug:
            draw_text(overlay, small, f"XYZ: {player.pos[0]:.1f}, {player.pos[1]:.1f}, {player.pos[2]:.1f}", (12, 12))
            draw_text(overlay, small, f"Chunks: {len(world.chunks)} | FPS: {clock.get_fps():.0f} | Flying: {player.flying}", (12, 32))
            draw_text(overlay, small, "F toggles flight | F3 debug | Esc releases mouse | Enter captures", (12, 52))
        if time.time() < message_until:
            label = font.render(message, True, (255,255,255))
            overlay.blit(label, (WIDTH//2-label.get_width()//2, 18))

        # Blit overlay using pygame after switching out of the OpenGL framebuffer.
        # pygame's OPENGL display does not support normal Surface blits, so draw UI via
        # a temporary 2D OpenGL texture.
        rgba = pygame.image.tostring(overlay, "RGBA", True)
        tex = renderer.ctx.texture((WIDTH, HEIGHT), 4, rgba)
        tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        # A tiny fullscreen shader for the HUD.
        if not hasattr(renderer, "hud_program"):
            renderer.hud_program = renderer.ctx.program(
                vertex_shader="""#version 330
                in vec2 p; in vec2 uv; out vec2 v_uv;
                void main(){ v_uv=uv; gl_Position=vec4(p,0.0,1.0); }""",
                fragment_shader="""#version 330
                uniform sampler2D hud; in vec2 v_uv; out vec4 f;
                void main(){ f=texture(hud,v_uv); }"""
            )
            quad = np.array([-1,-1,0,0, 1,-1,1,0, 1,1,1,1,
                             -1,-1,0,0, 1,1,1,1, -1,1,0,1], dtype="f4")
            renderer.hud_vbo = renderer.ctx.buffer(quad.tobytes())
            renderer.hud_vao = renderer.ctx.vertex_array(renderer.hud_program,
                [(renderer.hud_vbo, "2f 2f", "p", "uv")])
        renderer.ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        tex.use(0)
        renderer.hud_program["hud"].value = 0
        renderer.hud_vao.render(moderngl.TRIANGLES)
        renderer.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        tex.release()
        pygame.display.flip()

    world.save()
    renderer.close()
    if hasattr(renderer, "hud_vao"):
        renderer.hud_vao.release()
        renderer.hud_vbo.release()
        renderer.hud_program.release()
    pygame.quit()

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\nVoxelCraft stopped with an error:")
        print(exc)
        raise
