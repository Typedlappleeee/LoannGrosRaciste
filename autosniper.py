"""Macro salle des ventes - Forza Horizon 6 (boucle aveugle, sans detection).

Repete en boucle, le plus vite que le jeu suit :
    Echap -> Entree -> Entree -> Y -> Fleche bas -> Entree
  (Echap/Entree/Entree relancent la recherche ; Y ouvre les options de la
   voiture selectionnee ; bas + Entree = Acheter immediat. S'il n'y a pas de
   voiture, ces touches ne font rien de grave.)

A lancer depuis l'ecran de resultats "AUCUNE ENCHERE A AFFICHER".

Touches :
  F6  -> demarre / arrete la boucle
  F1  -> plus RAPIDE   (reduit le delai entre touches)
  F2  -> plus LENT     (augmente le delai)
  F3  -> appui plus court   F4 -> appui plus long  (si des touches sont ignorees)
  F12 -> quitter

PC uniquement, jeu en fenetre / fenetre sans bordure, terminal en admin.
Si les ENTREE sont ignorees meme en ralentissant : dis-le-moi, on passera a un
envoi des touches en scancode materiel.
"""
from __future__ import annotations

import threading
import time

from pynput import keyboard

# ===== REGLAGES (modifiables en direct : F1-F4) ============================
CYCLE_KEYS = ["esc", "enter", "enter", "y", "down", "enter"]
CYCLE_KEY_DELAY = 0.18        # pause entre chaque touche
KEY_HOLD = 0.05               # duree d'appui de chaque touche
LOOP_PAUSE = 0.05             # petite pause en fin de cycle

STEP = 0.02
MIN_DELAY = 0.01
# ===========================================================================

kb = keyboard.Controller()
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
    time.sleep(KEY_HOLD)
    kb.release(k)


def print_speeds() -> None:
    print(f"[VITESSE] delai entre touches={CYCLE_KEY_DELAY:.2f}s | "
          f"appui={KEY_HOLD:.2f}s")


def worker() -> None:
    while True:
        if not running:
            time.sleep(0.05)
            continue
        for key_str in CYCLE_KEYS:
            if not running:
                break
            tap(key_str)
            time.sleep(CYCLE_KEY_DELAY)
        time.sleep(LOOP_PAUSE)


def on_press(key) -> bool | None:
    global running, CYCLE_KEY_DELAY, KEY_HOLD
    if key == keyboard.Key.f6:
        running = not running
        print(f"[MACRO] {'ON ▶' if running else 'OFF ⏸'}")
    elif key == keyboard.Key.f1:
        CYCLE_KEY_DELAY = max(MIN_DELAY, CYCLE_KEY_DELAY - STEP)
        print_speeds()
    elif key == keyboard.Key.f2:
        CYCLE_KEY_DELAY += STEP
        print_speeds()
    elif key == keyboard.Key.f3:
        KEY_HOLD = max(MIN_DELAY, KEY_HOLD - STEP)
        print_speeds()
    elif key == keyboard.Key.f4:
        KEY_HOLD += STEP
        print_speeds()
    elif key == keyboard.Key.f12:
        print("Arret.")
        return False
    return None


def main() -> None:
    print(__doc__)
    print(f"Cycle : {CYCLE_KEYS}")
    print_speeds()
    print("\nLance depuis l'ecran 'AUCUNE ENCHERE'. F6 pour demarrer/arreter, "
          "F1/F2 vitesse, F3/F4 duree d'appui, F12 quitter.\n")
    threading.Thread(target=worker, daemon=True).start()
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
