"""Compatibility entry point; prefer the ferroamp-sunspec command."""

from ferroamp_sunspec.bridge import cli

if __name__ == "__main__":
    cli()
