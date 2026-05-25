"""Auto-sniper salle des ventes - Forza Horizon 6.

Principe (mode SURVEILLANCE SEULE par defaut, ne touche a aucun menu) :
  - regarde la carte en haut a gauche de la salle des ventes :
       sombre/grise -> "AUCUNE ENCHERE" ; blanche -> une voiture est la !
  - des qu'une voiture apparait (front vide -> blanc) :
       achat immediat : Y (options) -> Fleche bas (Acheter immediat) -> Entree
  - se re-arme quand la carte redevient vide.
Le rafraichissement automatique de la liste est DESACTIVE par defaut
(REFRESH_KEYS = []) pour ne pas te faire sortir de la salle.

Touches de configuration :
  F7  -> coin HAUT-GAUCHE de la zone a surveiller (a la position du curseur)
  F8  -> coin BAS-DROITE de la zone
  F9  -> calibre la luminosite "liste vide" (sur l'ecran AUCUNE ENCHERE)
  F11 -> lit la luminosite actuelle (pour comparer vide vs voiture)
  F6  -> demarre / arrete le sniper
  F12 -> quitter

Conseil zone : encadre la CARTE DU HAUT de la liste de gauche (la 1re voiture).
Vide = fond sombre ; voiture = grand rectangle blanc -> gros ecart de luminosite.

PC uniquement, jeu en mode fenetre / fenetre sans bordure, terminal en admin.
"""
from __future__ import annotations

import threading
import time

import numpy as np
from mss import mss
from pynput import keyboard, mouse

# ===== REGLAGES (ajuste si besoin) =========================================
# Touches de rafraichissement de la liste.
#   []  = MODE SURVEILLANCE SEULE (recommande au depart) : le bot ne touche a
#         AUCUN menu, il reste dans la salle et achete uniquement quand une
#         voiture apparait. Il ne peut donc pas te sortir vers la map.
#   ex: ["esc", "enter"] = essaie de rafraichir (a n'utiliser que si tu m'as
#         donne la bonne sequence pour relancer la liste sans quitter la salle).
REFRESH_KEYS: list[str] = []
REFRESH_KEY_DELAY = 0.18      # pause entre les touches de rafraichissement
LOAD_SETTLE = 0.45            # temps de chargement de la liste avant de regarder
WATCH_INTERVAL = 0.05         # frequence de verification en mode surveillance

# Sequence d'achat quand une voiture est detectee :
#   Y -> ouvre "Options des encheres" (curseur sur "Encherir")
#   down -> descend sur "Acheter immediatement"
#   enter -> valide
# Si une confirmation supplementaire apparait, ajoute un "enter" a la fin.
BUY_KEYS = ["y", "down", "enter"]
BUY_KEY_DELAY = 0.15          # pause entre chaque touche d'achat
MENU_OPEN_WAIT = 0.20         # pause apres le Y, le temps que le menu s'ouvre

# Detection :
TRIGGER_DELTA = 60            # hausse de luminosite (0-255) = carte blanche = voiture
COOLDOWN_AFTER_BUY = 1.5      # pause apres une tentative d'achat
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
    time.sleep(0.03)
    kb.release(k)


def read_brightness() -> float | None:
    if region is None:
        return None
    with mss() as sct:
        img = np.asarray(sct.grab(region))     # H x W x 4 (BGRA)
        return float(img[:, :, :3].mean())


def do_buy() -> None:
    print("[BUY] voiture detectee -> Y / bas / Entree")
    for i, key_str in enumerate(BUY_KEYS):
        tap(key_str)
        # apres le tout premier Y, laisser le menu s'ouvrir
        time.sleep(MENU_OPEN_WAIT if i == 0 else BUY_KEY_DELAY)
    time.sleep(COOLDOWN_AFTER_BUY)


def worker() -> None:
    armed = True  # ne tire que sur le front "vide -> voiture", puis se re-arme
    with mss() as sct:
        while True:
            if not running or region is None or baseline is None:
                armed = True
                time.sleep(0.1)
                continue

            # 1) rafraichir la liste (uniquement si des touches sont definies)
            if REFRESH_KEYS:
                for key_str in REFRESH_KEYS:
                    if not running:
                        break
                    tap(key_str)
                    time.sleep(REFRESH_KEY_DELAY)
                if not running:
                    continue
                time.sleep(LOAD_SETTLE)

            # 2) regarder la carte du haut
            try:
                img = np.asarray(sct.grab(region))
                b = float(img[:, :, :3].mean())
            except Exception as exc:
                print("[WATCH] capture impossible:", exc)
                time.sleep(0.5)
                continue

            # 3) front vide -> voiture : on achete ; on se re-arme quand ca redevient vide
            trigger = baseline + TRIGGER_DELTA
            rearm = baseline + TRIGGER_DELTA * 0.5
            if armed and b >= trigger:
                print(f"[DETECT] luminosite={b:.1f} (vide={baseline:.1f}) -> ACHAT")
                armed = False
                do_buy()
            elif not armed and b <= rearm:
                armed = True

            if not REFRESH_KEYS:
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
    print(f"Rafraichissement : {REFRESH_KEYS}  |  Achat : {BUY_KEYS}")
    print("Etapes : F7 (haut-gauche carte) -> F8 (bas-droite carte) -> "
          "F9 (calibrer ecran vide) -> F6 (lancer). F12 pour quitter.\n")
    threading.Thread(target=worker, daemon=True).start()
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
