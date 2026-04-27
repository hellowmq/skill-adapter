#!/usr/bin/env python3
"""Placeholder PDF helper script for the example skill."""
import sys

def main():
    if len(sys.argv) < 2:
        print("Usage: run.py <extract|merge|split|rotate> [args...]")
        sys.exit(1)
    cmd = sys.argv[1]
    print(f"[pdf-helper] would execute: {cmd} with args {sys.argv[2:]}")

if __name__ == "__main__":
    main()
