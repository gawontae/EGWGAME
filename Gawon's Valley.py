import pygame
import sys

# ==============================
# Mini Stardew-like Farm Game
# (Wide, Polished, Crop Sprites)
# ==============================

pygame.init()

# ------- 기본 설정 -------
TILE_SIZE = 32
GRID_WIDTH = 26          # 가로 넓게
GRID_HEIGHT = 15
HUD_HEIGHT = 200
TOWN_COLS = 6            # 오른쪽 마을(길+집) 칸 수
TOWN_START_COL = GRID_WIDTH - TOWN_COLS

SCREEN_WIDTH = TILE_SIZE * GRID_WIDTH
SCREEN_HEIGHT = TILE_SIZE * GRID_HEIGHT + HUD_HEIGHT

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Mini Stardew Farm Plus (Python)")

clock = pygame.time.Clock()

# 폰트: 말굽고딕 없으면 기본 폰트
try:
    FONT = pygame.font.SysFont("malgungothic", 18)
    FONT_SMALL = pygame.font.SysFont("malgungothic", 14)
except:
    FONT = pygame.font.SysFont(None, 18)
    FONT_SMALL = pygame.font.SysFont(None, 14)

# ------- 색상 정의 -------
COLOR_HUD_BG = (24, 28, 52)
COLOR_HUD_BORDER = (80, 90, 140)
COLOR_WHITE = (255, 255, 255)
COLOR_YELLOW = (255, 230, 120)

COLOR_GRASS_DAY = (90, 155, 90)
COLOR_GRASS_NIGHT = (24, 60, 36)
COLOR_TILLED = (110, 80, 55)

TILE_EMPTY = 0
TILE_TILLED = 1
TILE_PLANTED = 2
TILE_GROWN = 3


# ==============================
# 데이터 구조
# ==============================
class CropType:
    def __init__(self, name, kr_name, growth_days, buy_price, sell_price,
                 color_main):
        self.name = name
        self.kr_name = kr_name
        self.growth_days = growth_days
        self.buy_price = buy_price
        self.sell_price = sell_price
        self.color_main = color_main


CROP_TYPES = [
    CropType("Turnip", "무", 2, 10, 20, (240, 240, 250)),   # 흰색 뿌리
    CropType("Potato", "감자", 3, 20, 40, (180, 135, 80)),  # 갈색
    CropType("Pumpkin", "호박", 5, 40, 90, (245, 150, 60)), # 주황
]


class Tile:
    def __init__(self):
        self.state = TILE_EMPTY
        self.growth_progress = 0.0   # 0~1
        self.crop_type = None

    def till(self):
        if self.state == TILE_EMPTY:
            self.state = TILE_TILLED

    def plant(self, crop_idx):
        if self.state == TILE_TILLED:
            self.state = TILE_PLANTED
            self.growth_progress = 0.0
            self.crop_type = crop_idx

    def grow(self, days_amount, required_days):
        if self.state == TILE_PLANTED and self.crop_type is not None:
            if required_days <= 0:
                required_days = 1
            self.growth_progress += days_amount / float(required_days)
            if self.growth_progress >= 1.0:
                self.growth_progress = 1.0
                self.state = TILE_GROWN

    def harvest(self):
        if self.state == TILE_GROWN:
            crop_idx = self.crop_type
            self.state = TILE_TILLED
            self.growth_progress = 0.0
            self.crop_type = None
            return crop_idx
        return None


class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.gold = 100
        self.seed_inventory = [5, 3, 1]  # 무, 감자, 호박
        self.selected_seed = 0
        self.farming_xp = 0
        self.farming_level = 1

    def move(self, dx, dy):
        nx = self.x + dx
        ny = self.y + dy
        if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
            self.x = nx
            self.y = ny

    def add_xp(self, amount=1):
        self.farming_xp += amount
        need = self.farming_level * 5
        if self.farming_xp >= need:
            self.farming_xp -= need
            self.farming_level += 1
            return True
        return False


class Quest:
    def __init__(self, title, desc, target_crop_idx, target_count, reward_gold):
        self.title = title
        self.desc = desc
        self.target_crop_idx = target_crop_idx
        self.target_count = target_count
        self.reward_gold = reward_gold
        self.progress = 0
        self.completed = False
        self.reward_given = False

    def on_harvest(self, crop_idx):
        if self.completed:
            return False
        if crop_idx == self.target_crop_idx:
            self.progress += 1
            if self.progress >= self.target_count:
                self.completed = True
                return True
        return False


# ==============================
# 메인 게임 클래스
# ==============================
class FarmGame:
    def __init__(self):
        self.tiles = [[Tile() for _ in range(GRID_HEIGHT)]
                      for _ in range(GRID_WIDTH)]
        self.player = Player(GRID_WIDTH // 2 - 2, GRID_HEIGHT // 2)

        self.day = 1
        self.time_minutes = 480.0
        self.TIME_SPEED = 240.0
        self.running = True

        self.npc_pos = (GRID_WIDTH - TOWN_COLS // 2 - 1, GRID_HEIGHT // 2 + 1)
        self.shop_open = False

        self.quests = [
            Quest("첫 수확", "무 5개 수확하기", 0, 5, 100)
        ]
        self.active_quest = self.quests[0]
        self.notification = ""
        self.notification_timer = 0.0

    # ---------- 유틸 ----------
    def lerp_color(self, c1, c2, t):
        t = max(0.0, min(1.0, t))
        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )

    # ---------- 시간 & 성장 ----------
    def update_time_and_growth(self, dt):
        if self.shop_open:
            return

        minutes_passed = dt * self.TIME_SPEED
        self.time_minutes += minutes_passed
        days_passed = minutes_passed / 1440.0

        if days_passed > 0:
            self.advance_growth(days_passed)

        while self.time_minutes >= 1440.0:
            self.time_minutes -= 1440.0
            self.day += 1

    def get_time_str(self):
        total = int(self.time_minutes)
        h = (total // 60) % 24
        m = total % 60
        return f"{h:02d}:{m:02d}"

    def get_day_night_factor(self):
        t = self.time_minutes
        if 600 <= t <= 1080:
            return 1.0
        if t < 300 or t > 1260:
            return 0.0
        if 300 <= t < 600:
            return (t - 300) / 300.0
        if 1080 < t <= 1260:
            return 1.0 - (t - 1080) / 180.0
        return 0.3

    def get_crop_growth_days(self, crop_idx):
        base = CROP_TYPES[crop_idx].growth_days
        reduction = (self.player.farming_level - 1) // 2
        return max(1, base - reduction)

    def advance_growth(self, days_amount):
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                tile = self.tiles[x][y]
                if tile.state == TILE_PLANTED and tile.crop_type is not None:
                    need = self.get_crop_growth_days(tile.crop_type)
                    tile.grow(days_amount, need)

    def fast_forward_one_day(self):
        self.day += 1
        self.advance_growth(1.0)
        self.time_minutes = 480.0

    def get_crop_sell_price(self, crop_idx):
        base = CROP_TYPES[crop_idx].sell_price
        bonus = 1.0 + (self.player.farming_level - 1) * 0.1
        return int(base * bonus)

    # ---------- 행동 ----------
    def handle_action(self):
        tile = self.tiles[self.player.x][self.player.y]

        if tile.state == TILE_GROWN:
            crop_idx = tile.harvest()
            if crop_idx is not None:
                gain = self.get_crop_sell_price(crop_idx)
                self.player.gold += gain

                if self.active_quest is not None:
                    finished = self.active_quest.on_harvest(crop_idx)
                    if finished:
                        self.notification = (
                            f"[퀘스트 완료] {self.active_quest.title} "
                            f"(+{self.active_quest.reward_gold}G)"
                        )
                        self.notification_timer = 3.0
                        if not self.active_quest.reward_given:
                            self.player.gold += self.active_quest.reward_gold
                            self.active_quest.reward_given = True

                leveled = self.player.add_xp(1)
                if leveled:
                    self.notification = f"[레벨 업] 농사 레벨 {self.player.farming_level}!"
                    self.notification_timer = 3.0
            return

        if tile.state == TILE_EMPTY:
            tile.till()
            return

        if tile.state == TILE_TILLED:
            idx = self.player.selected_seed
            if 0 <= idx < len(self.player.seed_inventory) and self.player.seed_inventory[idx] > 0:
                tile.plant(idx)
                self.player.seed_inventory[idx] -= 1

    # ---------- 입력 ----------
    def handle_events(self, dt):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.shop_open:
                        self.shop_open = False
                    else:
                        self.running = False

                elif self.shop_open:
                    if event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                        idx = event.key - pygame.K_1
                        if 0 <= idx < len(CROP_TYPES):
                            crop = CROP_TYPES[idx]
                            if self.player.gold >= crop.buy_price:
                                self.player.gold -= crop.buy_price
                                self.player.seed_inventory[idx] += 1
                                self.notification = f"{crop.kr_name} 씨앗 구매! (-{crop.buy_price}G)"
                                self.notification_timer = 2.0
                            else:
                                self.notification = "골드가 부족합니다!"
                                self.notification_timer = 2.0
                    elif event.key == pygame.K_e:
                        self.shop_open = False

                else:
                    if event.key == pygame.K_LEFT:
                        self.player.move(-1, 0)
                    elif event.key == pygame.K_RIGHT:
                        self.player.move(1, 0)
                    elif event.key == pygame.K_UP:
                        self.player.move(0, -1)
                    elif event.key == pygame.K_DOWN:
                        self.player.move(0, 1)
                    elif event.key == pygame.K_SPACE:
                        self.handle_action()
                    elif event.key == pygame.K_n:
                        self.fast_forward_one_day()
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                        idx = event.key - pygame.K_1
                        if 0 <= idx < len(CROP_TYPES):
                            self.player.selected_seed = idx
                    elif event.key == pygame.K_e:
                        if self.is_near_npc():
                            self.shop_open = True

    # ---------- NPC ----------
    def is_near_npc(self):
        px, py = self.player.x, self.player.y
        nx, ny = self.npc_pos
        return abs(px - nx) <= 1 and abs(py - ny) <= 1

    # ---------- 하늘 ----------
    def draw_sky(self, surface, factor):
        top_day = (40, 70, 130)
        bot_day = (135, 190, 255)
        top_night = (5, 10, 25)
        bot_night = (25, 40, 70)

        c1 = self.lerp_color(top_night, top_day, factor)
        c2 = self.lerp_color(bot_night, bot_day, factor)

        h = TILE_SIZE * GRID_HEIGHT
        for y in range(h):
            t = y / float(h)
            col = self.lerp_color(c1, c2, t)
            pygame.draw.line(surface, col, (0, y), (SCREEN_WIDTH, y))

    # ---------- 작물 스프라이트 ----------
    def draw_crop_sprite(self, surface, rect, tile):
        crop = CROP_TYPES[tile.crop_type]
        progress = max(0.1, min(1.0, tile.growth_progress if tile.state == TILE_PLANTED else 1.0))

        cx = rect.centerx
        cy = rect.centery

        # 기본: 흙 위에 심어져 있으므로, 씨앗/줄기 작은 것부터 시작
        # progress에 따라 크기 스케일
        max_radius = TILE_SIZE // 2 - 6
        radius = int(max_radius * progress)

        if tile.crop_type == 0:  # 무
            # 잎
            leaf_height = int(radius * 0.7)
            leaf_rect = pygame.Rect(0, 0, radius * 2 // 3, leaf_height)
            leaf_rect.midbottom = (cx, cy - radius + 4)
            pygame.draw.ellipse(surface, (60, 150, 70), leaf_rect)
            # 뿌리
            pygame.draw.circle(surface, crop.color_main, (cx, cy), radius)
            tri = [
                (cx - radius // 2, cy + radius // 2),
                (cx + radius // 2, cy + radius // 2),
                (cx, cy + radius),
            ]
            pygame.draw.polygon(surface, crop.color_main, tri)

        elif tile.crop_type == 1:  # 감자
            body_rect = pygame.Rect(0, 0, radius * 2, int(radius * 1.4))
            body_rect.center = (cx, cy)
            pygame.draw.ellipse(surface, crop.color_main, body_rect)
            # 살짝 점박이
            for dx in (-4, 3, 0):
                pygame.draw.circle(surface, (150, 110, 60),
                                   (body_rect.centerx + dx, body_rect.centery - 3),
                                   2)

            # 위에 작은 잎
            leaf_rect = pygame.Rect(0, 0, radius, radius // 2)
            leaf_rect.midbottom = (cx, body_rect.top + 4)
            pygame.draw.ellipse(surface, (70, 140, 70), leaf_rect)

        elif tile.crop_type == 2:  # 호박
            body_rect = pygame.Rect(0, 0, radius * 2, radius * 2)
            body_rect.center = (cx, cy)
            pygame.draw.ellipse(surface, crop.color_main, body_rect)

            # 줄무늬
            stripe_color = (225, 120, 40)
            for offset in (-radius // 2, 0, radius // 2):
                x = body_rect.centerx + offset
                pygame.draw.line(surface, stripe_color,
                                 (x, body_rect.top + 3),
                                 (x, body_rect.bottom - 3), 2)

            # 꼭지 & 잎
            stem_rect = pygame.Rect(0, 0, 6, 8)
            stem_rect.midbottom = (body_rect.centerx, body_rect.top + 3)
            pygame.draw.rect(surface, (80, 110, 50), stem_rect)
            leaf_rect = pygame.Rect(0, 0, radius, radius // 2)
            leaf_rect.midbottom = (body_rect.centerx - radius // 4,
                                   body_rect.top + 6)
            pygame.draw.ellipse(surface, (70, 150, 70), leaf_rect)

    # ---------- 타일(밭/길) ----------
    def draw_tiles(self, surface, grass_factor):
        for x in range(GRID_WIDTH):
            for y in range(GRID_HEIGHT):
                tile = self.tiles[x][y]
                rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)

                # 오른쪽 마을 타일은 돌길, 나머지는 잔디
                if x >= TOWN_START_COL:
                    base = (140, 140, 150)
                    alt = (130, 130, 140)
                else:
                    day = COLOR_GRASS_DAY
                    night = COLOR_GRASS_NIGHT
                    base_grass = self.lerp_color(night, day, grass_factor)
                    base = base_grass
                    alt = (max(base_grass[0] - 8, 0),
                           max(base_grass[1] - 8, 0),
                           max(base_grass[2] - 8, 0))

                use_base = ((x + y) % 2 == 0)
                tile_bg = base if use_base else alt

                # 밭(갈린 땅) 배경
                if tile.state in (TILE_TILLED, TILE_PLANTED, TILE_GROWN):
                    tile_bg = COLOR_TILLED

                pygame.draw.rect(surface, tile_bg, rect)
                inner = rect.inflate(-4, -4)
                pygame.draw.rect(surface, (0, 0, 0), inner, 1)

                # 작물 스프라이트
                if tile.state in (TILE_PLANTED, TILE_GROWN) and tile.crop_type is not None:
                    self.draw_crop_sprite(surface, rect, tile)

    # ---------- 플레이어 ----------
    def draw_player(self, surface):
        px = self.player.x * TILE_SIZE + TILE_SIZE // 2
        py = self.player.y * TILE_SIZE + TILE_SIZE // 2

        shadow_rect = pygame.Rect(0, 0, TILE_SIZE - 10, TILE_SIZE // 3)
        shadow_rect.center = (px, py + TILE_SIZE // 3)
        pygame.draw.ellipse(surface, (0, 0, 0, 120), shadow_rect)

        body_rect = pygame.Rect(0, 0, TILE_SIZE - 12, TILE_SIZE - 8)
        body_rect.midbottom = (px, py + 4)
        pygame.draw.rect(surface, (40, 60, 120), body_rect, border_radius=6)

        head_radius = TILE_SIZE // 2 - 6
        head_center = (px, body_rect.top)
        pygame.draw.circle(surface, (245, 230, 190), head_center, head_radius)

        eye_y = body_rect.top - 4
        pygame.draw.circle(surface, (0, 0, 0), (px - 4, eye_y), 3)
        pygame.draw.circle(surface, (0, 0, 0), (px + 4, eye_y), 3)
        pygame.draw.arc(surface, (0, 0, 0),
                        (px - 6, eye_y + 3, 12, 8),
                        3.14, 0, 1)

    # ---------- 집 + NPC ----------
    def draw_npc_and_town(self, surface):
        town_x = TOWN_START_COL * TILE_SIZE
        town_width = TOWN_COLS * TILE_SIZE

        house_width = town_width - 40
        house_rect = pygame.Rect(town_x + 20, 24, house_width, TILE_SIZE * 3)
        pygame.draw.rect(surface, (190, 135, 95), house_rect, border_radius=4)
        roof = [
            (house_rect.left, house_rect.top),
            (house_rect.right, house_rect.top),
            ((house_rect.left + house_rect.right) // 2, house_rect.top - 28),
        ]
        pygame.draw.polygon(surface, (150, 70, 70), roof)

        door = pygame.Rect(0, 0, 24, 32)
        door.midbottom = (house_rect.centerx, house_rect.bottom)
        pygame.draw.rect(surface, (90, 60, 40), door, border_radius=3)

        win = pygame.Rect(house_rect.left + 18, house_rect.top + 18, 22, 22)
        pygame.draw.rect(surface, (220, 240, 255), win, border_radius=4)

        nx, ny = self.npc_pos
        cx = nx * TILE_SIZE + TILE_SIZE // 2
        cy = ny * TILE_SIZE + TILE_SIZE // 2

        glow = pygame.Surface((TILE_SIZE * 2, TILE_SIZE * 2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (180, 210, 255, 110),
                           (TILE_SIZE, TILE_SIZE), TILE_SIZE // 2 + 4)
        surface.blit(glow, (cx - TILE_SIZE, cy - TILE_SIZE))

        pygame.draw.circle(surface, (210, 225, 255), (cx, cy), TILE_SIZE // 2 - 4)
        name_text = FONT_SMALL.render("상점 주인", True, COLOR_WHITE)
        surface.blit(name_text, (cx - name_text.get_width() // 2, cy - TILE_SIZE))

        if self.is_near_npc() and not self.shop_open:
            hint = FONT_SMALL.render("E: 대화 / 상점 열기", True, COLOR_YELLOW)
            surface.blit(hint, (cx - hint.get_width() // 2, cy + TILE_SIZE // 2))

    # ---------- HUD ----------
    def draw_hud(self, surface):
        hud_top = SCREEN_HEIGHT - HUD_HEIGHT
        hud_rect = pygame.Rect(0, hud_top, SCREEN_WIDTH, HUD_HEIGHT)

        pygame.draw.rect(surface, COLOR_HUD_BG, hud_rect)
        pygame.draw.line(surface, COLOR_HUD_BORDER,
                         (0, hud_top), (SCREEN_WIDTH, hud_top), 2)

        # 왼쪽: 날짜/시간/골드
        y = hud_top + 16
        surface.blit(FONT.render(f"Day {self.day}", True, COLOR_YELLOW), (16, y))
        y += 26
        surface.blit(FONT.render(f"시간 {self.get_time_str()}", True, COLOR_WHITE), (16, y))
        y += 26
        surface.blit(FONT.render(f"Gold: {self.player.gold}", True, COLOR_WHITE), (16, y))

        # 가운데: 씨앗/레벨
        seed_x_title = 260
        seed_y = hud_top + 16
        surface.blit(FONT.render("Seed (1~3 선택):", True, COLOR_WHITE),
                     (seed_x_title, seed_y))

        seed_list_x = seed_x_title + 180
        for i, crop in enumerate(CROP_TYPES):
            txt = f"{i+1}:{crop.kr_name} x{self.player.seed_inventory[i]}"
            color = COLOR_YELLOW if i == self.player.selected_seed else COLOR_WHITE
            surface.blit(FONT_SMALL.render(txt, True, color),
                         (seed_list_x, seed_y + 22 * i))

        lvl_text = FONT_SMALL.render(
            f"농사 Lv.{self.player.farming_level}  XP "
            f"{self.player.farming_xp}/{self.player.farming_level*5}",
            True, COLOR_WHITE
        )
        surface.blit(lvl_text, (seed_x_title, hud_top + 16 + 22 * 3))

        # 오른쪽: 퀘스트
        if self.active_quest:
            q = self.active_quest
            qx = SCREEN_WIDTH - 280
            qy = hud_top + 16
            surface.blit(FONT_SMALL.render("[퀘스트]", True, COLOR_YELLOW),
                         (qx, qy))
            qy += 20
            surface.blit(FONT_SMALL.render(q.title, True, COLOR_WHITE),
                         (qx, qy))
            qy += 20
            surface.blit(FONT_SMALL.render(q.desc, True, COLOR_WHITE),
                         (qx, qy))
            qy += 20
            prog = f"진행: {q.progress}/{q.target_count}  보상: {q.reward_gold}G"
            surface.blit(FONT_SMALL.render(prog, True, COLOR_WHITE),
                         (qx, qy))

        # 맨 아래: 조작법
        controls_y1 = hud_top + HUD_HEIGHT - 48
        controls_y2 = hud_top + HUD_HEIGHT - 26
        controls1 = FONT_SMALL.render(
            "←↑↓→ 이동   SPACE 작업(갈기/심기/수확)   N 잠자기(다음날)",
            True, COLOR_WHITE
        )
        controls2 = FONT_SMALL.render(
            "E NPC 상점   ESC 종료/상점닫기",
            True, COLOR_WHITE
        )
        surface.blit(controls1, (16, controls_y1))
        surface.blit(controls2, (16, controls_y2))

        if self.notification and self.notification_timer > 0:
            note = FONT.render(self.notification, True, COLOR_YELLOW)
            surface.blit(note,
                         (SCREEN_WIDTH - note.get_width() - 20,
                          hud_top + 16))

    # ---------- 상점 ----------
    def draw_shop(self, surface):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))

        w, h = 520, 260
        rect = pygame.Rect((SCREEN_WIDTH - w) // 2,
                           (SCREEN_HEIGHT - h) // 2, w, h)
        pygame.draw.rect(surface, (48, 52, 90), rect, border_radius=12)
        pygame.draw.rect(surface, (200, 210, 255), rect, 2, border_radius=12)

        title = FONT.render("씨앗 상점", True, COLOR_YELLOW)
        surface.blit(title,
                     (rect.centerx - title.get_width() // 2,
                      rect.top + 10))

        desc = FONT_SMALL.render(
            "1~3 키로 씨앗 구매, E 또는 ESC로 닫기", True, COLOR_WHITE)
        surface.blit(desc,
                     (rect.centerx - desc.get_width() // 2,
                      rect.top + 40))

        y = rect.top + 80
        for i, crop in enumerate(CROP_TYPES):
            line = (
                f"{i+1}. {crop.kr_name} 씨앗  "
                f"가격:{crop.buy_price}G  "
                f"성장:{crop.growth_days}일  "
                f"기본 판매가:{crop.sell_price}G"
            )
            txt = FONT_SMALL.render(line, True, COLOR_WHITE)
            surface.blit(txt, (rect.left + 30, y))
            y += 30

        gold_txt = FONT_SMALL.render(
            f"현재 Gold: {self.player.gold}", True, COLOR_YELLOW)
        surface.blit(gold_txt, (rect.left + 30, rect.bottom - 40))

    # ---------- 업데이트 & 그리기 ----------
    def update(self, dt):
        self.update_time_and_growth(dt)
        if self.notification_timer > 0:
            self.notification_timer -= dt
            if self.notification_timer <= 0:
                self.notification = ""

    def draw(self):
        factor = self.get_day_night_factor()
        self.draw_sky(screen, factor)
        self.draw_tiles(screen, factor)
        self.draw_npc_and_town(screen)
        self.draw_player(screen)
        self.draw_hud(screen)
        if self.shop_open:
            self.draw_shop(screen)
        pygame.display.flip()

    # ---------- 메인 루프 ----------
    def run(self):
        while self.running:
            dt = clock.tick(60) / 1000.0
            self.handle_events(dt)
            self.update(dt)
            self.draw()


# ==============================
# 실행
# ==============================
def main():
    game = FarmGame()
    game.run()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
