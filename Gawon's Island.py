import tkinter as tk
from tkinter import ttk
import time
import math
import random


# ------------------ 게임 로직 ------------------ #

class BuildingType:
    def __init__(self, name, desc, base_cost, cost_multiplier, prod_per_sec, prod_resource, cost_resource="gold", color="#cfa46a"):
        self.name = name
        self.desc = desc
        self.base_cost = base_cost
        self.cost_multiplier = cost_multiplier
        self.prod_per_sec = prod_per_sec
        self.prod_resource = prod_resource
        self.cost_resource = cost_resource
        self.color = color  # 섬 위에 그릴 건물 색

    def get_cost(self, owned_count):
        return math.floor(self.base_cost * (self.cost_multiplier ** owned_count))


class GameState:
    def __init__(self):
        self.resources = {
            "gold": 50.0,
            "wood": 0.0,
            "stone": 0.0,
        }
        # {건물 이름: 개수}
        self.buildings = {}
        self.last_update = time.time()

    def update(self, building_types, elapsed=None):
        """경과 시간만큼 자원 생산"""
        now = time.time()
        if elapsed is None:
            elapsed = now - self.last_update
        if elapsed <= 0:
            self.last_update = now
            return

        for bt in building_types:
            count = self.buildings.get(bt.name, 0)
            if count <= 0:
                continue
            gain = bt.prod_per_sec * count * elapsed
            self.resources[bt.prod_resource] = self.resources.get(bt.prod_resource, 0.0) + gain

        self.last_update = now

    def add_building(self, building_name):
        self.buildings[building_name] = self.buildings.get(building_name, 0) + 1

    def can_afford(self, res_name, amount):
        return self.resources.get(res_name, 0.0) >= amount

    def spend(self, res_name, amount):
        if not self.can_afford(res_name, amount):
            return False
        self.resources[res_name] -= amount
        return True


# ------------------ GUI ------------------ #

class IdleIslandGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Ropuka's Idle Island - Python GUI Island Ver.")
        self.root.geometry("950x600")
        self.root.configure(bg="#f3efe2")

        # ttk 스타일
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("맑은 고딕", 18, "bold"), background="#f3efe2")
        style.configure("Subtitle.TLabel", font=("맑은 고딕", 10), background="#f3efe2")
        style.configure("ResourceName.TLabel", font=("맑은 고딕", 10, "bold"), background="#383b44", foreground="white")
        style.configure("ResourceVal.TLabel", font=("맑은 고딕", 11, "bold"), background="#383b44", foreground="#ffe27a")
        style.configure("Panel.TLabelframe", background="#f8f5ec")
        style.configure("Panel.TLabelframe.Label", font=("맑은 고딕", 11, "bold"))
        style.configure("Small.TLabel", font=("맑은 고딕", 9), background="#f8f5ec")
        style.configure("Buy.TButton", font=("맑은 고딕", 10, "bold"))
        style.configure("TButton", padding=4)

        # 게임 상태 & 건물 정의
        self.state = GameState()
        self.building_types = [
            BuildingType(
                name="금광",
                desc="섬 깊은 곳에서 금을 캐내는 광산",
                base_cost=10,
                cost_multiplier=1.15,
                prod_per_sec=1.0,
                prod_resource="gold",
                color="#f4d35e",
            ),
            BuildingType(
                name="제재소",
                desc="섬의 나무를 잘라 목재를 생산",
                base_cost=30,
                cost_multiplier=1.17,
                prod_per_sec=0.8,
                prod_resource="wood",
                color="#8fb339",
            ),
            BuildingType(
                name="채석장",
                desc="바위 절벽에서 돌을 채굴",
                base_cost=50,
                cost_multiplier=1.20,
                prod_per_sec=0.5,
                prod_resource="stone",
                color="#a0a4b8",
            ),
        ]

        # UI 변수
        self.resource_vars = {k: tk.StringVar() for k in ["gold", "wood", "stone"]}
        self.building_count_vars = {}
        self.building_cost_vars = {}
        self.message_var = tk.StringVar()

        # 섬 위 건물 배치 좌표 저장용
        self.island_building_positions = {bt.name: [] for bt in self.building_types}

        self._build_ui()
        self.refresh_ui()

        # 주기 업데이트
        self.last_loop_time = time.time()
        self.game_loop()

    # ---------- UI 구성 ---------- #
    def _build_ui(self):
        # 상단 제목
        top = ttk.Frame(self.root, style="Panel.TLabelframe")
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=6)

        ttk.Label(top, text="Ropuka's Idle Island", style="Title.TLabel").pack(anchor="center")
        ttk.Label(
            top,
            text="섬에 건물을 지어 골드 / 목재 / 돌을 모으는 방치형 미니 버전",
            style="Subtitle.TLabel",
        ).pack(anchor="center", pady=(2, 4))

        # 자원 바
        resource_bar = tk.Frame(self.root, bg="#383b44")
        resource_bar.pack(side=tk.TOP, fill=tk.X)

        for name in ["gold", "wood", "stone"]:
            frame = tk.Frame(resource_bar, bg="#383b44", padx=18, pady=6)
            frame.pack(side=tk.LEFT, expand=True)

            ttk.Label(frame, text=name.upper(), style="ResourceName.TLabel").pack(anchor="w")
            ttk.Label(frame, textvariable=self.resource_vars[name], style="ResourceVal.TLabel").pack(anchor="w")

        # 메인 영역 (왼: 섬, 오른: 건물 패널)
        main_frame = tk.Frame(self.root, bg="#f3efe2")
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=8)

        # ---- 왼쪽: 섬 Canvas ---- #
        island_frame = ttk.Labelframe(main_frame, text="섬", style="Panel.TLabelframe")
        island_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        self.canvas = tk.Canvas(island_frame, width=480, height=420, bg="#75cbe7", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.draw_island_base()

        # ---- 오른쪽: 건물/시간 패널 ---- #
        right_frame = ttk.Labelframe(main_frame, text="건물 & 시간", style="Panel.TLabelframe")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(8, 0))

        # 건물 리스트
        building_frame = ttk.Frame(right_frame, padding=6)
        building_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        for idx, bt in enumerate(self.building_types):
            row = idx

            # 이름
            name_lbl = ttk.Label(building_frame, text=bt.name, style="Small.TLabel")
            name_lbl.grid(row=row * 2, column=0, sticky="w")

            # 설명 + 생산량
            desc_lbl = ttk.Label(
                building_frame,
                text=f"{bt.desc}\n({bt.prod_resource} {bt.prod_per_sec}/초)",
                style="Small.TLabel",
                justify="left",
            )
            desc_lbl.grid(row=row * 2, column=1, sticky="w", padx=(4, 0))

            # 보유
            cnt_var = tk.StringVar()
            self.building_count_vars[bt.name] = cnt_var
            cnt_lbl = ttk.Label(building_frame, textvariable=cnt_var, style="Small.TLabel")
            cnt_lbl.grid(row=row * 2, column=2, sticky="e", padx=(6, 2))

            # 다음 비용
            cost_var = tk.StringVar()
            self.building_cost_vars[bt.name] = cost_var
            cost_lbl = ttk.Label(building_frame, textvariable=cost_var, style="Small.TLabel")
            cost_lbl.grid(row=row * 2, column=3, sticky="e", padx=(4, 2))

            # 구매 버튼
            buy_btn = ttk.Button(
                building_frame,
                text="구매",
                style="Buy.TButton",
                command=lambda b=bt: self.buy_building(b),
                width=6,
            )
            buy_btn.grid(row=row * 2, column=4, padx=(4, 0))

            # 행 간 구분
            ttk.Separator(building_frame, orient="horizontal").grid(
                row=row * 2 + 1, column=0, columnspan=5, sticky="ew", pady=(2, 4)
            )

        # 시간/메시지 영역
        bottom = ttk.Frame(right_frame, padding=6)
        bottom.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Label(bottom, text="시간 진행", style="Small.TLabel").pack(anchor="w")

        buttons_frame = ttk.Frame(bottom)
        buttons_frame.pack(fill=tk.X, pady=2)

        ttk.Button(buttons_frame, text="+10초", command=lambda: self.fast_forward(10)).pack(side=tk.LEFT, padx=2)
        ttk.Button(buttons_frame, text="+60초", command=lambda: self.fast_forward(60)).pack(side=tk.LEFT, padx=2)

        custom_frame = ttk.Frame(bottom)
        custom_frame.pack(fill=tk.X, pady=(4, 2))

        ttk.Label(custom_frame, text="커스텀(초):", style="Small.TLabel").pack(side=tk.LEFT)
        self.custom_entry = ttk.Entry(custom_frame, width=6)
        self.custom_entry.pack(side=tk.LEFT, padx=3)
        ttk.Button(custom_frame, text="진행", command=self.fast_forward_custom).pack(side=tk.LEFT)

        ttk.Label(bottom, textvariable=self.message_var, style="Small.TLabel", foreground="#006699").pack(
            anchor="w", pady=(4, 0)
        )

    # ---------- 섬 그리기 ---------- #
    def draw_island_base(self):
        """바다 + 섬 기본 배경"""
        self.canvas.delete("all")

        w = int(self.canvas["width"])
        h = int(self.canvas["height"])

        # 바다 물결 느낌
        for i in range(0, w, 40):
            self.canvas.create_oval(i - 30, h - 80, i + 40, h + 40, fill="#6ab7d6", outline="", tags="water")

        # 가운데 섬
        margin = 60
        self.island_bbox = (margin, margin, w - margin, h - margin)
        self.canvas.create_oval(
            self.island_bbox[0],
            self.island_bbox[1] + 40,
            self.island_bbox[2],
            self.island_bbox[3],
            fill="#f2e0a9",
            outline="#d1b36a",
            width=3,
            tags="island",
        )

        # 야자수 2개 정도
        self.draw_palm_tree(margin + 40, h - margin - 40)
        self.draw_palm_tree(w - margin - 60, h - margin - 60)

        # 건물은 따로 다시 그림
        self.draw_buildings_on_island()

    def draw_palm_tree(self, x, y):
        """간단 야자수"""
        # 줄기
        self.canvas.create_rectangle(x - 5, y - 40, x + 5, y, fill="#9c693f", outline="")
        # 잎
        self.canvas.create_polygon(
            x,
            y - 45,
            x - 30,
            y - 60,
            x - 5,
            y - 40,
            fill="#4ba45b",
            outline="",
        )
        self.canvas.create_polygon(
            x,
            y - 45,
            x + 30,
            y - 60,
            x + 5,
            y - 40,
            fill="#4ba45b",
            outline="",
        )
        self.canvas.create_polygon(
            x,
            y - 45,
            x - 10,
            y - 75,
            x + 10,
            y - 75,
            fill="#4ba45b",
            outline="",
        )

    def draw_buildings_on_island(self):
        """현재 건물 개수에 맞춰 섬 위에 작은 집 아이콘 뿌리기"""
        # 이전 건물 지우기
        self.canvas.delete("building")

        x1, y1, x2, y2 = self.island_bbox
        island_center_x = (x1 + x2) / 2
        island_center_y = (y1 + y2) / 2 + 20
        island_rx = (x2 - x1) / 2 - 40
        island_ry = (y2 - y1) / 2 - 40

        random.seed(0)  # 항상 같은 위치 나오도록

        for bt in self.building_types:
            count = self.state.buildings.get(bt.name, 0)
            for i in range(count):
                # 타원 내부 랜덤 위치
                angle = random.random() * 2 * math.pi
                r = random.random() ** 0.5  # 안쪽으로 조금 몰리게
                px = island_center_x + island_rx * r * math.cos(angle)
                py = island_center_y + island_ry * r * math.sin(angle)

                size = 16
                # 집 본체
                self.canvas.create_rectangle(
                    px - size / 2,
                    py - size / 2,
                    px + size / 2,
                    py + size / 2,
                    fill=bt.color,
                    outline="#5b4a3b",
                    tags="building",
                )
                # 지붕
                self.canvas.create_polygon(
                    px - size / 2 - 2,
                    py - size / 2,
                    px + size / 2 + 2,
                    py - size / 2,
                    px,
                    py - size,
                    fill="#b55239",
                    outline="#5b4a3b",
                    tags="building",
                )

    # ---------- 동작 ---------- #
    def refresh_ui(self):
        # 자원 텍스트
        for res, var in self.resource_vars.items():
            val = self.state.resources.get(res, 0.0)
            var.set(f"{val:,.1f}")

        # 건물 정보
        for bt in self.building_types:
            owned = self.state.buildings.get(bt.name, 0)
            self.building_count_vars[bt.name].set(f"{owned}개")
            cost = bt.get_cost(owned)
            self.building_cost_vars[bt.name].set(f"{bt.cost_resource} {cost:,}")

        # 섬 위 건물 다시 그림
        self.draw_buildings_on_island()

    def buy_building(self, bt: BuildingType):
        owned = self.state.buildings.get(bt.name, 0)
        cost = bt.get_cost(owned)

        if not self.state.can_afford(bt.cost_resource, cost):
            self.message_var.set(f"[{bt.name}] {bt.cost_resource}가 부족해서 구매할 수 없습니다.")
            return

        self.state.spend(bt.cost_resource, cost)
        self.state.add_building(bt.name)
        self.message_var.set(f"[{bt.name}] 1개를 섬에 지었습니다!")
        self.refresh_ui()

    def fast_forward(self, sec: float):
        if sec <= 0:
            return
        self.state.update(self.building_types, elapsed=sec)
        self.message_var.set(f"{sec:.1f}초 만큼 방치한 것으로 처리했습니다.")
        self.refresh_ui()

    def fast_forward_custom(self):
        text = self.custom_entry.get().strip()
        if not text:
            self.message_var.set("커스텀 시간(초)을 입력하세요.")
            return
        try:
            sec = float(text)
        except ValueError:
            self.message_var.set("숫자로 입력해주세요.")
            return
        if sec <= 0:
            self.message_var.set("0초 이하는 의미가 없습니다.")
            return
        self.fast_forward(sec)

    def game_loop(self):
        """0.5초마다 실제 지난 시간만큼 생산"""
        now = time.time()
        elapsed = now - self.last_loop_time
        self.last_loop_time = now

        self.state.update(self.building_types, elapsed=elapsed)
        self.refresh_ui()

        self.root.after(500, self.game_loop)


def main():
    root = tk.Tk()
    app = IdleIslandGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
