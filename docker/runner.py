# Required Notice: Copyright (c) 2026 hackall360. All Rights Reserved for Commercial Use.
# https://polyformproject.org/licenses/noncommercial/1.0.0
"""Keep an unhandled Python exception distinct from an explicit blocked result."""

import runpy
import sys
import traceback


def main() -> int:
    try:
        runpy.run_path("/verifier/verify.py", run_name="__main__")
    except SystemExit as exc:
        if type(exc.code) is int and exc.code in (0, 1, 2):
            return exc.code
        print("Verifier must explicitly exit with integer 0, 1, or 2.", file=sys.stderr)
        return 2
    except BaseException:
        traceback.print_exc(limit=3)
        return 2
    print(
        "Verifier returned without an explicit sys.exit(0|1|2) call; treating as inconclusive.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
