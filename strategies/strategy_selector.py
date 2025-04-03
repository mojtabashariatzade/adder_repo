"""
Simplified Strategy Selector Module

This module provides a simplified selector for the Distributed Cautious Strategy.
All other strategies have been removed for simplicity.
"""

import logging
from typing import Dict, List, Optional, Any

# Import only the strategy we need
from strategies.distributed_cautious_strategy import DistributedCautiousStrategy
from strategies.base_strategy import BaseStrategy

# Setup logger
logger = logging.getLogger("StrategySelector")


class StrategySelector:
    """
    Simplified selector class that only uses the Distributed Cautious Strategy.
    """

    def __init__(self):
        """Initialize the StrategySelector."""
        logger.debug("Simplified StrategySelector initialized")

    def select_strategy(self, **kwargs) -> BaseStrategy:
        """
        Always returns a Distributed Cautious Strategy instance.

        Args:
            **kwargs: Configuration parameters for the strategy

        Returns:
            BaseStrategy: A Distributed Cautious Strategy instance
        """
        logger.info("Using Distributed Cautious Strategy")
        return DistributedCautiousStrategy(**kwargs)

    def select_optimal_strategy(self, **kwargs) -> BaseStrategy:
        """
        Always returns a Distributed Cautious Strategy instance.

        Args:
            **kwargs: Configuration parameters for the strategy

        Returns:
            BaseStrategy: A Distributed Cautious Strategy instance
        """
        logger.info("Using Distributed Cautious Strategy (optimal selection)")
        return DistributedCautiousStrategy(**kwargs)

    def list_available_strategies(self) -> List[str]:
        """
        List all available strategy types.

        Returns:
            List[str]: List containing only "distributed_cautious"
        """
        return ["distributed_cautious"]

    def get_strategy_description(self, strategy_type: str) -> str:
        """
        Get a description of the specified strategy type.

        Args:
            strategy_type (str): Strategy type to describe

        Returns:
            str: Description of the Distributed Cautious Strategy
        """
        return ("Distributed Cautious strategy: Works 24/7 and distributes load across "
                "multiple accounts while maintaining a cautious approach to avoid restrictions.")

# Helper function to get a StrategySelector instance


def get_strategy_selector() -> StrategySelector:
    """
    Get a StrategySelector instance.

    Returns:
        StrategySelector: A new StrategySelector instance
    """
    return StrategySelector()
