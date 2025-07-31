import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest
import rich

from unpage.utils import edit_file


@pytest.mark.asyncio
async def test_edit_file_with_args():
    """Test edit_file with command that has arguments."""
    # Setup
    mock_path = Path("/tmp/test_file.txt")

    # Mock shutil.which to return a valid path for the editor
    with (
        patch("unpage.utils.shutil.which", return_value="/usr/bin/subl"),
        patch("unpage.utils.anyio.run_process", new_callable=AsyncMock) as mock_run_process,
        patch("unpage.utils.rich.print") as mock_print,
    ):
        # Call edit_file with editor that has arguments
        await edit_file(mock_path, editor="subl -w")

        # Check that run_process was called with correct arguments
        mock_run_process.assert_called_once()
        args, kwargs = mock_run_process.call_args

        # The command should be ['/usr/bin/subl', '-w', '/tmp/test_file.txt']
        assert args[0] == ["/usr/bin/subl", "-w", str(mock_path)]

        # Standard streams should be set properly
        assert kwargs["stdin"] == sys.stdin
        assert kwargs["stdout"] == sys.stdout
        assert kwargs["stderr"] == sys.stderr


@pytest.mark.asyncio
async def test_edit_file_editor_not_found():
    """Test edit_file when editor binary is not found."""
    # Setup
    mock_path = Path("/tmp/test_file.txt")

    # Mock shutil.which to return None (editor not found)
    with (
        patch("unpage.utils.shutil.which", return_value=None),
        patch("unpage.utils.rich.print") as mock_print,
    ):
        # Call edit_file with nonexistent editor
        await edit_file(mock_path, editor="nonexistent-editor -w")

        # Check that rich.print was called with error message
        mock_print.assert_any_call(f"[red]Editor 'nonexistent-editor' not found in $PATH[/red]")
        mock_print.assert_any_call(f"[blue]Please manually open: '{str(mock_path)}'[/blue]")


@pytest.mark.asyncio
async def test_edit_file_process_error():
    """Test edit_file when process execution fails."""
    # Setup
    mock_path = Path("/tmp/test_file.txt")

    # Mock shutil.which to return a valid path, but run_process raises an error
    with (
        patch("unpage.utils.shutil.which", return_value="/usr/bin/subl"),
        patch(
            "unpage.utils.anyio.run_process", side_effect=subprocess.CalledProcessError(1, "subl")
        ),
        patch("unpage.utils.rich.print") as mock_print,
    ):
        # Call edit_file with editor that will fail
        await edit_file(mock_path, editor="subl -w")

        # Check that rich.print was called with error message
        mock_print.assert_any_call(f"[red]Failed to open '{str(mock_path)}' with 'subl -w'[/red]")
        mock_print.assert_any_call(f"[blue]Please manually open: '{str(mock_path)}'[/blue]")
