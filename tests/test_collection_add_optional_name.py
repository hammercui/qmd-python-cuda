#!/usr/bin/env python
"""Test collection add command with optional --name parameter."""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from qmd.cli import Context
from qmd.cli._collection import collection_add
from qmd.models.config import CollectionConfig


def test_collection_add_without_name():
    """Test collection add without --name (should use basename)."""
    print("\n[Test 1] Collection add without --name parameter")

    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = os.path.join(tmpdir, "test-docs")
        os.makedirs(test_path)

        # Create a test markdown file
        with open(os.path.join(test_path, "test.md"), "w") as f:
            f.write("# Test Document\n\nThis is a test.")

        # Create mock context
        ctx = Context()
        original_collections = ctx.config.collections.copy()

        # Mock CLI object with necessary attributes
        class MockCtxObj:
            def __init__(self, context):
                self.config = context.config
                self.db = context.db

        ctx_obj = MockCtxObj(ctx)

        # Call collection_add without --name
        try:
            collection_add(ctx_obj, test_path, None, "**/*.md")

            # Verify collection was added with basename as name
            collection_names = [c.name for c in ctx_obj.config.collections]
            if "test-docs" in collection_names:
                print("  [PASS] Collection added with auto-generated name 'test-docs'")
                result = True
            else:
                print(f"  [FAIL] Expected 'test-docs', got: {collection_names}")
                result = False
        except Exception as e:
            print(f"  [ERROR] {e}")
            result = False
        finally:
            # Cleanup: restore original collections
            ctx.config.collections = original_collections
            ctx.config.save()

    return result


def test_collection_add_with_name():
    """Test collection add with explicit --name parameter."""
    print("\n[Test 2] Collection add with explicit --name parameter")

    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = os.path.join(tmpdir, "some-docs")
        os.makedirs(test_path)

        # Create a test markdown file
        with open(os.path.join(test_path, "test.md"), "w") as f:
            f.write("# Test Document\n\nThis is a test.")

        # Create mock context
        ctx = Context()
        original_collections = ctx.config.collections.copy()

        # Mock CLI object
        class MockCtxObj:
            def __init__(self, context):
                self.config = context.config
                self.db = context.db

        ctx_obj = MockCtxObj(ctx)

        # Call collection_add with --name
        try:
            collection_add(ctx_obj, test_path, "my-custom-name", "**/*.md")

            # Verify collection was added with custom name
            collection_names = [c.name for c in ctx_obj.config.collections]
            if "my-custom-name" in collection_names:
                print("  [PASS] Collection added with custom name 'my-custom-name'")
                result = True
            else:
                print(f"  [FAIL] Expected 'my-custom-name', got: {collection_names}")
                result = False
        except Exception as e:
            print(f"  [ERROR] {e}")
            result = False
        finally:
            # Cleanup: restore original collections
            ctx.config.collections = original_collections
            ctx.config.save()

    return result


def test_duplicate_name_detection():
    """Test that duplicate collection names are detected."""
    print("\n[Test 3] Duplicate name detection")

    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        test_path = os.path.join(tmpdir, "test-docs")
        os.makedirs(test_path)

        # Create a test markdown file
        with open(os.path.join(test_path, "test.md"), "w") as f:
            f.write("# Test Document\n\nThis is a test.")

        # Create mock context
        ctx = Context()
        original_collections = ctx.config.collections.copy()

        # Mock CLI object
        class MockCtxObj:
            def __init__(self, context):
                self.config = context.config
                self.db = context.db

        ctx_obj = MockCtxObj(ctx)

        try:
            # Add first collection
            collection_add(ctx_obj, test_path, "duplicate-test", "**/*.md")

            # Try to add second collection with same name (should fail)
            test_path2 = os.path.join(tmpdir, "other-docs")
            os.makedirs(test_path2)
            with open(os.path.join(test_path2, "test.md"), "w") as f:
                f.write("# Another Test\n\nContent.")

            # Capture output (should show error)
            import io
            from contextlib import redirect_stdout

            f_output = io.StringIO()
            with redirect_stdout(f_output):
                collection_add(ctx_obj, test_path2, "duplicate-test", "**/*.md")

            output = f_output.getvalue()

            # Check for error message
            if "already exists" in output.lower():
                print("  [PASS] Duplicate name detected correctly")
                result = True
            else:
                print(f"  [FAIL] Expected duplicate name error, got: {output[:100]}")
                result = False

        except Exception as e:
            print(f"  [ERROR] {e}")
            result = False
        finally:
            # Cleanup: restore original collections
            ctx.config.collections = original_collections
            ctx.config.save()

    return result


if __name__ == "__main__":
    print("=" * 60)
    print("Collection Add - Optional Name Parameter Tests")
    print("=" * 60)

    results = []
    results.append(test_collection_add_without_name())
    results.append(test_collection_add_with_name())
    results.append(test_duplicate_name_detection())

    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    sys.exit(0 if all(results) else 1)
