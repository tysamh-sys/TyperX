import pygame
import random
import math
import sys

from game.modes.base_mode import BaseMode
from game.settings import (
    COLOR_TEXT_NORMAL, COLOR_UI_TEXT, STATE_PLAYING, STATE_PAUSED,
    STATE_GAME_OVER, STATE_VICTORY, INITIAL_ENEMY_SPEED, SPEED_INCREMENT,
    INITIAL_SPAWN_COOLDOWN, SPAWN_COOLDOWN_DECREMENT, MIN_SPAWN_COOLDOWN,
    WORDS_TO_SUMMON_BOSS, LEVEL_THEMES, MAX_LEVEL
)
from game.player import Player
from game.enemy import Enemy
from game.text_manager import TextManager
from game.particles import ParticleSystem

class SurvivalMode(BaseMode):
    def __init__(self, game):
        super().__init__(game)
        self.player = Player()
        self.enemies = []
        self.active_enemy = None
        self.text_manager = TextManager()
        
        # State tracking
        self.current_level = 1
        self.boss_spawned = False
        self.boss_defeated = False
        self.words_this_level = 0
        self.level_transition_timer = 0
        self.last_spawn_time = 0
        self.play_start_time = 0
        self.pause_start_time = 0
        self.combo_count = 0
        self.boss_flash_timer = 0
        self.screen_shake = 0
        self.particle_system = None
        
        # New systems tracking
        self.session_saved = False
        self.session_max_combo = 0

    def start(self):
        self.session_saved = False
        self.session_max_combo = 0
        
        # Load progress and stats from database if profile is active
        if self.game.active_profile:
            prof_id = self.game.active_profile["id"]
            saved_stats = self.game.db_manager.get_stats(prof_id, self.game.difficulty, "survival")
            if saved_stats:
                self.current_level = saved_stats["current_level"]
                self.game.high_scores["survival"] = saved_stats["highest_score"]
            else:
                self.current_level = 1
            
            # Sync custom text settings from DB
            cust_text = self.game.db_manager.get_custom_text(prof_id)
            if cust_text and cust_text["use_custom"] == 1:
                import json
                try:
                    words = json.loads(cust_text["words_json"])
                    sentences = json.loads(cust_text["sentences_json"])
                    self.text_manager.set_custom_data(words, sentences, True)
                except Exception as e:
                    print(f"Error loading custom text JSON from DB: {e}")
                    self.text_manager.set_custom_data([], [], False)
            else:
                self.text_manager.set_custom_data([], [], False)
        else:
            self.current_level = 1
            self.text_manager.set_custom_data([], [], False)

        self.player.reset()
        self.player.level = self.current_level
        
        # Scale starting lives based on difficulty
        if self.game.difficulty == "beginner":
            self.player.max_lives = 7
        elif self.game.difficulty == "hard":
            self.player.max_lives = 3
        else:
            self.player.max_lives = 5
        self.player.lives = self.player.max_lives
        
        # Update high score tracker in player object
        self.player.high_score = self.game.high_scores["survival"]
        self.player.update_position(self.game.screen_w, self.game.screen_h)
        self.enemies.clear()
        self.active_enemy = None
        
        self.boss_spawned = False
        self.boss_defeated = False
        self.words_this_level = 0
        self.game.state = STATE_PLAYING
        self.play_start_time = pygame.time.get_ticks()
        self.last_spawn_time = self.play_start_time
        self.combo_count = 0
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
                mode="survival",
                level=self.current_level,
                score=self.player.score,
                words=self.player.words_typed,
                correct=self.player.correct_keystrokes,
                total=self.player.total_keystrokes,
                combo=self.session_max_combo,
                elapsed_time=elapsed
            )
            
            # Retrieve updated stats to refresh high scores
            saved_stats = self.game.db_manager.get_stats(
                self.game.active_profile["id"], self.game.difficulty, "survival"
            )
            if saved_stats:
                self.game.high_scores["survival"] = saved_stats["highest_score"]
                self.player.high_score = saved_stats["highest_score"]
                
        self.session_saved = True

    def advance_level(self):
        if self.current_level >= MAX_LEVEL:
            self.game.state = STATE_VICTORY
            self.save_session_stats()
            return
        self.current_level += 1
        self.player.level = self.current_level
        self.boss_spawned = False
        self.boss_defeated = False
        self.words_this_level = 0
        self.enemies.clear()
        self.active_enemy = None
        self.level_transition_timer = 180  # 3 seconds at 60fps
        self._reset_particles()
        self.game.play_sound("level_up")
        
        # Save progress at the beginning of the new level
        self.save_session_stats()
        # Reset session saved flag to allow future saving at game end
        self.session_saved = False

    def _reset_particles(self):
        theme = self.get_theme()
        self.particle_system = ParticleSystem(
            self.game.screen_w, self.game.screen_h, theme["type"], density=100, difficulty=self.game.difficulty
        )

    def get_theme(self, level=None):
        lvl = level if level else self.current_level
        # Modulo wrap levels above 5 so themes recycle beautifully
        level_index = (lvl - 1) % 5 + 1
        base_theme = LEVEL_THEMES.get(level_index, LEVEL_THEMES[1])
        
        # Make a copy and modify colors dynamically based on difficulty
        theme = base_theme.copy()
        if self.game.difficulty == "beginner":
            # Bright and relaxing sky/pastel tones
            theme["bg"] = tuple(min(255, c + 15) for c in theme["bg"])
            theme["bg"] = (theme["bg"][0], theme["bg"][1] + 12, theme["bg"][2] + 25) # Soft tint towards blue
            theme["accent"] = (100, 220, 255) # Soft pastel cyan
            theme["enemy"] = (210, 150, 240)  # Soft pastel violet
        elif self.game.difficulty == "hard":
            # Intense warn colors with deep red/black atmospheres
            theme["bg"] = (max(5, theme["bg"][0] // 2 + 12), max(1, theme["bg"][1] // 4), max(1, theme["bg"][2] // 4))
            theme["accent"] = (255, 64, 64)   # Blood red
            theme["enemy"] = (255, 235, 59)   # Alarm yellow
            
        return theme

    # ---- Spawn Logic ----

    def _get_spawn_cooldown(self):
        cooldown = INITIAL_SPAWN_COOLDOWN - self.words_this_level * SPAWN_COOLDOWN_DECREMENT
        
        # Scale cooldown by difficulty
        if self.game.difficulty == "beginner":
            cooldown = cooldown * 1.3
        elif self.game.difficulty == "hard":
            cooldown = cooldown * 0.7
            
        # Hard cap spawn cooldown
        min_cooldown = MIN_SPAWN_COOLDOWN if self.game.difficulty != "hard" else 800
        return max(min_cooldown, cooldown)

    def _get_enemy_speed(self):
        base = INITIAL_ENEMY_SPEED + (self.current_level - 1) * 0.2
        level_words = self.words_this_level
        speed = min(3.5, base + level_words * SPEED_INCREMENT)
        
        # Scale speed by difficulty
        if self.game.difficulty == "beginner":
            return speed * 0.7
        elif self.game.difficulty == "hard":
            return speed * 1.4
        return speed

    def _spawn_normal_enemy(self):
        word = self.text_manager.get_random_word(level=self.current_level, difficulty=self.game.difficulty)
        theme = self.get_theme()
        speed = self._get_enemy_speed()

        text_w = self.game.font_word.size(word)[0] + 30
        min_x = text_w // 2 + 20
        max_x = self.game.screen_w - text_w // 2 - 20
        x = random.randint(min_x, max(min_x + 1, max_x))
        y = 60

        for _ in range(15):
            if not any(abs(e.x - x) < text_w and abs(e.y - 60) < 50 for e in self.enemies):
                break
            x = random.randint(min_x, max(min_x + 1, max_x))

        self.enemies.append(Enemy(word, x, y, speed, theme, is_boss=False))

    def _spawn_boss(self):
        sentence = self.text_manager.get_boss_sentence(self.current_level)
        theme = self.get_theme()
        boss_speed = max(0.35, self._get_enemy_speed() * 0.28)
        boss = Enemy(sentence, self.game.screen_w // 2, 80, boss_speed, theme, is_boss=True)
        self.enemies.append(boss)
        self.active_enemy = boss
        boss.is_target = True
        self.boss_spawned = True
        self.boss_flash_timer = 120
        self.screen_shake = 20
        self.game.play_sound("level_up")

    # ---- Typing Logic ----

    def handle_keystroke(self, char):
        self.player.total_keystrokes += 1

        if self.active_enemy is None:
            candidates = [e for e in self.enemies if not e.is_boss and e.check_char(char)]
            if candidates:
                target = max(candidates, key=lambda e: e.y)
                self.active_enemy = target
                target.is_target = True
                target.type_char()
                self.player.correct_keystrokes += 1
                self.game.play_sound("shoot")
            else:
                self.game.play_sound("error")
                # Beginner is forgiving: typos don't reset combos!
                if self.game.difficulty != "beginner":
                    self.combo_count = 0
        else:
            if self.active_enemy.check_char(char):
                self.active_enemy.type_char()
                self.player.correct_keystrokes += 1
                self.game.play_sound("shoot")
                if self.active_enemy.is_completed():
                    self._destroy_enemy(self.active_enemy)
            else:
                self.game.play_sound("error")
                # Beginner is forgiving: typos don't reset combos!
                if self.game.difficulty != "beginner":
                    self.combo_count = 0
                # Hard resets active enemy typing progress back to 0 on mistake
                if self.game.difficulty == "hard" and self.active_enemy:
                    self.active_enemy.typed_index = 0

    def _destroy_enemy(self, enemy):
        word_len = len(enemy.word)
        self.player.add_score(word_len)
        self.screen_shake = 6 if enemy.is_boss else 2
        was_boss = enemy.is_boss

        # Combo reward
        self.combo_count += 1
        self.session_max_combo = max(self.session_max_combo, self.combo_count)
        
        # Difficulty scaled healing thresholds
        heal_threshold = 3
        if self.game.difficulty == "beginner":
            heal_threshold = 2
        elif self.game.difficulty == "hard":
            heal_threshold = 5
            
        if self.combo_count > 0 and self.combo_count % heal_threshold == 0:
            if self.player.lives < self.player.max_lives:
                self.player.lives += 1
                self.game.play_sound("level_up")

        if enemy in self.enemies:
            self.enemies.remove(enemy)
        self.active_enemy = None

        if was_boss:
            self.game.play_sound("explosion")
            self.boss_defeated = True
            self.advance_level()
        else:
            self.words_this_level += 1
            self.game.play_sound("explosion")
            if self.words_this_level >= WORDS_TO_SUMMON_BOSS and not self.boss_spawned:
                self.enemies.clear()
                self.active_enemy = None
                self._spawn_boss()

    # ---- Mode interface implementation ----

    def handle_event(self, event):
        if self.game.state == STATE_PLAYING:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.game.state = STATE_PAUSED
                    self.pause_start_time = pygame.time.get_ticks()
                elif event.key == pygame.K_BACKSPACE:
                    if self.active_enemy and not self.active_enemy.is_boss:
                        self.active_enemy.is_target = False
                        self.active_enemy.typed_index = 0
                        self.active_enemy = None
                elif event.key == pygame.K_SPACE:
                    if self.active_enemy and self.active_enemy.is_boss:
                        self.handle_keystroke(" ")
                else:
                    char = event.unicode
                    if char:
                        self.handle_keystroke(char)

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
                    # Save stats and quit to menu
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

    def update(self):
        if self.game.state == STATE_PLAYING:
            if self.level_transition_timer > 0:
                self.level_transition_timer -= 1
                if self.particle_system:
                    self.particle_system.update()
                return

            self.player.update()
            if self.particle_system:
                self.particle_system.update()
            if self.screen_shake > 0:
                self.screen_shake -= 1
            if self.boss_flash_timer > 0:
                self.boss_flash_timer -= 1

            now = pygame.time.get_ticks()

            if not self.boss_spawned:
                if now - self.last_spawn_time > self._get_spawn_cooldown():
                    self._spawn_normal_enemy()
                    self.last_spawn_time = now

            for enemy in list(self.enemies):
                enemy.update()
                if enemy.y >= self.player.y - 20:
                    self.game.play_sound("hit")
                    if enemy.is_boss:
                        self.player.lives = 0
                        self.game.state = STATE_GAME_OVER
                        self.save_session_stats()
                        break
                    else:
                        self.player.lose_life()
                        if self.game.difficulty != "beginner":
                            self.combo_count = 0
                        if enemy == self.active_enemy:
                            self.active_enemy = None
                        if enemy in self.enemies:
                            self.enemies.remove(enemy)
                        if self.player.lives <= 0:
                            self.game.state = STATE_GAME_OVER
                            self.save_session_stats()
                            break

    def draw(self, screen):
        theme = self.get_theme()
        
        # Sync particle system dimensions
        if self.particle_system:
            self.particle_system.screen_w = self.game.screen_w
            self.particle_system.screen_h = self.game.screen_h

        # Render depending on active sub-state
        if self.game.state == STATE_PLAYING:
            self._draw_playing(screen, theme)
        elif self.game.state == STATE_PAUSED:
            self._draw_playing(screen, theme)
            self._draw_pause_menu(screen, theme)
        elif self.game.state == STATE_GAME_OVER:
            self._draw_game_over(screen, theme)
        elif self.game.state == STATE_VICTORY:
            self._draw_victory(screen, theme)

    def _draw_playing(self, screen, theme):
        is_boss_active = self.boss_spawned and not self.boss_defeated and any(e.is_boss for e in self.enemies)
        
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

        # Boss vignette
        if is_boss_active:
            self._draw_boss_vignette(screen, theme)

        # Grid background
        grid_color = tuple(max(0, c + 6) for c in theme["bg"])
        for gx in range(0, self.game.screen_w, 80):
            pygame.draw.line(screen, grid_color, (gx + shake_dx, 50), (gx + shake_dx, self.game.screen_h))
        for gy in range(50, self.game.screen_h, 80):
            pygame.draw.line(screen, grid_color, (shake_dx, gy + shake_dy), (self.game.screen_w + shake_dx, gy + shake_dy))

        # HUD Panel
        hud_rect = pygame.Rect(0, 0, self.game.screen_w, 50)
        pygame.draw.rect(screen, (20, 20, 30), hud_rect)
        pygame.draw.line(screen, theme["accent"], (0, 50), (self.game.screen_w, 50), width=2)

        # Stats
        wpm = self._calc_wpm()
        acc = self._calc_accuracy()
        level_name = theme["name"]
        
        parts = [
            (f"SCORE: {self.player.score}", COLOR_UI_TEXT),
            (f"HIGH:  {self.game.high_scores['survival']}", (130, 130, 145)),
            (f"LEVEL {self.current_level}: {level_name}", theme["accent"]),
            (f"WPM: {wpm}", (255, 160, 30)),
            (f"ACC: {acc}%", (80, 200, 80)),
        ]
        if self.combo_count > 0:
            parts.append((f"COMBO: {self.combo_count}", (255, 235, 59)))
            
        x_offset = 16
        for text, col in parts:
            s = self.game.font_stats.render(text, True, col)
            screen.blit(s, (x_offset, 13))
            x_offset += s.get_width() + 30

        # Lives
        hearts_str = "♥ " * self.player.lives + "♡ " * (self.player.max_lives - self.player.lives)
        hs = self.game.font_stats.render(hearts_str, True, (220, 50, 80))
        screen.blit(hs, (self.game.screen_w - hs.get_width() - 16, 13))

        # Boss alert
        if is_boss_active and self.boss_flash_timer > 0:
            self._draw_boss_alert_banner(screen, theme)

        # Enemies
        for enemy in self.enemies:
            enemy.draw(screen, self.game.font_word, self.game.font_boss)

        # Player
        self.player.draw(screen, theme)

    def _draw_boss_vignette(self, screen, theme):
        v = pygame.Surface((self.game.screen_w, self.game.screen_h), pygame.SRCALPHA)
        r, g, b = theme.get("enemy", (200, 50, 50))
        v.fill((r // 5, g // 5, b // 5, 60))
        for edge in range(50):
            alpha = int(100 * (1 - edge / 50))
            pygame.draw.rect(v, (r // 3, g // 4, b // 4, alpha),
                             pygame.Rect(edge, edge, self.game.screen_w - edge*2, self.game.screen_h - edge*2),
                             width=1)
        screen.blit(v, (0, 0))

    def _draw_boss_alert_banner(self, screen, theme):
        pct = self.boss_flash_timer / 120
        alpha = int(255 * ((pct - 0.5) * 2)) if pct > 0.5 else int(255 * pct * 2)
        s = pygame.Surface((self.game.screen_w, 80), pygame.SRCALPHA)
        s.fill((*theme.get("enemy", (200, 50, 50))[:3], alpha // 2))
        screen.blit(s, (0, self.game.screen_h // 2 - 40))
        boss_text = self.game.font_heading.render("⚠  BOSS BATTLE  ⚠", True, theme["accent"])
        screen.blit(boss_text, (self.game.screen_w // 2 - boss_text.get_width() // 2, self.game.screen_h // 2 - 20))

    def _draw_level_transition_banner(self, screen, theme):
        overlay = pygame.Surface((self.game.screen_w, self.game.screen_h), pygame.SRCALPHA)
        overlay.fill((*theme["bg"][:3], 210))
        screen.blit(overlay, (0, 0))

        if self.particle_system:
            self.particle_system.draw(screen)

        title = self.game.font_title.render(f"LEVEL {self.current_level}", True, theme["accent"])
        subtitle = self.game.font_heading.render(theme["name"], True, theme["enemy"])
        screen.blit(title, (self.game.screen_w // 2 - title.get_width() // 2, self.game.screen_h // 2 - 80))
        screen.blit(subtitle, (self.game.screen_w // 2 - subtitle.get_width() // 2, self.game.screen_h // 2 + 10))

        hint = self.game.font_body.render("Prepare yourself...", True, (160, 160, 160))
        screen.blit(hint, (self.game.screen_w // 2 - hint.get_width() // 2, self.game.screen_h // 2 + 80))

    def _draw_pause_menu(self, screen, theme):
        overlay = pygame.Surface((self.game.screen_w, self.game.screen_h), pygame.SRCALPHA)
        overlay.fill((10, 10, 15, 180))
        screen.blit(overlay, (0, 0))

        pw, ph = 500, 300
        px = self.game.screen_w // 2 - pw // 2
        py = self.game.screen_h // 2 - ph // 2
        self.game._draw_panel(pygame.Rect(px, py, pw, ph), bg=(20, 20, 30), border=theme["accent"])

        title = self.game.font_heading.render("GAME PAUSED", True, theme["accent"])
        screen.blit(title, (self.game.screen_w // 2 - title.get_width() // 2, py + 30))

        options = [
            ("ESC / R — Resume Game", COLOR_TEXT_NORMAL),
            ("ENTER   — Restart Game", COLOR_TEXT_NORMAL),
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

        title = self.game.font_title.render("SYSTEM FAILURE", True, (220, 40, 40))
        screen.blit(title, (self.game.screen_w // 2 - title.get_width() // 2, self.game.screen_h // 2 - 200))

        s = self.game.font_sub.render("GRID PROTECTION COLLAPSED", True, (160, 60, 60))
        screen.blit(s, (self.game.screen_w // 2 - s.get_width() // 2, self.game.screen_h // 2 - 130))

        pw, ph = 480, 240
        px = self.game.screen_w // 2 - pw // 2
        py = self.game.screen_h // 2 - 60
        self.game._draw_panel(pygame.Rect(px, py, pw, ph))

        wpm = self._calc_wpm()
        acc = self._calc_accuracy()
        stats = [
            (f"Final Score:  {self.player.score}", theme["accent"]),
            (f"Highest Level: {self.current_level}", theme["enemy"]),
            (f"Words Typed:  {self.player.words_typed}", COLOR_TEXT_NORMAL),
            (f"Typing Speed: {wpm} WPM", (255, 170, 0)),
            (f"Accuracy:     {acc}%", (80, 200, 80)),
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

        title = self.game.font_title.render("GRID SECURED", True, cyb["accent"])
        screen.blit(title, (self.game.screen_w // 2 - title.get_width() // 2, self.game.screen_h // 2 - 220))
        s = self.game.font_heading.render("ALL THREATS NEUTRALIZED — MISSION COMPLETE", True, cyb["enemy"])
        screen.blit(s, (self.game.screen_w // 2 - s.get_width() // 2, self.game.screen_h // 2 - 150))

        pw, ph = 520, 260
        px = self.game.screen_w // 2 - pw // 2
        py = self.game.screen_h // 2 - 70
        self.game._draw_panel(pygame.Rect(px, py, pw, ph), bg=(8, 20, 8), border=cyb["accent"])

        wpm = self._calc_wpm()
        acc = self._calc_accuracy()
        stats = [
            (f"Total Score:    {self.player.score}", cyb["accent"]),
            (f"Words Destroyed: {self.player.words_typed}", cyb["enemy"]),
            (f"Peak Speed:     {wpm} WPM", (255, 170, 0)),
            (f"Accuracy:       {acc}%", (80, 200, 80)),
            (f"High Score:     {self.game.high_scores['survival']}", COLOR_TEXT_NORMAL),
        ]
        for i, (text, col) in enumerate(stats):
            s = self.game.font_body.render(text, True, col)
            screen.blit(s, (px + 40, py + 24 + i * 42))

        if (pygame.time.get_ticks() // 600) % 2:
            ps = self.game.font_heading.render("PRESS ENTER TO PLAY AGAIN", True, cyb["accent"])
            screen.blit(ps, (self.game.screen_w // 2 - ps.get_width() // 2, self.game.screen_h // 2 + 220))
        es = self.game.font_body.render("ESC for Main Menu", True, (60, 80, 60))
        screen.blit(es, (self.game.screen_w // 2 - es.get_width() // 2, self.game.screen_h // 2 + 270))

    # ---- Stat Calculations ----

    def _calc_wpm(self):
        elapsed_ms = pygame.time.get_ticks() - self.play_start_time
        mins = elapsed_ms / 60000.0
        if mins > 0.02:
            return int((self.player.correct_keystrokes / 5.0) / mins)
        return 0

    def _calc_accuracy(self):
        if self.player.total_keystrokes > 0:
            return int((self.player.correct_keystrokes / self.player.total_keystrokes) * 100)
        return 100
