#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Script for json_repair Integration

Demonstrates how json_repair handles malformed JSON often produced by LLMs.
"""
import sys
import json
import json_repair

def test_json_repair():
    print("="*60)
    print("Testing json_repair with various malformed inputs")
    print("="*60)

    test_cases = [
        {
            "name": "Standard JSON",
            "input": '{"agent": "Researcher", "task": "Find info"}',
            "expected_success": True
        },
        {
            "name": "Markdown Block",
            "input": '```json\n{"agent": "Researcher", "task": "Find info"}\n```',
            "expected_success": True
        },
        {
            "name": "Missing Quotes (Keys)",
            "input": '{agent: "Researcher", task: "Find info"}',
            "expected_success": True
        },
        {
            "name": "Trailing Comma",
            "input": '{"agent": "Researcher", "task": "Find info",}',
            "expected_success": True
        },
        {
            "name": "Single Quotes",
            "input": "{'agent': 'Researcher', 'task': 'Find info'}",
            "expected_success": True
        },
        {
            "name": "Truncated JSON",
            "input": '{"agent": "Researcher", "task": "Find',
            "expected_success": True
        }
    ]

    passed_count = 0

    for case in test_cases:
        print(f"\nCase: {case['name']}")
        print(f"Input: {case['input']}")

        # Try standard json (expected to fail for most)
        try:
            json.loads(case['input'])
            print("  Standard json.loads: ✅ Success")
        except Exception as e:
            print(f"  Standard json.loads: ❌ Failed ({str(e)[:50]}...)")

        # Try json_repair
        try:
            result = json_repair.loads(case['input'])
            print(f"  json_repair:         ✅ Success -> {result}")
            passed_count += 1
        except Exception as e:
            print(f"  json_repair:         ❌ Failed ({e})")

    print("\n" + "="*60)
    print(f"Summary: {passed_count}/{len(test_cases)} cases passed with json_repair")
    print("="*60)

    return passed_count == len(test_cases)

if __name__ == "__main__":
    success = test_json_repair()
    sys.exit(0 if success else 1)