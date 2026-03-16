from abc import ABC, abstractmethod

import numpy as np


class BaseEnvironment(ABC):
    """Abstract base class for PyBullet evaluation environments."""

    @abstractmethod
    def reset(self, config: dict | None = None) -> np.ndarray:
        """Reset the environment and return initial observation."""

    @abstractmethod
    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, dict]:
        """Execute action, return (obs, reward, done, info)."""

    @abstractmethod
    def get_observation(self) -> np.ndarray:
        """Get current observation."""

    @abstractmethod
    def get_success(self) -> bool:
        """Check if task is successfully completed."""

    @abstractmethod
    def close(self):
        """Clean up resources."""

    @property
    @abstractmethod
    def max_steps(self) -> int:
        """Maximum steps per episode."""

    @property
    @abstractmethod
    def action_dim(self) -> int:
        """Dimension of the action space."""

    @property
    @abstractmethod
    def observation_dim(self) -> int:
        """Dimension of the observation space."""
