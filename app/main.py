#!/usr/bin/env python3
"""AnberVc — dobór obrotów maszyny do średnicy narzędzia (limit prędkości
skrawania v_c) dla Anbernic RG40XX V. Szlifowanie/cięcie, wiercenie, frezowanie.

    v_c = π · D · n / 60   [m/s]     (= π·D·n/1000 [m/min])

Dobiera NAJWYŻSZE bezpieczne nastawienie obrotów: n_bezp = min(z limitu v_c,
obrotów znamionowych narzędzia, max obrotów maszyny).

Sterowanie (pad RG40XX V) — model regulacji jak AnberPKM/AnberWM:
  D-pad ↑/↓      wybór parametru
  D-pad ←/→      − / + wartość (o bieżący krok)
  L1/R1 · L2/R2  szybki krok − / + (L2/R2 = większy)
  Y              zmiana kroku (0.1 / 1 / 10 / 100 / 1000)
  A              reset zaznaczonego pola do wartości presetu
  X              reset WSZYSTKICH pól do presetu
  MENU / MODE    wyjście
  POWER          ekran off/on (apka działa dalej)

Baza SDL2/render/backlight jak AnberHex; logika w vc_lib (bez SDL, pytest+CI).
NIE SDL_INIT_JOYSTICK (grabuje event1); PYSDL2_DLL_PATH ustawia wrapper .sh.
"""
import os, sys, time, select, ctypes
from pathlib import Path

# ── logika w vc_lib (testowalna bez SDL) ─────────────────────────────────────
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))                 # dla power_screen
sys.path.insert(0, str(_HERE.parent))          # dla pakietu vc_lib
from vc_lib import (recommend, preset_params, PRESETS, VC_UNITS, BINDING_PL,  # noqa: E402
                    DEFAULTS)

if __name__ == '__main__' and '--selftest' in sys.argv:
    from vc_lib.core import _selftest
    raise SystemExit(_selftest())

os.environ.pop('SDL_VIDEODRIVER', None)
os.environ.setdefault('PYSDL2_DLL_PATH', '/usr/lib')
import sdl2                                     # noqa: E402
from PIL import Image, ImageDraw, ImageFont     # noqa: E402
from power_screen import ScreenPowerToggle      # noqa: E402

W, H = 640, 480
FONT_PATH = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'

BG   = (10, 14, 20, 255)
FG   = (210, 220, 230, 255)
ACC  = (90, 190, 255, 255)
GRN  = (95, 225, 125, 255)
YEL  = (255, 205, 70, 255)
RED  = (240, 95, 95, 255)
DIM  = (120, 132, 148, 255)
SEP  = (40, 50, 65, 255)
SEL  = (255, 200, 80, 255)
BOXG = (30, 70, 45, 255)
ROWSEL = (35, 55, 80, 255)

# evdev — kody jak AnberPKM/AnberWM (potwierdzone na egzemplarzu Karola)
EV_KEY, EV_ABS = 1, 3
BTN_A, BTN_B, BTN_X, BTN_Y = 304, 305, 307, 308
BTN_L1, BTN_R1, BTN_L2, BTN_R2 = 310, 311, 312, 313
BTN_MODE, KEY_MENU = 316, 354
EXIT_KEYS = {BTN_MODE, KEY_MENU}
ABS_X, ABS_Y = 16, 17

STEP_MODES = [0.1, 1, 10, 100, 1000]

# Pola: (name, unit, default, step_base, min, max, kind, desc)
#   kind: 'num' (krok=STEP_MODES), 'int' (±1), 'idx' (cykl z zawijaniem)
FIELDS = [
    ('preset',       '',        0,      1,   0, len(PRESETS) - 1, 'idx', 'Preset (operacja/materiał)'),
    ('diameter_mm',  'mm',      115.0,  1.0, 0.5, 2000,   'num', 'Średnica narzędzia D'),
    ('vc',           '',        80.0,   1.0, 0.1, 100000, 'num', 'Prędkość skrawania v_c'),
    ('vc_unit',      '',        0,      1,   0, 1,        'idx', 'Jednostka v_c'),
    ('rpm_min',      'obr/min', 3000,   100, 0, 200000,   'num', 'Min obroty maszyny'),
    ('rpm_max',      'obr/min', 12000,  100, 1, 200000,   'num', 'Max obroty maszyny'),
    ('n_settings',   'szt',     7,      1,   1, 30,       'int', 'Liczba nastawień'),
    ('tool_max_rpm', 'obr/min', 12500,  100, 1, 1000000, 'num', 'Znam. obroty narzędzia'),
]
LOG = Path('/mnt/data/anbervc.log')


class VcApp:
    def __init__(self):
        try:
            self._dbg = LOG.open('a', encoding='utf-8')
        except Exception:
            self._dbg = open(os.devnull, 'w')
        self._log(f'=== START {time.strftime("%H:%M:%S")} ===')

        self.field_idx = 0
        self.step_idx = 1                      # domyślnie krok = 1
        self.vals = {f[0]: f[2] for f in FIELDS}
        self._load_preset(0)                   # domyślny preset = szlifierka
        self.rec = None
        self.dirty = True
        self._recompute()

        sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_EVENTS)
        self.win = sdl2.SDL_CreateWindow(
            b"AnberVc", sdl2.SDL_WINDOWPOS_UNDEFINED, sdl2.SDL_WINDOWPOS_UNDEFINED,
            0, 0, sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP | sdl2.SDL_WINDOW_SHOWN)
        self.ren = sdl2.SDL_CreateRenderer(self.win, -1, sdl2.SDL_RENDERER_SOFTWARE) \
            or sdl2.SDL_CreateRenderer(self.win, -1, 0)
        self.img = Image.new('RGBA', (W, H), BG)
        self.draw = ImageDraw.Draw(self.img)
        self.f_sm = ImageFont.truetype(FONT_PATH, 13)
        self.f_md = ImageFont.truetype(FONT_PATH, 16)
        self.f_lg = ImageFont.truetype(FONT_PATH, 22)
        self.f_xl = ImageFont.truetype(FONT_PATH, 30)
        self._tex = None

        # event1 = pad + D-pad (grab z fallbackiem no-grab), jak AnberHex
        self._gp = None
        try:
            import evdev
            self._gp = evdev.InputDevice('/dev/input/event1')
            self._gp.grab()
            while select.select([self._gp.fd], [], [], 0)[0]:
                self._gp.read()
        except Exception as e:
            self._log(f'evdev grab FAIL ({e}), retry no-grab')
            try:
                import evdev as _ev
                self._gp = _ev.InputDevice('/dev/input/event1')
            except Exception as e2:
                self._log(f'evdev FAIL: {e2}')
                self._gp = None

        self._pwr = ScreenPowerToggle()        # POWER → ekran off/on (event0)

    def _log(self, msg):
        try:
            self._dbg.write(msg + '\n'); self._dbg.flush()
        except Exception:
            pass

    # ── model parametrów ─────────────────────────────────────────────────────
    def _load_preset(self, idx):
        p = preset_params(PRESETS[int(idx)])
        self.vals['preset'] = int(idx)
        self.vals['diameter_mm'] = p['diameter_mm']
        self.vals['vc'] = p['vc']
        self.vals['vc_unit'] = VC_UNITS.index(p['vc_unit'])
        self.vals['rpm_min'] = p['rpm_min']
        self.vals['rpm_max'] = p['rpm_max']
        self.vals['n_settings'] = int(p['n_settings'])
        self.vals['tool_max_rpm'] = p['tool_max_rpm']

    def _reset_field(self, name):
        """Reset pola do wartości z bieżącego presetu."""
        p = preset_params(PRESETS[int(self.vals['preset'])])
        if name == 'vc_unit':
            self.vals['vc_unit'] = VC_UNITS.index(p['vc_unit'])
        elif name == 'preset':
            self._load_preset(self.vals['preset'])
        elif name in p:
            self.vals[name] = p[name]

    def _adjust(self, dy, step_boost=0):
        f = FIELDS[self.field_idx]
        name, unit, _def, _sb, mn, mx, kind, _desc = f
        if kind == 'idx':
            n = int(mx - mn + 1)
            newv = (int(self.vals[name]) - mn + dy) % n + mn
            self.vals[name] = newv
            if name == 'preset':
                self._load_preset(newv)
        elif kind == 'int':
            v = int(self.vals[name]) + dy
            self.vals[name] = int(max(mn, min(mx, v)))
        else:
            idx = min(len(STEP_MODES) - 1, self.step_idx + step_boost)
            factor = STEP_MODES[idx]
            v = self.vals[name] + dy * factor
            self.vals[name] = max(mn, min(mx, round(v, 6)))
        self.dirty = True
        self._recompute()

    def _cycle_step(self):
        self.step_idx = (self.step_idx + 1) % len(STEP_MODES)
        self.dirty = True

    def _recompute(self):
        try:
            self.rec = recommend(
                rpm_min=self.vals['rpm_min'], rpm_max=self.vals['rpm_max'],
                n_settings=int(self.vals['n_settings']),
                tool_max_rpm=self.vals['tool_max_rpm'],
                vc=self.vals['vc'], vc_unit=VC_UNITS[int(self.vals['vc_unit'])],
                diameter_mm=self.vals['diameter_mm'])
        except Exception as e:
            self._log(f'recompute ERR: {e}')
            self.rec = None

    # ── render ───────────────────────────────────────────────────────────────
    def _t(self, x, y, txt, font, color):
        self.draw.text((x, y), txt, font=font, fill=color)

    def _fmt_val(self, name, v):
        if name == 'vc_unit':
            return VC_UNITS[int(v)]
        if name == 'preset':
            return PRESETS[int(v)]['name']
        if name == 'n_settings':
            return str(int(v))
        if isinstance(v, float):
            return f'{v:g}'
        return str(v)

    def render(self):
        d = self.draw
        d.rectangle([(0, 0), (W, H)], fill=BG)
        self._t(14, 8, 'AnberVc', self.f_lg, ACC)
        self._t(150, 16, 'dobór obrotów: szlifowanie / wiercenie / frezowanie',
                self.f_sm, DIM)
        self._t(W - 150, 16, f'krok: {STEP_MODES[self.step_idx]:g}', self.f_sm, YEL)
        d.line([(0, 38), (W, 38)], fill=SEP, width=1)

        # ── lewa kolumna: parametry ──
        y = 48
        for i, f in enumerate(FIELDS):
            name, unit, _def, _sb, _mn, _mx, kind, desc = f
            sel = (i == self.field_idx)
            col = SEL if sel else FG
            mark = '>' if sel else ' '
            self._t(12, y, f'{mark} {desc}', self.f_sm, col)
            val_str = self._fmt_val(name, self.vals[name])
            unit_str = f' {unit}' if unit else ''
            self._t(28, y + 14, f'{val_str}{unit_str}', self.f_md,
                    col if sel else DIM)
            y += 34
        d.line([(312, 38), (312, H - 26)], fill=SEP, width=1)

        # ── prawa kolumna: wynik ──
        rx = 324
        r = self.rec
        if r is None:
            self._t(rx, 60, 'błąd obliczeń', self.f_lg, RED)
        else:
            binding = BINDING_PL.get(r.binding, r.binding)
            self._t(rx, 46, f'n_bezp = {r.n_safe:.0f} obr/min', self.f_md, ACC)
            self._t(rx, 66, f'(wiąże: {binding})', self.f_sm, DIM)

            if r.recommended_k is None:
                d.rectangle([(rx, 86), (W - 10, 128)], fill=(70, 25, 25, 255),
                            outline=RED, width=2)
                self._t(rx + 8, 92, 'BRAK bezpiecznego', self.f_md, RED)
                self._t(rx + 8, 110, 'nastawienia!', self.f_md, RED)
            else:
                d.rectangle([(rx, 86), (W - 10, 140)], fill=BOXG,
                            outline=GRN, width=2)
                self._t(rx + 8, 90, f'Nastawienie {r.recommended_k}', self.f_md, GRN)
                self._t(rx + 8, 108, f'{r.rec_rpm:.0f} obr/min', self.f_lg, FG)
                self._t(rx + 8, 122, '', self.f_sm, FG)
            if r.recommended_k is not None:
                self._t(rx, 148, f'v_c = {r.rec_v:.1f} {r.vc_unit}', self.f_md, FG)
                self._t(rx, 168, f'margines do limitu: {r.margin_pct:.1f} %',
                        self.f_sm, GRN if r.margin_pct >= 0 else RED)

            # tabela nastawień
            ty = 194
            self._t(rx, ty, ' k   obr/min     v_c      ok', self.f_sm, DIM)
            ty += 16
            for s in r.settings:
                if ty > H - 60:
                    self._t(rx, ty, '...', self.f_sm, DIM)
                    break
                is_rec = (s.k == r.recommended_k)
                if is_rec:
                    d.rectangle([(rx - 2, ty - 1), (W - 10, ty + 14)], fill=ROWSEL)
                flag = 'OK' if s.safe else 'NIE'
                fcol = GRN if s.safe else RED
                line = f'{s.k:>2}  {s.rpm:>8.0f}  {s.v:>7.1f}   '
                self._t(rx, ty, line, self.f_sm, FG if s.safe else DIM)
                self._t(rx + 214, ty, flag, self.f_sm, fcol)
                ty += 16

        # ostrzeżenia (na czerwono, na dole)
        wy = H - 44
        if r and r.warnings:
            for w in r.warnings[:2]:
                self._t(12, wy, ('! ' + w)[:96], self.f_sm, RED)
                wy += 14

        # stopka
        self._t(12, H - 14,
                'D-pad ↑↓ pole  ←→ ± wartość  L/R szybki  Y krok  A/X reset  MENU wyjście',
                self.f_sm, DIM)

        # blit
        raw = self.img.tobytes()
        surf = sdl2.SDL_CreateRGBSurfaceWithFormatFrom(
            raw, W, H, 32, W * 4, sdl2.SDL_PIXELFORMAT_RGBA32)
        if self._tex:
            sdl2.SDL_DestroyTexture(self._tex)
        self._tex = sdl2.SDL_CreateTextureFromSurface(self.ren, surf)
        sdl2.SDL_FreeSurface(surf)
        sdl2.SDL_RenderClear(self.ren)
        sdl2.SDL_RenderCopy(self.ren, self._tex, None, None)
        sdl2.SDL_RenderPresent(self.ren)
        self.dirty = False

    # ── pętla ────────────────────────────────────────────────────────────────
    def run(self):
        ev = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(ev)):
            pass
        start_ms = sdl2.SDL_GetTicks()
        GUARD_MS = 1500

        while True:
            now = sdl2.SDL_GetTicks()
            guard = (now - start_ms) < GUARD_MS

            self._pwr.poll()
            self._pwr.tick(now)
            if self._pwr.is_off:
                sdl2.SDL_Delay(50)
                # nadal drenuj event1, by MENU po przebudzeniu działał
                if self._gp and select.select([self._gp.fd], [], [], 0)[0]:
                    self._gp.read()
                continue

            if self.dirty:
                self.render()

            while sdl2.SDL_PollEvent(ctypes.byref(ev)):
                if ev.type == sdl2.SDL_QUIT and not guard:
                    self.quit(); return

            if self._gp and select.select([self._gp.fd], [], [], 0)[0]:
                for e in self._gp.read():
                    if guard:
                        continue
                    if e.type == EV_KEY and e.value == 1:
                        if e.code in EXIT_KEYS:
                            self.quit(); return
                        elif e.code == BTN_Y:
                            self._cycle_step()
                        elif e.code == BTN_A:
                            self._reset_field(FIELDS[self.field_idx][0])
                            self.dirty = True; self._recompute()
                        elif e.code == BTN_X:
                            self._load_preset(self.vals['preset'])
                            self.dirty = True; self._recompute()
                        elif e.code in (BTN_L1, BTN_R1, BTN_L2, BTN_R2):
                            dy = 1 if e.code in (BTN_R1, BTN_R2) else -1
                            boost = 1 if e.code in (BTN_L1, BTN_R1) else 2
                            self._adjust(dy, step_boost=boost)
                    elif e.type == EV_ABS:
                        if e.code == ABS_Y and e.value != 0:
                            self.field_idx = (self.field_idx +
                                              (1 if e.value > 0 else -1)) % len(FIELDS)
                            self.dirty = True
                        elif e.code == ABS_X and e.value != 0:
                            self._adjust(1 if e.value > 0 else -1)

            sdl2.SDL_Delay(16)

    def quit(self):
        self._log(f'=== EXIT {time.strftime("%H:%M:%S")} ===')
        try:
            if self._gp:
                self._gp.ungrab()
        except Exception:
            pass
        try:
            self._pwr.restore()
        except Exception:
            pass
        sdl2.SDL_Quit()


if __name__ == '__main__':
    VcApp().run()
