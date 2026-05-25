"""Autoclicker configurable — utile pour spammer un bouton (ex: "Achat immediat"
dans une salle des encheres) ou rejouer une sequence de clics
(ex: Rechercher -> Achat immediat -> Confirmer).

Touches :
  F6  -> active / desactive le clic auto
  F7  -> enregistre la position actuelle du curseur comme point de clic
  F8  -> efface les points enregistres
  ESC -> quitter

Modes :
  - Aucun point enregistre : clique en boucle a la position courante du curseur.
  - 1 point ou plus        : deplace + clique sur chaque point dans l'ordre,
                             en boucle (ideal pour une sequence d'enchere).

PC uniquement. A utiliser en connaissance des regles du jeu (risque de ban).
"""
from __future__ import annotations

import threading
import time

from pynput import keyboard, mouse

# ----- reglages (ajuste selon ton besoin) ----------------------------------
CLICK_INTERVAL = 0.05   # secondes entre deux clics / etapes
MOVE_SETTLE = 0.02      # petite pause apres deplacement avant de cliquer
SEQUENCE_PAUSE = 0.30   # pause apres une boucle complete de la sequence
# ---------------------------------------------------------------------------

mouse_ctrl = mouse.Controller()
points: list[tuple[int, int]] = []
running = False


def worker() -> None:
    while True:
        if not running:
            time.sleep(0.05)
            continue

        pts = list(points)
        if not pts:
            # pas de point : on clique la ou se trouve le curseur
            mouse_ctrl.click(mouse.Button.left, 1)
            time.sleep(CLICK_INTERVAL)
            continue

        for (x, y) in pts:
            if not running:
                break
            mouse_ctrl.position = (x, y)
            time.sleep(MOVE_SETTLE)
            mouse_ctrl.click(mouse.Button.left, 1)
            time.sleep(CLICK_INTERVAL)
        time.sleep(SEQUENCE_PAUSE)


def on_press(key) -> bool | None:
    global running
    if key == keyboard.Key.f6:
        running = not running
        print(f"[AUTO-CLICK] {'ON ▶' if running else 'OFF ⏸'}"
              + (f"  ({len(points)} point(s))" if points else "  (curseur)"))
    elif key == keyboard.Key.f7:
        x, y = mouse_ctrl.position
        points.append((int(x), int(y)))
        print(f"[REC] point #{len(points)} = ({int(x)}, {int(y)})")
    elif key == keyboard.Key.f8:
        points.clear()
        print("[CLEAR] points effaces.")
    elif key == keyboard.Key.esc:
        print("Arret.")
        return False
    return None


def main() -> None:
    print(__doc__)
    print(f"Intervalle de clic : {CLICK_INTERVAL}s — modifiable en haut du script.\n"
          "Place le curseur sur le bouton et appuie F7 pour l'enregistrer,\n"
          "puis F6 pour lancer le spam. ESC pour quitter.\n")
    threading.Thread(target=worker, daemon=True).start()
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
