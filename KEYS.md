# AnberVc — mapowanie przycisków

Kody evdev **REALNE** (egzemplarz Karola, źródło: AnberPKM/AnberWM,
skill `rg40xx-input-mapping`). Pad czytany z `/dev/input/event1`,
POWER z `/dev/input/event0`.

A=304 · B=305 · X=307 · Y=308 · L1=310 · R1=311 · L2=312 · R2=313 ·
MODE=316 · MENU=354 · POWER=116 (`event0`) · D-pad = EV_ABS 16 (←→) / 17 (↑↓).

> **NIE** `SDL_INIT_JOYSTICK` — grabuje event1 i zabiera pad aplikacji.
> `PYSDL2_DLL_PATH=/usr/lib` ustawia launcher `AnberVc.sh`.

| Przycisk (kod)        | Akcja                                             |
|-----------------------|---------------------------------------------------|
| D-pad ↑/↓ (ABS 17)    | wybór parametru                                   |
| D-pad ←/→ (ABS 16)    | − / + wartość o bieżący krok                      |
| **L1 (310) / R1 (311)** | szybki krok − / + (o jeden stopień większy)     |
| **L2 (312) / R2 (313)** | szybki krok − / + (o dwa stopnie większy)       |
| **Y (308)**           | zmiana kroku (0.1 / 1 / 10 / 100 / 1000)          |
| **A (304)**           | reset zaznaczonego pola do wartości presetu       |
| **X (307)**           | reset WSZYSTKICH pól do presetu                    |
| **MENU (354) / MODE (316)** | wyjście z aplikacji                         |
| **POWER (116)**       | ekran off/on (apka działa dalej)                  |

Pola idx (Preset, Jednostka v_c) zmieniają się ←/→ z zawijaniem; zmiana
**Presetu** przeładowuje pozostałe parametry. „Liczba nastawień" zmienia się
o ±1 (bez wpływu kroku). Wynik przelicza się automatycznie po każdej zmianie.
