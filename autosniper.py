"""Auto-sniper salle des encheres.

Boucle Entree -> Echap -> Entree -> Echap pour rafraichir le panneau, surveille
une zone d'ecran (le panneau gauche), et des qu'une voiture apparait
(panneau grise -> blanc, hausse de luminosite), declenche le bind d'achat
immediat. Se re-arme quand le panneau redevient grise.

Touches :
  F7  -> enregistre le coin HAUT-GAUCHE de la zone (a la position du curseur)
  F8  -> enregistre le coin BAS-DROITE de la zone
  F9  -> calibre la luminosite "panneau vide" (mets le curseur ailleurs, zone vide)
  F6  -> demarre / arrete le sniper
  F11 -> affiche en continu la luminosite de la zone (pour calibrer le seuil)
  F12 -> quitter

PC uniquement, jeu en mode fenetre / fenetre sans bordure, terminal en admin.
"""
from __future__ import annotations

import threading
import time

import numpy as np
from mss import mss
from pynput import keyboard, mouse

# ===== REGLAGES ============================================================
# Sequence de rafraichissement envoyee en boucle :
CYCLE_KEYS = ["enter", "esc"]      # -> entree, echap, entree, echap, ...
CYCLE_DELAY = 0.25                 # secondes entre chaque touche

# Touche(s) du bind "achat immediat" a envoyer quand une voiture est detectee :
BUY_KEYS = ["enter"]               # ex: ["e"], ["enter"], ["space"]...
# Optionnel : cliquer a une position au lieu / en plus (None pour desactiver)
BUY_CLICK = None                   # ex: (1280, 720)

# Detection :
TRIGGER_DELTA = 35                 # hausse de luminosite (0-255) = voiture presente
COOLDOWN_AFTER_BUY = 1.0           # pause apres un achat
WATCH_INTERVAL = 0.03              # frequence de capture ecran
# ===========================================================================

mouse_ctrl = mouse.Controller()
kb = keyboard.Controller()

region: dict | None = None          # {"left","top","width","height"} pour mss
_corner_tl: tuple[int, int] | None = None
_corner_br: tuple[int, int] | None = None
baseline: float | None = None       # luminosite "vide"
running = False
show_brightness = False
_buying = False

SPECIAL = {
    "enter": keyboard.Key.enter, "esc": keyboard.Key.esc, "escape": keyboard.Key.esc,
    "space": keyboard.Key.space, "tab": keyboard.Key.tab,
    "up": keyboard.Key.up, "down": keyboard.Key.down,
    "left": keyboard.Key.left, "right": keyboard.Key.right,
    "backspace": keyboard.Key.backspace,
}


def to_key(s: str):
    return SPECIAL.get(s.lower(), s)


def tap(key_str: str) -> None:
    k = to_key(key_str)
    kb.press(k)
    time.sleep(0.03)
    kb.release(k)


def grab_brightness(sct) -> float:
    img = np.asarray(sct.grab(region))      # H x W x 4 (BGRA)
    return float(img[:, :, :3].mean())


def do_buy() -> None:
    global _buying
    _buying = True
    print("[BUY] voiture detectee -> achat immediat !")
    if BUY_CLICK:
        mouse_ctrl.position = BUY_CLICK
        time.sleep(0.02)
        mouse_ctrl.click(mouse.Button.left, 1)
    for key_str in BUY_KEYS:
        tap(key_str)
        time.sleep(0.05)
    time.sleep(COOLDOWN_AFTER_BUY)
    _buying = False


def cycler() -> None:
    """Envoie la sequence Entree/Echap en boucle pour rafraichir le panneau."""
    while True:
        if running and not _buying:
            for key_str in CYCLE_KEYS:
                if not running or _buying:
                    break
                tap(key_str)
                time.sleep(CYCLE_DELAY)
        else:
            time.sleep(0.05)


def watcher() -> None:
    """Surveille la zone et declenche l'achat sur le front grise -> blanc."""
    armed = True
    with mss() as sct:
        while True:
            if not running or region is None or baseline is None:
                time.sleep(0.1)
                continue
            try:
                b = grab_brightness(sct)
            except Exception as exc:
                print("[WATCH] capture impossible:", exc)
                time.sleep(0.5)
                continue

            if show_brightness:
                print(f"[WATCH] luminosite={b:.1f} (vide={baseline:.1f}, "
                      f"seuil={baseline + TRIGGER_DELTA:.1f}) armed={armed}")

            trigger = baseline + TRIGGER_DELTA
            rearm = baseline + TRIGGER_DELTA * 0.5
            if armed and b >= trigger and not _buying:
                armed = False
                do_buy()
            elif not armed and b <= rearm:
                armed = True               # panneau revenu vide -> pret a re-snipe
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
    global _corner_tl, _corner_br, baseline, running, show_brightness
    if key == keyboard.Key.f7:
        _corner_tl = tuple(int(v) for v in mouse_ctrl.position)
        print(f"[ZONE] coin haut-gauche = {_corner_tl}")
        _update_region()
    elif key == keyboard.Key.f8:
        _corner_br = tuple(int(v) for v in mouse_ctrl.position)
        print(f"[ZONE] coin bas-droite = {_corner_br}")
        _update_region()
    elif key == keyboard.Key.f9:
        if region is None:
            print("[CALIB] definis d'abord la zone (F7 puis F8).")
        else:
            with mss() as sct:
                baseline = grab_brightness(sct)
            print(f"[CALIB] luminosite vide = {baseline:.1f}")
    elif key == keyboard.Key.f11:
        show_brightness = not show_brightness
        print(f"[DEBUG] affichage luminosite {'ON' if show_brightness else 'OFF'}")
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


def main() -> None:
    print(__doc__)
    print("Etapes : F7 (coin haut-gauche) -> F8 (coin bas-droite) -> "
          "F9 (calibrer zone vide) -> F6 (lancer). F11 pour calibrer le seuil.\n")
    threading.Thread(target=cycler, daemon=True).start()
    threading.Thread(target=watcher, daemon=True).start()
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
