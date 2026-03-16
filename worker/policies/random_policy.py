import numpy as np


class RandomPolicy:
    """Random policy for testing. Outputs uniform random actions."""

    def __init__(self, action_dim: int):
        self.action_dim = action_dim

    def predict(self, observation: np.ndarray) -> np.ndarray:
        return np.random.uniform(-1.0, 1.0, size=self.action_dim)
