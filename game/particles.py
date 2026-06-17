import pygame
import random
import math

class Particle:
    def __init__(self, x, y, vx, vy, color, size, life, fade=True):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.size = size
        self.life = life
        self.max_life = life
        self.fade = fade

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1

    def draw(self, screen):
        if self.life <= 0:
            return
        alpha_ratio = self.life / self.max_life if self.fade else 1.0
        r, g, b = self.color[:3]
        radius = max(1, int(self.size * alpha_ratio))
        pygame.draw.circle(screen, (r, g, b), (int(self.x), int(self.y)), radius)


class ParticleSystem:
    """Generic particle system for level backgrounds."""
    def __init__(self, screen_w, screen_h, theme_type, density=80, difficulty="medium"):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.theme_type = theme_type
        self.difficulty = difficulty
        
        # Scale density based on difficulty
        if difficulty == "beginner":
            self.density = int(density * 0.6)
        elif difficulty == "hard":
            self.density = int(density * 1.6)
        else:
            self.density = density
            
        self.particles = []
        self.anim_tick = 0
        self._spawn_initial()

    def _spawn_initial(self):
        for _ in range(self.density):
            self._spawn_particle(initial=True)

    def _spawn_particle(self, initial=False):
        t = self.theme_type
        diff = self.difficulty
        
        # Speed multiplier
        speed_mult = 0.6 if diff == "beginner" else (1.5 if diff == "hard" else 1.0)
        
        if t == "space":
            x = random.randint(0, self.screen_w)
            y = random.randint(0, self.screen_h) if initial else 0
            brightness = random.randint(100, 255)
            
            # Beginner gets friendly pastel sky blue, Hard gets warning red/orange flares
            if diff == "beginner":
                color = (min(255, brightness + 30), brightness, 255)
            elif diff == "hard":
                color = (255, random.randint(60, 120), random.randint(0, 50))
            else:
                color = (brightness, brightness, min(255, brightness + 40))
                
            size = random.choice([1, 1, 1, 2, 2, 3])
            speed = random.uniform(0.1, 0.8) * speed_mult
            life = int(self.screen_h / max(speed, 0.05)) if not initial else random.randint(20, 300)
            self.particles.append(Particle(x, y, random.uniform(-0.1, 0.1), speed, color, size, life, fade=False))

        elif t == "winter":
            x = random.randint(0, self.screen_w)
            y = random.randint(0, self.screen_h) if initial else -5
            shade = random.randint(180, 255)
            
            if diff == "beginner":
                color = (200, 240, 255) # Soft baby blue
            elif diff == "hard":
                color = (random.choice([255, 180]), 100, 255) # Tense cyan-purple crystals
            else:
                color = (shade, shade, 255)
                
            size = random.randint(1, 3)
            vx = random.uniform(-0.4, 0.4) * speed_mult
            vy = random.uniform(0.4, 1.2) * speed_mult
            life = int(self.screen_h / max(vy, 0.1))
            self.particles.append(Particle(x, y, vx, vy, color, size, life, fade=False))

        elif t == "volcano":
            x = random.randint(0, self.screen_w)
            y = self.screen_h if not initial else random.randint(0, self.screen_h)
            
            if diff == "beginner":
                color = (255, 180, 120) # Soft glowing peach/orange
            elif diff == "hard":
                color = random.choice([(255, 0, 0), (255, 50, 0), (120, 0, 0)]) # Dark volcanic embers
            else:
                color = random.choice([(255, 60, 0), (255, 120, 0), (255, 200, 50)])
                
            size = random.randint(1, 3)
            vx = random.uniform(-0.6, 0.6) * speed_mult
            vy = random.uniform(-2.5, -0.8) * speed_mult
            life = random.randint(30, 90)
            self.particles.append(Particle(x, y, vx, vy, color, size, life, fade=True))

        elif t == "fantasy":
            x = random.randint(0, self.screen_w)
            y = random.randint(0, self.screen_h) if initial else random.randint(0, self.screen_h // 2)
            shade_r = random.randint(150, 255)
            shade_g = random.randint(50, 150)
            
            if diff == "beginner":
                color = (180, 220, 255) # Soft magic light blue
            elif diff == "hard":
                color = (255, 50, random.choice([255, 100])) # Angry pink/magenta runes
            else:
                color = (shade_r, shade_g, 255)
                
            size = random.randint(1, 4)
            vx = random.uniform(-0.3, 0.3) * speed_mult
            vy = random.uniform(-0.5, 0.5) * speed_mult
            life = random.randint(80, 200)
            self.particles.append(Particle(x, y, vx, vy, color, size, life, fade=True))

        elif t == "cyber":
            x = random.randint(0, self.screen_w // 10) * 10
            y = random.randint(0, self.screen_h) if initial else 0
            shade = random.randint(100, 255)
            
            if diff == "beginner":
                color = (100, 255, 180) # Relaxing emerald matrix
            elif diff == "hard":
                # Red alerts flashing within code streams
                color = (255, 30, 30) if random.random() < 0.35 else (0, shade, 50)
            else:
                color = (0, shade, random.randint(50, 120))
                
            size = random.randint(1, 2)
            vy = random.uniform(1.5, 4.0) * speed_mult
            life = int(self.screen_h / max(vy, 0.1))
            self.particles.append(Particle(x, y, 0, vy, color, size, life, fade=False))

    def update(self):
        self.anim_tick += 1
        if self.theme_type == "fantasy":
            # Wave motion scales with speed
            mult = 0.05 if self.difficulty == "hard" else (0.02 if self.difficulty == "beginner" else 0.03)
            for p in self.particles:
                p.vx = 0.3 * math.sin(p.y * 0.02 + self.anim_tick * mult)

        self.particles = [p for p in self.particles if p.life > 0]
        for p in self.particles:
            p.update()

        while len(self.particles) < self.density:
            self._spawn_particle(initial=False)

    def draw(self, screen):
        for p in self.particles:
            p.draw(screen)

