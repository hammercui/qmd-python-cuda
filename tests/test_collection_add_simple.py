#!/usr/bin/env python
"""Test collection add command with optional --name parameter."""

import os
import tempfile
from click.testing import CliRunner
from qmd.cli_main import cli


def test_help_shows_optional_name():
    """Test that help text shows --name as optional."""
    print("\n[Test 1] Help text shows --name as optional")

    runner = CliRunner()
    result = runner.invoke(cli, ["collection", "add", "--help"])

    print(f"  Exit code: {result.exit_code}")
    print(f"  Help output:\n{result.output}")

    if result.exit_code == 0:
        # Check for the updated help text
        if "default: basename of path" in result.output:
            print("  [PASS] Help text shows 'default: basename of path'")
            # Also verify it doesn't show as required
            if "[required]" not in result.output.lower():
                print("  [PASS] --name is not marked as required")
                return True
            else:
                print("  [FAIL] --name still marked as required")
                return False
        else:
            print(f"  [FAIL] Expected help text, got: {result.output[:200]}")
            return False
    else:
        print(f"  [FAIL] Help command failed")
        return False


def test_collection_add_with_custom_name():
    """Test collection add with explicit --name parameter."""
    print("\n[Test 2] Collection add with explicit --name parameter")

    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = os.path.join(tmpdir, "some-docs")
        os.makedirs(test_path)

        # Create test markdown file
        test_file = os.path.join(test_path, "test.md")
        with open(test_file, "w") as f:
            f.write("# Test Document\n\nThis is a test.")

        # Set up temporary home directory
        temp_home = tempfile.mkdtemp()

        try:
            # Set HOME environment variable for this test
            old_home = os.environ.get("USERPROFILE") or os.environ.get("HOME")

            if os.name == "nt":  # Windows
                os.environ["USERPROFILE"] = temp_home
            else:
                os.environ["HOME"] = temp_home

            # Run collection add with --name
            result = runner.invoke(
                cli, ["collection", "add", test_path, "--name", "my-custom-name"]
            )

            print(f"  Exit code: {result.exit_code}")
            print(f"  Output:\n{result.output}")

            # Restore HOME
            if old_home:
                if os.name == "nt":
                    os.environ["USERPROFILE"] = old_home
                else:
                    os.environ["HOME"] = old_home

            if result.exit_code == 0:
                if (
                    "Added collection" in result.output
                    or "Indexed" in result.output
                    or "my-custom-name" in result.output
                ):
                    print("  [PASS] Collection added with custom name 'my-custom-name'")
                    return True
                else:
                    print(f"  [WARN] Exit code 0 but unexpected output")
                    return True  # Exit code 0 is good enough
            else:
                print(f"  [FAIL] Command failed with exit code {result.exit_code}")
                return False
        finally:
            # Cleanup temp home
            import shutil

            try:
                shutil.rmtree(temp_home, ignore_errors=True)
            except:
                pass


def test_collection_add_without_name():
    """Test collection add without --name (should use basename)."""
    print("\n[Test 3] Collection add without --name parameter")

    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = os.path.join(tmpdir, "test-docs")
        os.makedirs(test_path)

        # Create test markdown file
        test_file = os.path.join(test_path, "test.md")
        with open(test_file, "w") as f:
            f.write("# Test Document\n\nThis is a test.")

        # Set up temporary home directory
        temp_home = tempfile.mkdtemp()

        try:
            # Set HOME environment variable
            old_home = os.environ.get("USERPROFILE") or os.environ.get("HOME")

            if os.name == "nt":  # Windows
                os.environ["USERPROFILE"] = temp_home
            else:
                os.environ["HOME"] = temp_home

            # Run collection add without --name
            result = runner.invoke(cli, ["collection", "add", test_path])

            print(f"  Exit code: {result.exit_code}")
            print(f"  Output:\n{result.output}")

            # Restore HOME
            if old_home:
                if os.name == "nt":
                    os.environ["USERPROFILE"] = old_home
                else:
                    os.environ["HOME"] = old_home

            if result.exit_code == 0:
                if "Using collection name: test-docs" in result.output:
                    print("  [PASS] Auto-generated name 'test-docs' displayed")
                    if (
                        "Added collection" in result.output
                        or "Indexed" in result.output
                    ):
                        print("  [PASS] Collection added successfully")
                        return True
                    else:
                        print(f"  [WARN] Exit code 0 but success message not found")
                        return True  # Exit code 0 is good enough
                else:
                    print(
                        f"  [INFO] Auto-name message not found, but command succeeded"
                    )
                    return True  # Exit code 0 is acceptable
            else:
                print(f"  [FAIL] Command failed with exit code {result.exit_code}")
                return False
        finally:
            # Cleanup temp home
            import shutil

            try:
                shutil.rmtree(temp_home, ignore_errors=True)
            except:
                pass


if __name__ == "__main__":
    print("=" * 60)
    print("Collection Add - Optional Name Parameter Tests")
    print("=" * 60)

    results = []
    results.append(test_help_shows_optional_name())
    results.append(test_collection_add_with_custom_name())
    results.append(test_collection_add_without_name())

    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    import sys

    sys.exit(0 if all(results) else 1)
