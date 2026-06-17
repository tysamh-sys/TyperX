import pygame

class BaseMode:
    def __init__(self, game):
        """
        Initialize the game mode.
        :param game: The main Game shell instance (provides access to screen, sounds, fonts, themes, etc.)
        """
        self.game = game

    def start(self):
        """Reset internal state and start the game mode."""
        pass

    def handle_event(self, event):
        """
        Process a Pygame event.
        :param event: Pygame Event object
        """
        pass

    def update(self):
        """Update game logic, positioning, timers, etc."""
        pass

    def draw(self, screen):
        """
        Render the gameplay frame.
        :param screen: The active Pygame screen Surface
        """
        pass
