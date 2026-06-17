import pygame
import math
import sys
import random
import json

from game.modes.base_mode import BaseMode
from game.settings import (
    STATE_PLAYING, STATE_PAUSED, STATE_GAME_OVER,
    COLOR_TEXT_NORMAL, COLOR_UI_TEXT,
    LEVEL_THEMES
)
from game.particles import ParticleSystem
from game.player import Player


# ── Precision Word / Phrase Banks ──────────────────────────────────────────

PRECISION_LEVELS = {
    1: {  # Very short, common words
        "label": "INITIALIZING",
        "words": ["go", "hi", "do", "ok", "be", "up", "at", "in", "on", "so",
                  "cat", "dog", "run", "sit", "key", "tap", "hit", "map", "pen",
                  "sun", "cup", "top", "new", "old", "big", "red", "try", "yes"],
        "phrases": []
    },
    2: {  # Short common words, 4-6 chars
        "label": "CALIBRATING",
        "words": ["type", "code", "fast", "word", "hand", "mind", "data", "link",
                  "scan", "sync", "grid", "mode", "bolt", "test", "peak", "flow",
                  "logic", "press", "speed", "track", "pulse", "sharp", "solid"],
        "phrases": []
    },
    3: {  # Medium words, 5-8 chars
        "label": "ENGAGED",
        "words": ["typing", "cursor", "signal", "matrix", "system", "cipher",
                  "vector", "target", "combat", "reflex", "streak", "output",
                  "control", "process", "execute", "mission", "command", "program"],
        "phrases": []
    },
    4: {  # Longer words + technical vocabulary, 7-12 chars
        "label": "INTENSIFIED",
        "words": ["keyboard", "accuracy", "sequence", "protocol", "override",
                  "fragment", "terminal", "compiler", "function", "latency",
                  "firmware", "bytecode", "feedback", "database", "algorithm",
                  "benchmark", "interface", "detection", "generator", "structure"],
        "phrases": ["type it fast", "stay sharp now", "keep your focus",
                    "hit every key", "no mistakes here"]
    },
    5: {  # Phrases and long technical words
        "label": "CRITICAL",
        "words": ["cryptography", "architecture", "initialization", "miscellaneous",
                  "authentication", "vulnerability", "polymorphism", "concatenation",
                  "electromagnetic", "implementation", "reconfiguration", "serialization"],
        "phrases": ["precision is everything", "fingers on the grid", "lock and type the target",
                    "one wrong key ends the run", "stay calm and type true",
                    "control your breathing now", "zero errors tolerated here",
                    "each keystroke must be perfect"]
    },
    6: {  # Full sentences, maximum challenge
        "label": "MAXIMUM THREAT",
        "words": [],
        "phrases": ["the quick brown fox jumps over the lazy dog",
                    "all systems are fully operational at this time",
                    "initiate emergency lockdown protocol seven immediately",
                    "execute precision targeting sequence on primary grid node",
                    "override the encryption matrix to access the secure datastream",
                    "type each character without hesitation or deviation from target"]
    }
}

# Time limit per challenge (milliseconds) — decreases with level
PRECISION_TIME_LIMITS = {
    1: 8000,
    2: 9000,
    3: 10000,
    4: 12000,
    5: 14000,
    6: 18000
}


class PrecisionMode(BaseMode):
    """
    Precision Typing Mode
    - One challenge word/phrase displayed at a time
    - Player must type it exactly — any wrong key = instant GAME OVER
    - No health system; instant fail on first mistake
    - Also fails if the timer runs out
    - Score = words completed × speed bonus + survival time bonus
    - Progression: starts simple, grows into long phrases and sentences
    """

    def __init__(self, game):
        super().__init__(game)

        # Challenge tracking
        self.current_target = ""       # The string to type
        self.typed_index = 0           # How many chars correctly typed so far
        self.challenge_count = 0       # How many challenges survived this run
        self.precision_level = 1       # Internal precision difficulty tier (1-6)

        # Timing
        self.play_start_time = 0       # Time when the run began
        self.challenge_start_time = 0  # Time when current challenge began
        self.time_limit_ms = 8000      # ms to complete the current challenge

        # Stats for DB saving
        self.session_score = 0
        self.total_chars_typed = 0
        self.session_saved = False
        self.run_duration_s = 0.0      # Total seconds for this completed run

        # Fastest completion tracking (best record in ms for a challenge at max prec_level)
        self.session_fastest_ms = 999999

        # Visuals
        self.particle_system = None
        self.fail_flash_timer = 0      # Brief red flash on instant fail
        self.success_flash_timer = 0   # Brief green flash on success

        # State machine — handled internally
        # Shares STATE_PLAYING / STATE_GAME_OVER with the main game state

        # Custom text pool loaded from profile
        self._custom_words = []
        self._custom_phrases = []
        self._use_custom = False

    # ──────────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────────

    def start(self):
        self.session_saved = False
        self.challenge_count = 0
        self.precision_level = 1
        self.session_score = 0
        self.total_chars_typed = 0
        self.session_fastest_ms = 999999
        self.fail_flash_timer = 0
        self.success_flash_timer = 0

        # Load custom text if profile active
        self._load_custom_text()

        self.play_start_time = pygame.time.get_ticks()
        self._reset_particles()
        self._next_challenge()

        self.game.state = STATE_PLAYING

    def _load_custom_text(self):
        self._custom_words = []
        self._custom_phrases = []
        self._use_custom = False
        if self.game.active_profile:
            prof_id = self.game.active_profile["id"]
            cust = self.game.db_manager.get_custom_text(prof_id)
            if cust and cust["use_custom"] == 1:
                try:
                    self._custom_words = json.loads(cust["words_json"])
                    self._custom_phrases = json.loads(cust["sentences_json"])
                    self._use_custom = True
                except Exception:
                    pass

    def _reset_particles(self):
        # Use cyber theme for precision mode — it fits the zero-error atmosphere
        self.particle_system = ParticleSystem(
            self.game.screen_w, self.game.screen_h, "cyber", density=90,
            difficulty=self.game.difficulty
        )

    # ──────────────────────────────────────────────────────────────────────
    # Challenge generation
    # ──────────────────────────────────────────────────────────────────────

    def _build_pool(self):
        """Build the word / phrase pool for the current precision_level."""
        lvl = min(self.precision_level, 6)
        data = PRECISION_LEVELS[lvl]

        # Apply difficulty modifier: on easy, cap at earlier levels
        diff = self.game.difficulty
        if diff == "beginner":
            lvl = min(lvl, 4)
            data = PRECISION_LEVELS[lvl]
        elif diff == "hard" and self.precision_level < 3:
            lvl = max(2, self.precision_level)
            data = PRECISION_LEVELS[lvl]

        words = list(data["words"])
        phrases = list(data["phrases"])

        # Blend custom text into pool if enabled
        if self._use_custom:
            if self._custom_words:
                # Filter custom words by approximate length range
                if lvl <= 2:
                    cw = [w for w in self._custom_words if len(w) <= 6]
                elif lvl <= 4:
                    cw = [w for w in self._custom_words if 4 <= len(w) <= 12]
                else:
                    cw = [w for w in self._custom_words if len(w) >= 8]
                words += cw[:20]  # cap added words

            if self._custom_phrases and lvl >= 4:
                phrases += self._custom_phrases[:10]

        return words, phrases

    def _pick_next_target(self):
        lvl = min(self.precision_level, 6)
        words, phrases = self._build_pool()

        # At level 5-6 mix phrases more heavily; earlier levels stay words-only
        if lvl >= 6:
            pool = phrases if phrases else words
        elif lvl == 5:
            pool = (phrases * 2 + words) if phrases else words
        elif lvl == 4:
            pool = (phrases + words * 3) if phrases else words
        else:
            pool = words

        if not pool:
            pool = words if words else ["precision"]

        return random.choice(pool)

    def _next_challenge(self):
        self.current_target = self._pick_next_target()
        self.typed_index = 0
        self.challenge_start_time = pygame.time.get_ticks()

        # Difficulty modifies time limit
        base_ms = PRECISION_TIME_LIMITS.get(min(self.precision_level, 6), 12000)
        diff = self.game.difficulty
        if diff == "beginner":
            self.time_limit_ms = int(base_ms * 1.5)
        elif diff == "hard":
            self.time_limit_ms = int(base_ms * 0.7)
        else:
            self.time_limit_ms = base_ms

        # Update the precision tier every N challenges
        tier_thresholds = {1: 3, 2: 6, 3: 10, 4: 15, 5: 21, 6: 999}
        for tier in sorted(tier_thresholds.keys()):
            if self.challenge_count < tier_thresholds[tier]:
                self.precision_level = tier
                break
        else:
            self.precision_level = 6

    # ──────────────────────────────────────────────────────────────────────
    # Scoring
    # ──────────────────────────────────────────────────────────────────────

    def _award_challenge_score(self, completion_ms):
        """Score the just-completed challenge."""
        word_len = len(self.current_target)
        # Base score: 10 pts per character
        base = word_len * 10

        # Speed bonus: faster = more points (up to 2× if completed in < 20% of time limit)
        ratio = completion_ms / max(self.time_limit_ms, 1)
        speed_mult = max(1.0, 2.5 - ratio * 2)

        # Combo bonus grows with challenge_count
        combo_mult = 1.0 + self.challenge_count * 0.05

        points = int(base * speed_mult * combo_mult)
        self.session_score += points
        return points

    # ──────────────────────────────────────────────────────────────────────
    # DB Persistence
    # ──────────────────────────────────────────────────────────────────────

    def save_session_stats(self):
        if self.session_saved:
            return
        if self.game.active_profile:
            elapsed = (pygame.time.get_ticks() - self.play_start_time) / 1000.0
            elapsed = max(elapsed, 0.0)
            self.game.db_manager.save_game_session(
                profile_id=self.game.active_profile["id"],
                difficulty=self.game.difficulty,
                mode="precision",
                level=self.precision_level,
                score=self.session_score,
                words=self.challenge_count,
                correct=self.total_chars_typed,
                total=self.total_chars_typed,  # precision mode: correct == total at time of save
                combo=self.challenge_count,    # challenge_count as combo equivalent
                elapsed_time=elapsed
            )
            # Update precision high score cache
            saved = self.game.db_manager.get_stats(
                self.game.active_profile["id"], self.game.difficulty, "precision"
            )
            if saved:
                self.game.high_scores["precision"] = saved["highest_score"]

        self.session_saved = True

    # ──────────────────────────────────────────────────────────────────────
    # Event Handling
    # ──────────────────────────────────────────────────────────────────────

    def handle_event(self, event):
        if self.game.state == STATE_PLAYING:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.save_session_stats()
                    self.game.state = STATE_GAME_OVER
                elif event.key == pygame.K_SPACE:
                    # Space is a valid character in multi-word phrases
                    self._handle_char(" ")
                else:
                    char = event.unicode
                    if char and char.isprintable():
                        self._handle_char(char)

        elif self.game.state == STATE_GAME_OVER:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    self.start()
                elif event.key == pygame.K_ESCAPE:
                    self.save_session_stats()
                    self.game.state = "menu"

    def _handle_char(self, char):
        """Process a single typed character. Instant fail on any mismatch."""
        expected = self.current_target[self.typed_index]

        if char == expected:
            self.typed_index += 1
            self.total_chars_typed += 1
            self.game.play_sound("shoot")

            if self.typed_index >= len(self.current_target):
                # Challenge complete!
                completion_ms = pygame.time.get_ticks() - self.challenge_start_time
                self.session_fastest_ms = min(self.session_fastest_ms, completion_ms)
                self._award_challenge_score(completion_ms)
                self.challenge_count += 1
                self.success_flash_timer = 25
                self.game.play_sound("explosion")
                self._next_challenge()
        else:
            # Wrong key — instant game over
            self.fail_flash_timer = 45
            self.game.play_sound("error")
            self.run_duration_s = (pygame.time.get_ticks() - self.play_start_time) / 1000.0
            self.save_session_stats()
            self.game.state = STATE_GAME_OVER

    # ──────────────────────────────────────────────────────────────────────
    # Update
    # ──────────────────────────────────────────────────────────────────────

    def update(self):
        if self.game.state == STATE_PLAYING:
            if self.particle_system:
                self.particle_system.screen_w = self.game.screen_w
                self.particle_system.screen_h = self.game.screen_h
                self.particle_system.update()

            if self.fail_flash_timer > 0:
                self.fail_flash_timer -= 1
            if self.success_flash_timer > 0:
                self.success_flash_timer -= 1

            # Check time expiry
            elapsed_challenge = pygame.time.get_ticks() - self.challenge_start_time
            if elapsed_challenge >= self.time_limit_ms:
                # Time ran out — treat as instant fail
                self.fail_flash_timer = 45
                self.game.play_sound("error")
                self.run_duration_s = (pygame.time.get_ticks() - self.play_start_time) / 1000.0
                self.save_session_stats()
                self.game.state = STATE_GAME_OVER

        elif self.game.state == STATE_GAME_OVER:
            if self.particle_system:
                self.particle_system.update()

    # ──────────────────────────────────────────────────────────────────────
    # Drawing
    # ──────────────────────────────────────────────────────────────────────

    def draw(self, screen):
        if self.game.state == STATE_PLAYING:
            self._draw_playing(screen)
        elif self.game.state == STATE_GAME_OVER:
            self._draw_game_over(screen)

    def _draw_playing(self, screen):
        now = pygame.time.get_ticks()
        sw, sh = self.game.screen_w, self.game.screen_h

        # Background
        bg = (4, 4, 6)
        if self.success_flash_timer > 0:
            p = self.success_flash_timer / 25
            bg = (int(4 + 30 * p), int(4 + 60 * p), int(6 + 20 * p))
        elif self.fail_flash_timer > 0:
            p = self.fail_flash_timer / 45
            bg = (int(4 + 140 * p), 4, 6)

        screen.fill(bg)
        if self.particle_system:
            self.particle_system.draw(screen)

        # Subtle grid
        grid_col = (10, 20, 12)
        for gx in range(0, sw, 80):
            pygame.draw.line(screen, grid_col, (gx, 50), (gx, sh))
        for gy in range(50, sh, 80):
            pygame.draw.line(screen, grid_col, (0, gy), (sw, gy))

        # ── HUD ──────────────────────────────────────────────────
        hud_rect = pygame.Rect(0, 0, sw, 50)
        pygame.draw.rect(screen, (16, 20, 16), hud_rect)
        pygame.draw.line(screen, (50, 255, 50), (0, 50), (sw, 50), width=2)

        # HUD text parts
        run_elapsed_s = (now - self.play_start_time) / 1000.0
        hs_val = self.game.high_scores.get("precision", 0)

        hud_parts = [
            (f"SCORE: {self.session_score}", (255, 255, 255)),
            (f"BEST: {hs_val}", (130, 130, 145)),
            (f"CHALLENGES: {self.challenge_count}", (50, 255, 50)),
            (f"TIER {self.precision_level}: {PRECISION_LEVELS[min(self.precision_level, 6)]['label']}", (0, 200, 100)),
            (f"TIME: {run_elapsed_s:.1f}s", (255, 180, 30)),
        ]
        x_off = 16
        for text, col in hud_parts:
            s = self.game.font_stats.render(text, True, col)
            screen.blit(s, (x_off, 13))
            x_off += s.get_width() + 30

        # Difficulty badge (top right)
        diff_col = {"beginner": (100, 220, 255), "medium": (255, 235, 59), "hard": (255, 60, 60)}
        dc = diff_col.get(self.game.difficulty, (200, 200, 200))
        d_surf = self.game.font_stats.render(f"[{self.game.difficulty.upper()}]", True, dc)
        screen.blit(d_surf, (sw - d_surf.get_width() - 16, 13))

        # ── Timer Bar ────────────────────────────────────────────
        elapsed_challenge = now - self.challenge_start_time
        ratio = max(0.0, 1.0 - elapsed_challenge / self.time_limit_ms)

        bar_x, bar_y = sw // 2 - 320, sh // 2 - 160
        bar_w, bar_h = 640, 12
        bar_rect = pygame.Rect(bar_x, bar_y, bar_w, bar_h)
        pygame.draw.rect(screen, (30, 40, 30), bar_rect, border_radius=6)

        filled_w = int(bar_w * ratio)
        if filled_w > 0:
            if ratio > 0.5:
                bar_color = (50, 255, 80)
            elif ratio > 0.25:
                bar_color = (255, 200, 50)
            else:
                pulse = int(abs(math.sin(now * 0.01)) * 80)
                bar_color = (220 + pulse // 3, 40 - pulse // 4, 40 - pulse // 4)
            pygame.draw.rect(screen, bar_color, pygame.Rect(bar_x, bar_y, filled_w, bar_h), border_radius=6)

        pygame.draw.rect(screen, (60, 80, 60), bar_rect, width=1, border_radius=6)

        remaining_s = max(0.0, (self.time_limit_ms - elapsed_challenge) / 1000.0)
        time_surf = self.game.font_stats.render(f"{remaining_s:.1f}s", True, (100, 200, 100) if ratio > 0.3 else (255, 80, 80))
        screen.blit(time_surf, (bar_x + bar_w + 12, bar_y - 2))

        # ── Target Word / Phrase ──────────────────────────────────
        # Determine appropriate font size based on target length
        if len(self.current_target) <= 8:
            word_font = self.game.font_title
        elif len(self.current_target) <= 18:
            word_font = pygame.font.SysFont("Consolas", 42, bold=True)
        else:
            word_font = pygame.font.SysFont("Consolas", 28, bold=True)

        target = self.current_target
        typed_part = target[:self.typed_index]
        untyped_part = target[self.typed_index:]
        cursor_char = target[self.typed_index] if self.typed_index < len(target) else ""

        # Calculate text layout for centering
        typed_surf = word_font.render(typed_part, True, (0, 229, 255))   # Cyan = typed OK
        cursor_surf = word_font.render(cursor_char, True, (255, 255, 255)) if cursor_char else None
        untyped_rest = untyped_part[1:] if len(untyped_part) > 1 else ""
        untyped_surf = word_font.render(untyped_rest, True, (100, 100, 110))  # Dim grey

        total_w = typed_surf.get_width()
        if cursor_surf:
            total_w += cursor_surf.get_width()
        total_w += word_font.size(untyped_rest)[0]

        word_y = sh // 2 - 40
        draw_x = sw // 2 - total_w // 2

        # Draw typed (cyan)
        screen.blit(typed_surf, (draw_x, word_y))
        draw_x += typed_surf.get_width()

        # Draw cursor character with blinking underline highlight
        if cursor_surf:
            blink = (now // 350) % 2 == 0
            cur_w = cursor_surf.get_width()
            cur_h = cursor_surf.get_height()

            # Highlight box behind cursor char
            if blink:
                chl_surf = pygame.Surface((cur_w, cur_h), pygame.SRCALPHA)
                chl_surf.fill((50, 255, 80, 60))
                screen.blit(chl_surf, (draw_x, word_y))

            screen.blit(cursor_surf, (draw_x, word_y))

            # Blinking underline
            if blink:
                pygame.draw.rect(screen, (50, 255, 80),
                                 pygame.Rect(draw_x, word_y + cur_h - 3, cur_w, 3))
            draw_x += cur_w

        # Draw remaining untyped chars (dim)
        if untyped_rest:
            untyped_draw = word_font.render(untyped_rest, True, (90, 90, 100))
            screen.blit(untyped_draw, (draw_x, word_y))

        # ── "Type this" label ──────────────────────────────────
        label_surf = self.game.font_stats.render("TYPE THE TARGET:", True, (70, 120, 70))
        screen.blit(label_surf, (sw // 2 - label_surf.get_width() // 2, word_y - 48))

        # ── Input Echo Box ────────────────────────────────────────
        echo_y = sh // 2 + 60
        echo_rect = pygame.Rect(sw // 2 - 300, echo_y, 600, 42)
        pygame.draw.rect(screen, (14, 22, 14), echo_rect, border_radius=8)
        pygame.draw.rect(screen, (40, 80, 40), echo_rect, width=1, border_radius=8)

        echo_text = typed_part + ("|" if (now // 400) % 2 == 0 else "")
        echo_surf = self.game.font_sub.render(echo_text, True, (0, 229, 255))
        screen.blit(echo_surf, (sw // 2 - echo_surf.get_width() // 2, echo_y + 8))

        # ── Challenge Progress Dots ───────────────────────────────
        dot_y = sh // 2 + 130
        max_dots = min(self.challenge_count + 5, 30)
        dot_spacing = 22
        total_dots_w = max_dots * dot_spacing
        dot_start_x = sw // 2 - total_dots_w // 2

        for di in range(max_dots):
            dot_x = dot_start_x + di * dot_spacing
            if di < self.challenge_count:
                pygame.draw.circle(screen, (50, 220, 80), (dot_x, dot_y), 7)
            elif di == self.challenge_count:
                # Current: pulsing white
                pulse_r = 5 + int(abs(math.sin(now * 0.005)) * 3)
                pygame.draw.circle(screen, (200, 200, 255), (dot_x, dot_y), pulse_r, width=2)
            else:
                pygame.draw.circle(screen, (30, 50, 35), (dot_x, dot_y), 5)

        if max_dots < self.challenge_count:
            more_surf = self.game.font_stats.render(f"+{self.challenge_count - max_dots}", True, (80, 200, 80))
            screen.blit(more_surf, (dot_start_x + total_dots_w + 8, dot_y - 8))

        # ── Bottom Hint ───────────────────────────────────────────
        hint_surf = self.game.font_stats.render("ONE MISTAKE = INSTANT FAILURE  |  ESC = Abandon Run", True, (50, 70, 55))
        screen.blit(hint_surf, (sw // 2 - hint_surf.get_width() // 2, sh - 35))

    def _draw_game_over(self, screen):
        sw, sh = self.game.screen_w, self.game.screen_h

        screen.fill((10, 4, 4))
        if self.particle_system:
            self.particle_system.draw(screen)

        # Title
        title = self.game.font_title.render("RUN TERMINATED", True, (220, 40, 40))
        screen.blit(title, (sw // 2 - title.get_width() // 2, sh // 2 - 240))

        sub = self.game.font_sub.render("PRECISION PROTOCOL FAILED", True, (160, 50, 50))
        screen.blit(sub, (sw // 2 - sub.get_width() // 2, sh // 2 - 170))

        # Stats panel
        pw, ph = 500, 300
        px = sw // 2 - pw // 2
        py = sh // 2 - 80
        pygame.draw.rect(screen, (20, 16, 16), pygame.Rect(px, py, pw, ph), border_radius=12)
        pygame.draw.rect(screen, (100, 30, 30), pygame.Rect(px, py, pw, ph), width=2, border_radius=12)

        run_s = self.run_duration_s if self.run_duration_s > 0 else (pygame.time.get_ticks() - self.play_start_time) / 1000.0
        hs_val = self.game.high_scores.get("precision", 0)
        new_best = self.session_score > 0 and self.session_score >= hs_val

        stats = [
            (f"Challenges Survived: {self.challenge_count}", (0, 200, 120)),
            (f"Final Score:         {self.session_score}", (255, 235, 59) if new_best else (220, 220, 225)),
            (f"Personal Best:       {hs_val}", (0, 229, 255)),
            (f"Survival Time:       {run_s:.2f}s", (255, 180, 30)),
            (f"Tier Reached:        {PRECISION_LEVELS[min(self.precision_level, 6)]['label']}", (180, 100, 255)),
        ]

        if new_best:
            best_surf = self.game.font_sub.render("★ NEW HIGH SCORE ★", True, (255, 215, 0))
            screen.blit(best_surf, (sw // 2 - best_surf.get_width() // 2, py + 14))
            start_idx = 50
        else:
            start_idx = 24

        for i, (text, col) in enumerate(stats):
            s = self.game.font_body.render(text, True, col)
            screen.blit(s, (px + 40, py + start_idx + i * 42))

        # Restart / menu prompts
        blink = (pygame.time.get_ticks() // 550) % 2
        if blink:
            rs = self.game.font_heading.render("PRESS ENTER TO RETRY", True, (220, 80, 80))
            screen.blit(rs, (sw // 2 - rs.get_width() // 2, sh // 2 + 250))
        ms = self.game.font_body.render("ESC for Main Menu", True, (80, 50, 50))
        screen.blit(ms, (sw // 2 - ms.get_width() // 2, sh // 2 + 300))

    # ──────────────────────────────────────────────────────────────────────
    # Utilities
    # ──────────────────────────────────────────────────────────────────────

    def _calc_wpm(self):
        """Estimate WPM from chars typed / 5 over run time."""
        elapsed_ms = pygame.time.get_ticks() - self.play_start_time
        mins = elapsed_ms / 60000.0
        if mins > 0.05:
            return int((self.total_chars_typed / 5.0) / mins)
        return 0
