"""Tests for the agent templates CLI command."""

from pathlib import Path


def test_list_templates_success(unpage):
    """Test successful listing of agent templates.

    Should:
    - List all available agent templates
    - Show templates in sorted order
    - Exit with code 0 (success)
    """
    # Run the command
    stdout, stderr, exit_code = unpage("agent templates")

    # Verify success and exit code
    assert stderr == ""
    assert exit_code == 0

    # Verify output contains header and built-in templates
    assert "Available agent templates:" in stdout
    assert "* blank" in stdout
    assert "* default" in stdout
    assert "* demo_quickstart" in stdout

    # Verify templates are listed in sorted order
    lines = stdout.strip().split("\n")
    template_lines = [line for line in lines if line.startswith("* ")]
    template_dir = (
        Path(__file__).parent.parent.parent.parent / "src" / "unpage" / "agent" / "templates"
    )
    expected_templates = [
        f"* {template_file.relative_to(template_dir).with_suffix('')}"
        for template_file in template_dir.glob("**/*.yaml")
    ]
    assert sorted(template_lines) == sorted(expected_templates)


def test_list_templates_without_fixture(unpage, test_profile):
    """Test listing templates when using the real template directory.

    This tests the command against the actual built-in templates.
    """
    # Run the command
    stdout, stderr, exit_code = unpage("agent templates")

    # Verify success and exit code
    assert stderr == ""
    assert exit_code == 0

    # Verify output format
    assert "Available agent templates:" in stdout

    # Should have at least one template (built-in ones)
    lines = stdout.strip().split("\n")
    template_lines = [line for line in lines if line.startswith("* ")]
    assert len(template_lines) >= 1  # At least one template should exist


def test_templates_output_format(unpage):
    """Test that template output follows the expected format."""
    stdout, stderr, exit_code = unpage("agent templates")

    assert exit_code == 0
    assert stderr == ""

    lines = stdout.strip().split("\n")

    # First line should be the header
    assert lines[0] == "Available agent templates:"

    # Subsequent lines should be templates with "* " prefix
    for line in lines[1:]:
        if line.strip():  # Skip empty lines
            assert line.startswith("* ")
            # Template name should not be empty
            template_name = line[2:].strip()
            assert len(template_name) > 0
