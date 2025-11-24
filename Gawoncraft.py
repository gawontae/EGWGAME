import pygame, sys, json, os, math

# ===============================
# Init
# ===============================
pygame.init()

WIDTH, HEIGHT = 960, 640
TILE = 32

SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Mini Minecraft 2D+ Step & Break")
CLOCK = pygame.time.Clock()
FPS = 60

# Colors
DAY_COLOR = (135, 206, 235)
NIGHT_COLOR = (10, 10, 40)

COLOR_HOTBAR_BG = (40, 40, 40)
COLOR_HOTBAR_BORDER = (220, 220, 220)
COLOR_HOTBAR_SELECTED = (255, 255, 0)

BLOCK_COLORS = {
    0: None,                # air
    1: (139, 69, 19),       # dirt
    2: (34, 139, 34),       # grass
    3: (100, 100, 100),     # stone
    4: (160, 82, 45),       # wood
    5: (34, 139, 84),       # leaves
}

BLOCK_NAME = {
    1: "Dirt",
    2: "Grass",
    3: "Stone",
    4: "Wood",
    5: "Leaves",
}

HOTBAR_SLOTS = [1, 2, 3, 4, 5]
selected_block_index = 0

FONT = pygame.font.Font(None, 20)     # 일반 UI
FONT_SMALL = pygame.font.Font(None, 16)  # 아래 설명 글씨 조금 더 작게

# ===============================
# World
# ===============================
WORLD_COLS = 200
WORLD_ROWS = 30
GROUND_LEVEL = 20

world = [[0 for _ in range(WORLD_COLS)] for _ in range(WORLD_ROWS)]

for y in range(GROUND_LEVEL, WORLD_ROWS):
    for x in range(WORLD_COLS):
        if y == GROUND_LEVEL:
            world[y][x] = 2  # grass
        elif y < GROUND_LEVEL + 3:
            world[y][x] = 1  # dirt
        else:
            world[y][x] = 3  # stone

# ===============================
# Player
# ===============================
player_width = 24
player_height = 40

spawn_x = WIDTH // 2
spawn_y = (GROUND_LEVEL - 2) * TILE

player_rect = pygame.Rect(spawn_x, spawn_y, player_width, player_height)
player_vx = 0.0
player_vy = 0.0

PLAYER_SPEED = 4
PLAYER_JUMP = -6    # 대략 1블럭 정도 올라가는 점프
GRAVITY = 0.5
MAX_FALL_SPEED = 18

player_facing = 1          # 1: right, -1: left
is_attacking = False
attack_timer = 0.0
ATTACK_DURATION = 0.18
ATTACK_RANGE = 32

camera_x = 0
camera_y = 0

max_health = 10
health = max_health
invincible_timer = 0.0

time_of_day = 0.25
TIME_SPEED = 0.02

mobs = []

# Block breaking (hold right mouse)
BREAK_TIME = 0.5           # hold time to break block
breaking = False
break_tx = None
break_ty = None
break_timer = 0.0


# ===============================
# Utils
# ===============================
def get_block_at(tx, ty):
    if 0 <= tx < WORLD_COLS and 0 <= ty < WORLD_ROWS:
        return world[ty][tx]
    return 0


def set_block_at(tx, ty, block_id):
    if 0 <= tx < WORLD_COLS and 0 <= ty < WORLD_ROWS:
        world[ty][tx] = block_id


def rect_collides_with_world(rect):
    collided_tiles = []

    left = rect.left // TILE
    right = rect.right // TILE
    top = rect.top // TILE
    bottom = rect.bottom // TILE

    for ty in range(top, bottom + 1):
        for tx in range(left, right + 1):
            block_id = get_block_at(tx, ty)
            if block_id != 0:
                tile_rect = pygame.Rect(tx * TILE, ty * TILE, TILE, TILE)
                if rect.colliderect(tile_rect):
                    collided_tiles.append(tile_rect)
    return collided_tiles


def move_and_collide(rect, vx, vy, max_step=TILE):
    """
    플레이어 이동 + 충돌 처리 + 1블럭 스텝 업.
    """
    # ----- Horizontal with step-up -----
    original_x = rect.x

    rect.x += vx
    collisions = rect_collides_with_world(rect)

    if collisions:
        # 계단 올라가기 시도: 위로 max_step 픽셀까지 올려보기
        step_rect = rect.copy()
        stepped = False
        for _ in range(max_step):
            step_rect.y -= 1
            if not rect_collides_with_world(step_rect):
                rect = step_rect
                stepped = True
                break
        if not stepped:
            # 계단 실패 → 원래 x로 롤백
            rect.x = original_x

    # ----- Vertical -----
    rect.y += vy
    on_ground = False
    collisions = rect_collides_with_world(rect)
    for tile in collisions:
        if vy > 0:
            rect.bottom = tile.top
            on_ground = True
            vy = 0
        elif vy < 0:
            rect.top = tile.bottom
            vy = 0

    return rect, vx, vy, on_ground


def world_to_screen(wx, wy):
    return wx - camera_x, wy - camera_y


def screen_to_world(sx, sy):
    return sx + camera_x, sy + camera_y


def lerp_color(c1, c2, t):
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def has_support_block(tx, ty):
    """
    해당 타일 주변(아래, 왼쪽, 오른쪽)에 블럭이 하나라도 있으면 True.
    → 공중에는 못 놓지만, 바닥/벽/기둥 주변엔 설치 가능.
    """
    neighbors = [
        (tx, ty + 1),
        (tx - 1, ty),
        (tx + 1, ty),
    ]
    for nx, ny in neighbors:
        if 0 <= nx < WORLD_COLS and 0 <= ny < WORLD_ROWS:
            if get_block_at(nx, ny) != 0:
                return True
    return False


# ===============================
# Mobs
# ===============================
def init_mobs():
    global mobs
    mobs = []
    for x_tile in (20, 60, 100, 150):
        rect = pygame.Rect(x_tile * TILE, 0, 26, 26)
        mobs.append({"rect": rect, "vx": 1})


def update_mobs(dt):
    for mob in mobs:
        rect = mob["rect"]
        vx = mob["vx"]

        rect.y += 10
        collisions = rect_collides_with_world(rect)
        for tile in collisions:
            rect.bottom = tile.top

        rect.x += vx
        collisions = rect_collides_with_world(rect)
        for tile in collisions:
            if vx > 0:
                rect.right = tile.left
            elif vx < 0:
                rect.left = tile.right
            vx = -vx
        mob["vx"] = vx
        mob["rect"] = rect


# ===============================
# Drawing
# ===============================
def draw_world(sky_color):
    SCREEN.fill(sky_color)

    start_tx = max(camera_x // TILE, 0)
    end_tx = min((camera_x + WIDTH) // TILE + 1, WORLD_COLS)
    start_ty = max(camera_y // TILE, 0)
    end_ty = min((camera_y + HEIGHT) // TILE + 1, WORLD_ROWS)

    for ty in range(start_ty, end_ty):
        for tx in range(start_tx, end_tx):
            block_id = world[ty][tx]
            color = BLOCK_COLORS.get(block_id)
            if color:
                wx = tx * TILE
                wy = ty * TILE
                sx, sy = world_to_screen(wx, wy)
                pygame.draw.rect(SCREEN, color, (sx, sy, TILE, TILE))


def draw_player():
    sx, sy = world_to_screen(player_rect.x, player_rect.y)

    pygame.draw.rect(SCREEN, (255, 228, 196), (sx, sy, player_rect.width, player_rect.height))
    head_rect = pygame.Rect(sx + 4, sy - 16, player_rect.width - 8, 16)
    pygame.draw.rect(SCREEN, (255, 224, 189), head_rect)
    hair_rect = pygame.Rect(head_rect.x, head_rect.y, head_rect.width, 8)
    pygame.draw.rect(SCREEN, (139, 69, 19), hair_rect)


def draw_attack():
    if not is_attacking:
        return

    if player_facing >= 0:
        ax = player_rect.right
    else:
        ax = player_rect.left - ATTACK_RANGE
    ay = player_rect.centery - 10

    sx, sy = world_to_screen(ax, ay)
    pygame.draw.rect(SCREEN, (255, 200, 0), (sx, sy, ATTACK_RANGE, 20), 2)


def get_attack_rect():
    if not is_attacking:
        return None
    if player_facing >= 0:
        ax = player_rect.right
    else:
        ax = player_rect.left - ATTACK_RANGE
    ay = player_rect.centery - 10
    return pygame.Rect(ax, ay, ATTACK_RANGE, 20)


def draw_mobs():
    for mob in mobs:
        rect = mob["rect"]
        sx, sy = world_to_screen(rect.x, rect.y)
        pygame.draw.rect(SCREEN, (120, 200, 120), (sx, sy, rect.width, rect.height))
        eye1 = pygame.Rect(sx + 5, sy + 6, 4, 4)
        eye2 = pygame.Rect(sx + rect.width - 9, sy + 6, 4, 4)
        pygame.draw.rect(SCREEN, (0, 0, 0), eye1)
        pygame.draw.rect(SCREEN, (0, 0, 0), eye2)


def draw_hotbar():
    bar_width = 300
    bar_height = 50
    bar_x = (WIDTH - bar_width) // 2
    bar_y = HEIGHT - bar_height - 16

    pygame.draw.rect(SCREEN, COLOR_HOTBAR_BG, (bar_x, bar_y, bar_width, bar_height))
    pygame.draw.rect(SCREEN, COLOR_HOTBAR_BORDER, (bar_x, bar_y, bar_width, bar_height), 2)

    slot_margin = 6
    slot_size = bar_height - slot_margin * 2

    for i, block_id in enumerate(HOTBAR_SLOTS):
        slot_x = bar_x + slot_margin + i * (slot_size + slot_margin)
        slot_y = bar_y + slot_margin
        slot_rect = pygame.Rect(slot_x, slot_y, slot_size, slot_size)

        if i == selected_block_index:
            pygame.draw.rect(SCREEN, COLOR_HOTBAR_SELECTED, slot_rect, 3)
        else:
            pygame.draw.rect(SCREEN, COLOR_HOTBAR_BORDER, slot_rect, 1)

        color = BLOCK_COLORS.get(block_id)
        if color:
            inner = slot_rect.inflate(-6, -6)
            pygame.draw.rect(SCREEN, color, inner)

    selected_block_id = HOTBAR_SLOTS[selected_block_index]
    name = BLOCK_NAME.get(selected_block_id, "Unknown")
    text = FONT.render(f"Block: {selected_block_id} ({name})", True, (0, 0, 0))
    SCREEN.blit(text, (bar_x, bar_y - 24))


def draw_crosshair():
    mx, my = pygame.mouse.get_pos()
    size = 8
    pygame.draw.line(SCREEN, (0, 0, 0), (mx - size, my), (mx + size, my), 1)
    pygame.draw.line(SCREEN, (0, 0, 0), (mx, my - size), (mx, my + size), 1)


def draw_health():
    x = 16
    y = 16
    w = 14
    h = 18
    gap = 4

    for i in range(max_health):
        rect = pygame.Rect(x + i * (w + gap), y, w, h)
        if i < health:
            pygame.draw.rect(SCREEN, (200, 0, 0), rect)
        pygame.draw.rect(SCREEN, (0, 0, 0), rect, 1)

    txt = FONT.render(f"HP: {health}/{max_health}", True, (0, 0, 0))
    SCREEN.blit(txt, (x, y + h + 4))


def draw_time_indicator():
    bar_width = 200
    bar_height = 10
    x = WIDTH - bar_width - 20
    y = 24

    pygame.draw.rect(SCREEN, (30, 30, 30), (x, y, bar_width, bar_height))
    pygame.draw.rect(SCREEN, (220, 220, 220), (x, y, bar_width, bar_height), 1)

    inner_width = int(bar_width * time_of_day)
    pygame.draw.rect(SCREEN, (250, 250, 120), (x, y, inner_width, bar_height))

    label = FONT.render("Day / Night", True, (0, 0, 0))
    SCREEN.blit(label, (x, y - 22))


def draw_paused_overlay():
    s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    s.fill((0, 0, 0, 160))
    SCREEN.blit(s, (0, 0))

    txt1 = FONT.render("PAUSED", True, (255, 255, 255))
    txt2 = FONT.render("Press ESC to resume", True, (230, 230, 230))

    SCREEN.blit(txt1, txt1.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 10)))
    SCREEN.blit(txt2, txt2.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 20)))


def draw_break_progress():
    if not breaking:
        return
    if break_tx is None or break_ty is None:
        return
    progress = max(0.0, min(1.0, break_timer / BREAK_TIME))
    wx = break_tx * TILE
    wy = break_ty * TILE
    sx, sy = world_to_screen(wx, wy)

    bar_width = TILE - 4
    bar_height = 4
    bx = sx + 2
    by = sy + TILE // 2 - 2

    pygame.draw.rect(SCREEN, (0, 0, 0), (bx, by, bar_width, bar_height), 1)
    inner = int(bar_width * progress)
    if inner > 2:
        pygame.draw.rect(SCREEN, (255, 255, 0), (bx + 1, by + 1, inner - 2, bar_height - 2))


# ===============================
# Save / Load / Respawn
# ===============================
def save_world(filename="world_save.json"):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(world, f)
        print("World saved to", filename)
    except Exception as e:
        print("Save failed:", e)


def load_world(filename="world_save.json"):
    global world
    if not os.path.exists(filename):
        print("No save file")
        return
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            world = data
            print("World loaded from", filename)
    except Exception as e:
        print("Load failed:", e)


def respawn():
    global player_rect, player_vx, player_vy, health
    player_rect.x = spawn_x
    player_rect.y = spawn_y
    player_vx = 0
    player_vy = 0
    health = max_health


# ===============================
# Main Loop
# ===============================
def main():
    global selected_block_index, player_rect, player_vx, player_vy, camera_x, camera_y
    global invincible_timer, time_of_day, health
    global is_attacking, attack_timer, player_facing
    global breaking, break_tx, break_ty, break_timer

    init_mobs()
    paused = False
    on_ground = False
    running = True

    while running:
        dt_ms = CLOCK.tick(FPS)
        dt = dt_ms / 1000.0

        mx, my = pygame.mouse.get_pos()
        wx, wy = screen_to_world(mx, my)
        tx = wx // TILE
        ty = wy // TILE

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    paused = not paused

                if not paused:
                    if event.key == pygame.K_1:
                        selected_block_index = 0
                    elif event.key == pygame.K_2 and len(HOTBAR_SLOTS) >= 2:
                        selected_block_index = 1
                    elif event.key == pygame.K_3 and len(HOTBAR_SLOTS) >= 3:
                        selected_block_index = 2
                    elif event.key == pygame.K_4 and len(HOTBAR_SLOTS) >= 4:
                        selected_block_index = 3
                    elif event.key == pygame.K_5 and len(HOTBAR_SLOTS) >= 5:
                        selected_block_index = 4

                    if event.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                        if on_ground:
                            player_vy = PLAYER_JUMP

                    if event.key == pygame.K_F5:
                        save_world()
                    if event.key == pygame.K_F9:
                        load_world()

                    if event.key == pygame.K_f:
                        if not is_attacking:
                            is_attacking = True
                            attack_timer = ATTACK_DURATION

            if not paused and event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # left click: place block
                    mx_e, my_e = event.pos
                    wx_e, wy_e = screen_to_world(mx_e, my_e)
                    tx_e = wx_e // TILE
                    ty_e = wy_e // TILE

                    player_center_tx = player_rect.centerx // TILE

                    # 플레이어 기준 좌우 1칸, 타일은 비어있고,
                    # 주변(아래/왼쪽/오른쪽) 어딘가에 블럭이 있어야 설치 가능
                    if (
                        0 <= tx_e < WORLD_COLS and
                        0 <= ty_e < WORLD_ROWS and
                        get_block_at(tx_e, ty_e) == 0 and
                        abs(tx_e - player_center_tx) <= 1 and
                        has_support_block(tx_e, ty_e)
                    ):
                        block_rect = pygame.Rect(tx_e * TILE, ty_e * TILE, TILE, TILE)
                        if not player_rect.colliderect(block_rect):
                            selected_block_id = HOTBAR_SLOTS[selected_block_index]
                            set_block_at(tx_e, ty_e, selected_block_id)

        # Block breaking (hold right mouse)
        if not paused:
            mouse_buttons = pygame.mouse.get_pressed()
            if mouse_buttons[2]:  # right button held
                if (
                    0 <= tx < WORLD_COLS and
                    0 <= ty < WORLD_ROWS and
                    get_block_at(tx, ty) != 0
                ):
                    if not breaking or break_tx != tx or break_ty != ty:
                        breaking = True
                        break_tx, break_ty = tx, ty
                        break_timer = 0.0
                    else:
                        break_timer += dt
                        if break_timer >= BREAK_TIME:
                            set_block_at(tx, ty, 0)
                            breaking = False
                            break_tx = break_ty = None
                            break_timer = 0.0
                else:
                    breaking = False
                    break_tx = break_ty = None
                    break_timer = 0.0
            else:
                breaking = False
                break_tx = break_ty = None
                break_timer = 0.0

        if paused:
            sky_t = (math.sin(time_of_day * 2 * math.pi - math.pi / 2) + 1) / 2
            sky_color = lerp_color(NIGHT_COLOR, DAY_COLOR, sky_t)

            draw_world(sky_color)
            draw_mobs()
            draw_player()
            draw_attack()
            draw_hotbar()
            draw_crosshair()
            draw_health()
            draw_time_indicator()
            draw_break_progress()
            draw_paused_overlay()
            pygame.display.flip()
            continue

        keys = pygame.key.get_pressed()
        player_vx = 0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            player_vx = -PLAYER_SPEED
            player_facing = -1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            player_vx = PLAYER_SPEED
            player_facing = 1

        player_vy += GRAVITY
        if player_vy > MAX_FALL_SPEED:
            player_vy = MAX_FALL_SPEED

        prev_vy = player_vy
        player_rect, player_vx, player_vy, on_ground = move_and_collide(
            player_rect, player_vx, player_vy
        )

        if on_ground and prev_vy > 14:
            dmg = min(max_health, int((prev_vy - 14) // 2) + 1)
            if dmg > 0:
                health -= dmg
                if health <= 0:
                    respawn()

        camera_x = player_rect.centerx - WIDTH // 2
        camera_y = player_rect.centery - HEIGHT // 2

        max_cam_x = WORLD_COLS * TILE - WIDTH
        max_cam_y = WORLD_ROWS * TILE - HEIGHT

        camera_x = max(0, min(camera_x, max_cam_x))
        camera_y = max(0, min(camera_y, max_cam_y))

        time_of_day += TIME_SPEED * dt
        if time_of_day > 1.0:
            time_of_day -= 1.0

        sky_t = (math.sin(time_of_day * 2 * math.pi - math.pi / 2) + 1) / 2
        sky_color = lerp_color(NIGHT_COLOR, DAY_COLOR, sky_t)

        if invincible_timer > 0:
            invincible_timer -= dt
            if invincible_timer < 0:
                invincible_timer = 0

        if is_attacking:
            attack_timer -= dt
            if attack_timer <= 0:
                is_attacking = False

        update_mobs(dt)

        if is_attacking:
            atk_rect = get_attack_rect()
            if atk_rect:
                to_remove = []
                for mob in mobs:
                    if mob["rect"].colliderect(atk_rect):
                        to_remove.append(mob)
                for m in to_remove:
                    if m in mobs:
                        mobs.remove(m)

        for mob in mobs:
            if player_rect.colliderect(mob["rect"]):
                if invincible_timer <= 0:
                    health -= 1
                    invincible_timer = 1.0
                    if health <= 0:
                        respawn()

        draw_world(sky_color)
        draw_mobs()
        draw_player()
        draw_attack()
        draw_hotbar()
        draw_crosshair()
        draw_health()
        draw_time_indicator()
        draw_break_progress()

        instr = FONT_SMALL.render(
            "Move: A/D or arrows | Jump: W/Up/Space | Attack: F | Place: LMB (side 1 tile) | Hold RMB to break | Save: F5 | Load: F9 | Pause: ESC",
            True, (0, 0, 0)
        )
        SCREEN.blit(instr, (20, HEIGHT - 80))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
