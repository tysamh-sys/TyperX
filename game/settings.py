import pygame

# Default Fallback Configurations (if windowed)
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
FPS = 60

# Colors (Hex / RGB)
COLOR_BG = (18, 18, 24)           # Deep slate blue/black
COLOR_PLAYER = (156, 39, 176)      # Neon/Pastel purple
COLOR_TEXT_NORMAL = (220, 220, 225) # Soft white
COLOR_TEXT_TYPED = (0, 229, 255)    # Bright neon cyan
COLOR_ENEMY_NORMAL = (255, 64, 129) # Vibrant pink/red
COLOR_ENEMY_TARGET = (255, 235, 59) # Bright yellow (for current target word)
COLOR_PANEL_BG = (30, 30, 40)       # Dark gray panel
COLOR_UI_TEXT = (255, 255, 255)     # White for stats
COLOR_BORDER = (45, 45, 60)         # Border line color

# Game States
STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_GAME_OVER = "game_over"
STATE_VICTORY = "victory"
STATE_PROFILES = "profiles"
STATE_CUSTOM_TEXT = "custom_text"
STATE_STATS = "stats"

# Game Mechanics Settings
INITIAL_ENEMY_SPEED = 0.8     # Starting speed (pixels per frame)
SPEED_INCREMENT = 0.05        # Speed increment per correctly typed word
INITIAL_SPAWN_COOLDOWN = 3500 # Spawning cooldown (ms) at start
SPAWN_COOLDOWN_DECREMENT = 100 # Cooldown reduction (ms) per typed word
MIN_SPAWN_COOLDOWN = 1200     # Cap on fastest spawning (1.2 seconds)

STARTING_LIVES = 5
WORDS_TO_SUMMON_BOSS = 8      # Number of normal words to type before Boss Battle

# Theme Configurations
LEVEL_THEMES = {
    1: {
        "name": "COSMIC SPACE SECTOR",
        "bg": (10, 10, 20),
        "accent": (0, 229, 255),       # Neon Cyan
        "enemy": (180, 80, 220),       # Cosmic Violet
        "type": "space"
    },
    2: {
        "name": "FROSTBITTEN TUNDRA",
        "bg": (12, 22, 32),
        "accent": (140, 220, 255),     # Glacier Blue
        "enemy": (200, 240, 255),      # Frost White
        "type": "winter"
    },
    3: {
        "name": "HELLFIRE CALDERA",
        "bg": (22, 8, 8),
        "accent": (255, 120, 0),       # Magma Orange
        "enemy": (255, 60, 60),        # Ember Red
        "type": "volcano"
    },
    4: {
        "name": "ARCANE CRYSTAL SPIRE",
        "bg": (20, 10, 30),
        "accent": (255, 215, 0),       # Gold
        "enemy": (210, 100, 250),      # Mana Pink
        "type": "fantasy"
    },
    5: {
        "name": "NEON CYBER CORE",
        "bg": (4, 4, 6),
        "accent": (50, 255, 50),       # Matrix Green
        "enemy": (0, 200, 120),        # Cyber Teal
        "type": "cyber"
    }
}

MAX_LEVEL = 5
