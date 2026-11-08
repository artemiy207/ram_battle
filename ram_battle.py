# -*- coding: utf-8 -*-
# УПРАВЛЕНИЕ В БИТВЕ: стрелки  <-  /  ->  (жми быстро!) помогают ПК / Сэму.
# Каждое нажатие копит заряд (до +5% урона), полный заряд даёт СУПЕР-удар.
# ESC в любой момент: удалить созданные файлы и выйти.
#
# Сборка (Windows):
# pyinstaller --onefile --noconsole ^
#   --add-data "sam.png;." --add-data "pc.png;." --add-data "ram.png;." ^
#   --add-data "bg_battle.png;." --add-data "audio.ogg;." --add-data "mk.ogg;." battle.py

import os
import sys
import io
import time
import math
import array
import base64
import random
import shutil
import queue
import tempfile
import threading
import ctypes
import tkinter as tk

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import pygame


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


class MemeBattle:
    NEON = ["#00FFFF", "#FF00FF", "#39FF14", "#FFFF00", "#FF073A",
            "#00FF9C", "#7DF9FF", "#FF6EC7", "#FFA500", "#9D00FF"]
    EMBER = ["#FF6A00", "#FFB300", "#FF3D00", "#FFD54F"]
    WORDS = ["ТЯНИ!", "ДАВИ!", "РВИ!", "БАХ!", "ГИГАБАЙТЫ!", "ХРУСТ!", "ДАЙ СЮДА!", "МОЁ!"]
    HITS = ["УДАР!", "КРИТ!", "КОМБО!", "ПРОБИТИЕ!", "ЛАГ!", "ERROR 404"]
    PC_COL = "#00FF66"
    SAM_COL = "#FF2D2D"
    NAMES = ("ПК", "САМ")
    DMG = {".exe": 14, ".msi": 14, ".iso": 15, ".zip": 11, ".rar": 11, ".7z": 11,
           ".mp4": 10, ".pdf": 9, ".pptx": 9, ".docx": 8, ".doc": 8, ".xlsx": 8,
           ".png": 7, ".jpg": 7, ".jpeg": 7, ".mp3": 7, ".lnk": 6, ".txt": 5}
    RICK_URL = "https://youtu.be/dQw4w9WgXcQ"
    BOOST_STEP = 0.005     # +0.5% урона за каждый заряд (максимум 10 зарядов)
    BOOST_DECAY = 0.30     # заряд тает: -1 каждые 0.3 сек, надо жать, чтобы держать
    SUPER_DMG = 9          # урон супер-удара
    SUPER_CD = 8.0         # пауза между супер-ударами (сек)
    LUCK_MULT = 1.03       # небольшое преимущество «везунчика» (randint 0/1)
    ENV_DT = 0.02      # шаг огибающей звука (сек)
    SYNC = 0.0         # подстройка визуала под звук (сек): + раньше, - позже

    # ================================================================ init
    def __init__(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        try:
            pygame.mixer.init(44100, -16, 2, 512)
        except Exception:
            try:
                pygame.mixer.init()
            except Exception:
                pass
        self.root = None
        self.canvas = None
        self.imgs = []
        self.created_files = []
        self.exiting = False
        self.cleaned = False
        self.wall_changed = False
        self.abort_spawn = False
        self.spawn_thread = None
        self.log_win = None
        self.log_text = None
        self.log_prog = None
        self.orig_wallpaper = self._get_wallpaper()
        self.desktop = self._get_desktop()
        self._analyze_audio("audio.ogg")

    # ================================================================ утилиты
    def _get_desktop(self):
        try:
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.shell32.SHGetFolderPathW(None, 0, None, 0, buf)
            if buf.value and os.path.isdir(buf.value):
                return buf.value
        except Exception:
            pass
        return os.path.join(os.path.expanduser("~"), "Desktop")

    def _get_wallpaper(self):
        try:
            buf = ctypes.create_unicode_buffer(512)
            ctypes.windll.user32.SystemParametersInfoW(0x73, 512, buf, 0)
            return buf.value
        except Exception:
            return ""

    def _set_wallpaper(self, path):
        try:
            ctypes.windll.user32.SystemParametersInfoW(0x14, 0, path, 3)
            return True
        except Exception:
            return False

    @staticmethod
    def _ease(p):
        p = max(0.0, min(1.0, p))
        return p * p * (3 - 2 * p)

    @staticmethod
    def _font(face, px, style="bold"):
        return (face, -max(8, int(px)), style)

    def _play_music(self, name, loops=-1):
        try:
            pygame.mixer.music.load(resource_path(name))
            pygame.mixer.music.set_volume(0.9)
            pygame.mixer.music.play(loops)
        except Exception:
            pass

    # ---------------------------------------------------------- картинки
    def _surface(self, name, height):
        try:
            surf = pygame.image.load(resource_path(name))
        except Exception:
            surf = pygame.Surface((200, 200))
            surf.fill((255, 0, 255))
        rgba = pygame.Surface(surf.get_size(), pygame.SRCALPHA, 32)
        rgba.blit(surf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        w, h = rgba.get_size()
        height = max(2, int(height))
        nw = max(2, int(w * height / h))
        return pygame.transform.smoothscale(rgba, (nw, height))

    def _photo(self, surf):
        try:
            buf = io.BytesIO()
            pygame.image.save(surf, buf, "x.png")
            raw = buf.getvalue()
        except Exception:
            tmp = os.path.join(tempfile.gettempdir(), "_mb_tmp.png")
            pygame.image.save(surf, tmp)
            with open(tmp, "rb") as f:
                raw = f.read()
        photo = tk.PhotoImage(master=self.root, data=base64.b64encode(raw))
        self.imgs.append(photo)
        return photo

    def _load_img(self, name, height):
        surf = self._surface(name, height)
        w, h = surf.get_size()
        return self._photo(surf), w, h

    def _load_series(self, name, height, n=14, smin=0.08):
        base = self._surface(name, height)
        bw, bh = base.get_size()
        out = []
        for i in range(n):
            s = 1.0 - (1.0 - smin) * i / (n - 1)
            w, h = max(2, int(bw * s)), max(2, int(bh * s))
            out.append(self._photo(pygame.transform.smoothscale(base, (w, h))))
        return out

    # ---------------------------------------------------------- анализ звука
    def _analyze_audio(self, name):
        dt = self.ENV_DT
        env = None
        self.snd = None
        self.dur = 7.5
        try:
            snd = pygame.mixer.Sound(resource_path(name))
            self.snd = snd
            self.dur = float(snd.get_length())
            freq, fmt, ch = pygame.mixer.get_init()
            if fmt != -16:
                raise ValueError("unsupported mixer format")
            raw = snd.get_raw()
            a = array.array("h")
            a.frombytes(raw[: len(raw) // 2 * 2])
            step = max(1, int(freq * dt)) * ch
            env = []
            for i in range(0, len(a) - step + 1, step):
                chunk = a[i:i + step:3]
                env.append(math.sqrt(sum(v * v for v in chunk) / len(chunk)))
            m = max(env) or 1.0
            env = [v / m for v in env]
        except Exception:
            env = None
        if not env or len(env) < 40:
            n = max(60, int(self.dur / dt))
            env = [0.55 + 0.4 * math.sin(i * 0.35) for i in range(n)]
        self.env = env
        n = len(env)

        # удары (онсеты) по огибающей
        onsets, last = [], -100
        for i in range(3, n):
            base = min(env[i - 3:i])
            if env[i] - base > 0.22 and env[i] > 0.3 and i - last >= 7:
                onsets.append(i * dt)
                last = i
        self.onsets = onsets

        # тихая «заминка» посередине: ПК тянул, Сэм упёрся, потом рывок к Сэму
        mean = sum(env) / n

        def loud(i):
            seg = env[i:i + 15]
            return sum(seg) / len(seg)

        q0 = None
        for i in range(int(0.2 * n), int(0.8 * n)):
            if loud(i) < 0.5 * mean:
                q0 = i
                break
        self.stall = False
        if q0 is not None:
            j = q0
            while j < n - 15 and loud(j) < 0.9 * mean:
                j += 1
            if (j - q0) * dt >= 0.35 and j < n - 15:
                self.stall = True
                self.q0, self.q1 = q0 * dt, j * dt
        if not self.stall:
            self.q0 = self.q1 = self.dur * 0.42

    def _env_at(self, t):
        x = t / self.ENV_DT
        k = int(x)
        if k < 0 or k >= len(self.env) - 1:
            return 0.0
        f = x - k
        return self.env[k] * (1 - f) + self.env[k + 1] * f

    # ---------------------------------------------------------- окна и холст
    def _make_overlay(self):
        r = tk.Tk()
        self.W = r.winfo_screenwidth()
        self.H = r.winfo_screenheight()
        r.config(bg="gray")
        r.overrideredirect(True)
        r.attributes("-topmost", True)
        r.attributes("-transparentcolor", "gray")
        r.geometry("%dx%d+0+0" % (self.W, self.H))
        c = tk.Canvas(r, width=self.W, height=self.H, bg="gray",
                      highlightthickness=0, bd=0)
        c.pack(fill="both", expand=True)
        self.root, self.canvas = r, c
        self.imgs = []
        self.particles, self.rings, self.popups, self.bolts = [], [], [], []
        self.flash_t = 0.0
        r.after(300, self._poll_esc)

    def _poll_esc(self):
        if self.exiting:
            return
        try:
            if ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000:
                self._cleanup_and_exit()
                return
        except Exception:
            pass
        try:
            self.root.after(40, self._poll_esc)
        except Exception:
            pass

    # ---------------------------------------------------------- текст с тенью
    def _stext(self, x, y, text, color, px, anchor="center", tags=(), width=0):
        off = max(2, int(px * 0.06))
        kw = dict(text=text, font=self._font("Impact", px), anchor=anchor, justify="center")
        if width:
            kw["width"] = int(width)
        s = self.canvas.create_text(x + off, y + off, fill="#000000", tags=tags, **kw)
        m = self.canvas.create_text(x, y, fill=color, tags=tags, **kw)
        return (s, m)

    def _set_stext(self, pair, text=None, color=None, px=None, x=None, y=None):
        c = self.canvas
        for k, it in enumerate(pair):
            kw = {}
            if text is not None:
                kw["text"] = text
            if px is not None:
                kw["font"] = self._font("Impact", px)
            if color is not None and k == 1:
                kw["fill"] = color
            if kw:
                c.itemconfig(it, **kw)
        if x is not None and y is not None:
            off = max(2, int((px or self.H * 0.05) * 0.06))
            c.coords(pair[0], x + off, y + off)
            c.coords(pair[1], x, y)

    # ---------------------------------------------------------- эффекты
    @staticmethod
    def _zig(x1, y1, x2, y2, seg=6, jit=22):
        pts = [x1, y1]
        for i in range(1, seg):
            f = i / seg
            pts += [x1 + (x2 - x1) * f + random.uniform(-jit, jit),
                    y1 + (y2 - y1) * f + random.uniform(-jit, jit)]
        pts += [x2, y2]
        return pts

    def _beam(self, x1, y1, x2, y2, w, col=None, jit=22):
        col = col or random.choice(self.NEON)
        pts = self._zig(x1, y1, x2, y2, 6, jit)
        self.canvas.create_line(*pts, fill=col, width=max(2, int(w)),
                                capstyle=tk.ROUND, joinstyle=tk.ROUND, tags="fx")
        self.canvas.create_line(*pts, fill="white", width=max(1, int(w) // 3), tags="fx")

    def _spark(self, x, y, n, cols=None, spd=(80, 520), life=(0.25, 0.6),
               grav=0.0, size=(2, 4)):
        for _ in range(n):
            a = random.uniform(0, 6.2832)
            s = random.uniform(*spd)
            lf = random.uniform(*life)
            self.particles.append([x, y, math.cos(a) * s, math.sin(a) * s, lf, lf,
                                   random.choice(cols or self.NEON),
                                   random.uniform(*size), grav])

    def _boom(self, x, y, col, big=False):
        self._spark(x, y, 44 if big else 26, [col, "#FFFFFF", "#FFD700"],
                    spd=(120, 700), life=(0.3, 0.8))
        self.rings.append([x, y, 10, 900 if big else 600, 0.5, 0.5, col])
        if big:
            self.rings.append([x, y, 6, 520, 0.7, 0.7, "#FFFFFF"])
            self.flash_t = max(self.flash_t, 0.06)

    def _draw_fx(self, dt, cap=300):
        c = self.canvas
        alive = []
        for p in self.particles:
            p[4] -= dt
            if p[4] <= 0:
                continue
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += p[8] * dt
            s = max(1.0, p[7] * (0.4 + 0.6 * p[4] / p[5]))
            c.create_oval(p[0] - s, p[1] - s, p[0] + s, p[1] + s,
                          fill=p[6], outline="", tags="fx")
            alive.append(p)
        self.particles = alive[-cap:]
        ring_alive = []
        for rg in self.rings:
            rg[2] += rg[3] * dt
            rg[4] -= dt
            if rg[4] <= 0:
                continue
            w = max(1, int(8 * rg[4] / rg[5]))
            c.create_oval(rg[0] - rg[2], rg[1] - rg[2], rg[0] + rg[2], rg[1] + rg[2],
                          outline=rg[6], width=w, tags="fx")
            ring_alive.append(rg)
        self.rings = ring_alive
        pop_alive = []
        for pp in self.popups:
            pp[4] -= dt
            if pp[4] <= 0:
                continue
            k = 1 - pp[4] / pp[5]
            self._stext(pp[0], pp[1] - 70 * k, pp[2], pp[3], self.H * 0.045, tags=("fx",))
            pop_alive.append(pp)
        self.popups = pop_alive

    def _draw_flash(self, dt):
        if self.flash_t > 0:
            self.canvas.create_rectangle(0, 0, self.W, self.H, fill="white",
                                         stipple="gray25", outline="", tags="fx")
            self.flash_t -= dt

    def _draw_bolts(self, dt):
        alive = []
        for b in self.bolts:
            b[4] -= dt
            if b[4] <= 0:
                continue
            self._beam(b[0], b[1], b[2], b[3], 7, "#BFE9FF", 38)
            alive.append(b)
        self.bolts = alive

    # ================================================================ ФАЗА 1: ПЕРЕТЯГИВАНИЕ ПОД ЗВУК
    def _start_intro(self):
        self._make_overlay()
        W, H, c = self.W, self.H, self.canvas
        self.cy = H * 0.56
        self.pc_cx, self.sam_cx = W * 0.17, W * 0.83
        pc, self.pc_w, pc_h = self._load_img("pc.png", H * 0.40)
        sam, self.sam_w, sam_h = self._load_img("sam.png", H * 0.45)
        ram, self.ram_w, self.ram_h = self._load_img("ram.png", H * 0.12)

        self.pc_item = c.create_image(self.pc_cx, self.cy, image=pc)
        self.sam_item = c.create_image(self.sam_cx, self.cy, image=sam)
        self._stext(self.pc_cx, self.cy - pc_h / 2 - 50, "ТВОЙ ПК", "#00FF00", H * 0.06)
        self._stext(self.sam_cx, self.cy - sam_h / 2 - 50, "СЭМ АЛЬТМАН", "#FF0000", H * 0.06)
        self.ram_item = c.create_image(W / 2, self.cy, image=ram)

        # шкала перетягивания
        self.bw = W * 0.44
        self.bx0 = W / 2 - self.bw / 2
        self.by0 = H * 0.05
        self.bh = H * 0.028
        c.create_rectangle(self.bx0 - 4, self.by0 - 4, self.bx0 + self.bw + 4,
                           self.by0 + self.bh + 4, fill="#111111", outline="#FFD700", width=3)
        self.bar_pc = c.create_rectangle(0, 0, 0, 0, fill="#00DD55", outline="")
        self.bar_sam = c.create_rectangle(0, 0, 0, 0, fill="#EE2222", outline="")
        self.bar_mark = c.create_line(0, 0, 0, 0, fill="white", width=4)
        self._stext(W / 2, self.by0 - H * 0.025, "ПЕРЕТЯГИВАНИЕ ОЗУ", "#FFD700", H * 0.03)

        self.x_mid = W / 2
        self.x_pc = self.pc_cx + self.pc_w / 2 + self.ram_w / 2 - 10
        self.x_sam = self.sam_cx - self.sam_w / 2 - self.ram_w / 2 + 10
        self.pos, self.vel = 0.0, 0.0
        self.shake, self.envs = 0.0, 0.0
        self.alt, self.pull, self.oi = 1, -1, 0
        self.boomed = False
        self.ram_xy = (W / 2, self.cy)
        self.intro_total = self.dur + 0.55

        if self.snd is not None:
            try:
                self.snd.set_volume(1.0)
                self.snd.play()
            except Exception:
                pass
        else:
            self._play_music("audio.ogg", 0)
        self.t0 = time.perf_counter()
        self.last = self.t0
        self._intro_tick()

    def _pos_x(self, p):
        if p < 0:
            return self.x_mid + (self.x_pc - self.x_mid) * (-p)
        return self.x_mid + (self.x_sam - self.x_mid) * p

    def _tug_target(self, t):
        q0, q1 = self.q0, self.q1
        start = -0.93
        mid = start + (0.25 if self.stall else 0.0)
        if t < q0:
            return start * self._ease(t / max(0.001, q0))
        if self.stall and t < q1:
            return start + 0.25 * (t - q0) / max(0.001, q1 - q0)
        k = (t - q1) / max(0.001, self.dur - q1)
        return mid + (0.95 - mid) * self._ease(k)

    def _intro_onset(self, ton):
        e = self._env_at(ton)
        if ton < self.q0:
            side = -1
        elif self.stall and ton < self.q1:
            self.alt = -self.alt
            side = self.alt
        else:
            side = 1
        self.pull = side
        self.vel += side * (1.3 + 2.4 * e)
        self.shake = max(self.shake, 4 + 12 * e)
        x, y = self.ram_xy
        col = random.choice(self.NEON)
        self._spark(x, y, 16 + int(30 * e))
        self.rings.append([x, y, 14, 700, 0.5, 0.5, col])
        if e > 0.7:
            self.flash_t = 0.06
        if e > 0.55 and len(self.popups) < 3:
            self.popups.append([x + random.uniform(-80, 80), y - 90,
                                random.choice(self.WORDS), random.choice(self.NEON), 0.7, 0.7])

    def _intro_tick(self):
        now = time.perf_counter()
        dt = min(0.05, max(0.001, now - self.last))
        self.last = now
        t = now - self.t0 + self.SYNC
        if t >= self.intro_total:
            self.root.destroy()
            return
        c, W, H = self.canvas, self.W, self.H

        self.envs = max(self._env_at(t), self.envs - dt * 2.2)
        e = self.envs

        # физика перетягивания (пружина + рывки на ударах звука)
        target = self._tug_target(t)
        self.vel += ((target - self.pos) * 70.0 - self.vel * 9.0) * dt
        self.pos = max(-1.08, min(1.08, self.pos + self.vel * dt))
        x = self._pos_x(self.pos)
        if t < self.q0:
            amp = 8
        elif self.stall and t < self.q1:
            amp = 6
        else:
            amp = 16
        amp *= 0.55 + 0.45 * e
        y = self.cy + random.uniform(-amp, amp)
        x += random.uniform(-3, 3) * e
        self.ram_xy = (x, y)
        c.coords(self.ram_item, x, y)

        if t < self.q0:
            self.pull = -1
        elif t >= self.q1:
            self.pull = 1

        while self.oi < len(self.onsets) and self.onsets[self.oi] <= t:
            self._intro_onset(self.onsets[self.oi])
            self.oi += 1

        if not self.boomed and t >= self.dur + 0.1:
            self.boomed = True
            for _ in range(3):
                self._boom(x, y, random.choice(self.NEON), True)
            self._spark(x, y, 90, spd=(200, 900), life=(0.4, 1.0))

        # персонажи: тряска и наклон к плашке
        sh = 1.5 + 8 * e + self.shake
        self.shake = max(0.0, self.shake - dt * 60)
        lean_pc = 34 * max(0.0, -self.pos)
        lean_sam = -34 * max(0.0, self.pos)
        c.coords(self.pc_item, self.pc_cx + lean_pc + random.uniform(-sh, sh),
                 self.cy + random.uniform(-sh, sh))
        c.coords(self.sam_item, self.sam_cx + lean_sam + random.uniform(-sh, sh),
                 self.cy + random.uniform(-sh, sh))

        # шкала
        frac_pc = max(0.0, min(1.0, 1 - (self.pos + 1) / 2))
        xm = self.bx0 + self.bw * frac_pc
        c.coords(self.bar_pc, self.bx0, self.by0, xm, self.by0 + self.bh)
        c.coords(self.bar_sam, xm, self.by0, self.bx0 + self.bw, self.by0 + self.bh)
        c.coords(self.bar_mark, xm, self.by0 - 6, xm, self.by0 + self.bh + 6)

        # лазеры, искры, кольца
        c.delete("fx")
        self._draw_flash(dt)
        n = 1 + int(e * 2.4)
        for side in (-1, 1):
            ax = (self.pc_cx + self.pc_w * 0.38) if side == -1 else (self.sam_cx - self.sam_w * 0.38)
            mult = 1.5 if side == self.pull else 0.8
            for _ in range(n):
                self._beam(ax, self.cy + random.uniform(-0.12, 0.12) * H,
                           x, y + random.uniform(-10, 10), (3 + 9 * e) * mult)
        self._spark(x, y, 2 + int(e * 14), spd=(80, 520), life=(0.25, 0.6))
        self._draw_fx(dt, 320)
        c.tag_raise(self.ram_item)
        self.root.after(8, self._intro_tick)

    # ================================================================ ФАЗА 2: БИТВА ЗА РАБОЧИЙ СТОЛ
    def _desktop_metrics(self):
        self.icon_w, self.icon_h, work_h = 75, 75, self.H - 48
        try:
            from ctypes import wintypes
            u = ctypes.windll.user32
            self.icon_w = u.GetSystemMetrics(38) or 75
            self.icon_h = u.GetSystemMetrics(39) or 75
            rc = wintypes.RECT()
            if u.SystemParametersInfoW(0x30, 0, ctypes.byref(rc), 0):
                work_h = rc.bottom - rc.top
        except Exception:
            pass
        self.rows = max(1, int(work_h // self.icon_h))
        cnt = 0
        for d in (self.desktop, os.path.join(os.environ.get("PUBLIC", "C:\\Users\\Public"), "Desktop")):
            try:
                cnt += sum(1 for n in os.listdir(d)
                           if n.lower() != "desktop.ini" and not n.startswith("."))
            except Exception:
                pass
        self.slot_base = cnt

    def _slot_xy(self, k):
        col, row = divmod(k, self.rows)
        return (8 + col * self.icon_w + self.icon_w / 2,
                8 + row * self.icon_h + self.icon_h / 2)

    def _build_file_pool(self):
        """Реальные имена файлов с рабочего стола: ими бойцы кидаются (файлы НЕ трогаются)."""
        items, idx = [], 0
        for d in (self.desktop, os.path.join(os.environ.get("PUBLIC", "C:\\Users\\Public"), "Desktop")):
            try:
                for n in sorted(os.listdir(d)):
                    if n.lower() == "desktop.ini" or n.startswith("."):
                        continue
                    items.append((n, os.path.isdir(os.path.join(d, n)), idx))
                    idx += 1
            except Exception:
                pass
        random.shuffle(items)
        items = items[:40]
        if len(items) < 6:
            items += [("Новая папка", True, 0), ("Реферат_финал_v7.docx", False, 1),
                      ("homework.pdf", False, 2), ("setup.exe", False, 3),
                      ("мем.png", False, 4), ("Корзина", True, 5)]
        return items

    def _file_dmg(self, name, isdir):
        if name.startswith("BATTLE_LOG_SLOT_"):
            return 4
        if isdir:
            return 10
        return self.DMG.get(os.path.splitext(name)[1].lower(), 7)

    @staticmethod
    def _short(s, n):
        return s if len(s) <= n else s[:n - 1] + "…"

    def _start_battle(self):
        self._make_overlay()
        W, H, c = self.W, self.H, self.canvas
        self._desktop_metrics()
        self.pool = self._build_file_pool()

        self.luck = random.randint(0, 1)           # кому чуть-чуть везёт: 0 = ПК, 1 = Сэм
        self.winner = self.loser = self.outcome = self.pc_wins = None

        self.fy = H * 0.56
        self.base_x = [W * 0.23, W * 0.77]
        pc, pw, ph = self._load_img("pc.png", H * 0.36)
        sam, sw, sh_ = self._load_img("sam.png", H * 0.42)
        self.f_h = [ph, sh_]
        self.f_item = [c.create_image(self.base_x[0], self.fy, image=pc),
                       c.create_image(self.base_x[1], self.fy, image=sam)]
        self.f_xy = [(self.base_x[0], self.fy), (self.base_x[1], self.fy)]
        self._stext(self.base_x[0], self.fy - ph / 2 - 40, "ТВОЙ ПК", "#00FF00", H * 0.05)
        self._stext(self.base_x[1], self.fy - sh_ / 2 - 40, "СЭМ АЛЬТМАН", "#FF0000", H * 0.05)

        # HUD: полоски здоровья (с «хвостом» урона)
        self.bar_y, self.bar_h = H * 0.045, H * 0.032
        self.bars = [(W * 0.05, W * 0.45), (W * 0.55, W * 0.95)]
        self.hp_chip, self.hp_fill = [], []
        for x0, x1 in self.bars:
            c.create_rectangle(x0 - 4, self.bar_y - 4, x1 + 4, self.bar_y + self.bar_h + 4,
                               fill="#1A1A1A", outline="#FFD700", width=3)
            self.hp_chip.append(c.create_rectangle(x0, self.bar_y, x1, self.bar_y + self.bar_h,
                                                   fill="#FFB84D", outline=""))
            self.hp_fill.append(c.create_rectangle(x0, self.bar_y, x1, self.bar_y + self.bar_h,
                                                   fill="#2ECC40", outline=""))
        c.create_rectangle(W / 2 - H * 0.05, self.bar_y - 6, W / 2 + H * 0.05,
                           self.bar_y + self.bar_h + 6, fill="#1A1A1A", outline="#FFD700", width=3)
        self.timer_txt = self._stext(W / 2, self.bar_y + self.bar_h / 2, "45", "#FFFFFF", H * 0.05)
        self._stext(self.bars[0][0], self.bar_y + self.bar_h + H * 0.03, "ТВОЙ ПК",
                    "#00FF00", H * 0.03, anchor="w")
        self._stext(self.bars[1][1], self.bar_y + self.bar_h + H * 0.03, "СЭМ АЛЬТМАН",
                    "#FF0000", H * 0.03, anchor="e")
        self.cap_txt = self._stext(W / 2, H * 0.125, "", "#FFD700", H * 0.032)
        self.banner = self._stext(W / 2, H * 0.30, "", "#FFD700", H * 0.1)

        # шкалы помощи игрока (стрелки)
        self.seg_items = [[], []]
        sw_, sy, sh2 = W * 0.016, H * 0.138, H * 0.018
        for j in range(10):
            xl = W * 0.05 + j * (sw_ + 4)
            xr = W * 0.95 - j * (sw_ + 4)
            self.seg_items[0].append(c.create_rectangle(xl, sy, xl + sw_, sy + sh2,
                                                        fill="#222222", outline="#555555"))
            self.seg_items[1].append(c.create_rectangle(xr - sw_, sy, xr, sy + sh2,
                                                        fill="#222222", outline="#555555"))
        self.help_txt = [self._stext(W * 0.05, H * 0.182, "[←] ПОМОГИ ПК", "#00FF00",
                                     H * 0.024, anchor="w"),
                         self._stext(W * 0.95, H * 0.182, "ПОМОГИ САМУ [→]", "#FF0000",
                                     H * 0.024, anchor="e")]

        self.hp = [100.0, 100.0]
        self.hp_vis = [100.0, 100.0]
        self.cap = [0, 0]
        self.hit_t = [0.0, 0.0]
        self.lunge = [0.0, 0.0]
        self.dodge_t = [0.0, 0.0]
        self.boost = [0, 0]
        self.boost_decay = [0.0, 0.0]
        self.super_ready = [False, False]
        self.super_cd = [0.0, 0.0]
        self.key_prev = [False, False]
        self.cd = [random.uniform(0.6, 1.2), random.uniform(0.6, 1.2)]
        self.proj, self.beams = [], []
        self.next_light = 4.0
        self.ember_acc = 0.0
        self.slot_i = 0
        self.frame = 0
        self.stage = 0
        self.rem = 45
        self.fin_t0 = 0.0
        self.stop_battle = False
        self.thread_started = False
        self.spawn_done = False
        self.slot_q = queue.Queue()
        self._update_cap_text()

        self.b0 = time.perf_counter()
        self.last = self.b0
        self._battle_tick()

    def _update_cap_text(self):
        self._set_stext(self.cap_txt, "ЗАХВАЧЕНО СЛОТОВ:   ПК %d   :   %d САМ" % tuple(self.cap))

    # ---------------------------------------------------------- лог-окно хакеров
    def _open_log(self):
        W, H = self.W, self.H
        w, h = max(580, int(W * 0.34)), max(300, int(H * 0.30))
        lw = tk.Toplevel(self.root)
        lw.overrideredirect(True)
        lw.attributes("-topmost", True)
        lw.geometry("%dx%d+%d+%d" % (w, h, (W - w) // 2, H - h - 80))
        lw.config(bg="#00FF41")
        inner = tk.Frame(lw, bg="black")
        inner.pack(fill="both", expand=True, padx=2, pady=2)
        tk.Label(inner, text=" ● root@battle:~/Desktop — spawn_slots.sh   PID 31337",
                 bg="#001A07", fg="#00FF41", font=("Consolas", -14, "bold"),
                 anchor="w").pack(fill="x")
        self.log_text = tk.Text(inner, bg="black", fg="#00FF41", font=("Consolas", -13),
                                bd=0, highlightthickness=0, wrap="none", height=1)
        self.log_text.pack(fill="both", expand=True, padx=6, pady=4)
        for tag, col in (("ok", "#00FF41"), ("dim", "#1F8F3A"), ("fail", "#FF3B3B"),
                         ("warn", "#FFE600")):
            self.log_text.tag_config(tag, foreground=col)
        self.log_prog = tk.Label(inner, text="", bg="black", fg="#00FF41",
                                 font=("Consolas", -14, "bold"), anchor="w")
        self.log_prog.pack(fill="x", padx=6, pady=(0, 4))
        self.log_win = lw
        self._log('root@battle:~# ./spawn_slots --target "%s" --count 50' % self.desktop, "ok")
        self._log("[*] загрузка модуля RAM-DRAIN v6.6.6 ........ OK", "dim")
        self._log("[*] обход защиты рабочего стола ............. OK", "dim")
        self._log("[!] ЗАХВАТ РАБОЧЕГО СТОЛА НАЧАТ", "warn")
        self._log_progress(0)

    def _log(self, line, tag="ok"):
        if not self.log_text:
            return
        self.log_text.insert("end", line + "\n", tag)
        self.log_text.see("end")
        try:
            if int(self.log_text.index("end-1c").split(".")[0]) > 300:
                self.log_text.delete("1.0", "60.0")
        except Exception:
            pass

    def _log_progress(self, n):
        if self.log_prog:
            k = int(20 * n / 50)
            self.log_prog.config(text="[%s%s] %02d/50 слотов" % ("█" * k, "░" * (20 - k), n))

    # ---------------------------------------------------------- фоновый поток
    def _spawn_files(self):
        time.sleep(0.8)
        used = set()
        for i in range(50):
            if self.abort_spawn:
                break
            while True:
                rnd = random.randint(100000, 999999)
                if rnd not in used:
                    used.add(rnd)
                    break
            name = "BATTLE_LOG_SLOT_%d.txt" % rnd
            path = os.path.join(self.desktop, name)
            err = None
            try:
                open(path, "w").close()
                self.created_files.append(path)
            except Exception as ex:
                err = str(ex)
            self.slot_q.put(("slot", i, name, err))
            if i % 3 == 2:
                self.slot_q.put(("hex", "[MEM] 0x%08X -> 0x%08X  RAM-DRAIN" %
                                 (random.getrandbits(32), random.getrandbits(32))))
            time.sleep(random.uniform(0.22, 0.38))
        self.slot_q.put(("done",))

    # ---------------------------------------------------------- главный тик битвы
    def _battle_tick(self):
        if self.stop_battle or self.exiting:
            return
        now = time.perf_counter()
        dt = min(0.05, max(0.001, now - self.last))
        self.last = now
        bt = now - self.b0
        if self.stage == 2:                          # слоу-мо после нокаута
            dt *= 0.3 + 0.7 * min(1.0, (bt - self.fin_t0) / 1.2)
        self.canvas.delete("fx")
        self._draw_flash(dt)

        self._poll_keys(dt)
        self._b_stage(bt)
        self._b_events()
        self._b_ai(dt)
        self._b_fighters(bt, dt)
        self._b_projectiles(dt)
        self._b_beams(dt)
        self._b_ambient(dt)
        self._draw_bolts(dt)
        self._draw_fx(dt, 300)
        self._b_hud(bt, dt)

        if self.log_win and self.frame % 45 == 0:
            try:
                self.log_win.lift()
            except Exception:
                pass
        self.frame += 1
        if self.stage == 2 and bt - self.fin_t0 >= 4.0:
            self._start_final()
            return
        self.root.after(8, self._battle_tick)

    # ---------------------------------------------------------- стадии боя
    def _b_stage(self, bt):
        W, H = self.W, self.H
        if self.stage == 0:
            if bt < 1.3:
                k = self._ease(bt / 0.5)
                self._set_stext(self.banner, "БИТВА ЗА РАБОЧИЙ СТОЛ", "#FFD700", H * 0.085,
                                W / 2, H * (-0.1 + 0.4 * k))
            elif bt < 2.0:
                self._set_stext(self.banner, "РАУНД 1", "#FFFFFF", H * 0.11, W / 2, H * 0.30)
            elif bt < 3.0:
                slam = 1 + 0.8 * max(0.0, 1 - (bt - 2.0) / 0.25)
                self._set_stext(self.banner, "FIGHT!", "#FF2D2D", H * 0.16 * slam, W / 2, H * 0.30)
            if bt >= 2.0 and not self.thread_started:
                self.thread_started = True
                self._open_log()
                self.spawn_thread = threading.Thread(target=self._spawn_files, daemon=True)
                self.spawn_thread.start()
            if bt >= 3.0:
                self.stage = 1
                self._set_stext(self.banner, "")
        elif self.stage == 1:
            self.rem = max(0, int(45 - (bt - 3.0)))
            if bt > 90:
                self.spawn_done = True
            loser = None
            if self.hp[0] <= 0 and self.hp[1] <= 0:
                loser = 1 - self.luck
            elif self.hp[0] <= 0:
                loser = 0
            elif self.hp[1] <= 0:
                loser = 1
            elif self.rem <= 0 and self.spawn_done:
                if self.hp[0] == self.hp[1]:
                    loser = 1 - self.luck
                else:
                    loser = 0 if self.hp[0] < self.hp[1] else 1
            if loser is not None:
                self._ko(loser, bt)
        else:
            tf = bt - self.fin_t0
            slam = 1 + 0.8 * max(0.0, 1 - (tf % 1.3 if tf < 1.3 else tf - 1.3) / 0.3)
            if tf < 1.3:
                self._set_stext(self.banner, "K.O.!", "#FF2D2D", H * 0.2 * slam, W / 2, H * 0.30)
            else:
                col = "#FF3B00" if int(tf * 6) % 2 == 0 else "#FFD700"
                self._set_stext(self.banner, "FINISH HIM!", col, H * 0.14 * slam, W / 2, H * 0.30)

    def _ko(self, loser, bt):
        self.loser = loser
        self.winner = 1 - loser
        self.pc_wins = (self.winner == 0)
        self.outcome = 0 if self.pc_wins else 1
        self.hp[loser] = 0.0
        self.stage = 2
        self.fin_t0 = bt
        self.proj, self.beams = [], []
        self.hit_t[loser] = 0.45
        self._log("[###] K.O.! %s ПОВЕРЖЕН. СЛОТЫ: ПК %d : %d САМ" %
                  (self.NAMES[loser], self.cap[0], self.cap[1]), "warn")
        x, y = self.f_xy[loser]
        self._boom(x, y, "#FFFFFF", True)
        self._boom(x, y, "#FFD700", True)

    def _b_events(self):
        try:
            while True:
                ev = self.slot_q.get_nowait()
                if ev[0] == "slot":
                    _, i, name, err = ev
                    if err:
                        self._log("[FAIL] %s -> %s" % (name, err), "fail")
                    else:
                        self._log("[ OK ] %02d/50 create %s (0 bytes)" % (i + 1, name), "ok")
                    self._log_progress(i + 1)
                    self.slot_i = i + 1
                    self._launch_slot(i, name)
                elif ev[0] == "hex":
                    self._log(ev[1], "dim")
                elif ev[0] == "done":
                    self.spawn_done = True
        except queue.Empty:
            pass

    def _launch_slot(self, i, name):
        self.pool.append((name, False, self.slot_base + i))     # новый файл тоже годится для броска
        if self.stage == 2:
            return
        if self.hp[0] != self.hp[1]:
            leader = 0 if self.hp[0] > self.hp[1] else 1
        else:
            leader = self.luck
        owner = leader if random.random() < 0.62 else 1 - leader  # слот чаще берёт лидер боя
        sx, sy = self._slot_xy(self.slot_base + i)
        fx, fy = self.f_xy[owner]
        col = self.PC_COL if owner == 0 else self.SAM_COL
        dist = math.hypot(sx - fx, sy - fy)
        self.lunge[owner] = 0.3
        self.proj.append({"kind": "slot", "owner": owner, "t": 0.0, "T": max(0.3, dist / 1700.0),
                          "x0": fx, "y0": fy, "x1": sx, "y1": sy, "x": fx, "y": fy,
                          "col": col, "trail": [], "home": None,
                          "arc": random.uniform(40, 160) * random.choice((-1, 1))})

    # ---------------------------------------------------------- помощь игрока
    def _poll_keys(self, dt):
        for s in (0, 1):
            self.super_cd[s] = max(0.0, self.super_cd[s] - dt)
            if self.boost[s] > 0 and not self.super_ready[s]:
                self.boost_decay[s] += dt
                if self.boost_decay[s] >= self.BOOST_DECAY:
                    self.boost_decay[s] = 0.0
                    self.boost[s] -= 1
            self._check_super(s)
        if self.stage == 2:
            return
        try:
            g = ctypes.windll.user32.GetAsyncKeyState
            for s, key in ((0, 0x25), (1, 0x27)):       # стрелка влево = ПК, вправо = Сэм
                down = bool(g(key) & 0x8000)
                if down and not self.key_prev[s]:
                    self._cheer(s)
                self.key_prev[s] = down
        except Exception:
            pass

    def _check_super(self, s):
        if self.stage < 2 and not self.super_ready[s] and self.boost[s] >= 10 and self.super_cd[s] <= 0:
            self.super_ready[s] = True
            x, y = self.f_xy[s]
            self.popups.append([x, y - self.f_h[s] * 0.6, "СУПЕР ГОТОВ!", "#FFD700", 1.0, 1.0])
            self._boom(x, y, "#FFD700", True)

    def _cheer(self, s):
        if self.super_ready[s]:
            return
        self.boost[s] = min(10, self.boost[s] + 1)
        self.boost_decay[s] = 0.0
        x, y = self.f_xy[s]
        col = self.PC_COL if s == 0 else self.SAM_COL
        self._spark(x, y - self.f_h[s] * 0.4, 8, [col, "#FFFFFF"], spd=(60, 260), life=(0.2, 0.45))
        self._check_super(s)

    def _mult(self, a):
        m = 1 + self.BOOST_STEP * self.boost[a] + 0.003 * self.cap[a]
        if self.luck == a:
            m *= self.LUCK_MULT
        return m

    # ---------------------------------------------------------- атаки и урон
    def _b_ai(self, dt):
        if self.stage != 1:
            return
        for a in (0, 1):
            self.cd[a] -= dt
            if self.super_ready[a]:
                self.cd[a] = min(self.cd[a], 0.25)
            if self.cd[a] <= 0:
                self.cd[a] = random.uniform(1.1, 1.8)
                self._attack(a)

    def _miss_xy(self, a, d):
        dx, dy = self.f_xy[d]
        return dx + (1 if a == 0 else -1) * 260, dy + random.uniform(-260, -140)

    def _attack(self, a):
        d = 1 - a
        ax, ay = self.f_xy[a]
        dx, dy = self.f_xy[d]
        col = self.PC_COL if a == 0 else self.SAM_COL
        mult = self._mult(a) * random.uniform(0.9, 1.1)
        crit = random.random() < 0.1
        if crit:
            mult *= 1.5
        dodge = random.random() < 0.12
        self.lunge[a] = 0.3

        if self.super_ready[a]:
            self.super_ready[a] = False
            self.boost[a] = 0
            self.super_cd[a] = self.SUPER_CD
            self.beams.append({"a": a, "d": d, "t": 0.8, "kind": "super", "col": col,
                               "dmg": self.SUPER_DMG * mult, "dodge": False, "crit": False})
            self.popups.append([ax, ay - self.f_h[a] * 0.6, "СУПЕР!", "#FFD700", 0.9, 0.9])
            self.flash_t = 0.1
            return

        kind = random.choices(("file", "fire", "beam", "bolt"), (50, 20, 15, 15))[0]
        if kind == "file":
            name, isdir, idx = random.choice(self.pool)
            ix, iy = self._slot_xy(idx)
            self.proj.append({"kind": "file", "owner": a, "ph": 0, "t": 0.0, "T": 0.28,
                              "x0": ix, "y0": iy, "x1": ax, "y1": ay, "x": ix, "y": iy,
                              "home": a, "arc": random.uniform(-60, 60), "col": col, "trail": [],
                              "name": name, "dir": isdir, "dodge": dodge, "crit": crit,
                              "dmg": self._file_dmg(name, isdir) * mult, "dtrig": False})
        elif kind == "fire":
            ex, ey = self._miss_xy(a, d) if dodge else (dx, dy)
            self.proj.append({"kind": "fire", "owner": a, "ph": 1, "t": 0.0, "T": 0.45,
                              "x0": ax, "y0": ay, "x1": ex, "y1": ey, "x": ax, "y": ay,
                              "home": None if dodge else d, "arc": random.uniform(-60, 60),
                              "col": col, "trail": [], "dodge": dodge, "crit": crit,
                              "dmg": random.uniform(6, 10) * mult, "dtrig": False})
        elif kind == "beam":
            self.beams.append({"a": a, "d": d, "t": 0.4, "kind": "beam", "col": col,
                               "dmg": random.uniform(9, 13) * mult, "dodge": dodge, "crit": crit})
        else:
            self.beams.append({"a": a, "d": d, "t": 0.3, "kind": "bolt", "col": col,
                               "sx": dx + random.uniform(-120, 120),
                               "dmg": random.uniform(8, 12) * mult, "dodge": dodge, "crit": crit})

    def _impact(self, a, d, dmg, dodge, x, y, col, label=None, crit=False):
        dx, dy = self.f_xy[d]
        if dodge:
            self.dodge_t[d] = max(self.dodge_t[d], 0.4)
            self.popups.append([dx, dy - self.f_h[d] * 0.5, "МИМО!", "#FFFFFF", 0.8, 0.8])
            self._spark(x, y, 10, ["#FFFFFF", col], spd=(60, 260), life=(0.2, 0.4))
            return
        floor = 0.0 if self.spawn_done else 1.0          # пока идёт захват слотов, бой не заканчивается
        self.hp[d] = max(floor, self.hp[d] - dmg)
        self.hit_t[d] = 0.45
        self._boom(x, y, col, True)
        txt = "-%d" % round(dmg)
        if label:
            txt = "%s  %s" % (self._short(label, 14), txt)
        if crit:
            txt = "КРИТ! " + txt
        if len(self.popups) < 7:
            self.popups.append([x + random.uniform(-60, 60), y - self.f_h[d] * 0.45, txt, col, 0.9, 0.9])
        if label:
            self._log("[HIT] %s -> %s: %s  -%d HP" % (self.NAMES[a], self.NAMES[d], label, round(dmg)), "warn")

    def _draw_card(self, x, y, name, isdir, col):
        c = self.canvas
        s = self.H * 0.032
        w, h = s * 1.6, s * 2.0
        if isdir:
            c.create_rectangle(x - w / 2, y - h / 2 + 5, x + w / 2, y + h / 2,
                               fill="#FFC83D", outline="#7A5A00", width=2, tags="fx")
            c.create_rectangle(x - w / 2, y - h / 2, x, y - h / 2 + 9,
                               fill="#FFD76A", outline="#7A5A00", width=2, tags="fx")
        else:
            c.create_rectangle(x - w / 2, y - h / 2, x + w / 2, y + h / 2,
                               fill="#F4F4F4", outline="#222222", width=2, tags="fx")
            c.create_rectangle(x - w / 2, y - h / 2, x + w / 2, y - h / 2 + h * 0.28,
                               fill=col, outline="", tags="fx")
            ext = os.path.splitext(name)[1][1:4].upper() or "FILE"
            c.create_text(x, y + h * 0.12, text=ext, fill="#222222",
                          font=self._font("Consolas", s * 0.55), tags="fx")
        self._stext(x, y + h / 2 + 16, self._short(name, 16), "#FFFFFF", self.H * 0.02, tags=("fx",))

    def _b_fighters(self, bt, dt):
        c = self.canvas
        tf = bt - self.fin_t0
        for i in (0, 1):
            self.lunge[i] = max(0.0, self.lunge[i] - dt)
            self.hit_t[i] = max(0.0, self.hit_t[i] - dt)
            self.dodge_t[i] = max(0.0, self.dodge_t[i] - dt)
            d = 1 if i == 0 else -1
            x = self.base_x[i]
            y = self.fy + 7 * math.sin(bt * 3.0 + i * 1.7)
            if self.lunge[i] > 0:
                x += d * 90 * math.sin(math.pi * (1 - self.lunge[i] / 0.3))
            if self.dodge_t[i] > 0:
                y -= 90 * math.sin(math.pi * (1 - self.dodge_t[i] / 0.4))
            if self.hit_t[i] > 0:
                k = self.hit_t[i] / 0.45
                x += -d * 26 * k + random.uniform(-14, 14) * k
                y += random.uniform(-14, 14) * k
            hidden = False
            if self.stage == 2 and i == self.loser:
                y += min(50, tf * 40)
                x += random.uniform(-8, 8)
                hidden = tf > 0.6 and int(bt * 14) % 2 == 0
            c.coords(self.f_item[i], x, y)
            c.itemconfig(self.f_item[i], state="hidden" if hidden else "normal")
            self.f_xy[i] = (x, y)
        if self.stage < 2:                          # аура заряда от болельщика
            for i in (0, 1):
                n = self.boost[i]
                if n > 0:
                    x, y = self.f_xy[i]
                    r = self.f_h[i] * (0.52 + 0.012 * n)
                    col = "#FFD700" if self.super_ready[i] else (self.PC_COL if i == 0 else self.SAM_COL)
                    c.create_oval(x - r, y - r, x + r, y + r, outline=col, width=1 + n // 2, tags="fx")
        else:
            wx, wy = self.f_xy[self.winner]
            r = self.f_h[self.winner] * (0.62 + 0.05 * math.sin(bt * 8))
            c.create_oval(wx - r, wy - r, wx + r, wy + r, outline="#FFD700", width=5, tags="fx")

    def _b_projectiles(self, dt):
        c = self.canvas
        alive = []
        for p in self.proj:
            if p.get("home") is not None:
                p["x1"], p["y1"] = self.f_xy[p["home"]]
            p["t"] += dt
            k = min(1.0, p["t"] / p["T"])
            p["x"] = p["x0"] + (p["x1"] - p["x0"]) * k
            p["y"] = p["y0"] + (p["y1"] - p["y0"]) * k - math.sin(math.pi * k) * p["arc"]
            p["trail"].append((p["x"], p["y"]))
            p["trail"] = p["trail"][-7:]
            if p.get("dodge") and p["ph"] == 1 and k > 0.55 and not p["dtrig"]:
                p["dtrig"] = True
                self.dodge_t[1 - p["owner"]] = 0.4
            if k >= 1.0:
                if p["kind"] == "slot":
                    self.cap[p["owner"]] += 1
                    self._update_cap_text()
                    self._boom(p["x1"], p["y1"], p["col"], False)
                    if len(self.popups) < 7:
                        self.popups.append([p["x1"] + 60, p["y1"], "+1", p["col"], 0.7, 0.7])
                elif p["kind"] == "file" and p["ph"] == 0:      # подобрал файл -> бросок
                    a = p["owner"]
                    d = 1 - a
                    ax, ay = self.f_xy[a]
                    if p["dodge"]:
                        ex, ey = self._miss_xy(a, d)
                        home = None
                    else:
                        ex, ey = self.f_xy[d]
                        home = d
                    p.update(ph=1, t=0.0, T=0.55, x0=ax, y0=ay, x1=ex, y1=ey, home=home,
                             arc=random.uniform(60, 160), trail=[])
                    alive.append(p)
                else:
                    a = p["owner"]
                    self._impact(a, 1 - a, p["dmg"], p["dodge"], p["x1"], p["y1"], p["col"],
                                 p.get("name"), p.get("crit", False))
                continue
            if p["kind"] == "slot":
                r = 14 + 40 * (1 - k)
                c.create_oval(p["x1"] - r, p["y1"] - r, p["x1"] + r, p["y1"] + r,
                              outline=p["col"], width=3, tags="fx")
                c.create_line(p["x1"] - r - 8, p["y1"], p["x1"] + r + 8, p["y1"],
                              fill=p["col"], width=2, tags="fx")
                c.create_line(p["x1"], p["y1"] - r - 8, p["x1"], p["y1"] + r + 8,
                              fill=p["col"], width=2, tags="fx")
            for j, (tx, ty) in enumerate(p["trail"]):
                s = 3 + j * 1.6
                c.create_oval(tx - s, ty - s, tx + s, ty + s, fill=p["col"], outline="", tags="fx")
            if p["kind"] == "file":
                self._draw_card(p["x"], p["y"], p["name"], p["dir"], p["col"])
            else:
                c.create_oval(p["x"] - 12, p["y"] - 12, p["x"] + 12, p["y"] + 12,
                              fill="white", outline=p["col"], width=4, tags="fx")
            alive.append(p)
        self.proj = alive

    def _b_beams(self, dt):
        alive = []
        for b in self.beams:
            b["t"] -= dt
            ax, ay = self.f_xy[b["a"]]
            dx, dy = self.f_xy[b["d"]]
            if b["kind"] == "bolt":
                self._beam(b["sx"], 0, dx, dy, 9, "#BFE9FF", 40)
            else:
                big = b["kind"] == "super"
                for _ in range(6 if big else 3):
                    self._beam(ax, ay + random.uniform(-20, 20), dx, dy + random.uniform(-20, 20),
                               random.randint(6, 26 if big else 13),
                               random.choice((b["col"], "#FFFFFF", "#FFD700")), 26)
                if big and random.random() < 0.3:
                    self.flash_t = 0.04
            if b["t"] <= 0:
                self._impact(b["a"], b["d"], b["dmg"], b["dodge"], dx, dy, b["col"], None, b["crit"])
            else:
                alive.append(b)
        self.beams = alive

    def _b_ambient(self, dt):
        W, H = self.W, self.H
        self.ember_acc += dt * 30
        while self.ember_acc >= 1:
            self.ember_acc -= 1
            if len(self.particles) < 240:
                lf = random.uniform(2.0, 4.0)
                self.particles.append([random.uniform(0, W), H + 10, random.uniform(-30, 30),
                                       -random.uniform(60, 220), lf, lf,
                                       random.choice(self.EMBER), random.uniform(2, 3.5), 0.0])
        self.next_light -= dt
        if self.next_light <= 0 and self.stage < 2:
            self.next_light = random.uniform(2.2, 4.0)
            self.bolts.append([random.uniform(W * 0.2, W * 0.8), 0,
                               random.uniform(W * 0.1, W * 0.9), random.uniform(H * 0.5, H * 0.9), 0.2])
            self.flash_t = 0.08

    def _b_hud(self, bt, dt):
        c = self.canvas
        for i in (0, 1):
            if self.hp_vis[i] > self.hp[i]:
                self.hp_vis[i] = max(self.hp[i], self.hp_vis[i] - dt * 22)
            else:
                self.hp_vis[i] = self.hp[i]
            x0, x1 = self.bars[i]
            bw = x1 - x0
            fr = max(0.0, min(1.0, self.hp[i] / 100.0))
            fv = max(0.0, min(1.0, self.hp_vis[i] / 100.0))
            y0, y1 = self.bar_y, self.bar_y + self.bar_h
            if i == 0:
                c.coords(self.hp_fill[i], x1 - bw * fr, y0, x1, y1)
                c.coords(self.hp_chip[i], x1 - bw * fv, y0, x1, y1)
            else:
                c.coords(self.hp_fill[i], x0, y0, x0 + bw * fr, y1)
                c.coords(self.hp_chip[i], x0, y0, x0 + bw * fv, y1)
            if self.hit_t[i] > 0:
                col = "#FFFFFF"
            elif self.hp[i] > 55:
                col = "#2ECC40"
            elif self.hp[i] > 25:
                col = "#FFDC00"
            else:
                col = "#FF4136"
            c.itemconfig(self.hp_fill[i], fill=col)
        for s in (0, 1):
            ready = self.super_ready[s]
            for j, it in enumerate(self.seg_items[s]):
                if ready:
                    col = "#FFD700" if int(bt * 8) % 2 == 0 else "#FFFFFF"
                elif j < self.boost[s]:
                    col = self.PC_COL if s == 0 else self.SAM_COL
                else:
                    col = "#222222"
                c.itemconfig(it, fill=col)
            if ready:
                self._set_stext(self.help_txt[s], "СУПЕР ГОТОВ!", "#FFD700")
            else:
                self._set_stext(self.help_txt[s], "[←] ПОМОГИ ПК" if s == 0 else "ПОМОГИ САМУ [→]",
                                "#00FF00" if s == 0 else "#FF0000")
        self._set_stext(self.timer_txt, "%02d" % self.rem)

    # ================================================================ ФИНАЛ
    def _start_final(self):
        self.stop_battle = True
        if self.log_win:
            try:
                self.log_win.destroy()
            except Exception:
                pass
            self.log_win = None
        W, H = self.W, self.H
        fw = tk.Toplevel(self.root)
        fw.overrideredirect(True)
        fw.config(bg="black")
        fw.attributes("-topmost", True)
        fw.geometry("%dx%d+0+0" % (W, H))
        fc = tk.Canvas(fw, width=W, height=H, bg="black", highlightthickness=0, bd=0)
        fc.pack(fill="both", expand=True)
        fw.focus_force()
        fw.bind("<Escape>", lambda e: self._cleanup_and_exit())
        self.fw, self.canvas = fw, fc
        self.particles, self.rings, self.popups, self.bolts = [], [], [], []
        self.flash_t = 0.0

        self.series = self._load_series("ram.png", H * 0.13, 14, 0.08)
        if self.pc_wins:
            ch, self.cw, self.chh = self._load_img("pc.png", H * 0.50)
            self.char_xy = (W / 2, H * 0.54)
            self.ram_from = (W * 0.88, H * 0.30)
            self.ram_to = self.char_xy
            self.T_WIND, self.T_MOVE = 1.2, 3.2
        else:
            ch, self.cw, self.chh = self._load_img("sam.png", H * 0.56)
            self.char_xy = (W / 2, H * 0.50)
            self.ram_from = (W / 2, H * 0.93)
            self.ram_to = (W / 2, -H * 0.12)
            self.T_WIND, self.T_MOVE = 1.2, 3.0
        self.f_char = fc.create_image(self.char_xy[0], self.char_xy[1], image=ch)
        self.f_ram = fc.create_image(self.ram_from[0], self.ram_from[1], image=self.series[0])
        self.ram_alive = True
        self.final_text = None
        self.text_t0 = 0.0
        self.music_cut = False
        self.glitch_t0 = None
        self.f0 = time.perf_counter()
        self.last = self.f0
        self._final_tick()

    def _final_tick(self):
        if self.exiting:
            return
        now = time.perf_counter()
        dt = min(0.05, max(0.001, now - self.last))
        self.last = now
        t = now - self.f0
        c, W, H = self.canvas, self.W, self.H
        cx, cy = self.char_xy
        wind = min(1.0, t / self.T_WIND)
        p = max(0.0, min(1.0, (t - self.T_WIND) / self.T_MOVE))
        e = self._ease(p)
        c.delete("fx")
        self._draw_flash(dt)

        if self.pc_wins:
            amp = 3 + 10 * wind + (6 if 0 < p < 1 else 0) if self.ram_alive else 5
        else:
            amp = 4 + 16 * wind + (8 if 0 < p < 1 else 0) if self.ram_alive else 10
        c.coords(self.f_char, cx + random.uniform(-amp, amp), cy + random.uniform(-amp, amp))

        if self.ram_alive:
            fx, fy = self.ram_from
            tx, ty = self.ram_to
            if self.pc_wins:
                x = fx + (tx - fx) * e + math.sin(math.pi * e) * H * 0.10
                y = fy + (ty - fy) * e - math.sin(math.pi * e) * H * 0.12
                kk = max(0.0, (e - 0.45) / 0.55)
                col_set = ["#00FF66", "#39FF14", "#FFFFFF"]
            else:
                q = e ** 1.8
                x = fx + math.sin(q * 14) * 22 * (1 - q * 0.5)
                y = fy + (ty - fy) * q
                kk = 0.0
                col_set = ["#FF2D2D", "#FF6EC7", "#FFFFFF"]
                if t >= self.T_WIND and not self.music_cut:
                    self.music_cut = True
                    try:
                        pygame.mixer.music.fadeout(900)
                    except Exception:
                        pass
            if p <= 0:
                x, y = fx + random.uniform(-4, 4), fy + random.uniform(-4, 4)
            c.coords(self.f_ram, x, y)
            c.itemconfig(self.f_ram, image=self.series[int(kk * (len(self.series) - 1))])
            if t >= self.T_WIND * 0.5:
                if self.pc_wins:
                    for _ in range(3):
                        a = random.uniform(0, 6.2832)
                        r = random.uniform(30, 160)
                        sx, sy = cx + math.cos(a) * r, cy + math.sin(a) * r
                        self.particles.append([sx, sy, (x - sx) * 3, (y - sy) * 3, 0.3, 0.3,
                                               random.choice(col_set), 3, 0.0])
                else:
                    for _ in range(4):
                        self.particles.append([x + random.uniform(-40, 40), y + random.uniform(0, 60),
                                               random.uniform(-40, 40), -random.uniform(200, 600),
                                               0.5, 0.5, random.choice(col_set), 3, 0.0])
            if p >= 1.0:
                self.ram_alive = False
                c.delete(self.f_ram)
                if self.pc_wins:
                    self._boom(cx, cy, self.PC_COL, True)
                    self._spark(cx, cy, 120, [self.PC_COL, "#FFD700", "#FFFFFF"],
                                spd=(200, 900), life=(0.5, 1.2))
                    self.final_text = self._stext(W / 2, H * 0.88,
                                                  "ФАТАЛИТИ! ПК СЪЕЛ ОПЕРАТИВКУ И ВЫЖИЛ!",
                                                  "#FF2D2D", H * 0.08, width=W * 0.92)
                    self.text_t0 = t
                    self.root.after(4500, self._cleanup_and_exit)
                else:
                    try:
                        pygame.mixer.music.stop()
                    except Exception:
                        pass
                    self.glitch_t0 = t
        elif self.pc_wins:
            ts = t - self.text_t0
            slam = 1 + 1.0 * max(0.0, 1 - ts / 0.35)
            col = "#FF2D2D" if int(ts * 5) % 2 == 0 else "#FFD700"
            self._set_stext(self.final_text, None, col, H * 0.07 * slam, W / 2, H * 0.88)
            self._spark(random.uniform(0, W), random.uniform(0, H * 0.7), 2,
                        [self.PC_COL, "#FFD700", "#FFFFFF"], spd=(20, 120), life=(0.6, 1.2),
                        grav=120.0)
            if random.random() < dt * 3:
                self._boom(random.uniform(W * 0.2, W * 0.8), random.uniform(H * 0.1, H * 0.5),
                           random.choice(self.NEON), False)
        elif self.glitch_t0 is not None:
            tg = t - self.glitch_t0
            for _ in range(14):
                x0, y0 = random.uniform(0, W), random.uniform(0, H)
                c.create_rectangle(x0, y0, x0 + random.uniform(40, W * 0.5), y0 + random.uniform(4, 40),
                                   fill=random.choice(("#0078D7", "#FFFFFF", "#000000", "#FF0000", "#00FFFF")),
                                   outline="", tags="fx")
            if tg >= 0.9:
                self._show_bsod()
                return

        self._draw_fx(dt, 360)
        self.root.after(8, self._final_tick)

    # ---------------------------------------------------------- QR-код (рикролл)
    @staticmethod
    def _qr_matrix(text):
        """QR Model 2, версия 2 (25x25), уровень коррекции L, байтовый режим."""
        data = text.encode("utf-8")
        N, DATA_CW, EC_CW = 25, 34, 10
        if len(data) > 32:
            raise ValueError("too long")
        bits = "0100" + format(len(data), "08b") + "".join(format(b, "08b") for b in data)
        bits += "0" * min(4, DATA_CW * 8 - len(bits))
        bits += "0" * (-len(bits) % 8)
        cw = [int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)]
        k = 0
        while len(cw) < DATA_CW:
            cw.append((0xEC, 0x11)[k % 2])
            k += 1
        # GF(256), порождающий многочлен, остаток Рида-Соломона
        exp, log, x = [0] * 512, [0] * 256, 1
        for i in range(255):
            exp[i], log[x] = x, i
            x <<= 1
            if x & 0x100:
                x ^= 0x11D
        for i in range(255, 512):
            exp[i] = exp[i - 255]

        def mul(a, b):
            return 0 if a == 0 or b == 0 else exp[log[a] + log[b]]

        gen = [1]
        for i in range(EC_CW):
            ng = [0] * (len(gen) + 1)
            for j, cf in enumerate(gen):
                ng[j] ^= cf
                ng[j + 1] ^= mul(cf, exp[i])
            gen = ng
        rem = [0] * EC_CW
        for b in cw:
            f = b ^ rem[0]
            rem = rem[1:] + [0]
            for j in range(EC_CW):
                rem[j] ^= mul(gen[j + 1], f)
        allcw = cw + rem

        # служебные модули
        m = [[False] * N for _ in range(N)]
        fn = [[False] * N for _ in range(N)]

        def put(r, c, v):
            m[r][c] = v
            fn[r][c] = True

        for r0, c0 in ((0, 0), (0, N - 7), (N - 7, 0)):
            for dr in range(-1, 8):
                for dc in range(-1, 8):
                    r, c = r0 + dr, c0 + dc
                    if 0 <= r < N and 0 <= c < N:
                        put(r, c, 0 <= dr <= 6 and 0 <= dc <= 6 and max(abs(dr - 3), abs(dc - 3)) != 2)
        for i in range(N):
            put(6, i, i % 2 == 0)
            put(i, 6, i % 2 == 0)
        for r0, c0 in ((0, 0), (0, N - 7), (N - 7, 0)):     # перекрасить finder поверх таймингов
            for dr in range(-1, 8):
                for dc in range(-1, 8):
                    r, c = r0 + dr, c0 + dc
                    if 0 <= r < N and 0 <= c < N:
                        put(r, c, 0 <= dr <= 6 and 0 <= dc <= 6 and max(abs(dr - 3), abs(dc - 3)) != 2)
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                put(18 + dr, 18 + dc, max(abs(dr), abs(dc)) != 1)
        for i in range(9):
            fn[8][i] = fn[i][8] = True
        for i in range(8):
            fn[8][N - 1 - i] = fn[N - 1 - i][8] = True
        put(N - 8, 8, True)

        # данные змейкой
        i = 0
        right = N - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(N):
                for j in range(2):
                    xx = right - j
                    up = ((right + 1) & 2) == 0
                    yy = N - 1 - vert if up else vert
                    if not fn[yy][xx] and i < len(allcw) * 8:
                        m[yy][xx] = ((allcw[i >> 3] >> (7 - (i & 7))) & 1) == 1
                        i += 1
            right -= 2

        masks = [lambda r, c: (r + c) % 2 == 0, lambda r, c: r % 2 == 0,
                 lambda r, c: c % 3 == 0, lambda r, c: (r + c) % 3 == 0,
                 lambda r, c: (r // 2 + c // 3) % 2 == 0,
                 lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
                 lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
                 lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0]

        def with_mask(mk):
            g = [row[:] for row in m]
            for r in range(N):
                for c in range(N):
                    if not fn[r][c] and masks[mk](r, c):
                        g[r][c] = not g[r][c]
            d = 1 << 3 | mk                      # уровень L = 01, затем номер маски
            rm = d
            for _ in range(10):
                rm = (rm << 1) ^ ((rm >> 9) * 0x537)
            fb = (d << 10 | rm) ^ 0x5412
            bit = lambda n: ((fb >> n) & 1) == 1
            for n in range(6):
                g[n][8] = bit(n)
            g[7][8], g[8][8], g[8][7] = bit(6), bit(7), bit(8)
            for n in range(9, 15):
                g[8][14 - n] = bit(n)
            for n in range(8):
                g[8][N - 1 - n] = bit(n)
            for n in range(8, 15):
                g[N - 15 + n][8] = bit(n)
            g[N - 8][8] = True
            return g

        def penalty(g):
            p = 0
            for lines in (g, [list(col) for col in zip(*g)]):
                for row in lines:
                    run = 1
                    for a in range(1, N):
                        if row[a] == row[a - 1]:
                            run += 1
                        else:
                            if run >= 5:
                                p += 3 + run - 5
                            run = 1
                    if run >= 5:
                        p += 3 + run - 5
                    s = "".join("1" if v else "0" for v in row)
                    p += 40 * (s.count("10111010000") + s.count("00001011101"))
            for r in range(N - 1):
                for c in range(N - 1):
                    if g[r][c] == g[r][c + 1] == g[r + 1][c] == g[r + 1][c + 1]:
                        p += 3
            dark = sum(v for row in g for v in row)
            p += 10 * (math.ceil(abs(dark * 20 - N * N * 10) / (N * N)) - 1)
            return p

        return min((with_mask(mk) for mk in range(8)), key=penalty)

    # ================================================================ BSOD
    def _show_bsod(self):
        W, H = self.W, self.H
        try:
            self.fw.destroy()
        except Exception:
            pass
        b = tk.Toplevel(self.root)
        b.overrideredirect(True)
        b.config(bg="#0078D7", cursor="none")
        b.attributes("-topmost", True)
        b.geometry("%dx%d+0+0" % (W, H))
        cv = tk.Canvas(b, width=W, height=H, bg="#0078D7", highlightthickness=0, bd=0, cursor="none")
        cv.pack(fill="both", expand=True)
        b.bind("<Escape>", lambda e: self._cleanup_and_exit())
        self.root.bind_all("<Escape>", lambda e: self._cleanup_and_exit())
        self.bsod = b

        def F(px):
            return ("Segoe UI", -int(px))

        lm = int(W * 0.085)
        cv.create_text(lm, int(H * 0.07), text=":(", fill="white", font=F(H * 0.20), anchor="nw")
        cv.create_text(lm, int(H * 0.37), fill="white", font=F(H * 0.034), anchor="nw",
                       width=int(W * 0.78),
                       text="На вашем ПК возникла проблема, и его необходимо перезагрузить. "
                            "Оперативная память была изъята Сэмом Альтманом для обучения "
                            "следующей версии нейросети. Все ваши гигабайты теперь принадлежат ему.")
        self.bsod_cv = cv
        self.bsod_pct = cv.create_text(lm, int(H * 0.56), text="0% завершено", fill="white",
                                       font=F(H * 0.034), anchor="nw")
        self.pct = 0

        # настоящий QR-код: рикролл
        grid = self._qr_matrix(self.RICK_URL)
        n, quiet = len(grid), 3
        mod = max(3, int(H * 0.17) // (n + 2 * quiet))
        q = mod * (n + 2 * quiet)
        y0 = int(H * 0.655)
        cv.create_rectangle(lm, y0, lm + q, y0 + q, fill="white", outline="")
        for r in range(n):
            start = None
            for k in range(n + 1):
                dark = k < n and grid[r][k]
                if dark and start is None:
                    start = k
                elif not dark and start is not None:
                    cv.create_rectangle(lm + (start + quiet) * mod, y0 + (r + quiet) * mod,
                                        lm + (k + quiet) * mod, y0 + (r + quiet + 1) * mod,
                                        fill="black", outline="")
                    start = None
        cv.create_text(lm + q + int(H * 0.03), y0 + mod * quiet, fill="white", font=F(H * 0.0175), anchor="nw",
                       width=int(W * 0.6),
                       text="Дополнительные сведения об этой ошибке: https://www.windows.com/stopcode\n\n"
                            "Если вы позвоните в службу поддержки, сообщите им следующие данные:\n"
                            "Код остановки: WHEA_UNCORRECTABLE_SAM_ALTMAN_ERROR\n"
                            "Что не удалось: ram.sys (модули ОЗУ изъяты, осталось 0 ГБ)")
        cv.create_text(lm, int(H * 0.92), fill="white", font=F(H * 0.02), anchor="nw",
                       text="Нажмите ESC, чтобы вернуть память (и рабочий стол) на место.")
        b.focus_force()
        self.root.after(250, self._bsod_tick)

    def _bsod_tick(self):
        if self.exiting:
            return
        if self.pct < 100:
            self.pct = min(100, self.pct + random.choice((1, 1, 2, 3)))
            self.bsod_cv.itemconfig(self.bsod_pct, text="%d%% завершено" % self.pct)
        self.root.after(random.randint(150, 320), self._bsod_tick)

    # ================================================================ выход
    def _remove_files(self):
        for p in list(self.created_files):
            try:
                os.remove(p)
            except Exception:
                pass
        self.created_files = []

    def _final_cleanup(self):
        if self.cleaned:
            return
        self.cleaned = True
        self.abort_spawn = True
        if self.spawn_thread is not None and self.spawn_thread.is_alive():
            self.spawn_thread.join(timeout=1.5)
        self._remove_files()
        if self.wall_changed and self.orig_wallpaper and os.path.exists(self.orig_wallpaper):
            self._set_wallpaper(self.orig_wallpaper)
        try:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        except Exception:
            pass

    def _cleanup_and_exit(self):
        if self.exiting:
            return
        self.exiting = True
        self._final_cleanup()
        try:
            self.root.destroy()
        except Exception:
            pass

    # ================================================================ запуск
    def run(self):
        try:
            self._start_intro()
            self.root.mainloop()
            if self.exiting:
                return

            try:
                dst = os.path.join(tempfile.gettempdir(), "bg_battle_wall.png")
                shutil.copyfile(resource_path("bg_battle.png"), dst)
                self.wall_changed = self._set_wallpaper(dst)
            except Exception:
                pass
            self._play_music("mk.ogg", -1)

            self._start_battle()
            self.root.mainloop()
        finally:
            self._final_cleanup()


if __name__ == "__main__":
    MemeBattle().run()