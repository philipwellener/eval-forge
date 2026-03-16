"""Example random policy for testing EvalForge."""

import numpy as np


class RandomPolicy:
    """Outputs uniform random actions. Useful as a baseline."""

    def __init__(self, action_dim: int):
        self.action_dim = action_dim

    def predict(self, observation: np.ndarray) -> np.ndarray:
        return np.random.uniform(-1.0, 1.0, size=self.action_dim)
