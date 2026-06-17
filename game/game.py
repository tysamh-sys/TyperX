import pygame
import sys
import random
import math
import os

from game.settings import (
    FPS, COLOR_TEXT_NORMAL, COLOR_UI_TEXT, COLOR_BORDER,
    STATE_MENU, STATE_PLAYING, STATE_PAUSED, STATE_GAME_OVER, STATE_VICTORY,
    STATE_PROFILES, STATE_CUSTOM_TEXT, STATE_STATS,
    LEVEL_THEMES
)
from game.particles import ParticleSystem
from game.modes.survival_mode import SurvivalMode
from game.modes.reflex_mode import ReflexMode
from game.modes.precision_mode import PrecisionMode
from game.database import DatabaseManager
from game.text_manager import TextManager

class Game:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()

        # Window configuration
        os.environ['SDL_VIDEO_CENTERED'] = '1'
        info = pygame.display.Info()
        
        self.fullscreen = False
        self.window_w = int(info.current_w * 0.9)
        self.window_h = int(info.current_h * 0.85)
        self.screen_w = self.window_w
        self.screen_h = self.window_h
        
        self.screen = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.RESIZABLE)
        pygame.display.set_caption("CYBER TYPER — GRID TRAINING COMPLEX")
        self.clock = pygame.time.Clock()

        # Try to maximize the window programmatically on Windows
        try:
            import ctypes
            hwnd = pygame.display.get_wm_info().get("window")
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 3)  # 3 is SW_MAXIMIZE
        except Exception as e:
            print(f"Could not maximize window on startup: {e}")

        # SQLite Database System
        self.db_manager = DatabaseManager()
        self.active_profile = self.db_manager.get_active_profile()
        if not self.active_profile:
            self.active_profile = self.db_manager.get_profiles()[0]
        
        # Difficulty configuration (beginner, medium, hard)
        self.difficulty = self.active_profile.get("last_difficulty", "medium")

        # Shared high scores
        self.high_scores = {
            "survival": 0,
            "reflex": 0,
            "precision": 0
        }
        self.sync_high_scores()

        # Fonts
        self.font_title  = self.load_font(60, bold=True)
        self.font_heading= self.load_font(36, bold=True)
        self.font_sub    = self.load_font(26, bold=True)
        self.font_body   = self.load_font(20)
        self.font_stats  = self.load_font(18, bold=True)
        self.font_word   = self.load_font(20)
        self.font_boss   = self.load_font(26, bold=True)

        # Sounds
        self.sounds = {}
        self._load_sounds()

        # Game Modes
        self.modes = {
            "survival": SurvivalMode(self),
            "reflex": ReflexMode(self),
            "precision": PrecisionMode(self)
        }
        self.active_mode = None
        self.state = STATE_MENU

        # Menu dashboard configuration
        self.menu_selected_idx = 0
        self.menu_modes = [
            {
                "id": "survival",
                "title": "TYPING SURVIVAL",
                "desc": "Defend the grid from falling meteors, ice crystals, magma embers, arcane runes, and blocks. Type full words & sentences to eliminate threats. Face 5 intense sectors and defeat core bosses.",
                "accent": (180, 80, 220), # Cosmic Violet / Purple
                "icon": "ship"
            },
            {
                "id": "reflex",
                "title": "REFLEX TRAINER",
                "desc": "Improve key recognition speed and raw precision. Instantly destroy fast-falling individual letters, numbers, and punctuation. Maintain streaks for massive score multipliers.",
                "accent": (0, 229, 255), # Matrix Cyber Cyan
                "icon": "target"
            },
            {
                "id": "precision",
                "title": "PRECISION TYPING",
                "desc": "Zero tolerance. Type exact words and phrases perfectly — one wrong keystroke ends the run instantly. Survive as long as possible through escalating tiers of difficulty.",
                "accent": (50, 255, 80),  # Neon Green
                "icon": "crosshair"
            }
        ]

        # Background particle system for the menu
        self.menu_particles = ParticleSystem(self.screen_w, self.screen_h, "cyber", density=80)
        
        # Sub-screen UI parameters
        self.profile_list_idx = 0
        self.profile_creation_active = False
        self.profile_deletion_confirm = False
        self.profile_error_msg = ""
        self.profile_error_timer = 0
        self.new_profile_name = ""
        
        self.stats_reset_confirm = False
        
        # Hovered config indexes for main menu dashboard buttons
        self.hovered_config_idx = -1

    # ---- Init Helpers ----

    def load_font(self, size, bold=False):
        try:
            return pygame.font.SysFont("Consolas", size, bold=bold)
        except Exception:
            return pygame.font.Font(None, size)

    def _load_sounds(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ["shoot", "explosion", "hit", "level_up", "error"]:
            path = os.path.join(base, "assets", "sounds", f"{name}.wav")
            self.sounds[name] = pygame.mixer.Sound(path) if os.path.exists(path) else None

    def play_sound(self, name):
        s = self.sounds.get(name)
        if s:
            s.play()

    def sync_high_scores(self):
        if self.active_profile:
            prof_id = self.active_profile["id"]
            
            stats_surv = self.db_manager.get_stats(prof_id, self.difficulty, "survival")
            self.high_scores["survival"] = stats_surv["highest_score"] if stats_surv else 0
            
            stats_refl = self.db_manager.get_stats(prof_id, self.difficulty, "reflex")
            self.high_scores["reflex"] = stats_refl["highest_score"] if stats_refl else 0

            stats_prec = self.db_manager.get_stats(prof_id, self.difficulty, "precision")
            self.high_scores["precision"] = stats_prec["highest_score"] if stats_prec else 0

    # ---- Screen Scaling and Fullscreen ----

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.window_w = self.screen_w
            self.window_h = self.screen_h
            
            info = pygame.display.Info()
            self.screen_w = info.current_w
            self.screen_h = info.current_h
            self.screen = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.FULLSCREEN)
        else:
            self.screen_w = self.window_w
            self.screen_h = self.window_h
            self.screen = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.RESIZABLE)
            try:
                import ctypes
                hwnd = pygame.display.get_wm_info().get("window")
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 1)  # SW_SHOWNORMAL
            except Exception:
                pass

        # Adjust dimensions in active mode
        if self.active_mode:
            self.active_mode.player.update_position(self.screen_w, self.screen_h)
        self.menu_particles.screen_w = self.screen_w
        self.menu_particles.screen_h = self.screen_h

    # ---- Mode Management ----

    def start_mode(self, mode_id):
        self.active_mode = self.modes[mode_id]
        self.active_mode.start()

    # ---- UI Helpers ----

    def _blit_center(self, surf, y):
        self.screen.blit(surf, (self.screen_w // 2 - surf.get_width() // 2, y))

    def _draw_panel(self, rect, bg=(25, 25, 38), border=(60, 60, 80), border_width=2):
        pygame.draw.rect(self.screen, bg, rect, border_radius=12)
        pygame.draw.rect(self.screen, border, rect, width=border_width, border_radius=12)

    def _draw_text_wrap(self, text, x, y, max_w, color, font, max_lines=99):
        """Word-wrap text within max_w pixels, up to max_lines lines."""
        words = text.split(' ')
        lines = []
        current_line = []
        for word in words:
            test_line = ' '.join(current_line + [word])
            if font.size(test_line)[0] < max_w:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        if current_line:
            lines.append(' '.join(current_line))

        line_h = font.size("A")[1] + 4
        for i, line in enumerate(lines[:max_lines]):
            surf = font.render(line, True, color)
            self.screen.blit(surf, (x, y + i * line_h))
        return len(lines)

    def _truncate_text(self, text, font, max_w, ellipsis="..."):
        """Return text truncated with ellipsis if it exceeds max_w pixels."""
        if font.size(text)[0] <= max_w:
            return text
        while text and font.size(text + ellipsis)[0] > max_w:
            text = text[:-1]
        return text + ellipsis

    def _draw_button(self, screen, rect, label, font, hovered,
                     bg_normal=(20, 22, 30), bg_hover=(35, 38, 55),
                     border_normal=(55, 60, 80), border_hover=(0, 229, 255)):
        """Draw a labelled button, auto-truncating text to fit the button width."""
        bg = bg_hover if hovered else bg_normal
        bc = border_hover if hovered else border_normal
        pygame.draw.rect(screen, bg, rect, border_radius=8)
        pygame.draw.rect(screen, bc, rect, width=2, border_radius=8)
        safe_label = self._truncate_text(label, font, rect.width - 12)
        s = font.render(safe_label, True, (255, 255, 255) if hovered else (190, 195, 210))
        screen.blit(s, (rect.centerx - s.get_width() // 2, rect.centery - s.get_height() // 2))

    # ---- Main Game Loop ----

    def run(self):
        while True:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

    def handle_events(self):
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                # Save session progress on close if playing!
                if self.state == STATE_PLAYING and self.active_mode:
                    if hasattr(self.active_mode, "save_session_stats"):
                        self.active_mode.save_session_stats()
                pygame.quit()
                sys.exit()

            elif event.type == pygame.VIDEORESIZE:
                if not self.fullscreen:
                    new_w, new_h = event.w, event.h
                    if new_w != self.screen_w or new_h != self.screen_h:
                        self.screen_w = new_w
                        self.screen_h = new_h
                        self.screen = pygame.display.set_mode((self.screen_w, self.screen_h), pygame.RESIZABLE)
                        self.menu_particles.screen_w = self.screen_w
                        self.menu_particles.screen_h = self.screen_h
                        if self.active_mode:
                            self.active_mode.player.update_position(self.screen_w, self.screen_h)

            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                self.toggle_fullscreen()
            
            else:
                if self.state == STATE_MENU:
                    self.handle_menu_event(event)
                elif self.state == STATE_PROFILES:
                    self.handle_profiles_event(event)
                elif self.state == STATE_CUSTOM_TEXT:
                    self.handle_custom_text_event(event)
                elif self.state == STATE_STATS:
                    self.handle_stats_event(event)
                elif self.active_mode:
                    self.active_mode.handle_event(event)

    def handle_menu_event(self, event):
        start_x = self.screen_w // 2 - 400
        dash_y = self.screen_h // 2 - 170
        btn_w, btn_h = 190, 45
        gap = 13
        
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_LEFT, pygame.K_a):
                self.menu_selected_idx = (self.menu_selected_idx - 1) % len(self.menu_modes)
                self.play_sound("shoot")
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.menu_selected_idx = (self.menu_selected_idx + 1) % len(self.menu_modes)
                self.play_sound("shoot")
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                mode_id = self.menu_modes[self.menu_selected_idx]["id"]
                self.start_mode(mode_id)
            elif event.key == pygame.K_p:
                self.state = STATE_PROFILES
                self.play_sound("shoot")
                # Pre-highlight active profile in list
                profiles = self.db_manager.get_profiles()
                for idx, p in enumerate(profiles):
                    if p["id"] == self.active_profile["id"]:
                        self.profile_list_idx = idx
            elif event.key == pygame.K_d:
                # Toggle difficulty
                self.play_sound("shoot")
                if self.difficulty == "beginner":
                    self.difficulty = "medium"
                elif self.difficulty == "medium":
                    self.difficulty = "hard"
                else:
                    self.difficulty = "beginner"
                if self.active_profile:
                    self.db_manager.set_last_difficulty(self.active_profile["id"], self.difficulty)
                self.sync_high_scores()
            elif event.key == pygame.K_c:
                self.state = STATE_CUSTOM_TEXT
                self.play_sound("shoot")
            elif event.key == pygame.K_s:
                self.state = STATE_STATS
                self.play_sound("shoot")
            elif event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()

        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            
            # Check dashboard configuration buttons
            self.hovered_config_idx = -1
            for idx in range(4):
                bx = start_x + idx * (btn_w + gap)
                rect = pygame.Rect(bx, dash_y, btn_w, btn_h)
                if rect.collidepoint(mx, my):
                    self.hovered_config_idx = idx
            
            # Mode cards bounding boxes
            card_w, card_h = 260, 360
            card_gap = 24
            num_cards = len(self.menu_modes)
            total_w = card_w * num_cards + card_gap * (num_cards - 1)
            card_start_x = self.screen_w // 2 - total_w // 2
            card_y = self.screen_h // 2 - 90

            for idx in range(num_cards):
                card_x = card_start_x + idx * (card_w + card_gap)
                rect = pygame.Rect(card_x, card_y, card_w, card_h)
                if rect.collidepoint(mx, my) and self.menu_selected_idx != idx:
                    self.menu_selected_idx = idx
                    self.play_sound("shoot")

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1: # Left click
                mx, my = event.pos
                
                # Check dashboard buttons
                for idx in range(4):
                    bx = start_x + idx * (btn_w + gap)
                    rect = pygame.Rect(bx, dash_y, btn_w, btn_h)
                    if rect.collidepoint(mx, my):
                        self.play_sound("shoot")
                        if idx == 0:
                            self.state = STATE_PROFILES
                            profiles = self.db_manager.get_profiles()
                            for p_idx, p in enumerate(profiles):
                                if p["id"] == self.active_profile["id"]:
                                    self.profile_list_idx = p_idx
                        elif idx == 1:
                            if self.difficulty == "beginner":
                                self.difficulty = "medium"
                            elif self.difficulty == "medium":
                                self.difficulty = "hard"
                            else:
                                self.difficulty = "beginner"
                            if self.active_profile:
                                self.db_manager.set_last_difficulty(self.active_profile["id"], self.difficulty)
                            self.sync_high_scores()
                        elif idx == 2:
                            self.state = STATE_CUSTOM_TEXT
                        elif idx == 3:
                            self.state = STATE_STATS
                        return
                
                # Check mode cards
                card_w, card_h = 260, 360
                card_gap = 24
                num_cards = len(self.menu_modes)
                total_w = card_w * num_cards + card_gap * (num_cards - 1)
                card_start_x = self.screen_w // 2 - total_w // 2
                card_y = self.screen_h // 2 - 90

                for idx in range(num_cards):
                    card_x = card_start_x + idx * (card_w + card_gap)
                    rect = pygame.Rect(card_x, card_y, card_w, card_h)
                    if rect.collidepoint(mx, my):
                        self.menu_selected_idx = idx
                        mode_id = self.menu_modes[idx]["id"]
                        self.start_mode(mode_id)

    # ---- Profile Manager Event Handler ----

    def handle_profiles_event(self, event):
        profiles = self.db_manager.get_profiles()
        
        if self.profile_creation_active:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.profile_creation_active = False
                    self.new_profile_name = ""
                    self.play_sound("error")
                elif event.key == pygame.K_RETURN:
                    # Submit profile creation
                    success, res = self.db_manager.create_profile(self.new_profile_name)
                    if success:
                        self.play_sound("level_up")
                        self.active_profile = self.db_manager.get_active_profile()
                        self.difficulty = self.active_profile["last_difficulty"]
                        self.sync_high_scores()
                        self.profile_creation_active = False
                        self.new_profile_name = ""
                        self.state = STATE_MENU
                    else:
                        self.play_sound("error")
                        self.profile_error_msg = res
                        self.profile_error_timer = 120 # 2 seconds at 60 FPS
                elif event.key == pygame.K_BACKSPACE:
                    self.new_profile_name = self.new_profile_name[:-1]
                else:
                    # Max 12 characters, alphanumeric and spaces only
                    char = event.unicode
                    if len(self.new_profile_name) < 12 and (char.isalnum() or event.key == pygame.K_SPACE):
                        if char:
                            self.new_profile_name += char
            return

        if self.profile_deletion_confirm:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_y:
                    # Confirm delete
                    target = profiles[self.profile_list_idx]
                    self.db_manager.delete_profile(target["id"])
                    self.play_sound("explosion")
                    self.active_profile = self.db_manager.get_active_profile()
                    self.difficulty = self.active_profile["last_difficulty"]
                    self.sync_high_scores()
                    self.profile_deletion_confirm = False
                    self.profile_list_idx = 0
                elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                    self.profile_deletion_confirm = False
                    self.play_sound("error")
            return

        # Normal list navigation
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = STATE_MENU
                self.play_sound("shoot")
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.profile_list_idx = (self.profile_list_idx - 1) % len(profiles)
                self.play_sound("shoot")
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.profile_list_idx = (self.profile_list_idx + 1) % len(profiles)
                self.play_sound("shoot")
            elif event.key == pygame.K_RETURN:
                # Select highlighted profile
                self.play_sound("level_up")
                target = profiles[self.profile_list_idx]
                self.db_manager.select_profile(target["id"])
                self.active_profile = self.db_manager.get_active_profile()
                self.difficulty = self.active_profile["last_difficulty"]
                self.sync_high_scores()
                self.state = STATE_MENU
            elif event.key == pygame.K_n:
                self.profile_creation_active = True
                self.profile_error_timer = 0
                self.play_sound("shoot")
            elif event.key == pygame.K_DELETE:
                if len(profiles) > 1:
                    self.profile_deletion_confirm = True
                    self.play_sound("shoot")
                else:
                    self.play_sound("error")

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mx, my = event.pos
                px = self.screen_w // 2 - 300
                py = self.screen_h // 2 - 230
                
                # Check clicks on profiles rows
                for idx, p in enumerate(profiles):
                    row_y = py + 90 + idx * 45
                    rect = pygame.Rect(px + 40, row_y - 5, 520, 40)
                    if rect.collidepoint(mx, my):
                        self.profile_list_idx = idx
                        self.play_sound("shoot")
                
                # Check bottom buttons
                if pygame.Rect(px + 40, py + 380, 160, 40).collidepoint(mx, my):
                    self.profile_creation_active = True
                    self.profile_error_timer = 0
                    self.play_sound("shoot")
                elif pygame.Rect(px + 220, py + 380, 160, 40).collidepoint(mx, my):
                    if len(profiles) > 1:
                        self.profile_deletion_confirm = True
                        self.play_sound("shoot")
                    else:
                        self.play_sound("error")
                elif pygame.Rect(px + 400, py + 380, 160, 40).collidepoint(mx, my):
                    self.play_sound("level_up")
                    target = profiles[self.profile_list_idx]
                    self.db_manager.select_profile(target["id"])
                    self.active_profile = self.db_manager.get_active_profile()
                    self.difficulty = self.active_profile["last_difficulty"]
                    self.sync_high_scores()
                    self.state = STATE_MENU
                elif pygame.Rect(px + 540, py + 20, 40, 40).collidepoint(mx, my):
                    self.state = STATE_MENU
                    self.play_sound("shoot")

    # ---- Custom Text Screen Event Handler ----

    def handle_custom_text_event(self, event):
        px = self.screen_w // 2 - 350
        py = self.screen_h // 2 - 250
        
        # Action bounds
        toggle_rect = pygame.Rect(px + 40, py + 350, 200, 40)
        paste_rect = pygame.Rect(px + 260, py + 350, 200, 40)
        load_rect = pygame.Rect(px + 480, py + 350, 180, 40)
        clear_rect = pygame.Rect(px + 150, py + 410, 180, 40)
        back_rect = pygame.Rect(px + 370, py + 410, 180, 40)
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = STATE_MENU
                self.play_sound("shoot")
            elif event.key == pygame.K_t:
                self.play_sound("shoot")
                self.toggle_custom_text_use()
            elif event.key == pygame.K_v:
                self.paste_custom_clipboard()
            elif event.key == pygame.K_l:
                self.load_custom_file()
            elif event.key == pygame.K_x:
                self.clear_custom_text()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mx, my = event.pos
                if toggle_rect.collidepoint(mx, my):
                    self.play_sound("shoot")
                    self.toggle_custom_text_use()
                elif paste_rect.collidepoint(mx, my):
                    self.paste_custom_clipboard()
                elif load_rect.collidepoint(mx, my):
                    self.load_custom_file()
                elif clear_rect.collidepoint(mx, my):
                    self.clear_custom_text()
                elif back_rect.collidepoint(mx, my):
                    self.state = STATE_MENU
                    self.play_sound("shoot")

    def toggle_custom_text_use(self):
        if self.active_profile:
            cust = self.db_manager.get_custom_text(self.active_profile["id"])
            current = cust["use_custom"] == 1 if cust else False
            self.db_manager.set_use_custom_text(self.active_profile["id"], not current)

    def save_custom_text_data(self, text):
        if self.active_profile:
            words, sentences = TextManager.parse_text(text)
            self.db_manager.save_custom_text(
                profile_id=self.active_profile["id"],
                raw_text=text,
                words=words,
                sentences=sentences,
                use_custom=1
            )

    def paste_custom_clipboard(self):
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            text = root.clipboard_get()
            root.destroy()
            
            if text and text.strip():
                self.save_custom_text_data(text)
                self.play_sound("level_up")
            else:
                self.play_sound("error")
        except Exception as e:
            print(f"Error pasting from clipboard: {e}")
            self.play_sound("error")

    def load_custom_file(self):
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            file_path = filedialog.askopenfilename(
                title="Select Training Text File",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
            )
            root.destroy()
            
            if file_path:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                if text and text.strip():
                    self.save_custom_text_data(text)
                    self.play_sound("level_up")
                else:
                    self.play_sound("error")
        except Exception as e:
            print(f"Error loading custom text file: {e}")

    def clear_custom_text(self):
        if self.active_profile:
            self.db_manager.save_custom_text(
                profile_id=self.active_profile["id"],
                raw_text="",
                words=[],
                sentences=[],
                use_custom=0
            )
            self.play_sound("explosion")

    # ---- Statistics Screen Event Handler ----

    def handle_stats_event(self, event):
        px = self.screen_w // 2 - 400
        py = self.screen_h // 2 - 260
        
        reset_rect = pygame.Rect(px + 180, py + 450, 200, 45)
        back_rect = pygame.Rect(px + 420, py + 450, 200, 45)
        
        if self.stats_reset_confirm:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_y:
                    if self.active_profile:
                        self.db_manager.reset_profile_stats(self.active_profile["id"])
                        self.play_sound("explosion")
                        self.sync_high_scores()
                    self.stats_reset_confirm = False
                elif event.key in (pygame.K_n, pygame.K_ESCAPE):
                    self.stats_reset_confirm = False
                    self.play_sound("error")
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.state = STATE_MENU
                self.play_sound("shoot")
            elif event.key == pygame.K_r:
                self.stats_reset_confirm = True
                self.play_sound("shoot")

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                mx, my = event.pos
                if reset_rect.collidepoint(mx, my):
                    self.stats_reset_confirm = True
                    self.play_sound("shoot")
                elif back_rect.collidepoint(mx, my):
                    self.state = STATE_MENU
                    self.play_sound("shoot")

    # ---- Screen Drawing Methods ----

    def update(self):
        if self.state in (STATE_MENU, STATE_PROFILES, STATE_CUSTOM_TEXT, STATE_STATS):
            self.menu_particles.update()
        elif self.active_mode:
            self.active_mode.update()

    def draw(self):
        if self.state == STATE_MENU:
            self.draw_menu()
        elif self.state == STATE_PROFILES:
            self.draw_profiles_screen()
        elif self.state == STATE_CUSTOM_TEXT:
            self.draw_custom_text_screen()
        elif self.state == STATE_STATS:
            self.draw_stats_screen()
        elif self.active_mode:
            self.active_mode.draw(self.screen)
        pygame.display.flip()

    def draw_menu(self):
        theme = LEVEL_THEMES[5]
        sw, sh = self.screen_w, self.screen_h
        self.screen.fill(theme["bg"])
        self.menu_particles.draw(self.screen)

        # ── Title ─────────────────────────────────────────────────────────
        title_y = max(20, sh // 2 - 290)
        t_shadow = self.font_title.render("NEURAL TYPING COMPLEX", True, (10, 40, 20))
        t_main   = self.font_title.render("NEURAL TYPING COMPLEX", True, theme["accent"])
        self._blit_center(t_shadow, title_y + 4)
        self._blit_center(t_main,   title_y)
        sub_surf = self.font_sub.render("SELECT COGNITIVE TRAINING PROTOCOL", True, (180, 180, 195))
        self._blit_center(sub_surf, title_y + 68)

        # ── Dashboard button row ───────────────────────────────────────────
        # 4 equal buttons filling ~820px centred on screen (capped to sw-40)
        db_total_w = min(820, sw - 40)
        btn_gap    = 10
        btn_w      = (db_total_w - btn_gap * 3) // 4
        btn_h      = 40
        dash_y     = title_y + 118
        db_start_x = sw // 2 - db_total_w // 2

        is_custom = False
        if self.active_profile:
            cust = self.db_manager.get_custom_text(self.active_profile["id"])
            if cust and cust["use_custom"] == 1:
                is_custom = True
        custom_status = "ON" if is_custom else "OFF"

        # Truncate long profile names so the label fits the button
        max_name_chars = max(4, (btn_w - 60) // 9)   # rough char budget
        profile_name = self.active_profile["name"]
        if len(profile_name) > max_name_chars:
            profile_name = profile_name[:max_name_chars - 1] + "…"

        btn_data = [
            (f"PROFILE: {profile_name}", 0),
            (f"DIFFICULTY: {self.difficulty.upper()}", 1),
            (f"CUSTOM TEXT: {custom_status}", 2),
            ("STATISTICS", 3)
        ]

        mx, my = pygame.mouse.get_pos()
        for label, idx in btn_data:
            bx   = db_start_x + idx * (btn_w + btn_gap)
            rect = pygame.Rect(bx, dash_y, btn_w, btn_h)
            hov  = (self.hovered_config_idx == idx)
            bg   = (30, 30, 45) if hov else (18, 18, 26)
            bc   = theme["accent"] if hov else (50, 52, 70)
            self._draw_panel(rect, bg=bg, border=bc, border_width=2 if hov else 1)
            safe_lbl = self._truncate_text(label, self.font_stats, btn_w - 16)
            ls = self.font_stats.render(safe_lbl, True, (255, 255, 255) if hov else (175, 178, 200))
            self.screen.blit(ls, (rect.centerx - ls.get_width() // 2,
                                  rect.centery - ls.get_height() // 2))

        # ── Mode cards (3 × responsive width) ─────────────────────────────
        num_cards  = len(self.menu_modes)
        card_gap   = 20
        # Max total cards width = sw - 80; each card equal share
        max_total  = min(sw - 80, 860)
        card_w     = (max_total - card_gap * (num_cards - 1)) // num_cards
        card_h     = 340
        card_y     = dash_y + btn_h + 20
        card_start = sw // 2 - (card_w * num_cards + card_gap * (num_cards - 1)) // 2

        # Description area: from y=160 to y=card_h-40  → available height
        desc_top    = 160
        desc_bottom = card_h - 45
        desc_h      = desc_bottom - desc_top
        line_h      = self.font_stats.size("A")[1] + 4
        max_desc_lines = max(1, desc_h // line_h)

        for idx, mode in enumerate(self.menu_modes):
            card_x   = card_start + idx * (card_w + card_gap)
            rect     = pygame.Rect(card_x, card_y, card_w, card_h)
            selected = (self.menu_selected_idx == idx)
            accent   = mode["accent"]

            if selected:
                self._draw_panel(rect, bg=(20, 20, 30), border=accent, border_width=4)
                glow = pygame.Surface((card_w - 8, card_h - 8), pygame.SRCALPHA)
                pygame.draw.rect(glow, (*accent, 18), (0, 0, card_w - 8, card_h - 8), border_radius=12)
                self.screen.blit(glow, (card_x + 4, card_y + 4))
            else:
                self._draw_panel(rect, bg=(14, 14, 20), border=(42, 44, 60), border_width=1)

            # Title — clipped to card width
            title_col  = (255, 255, 255) if selected else (155, 158, 170)
            title_lbl  = self._truncate_text(mode["title"], self.font_sub, card_w - 20)
            title_surf = self.font_sub.render(title_lbl, True, title_col)
            self.screen.blit(title_surf, (card_x + card_w // 2 - title_surf.get_width() // 2,
                                          card_y + 14))

            # Icon area (centred, y=50→140)
            icon_cx = card_x + card_w // 2
            icon_cy = card_y + 97

            if mode["icon"] == "ship":
                pulse  = math.sin(pygame.time.get_ticks() * 0.005) * 4 if selected else 0
                cy_off = icon_cy + pulse
                pts    = [(icon_cx, cy_off-22), (icon_cx-24, cy_off+16),
                          (icon_cx-8,  cy_off+8), (icon_cx, cy_off+13),
                          (icon_cx+8,  cy_off+8), (icon_cx+24, cy_off+16)]
                pygame.draw.polygon(self.screen, accent, pts)
                pygame.draw.polygon(self.screen, (255,255,255), pts, width=1)
                if selected and (pygame.time.get_ticks()//100)%2:
                    flame = [(icon_cx-5, cy_off+13),(icon_cx, cy_off+24),(icon_cx+5, cy_off+13)]
                    pygame.draw.polygon(self.screen, (255,100,0), flame)

            elif mode["icon"] == "target":
                pulse   = math.sin(pygame.time.get_ticks() * 0.007) * 3 if selected else 0
                r_outer = int(26 + pulse)
                pygame.draw.circle(self.screen, accent, (icon_cx, icon_cy), r_outer, width=2)
                pygame.draw.circle(self.screen, accent, (icon_cx, icon_cy), 11, width=1)
                pygame.draw.circle(self.screen, (255,255,255), (icon_cx, icon_cy), 4)
                pygame.draw.line(self.screen, accent,
                                 (icon_cx - r_outer - 5, icon_cy), (icon_cx + r_outer + 5, icon_cy), 1)
                pygame.draw.line(self.screen, accent,
                                 (icon_cx, icon_cy - r_outer - 5), (icon_cx, icon_cy + r_outer + 5), 1)

            elif mode["icon"] == "crosshair":
                pulse = math.sin(pygame.time.get_ticks() * 0.006) * 3 if selected else 0
                r     = int(24 + pulse)
                pygame.draw.circle(self.screen, accent, (icon_cx, icon_cy), r, width=2)
                pygame.draw.circle(self.screen, (255,255,255), (icon_cx, icon_cy), 3)
                g = 7
                pygame.draw.line(self.screen, accent, (icon_cx-r-4, icon_cy), (icon_cx-g, icon_cy), 2)
                pygame.draw.line(self.screen, accent, (icon_cx+g, icon_cy), (icon_cx+r+4, icon_cy), 2)
                pygame.draw.line(self.screen, accent, (icon_cx, icon_cy-r-4), (icon_cx, icon_cy-g), 2)
                pygame.draw.line(self.screen, accent, (icon_cx, icon_cy+g), (icon_cx, icon_cy+r+4), 2)
                for adeg in [0, 90, 180, 270]:
                    arad = math.radians(adeg + (pygame.time.get_ticks()*0.02 if selected else 0))
                    pygame.draw.circle(self.screen, accent,
                                       (int(icon_cx+(r-5)*math.cos(arad)),
                                        int(icon_cy+(r-5)*math.sin(arad))), 2)

            # Description — strictly bounded, limited lines
            desc_col = (205, 208, 218) if selected else (130, 132, 142)
            self._draw_text_wrap(mode["desc"],
                                 card_x + 14, card_y + desc_top,
                                 card_w - 28, desc_col,
                                 self.font_stats, max_lines=max_desc_lines)

            # Personal best — pinned to card bottom
            hs_val  = self.high_scores.get(mode["id"], 0)
            hs_surf = self.font_stats.render(f"BEST: {hs_val}",
                                              True, accent if selected else (90, 93, 108))
            self.screen.blit(hs_surf,
                             (card_x + card_w//2 - hs_surf.get_width()//2,
                              card_y + card_h - 30))

        # ── Bottom bar ────────────────────────────────────────────────────
        bar_y   = card_y + card_h + 16
        bar_y   = min(bar_y, sh - 60)    # never go off screen
        blink   = (pygame.time.get_ticks() // 600) % 2
        lc      = theme["accent"] if blink else (0, 145, 76)
        launch  = self.font_sub.render("PRESS ENTER OR CLICK TO LAUNCH PROTOCOL", True, lc)
        self._blit_center(launch, bar_y)
        hint    = self.font_stats.render(
            "P Profile  |  D Difficulty  |  C Custom Text  |  S Stats  |  ESC Quit",
            True, (100, 103, 118))
        self._blit_center(hint, bar_y + 34)

    # ---- User Profiles Dashboard Screen Draw ----

    def draw_profiles_screen(self):
        sw, sh = self.screen_w, self.screen_h
        self.screen.fill((10, 15, 12))
        self.menu_particles.draw(self.screen)

        # Panel — responsive: up to 660px wide, fits screen
        pw = min(660, sw - 60)
        ph = min(500, sh - 80)
        px = sw // 2 - pw // 2
        py = sh // 2 - ph // 2
        self._draw_panel(pygame.Rect(px, py, pw, ph), bg=(15, 22, 18),
                         border=(0, 200, 100), border_width=3)

        # Title (truncated to panel)
        title_lbl  = self._truncate_text("USER PROFILES ARCHIVE", self.font_heading, pw - 80)
        title_surf = self.font_heading.render(title_lbl, True, (0, 255, 120))
        self.screen.blit(title_surf, (px + 20, py + 22))

        # Close button — always inside panel
        close_rect = pygame.Rect(px + pw - 50, py + 16, 36, 36)
        pygame.draw.rect(self.screen, (28, 38, 32), close_rect, border_radius=6)
        pygame.draw.rect(self.screen, (0, 200, 100), close_rect, width=1, border_radius=6)
        xs = self.font_stats.render("X", True, (0, 200, 100))
        self.screen.blit(xs, (close_rect.centerx - xs.get_width()//2,
                               close_rect.centery - xs.get_height()//2))

        profiles = self.db_manager.get_profiles()

        # List area: from y=72 to y=ph-80 (leaves room for buttons)
        list_top    = py + 72
        list_bottom = py + ph - 88
        row_h       = 42
        inner_w     = pw - 40   # usable row width
        # Columns: name (40%), active tag (26%), words (rest)
        col_active  = px + 20 + int(inner_w * 0.42)
        col_words   = px + 20 + int(inner_w * 0.70)
        max_rows    = max(1, (list_bottom - list_top) // row_h)
        visible     = profiles[:max_rows]

        for idx, p in enumerate(visible):
            row_y    = list_top + idx * row_h
            row_rect = pygame.Rect(px + 20, row_y, inner_w, row_h - 4)
            highlighted = (self.profile_list_idx == idx)
            is_active   = (p["id"] == self.active_profile["id"])

            rb = (30, 50, 40) if highlighted else (18, 25, 20)
            rc = (0, 255, 120) if highlighted else (38, 55, 46)
            pygame.draw.rect(self.screen, rb, row_rect, border_radius=6)
            pygame.draw.rect(self.screen, rc, row_rect, width=1, border_radius=6)

            # Cursor arrow
            name_x = px + 36
            if highlighted:
                arr = self.font_stats.render(">", True, (0, 255, 120))
                self.screen.blit(arr, (px + 24, row_y + (row_h-4)//2 - arr.get_height()//2))
                name_x = px + 44

            # Name — truncated to available width before active column
            max_name_w = col_active - name_x - 8
            name_lbl   = self._truncate_text(p["name"], self.font_body, max_name_w)
            name_surf  = self.font_body.render(name_lbl, True,
                                               (255,255,255) if highlighted else (200,215,205))
            self.screen.blit(name_surf, (name_x, row_y + (row_h-4)//2 - name_surf.get_height()//2))

            # Active badge
            if is_active:
                act = self.font_stats.render("[ ACTIVE ]", True, (0, 229, 255))
                self.screen.blit(act, (col_active, row_y + (row_h-4)//2 - act.get_height()//2))

            # Word count
            stats       = self.db_manager.get_all_stats_for_profile(p["id"])
            total_words = sum(s["total_words"] for s in stats)
            wds = self.font_stats.render(f"W: {total_words}", True, (110, 135, 120))
            self.screen.blit(wds, (col_words, row_y + (row_h-4)//2 - wds.get_height()//2))

        # Bottom buttons — 3 equal-width, inside panel
        btn_y   = py + ph - 74
        btn_gap = 10
        btn_w   = (inner_w - btn_gap * 2) // 3
        btn_h   = 38
        btn_labels = ["CREATE [N]", "DELETE [Del]", "SELECT [Enter]"]
        btn_bgs_n  = [(15,28,20), (22,14,14), (14,20,28)]
        btn_bcs_n  = [(0,140,70), (140,35,35), (0,130,165)]
        btn_bgs_h  = [(28,50,36), (40,20,20), (22,36,50)]
        btn_bcs_h  = [(0,255,120),(255,55,55),(0,200,255)]
        mx, my = pygame.mouse.get_pos()
        for i, lbl in enumerate(btn_labels):
            bx       = px + 20 + i * (btn_w + btn_gap)
            btn_rect = pygame.Rect(bx, btn_y, btn_w, btn_h)
            hov      = btn_rect.collidepoint(mx, my)
            bg = btn_bgs_h[i] if hov else btn_bgs_n[i]
            bc = btn_bcs_h[i] if hov else btn_bcs_n[i]
            pygame.draw.rect(self.screen, bg, btn_rect, border_radius=8)
            pygame.draw.rect(self.screen, bc, btn_rect, width=2, border_radius=8)
            safe_lbl = self._truncate_text(lbl, self.font_stats, btn_w - 12)
            bs = self.font_stats.render(safe_lbl, True,
                                         (255,255,255) if hov else (175,200,185))
            self.screen.blit(bs, (btn_rect.centerx - bs.get_width()//2,
                                   btn_rect.centery - bs.get_height()//2))

        # Key hint below buttons
        hint = self.font_stats.render("↑↓ Navigate   Enter Select   Del Delete",
                                       True, (70, 95, 80))
        self.screen.blit(hint, (px + 20, py + ph - 30))

        # ── Profile creation modal ──
        if self.profile_creation_active:
            dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 160))
            self.screen.blit(dim, (0, 0))
            m_w, m_h = min(480, sw - 40), 188
            m_x = sw // 2 - m_w // 2
            m_y = sh // 2 - m_h // 2
            self._draw_panel(pygame.Rect(m_x, m_y, m_w, m_h), bg=(12,18,15),
                             border=(0,229,255), border_width=3)
            lbl = self.font_body.render("NEW PROFILE NAME:", True, (0,229,255))
            self.screen.blit(lbl, (m_x + 24, m_y + 22))
            inp_rect = pygame.Rect(m_x + 24, m_y + 54, m_w - 48, 40)
            pygame.draw.rect(self.screen, (18,28,22), inp_rect, border_radius=6)
            pygame.draw.rect(self.screen, (48,96,76), inp_rect, width=1, border_radius=6)
            cursor_c = "|" if (pygame.time.get_ticks() // 500) % 2 else ""
            inp_surf = self.font_heading.render(self.new_profile_name + cursor_c, True, (255,255,255))
            # Clip input text to field width
            inp_clip = pygame.Rect(inp_rect.x+6, inp_rect.y+4, inp_rect.width-12, inp_rect.height-8)
            self.screen.set_clip(inp_clip)
            self.screen.blit(inp_surf, (inp_rect.x + 8, inp_rect.y + 6))
            self.screen.set_clip(None)
            if self.profile_error_timer > 0:
                self.profile_error_timer -= 1
                err = self.font_stats.render(self.profile_error_msg, True, (245,65,65))
                self.screen.blit(err, (m_x + 24, m_y + 104))
            else:
                hint2 = self.font_stats.render("Enter = Confirm   ESC = Cancel",
                                                True, (110,132,122))
                self.screen.blit(hint2, (m_x + 24, m_y + 108))
            char_hint = self.font_stats.render(f"{len(self.new_profile_name)}/12",
                                               True, (80,110,95))
            self.screen.blit(char_hint, (m_x + m_w - char_hint.get_width() - 24, m_y + 108))

        # ── Delete confirmation ──
        elif self.profile_deletion_confirm:
            dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 160))
            self.screen.blit(dim, (0, 0))
            m_w, m_h = min(460, sw - 40), 158
            m_x = sw // 2 - m_w // 2
            m_y = sh // 2 - m_h // 2
            self._draw_panel(pygame.Rect(m_x, m_y, m_w, m_h), bg=(20,10,10),
                             border=(255,50,50), border_width=3)
            target_name = self._truncate_text(
                profiles[self.profile_list_idx]["name"],
                self.font_body, m_w - 60)
            lbl  = self.font_body.render(f"DELETE '{target_name}'?", True, (255,70,70))
            lbl2 = self.font_stats.render("All progress will be permanently erased.",
                                           True, (155,155,155))
            lbl3 = self.font_heading.render("[Y] Confirm   [N] Cancel", True, (255,235,59))
            self.screen.blit(lbl,  (m_x + 24, m_y + 24))
            self.screen.blit(lbl2, (m_x + 24, m_y + 60))
            self.screen.blit(lbl3, (m_x + 24, m_y + 96))

    # ---- Custom Training Dataset Screen Draw ----

    def draw_custom_text_screen(self):
        sw, sh = self.screen_w, self.screen_h
        self.screen.fill((16, 12, 8))
        self.menu_particles.draw(self.screen)

        # Panel — responsive
        pw = min(720, sw - 60)
        ph = min(500, sh - 80)
        px = sw // 2 - pw // 2
        py = sh // 2 - ph // 2
        self._draw_panel(pygame.Rect(px, py, pw, ph), bg=(22, 16, 10),
                         border=(255, 140, 0), border_width=3)

        # Title
        title_lbl  = self._truncate_text("CUSTOM TRAINING DATASET", self.font_heading, pw - 40)
        title_surf = self.font_heading.render(title_lbl, True, (255, 160, 0))
        self.screen.blit(title_surf, (px + 20, py + 20))

        # Fetch data
        cust_data  = self.db_manager.get_custom_text(self.active_profile["id"])
        raw_text   = cust_data["raw_text"] if cust_data else ""
        use_custom = cust_data["use_custom"] == 1 if cust_data else False
        if cust_data:
            import json
            try:
                words     = json.loads(cust_data["words_json"])
                sentences = json.loads(cust_data["sentences_json"])
            except Exception:
                words, sentences = [], []
        else:
            words, sentences = [], []

        # Status row
        st_text = "ACTIVE" if use_custom else "BYPASSED — using built-in"
        st_col  = (0, 255, 100) if use_custom else (150, 150, 150)
        st_surf = self.font_stats.render(f"STATUS: {st_text}   |   "
                                          f"{len(words)} words  {len(sentences)} phrases",
                                          True, st_col)
        self.screen.blit(st_surf, (px + 20, py + 62))

        # Preview box — height fills from y=88 to buttons row
        preview_top  = py + 88
        btn_area_h   = 100           # space reserved for two button rows
        preview_h    = ph - 88 - btn_area_h - 16
        preview_rect = pygame.Rect(px + 20, preview_top, pw - 40, max(preview_h, 80))
        pygame.draw.rect(self.screen, (14, 11, 8), preview_rect, border_radius=6)
        pygame.draw.rect(self.screen, (58, 46, 36), preview_rect, width=1, border_radius=6)

        # Clip rendering to preview box
        self.screen.set_clip(preview_rect.inflate(-6, -6))
        line_h      = self.font_stats.size("A")[1] + 3
        max_preview = max(1, (preview_rect.height - 12) // line_h)
        if not raw_text.strip():
            es1 = self.font_body.render("DATASET IS EMPTY.", True, (108, 98, 86))
            es2 = self.font_stats.render("Paste from clipboard or load a .txt file.",
                                          True, (88, 78, 72))
            self.screen.blit(es1, (preview_rect.x + 16, preview_rect.y + 16))
            self.screen.blit(es2, (preview_rect.x + 16, preview_rect.y + 44))
        else:
            lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
            max_char = (preview_rect.width - 32) // max(1, self.font_stats.size("A")[0])
            for i, line in enumerate(lines[:max_preview]):
                if len(line) > max_char:
                    line = line[:max_char - 3] + "..."
                ls = self.font_stats.render(line, True, (218, 200, 182))
                self.screen.blit(ls, (preview_rect.x + 14,
                                      preview_rect.y + 8 + i * line_h))
            if len(lines) > max_preview:
                more = self.font_stats.render(
                    f"  … {len(lines) - max_preview} more lines", True, (120, 100, 80))
                self.screen.blit(more, (preview_rect.x + 14,
                                        preview_rect.y + 8 + max_preview * line_h))
        self.screen.set_clip(None)

        # Button rows — two rows of buttons anchored inside panel
        mx, my = pygame.mouse.get_pos()
        btn_h      = 38
        inner_w    = pw - 40
        row1_y     = py + ph - btn_area_h + 4
        row2_y     = row1_y + btn_h + 10

        # Row 1: 3 equal buttons
        r1_gap  = 10
        r1_bw   = (inner_w - r1_gap * 2) // 3
        toggle_lbl = "BYPASS TEXT [T]" if use_custom else "ENGAGE TEXT [T]"
        row1 = [
            (toggle_lbl,       "toggle"),
            ("PASTE CLIP [V]", "paste"),
            ("LOAD FILE [L]",  "load"),
        ]
        for i, (lbl, kind) in enumerate(row1):
            bx  = px + 20 + i * (r1_bw + r1_gap)
            br  = pygame.Rect(bx, row1_y, r1_bw, btn_h)
            hov = br.collidepoint(mx, my)
            if kind == "toggle":
                bg = (28,50,32) if hov else (16,30,18);  bc = (0,255,100) if hov else (0,140,65)
            else:
                bg = (42,34,22) if hov else (24,18,12);  bc = (255,140,0) if hov else (145,78,0)
            pygame.draw.rect(self.screen, bg, br, border_radius=8)
            pygame.draw.rect(self.screen, bc, br, width=2, border_radius=8)
            sl = self.font_stats.render(self._truncate_text(lbl, self.font_stats, r1_bw-14),
                                         True, (255,255,255) if hov else (200,188,170))
            self.screen.blit(sl, (br.centerx - sl.get_width()//2,
                                   br.centery - sl.get_height()//2))

        # Row 2: 2 centred buttons
        r2_gap  = 16
        r2_bw   = (inner_w - r2_gap) // 2
        row2 = [
            ("CLEAR DATASET [X]", "clear"),
            ("BACK TO MENU [Esc]", "back"),
        ]
        for i, (lbl, kind) in enumerate(row2):
            bx  = px + 20 + i * (r2_bw + r2_gap)
            br  = pygame.Rect(bx, row2_y, r2_bw, btn_h)
            hov = br.collidepoint(mx, my)
            if kind == "clear":
                bg = (48,20,20) if hov else (28,12,12);  bc = (255,55,55) if hov else (145,36,36)
            else:
                bg = (20,32,44) if hov else (12,20,28);  bc = (0,200,240) if hov else (0,130,160)
            pygame.draw.rect(self.screen, bg, br, border_radius=8)
            pygame.draw.rect(self.screen, bc, br, width=2, border_radius=8)
            sl = self.font_stats.render(self._truncate_text(lbl, self.font_stats, r2_bw-14),
                                         True, (255,255,255) if hov else (200,188,170))
            self.screen.blit(sl, (br.centerx - sl.get_width()//2,
                                   br.centery - sl.get_height()//2))

    # ---- Statistics Dashboard Screen Draw ----

    def draw_stats_screen(self):
        sw, sh = self.screen_w, self.screen_h
        self.screen.fill((10, 12, 16))
        self.menu_particles.draw(self.screen)
        
        # Dimensions
        pw, ph = 800, 520
        px = self.screen_w // 2 - pw // 2
        py = self.screen_h // 2 - ph // 2
        
        # Panel
        self._draw_panel(pygame.Rect(px, py, pw, ph), bg=(16, 20, 26), border=(0, 229, 255), border_width=3)
        
        # Title
        title = self.font_heading.render("NEURAL SYSTEM PERFORMANCE DASHBOARD", True, (0, 229, 255))
        self.screen.blit(title, (px + 40, py + 30))
        
        # Fetch stats
        stats_list = self.db_manager.get_all_stats_for_profile(self.active_profile["id"])
        
        # Left Panel: Cumulative stats
        left_rect = pygame.Rect(px + 40, py + 85, 280, 340)
        pygame.draw.rect(self.screen, (22, 28, 38), left_rect, border_radius=8)
        pygame.draw.rect(self.screen, (40, 50, 70), left_rect, width=1, border_radius=8)
        
        total_games = sum(s["total_games"] for s in stats_list)
        total_words = sum(s["total_words"] for s in stats_list)
        total_keys = sum(s["total_keystrokes"] for s in stats_list)
        correct_keys = sum(s["correct_keystrokes"] for s in stats_list)
        play_time_s = sum(s["play_time"] for s in stats_list)
        
        acc = int((correct_keys / total_keys) * 100) if total_keys > 0 else 100
        
        hours = int(play_time_s // 3600)
        minutes = int((play_time_s % 3600) // 60)
        seconds = int(play_time_s % 60)
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        left_title = self.font_sub.render("OVERALL METRICS", True, (255, 255, 255))
        self.screen.blit(left_title, (px + 60, py + 105))
        
        overall_data = [
            ("COGNITIVE SIGNATURE:", self.active_profile["name"], (0, 229, 255)),
            ("TOTAL PLAYTIME:", time_str, COLOR_TEXT_NORMAL),
            ("TEST RUNS COMPLETED:", str(total_games), COLOR_TEXT_NORMAL),
            ("WORDS DESTRUCTED:", str(total_words), COLOR_TEXT_NORMAL),
            ("KEYSTROKE SUCCESSES:", str(correct_keys), COLOR_TEXT_NORMAL),
            ("TOTAL ATTEMPTS:", str(total_keys), COLOR_TEXT_NORMAL),
            ("SYSTEM ACCURACY:", f"{acc}%", (80, 200, 80))
        ]
        
        for idx, (label, val, col) in enumerate(overall_data):
            y_offset = py + 155 + idx * 36
            lbl_surf = self.font_stats.render(label, True, (130, 140, 160))
            self.screen.blit(lbl_surf, (px + 60, y_offset))
            
            val_surf = self.font_body.render(val, True, col)
            self.screen.blit(val_surf, (px + 60, y_offset + 16))

        # Right Panel: Difficulty comparisons grid
        right_rect = pygame.Rect(px + 340, py + 85, 420, 340)
        pygame.draw.rect(self.screen, (22, 28, 38), right_rect, border_radius=8)
        pygame.draw.rect(self.screen, (40, 50, 70), right_rect, width=1, border_radius=8)
        
        right_title = self.font_sub.render("DIFFICULTY BREAKDOWN", True, (255, 255, 255))
        self.screen.blit(right_title, (px + 360, py + 105))
        
        headers = ["METRIC", "BEGINNER", "MEDIUM", "HARD"]
        header_xs = [px + 360, px + 480, px + 575, px + 670]
        for h_idx, h in enumerate(headers):
            h_surf = self.font_stats.render(h, True, (0, 229, 255) if h_idx > 0 else (130, 140, 160))
            self.screen.blit(h_surf, (header_xs[h_idx], py + 150))
            
        pygame.draw.line(self.screen, (60, 75, 100), (px + 360, py + 172), (px + 740, py + 172), width=1)
        
        def get_diff_val(diff, key, mode=None):
            matching = [s for s in stats_list if s["difficulty"] == diff and (mode is None or s["mode"] == mode)]
            if not matching:
                return "0"
            if key == "level":
                return str(max(s["current_level"] for s in matching))
            elif key == "highest_score":
                return str(max(s["highest_score"] for s in matching))
            elif key == "combo":
                return str(max(s["longest_combo"] for s in matching))
            elif key == "accuracy":
                tot = sum(s["total_keystrokes"] for s in matching)
                cor = sum(s["correct_keystrokes"] for s in matching)
                return f"{int((cor/tot)*100)}%" if tot > 0 else "100%"
            return "0"

        metrics_grid = [
            ("Survival Level", lambda d: get_diff_val(d, "level", "survival")),
            ("Reflex Level", lambda d: get_diff_val(d, "level", "reflex")),
            ("Survival High", lambda d: get_diff_val(d, "highest_score", "survival")),
            ("Reflex High", lambda d: get_diff_val(d, "highest_score", "reflex")),
            ("Precision High", lambda d: get_diff_val(d, "highest_score", "precision")),
            ("Precision Runs", lambda d: get_diff_val(d, "combo", "precision")),
            ("Max Word Combo", lambda d: get_diff_val(d, "combo", "survival")),
            ("Best Key Streak", lambda d: get_diff_val(d, "combo", "reflex")),
            ("Avg Accuracy", lambda d: get_diff_val(d, "accuracy"))
        ]
        
        for row_idx, (m_label, resolver) in enumerate(metrics_grid):
            ry = py + 185 + row_idx * 27
            lbl_surf = self.font_stats.render(m_label, True, (200, 205, 220))
            self.screen.blit(lbl_surf, (px + 360, ry))
            
            for col_idx, d_name in enumerate(["beginner", "medium", "hard"]):
                val = resolver(d_name)
                d_color = (180, 180, 180)
                if d_name == "beginner":
                    d_color = (150, 220, 255)
                elif d_name == "medium":
                    d_color = (255, 235, 59)
                elif d_name == "hard":
                    d_color = (255, 60, 60)
                    
                val_surf = self.font_stats.render(val, True, d_color)
                self.screen.blit(val_surf, (header_xs[col_idx + 1], ry))

        # Control Buttons
        reset_rect = pygame.Rect(px + 180, py + 450, 200, 45)
        back_rect = pygame.Rect(px + 420, py + 450, 200, 45)
        
        mx, my = pygame.mouse.get_pos()
        
        r_hov = reset_rect.collidepoint(mx, my)
        r_bg = (40, 20, 20) if r_hov else (25, 15, 15)
        r_border = (255, 50, 50) if r_hov else (150, 30, 30)
        pygame.draw.rect(self.screen, r_bg, reset_rect, border_radius=8)
        pygame.draw.rect(self.screen, r_border, reset_rect, width=2, border_radius=8)
        r_surf = self.font_stats.render("RESET STATISTICS [R]", True, (255, 255, 255) if r_hov else (200, 180, 180))
        self.screen.blit(r_surf, (px + 280 - r_surf.get_width() // 2, py + 472 - r_surf.get_height() // 2))
        
        b_hov = back_rect.collidepoint(mx, my)
        b_bg = (20, 35, 45) if b_hov else (12, 22, 30)
        b_border = (0, 229, 255) if b_hov else (0, 150, 180)
        pygame.draw.rect(self.screen, b_bg, back_rect, border_radius=8)
        pygame.draw.rect(self.screen, b_border, back_rect, width=2, border_radius=8)
        b_surf = self.font_stats.render("BACK TO MENU [ESC]", True, (255, 255, 255) if b_hov else (180, 200, 225))
        self.screen.blit(b_surf, (px + 520 - b_surf.get_width() // 2, py + 472 - b_surf.get_height() // 2))

        # Reset statistics confirmation overlay
        if self.stats_reset_confirm:
            dim_s = pygame.Surface((self.screen_w, self.screen_h), pygame.SRCALPHA)
            dim_s.fill((0, 0, 0, 150))
            self.screen.blit(dim_s, (0,0))
            
            m_w, m_h = 440, 150
            m_x = self.screen_w // 2 - m_w // 2
            m_y = self.screen_h // 2 - m_h // 2
            
            self._draw_panel(pygame.Rect(m_x, m_y, m_w, m_h), bg=(25, 12, 12), border=(255, 50, 50), border_width=3)
            
            lbl = self.font_body.render("RESET ALL SIGNATURE STATISTICS?", True, (255, 70, 70))
            self.screen.blit(lbl, (m_x + 30, m_y + 30))
            lbl2 = self.font_stats.render("Cumulative testing metrics will be purged.", True, (160, 160, 160))
            self.screen.blit(lbl2, (m_x + 30, m_y + 60))
            lbl3 = self.font_heading.render("CONFIRM RESET: [Y] / [N]", True, (255, 235, 59))
            self.screen.blit(lbl3, (m_x + 30, m_y + 95))
