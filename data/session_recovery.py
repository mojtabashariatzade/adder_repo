"""
Session Recovery Module

This module provides utilities for recovering interrupted sessions and implementing
checkpoint-based recovery mechanisms. It handles the detection, analysis, and
resumption of sessions that were interrupted due to application crashes,
network failures, or other unexpected events.

Features:
- Detection of interrupted sessions
- Analysis of session state for recoverability
- Implementation of recovery strategies
- Checkpoint-based recovery mechanisms
- Monitoring and reporting of recovery operations
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from session_types import SessionStatus
from session import Session
from session_storage import SessionStorage, default_storage

# Setup logger
logger = logging.getLogger(__name__)


class RecoveryStrategy:
    """Base class for session recovery strategies."""

    def can_recover(self, session: Session) -> bool:
        """
        Determine if this strategy can recover the given session.

        Args:
            session (Session): The session to evaluate

        Returns:
            bool: True if this strategy can recover the session
        """
        return False

    def recover(self, session: Session) -> bool:
        """
        Attempt to recover the session.

        Args:
            session (Session): The session to recover

        Returns:
            bool: True if recovery was successful
        """
        return False


class CheckpointRecoveryStrategy(RecoveryStrategy):
    """Recovery strategy based on checkpoints in the session state."""

    def can_recover(self, session: Session) -> bool:
        """
        Check if the session has valid checkpoints for recovery.

        Args:
            session (Session): The session to evaluate

        Returns:
            bool: True if checkpoints are available for recovery
        """
        # Check if the session has a recovery point
        if session.recovery_point is not None:
            return True

        # Check if the session has checkpoints in custom data
        checkpoints = session.custom_data.get("checkpoints", [])
        return len(checkpoints) > 0

    def recover(self, session: Session) -> bool:
        """
        Recover a session from its latest checkpoint.

        Args:
            session (Session): The session to recover

        Returns:
            bool: True if recovery was successful
        """
        try:
            # First try to use the recovery point if available
            if session.recovery_point is not None:
                logger.info(
                    f"Recovering session {session.session_id} using recovery point")

                # Get recovery data
                recovery_data = session.recovery_point.get("data", {})

                # Update session state with recovery data
                session.update_state(recovery_data)

                # Update session status
                session.set_status(SessionStatus.RECOVERED)

                # Log recovery event
                session.log_event("Session recovered from recovery point", {
                    "recovery_time": datetime.now().isoformat(),
                    "recovery_point_time": session.recovery_point.get("timestamp")
                })

                return True

            # Otherwise try to use checkpoints in custom data
            checkpoints = session.custom_data.get("checkpoints", [])
            if not checkpoints:
                logger.warning(
                    f"No checkpoints available for recovery of session {session.session_id}")
                return False

            # Get the latest checkpoint
            latest_checkpoint = max(
                checkpoints,
                key=lambda c: c.get("timestamp", "")
            )

            logger.info(
                f"Recovering session {session.session_id} using checkpoint: {latest_checkpoint.get('name')}"
            )

            # Update session state with checkpoint data
            checkpoint_state = latest_checkpoint.get("state", {})
            session.update_state(checkpoint_state)

            # Update session status
            session.set_status(SessionStatus.RECOVERED)

            # Log recovery event
            session.log_event("Session recovered from checkpoint", {
                "recovery_time": datetime.now().isoformat(),
                "checkpoint_name": latest_checkpoint.get("name"),
                "checkpoint_time": latest_checkpoint.get("timestamp")
            })

            return True

        except Exception as e:
            logger.error(
                f"Error recovering session {session.session_id} from checkpoint: {e}")
            return False


class StateBasedRecoveryStrategy(RecoveryStrategy):
    """Recovery strategy based on state history and analysis."""

    def can_recover(self, session: Session) -> bool:
        """
        Check if the session state has enough information for recovery.

        Args:
            session (Session): The session to evaluate

        Returns:
            bool: True if state contains recoverable information
        """
        # Check if we have state information
        if not session.state:
            return False

        # Check if we have crucial recovery information
        # This depends on the session type and operation being performed
        # Here we implement a basic check that can be extended

        # For member transfer sessions, we need source and destination info
        if session.session_type == "member_transfer":
            has_source = "source_group" in session.state
            has_destination = "destination_group" in session.state
            has_progress = "processed" in session.state and "total" in session.state

            return has_source and has_destination and has_progress

        # For more general cases, check for some progress indicator
        return "progress" in session.state or ("processed" in session.state and "total" in session.state)

    def recover(self, session: Session) -> bool:
        """
        Recover a session based on its last known state.

        Args:
            session (Session): The session to recover

        Returns:
            bool: True if recovery was successful
        """
        try:
            logger.info(
                f"Recovering session {session.session_id} based on state analysis")

            # Record original state for reference
            recovery_info = {
                "original_state": session.state.copy(),
                "recovery_time": datetime.now().isoformat()
            }

            # Reconstruct a valid state for resuming operations
            # This implementation will vary based on the session type

            # For member transfer sessions
            if session.session_type == "member_transfer":
                # Reset any in-progress flags to allow restart
                if "in_progress" in session.state:
                    session.state["in_progress"] = False

                # Ensure we have processed and total counters
                if "processed" not in session.state:
                    session.state["processed"] = 0

                if "total" not in session.state and "member_count" in session.state:
                    session.state["total"] = session.state["member_count"]

            # Update session status
            session.set_status(SessionStatus.RECOVERED)

            # Log recovery event
            session.log_event(
                "Session recovered from state analysis", recovery_info)

            return True

        except Exception as e:
            logger.error(
                f"Error recovering session {session.session_id} from state: {e}")
            return False


class SessionRecoveryManager:
    """
    Manager for session recovery operations.

    This class coordinates the detection and recovery of interrupted sessions.
    """

    def __init__(self, storage: Optional[SessionStorage] = None):
        """
        Initialize the recovery manager.

        Args:
            storage (SessionStorage, optional): Storage for session data.
                If None, uses the default storage.
        """
        self.storage = storage or default_storage
        self.recovery_strategies = [
            CheckpointRecoveryStrategy(),  # Try checkpoint recovery first
            StateBasedRecoveryStrategy()   # Fall back to state-based recovery
        ]

    def find_interrupted_sessions(self,
                                  max_age_hours: int = 24,
                                  session_types: Optional[List[str]] = None) -> List[str]:
        """
        Find sessions that were likely interrupted.

        Args:
            max_age_hours (int): Maximum age of sessions to consider (in hours)
            session_types (List[str], optional): Filter by session types

        Returns:
            List[str]: List of session IDs that appear to be interrupted
        """
        interrupted_sessions = []

        # List all session files
        session_files = self.storage.list_session_files()

        # Current time for age filtering
        now = datetime.now()

        for file_path in session_files:
            try:
                # Get session data
                with open(file_path, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)

                # Extract key information
                session_id = os.path.basename(file_path).replace(
                    "session_", "").replace(".json", "")
                status = session_data.get("status", "").lower()
                session_type = session_data.get("session_type")

                # Filter by interrupted status
                if status not in ["running", "paused", "interrupted"]:
                    continue

                # Filter by session type if specified
                if session_types and session_type not in session_types:
                    continue

                # Filter by age
                updated_str = session_data.get("updated_at")
                if not updated_str:
                    continue

                try:
                    updated_time = datetime.fromisoformat(updated_str)
                    age = now - updated_time

                    if age > timedelta(hours=max_age_hours):
                        continue
                except (ValueError, TypeError):
                    continue

                # This session appears to be interrupted
                interrupted_sessions.append(session_id)

            except Exception as e:
                logger.warning(f"Error checking session file {file_path}: {e}")

        logger.info(f"Found {len(interrupted_sessions)} interrupted sessions")
        return interrupted_sessions

    def analyze_session(self, session: Session) -> Dict[str, Any]:
        """
        Analyze a session to determine its recoverability.

        Args:
            session (Session): The session to analyze

        Returns:
            Dict[str, Any]: Analysis results including recoverability assessment
        """
        # Initialize analysis result
        analysis = {
            "session_id": session.session_id,
            "session_type": session.session_type,
            "current_status": SessionStatus.to_str(session.status),
            "last_updated": session.updated_at,
            "progress": session.progress,
            "recoverable": False,
            "recommended_strategy": None,
            "has_recovery_point": session.recovery_point is not None,
            "has_checkpoints": "checkpoints" in session.custom_data and len(session.custom_data["checkpoints"]) > 0,
            "has_state_history": len(session.state_history) > 0,
            "recovery_options": []
        }

        # Check each recovery strategy
        for strategy in self.recovery_strategies:
            strategy_name = strategy.__class__.__name__
            can_recover = strategy.can_recover(session)

            analysis["recovery_options"].append({
                "strategy": strategy_name,
                "can_recover": can_recover
            })

            # If strategy can recover and we haven't found a strategy yet
            if can_recover and not analysis["recommended_strategy"]:
                analysis["recommended_strategy"] = strategy_name
                analysis["recoverable"] = True

        return analysis

    def recover_session(self, session: Session) -> bool:
        """
        Attempt to recover an interrupted session.

        Args:
            session (Session): The session to recover

        Returns:
            bool: True if recovery was successful
        """
        logger.info(f"Attempting to recover session {session.session_id}")

        # If session is already in a completed state, no recovery needed
        if session.status in [SessionStatus.COMPLETED, SessionStatus.RECOVERED]:
            logger.info(
                f"Session {session.session_id} is already in {SessionStatus.to_str(session.status)} state, no recovery needed")
            return True

        # Update status to reflect we're working with an interrupted session
        if session.status != SessionStatus.INTERRUPTED:
            session.set_status(SessionStatus.INTERRUPTED)

        # Try each recovery strategy in order
        for strategy in self.recovery_strategies:
            strategy_name = strategy.__class__.__name__

            if strategy.can_recover(session):
                logger.info(f"Attempting recovery with {strategy_name}")

                if strategy.recover(session):
                    logger.info(
                        f"Successfully recovered session {session.session_id} with {strategy_name}")

                    # Save the recovered session
                    self.storage.save_session(session)

                    return True
                else:
                    logger.warning(
                        f"Recovery with {strategy_name} failed for session {session.session_id}")

        logger.error(
            f"All recovery strategies failed for session {session.session_id}")
        return False

    def recover_sessions(self, session_ids: List[str]) -> Dict[str, bool]:
        """
        Attempt to recover multiple sessions.

        Args:
            session_ids (List[str]): List of session IDs to recover

        Returns:
            Dict[str, bool]: Dictionary mapping session IDs to recovery status
        """
        results = {}

        for session_id in session_ids:
            try:
                # Load session data
                session_data = self.storage.load_session(session_id)

                if not session_data:
                    logger.warning(
                        f"Could not load data for session {session_id}")
                    results[session_id] = False
                    continue

                # Create session object
                from session import Session
                session = Session.from_dict(session_data)

                # Attempt recovery
                result = self.recover_session(session)
                results[session_id] = result

            except Exception as e:
                logger.error(
                    f"Error during recovery of session {session_id}: {e}")
                results[session_id] = False

        # Log summary
        success_count = sum(1 for result in results.values() if result)
        logger.info(
            f"Recovered {success_count} out of {len(session_ids)} sessions")

        return results

    def create_checkpoint(self, session: Session, name: str) -> bool:
        """
        Create a named checkpoint for a session.

        Args:
            session (Session): The session to checkpoint
            name (str): Name for the checkpoint

        Returns:
            bool: True if checkpoint was created successfully
        """
        try:
            # Add checkpoint to session
            session.add_state_checkpoint(name)

            # Save the session to persist the checkpoint
            return self.storage.save_session(session)

        except Exception as e:
            logger.error(
                f"Error creating checkpoint for session {session.session_id}: {e}")
            return False

    def set_recovery_point(self, session: Session, data: Dict[str, Any]) -> bool:
        """
        Set a recovery point for a session.

        Args:
            session (Session): The session to update
            data (Dict[str, Any]): Recovery data

        Returns:
            bool: True if recovery point was set successfully
        """
        try:
            # Set recovery point
            session.set_recovery_point(data)

            # Save the session to persist the recovery point
            return self.storage.save_session(session)

        except Exception as e:
            logger.error(
                f"Error setting recovery point for session {session.session_id}: {e}")
            return False

    def generate_recovery_report(self, session_ids: List[str]) -> Dict[str, Any]:
        """
        Generate a report on the recoverability of multiple sessions.

        Args:
            session_ids (List[str]): List of session IDs to analyze

        Returns:
            Dict[str, Any]: Recovery report
        """
        report = {
            "total_sessions": len(session_ids),
            "recoverable_sessions": 0,
            "unrecoverable_sessions": 0,
            "analysis_time": datetime.now().isoformat(),
            "sessions": []
        }

        for session_id in session_ids:
            try:
                # Load session data
                session_data = self.storage.load_session(session_id)

                if not session_data:
                    session_report = {
                        "session_id": session_id,
                        "status": "error",
                        "error": "Could not load session data",
                        "recoverable": False
                    }
                else:
                    # Create session object
                    from session import Session
                    session = Session.from_dict(session_data)

                    # Analyze session
                    analysis = self.analyze_session(session)

                    # Create session report
                    session_report = {
                        "session_id": session_id,
                        "status": analysis["current_status"],
                        "last_updated": analysis["last_updated"],
                        "progress": analysis["progress"],
                        "recoverable": analysis["recoverable"],
                        "recommended_strategy": analysis["recommended_strategy"]
                    }

                    # Update counters
                    if analysis["recoverable"]:
                        report["recoverable_sessions"] += 1
                    else:
                        report["unrecoverable_sessions"] += 1

                # Add to sessions list
                report["sessions"].append(session_report)

            except Exception as e:
                # Handle errors
                logger.error(f"Error analyzing session {session_id}: {e}")
                report["sessions"].append({
                    "session_id": session_id,
                    "status": "error",
                    "error": str(e),
                    "recoverable": False
                })
                report["unrecoverable_sessions"] += 1

        return report


# Create a default recovery manager instance
default_recovery_manager = SessionRecoveryManager()

# Helper functions for common operations


def find_interrupted_sessions(max_age_hours: int = 24) -> List[str]:
    """
    Find interrupted sessions using the default recovery manager.

    Args:
        max_age_hours (int): Maximum age of sessions to consider

    Returns:
        List[str]: List of interrupted session IDs
    """
    return default_recovery_manager.find_interrupted_sessions(max_age_hours)


def recover_session(session: Session) -> bool:
    """
    Recover a session using the default recovery manager.

    Args:
        session (Session): Session to recover

    Returns:
        bool: True if recovery was successful
    """
    return default_recovery_manager.recover_session(session)


def create_checkpoint(session: Session, name: str) -> bool:
    """
    Create a checkpoint for a session.

    Args:
        session (Session): Session to checkpoint
        name (str): Checkpoint name

    Returns:
        bool: True if successful
    """
    return default_recovery_manager.create_checkpoint(session, name)
