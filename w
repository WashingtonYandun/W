#!/usr/bin/env python3
import os
import sys

repo_root = os.path.dirname(os.path.realpath(__file__))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from main import main

if __name__ == "__main__":
    main()
