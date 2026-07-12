# AnberVc — mapowanie przycisków

Kody evdev **REALNE** dla egzemplarza Karola (RG40XX V), zweryfikowane
**empirycznie**: logi faktycznie emitowanych kodów (`/mnt/data/anberwm.log`,
`/mnt/data/anberpkm.log`) + działający handler AnberWM. Pad czytany z
`/dev/input/event1`, POWER z `/dev/input/event0`.

A=304 · B=305 · X=307 · Y=308 · **L1=309** · **R1=312** · **L2=314** ·
**R2=315** · MODE=316 · MENU=354 · POWER=116 (`event0`) ·
D-pad = EV_ABS 16 (←→) / 17 (↑↓).

> **UWAGA — pułapka kodów barków.** „Kanoniczna” mapa (L1=310, R1=311, L2=312,
> R2=313) **NIE obowiązuje na tym urządzeniu**: kody 310/311/313 nie są w ogóle
> emitowane. Dlatego wcześniejsze `BTN_R2=313` było **martwe** — R2 nie generował
> PDF-a. Zbiór realnie emitowanych kodów barków tego egzemplarza = {309, 312,
> 314, 315}; **L2=314** i **R2=315** potwierdzone działaniem. **L1=309,
> R1=312** — user potwierdził 2026-07-12, że fizyczny L1 NIE emituje 312, więc
> przez ELIMINACJĘ (312≠L1, a jest w zbiorze) 312=R1 i 309=L1 (wcześniejsza
> hipoteza L1=312/R1=309 była ODWROTNA). **POTWIERDZIĆ pomiarem** (log evdev)
> gdy konsola stabilna. Ze starych apek (AnberPKM/AnberWM) kopiuj **tylko
> kody**, nie logikę wartości.

> **NIE** `SDL_INIT_JOYSTICK` — grabuje event1 i zabiera pad aplikacji.
> `PYSDL2_DLL_PATH=/usr/lib` ustawia launcher `AnberVc.sh`.

| Przycisk (kod)              | Akcja                                              |
|-----------------------------|----------------------------------------------------|
| D-pad ↑/↓ (ABS 17)          | wybór parametru (nawigacja pól)                    |
| D-pad ←/→ (ABS 16)          | − / + **wartość** pola o bieżący rozmiar kroku     |
| **L1 (309)**                | rozmiar kroku **−** (mniejszy)                     |
| **L2 (314)**                | rozmiar kroku **+** (większy)                      |
| **A (304)**                 | reset zaznaczonego pola do wartości presetu        |
| **X (307)**                 | reset WSZYSTKICH pól do presetu                    |
| **R2 (315)**                | generuj raport **PDF** do druku (A4)              |
| **MENU (354) / MODE (316)** | wyjście z aplikacji                                |
| **POWER (116)**             | ekran off/on (apka działa dalej)                   |

R1 (312) jest wolne (bez akcji). Pola idx (Preset, Jednostka v_c) zmieniają się
←/→ z zawijaniem; zmiana **Presetu** przeładowuje pozostałe parametry. „Liczba
nastawień” zmienia się o ±1. Wynik przelicza się automatycznie po każdej zmianie.

## Zasada odporności (klasa błędu „wartości mrugają”)

**Wartość pola zmienia się WYŁĄCZNIE na jawną regulację usera** — D-pad ←/→
(`_adjust`) albo A/X (reset do presetu). Nawigacja pól (D-pad ↑/↓), zmiana kroku
(L1/L2), R2/PDF, wyjście (MENU/MODE), start oraz zapis/wczytanie configu **NIGDY
nie ruszają `self.vals`**. Wyjście (MENU/MODE) jest sprawdzane **przed** dowolną
gałęzią regulacji — cała partia zdarzeń z przyciskiem wyjścia kończy się czystym
`return`, więc przycisk nie może „musnąć” wartości/pola/kroku.
