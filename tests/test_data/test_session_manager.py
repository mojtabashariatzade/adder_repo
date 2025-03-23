"""
Test module for data/session_manager.py

This module contains unit tests for the SessionManager and Session classes which manage
application sessions and their state.
"""

import unittest
import os
import sys
import tempfile
import shutil
import time
import json
import threading
from datetime import datetime
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the module being tested
from data.session_manager import SessionManager, Session, SessionStatus


class TestSession(unittest.TestCase):
    """Test suite for the Session class."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_id = "test-session-id"
        self.session_type = "test-session"

        # Disable auto-save for tests to prevent background saves
        self.session = Session(
            session_id=self.session_id,
            session_type=self.session_type,
            auto_save=False
        )

    def tearDown(self):
        """Tear down test fixtures."""
        self.session.cleanup()

    def test_initialization(self):
        """Test session initialization."""
        # Check that the session was initialized correctly
        self.assertEqual(self.session.session_id, self.session_id)
        self.assertEqual(self.session.session_type, self.session_type)
        self.assertEqual(self.session.status, SessionStatus.CREATED)
        self.assertEqual(self.session.progress, 0.0)
        self.assertEqual(self.session.state, {})
        self.assertEqual(self.session.state_history, [])
        self.assertEqual(self.session.event_log, [])
        self.assertEqual(self.session.metrics, {})
        self.assertEqual(self.session.errors, [])
        self.assertIsNone(self.session.recovery_point)
        self.assertEqual(self.session.custom_data, {})

    def test_update_state(self):
        """Test updating the session state."""
        # Initial update
        initial_state = {"key1": "value1", "processed": 10, "total": 100}
        self.session.update_state(initial_state)

        # Check that the state was updated
        self.assertEqual(self.session.state, initial_state)

        # Check that progress was calculated
        self.assertEqual(self.session.progress, 10.0)  # (10/100) * 100

        # Check that no history was recorded for the first update
        self.assertEqual(len(self.session.state_history), 0)

        # Update with new values
        updated_state = {"key1": "updated", "key2": "value2", "processed": 20, "total": 100}
        self.session.update_state(updated_state)

        # Check that the state was merged correctly
        expected_state = {"key1": "updated", "key2": "value2", "processed": 20, "total": 100}
        self.assertEqual(self.session.state, expected_state)

        # Check that progress was updated
        self.assertEqual(self.session.progress, 20.0)  # (20/100) * 100

        # Check that history was recorded
        self.assertEqual(len(self.session.state_history), 1)

        # Check direct progress update
        self.session.update_state({"progress": 50.0})
        self.assertEqual(self.session.progress, 50.0)

    def test_set_status(self):
        """Test setting the session status."""
        # Set status with enum
        self.session.set_status(SessionStatus.RUNNING)
        self.assertEqual(self.session.status, SessionStatus.RUNNING)

        # Set status with string
        self.session.set_status("paused")
        self.assertEqual(self.session.status, SessionStatus.PAUSED)

        # Check that we get None for completion time for non-terminal states
        self.assertIsNone(self.session.completed_at)

        # Set a terminal status
        self.session.set_status(SessionStatus.COMPLETED)
        self.assertEqual(self.session.status, SessionStatus.COMPLETED)

        # Check that completion time was set for terminal status
        self.assertIsNotNone(self.session.completed_at)

    def test_log_event(self):
        """Test logging events."""
        # Log a simple event
        self.session.log_event("Test event")

        # Check that the event was logged
        self.assertEqual(len(self.session.event_log), 1)
        self.assertEqual(self.session.event_log[0]["message"], "Test event")

        # Log an event with data
        event_data = {"key": "value"}
        self.session.log_event("Test event with data", event_data)

        # Check that the event was logged with data
        self.assertEqual(len(self.session.event_log), 2)
        self.assertEqual(self.session.event_log[1]["message"], "Test event with data")
        self.assertEqual(self.session.event_log[1]["data"], event_data)

    def test_log_error(self):
        """Test logging errors."""
        # Log a simple error
        self.session.log_error("Test error")

        # Check that the error was logged
        self.assertEqual(len(self.session.errors), 1)
        self.assertEqual(self.session.errors[0]["message"], "Test error")
        self.assertEqual(self.session.errors[0]["type"], "UnknownError")

        # Log an error with a type
        self.session.log_error("Test error with type", "TestError")

        # Check that the error was logged with the correct type
        self.assertEqual(len(self.session.errors), 2)
        self.assertEqual(self.session.errors[1]["message"], "Test error with type")
        self.assertEqual(self.session.errors[1]["type"], "TestError")

        # Log an error with an exception
        exception = ValueError("Test exception")
        self.session.log_error("Test error with exception", exception=exception)

        # Check that the error was logged with the exception info
        self.assertEqual(len(self.session.errors), 3)
        self.assertEqual(self.session.errors[2]["message"], "Test error with exception")
        self.assertEqual(self.session.errors[2]["type"], "ValueError")
        self.assertEqual(self.session.errors[2]["exception"], "Test exception")

        # Check that the error was also added to the event log
        error_events = [e for e in self.session.event_log if "Error:" in e["message"]]
        self.assertEqual(len(error_events), 3)

    def test_record_metric(self):
        """Test recording metrics."""
        # Record a simple metric
        self.session.record_metric("test_metric", 42)

        # Check that the metric was recorded
        self.assertIn("general", self.session.metrics)
        self.assertIn("test_metric", self.session.metrics["general"])
        self.assertEqual(len(self.session.metrics["general"]["test_metric"]), 1)
        self.assertEqual(self.session.metrics["general"]["test_metric"][0]["value"], 42)

        # Record a metric with a category
        self.session.record_metric("category_metric", 100, "test_category")

        # Check that the metric was recorded in the correct category
        self.assertIn("test_category", self.session.metrics)
        self.assertIn("category_metric", self.session.metrics["test_category"])
        self.assertEqual(len(self.session.metrics["test_category"]["category_metric"]), 1)
        self.assertEqual(self.session.metrics["test_category"]["category_metric"][0]["value"], 100)

        # Record another value for the same metric
        self.session.record_metric("test_metric", 43)

        # Check that the new value was added to the metric
        self.assertEqual(len(self.session.metrics["general"]["test_metric"]), 2)
        self.assertEqual(self.session.metrics["general"]["test_metric"][1]["value"], 43)

    def test_recovery_point(self):
        """Test setting and clearing recovery points."""
        # Set a recovery point
        recovery_data = {"position": 42, "items_processed": [1, 2, 3]}
        self.session.set_recovery_point(recovery_data)

        # Check that the recovery point was set
        self.assertIsNotNone(self.session.recovery_point)
        self.assertEqual(self.session.recovery_point["data"], recovery_data)

        # Clear the recovery point
        self.session.clear_recovery_point()

        # Check that the recovery point was cleared
        self.assertIsNone(self.session.recovery_point)

    def test_custom_data(self):
        """Test setting and getting custom data."""
        # Set a custom data value
        self.session.set_custom_data("test_key", "test_value")

        # Check that the custom data was set
        self.assertEqual(self.session.custom_data["test_key"], "test_value")

        # Get a custom data value
        value = self.session.get_custom_data("test_key")

        # Check that we got the correct value
        self.assertEqual(value, "test_value")

        # Get a non-existent value
        value = self.session.get_custom_data("non_existent")

        # Check that we got None
        self.assertIsNone(value)

        # Get a non-existent value with a default
        value = self.session.get_custom_data("non_existent", "default")

        # Check that we got the default value
        self.assertEqual(value, "default")

    def test_to_from_dict(self):
        """Test converting a session to and from a dictionary."""
        # Set up a session with various data
        self.session.update_state({"key1": "value1", "processed": 10, "total": 100})
        self.session.set_status(SessionStatus.RUNNING)
        self.session.log_event("Test event")
        self.session.log_error("Test error")
        self.session.record_metric("test_metric", 42)
        self.session.set_recovery_point({"position": 42})
        self.session.set_custom_data("test_key", "test_value")

        # Convert to dictionary
        session_dict = self.session.to_dict()

        # Check that the dictionary has all the expected keys
        expected_keys = [
            "session_id", "session_type", "created_at", "updated_at",
            "status", "progress", "state", "state_history", "event_log",
            "metrics", "errors", "recovery_point", "custom_data"
        ]
        for key in expected_keys:
            self.assertIn(key, session_dict)

        # Convert back to a session
        new_session = Session.from_dict(session_dict)

        # Check that the new session has the same data
        self.assertEqual(new_session.session_id, self.session.session_id)
        self.assertEqual(new_session.session_type, self.session.session_type)
        self.assertEqual(new_session.status, self.session.status)
        self.assertEqual(new_session.progress, self.session.progress)
        self.assertEqual(new_session.state, self.session.state)
        self.assertEqual(len(new_session.event_log), len(self.session.event_log))
        self.assertEqual(len(new_session.errors), len(self.session.errors))
        self.assertEqual(new_session.recovery_point["data"], self.session.recovery_point["data"])
        self.assertEqual(new_session.custom_data, self.session.custom_data)

    def test_context_manager(self):
        """Test using a session as a context manager."""
        # Use a session as a context manager
        with self.session as s:
            # Check that we got the session
            self.assertEqual(s, self.session)

            # Do something that raises an exception
            if True:  # Use if to avoid syntax error
                raise ValueError("Test exception")

        # Check that the exception was logged
        error_found = False
        for error in self.session.errors:
            if error["type"] == "ValueError" and "Test exception" in error["exception"]:
                error_found = True
                break

        self.assertTrue(error_found, "Exception was not logged")

    def test_export_summary(self):
        """Test exporting a session summary."""
        # Set up a session with some data
        self.session.update_state({"key1": "value1", "processed": 10, "total": 100})
        self.session.set_status(SessionStatus.RUNNING)

        # Export as JSON
        json_summary = self.session.export_summary(format='json')

        # Check that the JSON summary has the expected keys
        expected_keys = [
            "session_id", "session_type", "status", "progress",
            "created_at", "updated_at", "error_count"
        ]
        for key in expected_keys:
            self.assertIn(key, json_summary)

        # Export as text
        text_summary = self.session.export_summary(format='text')

        # Check that the text summary contains the session ID
        self.assertIn(self.session.session_id, text_summary)

        # Check that invalid format raises an exception
        with self.assertRaises(ValueError):
            self.session.export_summary(format='invalid')

    def test_checkpoints(self):
        """Test adding state checkpoints."""
        # Add a checkpoint
        self.session.update_state({"position": 1})
        self.session.add_state_checkpoint("checkpoint1")

        # Update state and add another checkpoint
        self.session.update_state({"position": 2})
        self.session.add_state_checkpoint("checkpoint2")

        # Check that checkpoints were added to custom data
        self.assertIn("checkpoints", self.session.custom_data)
        self.assertEqual(len(self.session.custom_data["checkpoints"]), 2)

        # Check that checkpoint data is correct
        checkpoint1 = self.session.custom_data["checkpoints"][0]
        self.assertEqual(checkpoint1["name"], "checkpoint1")
        self.assertEqual(checkpoint1["state"]["position"], 1)

        checkpoint2 = self.session.custom_data["checkpoints"][1]
        self.assertEqual(checkpoint2["name"], "checkpoint2")
        self.assertEqual(checkpoint2["state"]["position"], 2)


class TestSessionManager(unittest.TestCase):
    """Test suite for the SessionManager class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for session files
        self.temp_dir = tempfile.mkdtemp()

        # Clear the SessionManager instance
        SessionManager._instance = None

        # Create a SessionManager with the temporary directory
        self.session_manager = SessionManager(
            sessions_dir=self.temp_dir,
            auto_cleanup=False  # Disable auto-cleanup for tests
        )

    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up any resources
        try:
            # Clean up temporary directory
            shutil.rmtree(self.temp_dir)
        except (OSError, IOError):
            pass  # Ignore errors during cleanup

    def test_singleton_pattern(self):
        """Test the singleton pattern."""
        # Create another SessionManager
        another_manager = SessionManager()

        # Check that we got the same instance
        self.assertIs(another_manager, self.session_manager)

        # Check that the sessions directory is the same
        self.assertEqual(another_manager.sessions_dir, self.session_manager.sessions_dir)

    def test_create_session(self):
        """Test creating a session."""
        # Create a session
        session = self.session_manager.create_session(session_type="test")

        # Check that the session was created
        self.assertIsNotNone(session)
        self.assertEqual(session.session_type, "test")

        # Check that the session was added to active sessions
        self.assertIn(session.session_id, self.session_manager.active_sessions)

        # Check that the session file was created
        session_file = os.path.join(
            self.temp_dir, f"session_{session.session_id}.json"
        )
        self.assertTrue(os.path.exists(session_file))

    def test_save_load_session(self):
        """Test saving and loading a session."""
        # Create a session
        session = self.session_manager.create_session(session_type="test")

        # Update the session state
        session.update_state({"key": "value"})
        session.set_status(SessionStatus.RUNNING)

        # Save the session
        result = self.session_manager.save_session(session)
        self.assertTrue(result)

        # Clear the active sessions cache
        self.session_manager.active_sessions.clear()

        # Load the session
        loaded_session = self.session_manager.load_session(session.session_id)

        # Check that the session was loaded correctly
        self.assertIsNotNone(loaded_session)
        self.assertEqual(loaded_session.session_id, session.session_id)
        self.assertEqual(loaded_session.session_type, session.session_type)
        self.assertEqual(loaded_session.state, session.state)
        self.assertEqual(loaded_session.status, session.status)

    def test_get_session(self):
        """Test getting a session."""
        # Create a session
        session = self.session_manager.create_session(session_type="test")
        session_id = session.session_id

        # Clear the active sessions cache
        self.session_manager.active_sessions.clear()

        # Get the session (should load from file)
        retrieved_session = self.session_manager.get_session(session_id)

        # Check that the session was retrieved correctly
        self.assertIsNotNone(retrieved_session)
        self.assertEqual(retrieved_session.session_id, session_id)

        # Try to get a non-existent session
        non_existent = self.session_manager.get_session("non-existent")
        self.assertIsNone(non_existent)

        # Try to get a non-existent session with create_if_missing=True
        created_session = self.session_manager.get_session(
            "new-session", create_if_missing=True, session_type="test"
        )
        self.assertIsNotNone(created_session)
        self.assertEqual(created_session.session_id, "new-session")
        self.assertEqual(created_session.session_type, "test")

    def test_list_sessions(self):
        """Test listing sessions."""
        # Create some sessions
        session1 = self.session_manager.create_session(session_type="type1")
        session1.set_status(SessionStatus.RUNNING)
        self.session_manager.save_session(session1)

        session2 = self.session_manager.create_session(session_type="type2")
        session2.set_status(SessionStatus.COMPLETED)
        self.session_manager.save_session(session2)

        session3 = self.session_manager.create_session(session_type="type1")
        session3.set_status(SessionStatus.PAUSED)
        self.session_manager.save_session(session3)

        # List all sessions
        sessions = self.session_manager.list_sessions()
        self.assertEqual(len(sessions), 3)

        # List sessions by type
        type1_sessions = self.session_manager.list_sessions(session_type="type1")
        self.assertEqual(len(type1_sessions), 2)

        # List sessions by status
        running_sessions = self.session_manager.list_sessions(status="running")
        self.assertEqual(len(running_sessions), 1)
        self.assertEqual(running_sessions[0]["session_id"], session1.session_id)

        completed_sessions = self.session_manager.list_sessions(status=SessionStatus.COMPLETED)
        self.assertEqual(len(completed_sessions), 1)
        self.assertEqual(completed_sessions[0]["session_id"], session2.session_id)

    def test_find_incomplete_sessions(self):
        """Test finding incomplete sessions."""
        # Create some sessions with different statuses
        session1 = self.session_manager.create_session()
        session1.set_status(SessionStatus.RUNNING)
        self.session_manager.save_session(session1)

        session2 = self.session_manager.create_session()
        session2.set_status(SessionStatus.COMPLETED)
        self.session_manager.save_session(session2)

        session3 = self.session_manager.create_session()
        session3.set_status(SessionStatus.PAUSED)
        self.session_manager.save_session(session3)

        session4 = self.session_manager.create_session()
        session4.set_status(SessionStatus.INTERRUPTED)
        self.session_manager.save_session(session4)

        # Find incomplete sessions
        incomplete = self.session_manager.find_incomplete_sessions()

        # Check that we found the running, paused, and interrupted sessions
        self.assertEqual(len(incomplete), 3)
        self.assertIn(session1.session_id, incomplete)
        self.assertIn(session3.session_id, incomplete)
        self.assertIn(session4.session_id, incomplete)

        # Check that we didn't find the completed session
        self.assertNotIn(session2.session_id, incomplete)

    def test_delete_session(self):
        """Test deleting a session."""
        # Create a session
        session = self.session_manager.create_session()
        session_id = session.session_id

        # Check that the session file exists
        session_file = os.path.join(
            self.temp_dir, f"session_{session_id}.json"
        )
        self.assertTrue(os.path.exists(session_file))

        # Delete the session
        result = self.session_manager.delete_session(session_id)
        self.assertTrue(result)

        # Check that the session file was deleted
        self.assertFalse(os.path.exists(session_file))

        # Check that the session was removed from active sessions
        self.assertNotIn(session_id, self.session_manager.active_sessions)

        # Try to delete a non-existent session
        result = self.session_manager.delete_session("non-existent")
        self.assertFalse(result)

    def test_archive_sessions(self):
        """Test archiving sessions."""
        # Create some sessions that will be "old"
        for i in range(3):
            session = self.session_manager.create_session()
            session.set_status(SessionStatus.COMPLETED)
            # Directly update the updated_at timestamp to make it "old"
            session.updated_at = "2000-01-01T00:00:00"
            self.session_manager.save_session(session)

        # Create some recent sessions
        for i in range(2):
            session = self.session_manager.create_session()
            session.set_status(SessionStatus.COMPLETED)
            self.session_manager.save_session(session)

        # Archive old sessions
        archive_dir = os.path.join(self.temp_dir, "archives")
        count = self.session_manager.archive_completed_sessions(
            older_than_days=1,  # Anything older than 1 day is archived
            archive_dir=archive_dir,
            compress=False  # Don't compress for this test
        )

        # Check that 3 sessions were archived
        self.assertEqual(count, 3)

        # Check that the archive directory was created
        self.assertTrue(os.path.exists(archive_dir))

        # Check that 3 session files were moved to the archive directory
        archived_files = os.listdir(archive_dir)
        self.assertEqual(len(archived_files), 3)

        # Check that only the recent sessions remain in the main directory
        main_files = [f for f in os.listdir(self.temp_dir)
                     if f.startswith("session_") and f.endswith(".json")]
        self.assertEqual(len(main_files), 2)

    @patch('time.time', side_effect=[100, 101, 102, 103])
    def test_session_trim(self, mock_time):
        """Test trimming active sessions when limit is exceeded."""
        # Set the max_active_sessions to a small number
        self.session_manager.max_active_sessions = 2

        # Create 3 sessions (exceeding the limit)
        session1 = self.session_manager.create_session()
        session2 = self.session_manager.create_session()
        session3 = self.session_manager.create_session()

        # Check that we have 2 sessions in memory (the 2 most recent)
        self.assertEqual(len(self.session_manager.active_sessions), 2)

        # Check that the oldest session was removed from memory
        self.assertNotIn(session1.session_id, self.session_manager.active_sessions)
        self.assertIn(session2.session_id, self.session_manager.active_sessions)
        self.assertIn(session3.session_id, self.session_manager.active_sessions)

    def test_import_session(self):
        """Test importing a session from a file."""
        # Create a session
        session = self.session_manager.create_session(session_type="test")
        session.update_state({"key": "value"})
        self.session_manager.save_session(session)

        # Get the session file path
        session_file = os.path.join(
            self.temp_dir, f"session_{session.session_id}.json"
        )

        # Create a copy of the session file for importing
        import_file = os.path.join(self.temp_dir, "import.json")
        shutil.copy2(session_file, import_file)

        # Delete the original session
        self.session_manager.delete_session(session.session_id)

        # Import the session with a new ID
        new_id = "imported-session"
        imported_id = self.session_manager.import_session(import_file, new_id=new_id)

        # Check that the import was successful
        self.assertEqual(imported_id, new_id)

        # Check that the imported session exists
        imported_session = self.session_manager.get_session(new_id)
        self.assertIsNotNone(imported_session)
        self.assertEqual(imported_session.session_type, "test")
        self.assertEqual(imported_session.state, {"key": "value"})

        # Try to import again (should fail because the session already exists)
        result = self.session_manager.import_session(import_file, new_id=new_id)
        self.assertIsNone(result)

        # Try to import again with overwrite=True
        result = self.session_manager.import_session(import_file, new_id=new_id, overwrite=True)
        self.assertEqual(result, new_id)


def test_get_session_manager():
    """Test getting a session manager directly."""
    # Use a temporary directory
    temp_dir = tempfile.mkdtemp()
    try:
        # Get a session manager
        manager = SessionManager(sessions_dir=temp_dir)

        # Check that we got a SessionManager instance
        assert isinstance(manager, SessionManager)

        # Check that the sessions directory was set correctly
        assert manager.sessions_dir == temp_dir

        # Get another session manager (should be same instance)
        manager2 = SessionManager()

        # Check that we got the same instance
        assert manager2 is manager
    finally:
        # Clean up
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    unittest.main()