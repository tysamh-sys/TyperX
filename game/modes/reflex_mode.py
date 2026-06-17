import pygame
import random
import math
import sys
import string

from game.modes.base_mode import BaseMode
from game.settings import (
    COLOR_TEXT_NORMAL, COLOR_UI_TEXT, STATE_PLAYING, STATE_PAUSED,
    STATE_GAME_OVER, STATE_VICTORY, LEVEL_THEMES, MAX_LEVEL
)
from game.player import Player
from game.particles import ParticleSystem

class FallingLetter:
    def __init__(self, char, x, y, speed, color):
        self.char = char
        self.x = x
        self.y = y
        self.speed = speed
        self.color = color
        self.radius = 18
        self.pulse_timer = random.uniform(0, 2 * math.pi)
        self.trail_particles = []

    def update(self):
        self.y += self.speed
        self.pulse_timer += 0.08
        
        # Emit trail particles occasionally
        if random.random() < 0.25:
            self.trail_particles.append({
                "x": self.x + random.randint(-4, 4),
                "y": self.y - 8,
                "vx": random.uniform(-0.4, 0.4),
                "vy": -random.uniform(0.3, 1.2),
                "life": 16,
                "max_life": 16
            })
            
        for p in self.trail_particles[:]:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["life"] -= 1
            if p["life"] <= 0:
                self.trail_particles.remove(p)

    def draw(self, screen, font):
        # Draw particle trail
        for p in self.trail_particles:
            alpha = int(255 * (p["life"] / p["max_life"]))
            r, g, b = self.color[:3]
            size = max(1, int(3 * (p["life"] / p["max_life"])))
            pygame.draw.circle(screen, (r, g, b), (int(p["x"]), int(p["y"])), size)

        # Pulse animation
        pulse_r = self.radius + math.sin(self.pulse_timer) * 3
        
        # Glow outer ring
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), int(pulse_r), width=2)
        
        # Solid inner circle
        pygame.draw.circle(screen, (15, 15, 22), (int(self.x), int(self.y)), self.radius)
        
        # Letter text
        text_surf = font.render(self.char, True, (255, 255, 255))
        screen.blit(text_surf, (int(self.x - text_surf.get_width() / 2), int(self.y - text_surf.get_height() / 2)))


class ReflexMode(BaseMode):
    def __init__(self, game):
        super().__init__(game)
        self.player = Player()
        
        # Game stats
        self.current_level = 1
        self.score = 0
        self.lives = 5
        self.max_lives = 5
        self.streak = 0
        self.best_streak = 0
        self.correct_keys = 0
        self.total_keys = 0
        self.errors = 0
        self.misses = 0
        
        # State machine
        self.level_completed_stats = False
        self.play_start_time = 0
        self.pause_start_time = 0
        self.last_spawn_time = 0
        self.level_transition_timer = 0
        self.screen_shake = 0
        
        # Entities & VFX
        self.falling_letters = []
        self.particle_system = None
        self.lasers = []
        self.streak_popups = []
        self.explosion_particles = []
        
        self.player_target_x = self.game.screen_w // 2
        
    def start(self):
        self.session_saved = False
        
        # Load progress and stats from database if profile is active
        if self.game.active_profile:
            prof_id = self.game.active_profile["id"]
            saved_stats = self.game.db_manager.get_stats(prof_id, self.game.difficulty, "reflex")
            if saved_stats:
                self.current_level = saved_stats["current_level"]
                self.game.high_scores["reflex"] = saved_stats["highest_score"]
            else:
                self.current_level = 1
        else:
            self.current_level = 1

        self.score = 0
        
        # Scale starting lives based on difficulty
        if self.game.difficulty == "beginner":
            self.max_lives = 7
        elif self.game.difficulty == "hard":
            self.max_lives = 3
        else:
            self.max_lives = 5
            
        self.lives = self.max_lives
        self.streak = 0
        self.best_streak = 0
        self.correct_keys = 0
        self.total_keys = 0
        self.errors = 0
        self.misses = 0
        
        self.level_completed_stats = False
        self.falling_letters.clear()
        self.lasers.clear()
        self.streak_popups.clear()
        self.explosion_particles.clear()
        
        self.game.state = STATE_PLAYING
        self.play_start_time = pygame.time.get_ticks()
        self.last_spawn_time = self.play_start_time
        
        self.player_target_x = self.game.screen_w // 2
        self.player.x = self.player_target_x
        self.player.y = self.game.screen_h - 70
        self.player.lives = self.lives
        self.player.max_lives = self.max_lives
        self.player.score = 0
        self.player.high_score = self.game.high_scores["reflex"]
        
        self._reset_particles()

    def save_session_stats(self):
        """Saves current session metrics to the database."""
        if self.session_saved:
            return
        
        if self.game.active_profile:
            elapsed = (pygame.time.get_ticks() - self.play_start_time) / 1000.0
            if elapsed < 0:
                elapsed = 0.0
                
            self.game.db_manager.save_game_session(
                profile_id=self.game.active_profile["id"],
                difficulty=self.game.difficulty,
                mode="reflex",
                level=self.current_level,
                score=self.score,
                words=self.correct_keys,
                correct=self.correct_keys,
                total=self.total_keys,
                combo=self.best_streak,
                elapsed_time=elapsed
            )
            
            # Retrieve updated stats to refresh high scores
            saved_stats = self.game.db_manager.get_stats(
                self.game.active_profile["id"], self.game.difficulty, "reflex"
            )
            if saved_stats:
                self.game.high_scores["reflex"] = saved_stats["highest_score"]
                self.player.high_score = saved_stats["highest_score"]
                
        self.session_saved = True

    def advance_level(self):
        if self.current_level >= MAX_LEVEL:
            self.game.state = STATE_VICTORY
            self.save_session_stats()
            return
            
        self.current_level += 1
        self.level_completed_stats = False
        self.falling_letters.clear()
        self.lasers.clear()
        self.explosion_particles.clear()
        self.level_transition_timer = 180  # 3 seconds at 60fps
        self._reset_particles()
        self.game.play_sound("level_up")
        
        self.save_session_stats()
        self.session_saved = False

    def _reset_particles(self):
        theme = self.get_theme()
        self.particle_system = ParticleSystem(
            self.game.screen_w, self.game.screen_h, theme["type"], density=90, difficulty=self.game.difficulty
        )

    def get_theme(self):
        level_index = (self.current_level - 1) % 5 + 1
        base_theme = LEVEL_THEMES.get(level_index, LEVEL_THEMES[1])
        
        # Apply difficulty modifications dynamically
        theme = base_theme.copy()
        if self.game.difficulty == "beginner":
            theme["bg"] = tuple(min(255, c + 15) for c in theme["bg"])
            theme["bg"] = (theme["bg"][0], theme["bg"][1] + 12, theme["bg"][2] + 25)
            theme["accent"] = (100, 220, 255)
            theme["enemy"] = (210, 150, 240)
        elif self.game.difficulty == "hard":
            theme["bg"] = (max(5, theme["bg"][0] // 2 + 12), max(1, theme["bg"][1] // 4), max(1, theme["bg"][2] // 4))
            theme["accent"] = (255, 64, 64)
            theme["enemy"] = (255, 235, 59)
            
        return theme

    # ---- Difficulty Metrics ----

    def _get_level_target_score(self):
        targets = {1: 500, 2: 1000, 3: 1500, 4: 2500, 5: 3000}
        return targets.get(self.current_level, 5000)

    def _get_spawn_cooldown(self):
        cooldowns = {1: 1200, 2: 1200, 3: 1100, 4: 900, 5: 1000}
        cooldown = cooldowns.get(self.current_level, 700)
        
        if self.game.difficulty == "beginner":
            return int(cooldown * 1.3)
        elif self.game.difficulty == "hard":
            return int(cooldown * 0.7)
        return cooldown

    def _get_letter_speed(self):
        speeds = {
            1: (3.0, 6.4),
            2: (3.0, 6.4),
            3: (3.0, 6.4),
            4: (0.5, 1.4),
            5: (3.0, 6.4)
        }
        min_speed, max_speed = speeds.get(self.current_level, (3.2, 4.2))
        
        if self.game.difficulty == "beginner":
            return min_speed * 0.7, max_speed * 0.7
        elif self.game.difficulty == "hard":
            return min_speed * 1.4, max_speed * 1.4
        return min_speed, max_speed

    def _get_max_letters(self):
        limits = {1: 3, 2: 4, 3: 5, 4: 6, 5: 8}
        limit = limits.get(self.current_level, 8)
        
        if self.game.difficulty == "beginner":
            return max(2, limit - 1)
        elif self.game.difficulty == "hard":
            return limit + 2
        return limit

    def _get_char_pool(self):
        if self.current_level == 1:
            return string.ascii_lowercase
        elif self.current_level == 2:
            return string.ascii_uppercase
        elif self.current_level == 3:
            return string.digits
        elif self.current_level == 4:
            return string.ascii_lowercase + string.ascii_uppercase
        else:
            return string.ascii_lowercase + string.ascii_uppercase + string.digits

    # ---- Spawning ----

    def _spawn_letter(self):
        char = random.choice(self._get_char_pool())
        theme = self.get_theme()
        min_speed, max_speed = self._get_letter_speed()
        speed = random.uniform(min_speed, max_speed)
        
        x = random.randint(40, self.game.screen_w - 40)
        
        for _ in range(10):
            if not any(abs(l.x - x) < 36 and l.y < 120 for l in self.falling_letters):
                break
            x = random.randint(40, self.game.screen_w - 40)
            
        self.falling_letters.append(FallingLetter(char, x, 60, speed, theme["accent"]))

    # ---- Gameplay interactions ----

    def handle_correct_keystroke(self, target):
        self.correct_keys += 1
        self.streak += 1
        if self.streak > self.best_streak:
            self.best_streak = self.streak
            
        points = 10
        self.score += points
        self.player.score = self.score
        
        self.player_target_x = target.x
        
        theme = self.get_theme()
        self.lasers.append({
            "start": (self.player.x, self.player.y - 15),
            "end": (target.x, target.y),
            "timer": 8,
            "max_timer": 8,
            "color": theme["accent"]
        })
        
        for _ in range(15):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(2, 5)
            self.explosion_particles.append({
                "x": target.x,
                "y": target.y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": 25,
                "max_life": 25,
                "color": theme["accent"]
            })
            
        if self.streak > 0 and self.streak % 10 == 0:
            bonus = 50
            self.score += bonus
            self.player.score = self.score
            self.game.play_sound("level_up")
            self.streak_popups.append({
                "text": f"STREAK BONUS! +{bonus}",
                "x": target.x,
                "y": target.y - 25,
                "timer": 50,
                "max_timer": 50,
                "color": (255, 215, 0)
            })
            
        self.falling_letters.remove(target)
        self.game.play_sound("shoot")
        
        if self.score >= self._get_level_target_score():
            self.level_completed_stats = True
            self.game.play_sound("level_up")
            self.falling_letters.clear()

    def handle_incorrect_keystroke(self):
        self.errors += 1
        self.streak = 0
        
        # Scale score penalty based on difficulty
        if self.game.difficulty == "beginner":
            penalty = 2
        elif self.game.difficulty == "hard":
            penalty = 10
        else:
            penalty = 5
            
        self.score = max(0, self.score - penalty)
        self.player.score = self.score
        self.game.play_sound("error")

    def handle_miss(self, target):
        self.misses += 1
        self.streak = 0
        
        # Scale score penalty based on difficulty
        if self.game.difficulty == "beginner":
            penalty = 5
        elif self.game.difficulty == "hard":
            penalty = 20
        else:
            penalty = 10
            
        self.score = max(0, self.score - penalty)
        self.player.score = self.score
        
        # Hard difficulty loses 2 lives per miss, others lose 1
        life_loss = 2 if self.game.difficulty == "hard" else 1
        self.lives = max(0, self.lives - life_loss)
        self.player.lives = self.lives
        self.screen_shake = 10
        self.player.lose_life()
        
        self.falling_letters.remove(target)
        self.game.play_sound("hit")
        
        if self.lives <= 0:
            self.game.state = STATE_GAME_OVER
            self.save_session_stats()

    # ---- Event handling ----

    def handle_event(self, event):
        if self.game.state == STATE_PLAYING:
            if self.level_completed_stats:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        self.advance_level()
                    elif event.key == pygame.K_ESCAPE:
                        self.save_session_stats()
                        self.game.state = "menu"
                return

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.game.state = STATE_PAUSED
                    self.pause_start_time = pygame.time.get_ticks()
                else:
                    char = event.unicode
                    if char and char.isprintable() and len(char) == 1:
                        self.total_keys += 1
                        
                        matching = [l for l in self.falling_letters if l.char == char]
                        if matching:
                            target = max(matching, key=lambda l: l.y)
                            self.handle_correct_keystroke(target)
                        else:
                            self.handle_incorrect_keystroke()

        elif self.game.state == STATE_PAUSED:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_r):
                    pause_duration = pygame.time.get_ticks() - self.pause_start_time
                    self.play_start_time += pause_duration
                    self.last_spawn_time += pause_duration
                    self.game.state = STATE_PLAYING
                elif event.key == pygame.K_RETURN:
                    self.start()
                elif event.key == pygame.K_q:
                    self.save_session_stats()
                    self.game.state = "menu"
                elif event.key == pygame.K_x:
                    self.save_session_stats()
                    pygame.quit()
                    sys.exit()

        elif self.game.state in (STATE_GAME_OVER, STATE_VICTORY):
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    self.start()
                elif event.key == pygame.K_ESCAPE:
                    self.save_session_stats()
                    self.game.state = "menu"

    # ---- Update Loop ----

    def update(self):
        if self.game.state == STATE_PLAYING:
            if self.level_completed_stats:
                if self.particle_system:
                    self.particle_system.update()
                return

            if self.level_transition_timer > 0:
                self.level_transition_timer -= 1
                if self.particle_system:
                    self.particle_system.update()
                return

            self.player.update()
            self.player.x += (self.player_target_x - self.player.x) * 0.25
            
            if self.particle_system:
                self.particle_system.update()
            if self.screen_shake > 0:
                self.screen_shake -= 1

            now = pygame.time.get_ticks()
            if len(self.falling_letters) < self._get_max_letters():
                if now - self.last_spawn_time > self._get_spawn_cooldown():
                    self._spawn_letter()
                    self.last_spawn_time = now

            for letter in list(self.falling_letters):
                letter.update()
                if letter.y >= self.player.y - 15:
                    self.handle_miss(letter)

            for laser in self.lasers[:]:
                laser["timer"] -= 1
                if laser["timer"] <= 0:
                    self.lasers.remove(laser)

            for popup in self.streak_popups[:]:
                popup["timer"] -= 1
                popup["y"] -= 0.6
                if popup["timer"] <= 0:
                    self.streak_popups.remove(popup)

            for p in self.explosion_particles[:]:
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["life"] -= 1
                if p["life"] <= 0:
                    self.explosion_particles.remove(p)

    # ---- Drawing Loop ----

    def draw(self, screen):
        theme = self.get_theme()
        
        if self.particle_system:
            self.particle_system.screen_w = self.game.screen_w
            self.particle_system.screen_h = self.game.screen_h

        if self.game.state == STATE_PLAYING:
            if self.level_completed_stats:
                self._draw_stats_overlay(screen, theme)
            else:
                self._draw_playing(screen, theme)
        elif self.game.state == STATE_PAUSED:
            self._draw_playing(screen, theme)
            self._draw_pause_menu(screen, theme)
        elif self.game.state == STATE_GAME_OVER:
            self._draw_game_over(screen, theme)
        elif self.game.state == STATE_VICTORY:
            self._draw_victory(screen, theme)

    def _draw_playing(self, screen, theme):
        shake_dx = random.randint(-self.screen_shake, self.screen_shake) if self.screen_shake > 0 else 0
        shake_dy = random.randint(-self.screen_shake, self.screen_shake) if self.screen_shake > 0 else 0

        screen.fill(theme["bg"])

        # Background particles
        if self.particle_system:
            self.particle_system.draw(screen)

        # Transition banner
        if self.level_transition_timer > 0:
            self._draw_level_transition_banner(screen, theme)
            return

        # Grid lines
        grid_color = tuple(max(0, c + 6) for c in theme["bg"])
        for gx in range(0, self.game.screen_w, 80):
            pygame.draw.line(screen, grid_color, (gx + shake_dx, 50), (gx + shake_dx, self.game.screen_h))
        for gy in range(50, self.game.screen_h, 80):
            pygame.draw.line(screen, grid_color, (shake_dx, gy + shake_dy), (self.game.screen_w + shake_dx, gy + shake_dy))

        # Laser beam lines
        for laser in self.lasers:
            alpha = int(255 * (laser["timer"] / laser["max_timer"]))
            width = max(1, int(4 * (laser["timer"] / laser["max_timer"])))
            pygame.draw.line(screen, laser["color"], laser["start"], laser["end"], width=width+2)
            pygame.draw.line(screen, (255, 255, 255), laser["start"], laser["end"], width=max(1, width-1))

        # Explosion particles
        for p in self.explosion_particles:
            ratio = p["life"] / p["max_life"]
            color = tuple(int(c * ratio) for c in p["color"])
            radius = max(1, int(3 * ratio))
            pygame.draw.circle(screen, color, (int(p["x"]), int(p["y"])), radius)

        # Falling letters
        for letter in self.falling_letters:
            letter.draw(screen, self.game.font_sub)

        # Player ship
        self.player.draw(screen, theme)

        # Streak text popups
        for popup in self.streak_popups:
            surf = self.game.font_stats.render(popup["text"], True, popup["color"])
            # Fade out
            alpha = int(255 * (popup["timer"] / popup["max_timer"]))
            surf.set_alpha(alpha)
            screen.blit(surf, (popup["x"] - surf.get_width() // 2, int(popup["y"])))

        # HUD Panel
        hud_rect = pygame.Rect(0, 0, self.game.screen_w, 50)
        pygame.draw.rect(screen, (20, 20, 30), hud_rect)
        pygame.draw.line(screen, theme["accent"], (0, 50), (self.game.screen_w, 50), width=2)

        # HUD stats
        acc = self._calc_accuracy()
        target = self._get_level_target_score()
        parts = [
            (f"SCORE: {self.score} / {target}", COLOR_UI_TEXT),
            (f"HIGH:  {self.game.high_scores['reflex']}", (130, 130, 145)),
            (f"LEVEL {self.current_level}: {theme['name']}", theme["accent"]),
            (f"STREAK: {self.streak}", (255, 235, 59) if self.streak > 0 else (180, 180, 180)),
            (f"ACC: {acc}%", (80, 200, 80)),
        ]
        
        x_offset = 16
        for text, col in parts:
            s = self.game.font_stats.render(text, True, col)
            screen.blit(s, (x_offset, 13))
            x_offset += s.get_width() + 30

        # Lives representation
        hearts_str = "♥ " * self.lives + "♡ " * (self.max_lives - self.lives)
        hs = self.game.font_stats.render(hearts_str, True, (220, 50, 80))
        screen.blit(hs, (self.game.screen_w - hs.get_width() - 16, 13))

    def _draw_level_transition_banner(self, screen, theme):
        overlay = pygame.Surface((self.game.screen_w, self.game.screen_h), pygame.SRCALPHA)
        overlay.fill((*theme["bg"][:3], 210))
        screen.blit(overlay, (0, 0))

        if self.particle_system:
            self.particle_system.draw(screen)

        title = self.game.font_title.render(f"REFLEX LEVEL {self.current_level}", True, theme["accent"])
        subtitle = self.game.font_heading.render(theme["name"], True, theme["enemy"])
        screen.blit(title, (self.game.screen_w // 2 - title.get_width() // 2, self.game.screen_h // 2 - 80))
        screen.blit(subtitle, (self.game.screen_w // 2 - subtitle.get_width() // 2, self.game.screen_h // 2 + 10))

        hint = self.game.font_body.render("Prepare your reflex speed...", True, (160, 160, 160))
        screen.blit(hint, (self.game.screen_w // 2 - hint.get_width() // 2, self.game.screen_h // 2 + 80))

    def _draw_stats_overlay(self, screen, theme):
        # Semi-transparent dark background
        overlay = pygame.Surface((self.game.screen_w, self.game.screen_h), pygame.SRCALPHA)
        overlay.fill((*theme["bg"][:3], 220))
        screen.blit(overlay, (0, 0))
        
        if self.particle_system:
            self.particle_system.draw(screen)

        pw, ph = 540, 320
        px = self.game.screen_w // 2 - pw // 2
        py = self.game.screen_h // 2 - ph // 2
        self.game._draw_panel(pygame.Rect(px, py, pw, ph), bg=(20, 22, 32), border=theme["accent"])

        title = self.game.font_heading.render(f"LEVEL {self.current_level} SECURED", True, theme["accent"])
        screen.blit(title, (self.game.screen_w // 2 - title.get_width() // 2, py + 24))

        acc = self._calc_accuracy()
        stats = [
            (f"Final Score:      {self.score}", theme["accent"]),
            (f"Accuracy:         {acc}%", (80, 200, 80)),
            (f"Best Key Streak:  {self.best_streak}", (255, 215, 0)),
            (f"Key Misses:       {self.misses}", theme["enemy"]),
            (f"Invalid Keys:     {self.errors}", (180, 120, 120)),
        ]
        
        for i, (text, col) in enumerate(stats):
            s = self.game.font_body.render(text, True, col)
            screen.blit(s, (px + 50, py + 84 + i * 36))

        # Call to action
        if (pygame.time.get_ticks() // 600) % 2:
            prompt = self.game.font_sub.render("PRESS ENTER FOR NEXT PROTOCOL", True, theme["accent"])
            screen.blit(prompt, (self.game.screen_w // 2 - prompt.get_width() // 2, py + ph - 64))
        else:
            prompt = self.game.font_sub.render("PRESS ENTER FOR NEXT PROTOCOL", True, (0, 120, 120))
            screen.blit(prompt, (self.game.screen_w // 2 - prompt.get_width() // 2, py + ph - 64))

        esc_hint = self.game.font_stats.render("ESC to Return to Dashboard", True, (120, 120, 120))
        screen.blit(esc_hint, (self.game.screen_w // 2 - esc_hint.get_width() // 2, py + ph - 30))

    def _draw_pause_menu(self, screen, theme):
        overlay = pygame.Surface((self.game.screen_w, self.game.screen_h), pygame.SRCALPHA)
        overlay.fill((10, 10, 15, 180))
        screen.blit(overlay, (0, 0))

        pw, ph = 500, 300
        px = self.game.screen_w // 2 - pw // 2
        py = self.game.screen_h // 2 - ph // 2
        self.game._draw_panel(pygame.Rect(px, py, pw, ph), bg=(20, 20, 30), border=theme["accent"])

        title = self.game.font_heading.render("TRAINING PAUSED", True, theme["accent"])
        screen.blit(title, (self.game.screen_w // 2 - title.get_width() // 2, py + 30))

        options = [
            ("ESC / R — Resume Training", COLOR_TEXT_NORMAL),
            ("ENTER   — Restart Mode", COLOR_TEXT_NORMAL),
            ("Q       — Quit to Main Menu", theme["enemy"]),
            ("X       — Exit Game", (250, 70, 70))
        ]
        for i, (text, col) in enumerate(options):
            surf = self.game.font_body.render(text, True, col)
            screen.blit(surf, (px + 60, py + 100 + i * 40))

    def _draw_game_over(self, screen, theme):
        screen.fill((15, 5, 8))
        if self.particle_system:
            self.particle_system.update()
            self.particle_system.draw(screen)

        title = self.game.font_title.render("REFLEX OVERLOAD", True, (220, 40, 40))
        screen.blit(title, (self.game.screen_w // 2 - title.get_width() // 2, self.game.screen_h // 2 - 200))

        s = self.game.font_sub.render("CRITICAL ACCURACY THRESHOLD BREACHED", True, (160, 60, 60))
        screen.blit(s, (self.game.screen_w // 2 - s.get_width() // 2, self.game.screen_h // 2 - 130))

        pw, ph = 480, 240
        px = self.game.screen_w // 2 - pw // 2
        py = self.game.screen_h // 2 - 60
        self.game._draw_panel(pygame.Rect(px, py, pw, ph))

        acc = self._calc_accuracy()
        stats = [
            (f"Final Score:   {self.score}", theme["accent"]),
            (f"Sector Reached: Level {self.current_level}", theme["enemy"]),
            (f"Key Successes: {self.correct_keys}", COLOR_TEXT_NORMAL),
            (f"Best Streak:   {self.best_streak}", (255, 170, 0)),
            (f"Accuracy:      {acc}%", (80, 200, 80)),
        ]
        for i, (text, col) in enumerate(stats):
            s = self.game.font_body.render(text, True, col)
            screen.blit(s, (px + 40, py + 24 + i * 40))

        if (pygame.time.get_ticks() // 600) % 2:
            ps = self.game.font_heading.render("PRESS ENTER TO RESTART", True, (220, 80, 80))
            screen.blit(ps, (self.game.screen_w // 2 - ps.get_width() // 2, self.game.screen_h // 2 + 210))
        es = self.game.font_body.render("ESC for Main Menu", True, (80, 80, 80))
        screen.blit(es, (self.game.screen_w // 2 - es.get_width() // 2, self.game.screen_h // 2 + 260))

    def _draw_victory(self, screen, theme):
        cyb = LEVEL_THEMES[5]
        screen.fill(cyb["bg"])
        if self.particle_system is None or self.particle_system.theme_type != "cyber":
            self.particle_system = ParticleSystem(self.game.screen_w, self.game.screen_h, "cyber", density=140)
        self.particle_system.update()
        self.particle_system.draw(screen)

        title = self.game.font_title.render("REFLEX MASTERED", True, cyb["accent"])
        screen.blit(title, (self.game.screen_w // 2 - title.get_width() // 2, self.game.screen_h // 2 - 220))
        s = self.game.font_heading.render("ALL KEY PROTOCOLS SYNCHRONIZED PERFECTLY", True, cyb["enemy"])
        screen.blit(s, (self.game.screen_w // 2 - s.get_width() // 2, self.game.screen_h // 2 - 150))

        pw, ph = 520, 260
        px = self.game.screen_w // 2 - pw // 2
        py = self.game.screen_h // 2 - 70
        self.game._draw_panel(pygame.Rect(px, py, pw, ph), bg=(8, 20, 8), border=cyb["accent"])

        acc = self._calc_accuracy()
        stats = [
            (f"Total Score:     {self.score}", cyb["accent"]),
            (f"Accuracy Rating: {acc}%", (80, 200, 80)),
            (f"Peak Key Streak: {self.best_streak}", (255, 215, 0)),
            (f"Misses / Errors: {self.misses} / {self.errors}", cyb["enemy"]),
            (f"High Score:      {self.game.high_scores['reflex']}", COLOR_TEXT_NORMAL),
        ]
        for i, (text, col) in enumerate(stats):
            s = self.game.font_body.render(text, True, col)
            screen.blit(s, (px + 40, py + 24 + i * 42))

        if (pygame.time.get_ticks() // 600) % 2:
            ps = self.game.font_heading.render("PRESS ENTER TO PLAY AGAIN", True, cyb["accent"])
            screen.blit(ps, (self.game.screen_w // 2 - ps.get_width() // 2, self.game.screen_h // 2 + 220))
        es = self.game.font_body.render("ESC for Main Menu", True, (60, 80, 60))
        screen.blit(es, (self.game.screen_w // 2 - es.get_width() // 2, self.game.screen_h // 2 + 270))

    # ---- Statistics helpers ----

    def _calc_accuracy(self):
        if self.total_keys > 0:
            return int((self.correct_keys / self.total_keys) * 100)
        return 100
