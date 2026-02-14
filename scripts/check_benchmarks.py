#!/usr/bin/env python3
"""
Benchmark regression checker.

Compares current benchmark results to a saved baseline and checks
if performance has degraded beyond acceptable threshold (1.2x).
"""
import argparse
import json
import sys


def load_results(filename):
    """Load benchmark results from JSON file."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Baseline file {filename} not found. Creating new baseline.")
        return None


def check_regression(current, baseline, threshold=1.2):
    """Check if current results exceed threshold compared to baseline."""
    failed = False

    # Group results by test and group
    current_by_test = {}
    for result in current.get('benchmarks', []):
        key = f"{result['group']}/{result['name']}"
        current_by_test[key] = result

    baseline_by_test = {}
    for result in baseline.get('benchmarks', []):
        key = f"{result['group']}/{result['name']}"
        baseline_by_test[key] = result

    # Compare each test
    for key, current_result in current_by_test.items():
        if key not in baseline_by_test:
            print(f"  [NEW] {key}: No baseline to compare")
            continue

        baseline_result = baseline_by_test[key]

        current_median = current_result.get('stats', {}).get('median', 0)
        baseline_median = baseline_result.get('stats', {}).get('median', 0)

        if baseline_median == 0:
            ratio = 0
        else:
            ratio = current_median / baseline_median

        status = "✅ OK"
        if ratio > threshold:
            status = f"❌ FAILED ({ratio:.2f}x > {threshold}x)"
            failed = True

        print(f"  {status} {key}: {current_median:.4f}s (baseline: {baseline_median:.4f}s, ratio: {ratio:.2f}x)")

    return not failed


def main():
    parser = argparse.ArgumentParser(description='Check benchmark regression')
    parser.add_argument('--baseline', required=True, help='Baseline JSON file')
    parser.add_argument('--current', default='benchmark.json', help='Current results file')
    parser.add_argument('--threshold', type=float, default=1.2, help='Failure threshold (default: 1.2x)')

    args = parser.parse_args()

    baseline = load_results(args.baseline)
    if baseline is None:
        # No baseline, save current as new baseline
        import shutil
        shutil.copy(args.current, args.baseline)
        print(f"Created new baseline: {args.baseline}")
        sys.exit(0)

    current = load_results(args.current)
    if current is None:
        print(f"Error: Current results file not found: {args.current}")
        sys.exit(1)

    # Check regression
    passed = check_regression(current, baseline, args.threshold)

    if not passed:
        print("\n❌ Benchmark regression detected!")
        sys.exit(1)
    else:
        print("\n✅ All benchmarks within threshold")
        sys.exit(0)


if __name__ == '__main__':
    main()
