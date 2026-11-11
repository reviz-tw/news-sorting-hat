#!/usr/bin/env python3
"""Replay synthetic mixed-policy replies to exercise the workflow without a model service."""

import json
import sys
from pathlib import Path

request = json.load(sys.stdin)
suffixes = {"classification": "classification", "analysis": "analysis", "presentation": "modules"}
path = Path(__file__).resolve().parent / ("mixed-policy." + suffixes[request["stage"]] + ".json")
sys.stdout.write(path.read_text(encoding="utf-8"))
