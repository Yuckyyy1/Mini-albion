"""
Мини-Альбион на Python + Kivy (работает на ПК и собирается в APK для Android).

Идея, как в Albion Online:
- Город (безопасно) -> Зелёная зона (безопасно, тиры 1-4) -> Красная зона
  (опасно, тиры 5-8, мобы, при смерти теряется вся сумка).
- Чем дальше от города, тем выше тир ресурсов и цены.
- Вес ограничивает сумку и замедляет персонажа.
- Продажа только в городе, налог на рынке 4%, цены плавают.
- Улучшения: сумка, меч, инструмент сбора.

Управление: тап по земле - идти, тап по ресурсу - собирать, тап по мобу - атаковать.
"""
import math
import random

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Rectangle
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

WORLD = 3000
HALF = WORLD // 2
CX = CY = HALF
TOWN_R = 250
GREEN_R = 800
SALES_TAX = 0.04

RES = {
    "Руда": (0.65, 0.65, 0.8),
    "Дерево": (0.6, 0.38, 0.15),
    "Волокно": (0.45, 0.85, 0.3),
    "Шкура": (0.85, 0.65, 0.5),
    "Камень": (0.55, 0.55, 0.55),
}


def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def zone(x, y):
    d = dist(x, y, CX, CY)
    return "town" if d < TOWN_R else "green" if d < GREEN_R else "red"


def tier_at(x, y):
    d = dist(x, y, CX, CY)
    return max(1, min(8, 1 + int((d - TOWN_R) / ((HALF - TOWN_R) / 8))))


def base_price(tier):
    return 8 * 1.9 ** (tier - 1)


def item_weight(tier):
    return 0.5 + 0.3 * tier


def rand_point(min_r, max_r):
    a = random.uniform(0, math.tau)
    r = random.uniform(min_r, max_r)
    return CX + math.cos(a) * r, CY + math.sin(a) * r


class Game(Widget):
    def __init__(self, hud, msg, **kw):
        super().__init__(**kw)
        self.hud, self.msg = hud, msg
        self.msg_t = 0
        self.px, self.py = CX, CY
        self.hp = 100
        self.silver = 0
        self.bag_lvl = self.sword_lvl = self.tool_lvl = 1
        self.inv = {}  # (res, tier) -> count
        self.target = None
        self.gather_t = self.atk_t = self.hit_t = 0
        self.mkt = {r: 1.0 for r in RES}
        self.mkt_t = 0

        self.nodes = []
        for _ in range(220):
            x, y = rand_point(TOWN_R + 40, HALF - 40)
            t = max(1, min(8, tier_at(x, y) + random.choice([-1, 0, 0, 1])))
            self.nodes.append({"x": x, "y": y, "res": random.choice(list(RES)),
                               "tier": t, "left": random.randint(4, 8), "resp": 0})
        self.mobs = []
        for _ in range(35):
            x, y = rand_point(GREEN_R + 30, HALF - 40)
            t = tier_at(x, y)
            self.mobs.append({"x": x, "y": y, "tier": t, "hp": 30 * t,
                              "max": 30 * t, "resp": 0})

    # ---- параметры ----
    @property
    def max_hp(self):
        return 100

    @property
    def cap(self):
        return 15 + 15 * self.bag_lvl

    @property
    def weight(self):
        return sum(item_weight(t) * n for (_, t), n in self.inv.items())

    @property
    def damage(self):
        return 8 + 4 * self.sword_lvl

    def speed(self):
        return 190 * (1 - 0.45 * min(1, self.weight / self.cap))

    def say(self, text):
        self.msg.text, self.msg_t = text, 3

    # ---- ввод ----
    def on_touch_down(self, touch):
        wx, wy = touch.x + self.cam_x, touch.y + self.cam_y
        for m in self.mobs:
            if m["hp"] > 0 and dist(wx, wy, m["x"], m["y"]) < 34:
                self.target = ("mob", m)
                return True
        for n in self.nodes:
            if n["left"] > 0 and dist(wx, wy, n["x"], n["y"]) < 28:
                self.target = ("node", n)
                self.say(f"{n['res']} T{n['tier']} (осталось {n['left']})")
                return True
        self.target = ("move", wx, wy)
        return True

    # ---- логика ----
    @property
    def cam_x(self):
        return self.px - self.width / 2

    @property
    def cam_y(self):
        return self.py - self.height / 2

    def step_to(self, tx, ty, dt, stop):
        d = dist(tx, ty, self.px, self.py)
        if d <= stop:
            return True
        k = min(self.speed() * dt, d - stop) / d
        self.px = max(0, min(WORLD, self.px + (tx - self.px) * k))
        self.py = max(0, min(WORLD, self.py + (ty - self.py) * k))
        return False

    def add_item(self, res, tier):
        if self.weight + item_weight(tier) > self.cap:
            return False
        self.inv[(res, tier)] = self.inv.get((res, tier), 0) + 1
        return True

    def die(self):
        self.inv.clear()
        self.hp = self.max_hp
        self.px, self.py = CX, CY
        self.target = None
        self.say("Вы погибли в красной зоне и потеряли всю сумку!")

    def update(self, dt):
        self.msg_t -= dt
        if self.msg_t <= 0:
            self.msg.text = ""
        self.mkt_t += dt
        if self.mkt_t > 30:
            self.mkt_t = 0
            self.mkt = {r: random.uniform(0.7, 1.3) for r in RES}

        for e in self.nodes + self.mobs:
            if e.get("resp", 0) > 0:
                e["resp"] -= dt
                if e["resp"] <= 0:
                    if "left" in e:
                        e["left"] = random.randint(4, 8)
                    else:
                        e["hp"] = e["max"]

        tg = self.target
        if tg and tg[0] == "move":
            if self.step_to(tg[1], tg[2], dt, 4):
                self.target = None
        elif tg and tg[0] == "node":
            n = tg[1]
            if n["left"] <= 0:
                self.target = None
            elif self.step_to(n["x"], n["y"], dt, 30):
                self.gather_t += dt
                if self.gather_t >= 1.3 / (1 + 0.2 * (self.tool_lvl - 1)):
                    self.gather_t = 0
                    if self.add_item(n["res"], n["tier"]):
                        n["left"] -= 1
                        if n["left"] <= 0:
                            n["resp"] = 25
                            self.target = None
                    else:
                        self.say("Сумка полная!")
                        self.target = None
        elif tg and tg[0] == "mob":
            m = tg[1]
            if m["hp"] <= 0:
                self.target = None
            elif self.step_to(m["x"], m["y"], dt, 36):
                self.atk_t += dt
                if self.atk_t >= 0.6:
                    self.atk_t = 0
                    m["hp"] -= self.damage
                    if m["hp"] <= 0:
                        m["resp"] = 40
                        self.silver += 25 * m["tier"]
                        res = random.choice(list(RES))
                        self.add_item(res, m["tier"])
                        self.say(f"Убит моб T{m['tier']}: +{25 * m['tier']} серебра")
                        self.target = None

        in_town = zone(self.px, self.py) == "town"
        if in_town:
            self.hp = min(self.max_hp, self.hp + 10 * dt)
        else:
            self.hit_t += dt
            for m in self.mobs:
                if m["hp"] <= 0:
                    continue
                d = dist(m["x"], m["y"], self.px, self.py)
                if d < 230:
                    k = min(95 * dt, d) / max(d, 1)
                    m["x"] += (self.px - m["x"]) * k
                    m["y"] += (self.py - m["y"]) * k
                if d < 30 and self.hit_t >= 1:
                    self.hit_t = 0
                    self.hp -= 4 + 3 * m["tier"]
            if self.hp <= 0:
                self.die()

        self.draw()
        self.update_hud()

    # ---- отрисовка ----
    def circle(self, r, rgb):
        Color(*rgb)
        Ellipse(pos=(CX - r - self.cam_x, CY - r - self.cam_y), size=(2 * r, 2 * r))

    def draw(self):
        ox, oy = -self.cam_x, -self.cam_y
        self.canvas.clear()
        with self.canvas:
            Color(0.35, 0.12, 0.12)
            Rectangle(pos=(ox, oy), size=(WORLD, WORLD))
            self.circle(GREEN_R, (0.13, 0.32, 0.15))
            self.circle(TOWN_R, (0.5, 0.45, 0.3))
            for n in self.nodes:
                if n["left"] > 0:
                    s = 12 + 3 * n["tier"]
                    Color(*RES[n["res"]])
                    Rectangle(pos=(n["x"] + ox - s / 2, n["y"] + oy - s / 2), size=(s, s))
            for m in self.mobs:
                if m["hp"] > 0:
                    s = 20 + 2 * m["tier"]
                    Color(0.9, 0.15, 0.15)
                    Ellipse(pos=(m["x"] + ox - s / 2, m["y"] + oy - s / 2), size=(s, s))
                    Color(0.2, 0.2, 0.2)
                    Rectangle(pos=(m["x"] + ox - 18, m["y"] + oy + s / 2 + 3), size=(36, 4))
                    Color(0.2, 1, 0.2)
                    Rectangle(pos=(m["x"] + ox - 18, m["y"] + oy + s / 2 + 3),
                              size=(36 * m["hp"] / m["max"], 4))
            Color(0.95, 0.85, 0.2)
            Ellipse(pos=(self.px + ox - 12, self.py + oy - 12), size=(24, 24))

    def update_hud(self):
        z = {"town": "Город (безопасно)", "green": "Зелёная зона",
             "red": "КРАСНАЯ зона (полный лут!)"}[zone(self.px, self.py)]
        items = ", ".join(f"{r} T{t} x{n}" for (r, t), n in sorted(self.inv.items(), key=lambda i: i[0][1])) or "пусто"
        self.hud.text = (f"HP {int(self.hp)}/{self.max_hp}   Серебро: {self.silver}\n"
                         f"Вес {self.weight:.1f}/{self.cap}   {z}\nСумка: {items}")

    # ---- кнопки ----
    def sell(self, *_):
        if zone(self.px, self.py) != "town":
            return self.say("Продавать можно только в городе")
        total = sum(base_price(t) * self.mkt[r] * n for (r, t), n in self.inv.items())
        total = int(total * (1 - SALES_TAX))
        self.silver += total
        self.inv.clear()
        self.say(f"Продано на {total} серебра (налог {int(SALES_TAX * 100)}%)")

    def upgrade(self, what):
        if zone(self.px, self.py) != "town":
            return self.say("Улучшать можно только в городе")
        lvl = {"bag": self.bag_lvl, "sword": self.sword_lvl, "tool": self.tool_lvl}[what]
        cost = {"bag": 150, "sword": 200, "tool": 150}[what] * lvl
        if self.silver < cost:
            return self.say(f"Нужно {cost} серебра")
        self.silver -= cost
        setattr(self, f"{what}_lvl", lvl + 1)
        self.say(f"Улучшено до уровня {lvl + 1}")


class AlbionLikeApp(App):
    def build(self):
        root = FloatLayout()
        hud = Label(halign="left", valign="top", size_hint=(1, 0.2), pos_hint={"x": 0.01, "top": 1})
        hud.bind(size=lambda w, s: setattr(w, "text_size", s))
        msg = Label(size_hint=(1, 0.08), pos_hint={"x": 0, "y": 0.5}, color=(1, 1, 0.5, 1))
        game = Game(hud, msg, size_hint=(1, 1))
        root.add_widget(game)
        root.add_widget(hud)
        root.add_widget(msg)
        for i, (text, fn) in enumerate([
            ("Продать", game.sell),
            ("Сумка+", lambda *_: game.upgrade("bag")),
            ("Меч+", lambda *_: game.upgrade("sword")),
            ("Инстр.+", lambda *_: game.upgrade("tool")),
        ]):
            b = Button(text=text, size_hint=(0.2, 0.1), pos_hint={"x": 0.01 + i * 0.21, "y": 0.01})
            b.bind(on_release=fn)
            root.add_widget(b)
        Clock.schedule_interval(game.update, 1 / 60)
        return root


if __name__ == "__main__":
    AlbionLikeApp().run()
