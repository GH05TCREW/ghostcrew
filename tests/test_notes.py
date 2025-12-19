"""Tests for the Notes tool."""

import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

from pentestagent.tools.notes import notes, set_notes_file, get_all_notes, _notes

# We need to reset the global state for tests
@pytest.fixture(autouse=True)
def reset_notes_state(tmp_path):
    """Reset the notes global state for each test."""
    # Point to a temp file
    temp_notes_file = tmp_path / "notes.json"
    set_notes_file(temp_notes_file)
    
    # Clear the global dictionary (it's imported from the module)
    # We need to clear the actual dictionary object in the module
    from pentestagent.tools.notes import _notes
    _notes.clear()
    
    yield
    
    # Cleanup is handled by tmp_path

@pytest.mark.asyncio
async def test_create_note():
    """Test creating a new note."""
    args = {
        "action": "create",
        "key": "test_note",
        "value": "This is a test note",
        "category": "info",
        "confidence": "high"
    }
    
    result = await notes(args, runtime=None)
    assert "Created note 'test_note'" in result
    
    all_notes = await get_all_notes()
    assert "test_note" in all_notes
    assert all_notes["test_note"]["content"] == "This is a test note"
    assert all_notes["test_note"]["category"] == "info"
    assert all_notes["test_note"]["confidence"] == "high"

@pytest.mark.asyncio
async def test_read_note():
    """Test reading an existing note."""
    # Create first
    await notes({
        "action": "create",
        "key": "read_me",
        "value": "Content to read"
    }, runtime=None)
    
    # Read
    result = await notes({
        "action": "read",
        "key": "read_me"
    }, runtime=None)
    
    assert "Content to read" in result
    # The format is "[key] (category, confidence, status) content"
    assert "(info, medium, confirmed)" in result

@pytest.mark.asyncio
async def test_update_note():
    """Test updating a note."""
    await notes({
        "action": "create",
        "key": "update_me",
        "value": "Original content"
    }, runtime=None)
    
    result = await notes({
        "action": "update",
        "key": "update_me",
        "value": "New content"
    }, runtime=None)
    
    assert "Updated note 'update_me'" in result
    
    all_notes = await get_all_notes()
    assert all_notes["update_me"]["content"] == "New content"

@pytest.mark.asyncio
async def test_delete_note():
    """Test deleting a note."""
    await notes({
        "action": "create",
        "key": "delete_me",
        "value": "Bye bye"
    }, runtime=None)
    
    result = await notes({
        "action": "delete",
        "key": "delete_me"
    }, runtime=None)
    
    assert "Deleted note 'delete_me'" in result
    
    all_notes = await get_all_notes()
    assert "delete_me" not in all_notes

@pytest.mark.asyncio
async def test_list_notes():
    """Test listing all notes."""
    await notes({"action": "create", "key": "n1", "value": "v1"}, runtime=None)
    await notes({"action": "create", "key": "n2", "value": "v2"}, runtime=None)
    
    result = await notes({"action": "list"}, runtime=None)
    
    assert "n1" in result
    assert "n2" in result
    assert "Notes (2 entries):" in result

@pytest.mark.asyncio
async def test_persistence(tmp_path):
    """Test that notes are saved to disk."""
    # The fixture already sets a temp file
    temp_file = tmp_path / "notes.json"
    
    await notes({
        "action": "create",
        "key": "persistent_note",
        "value": "I survive restarts"
    }, runtime=None)
    
    assert temp_file.exists()
    content = json.loads(temp_file.read_text())
    assert "persistent_note" in content
    assert content["persistent_note"]["content"] == "I survive restarts"

@pytest.mark.asyncio
async def test_legacy_migration(tmp_path):
    """Test migration of legacy string notes."""
    # Create a legacy file
    legacy_file = tmp_path / "legacy_notes.json"
    legacy_data = {
        "old_note": "Just a string",
        "new_note": {"content": "A dict", "category": "info"}
    }
    legacy_file.write_text(json.dumps(legacy_data))
    
    # Point the tool to this file
    set_notes_file(legacy_file)
    
    # Trigger load (get_all_notes calls _load_notes_unlocked if empty, but we need to clear first)
    from pentestagent.tools.notes import _notes
    _notes.clear()
    
    all_notes = await get_all_notes()
    
    assert "old_note" in all_notes
    assert isinstance(all_notes["old_note"], dict)
    assert all_notes["old_note"]["content"] == "Just a string"
    assert all_notes["old_note"]["category"] == "info"
    
    assert "new_note" in all_notes
    assert all_notes["new_note"]["content"] == "A dict"
