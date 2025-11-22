# -*- coding: utf-8 -*-
"""
Gawon Fall Flat 2D (pygame only, harder map + clear 동작)

- pygame만 사용
- 뽀글머리 + 헤어롤 캐릭터
- A / D / ← / → : 좌우 이동
- Space / W / ↑ : 점프 (바닥에 있을 때)
- 오른쪽 위 초록 발판 "위에 서면" STAGE CLEAR → 클리어 화면 후 종료
"""

import sys
import math
import pygame
from pygame.locals import *

# -----------------------------
# 기본 설정
# -----------------------------

WIDTH, HEIGHT = 1280, 720
FPS = 60

COLOR_BG = (25, 30, 50)
COLOR_PLATFORM = (210, 210, 220)
COLOR_BOX = (190, 210, 255)
COLOR_GOAL = (140, 230, 160)
COLOR_TEXT = (235, 235, 235)

COLOR_PLAYER_BODY = (245, 220, 120)
COLOR_PLAYER_HEAD = (255, 235, 190)
COLOR_HAIR = (90, 60, 40)
COLOR_ROLLER = (240, 120, 180)
COLOR_ROLLER_STRIPE = (255, 210, 230)
COLOR_EYE = (40, 30, 30)
COLOR_MOUTH = (180, 60, 80)

GRAVITY = 1600          # 중력
MOVE_SPEED = 290        # 좌우 이동 속도
JUMP_SPEED = 670        # 점프 속도
FRICTION = 0.0009       # 바닥 마찰(살짝 미끄러지는 느낌)


# -----------------------------
# 플레이어
# -----------------------------

class Player:
    def __init__(self, x, y):
        self.width = 40
        self.height = 60
        self.rect = pygame.Rect(0, 0, self.width, self.height)
        self.rect.midbottom = (x, y)

        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False

        # 비틀비틀 애니메이션용
        self.wobble_t = 0.0

    def handle_input(self, keys):
        target_vx = 0.0
        if keys[K_a] or keys[K_LEFT]:
            target_vx -= MOVE_SPEED
        if keys[K_d] or keys[K_RIGHT]:
            target_vx += MOVE_SPEED

        # 살짝 관성 있는 움직임
        if target_vx == 0:
            # 키 안 누르면 서서히 멈춤
            if abs(self.vx) < 10:
                self.vx = 0
            else:
                self.vx *= 0.85
        else:
            # 목표 속도 쪽으로 천천히 붙어가게
            self.vx += (target_vx - self.vx) * 0.25

    def try_jump(self):
        if self.on_ground:
            self.vy = -JUMP_SPEED
            self.on_ground = False

    def update(self, dt, platforms):
        # 중력
        self.vy += GRAVITY * dt

        # 비틀비틀 파라미터 업데이트 (속도에 따라 조금 더 흔들)
        self.wobble_t += dt * (3.0 + abs(self.vx) / 150.0)

        # ---- 수평 이동 ----
        self.rect.x += int(self.vx * dt)

        # 수평 충돌
        for p in platforms:
            if self.rect.colliderect(p):
                if self.vx > 0:      # 오른쪽으로
                    self.rect.right = p.left
                elif self.vx < 0:    # 왼쪽으로
                    self.rect.left = p.right
                self.vx = 0

        # 화면 밖으로 나가지 않게
        if self.rect.left < 0:
            self.rect.left = 0
            self.vx = 0
        if self.rect.right > WIDTH:
            self.rect.right = WIDTH
            self.vx = 0

        # ---- 수직 이동 ----
        self.rect.y += int(self.vy * dt)

        # 수직 충돌
        self.on_ground = False
        for p in platforms:
            if self.rect.colliderect(p):
                if self.vy > 0:      # 아래로 떨어지는 중
                    self.rect.bottom = p.top
                    self.vy = 0
                    self.on_ground = True
                elif self.vy < 0:    # 위로 치솟는 중
                    self.rect.top = p.bottom
                    self.vy = 0

        # 바닥에 있을 때 살짝 마찰감
        if self.on_ground:
            if abs(self.vx) < 5:
                self.vx = 0
            else:
                self.vx *= (1.0 - FRICTION * (dt * 1000))

    def draw(self, surface):
        # 약간 몸이 흔들리는 느낌
        wobble_y = math.sin(self.wobble_t * 6.0) * (3 if not self.on_ground else 1.5)
        lean_x = int(self.vx * 0.02)  # 속도 방향으로 살짝 기울어진 느낌

        body_rect = self.rect.copy()
        body_rect.x += lean_x
        body_rect.y += int(wobble_y)

        # 몸통
        pygame.draw.rect(surface, COLOR_PLAYER_BODY, body_rect)

        # 머리 위치
        head_radius = 18
        hx = body_rect.centerx
        hy = body_rect.top - head_radius + int(wobble_y)

        # 뽀글머리
        hair_rect = pygame.Rect(0, 0, 56, 52)
        hair_rect.center = (hx, hy - 4)
        pygame.draw.ellipse(surface, COLOR_HAIR, hair_rect)
        for dx in (-18, 0, 18):
            pygame.draw.circle(surface, COLOR_HAIR, (hx + dx, hy + 16), 8)

        # 얼굴
        pygame.draw.circle(surface, COLOR_PLAYER_HEAD, (hx, hy), head_radius)

        # 헤어롤
        roller_w, roller_h = 34, 10
        roller_rect = pygame.Rect(
            hx - roller_w // 2,
            hy - head_radius - 4,
            roller_w,
            roller_h
        )
        pygame.draw.rect(surface, COLOR_ROLLER, roller_rect, border_radius=4)
        stripe_gap = 6
        for i in range(1, 4):
            sx = roller_rect.left + i * stripe_gap
            pygame.draw.line(surface, COLOR_ROLLER_STRIPE,
                             (sx, roller_rect.top + 2),
                             (sx, roller_rect.bottom - 2), 2)

        # 눈
        eye_offset_x = 7
        eye_y = hy - 2
        pygame.draw.circle(surface, COLOR_EYE, (hx - eye_offset_x, eye_y), 2)
        pygame.draw.circle(surface, COLOR_EYE, (hx + eye_offset_x, eye_y), 2)

        # 입
        mouth_rect = pygame.Rect(hx - 8, hy + 4, 16, 8)
        pygame.draw.arc(surface, COLOR_MOUTH, mouth_rect,
                        math.radians(10), math.radians(170), 2)


# -----------------------------
# 게임 클래스
# -----------------------------

class GawonFallFlatGame:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Gawon Fall Flat 2D (pygame only)")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        try:
            self.font = pygame.font.SysFont("malgungothic", 20)
            self.big_font = pygame.font.SysFont("malgungothic", 64, bold=True)
        except Exception:
            self.font = pygame.font.SysFont(None, 20)
            self.big_font = pygame.font.SysFont(None, 64)

        self.platforms = []   # 충돌용 발판
        self.boxes = []       # 장식/추가 발판
        self.goal_rect = None

        floor_y = HEIGHT - 80
        self.player = Player(80, floor_y)  # 왼쪽 아래
        self.goal_reached = False
        self.jump_was_down = False
        self.running = True

        self.create_level()

    def create_level(self):
        """
        난이도 높은 맵
        - 바닥 구멍 크게 3개
        - 좁은 발판들로 지그재그 점프
        - 오른쪽 위의 골 플랫폼
        """
        floor_y = HEIGHT - 80

        # 바닥 (구멍 세 개)
        self.platforms.append(pygame.Rect(0, floor_y, 220, 20))      # 시작
        self.platforms.append(pygame.Rect(340, floor_y, 200, 20))    # 중간
        self.platforms.append(pygame.Rect(650, floor_y, 220, 20))    # 끝 부분

        # 중간 계단형 (점프 여러 번 필요)
        self.platforms.append(pygame.Rect(230, floor_y - 90, 90, 18))
        self.platforms.append(pygame.Rect(380, floor_y - 170, 100, 18))
        self.platforms.append(pygame.Rect(550, floor_y - 250, 100, 18))
        self.platforms.append(pygame.Rect(720, floor_y - 330, 100, 18))

        # 위쪽 좁은 발판 (실수하면 바로 추락)
        self.platforms.append(pygame.Rect(900, floor_y - 380, 80, 18))
        self.platforms.append(pygame.Rect(1040, floor_y - 430, 80, 18))

        # 박스들 (점프 보조용 / 장식용)
        self.boxes.append(pygame.Rect(150, floor_y - 40, 60, 40))
        self.boxes.append(pygame.Rect(360, floor_y - 130, 60, 40))
        self.boxes.append(pygame.Rect(620, floor_y - 210, 60, 40))
        self.boxes.append(pygame.Rect(820, floor_y - 300, 60, 40))
        self.boxes.append(pygame.Rect(960, floor_y - 350, 60, 40))

        # 박스도 발판처럼 충돌에 사용
        self.platforms += self.boxes

        # 골(오른쪽 위)
        goal_w, goal_h = 90, 36
        goal_x = 1160
        goal_y = floor_y - 460
        self.goal_rect = pygame.Rect(goal_x, goal_y, goal_w, goal_h)
        self.platforms.append(self.goal_rect)  # 위에 설 수 있도록 플랫폼에 포함

    # --------- 이벤트 처리 ---------

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == QUIT:
                self.running = False
            elif event.type == KEYDOWN and event.key == K_ESCAPE:
                self.running = False

    def step(self, dt):
        keys = pygame.key.get_pressed()

        # 이동
        self.player.handle_input(keys)

        # 점프 (눌렀다 뗄 때 1번)
        jump_now = keys[K_SPACE] or keys[K_w] or keys[K_UP]
        if jump_now and not self.jump_was_down:
            self.player.try_jump()
        self.jump_was_down = jump_now

        # 업데이트(물리)
        self.player.update(dt, self.platforms)

        # ---------------------
        # 골 판정 (발밑 한 픽셀)
        # ---------------------
        foot_x = self.player.rect.centerx
        foot_y = self.player.rect.bottom + 1  # 발 바로 아래 한 픽셀
        if self.goal_rect.collidepoint(foot_x, foot_y):
            self.goal_reached = True
            self.running = False
            return

        # 바닥 아래로 떨어지면 리스폰
        if self.player.rect.top > HEIGHT + 200:
            floor_y = HEIGHT - 80
            self.player.rect.midbottom = (80, floor_y)
            self.player.vx = 0
            self.player.vy = 0

    def draw_world(self):
        self.screen.fill(COLOR_BG)

        # 발판
        for p in self.platforms:
            if p is self.goal_rect:
                continue
            pygame.draw.rect(self.screen, COLOR_PLATFORM, p)

        # 박스 (색 다르게)
        for b in self.boxes:
            pygame.draw.rect(self.screen, COLOR_BOX, b)

        # 골
        pygame.draw.rect(self.screen, COLOR_GOAL, self.goal_rect, border_radius=8)

        # 플레이어
        self.player.draw(self.screen)

        # UI
        self.draw_ui()

    def draw_ui(self):
        lines = [
            "조작법",
            "A / ← : 왼쪽 이동",
            "D / → : 오른쪽 이동",
            "Space / W / ↑ : 점프 (바닥에 있을 때)",
            "",
            "→ 바닥 구멍 조심해서 점프하면서 올라가서",
            "   오른쪽 위 초록 발판 위에 서면 클리어!",
        ]
        x, y = 20, 20
        for line in lines:
            surf = self.font.render(line, True, COLOR_TEXT)
            self.screen.blit(surf, (x, y))
            y += 22

    def show_clear_screen(self):
        # 클리어 화면 2초 정도 보여주고 ESC / 창 닫기 시 종료
        timer = 0.0
        showing = True
        while showing and timer < 2.0:
            dt = self.clock.tick(FPS) / 1000.0
            timer += dt

            for event in pygame.event.get():
                if event.type == QUIT:
                    showing = False
                elif event.type == KEYDOWN and event.key == K_ESCAPE:
                    showing = False

            self.screen.fill((15, 20, 30))

            text1 = self.big_font.render("STAGE CLEAR!", True, COLOR_GOAL)
            text2 = self.font.render("플레이해줘서 고마워 💚 (ESC 또는 잠시 후 종료)", True, COLOR_TEXT)

            rect1 = text1.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 30))
            rect2 = text2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 30))

            self.screen.blit(text1, rect1)
            self.screen.blit(text2, rect2)

            pygame.display.flip()

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.step(dt)
            self.draw_world()
            pygame.display.flip()

        # 골 도달 시 클리어 화면 한 번 보여주기
        if self.goal_reached:
            self.show_clear_screen()

        pygame.quit()
        sys.exit(0)


# -----------------------------
# 실행
# -----------------------------

if __name__ == "__main__":
    GawonFallFlatGame().run()
