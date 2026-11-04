"""Shared command-line and environment configuration."""

import argparse
import os
from pathlib import Path
import sys


def parse_configuration(parser: argparse.ArgumentParser) -> argparse.Namespace:
    """Parse with CLI > environment > environment file > default precedence.

    Environment keys are uppercase argument destinations (e.g. MQTT_HOST).
    Each key also supports a _FILE variable pointing to a UTF-8 text file.
    Trailing CR/LF characters are removed from file values, not other whitespace.
    Validated environment values become defaults and satisfy required arguments
    by clearing their required flag before parsing. Explicit CLI options bypass
    environment lookup. Store-true flags accept true/false, yes/no, on/off,
    or 1/0, case-insensitively. Invalid environment values use parser.error().
    The supplied parser is modified in place; dotenv files are not loaded.
    """
    provided = {arg.split("=", 1)[0] for arg in sys.argv[1:]}
    for action in parser._actions:
        if action.dest == "help" or provided.intersection(action.option_strings):
            continue
        key = action.dest.upper()
        raw = os.environ.get(key)
        source = key
        if raw is None and (file_path := os.environ.get(f"{key}_FILE")) is not None:
            source = f"{key}_FILE"
            try:
                raw = Path(file_path).read_text(encoding="utf-8").rstrip("\r\n")
            except (OSError, UnicodeError, ValueError):
                parser.error(f"Cannot read configuration from {source}: expected a readable UTF-8 file")
        if raw is None:
            continue
        try:
            if isinstance(action, argparse._StoreTrueAction):
                if raw.lower() not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
                    raise ValueError("expected true/false, 1/0, yes/no, or on/off")
                value = raw.lower() in ("true", "1", "yes", "on")
            else:
                value = action.type(raw) if action.type else raw
            if action.choices is not None and value not in action.choices:
                raise ValueError("not one of the allowed choices")
        except (ValueError, TypeError):
            parser.error(f"Invalid configuration for {source}: expected a valid value for {action.option_strings[0]}")
        action.default = value
        action.required = False
    return parser.parse_args()
