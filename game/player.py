import pygame
import math
from game.settings import (
    COLOR_PLAYER, COLOR_ENEMY_NORMAL
)

class Player:
    def __init__(self):
        self.max_lives = 5
        self.lives = self.max_lives
        self.score = 0
        self.high_score = 0
        self.level = 1
        
        # Stats tracking
        self.words_typed = 0
        self.correct_keystrokes = 0
        self.total_keystrokes = 0
        
        # Positions (initialized with fallbacks, set dynamically by game loop)
        self.x = 400
        self.y = 540
        self.width = 60
        self.height = 45
        
        # Hit flash animation timer
        self.hit_timer = 0
        # Rotation counter for orbiting animations (e.g. fantasy obelisk rings)
        self.anim_ticks = 0

    def update_position(self, screen_width, screen_height):
        self.x = screen_width // 2
        self.y = screen_height - 70

    def lose_life(self):
        self.lives = max(0, self.lives - 1)
        self.hit_timer = 15 # flash for 15 frames

    def add_score(self, word_len):
        points = word_len * 10 * self.level
        self.score += points
        self.words_typed += 1
        if self.score > self.high_score:
            self.high_score = self.score

    def reset(self):
        self.lives = self.max_lives
        self.score = 0
        self.level = 1
        self.words_typed = 0
        self.correct_keystrokes = 0
        self.total_keystrokes = 0
        self.hit_timer = 0
        self.anim_ticks = 0

    def update(self):
        if self.hit_timer > 0:
            self.hit_timer -= 1
        self.anim_ticks += 1

    def draw(self, screen, theme):
        theme_type = theme.get("type", "space")
        accent = theme.get("accent", (0, 229, 255))
        
        # If player hit recently, flash white/red
        primary_color = (255, 100, 100) if self.hit_timer % 4 > 1 else accent
        
        # 1. DRAW PLAYER BASED ON LEVEL THEME
        if theme_type == "space":
            # Space Starship
            points = [
                (self.x, self.y - self.height // 2),                   # Nose tip
                (self.x - self.width // 4, self.y - self.height // 6),  # Left body join
                (self.x - self.width // 2, self.y + self.height // 2),  # Left wingtip
                (self.x - self.width // 6, self.y + self.height // 4),  # Left thruster join
                (self.x, self.y + self.height // 3),                    # Inner tail notch
                (self.x + self.width // 6, self.y + self.height // 4),  # Right thruster join
                (self.x + self.width // 2, self.y + self.height // 2),  # Right wingtip
                (self.x + self.width // 4, self.y - self.height // 6)   # Right body join
            ]
            pygame.draw.polygon(screen, primary_color, points)
            # Inner wing lines
            pygame.draw.line(screen, (30, 30, 45), (self.x, self.y - 10), (self.x - 20, self.y + 15), 2)
            pygame.draw.line(screen, (30, 30, 45), (self.x, self.y - 10), (self.x + 20, self.y + 15), 2)
            
            # Engine Flame
            flame_len = 10 + (self.anim_ticks % 3) * 4
            flame_points = [
                (self.x - 6, self.y + self.height // 4),
                (self.x, self.y + self.height // 4 + flame_len),
                (self.x + 6, self.y + self.height // 4)
            ]
            pygame.draw.polygon(screen, (255, 120, 0), flame_points)
            
        elif theme_type == "winter":
            # Frost Cannon Turret
            # Base (Heavy dome)
            base_rect = pygame.Rect(self.x - 24, self.y + 5, 48, 20)
            pygame.draw.rect(screen, primary_color, base_rect, border_radius=6)
            pygame.draw.circle(screen, primary_color, (self.x, self.y + 5), 18)
            
            # Twin Barrels
            offset_y = math.sin(self.anim_ticks * 0.1) * 3
            pygame.draw.rect(screen, primary_color, pygame.Rect(self.x - 10, self.y - 18 + offset_y, 6, 20))
            pygame.draw.rect(screen, primary_color, pygame.Rect(self.x + 4, self.y - 18 - offset_y, 6, 20))
            # Blue core nozzles
            pygame.draw.rect(screen, (0, 255, 255), pygame.Rect(self.x - 9, self.y - 21 + offset_y, 4, 3))
            pygame.draw.rect(screen, (0, 255, 255), pygame.Rect(self.x + 5, self.y - 21 - offset_y, 4, 3))
            
        elif theme_type == "volcano":
            # Magma Tank
            # Side Tread plates
            pygame.draw.polygon(screen, (80, 80, 90), [
                (self.x - 28, self.y + 15), (self.x - 22, self.y - 8),
                (self.x - 14, self.y - 8), (self.x - 14, self.y + 15)
            ])
            pygame.draw.polygon(screen, (80, 80, 90), [
                (self.x + 14, self.y + 15), (self.x + 14, self.y - 8),
                (self.x + 22, self.y - 8), (self.x + 28, self.y + 15)
            ])
            # Main Tread Body
            body_rect = pygame.Rect(self.x - 20, self.y - 3, 40, 18)
            pygame.draw.rect(screen, primary_color, body_rect, border_radius=4)
            # Glowing Core
            pygame.draw.circle(screen, (255, 0, 0), (self.x, self.y + 5), 6)
            # Magma Cannon Barrel
            pygame.draw.rect(screen, primary_color, pygame.Rect(self.x - 4, self.y - 20, 8, 18))
            pygame.draw.circle(screen, (255, 100, 0), (self.x, self.y - 20), 5)
            
        elif theme_type == "fantasy":
            # Arcane Spellweaver Obelisk
            # Levitation floating offset
            float_offset = math.sin(self.anim_ticks * 0.08) * 6
            center_y = self.y + float_offset
            
            # Glowing Diamond Spire
            spire_points = [
                (self.x, center_y - 24),
                (self.x - 12, center_y),
                (self.x, center_y + 24),
                (self.x + 12, center_y)
            ]
            pygame.draw.polygon(screen, primary_color, spire_points)
            pygame.draw.polygon(screen, (255, 255, 255), spire_points, width=1)
            
            # Orbiting Rings (Drawn as ellipses)
            ring_angle = self.anim_ticks * 0.05
            ellipse_w = 40
            ellipse_h = 10
            # Orbit 1
            cos_val = math.cos(ring_angle)
            sin_val = math.sin(ring_angle)
            pygame.draw.ellipse(screen, (255, 215, 0), (self.x - 20, center_y - 8, 40, 16), width=1)
            # Orbit 2
            pygame.draw.ellipse(screen, (255, 215, 0), (self.x - 16, center_y + 2, 32, 10), width=1)
            
        elif theme_type == "cyber":
            # Mainframe Hacker Core Node
            # Main terminal box
            terminal_rect = pygame.Rect(self.x - 25, self.y - 15, 50, 30)
            pygame.draw.rect(screen, (20, 20, 30), terminal_rect, border_radius=4)
            pygame.draw.rect(screen, primary_color, terminal_rect, width=2, border_radius=4)
            
            # Flashing Node lights
            for idx in range(3):
                col_y = self.y - 8 + idx * 7
                active_light = (self.anim_ticks // 8) % 3 == idx
                light_color = primary_color if active_light else (15, 60, 20)
                pygame.draw.circle(screen, light_color, (self.x - 12, col_y), 3)
                
            # Right Node line graph
            line_pts = [
                (self.x + 5, self.y + 5),
                (self.x + 12, self.y - 5 + (self.anim_ticks % 5)),
                (self.x + 18, self.y + 5)
            ]
            pygame.draw.lines(screen, primary_color, False, line_pts, width=2)

        # 2. DRAW HUD SHIELD OVERLAY (AROUND PLAYER POSITION)
        if self.lives > 0:
            shield_radius = self.width - 5
            shield_rect = pygame.Rect(
                self.x - shield_radius, 
                self.y - shield_radius // 2, 
                shield_radius * 2, 
                shield_radius * 2
            )
            # Arc size represents percentage of health left
            health_pct = self.lives / self.max_lives
            pygame.draw.arc(
                screen, 
                primary_color, 
                shield_rect, 
                3.14 - (health_pct * 1.57), 
                3.14 + (health_pct * 1.57), 
                width=2
            )
            # Small glow sparkles
            if self.anim_ticks % 20 < 4:
                pygame.draw.circle(screen, (255, 255, 255), (int(self.x + shield_radius * math.cos(self.anim_ticks * 0.1)), int(self.y + shield_radius * 0.5 * math.sin(self.anim_ticks * 0.1))), 2)
