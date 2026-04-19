import sys
import pygame
import numpy as np
import math

from gesture_tracker import GestureTracker
from entities import Bird, PipePair

SCREEN_W, SCREEN_H = 960, 540
FPS = 60
BG_DARK = (63, 170, 205)
BG_LIGHT = (167, 228, 236)
HILL_COLOR = (82, 184, 97)
HILL_DARK = (52, 143, 75)
GROUND_COLOR = (222, 216, 149)
GROUND_LINE = (115, 191, 46)
GROUND_H = 90
GROUND_Y = SCREEN_H - GROUND_H

UI_WHITE = (255, 255, 255)
UI_BLACK = (0, 0, 0)
UI_YELLOW = (255, 255, 0)
UI_CYAN = (0, 255, 255)
UI_GREEN = (52, 143, 75)

class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Flappy bird")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()

        self.font_title = pygame.font.SysFont("Helvetica", 58, bold=True)
        self.font_lg = pygame.font.SysFont("Helvetica", 44, bold=True)
        self.font_md = pygame.font.SysFont("Helvetica", 25, bold=True)
        self.font_sm = pygame.font.SysFont("Helvetica", 18)

        self.tracker = GestureTracker()
        self.tracker.start()

        self.score = 0
        self.high_score = 0
        self.state = "START"
        self.ground_scroll = 0
        self.last_arm_y = None
        self.arm_ready = True
        self.arm_cooldown = 0
        self.arm_motion = 0.0

        self.reset_game()

    def reset_game(self):
        self.bird = Bird(SCREEN_W // 4, SCREEN_H // 2)
        self.pipes = []
        self.score = 0
        self.pipe_spawn_timer = 40
        self.pipe_speed = 4
        
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        # Space to flap (for testing)
                        if self.state == "PLAYING":
                            self.bird.flap()
                        elif self.state == "START":
                            self.reset_game()
                            self.state = "PLAYING"
                            self.bird.flap()
                        elif self.state == "GAME_OVER":
                            self.reset_game()
                            self.state = "PLAYING"

            gesture = self.tracker.get_state()
            flap_triggered = self._arm_flap_triggered(gesture)

            if self.state == "START":
                self._draw_start_screen(gesture)
                if flap_triggered:
                    self.reset_game()
                    self.state = "PLAYING"
                    self.bird.flap()
            elif self.state == "GAME_OVER":
                self._draw()
                self._draw_overlay_screen("GAME OVER", "Lift arm to restart")
                if flap_triggered:
                    self.reset_game()
                    self.state = "PLAYING"
                    self.bird.flap()
            elif self.state == "PLAYING":
                if flap_triggered:
                    self.bird.flap()
                self._update()
                self._draw()

            # Small webcam overlay (always top-right or corner)
            if self.state != "START":
                self._draw_webcam(gesture)

            pygame.display.flip()
            self.clock.tick(FPS)

        self.tracker.stop()
        pygame.quit()
        sys.exit()

    def _arm_flap_triggered(self, gesture):
        if self.arm_cooldown > 0:
            self.arm_cooldown -= 1

        if not gesture.get("hand_detected"):
            self.last_arm_y = None
            self.arm_ready = True
            self.arm_motion = 0.0
            return False

        current_y = gesture.get("hand_y", gesture.get("index_y", 0.5))
        if self.last_arm_y is None:
            self.last_arm_y = current_y
            return False

        delta_y = current_y - self.last_arm_y
        self.last_arm_y = current_y
        self.arm_motion = self.arm_motion * 0.7 + delta_y * 0.3

        if delta_y > 0.015:
            self.arm_ready = True

        if self.arm_ready and self.arm_cooldown == 0 and delta_y < -0.015:
            self.arm_ready = False
            self.arm_cooldown = 12
            return True

        return False

    def _update_ground(self):
        if not self.bird.dead:
            self.ground_scroll = (self.ground_scroll - self.pipe_speed) % 24

    def _update(self):
        self.bird.update()
        self._update_ground()
        
        # Spawn pipes
        self.pipe_spawn_timer -= 1
        if self.pipe_spawn_timer <= 0:
            self.pipes.append(PipePair(SCREEN_W + 30, SCREEN_H, gap_size=170, ground_h=GROUND_H))
            self.pipe_spawn_timer = 108

        for p in self.pipes:
            p.update(self.pipe_speed)
            
            # Score
            if not p.passed and p.x + p.width < self.bird.x:
                p.passed = True
                self.score += 1
                if self.score > self.high_score:
                    self.high_score = self.score

        # Remove off-screen pipes
        self.pipes = [p for p in self.pipes if p.x + p.width > -100]

        # Collisions
        if self.bird.y + self.bird.radius > GROUND_Y:
            self.bird.y = GROUND_Y - self.bird.radius
            if self.bird.velocity > 0:
                self.bird.velocity = 0
        
        if self.bird.y - self.bird.radius < 0:
            self.bird.y = self.bird.radius
            self.bird.velocity = 0

        for p in self.pipes:
            if p.collides_with(self.bird):
                self.bird.dead = True
                self.state = "GAME_OVER"

    def _draw_start_screen(self, gesture):
        self._draw_background()
        self._draw_ground()

        title_text = "Flappy bird"
        shadow_t = self.font_title.render(title_text, True, (36, 66, 75))
        self.screen.blit(shadow_t, (58, 48))
        main_t = self.font_title.render(title_text, True, UI_WHITE)
        self.screen.blit(main_t, (54, 44))

        tagline = self.font_md.render("Move your arm down, then lift it up to flap.", True, (26, 67, 74))
        self.screen.blit(tagline, (58, 112))

        pulse = (math.sin(pygame.time.get_ticks() / 210) + 1) / 2
        start_color = (
            int(255 - pulse * 25),
            int(236 - pulse * 30),
            int(86 + pulse * 60),
        )
        start_rect = pygame.Rect(58, 155, 330, 58)
        pygame.draw.rect(self.screen, start_color, start_rect, border_radius=8)
        pygame.draw.rect(self.screen, (42, 34, 34), start_rect, 3, border_radius=8)
        start_text = self.font_md.render("LIFT ARM TO START", True, UI_BLACK)
        self.screen.blit(start_text, (
            start_rect.centerx - start_text.get_width() // 2,
            start_rect.centery - start_text.get_height() // 2,
        ))

        hint = self.font_sm.render("A quick upward arm motion makes the bird jump.", True, (26, 67, 74))
        self.screen.blit(hint, (60, 225))

        calib_msg = "Show your hand to camera"
        calib_color = UI_BLACK
        ready = False

        if gesture.get("camera_error"):
            calib_msg = gesture["camera_error"]
            calib_color = (180, 45, 45)

        elif gesture.get("hand_detected") and gesture.get("hand_box"):
            x_min, y_min, x_max, y_max = gesture["hand_box"]
            box_w = x_max - x_min
            box_h = y_max - y_min
            
            if box_w > 0.8 or box_h > 0.8:
                calib_msg = "Move hand back"
            elif box_w < 0.2 or box_h < 0.2:
                calib_msg = "Move hand closer"
            elif x_min < 0.05 or x_max > 0.95 or y_min < 0.05 or y_max > 0.95:
                calib_msg = "Center your hand"
            else:
                calib_msg = "Perfect! Move arm down, then lift."
                calib_color = UI_GREEN
                ready = True

        bird_y = SCREEN_H // 2 + 70 + math.sin(pygame.time.get_ticks() / 200) * 12
        self.bird.x = 245
        self.bird.y = bird_y
        self.bird.wing_phase = pygame.time.get_ticks() / 85
        self.bird.flap_lift = 0.45 + 0.35 * math.sin(pygame.time.get_ticks() / 170)
        self.bird.draw(self.screen)

        camera_rect = pygame.Rect(548, 84, 364, 282)
        pygame.draw.rect(self.screen, (31, 91, 105), camera_rect, border_radius=8)
        pygame.draw.rect(self.screen, calib_color if ready else UI_WHITE, camera_rect, 4, border_radius=8)

        overlay = self.tracker.get_overlay()
        if overlay is not None:
            overlay_rgb = overlay[:, :, ::-1]
            overlay_rgb = np.ascontiguousarray(overlay_rgb)
            h, w, _ = overlay_rgb.shape
            
            w_scaled, h_scaled = 356, 267
            surf = pygame.image.frombuffer(overlay_rgb.tobytes(), (w, h), "RGB")
            surf = pygame.transform.scale(surf, (w_scaled, h_scaled))
            
            ox = camera_rect.centerx - w_scaled // 2
            oy = camera_rect.centery - h_scaled // 2
            
            self.screen.blit(surf, (ox, oy))

            if gesture.get("hand_detected") and gesture.get("hand_box"):
                x_min, y_min, x_max, y_max = gesture["hand_box"]
                bx = ox + int(x_min * w_scaled)
                by = oy + int(y_min * h_scaled)
                bw = int((x_max - x_min) * w_scaled)
                bh = int((y_max - y_min) * h_scaled)
                pygame.draw.rect(self.screen, UI_YELLOW, (bx, by, bw, bh), 2)
        else:
            loading = self.font_md.render("Camera loading...", True, UI_WHITE)
            self.screen.blit(loading, (
                camera_rect.centerx - loading.get_width() // 2,
                camera_rect.centery - loading.get_height() // 2,
            ))

        inst = self.font_md.render(calib_msg, True, calib_color)
        self.screen.blit(inst, (camera_rect.centerx - inst.get_width() // 2, camera_rect.bottom + 18))
        sub = self.font_sm.render("Keep your hand centered in the frame.", True, (26, 67, 74))
        self.screen.blit(sub, (camera_rect.centerx - sub.get_width() // 2, camera_rect.bottom + 51))


    def _draw_cloud(self, x, y, scale=1.0):
        color = (241, 252, 255)
        shadow = (191, 226, 232)
        points = [
            (x + int(20 * scale), y + int(18 * scale), int(20 * scale)),
            (x + int(42 * scale), y + int(10 * scale), int(28 * scale)),
            (x + int(73 * scale), y + int(20 * scale), int(21 * scale)),
        ]
        for cx, cy, radius in points:
            pygame.draw.circle(self.screen, shadow, (cx, cy + int(4 * scale)), radius)
            pygame.draw.circle(self.screen, color, (cx, cy), radius)
        pygame.draw.rect(self.screen, color, (x + int(16 * scale), y + int(18 * scale), int(70 * scale), int(24 * scale)), border_radius=8)

    def _draw_background(self):
        for y in range(SCREEN_H):
            t = y / SCREEN_H
            color = (
                int(BG_LIGHT[0] * (1 - t) + BG_DARK[0] * t),
                int(BG_LIGHT[1] * (1 - t) + BG_DARK[1] * t),
                int(BG_LIGHT[2] * (1 - t) + BG_DARK[2] * t),
            )
            pygame.draw.line(self.screen, color, (0, y), (SCREEN_W, y))

        scroll = (pygame.time.get_ticks() / 45) % (SCREEN_W + 220)
        for base_x, y, scale in [(60, 70, 0.8), (345, 42, 0.62), (705, 80, 0.92)]:
            x = int((base_x - scroll * 0.22) % (SCREEN_W + 220)) - 110
            self._draw_cloud(x, y, scale)

        hill_y = GROUND_Y - 32
        pygame.draw.circle(self.screen, HILL_DARK, (180, hill_y + 78), 142)
        pygame.draw.circle(self.screen, HILL_COLOR, (390, hill_y + 92), 156)
        pygame.draw.circle(self.screen, HILL_DARK, (710, hill_y + 84), 150)
        pygame.draw.rect(self.screen, HILL_COLOR, (0, hill_y + 44, SCREEN_W, 60))

    def _draw_ground(self):
        ground_rect = pygame.Rect(0, GROUND_Y, SCREEN_W, GROUND_H)
        pygame.draw.rect(self.screen, GROUND_COLOR, ground_rect)
        pygame.draw.line(self.screen, GROUND_LINE, (0, GROUND_Y), (SCREEN_W, GROUND_Y), 5)
        # draw scrolling pattern
        for i in range(-24, SCREEN_W, 24):
            pygame.draw.line(self.screen, GROUND_LINE, (i + self.ground_scroll, GROUND_Y), (i + self.ground_scroll + 10, GROUND_Y + 10), 3)

    def _draw(self):
        self._draw_background()

        for p in self.pipes:
            p.draw(self.screen)
            
        self._draw_ground()
        
        self.bird.draw(self.screen)

        # Score
        sc_txt = self.font_title.render(str(self.score), True, UI_WHITE)
        shadow = self.font_title.render(str(self.score), True, UI_BLACK)
        self.screen.blit(shadow, (SCREEN_W // 2 - sc_txt.get_width() // 2 + 2, 50 + 2))
        self.screen.blit(sc_txt, (SCREEN_W // 2 - sc_txt.get_width() // 2, 50))

    def _draw_webcam(self, gesture):
        overlay = self.tracker.get_overlay()
        if overlay is not None:
            overlay_rgb = overlay[:, :, ::-1]
            overlay_rgb = np.ascontiguousarray(overlay_rgb)
            h, w, _ = overlay_rgb.shape
            
            # Scale it down for corner
            scale = 4
            w_scaled, h_scaled = w // scale, h // scale
            surf = pygame.image.frombuffer(overlay_rgb.tobytes(), (w, h), "RGB")
            surf = pygame.transform.scale(surf, (w_scaled, h_scaled))
            
            ox = 10
            oy = 10
            
            color = UI_CYAN if self.arm_motion < -0.018 else UI_WHITE
            pygame.draw.rect(self.screen, color, (ox - 2, oy - 2, w_scaled + 4, h_scaled + 4), 2)
            self.screen.blit(surf, (ox, oy))

    def _draw_overlay_screen(self, title_text, sub_text):
        dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 100))
        self.screen.blit(dim, (0, 0))

        # Score board
        board_rect = pygame.Rect(SCREEN_W//2 - 120, SCREEN_H//2 - 80, 240, 160)
        pygame.draw.rect(self.screen, (222, 216, 149), board_rect, border_radius=10)
        pygame.draw.rect(self.screen, (84, 136, 34), board_rect, 4, border_radius=10)
        
        sc_lbl = self.font_sm.render("SCORE", True, UI_BLACK)
        sc_val = self.font_lg.render(str(self.score), True, UI_BLACK)
        hi_lbl = self.font_sm.render("BEST", True, UI_BLACK)
        hi_val = self.font_lg.render(str(self.high_score), True, UI_BLACK)
        
        self.screen.blit(sc_lbl, (SCREEN_W//2 - 80, SCREEN_H//2 - 60))
        self.screen.blit(sc_val, (SCREEN_W//2 - 80, SCREEN_H//2 - 40))
        
        self.screen.blit(hi_lbl, (SCREEN_W//2 + 30, SCREEN_H//2 - 60))
        self.screen.blit(hi_val, (SCREEN_W//2 + 30, SCREEN_H//2 - 40))

        title = self.font_lg.render(title_text, True, UI_WHITE)
        title_shadow = self.font_lg.render(title_text, True, UI_BLACK)
        sub = self.font_md.render(sub_text, True, UI_WHITE)
        sub_shadow = self.font_md.render(sub_text, True, UI_BLACK)
        
        self.screen.blit(title_shadow, (SCREEN_W // 2 - title.get_width() // 2 + 2, SCREEN_H // 2 - 140 + 2))
        self.screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, SCREEN_H // 2 - 140))
        
        self.screen.blit(sub_shadow, (SCREEN_W // 2 - sub.get_width() // 2 + 2, SCREEN_H // 2 + 100 + 2))
        self.screen.blit(sub, (SCREEN_W // 2 - sub.get_width() // 2, SCREEN_H // 2 + 100))

if __name__ == "__main__":
    game = Game()
    game.run()
