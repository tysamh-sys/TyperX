import pygame
import math
import random

class Enemy:
    def __init__(self, word, x, y, speed, theme, is_boss=False):
        self.word = word
        self.typed_index = 0
        self.x = x
        self.y = y
        self.speed = speed
        self.theme = theme
        self.is_target = False
        self.is_boss = is_boss
        
        # UI dimensions
        self.padding_x = 10
        self.padding_y = 6
        self.radius = 8
        
        # Unique random parameters for organic variety
        self.rotation = random.uniform(0, 360)
        self.wobble = random.uniform(0, math.pi * 2)
        self.wobble_speed = random.uniform(0.02, 0.06)
        self.particle_offset = random.randint(0, 12)
        self.anim_tick = 0
        
        # Particles for trailing effects
        self.trail_particles = []

    def update(self):
        self.y += self.speed
        self.anim_tick += 1
        self.rotation += 1.5 if not self.is_boss else 0.3
        self.wobble += self.wobble_speed
        
        # Emit trail particles
        if self.anim_tick % 3 == 0:
            particle_color = self._get_trail_color()
            if particle_color:
                self.trail_particles.append({
                    "x": self.x + random.randint(-8, 8),
                    "y": self.y,
                    "vx": random.uniform(-0.5, 0.5),
                    "vy": random.uniform(-1.0, -0.2),
                    "life": 20,
                    "max_life": 20,
                    "color": particle_color,
                    "size": random.randint(1, 3)
                })
                
        # Update existing particles
        for p in self.trail_particles[:]:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 1
            if p["life"] <= 0:
                self.trail_particles.remove(p)

    def check_char(self, char):
        if self.typed_index < len(self.word):
            return self.word[self.typed_index] == char
        return False

    def type_char(self):
        if self.typed_index < len(self.word):
            self.typed_index += 1

    def is_completed(self):
        return self.typed_index >= len(self.word)

    def _get_trail_color(self):
        theme_type = self.theme.get("type", "space")
        if theme_type == "space":
            return (random.randint(100, 180), random.randint(60, 120), random.randint(200, 255))
        elif theme_type == "winter":
            val = random.randint(160, 255)
            return (val - 20, val, 255)
        elif theme_type == "volcano":
            return (255, random.randint(40, 120), 0)
        elif theme_type == "fantasy":
            return (random.randint(150, 255), random.randint(50, 150), 255)
        elif theme_type == "cyber":
            return (0, random.randint(180, 255), random.randint(60, 140))
        return None

    def draw(self, screen, font, target_font=None):
        theme_type = self.theme.get("type", "space")
        accent = self.theme.get("accent", (0, 229, 255))
        enemy_color = self.theme.get("enemy", (180, 80, 220))
        
        use_font = target_font if (self.is_boss and target_font) else font
        
        # Draw trail particles behind object
        for p in self.trail_particles:
            alpha = int(255 * (p["life"] / p["max_life"]))
            color = p["color"]
            r = max(1, p["size"])
            # Draw particle as simple circle
            pygame.draw.circle(screen, color, (int(p["x"]), int(p["y"])), r)

        # === DRAW THEMED OBJECT ===
        if theme_type == "space":
            self._draw_meteor(screen, enemy_color, accent)
        elif theme_type == "winter":
            self._draw_ice_crystal(screen, enemy_color, accent)
        elif theme_type == "volcano":
            self._draw_fireball(screen, enemy_color, accent)
        elif theme_type == "fantasy":
            self._draw_rune(screen, enemy_color, accent)
        elif theme_type == "cyber":
            self._draw_digital_block(screen, enemy_color, accent)
        
        # === DRAW WORD TEXT ===
        self._draw_word(screen, use_font, accent)

    def _draw_meteor(self, screen, enemy_color, accent):
        # Irregular asteroid polygon
        size = 28 if self.is_boss else 18
        num_verts = 8 if self.is_boss else 7
        points = []
        for i in range(num_verts):
            angle = math.radians((360 / num_verts) * i + self.rotation)
            r = size + math.sin(self.wobble + i) * (size * 0.25)
            px = self.x + r * math.cos(angle)
            py = self.y - 5 + r * math.sin(angle)
            points.append((px, py))
        
        # Glow behind
        glow_surf = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
        pygame.draw.polygon(glow_surf, (*accent[:3], 30), [(p[0] - self.x + size * 2, p[1] - self.y + 5 + size * 2) for p in points])
        screen.blit(glow_surf, (self.x - size * 2, self.y - 5 - size * 2))
        
        # Main rock fill
        dark = tuple(max(0, c - 60) for c in enemy_color)
        pygame.draw.polygon(screen, dark, points)
        pygame.draw.polygon(screen, enemy_color, points, width=2)
        # Crater mark
        pygame.draw.circle(screen, (40, 40, 50), (int(self.x - size // 4), int(self.y - 8)), size // 4)

    def _draw_ice_crystal(self, screen, enemy_color, accent):
        size = 24 if self.is_boss else 16
        angle_offset = self.rotation
        # Two overlaid hexagons at different rotations
        for hex_rot in [0, 30]:
            pts = []
            for i in range(6):
                a = math.radians(60 * i + hex_rot + angle_offset)
                pts.append((self.x + size * math.cos(a), self.y - 5 + size * math.sin(a)))
            inner_pts = []
            for i in range(6):
                a = math.radians(60 * i + hex_rot + angle_offset)
                r2 = size * 0.5
                inner_pts.append((self.x + r2 * math.cos(a), self.y - 5 + r2 * math.sin(a)))
            
            # Fill with translucent ice effect
            s = pygame.Surface((size * 3, size * 3), pygame.SRCALPHA)
            shifted = [(p[0] - self.x + size * 1.5, p[1] - self.y + 5 + size * 1.5) for p in pts]
            if len(shifted) >= 3:
                pygame.draw.polygon(s, (*enemy_color[:3], 60 if hex_rot == 0 else 80), shifted)
            screen.blit(s, (self.x - size * 1.5, self.y - 5 - size * 1.5))
            pygame.draw.polygon(screen, enemy_color, pts, width=2)
        
        # Central glow dot
        pygame.draw.circle(screen, accent, (int(self.x), int(self.y - 5)), size // 3)
        pygame.draw.circle(screen, (255, 255, 255), (int(self.x), int(self.y - 5)), size // 6)

    def _draw_fireball(self, screen, enemy_color, accent):
        size = 26 if self.is_boss else 17
        # Outer flame corona
        for layer in range(3, 0, -1):
            r = size + layer * 5 + math.sin(self.anim_tick * 0.15 + layer) * 3
            alpha = 40 // layer
            s = pygame.Surface((r * 3, r * 3), pygame.SRCALPHA)
            flame_color = (255, max(0, 80 - layer * 20), 0, alpha)
            pygame.draw.circle(s, flame_color, (int(r * 1.5), int(r * 1.5)), int(r))
            screen.blit(s, (int(self.x - r * 1.5), int(self.y - 5 - r * 1.5)))
        
        # Core fireball
        pygame.draw.circle(screen, (255, 60, 0), (int(self.x), int(self.y - 5)), size)
        pygame.draw.circle(screen, (255, 160, 0), (int(self.x), int(self.y - 5)), int(size * 0.65))
        pygame.draw.circle(screen, (255, 240, 100), (int(self.x), int(self.y - 5)), int(size * 0.3))

    def _draw_rune(self, screen, enemy_color, accent):
        size = 24 if self.is_boss else 16
        # Glowing outer seal circle
        pygame.draw.circle(screen, enemy_color, (int(self.x), int(self.y - 5)), size, width=2)
        
        # Inner star pattern
        star_pts = []
        for i in range(5):
            # Outer tip
            a_outer = math.radians(72 * i - 90 + self.rotation)
            star_pts.append((self.x + size * math.cos(a_outer), self.y - 5 + size * math.sin(a_outer)))
            # Inner point
            a_inner = math.radians(72 * i + 36 - 90 + self.rotation)
            star_pts.append((self.x + size * 0.4 * math.cos(a_inner), self.y - 5 + size * 0.4 * math.sin(a_inner)))
        pygame.draw.polygon(screen, enemy_color, star_pts, width=1)
        
        # Pulsing glow center
        glow_r = int(size * 0.2 + math.sin(self.anim_tick * 0.1) * 3)
        pygame.draw.circle(screen, accent, (int(self.x), int(self.y - 5)), glow_r)
        
        # Outer ring tick marks
        for i in range(8):
            a = math.radians(45 * i + self.rotation)
            x1 = self.x + (size - 3) * math.cos(a)
            y1 = self.y - 5 + (size - 3) * math.sin(a)
            x2 = self.x + (size + 3) * math.cos(a)
            y2 = self.y - 5 + (size + 3) * math.sin(a)
            pygame.draw.line(screen, accent, (int(x1), int(y1)), (int(x2), int(y2)), 1)

    def _draw_digital_block(self, screen, enemy_color, accent):
        size = 26 if self.is_boss else 16
        # Blocky square
        block_rect = pygame.Rect(self.x - size, self.y - size - 5, size * 2, size * 2)
        pygame.draw.rect(screen, (10, 20, 10), block_rect, border_radius=3)
        pygame.draw.rect(screen, enemy_color, block_rect, width=2, border_radius=3)
        
        # Matrix code rain chars inside
        code_chars = "01ABCDXYZ#$!"
        char_tick = (self.anim_tick // 4 + self.particle_offset) % len(code_chars)
        char_surf = pygame.font.SysFont("Consolas", 10, bold=False)
        try:
            c1 = char_surf.render(code_chars[char_tick], True, accent)
            c2 = char_surf.render(code_chars[(char_tick + 3) % len(code_chars)], True, enemy_color)
            c3 = char_surf.render(code_chars[(char_tick + 7) % len(code_chars)], True, accent)
            screen.blit(c1, (int(self.x - 10), int(self.y - 12)))
            screen.blit(c2, (int(self.x + 2), int(self.y - 12)))
            screen.blit(c3, (int(self.x - 4), int(self.y)))
        except Exception:
            pass
        
        # Corner brackets
        b = size - 4
        cx, cy = int(self.x), int(self.y - 5)
        for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            fx = cx + dx * b
            fy = cy + dy * b
            pygame.draw.line(screen, accent, (fx, fy - dy * 6), (fx, fy), 2)
            pygame.draw.line(screen, accent, (fx - dx * 6, fy), (fx, fy), 2)

    def _draw_word(self, screen, font, accent):
        word = self.word
        typed_idx = self.typed_index
        
        # Measure total width
        total_w = font.size(word)[0]
        text_h = font.size("A")[1]
        
        # Object offset
        obj_gap = 26 if not self.is_boss else 38
        label_y = self.y + obj_gap

        box_w = total_w + self.padding_x * 2
        box_h = text_h + self.padding_y * 2
        box_x = int(self.x - box_w // 2)
        box_y = int(label_y - box_h // 2)
        
        box_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        
        # Border color based on target state
        border_col = accent if self.is_target else self.theme.get("enemy", (200, 100, 100))
        bg_col = (15, 15, 25) if not self.is_boss else (30, 10, 10)
        
        pygame.draw.rect(screen, bg_col, box_rect, border_radius=6)
        pygame.draw.rect(screen, border_col, box_rect, width=2, border_radius=6)
        
        # Draw characters individually with coloring
        cur_x = box_x + self.padding_x
        char_y = box_y + self.padding_y
        
        for i, ch in enumerate(word):
            if i < typed_idx:
                color = (50, 255, 50)        # Typed = green
            else:
                color = (220, 220, 225)      # Untyped = white-ish
                
            char_surf = font.render(ch, True, color)
            screen.blit(char_surf, (cur_x, char_y))
            cur_x += char_surf.get_width()

    def get_width(self, font):
        return font.size(self.word)[0] + self.padding_x * 2
