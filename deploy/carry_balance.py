import json
import sys
from pathlib import Path

START = 5.0
CEILING = 1000.0


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("prev")
    for state in sorted(root.rglob("paper_state.json")):
        try:
            value = json.loads(state.read_text(encoding="utf-8")).get("bankroll")
        except (OSError, ValueError):
            continue
        if isinstance(value, (int, float)) and 0 <= value <= CEILING:
            print(f"{float(value):.4f}")
            return 0
    print(f"{START:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
