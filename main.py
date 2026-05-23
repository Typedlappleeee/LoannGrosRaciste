"""Point d'entree : lance l'interface web de l'agent LoanGrosRaciste.

  python main.py
  -> ouvre http://127.0.0.1:8000 dans ton navigateur.
"""
from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"\n  LoanGrosRaciste -> http://{host}:{port}\n")
    uvicorn.run("webapp.server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
