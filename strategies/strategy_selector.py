"""
Strategy Selector Module

This module provides functionality for selecting appropriate operation strategies
based on various conditions such as account availability, user preferences, and
system resources. It follows the Factory pattern to create and return strategy
instances based on the given context.

The module implements:
1. A StrategySelector class for selecting strategies based on conditions
2. A StrategyFactory for creating strategy instances
3. Context-based decision making for optimal strategy selection

Usage:
    from strategies.strategy_selector import StrategySelector

    # Create a selector
    selector = StrategySelector()

    # Get a strategy based on available accounts and user preferences
    strategy = selector.select_strategy(
        available_accounts=5,
        preferred_strategy='parallel',
        parallel_level='medium'
    )

    # Or get a strategy automatically based on context
    strategy = selector.select_optimal_strategy(
        available_accounts=5,
        target_count=100,
        system_resources=system_resource_info
    )
"""

import logging
from typing import Dict, List, Optional, Any

# Import strategy classes
try:
    from strategies.base_strategy import BaseStrategy
    from strategies.sequential_strategy import SequentialStrategy
    from strategies.parallel_strategies import (
        ParallelLowStrategy,
        ParallelMediumStrategy,
        ParallelHighStrategy
    )
except ImportError:
    # For development, define placeholder classes if not available
    class BaseStrategy:
        """Placeholder for BaseStrategy."""
        pass

    class SequentialStrategy(BaseStrategy):
        """Placeholder for SequentialStrategy."""
        pass

    class ParallelLowStrategy(BaseStrategy):
        """Placeholder for ParallelLowStrategy."""
        pass

    class ParallelMediumStrategy(BaseStrategy):
        """Placeholder for ParallelMediumStrategy."""
        pass

    class ParallelHighStrategy(BaseStrategy):
        """Placeholder for ParallelHighStrategy."""
        pass

# Import custom exceptions
try:
    from core.exceptions import StrategyNotFoundError, StrategyExecutionError
except ImportError:
    # Define placeholder exceptions if not available
    class StrategyNotFoundError(Exception):
        """Raised when a requested strategy is not found."""
        pass

    class StrategyExecutionError(Exception):
        """Raised when strategy execution fails."""
        pass

# Setup logger
logger = logging.getLogger("StrategySelector")


class StrategyFactory:
    """
    Factory class for creating strategy instances.

    This class is responsible for creating and returning appropriate strategy
    instances based on strategy type and configuration parameters.
    """

    @classmethod
    def create_strategy(cls, strategy_type: str, config: Dict[str, Any]) -> BaseStrategy:
        """
        Create and return a strategy of the specified type.

        Args:
            strategy_type (str): Type of strategy to create ('sequential',
                                'parallel_low', 'parallel_medium', 'parallel_high')
            config (Dict[str, Any]): Configuration parameters for the strategy

        Returns:
            BaseStrategy: Instance of the requested strategy

        Raises:
            StrategyNotFoundError: If the requested strategy is not supported
        """
        # Map strategy types to strategy classes
        strategy_map = {
            'sequential': SequentialStrategy,
            'parallel_low': ParallelLowStrategy,
            'parallel_medium': ParallelMediumStrategy,
            'parallel_high': ParallelHighStrategy
        }

        # Check if the requested strategy type is supported
        if strategy_type not in strategy_map:
            logger.error("Strategy '%s' not found", strategy_type)
            raise StrategyNotFoundError(
                f"Strategy '{strategy_type}' not found")

        # Get the strategy class
        strategy_class = strategy_map[strategy_type]

        try:
            # Create and return an instance of the strategy
            logger.debug("Creating strategy: %s", strategy_type)
            return strategy_class(**config)
        except Exception as e:
            logger.error("Failed to create strategy '%s': %s",
                         strategy_type, e)
            raise StrategyExecutionError(
                f"Failed to create strategy '{strategy_type}': {e}")


class ParallelLevel:
    """Constants for parallel strategy levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StrategyType:
    """Constants for strategy types."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class StrategySelector:
    """
    Selector class for choosing appropriate strategies based on conditions.

    This class provides methods for selecting strategies based on various factors
    such as available accounts, user preferences, and system resources.
    """

    def __init__(self):
        """Initialize the StrategySelector."""
        self.factory = StrategyFactory()
        logger.debug("StrategySelector initialized")

    def select_strategy(self,
                        available_accounts: int,
                        preferred_strategy: str = StrategyType.SEQUENTIAL,
                        parallel_level: str = ParallelLevel.LOW,
                        **kwargs) -> BaseStrategy:
        """
        Select a strategy based on available accounts and user preferences.

        Args:
            available_accounts (int): Number of available accounts
            preferred_strategy (str): Preferred strategy type ('sequential' or 'parallel')
            parallel_level (str): Level of parallelism ('low', 'medium', 'high')
                                 Only used if preferred_strategy is 'parallel'
            **kwargs: Additional configuration parameters for the strategy

        Returns:
            BaseStrategy: The selected strategy instance

        Raises:
            StrategyNotFoundError: If the requested strategy is not supported
            StrategyExecutionError: If the strategy creation fails
        """
        # Validate inputs
        if available_accounts <= 0:
            logger.warning(
                "No available accounts, defaulting to sequential strategy")
            return self.factory.create_strategy(StrategyType.SEQUENTIAL, kwargs)

        # Normalize strategy type
        preferred_strategy = preferred_strategy.lower()

        # Determine the strategy type based on preferences and constraints
        if preferred_strategy == StrategyType.SEQUENTIAL:
            strategy_type = StrategyType.SEQUENTIAL
        elif preferred_strategy == StrategyType.PARALLEL:
            # Normalize parallel level
            parallel_level = parallel_level.lower()

            # Select parallel strategy based on level and available accounts
            if parallel_level == ParallelLevel.LOW and available_accounts >= 2:
                strategy_type = 'parallel_low'
            elif parallel_level == ParallelLevel.MEDIUM and available_accounts >= 4:
                strategy_type = 'parallel_medium'
            elif parallel_level == ParallelLevel.HIGH and available_accounts >= 7:
                strategy_type = 'parallel_high'
            else:
                # Default to lowest viable parallel level or sequential
                if available_accounts >= 2:
                    strategy_type = 'parallel_low'
                else:
                    logger.info(
                        "Insufficient accounts for parallel strategy, using sequential")
                    strategy_type = StrategyType.SEQUENTIAL
        else:
            # Default to sequential if strategy type is not recognized
            logger.warning(
                "Unrecognized strategy type: %s, defaulting to sequential",
                preferred_strategy
            )
            strategy_type = StrategyType.SEQUENTIAL

        # Create and return the strategy
        logger.info(
            "Selected strategy: %s (available accounts: %s)",
            strategy_type,
            available_accounts
        )
        return self.factory.create_strategy(strategy_type, kwargs)

    def select_optimal_strategy(self,
                                available_accounts: int,
                                target_count: int,
                                system_resources: Optional[Dict[str, Any]] = None,
                                **kwargs) -> BaseStrategy:
        """
        Automatically select the optimal strategy based on context.

        This method analyzes the current context including the number of available
        accounts, the target member count, and system resources to select the most
        appropriate strategy.

        Args:
            available_accounts (int): Number of available accounts
            target_count (int): Number of members to add/extract
            system_resources (Dict[str, Any], optional): System resource info
                                                       (CPU, memory, network)
            **kwargs: Additional configuration parameters for the strategy

        Returns:
            BaseStrategy: The optimal strategy instance

        Raises:
            StrategyNotFoundError: If the requested strategy is not supported
            StrategyExecutionError: If the strategy creation fails
        """
        # Default system resources if not provided
        if system_resources is None:
            system_resources = {
                'cpu_cores': 2,  # Default to 2 CPU cores
                'available_memory': 1024,  # 1GB in MB
                'network_speed': 1  # 1 Mbps
            }

        # Determine optimal strategy based on accounts, target and resources
        if available_accounts <= 1:
            # Only one account available, use sequential
            strategy_type = StrategyType.SEQUENTIAL
            parallel_level = None
        else:
            # Multiple accounts available, determine parallelism level

            # First check if we even need parallelism (small target count)
            if target_count <= 20:
                # Small operation, sequential is often more efficient
                strategy_type = StrategyType.SEQUENTIAL
                parallel_level = None
            else:
                # Determine parallel level based on accounts, target size, and resources
                strategy_type = StrategyType.PARALLEL

                # Calculate a resource score (simplified version)
                cpu_score = min(system_resources.get(
                    'cpu_cores', 2) / 2, 3)  # 0.5 to 3
                memory_score = min(system_resources.get(
                    'available_memory', 1024) / 1024, 2)  # 0.5 to 2
                network_score = min(system_resources.get(
                    'network_speed', 1) / 5, 1)  # 0.2 to 1

                resource_score = (cpu_score + memory_score + network_score) / 3

                # Determine level based on accounts and resources
                if available_accounts >= 7 and resource_score >= 2.0:
                    parallel_level = ParallelLevel.HIGH
                elif available_accounts >= 4 and resource_score >= 1.0:
                    parallel_level = ParallelLevel.MEDIUM
                else:
                    parallel_level = ParallelLevel.LOW

        # Log the decision factors and selected strategy
        logger.info(
            "Optimal strategy selection based on: accounts=%s, target=%s, resources=%s",
            available_accounts,
            target_count,
            system_resources
        )

        # Select the strategy with the determined parameters
        return self.select_strategy(
            available_accounts=available_accounts,
            preferred_strategy=strategy_type,
            parallel_level=parallel_level if parallel_level else ParallelLevel.LOW,
            **kwargs
        )

    def list_available_strategies(self) -> List[str]:
        """
        List all available strategy types.

        Returns:
            List[str]: List of available strategy type names
        """
        return [
            StrategyType.SEQUENTIAL,
            f"{StrategyType.PARALLEL} ({ParallelLevel.LOW})",
            f"{StrategyType.PARALLEL} ({ParallelLevel.MEDIUM})",
            f"{StrategyType.PARALLEL} ({ParallelLevel.HIGH})"
        ]

    @staticmethod
    def get_strategy_description(strategy_type: str) -> str:
        """
        Get a description of the specified strategy type.

        Args:
            strategy_type (str): Strategy type to describe

        Returns:
            str: Description of the strategy

        Raises:
            StrategyNotFoundError: If the strategy type is not recognized
        """
        descriptions = {
            StrategyType.SEQUENTIAL: "Sequential strategy: Uses one account at a time, "
            "minimizing risk of detection but potentially slower.",

            f"{StrategyType.PARALLEL} ({ParallelLevel.LOW})":
            "Low parallel strategy: Uses 2-3 accounts "
            "simultaneously, balancing speed and safety.",

            f"{StrategyType.PARALLEL} ({ParallelLevel.MEDIUM})":
            "Medium parallel strategy: Uses 4-6 accounts "
            "simultaneously, emphasizing speed with "
            "moderate safety measures.",

            f"{StrategyType.PARALLEL} ({ParallelLevel.HIGH})":
            "High parallel strategy: Uses 7+ accounts "
            "simultaneously, maximizing speed but with "
            "increased risk of detection."
        }

        # Handle specific parallel types
        if strategy_type == 'parallel_low':
            strategy_type = f"{StrategyType.PARALLEL} ({ParallelLevel.LOW})"
        elif strategy_type == 'parallel_medium':
            strategy_type = f"{StrategyType.PARALLEL} ({ParallelLevel.MEDIUM})"
        elif strategy_type == 'parallel_high':
            strategy_type = f"{StrategyType.PARALLEL} ({ParallelLevel.HIGH})"

        if strategy_type not in descriptions:
            logger.error("Strategy description not found: %s", strategy_type)
            raise StrategyNotFoundError(
                f"Strategy '{strategy_type}' not found")

        return descriptions[strategy_type]


# Helper function to get a StrategySelector instance
def get_strategy_selector() -> StrategySelector:
    """
    Get a StrategySelector instance.

    Returns:
        StrategySelector: A new StrategySelector instance
    """
    return StrategySelector()
