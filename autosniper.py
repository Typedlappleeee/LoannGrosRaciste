"""Macro salle des ventes - Forza Horizon 6 (boucle aveugle, scancode materiel).

Repete en boucle, dans cet ordre exact :
    Echap -> Entree -> Entree -> Y -> Fleche bas -> Entree
  puis recommence (Echap -> ...).

Les touches sont envoyees en SCANCODE MATERIEL (via SendInput), car FH6 ignore
les touches "virtuelles" classiques (c'est pour ca que les Entree ne passaient
pas alors qu'Echap/fleches passaient).

A lancer depuis l'ecran de resultats "AUCUNE ENCHERE A AFFICHER".

Touches :
  F6  -> demarre / arrete la boucle
  F1  -> plus RAPIDE   F2 -> plus LENT      (delai entre touches)
  F3  -> appui plus court   F4 -> appui plus long
  F12 -> quitter

WINDOWS uniquement, jeu en fenetre / fenetre sans bordure, terminal en admin.
"""
from __future__ import annotations

import ctypes
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

# --- envoi de touches en scancode materiel (SendInput) ---------------------
# scancodes "Set 1" (make codes) ; True = touche etendue (fleches)
SCANCODES = {
    "esc": (0x01, False),
    "enter": (0x1C, False),
    "y": (0x15, False),
    "down": (0x50, True),
    "up": (0x48, True),
    "left": (0x4B, True),
    "right": (0x4D, True),
    "space": (0x39, False),
    "tab": (0x0F, False),
}

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_KEYBOARD = 1

_PUL = ctypes.POINTER(ctypes.c_ulong)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", _PUL),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("u", _INPUTUNION)]


try:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)   # type: ignore[attr-defined]
    _SendInput = _user32.SendInput
    _SendInput.argtypes = (ctypes.c_uint, ctypes.POINTER(_INPUT), ctypes.c_int)
    _SendInput.restype = ctypes.c_uint
except (AttributeError, OSError):
    _SendInput = None  # pas sous Windows

_send_failed = False


def _send(scan: int, extended: bool, keyup: bool) -> None:
    global _send_failed
    if _SendInput is None:
        return
    flags = KEYEVENTF_SCANCODE
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    if keyup:
        flags |= KEYEVENTF_KEYUP
    ki = _KEYBDINPUT(0, scan, flags, 0, None)
    inp = _INPUT(INPUT_KEYBOARD, _INPUTUNION(ki))
    n = _SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))
    if n != 1 and not _send_failed:
        _send_failed = True
        print(f"[!] SendInput a echoue (n={n}, err={ctypes.get_last_error()}). "
              "Lance PowerShell en tant qu'ADMINISTRATEUR et reessaie.")


def tap(key_str: str) -> None:
    sc = SCANCODES.get(key_str.lower())
    if sc is None:
        return
    scan, ext = sc
    _send(scan, ext, False)
    time.sleep(KEY_HOLD)
    _send(scan, ext, True)


# ---------------------------------------------------------------------------
running = False


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
    if _SendInput is None:
        print("\n[!] SendInput indisponible (pas sous Windows ?) - les touches "
              "ne seront pas envoyees.")
    print("\nLance depuis l'ecran 'AUCUNE ENCHERE'. F6 demarrer/arreter, "
          "F1/F2 vitesse, F3/F4 duree d'appui, F12 quitter.\n")
    threading.Thread(target=worker, daemon=True).start()
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


if __name__ == "__main__":
    main()
