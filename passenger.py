#!/usr/bin/env python3
"""passgen — a simple, cryptographically secure password generator."""

import argparse
import secrets
import string
import sys

AMBIGUOUS = set("Il1O0o")

CHARSETS = {
    "lower": string.ascii_lowercase,
    "upper": string.ascii_uppercase,
    "digits": string.digits,
    "symbols": "!@#$%^&*()-_=+[]{};:,.<>?/",
}


def build_alphabet(no_ambiguous: bool) -> dict[str, str]:
    if not no_ambiguous:
        return CHARSETS
    return {
        name: "".join(c for c in chars if c not in AMBIGUOUS)
        for name, chars in CHARSETS.items()
    }


def generate(length: int, use: list[str], no_ambiguous: bool) -> str:
    alphabet = build_alphabet(no_ambiguous)
    pools = [alphabet[name] for name in use]
    all_chars = "".join(pools)

    if length < len(pools):
        raise ValueError(
            f"Length {length} is too short for {len(pools)} character sets."
        )

    # Guarantee at least one char from each selected set
    password = [secrets.choice(pool) for pool in pools]
    password += [secrets.choice(all_chars) for _ in range(length - len(pools))]

    # Fisher-Yates shuffle using secrets
    for i in range(len(password) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        password[i], password[j] = password[j], password[i]

    return "".join(password)


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="passgen",
        description="Generate cryptographically secure passwords.",
    )
    p.add_argument("-l", "--length", type=int, default=16,
                   help="password length (default: 16)")
    p.add_argument("-n", "--count", type=int, default=1,
                   help="number of passwords to generate (default: 1)")
    p.add_argument("--no-symbols", action="store_true",
                   help="exclude symbols")
    p.add_argument("--no-digits", action="store_true",
                   help="exclude digits")
    p.add_argument("--no-upper", action="store_true",
                   help="exclude uppercase letters")
    p.add_argument("--no-ambiguous", action="store_true",
                   help="exclude ambiguous chars (Il1O0o)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    use = ["lower"]
    if not args.no_upper:
        use.append("upper")
    if not args.no_digits:
        use.append("digits")
    if not args.no_symbols:
        use.append("symbols")

    try:
        for _ in range(args.count):
            print(generate(args.length, use, args.no_ambiguous))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
