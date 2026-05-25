"""Auto-sniper salle des ventes - Forza Horizon 6 (detection par POPUP).

Idee : on ne detecte plus la voiture dans la liste (le menu est blanc -> faux
positifs). A la place :

  CYCLE en boucle : Echap -> Entree -> Entree -> Y
    - Y ouvre "Options des encheres" SI une voiture est selectionnee.
    - pas de voiture -> Y n'ouvre rien -> le cycle recommence.
  Apres le Y, on regarde le CENTRE de l'ecran :
    - une fenetre BLANCHE s'est ouverte -> voiture ! -> Fleche bas -> Entree
    - rien -> on reboucle.

Le fond d'ecran de FH6 est anime (du blanc qui bouge), donc on calibre en
mesurant le MAX du fond pendant ~2s : seule la vraie fenetre (plus claire et
uniforme) depasse le seuil.

>>> COMMENCE EN MODE TEST (n'achete pas). F10 pour activer l'achat reel. <<<

Touches :
  F7  -> coin HAUT-GAUCHE de la zone = LE CENTRE, la ou s'ouvre la fenetre blanche
  F8  -> coin BAS-DROITE de la zone
  F9  -> calibre le FOND (~2s) : laisse l'ecran NORMAL, sans fenetre ouverte
  F11 -> lit la luminosite actuelle de la zone
  F6  -> demarre / arrete
  F10 -> bascule MODE TEST <-> ACHAT REEL
  F1 / F2 -> cycle plus RAPIDE / plus LENT
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

# ===== REGLAGES (modifiables en direct : F1-F4) ============================
CYCLE_KEYS = ["esc", "enter", "enter", "y"]   # le cycle complet
CYCLE_KEY_DELAY = 0.12        # pause entre chaque touche du cycle
POPUP_WAIT = 0.18             # apres le Y, laisser la fenetre s'ouvrir

BUY_KEYS = ["down", "enter"]  # fenetre ouverte -> descendre -> acheter immediat
BUY_KEY_DELAY = 0.08

POPUP_DELTA = 45              # marge de luminosite au-dessus du fond = fenetre
COOLDOWN_AFTER_BUY = 1.5
CALIB_SECONDS = 2.0           # duree de mesure du fond a la calibration (F9)

CYCLE_STEP = 0.03
BUY_STEP = 0.02
MIN_DELAY = 0.02
# ===========================================================================

mouse_ctrl = mouse.Controller()
kb = keyboard.Controller()

region: dict | None = None
_corner_tl: tuple[int, int] | None = None
_corner_br: tuple[int, int] | None = None
baseline: float | None = None   # luminosite MAX du fond (sans fenetre)
running = False
test_mode = True

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
    print(f"[VITESSE] cycle entre-touches={CYCLE_KEY_DELAY:.2f}s "
          f"attente-fenetre={POPUP_WAIT:.2f}s | achat entre-touches={BUY_KEY_DELAY:.2f}s")


def _sample(sct) -> float | None:
    try:
        img = np.asarray(sct.grab(region))
        return float(img[:, :, :3].mean())
    except Exception as exc:
        print("[WATCH] capture impossible:", exc)
        return None


def do_buy() -> None:
    print("[BUY] fenetre ouverte -> bas / Entree (achat immediat)")
    for key_str in BUY_KEYS:
        tap(key_str)
        time.sleep(BUY_KEY_DELAY)
    time.sleep(COOLDOWN_AFTER_BUY)


def worker() -> None:
    with mss() as sct:
        while True:
            if not running or region is None or baseline is None:
                time.sleep(0.1)
                continue

            # 1) cycle : Echap -> Entree -> Entree -> Y
            for key_str in CYCLE_KEYS:
                if not running:
                    break
                tap(key_str)
                time.sleep(CYCLE_KEY_DELAY)
            if not running:
                continue

            # 2) laisser la fenetre s'ouvrir, puis regarder le centre
            time.sleep(POPUP_WAIT)
            b = _sample(sct)
            if b is None:
                time.sleep(0.3)
                continue

            trigger = baseline + POPUP_DELTA
            popup = b >= trigger

            if test_mode:
                print(f"[TEST] centre lum={b:.1f} (seuil={trigger:.1f}) -> "
                      + ("FENETRE = VOITURE" if popup else "rien"))

            if popup:
                if test_mode:
                    print("   >>> fenetre detectee : ACHAT SIMULE (F10 pour activer)")
                else:
                    do_buy()


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


def read_brightness() -> float | None:
    if region is None:
        return None
    with mss() as sct:
        return _sample(sct)


def calibrate_background() -> None:
    """Mesure le fond pendant CALIB_SECONDS et retient son MAX."""
    global baseline
    if region is None:
        print("[CALIB] definis d'abord la zone (F7 puis F8).")
        return
    vals = []
    end = time.time() + CALIB_SECONDS
    with mss() as sct:
        while time.time() < end:
            v = _sample(sct)
            if v is not None:
                vals.append(v)
            time.sleep(0.03)
    if not vals:
        print("[CALIB] echec.")
        return
    baseline = max(vals)
    print(f"[CALIB] fond: min={min(vals):.1f} moy={sum(vals)/len(vals):.1f} "
          f"MAX={baseline:.1f} -> seuil fenetre = {baseline + POPUP_DELTA:.1f}")


def on_press(key) -> bool | None:
    global _corner_tl, _corner_br, running, test_mode
    global CYCLE_KEY_DELAY, POPUP_WAIT, BUY_KEY_DELAY

    if key == keyboard.Key.f7:
        _corner_tl = tuple(int(v) for v in mouse_ctrl.position)
        print(f"[ZONE] coin haut-gauche = {_corner_tl}")
        _update_region()
    elif key == keyboard.Key.f8:
        _corner_br = tuple(int(v) for v in mouse_ctrl.position)
        print(f"[ZONE] coin bas-droite = {_corner_br}")
        _update_region()
    elif key == keyboard.Key.f9:
        calibrate_background()
    elif key == keyboard.Key.f11:
        b = read_brightness()
        print(f"[LECTURE] luminosite zone = {b:.1f}" if b is not None
              else "[LECTURE] zone non definie.")
    elif key == keyboard.Key.f10:
        test_mode = not test_mode
        print(f"[MODE] {'TEST (n achete pas)' if test_mode else 'ACHAT REEL ACTIF'}")
    elif key == keyboard.Key.f1:
        CYCLE_KEY_DELAY = max(MIN_DELAY, CYCLE_KEY_DELAY - CYCLE_STEP)
        POPUP_WAIT = max(MIN_DELAY, POPUP_WAIT - CYCLE_STEP)
        print_speeds()
    elif key == keyboard.Key.f2:
        CYCLE_KEY_DELAY += CYCLE_STEP
        POPUP_WAIT += CYCLE_STEP
        print_speeds()
    elif key == keyboard.Key.f3:
        BUY_KEY_DELAY = max(MIN_DELAY, BUY_KEY_DELAY - BUY_STEP)
        print_speeds()
    elif key == keyboard.Key.f4:
        BUY_KEY_DELAY += BUY_STEP
        print_speeds()
    elif key == keyboard.Key.f6:
        if region is None or baseline is None:
            print("[!] Configure d'abord : zone (F7/F8) + calibration fond (F9).")
        else:
            running = not running
            print(f"[SNIPER] {'ON ▶' if running else 'OFF ⏸'}  "
                  f"(mode {'TEST' if test_mode else 'ACHAT REEL'})")
    elif key == keyboard.Key.f12:
        print("Arret.")
        return False
    return None


def main() -> None:
    print(__doc__)
    print(f"Cycle : {CYCLE_KEYS}  |  Achat apres fenetre : {BUY_KEYS}")
    print_speeds()
    print("\n>>> MODE TEST ACTIF (n'achete pas). Verifie d'abord, puis F10.\n"
          "Zone = LE CENTRE (fenetre blanche). Etapes : F7 -> F8 -> F9 (fond) -> F6.\n")
    threading.Thread(target=worker, daemon=True).start()
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
