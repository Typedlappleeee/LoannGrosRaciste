"""Auto-sniper salle des ventes - Forza Horizon 6.

A lancer depuis l'ecran de resultats vide "AUCUNE ENCHERE A AFFICHER".

Boucle (la liste ne se rafraichit jamais seule) :
  1. Echap -> Entree -> Entree  (revient au menu recherche puis re-confirme)
  2. courte attente de chargement
  3. analyse la carte en haut a gauche :
       sombre/grise -> rien -> on reboucle
       blanche      -> une voiture ! -> Y -> Fleche bas -> Entree (achat immediat)
  4. on recommence a l'infini.

Touches :
  F7  -> coin HAUT-GAUCHE de la zone a surveiller (1re carte de la liste)
  F8  -> coin BAS-DROITE de la zone
  F9  -> calibre la luminosite "vide" (sur l'ecran AUCUNE ENCHERE)
  F11 -> lit la luminosite actuelle (comparer vide vs voiture)
  F6  -> demarre / arrete le sniper
  F1 / F2 -> refresh plus RAPIDE / plus LENT
  F3 / F4 -> achat plus RAPIDE / plus LENT
  F12 -> quitter

PC uniquement, jeu en fenetre / fenetre sans bordure, terminal en admin.
"""
from __future__ import annotations

import threading
import time

import numpy as np
from mss import mss
from pynput import keyboard, mouse

# ===== REGLAGES (modifiables aussi en direct avec F1-F4) ===================
REFRESH_KEYS = ["esc", "enter", "enter"]   # Echap -> Entree -> Entree
REFRESH_KEY_DELAY = 0.12      # pause entre chaque touche du refresh
LOAD_SETTLE = 0.25            # attente apres le refresh avant d'analyser

BUY_KEYS = ["y", "down", "enter"]          # options -> bas -> acheter immediat
MENU_OPEN_WAIT = 0.12         # apres le Y, le temps que le menu s'ouvre
BUY_KEY_DELAY = 0.06          # pause entre les touches d'achat

TRIGGER_DELTA = 60            # hausse de luminosite = carte blanche = voiture
COOLDOWN_AFTER_BUY = 1.2      # pause apres une tentative d'achat
WATCH_INTERVAL = 0.05         # (mode surveillance seule : REFRESH_KEYS = [])

# pas de reglage des touches F1-F4
REFRESH_STEP = 0.03
BUY_STEP = 0.02
MIN_DELAY = 0.02
# ===========================================================================

mouse_ctrl = mouse.Controller()
kb = keyboard.Controller()

region: dict | None = None
_corner_tl: tuple[int, int] | None = None
_corner_br: tuple[int, int] | None = None
baseline: float | None = None
running = False

SPECIAL = {
    "enter": keyboard.Key.enter, "esc": keyboard.Key.esc, "escape": keyboard.Key.esc,
    "space": keyboard.Key.space, "tab": keyboard.Key.tab,
    "up": keyboard.Key.up, "down": keyboard.Key.down,
    "left": keyboard.Key.left, "right": keyboard.Key.right,
}


def to_key(s: str):
    return SPECIAL.get(s.lower(), s)


def tap(key_str: str) -> None:
    k = to_key(key_str)
    kb.press(k)
    time.sleep(0.02)
    kb.release(k)


def print_speeds() -> None:
    print(f"[VITESSE] refresh: entre-touches={REFRESH_KEY_DELAY:.2f}s "
          f"chargement={LOAD_SETTLE:.2f}s | achat: ouverture={MENU_OPEN_WAIT:.2f}s "
          f"entre-touches={BUY_KEY_DELAY:.2f}s")


def _sample(sct) -> float | None:
    try:
        img = np.asarray(sct.grab(region))
        return float(img[:, :, :3].mean())
    except Exception as exc:
        print("[WATCH] capture impossible:", exc)
        return None


def do_buy() -> None:
    print("[BUY] voiture detectee -> Y / bas / Entree")
    for i, key_str in enumerate(BUY_KEYS):
        tap(key_str)
        time.sleep(MENU_OPEN_WAIT if i == 0 else BUY_KEY_DELAY)
    time.sleep(COOLDOWN_AFTER_BUY)


def worker() -> None:
    armed = True
    with mss() as sct:
        while True:
            if not running or region is None or baseline is None:
                armed = True
                time.sleep(0.1)
                continue

            trigger = baseline + TRIGGER_DELTA

            if REFRESH_KEYS:
                # --- refresh: Echap -> Entree -> Entree, puis analyse ---
                for key_str in REFRESH_KEYS:
                    if not running:
                        break
                    tap(key_str)
                    time.sleep(REFRESH_KEY_DELAY)
                if not running:
                    continue
                time.sleep(LOAD_SETTLE)
                b = _sample(sct)
                if b is None:
                    time.sleep(0.3)
                    continue
                if b >= trigger:
                    print(f"[DETECT] luminosite={b:.1f} (vide={baseline:.1f}) -> ACHAT")
                    do_buy()
            else:
                # --- surveillance seule : front vide -> voiture ---
                b = _sample(sct)
                if b is None:
                    time.sleep(0.3)
                    continue
                rearm = baseline + TRIGGER_DELTA * 0.5
                if armed and b >= trigger:
                    print(f"[DETECT] luminosite={b:.1f} -> ACHAT")
                    armed = False
                    do_buy()
                elif not armed and b <= rearm:
                    armed = True
                time.sleep(WATCH_INTERVAL)


def _update_region() -> None:
    global region
    if _corner_tl and _corner_br:
        left = min(_corner_tl[0], _corner_br[0])
        top = min(_corner_tl[1], _corner_br[1])
        width = abs(_corner_br[0] - _corner_tl[0])
        height = abs(_corner_br[1] - _corner_tl[1])
        if width > 0 and height > 0:
            region = {"left": left, "top": top, "width": width, "height": height}
            print(f"[ZONE] {region}")


def on_press(key) -> bool | None:
    global _corner_tl, _corner_br, baseline, running
    global REFRESH_KEY_DELAY, LOAD_SETTLE, MENU_OPEN_WAIT, BUY_KEY_DELAY

    if key == keyboard.Key.f7:
        _corner_tl = tuple(int(v) for v in mouse_ctrl.position)
        print(f"[ZONE] coin haut-gauche = {_corner_tl}")
        _update_region()
    elif key == keyboard.Key.f8:
        _corner_br = tuple(int(v) for v in mouse_ctrl.position)
        print(f"[ZONE] coin bas-droite = {_corner_br}")
        _update_region()
    elif key == keyboard.Key.f9:
        b = read_brightness()
        if b is None:
            print("[CALIB] definis d'abord la zone (F7 puis F8).")
        else:
            baseline = b
            print(f"[CALIB] luminosite vide = {baseline:.1f} "
                  f"(seuil achat = {baseline + TRIGGER_DELTA:.1f})")
    elif key == keyboard.Key.f11:
        b = read_brightness()
        print(f"[LECTURE] luminosite zone = {b:.1f}" if b is not None
              else "[LECTURE] zone non definie.")
    elif key == keyboard.Key.f1:        # refresh plus rapide
        REFRESH_KEY_DELAY = max(MIN_DELAY, REFRESH_KEY_DELAY - REFRESH_STEP)
        LOAD_SETTLE = max(MIN_DELAY, LOAD_SETTLE - REFRESH_STEP)
        print_speeds()
    elif key == keyboard.Key.f2:        # refresh plus lent
        REFRESH_KEY_DELAY += REFRESH_STEP
        LOAD_SETTLE += REFRESH_STEP
        print_speeds()
    elif key == keyboard.Key.f3:        # achat plus rapide
        MENU_OPEN_WAIT = max(MIN_DELAY, MENU_OPEN_WAIT - BUY_STEP)
        BUY_KEY_DELAY = max(MIN_DELAY, BUY_KEY_DELAY - BUY_STEP)
        print_speeds()
    elif key == keyboard.Key.f4:        # achat plus lent
        MENU_OPEN_WAIT += BUY_STEP
        BUY_KEY_DELAY += BUY_STEP
        print_speeds()
    elif key == keyboard.Key.f6:
        if region is None or baseline is None:
            print("[!] Configure d'abord : zone (F7/F8) + calibration (F9).")
        else:
            running = not running
            print(f"[SNIPER] {'ON ▶' if running else 'OFF ⏸'}")
    elif key == keyboard.Key.f12:
        print("Arret.")
        return False
    return None


def read_brightness() -> float | None:
    if region is None:
        return None
    with mss() as sct:
        return _sample(sct)


def main() -> None:
    print(__doc__)
    print(f"Refresh : {REFRESH_KEYS}  |  Achat : {BUY_KEYS}")
    print_speeds()
    print("\nLance-toi depuis l'ecran 'AUCUNE ENCHERE'. Etapes : F7 (haut-gauche "
          "carte) -> F8 (bas-droite) -> F9 (sur ecran vide) -> F6. "
          "F1/F2 vitesse refresh, F3/F4 vitesse achat, F12 quitter.\n")
    threading.Thread(target=worker, daemon=True).start()
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
