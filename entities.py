import math
import pygame
import random

class Bird:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.velocity = 0
        self.gravity = 0.34
        self.flap_strength = -7.8
        self.radius = 18
        self.dead = False
        self.wing_phase = 0.0
        self.flap_lift = 0.0

    def flap(self):
        if not self.dead:
            self.velocity = self.flap_strength
            self.flap_lift = 1.0

    def update(self):
        self.velocity += self.gravity
        self.y += self.velocity
        self.wing_phase += 0.32 + min(abs(self.velocity) * 0.025, 0.18)
        self.flap_lift = max(0.0, self.flap_lift - 0.08)

    def _rotation(self):
        return max(-28, min(35, self.velocity * 4))

    def draw(self, surface):
        sprite = pygame.Surface((76, 58), pygame.SRCALPHA)
        cx, cy = 34, 29
        wing_swing = math.sin(self.wing_phase) * 8 - self.flap_lift * 13

        # Tail
        pygame.draw.polygon(sprite, (246, 185, 42), [(14, 25), (2, 17), (7, 31)])
        pygame.draw.polygon(sprite, (42, 34, 34), [(14, 25), (2, 17), (7, 31)], 2)

        # Body
        body_rect = pygame.Rect(cx - 22, cy - 18, 46, 36)
        pygame.draw.ellipse(sprite, (255, 231, 66), body_rect)
        pygame.draw.ellipse(sprite, (42, 34, 34), body_rect, 2)

        # Smoothly animated wing
        wing_tip_y = cy + wing_swing
        wing_points = [(cx - 10, cy - 2), (cx - 27, wing_tip_y), (cx - 6, cy + 14), (cx + 4, cy + 6)]
        pygame.draw.polygon(sprite, (255, 174, 52), wing_points)
        pygame.draw.lines(sprite, (42, 34, 34), True, wing_points, 2)
        pygame.draw.arc(sprite, (220, 118, 38), pygame.Rect(cx - 23, cy - 4, 24, 20), 0.25, 2.7, 2)

        # Eye
        pygame.draw.circle(sprite, (255, 255, 255), (cx + 13, cy - 8), 7)
        pygame.draw.circle(sprite, (42, 34, 34), (cx + 15, cy - 8), 3)
        pygame.draw.circle(sprite, (42, 34, 34), (cx + 13, cy - 8), 7, 1)

        # Beak
        beak = [(cx + 22, cy - 4), (cx + 38, cy + 1), (cx + 22, cy + 8)]
        pygame.draw.polygon(sprite, (255, 122, 35), beak)
        pygame.draw.lines(sprite, (42, 34, 34), True, beak, 2)

        rotated = pygame.transform.rotozoom(sprite, -self._rotation(), 1)
        rect = rotated.get_rect(center=(int(self.x), int(self.y)))
        surface.blit(rotated, rect)

class PipePair:
    def __init__(self, x, screen_h, gap_size=150, ground_h=90):
        self.x = x
        self.width = 74
        self.gap_size = gap_size
        self.screen_h = screen_h
        
        self.ground_y = screen_h - ground_h
        
        min_pipe_h = 45
        max_y = self.ground_y - min_pipe_h - self.gap_size
        self.gap_y = random.randint(min_pipe_h, max_y)
        self.passed = False

    def update(self, speed):
        self.x -= speed

    def draw(self, surface):
        color = (115, 191, 46)
        outline = (84, 136, 34)
        
        # Top pipe
        top_rect = pygame.Rect(self.x, 0, self.width, self.gap_y)
        pygame.draw.rect(surface, color, top_rect)
        pygame.draw.rect(surface, outline, top_rect, 3)
        # Cap
        cap_rect = pygame.Rect(self.x - 4, self.gap_y - 20, self.width + 8, 20)
        pygame.draw.rect(surface, color, cap_rect)
        pygame.draw.rect(surface, outline, cap_rect, 3)
        
        # Bottom pipe
        bottom_y = self.gap_y + self.gap_size
        bottom_h = self.ground_y - bottom_y
        bottom_rect = pygame.Rect(self.x, bottom_y, self.width, bottom_h)
        pygame.draw.rect(surface, color, bottom_rect)
        pygame.draw.rect(surface, outline, bottom_rect, 3)
        # Cap
        cap_rect2 = pygame.Rect(self.x - 4, bottom_y, self.width + 8, 20)
        pygame.draw.rect(surface, color, cap_rect2)
        pygame.draw.rect(surface, outline, cap_rect2, 3)

    def collides_with(self, bird):
        bird_rect = pygame.Rect(bird.x - bird.radius, bird.y - bird.radius, bird.radius * 2, bird.radius * 2)
        top_pipe = pygame.Rect(self.x, 0, self.width, self.gap_y)
        bottom_pipe = pygame.Rect(self.x, self.gap_y + self.gap_size, self.width, self.ground_y - (self.gap_y + self.gap_size))
        
        if bird_rect.colliderect(top_pipe) or bird_rect.colliderect(bottom_pipe):
            return True
        return False
