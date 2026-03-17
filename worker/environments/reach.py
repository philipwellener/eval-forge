import numpy as np
import pybullet as p
import pybullet_data

from worker.environments.base import BaseEnvironment


class ReachEnv(BaseEnvironment):
    """Panda arm reaches a target point in 3D space."""

    def __init__(self):
        self._physics_client = None
        self._panda_id = None
        self._target_pos = None
        self._step_count = 0
        self._ee_link = 11  # Panda end-effector link index
        self._success_threshold = 0.05

    @property
    def max_steps(self) -> int:
        return 200

    @property
    def action_dim(self) -> int:
        return 7  # 7 joint velocities

    @property
    def observation_dim(self) -> int:
        return 13  # 7 joint pos + 3 ee pos + 3 target pos

    def reset(self, config: dict | None = None) -> np.ndarray:
        if self._physics_client is not None:
            p.disconnect(self._physics_client)

        self._physics_client = p.connect(p.DIRECT)
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self._physics_client)
        p.setGravity(0, 0, -9.81, physicsClientId=self._physics_client)

        p.loadURDF("plane.urdf", physicsClientId=self._physics_client)
        self._panda_id = p.loadURDF(
            "franka_panda/panda.urdf",
            basePosition=[0, 0, 0],
            useFixedBase=True,
            physicsClientId=self._physics_client,
        )

        # Reset joints to home position
        home = [0, -0.785, 0, -2.356, 0, 1.571, 0.785, 0.04, 0.04]
        for i, val in enumerate(home):
            p.resetJointState(self._panda_id, i, val, physicsClientId=self._physics_client)

        # Random target within reach
        cfg = config or {}
        self._target_pos = np.array(
            cfg.get(
                "target",
                [
                    np.random.uniform(0.3, 0.7),
                    np.random.uniform(-0.4, 0.4),
                    np.random.uniform(0.2, 0.6),
                ],
            )
        )

        self._step_count = 0
        return self.get_observation()

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, dict]:
        action = np.clip(action[:7], -1.0, 1.0)

        for i in range(7):
            p.setJointMotorControl2(
                self._panda_id,
                i,
                controlMode=p.VELOCITY_CONTROL,
                targetVelocity=float(action[i]),
                force=87,
                physicsClientId=self._physics_client,
            )

        p.stepSimulation(physicsClientId=self._physics_client)
        self._step_count += 1

        obs = self.get_observation()
        ee_pos = obs[7:10]
        dist = np.linalg.norm(ee_pos - self._target_pos)
        reward = -dist
        done = self.get_success() or self._step_count >= self.max_steps

        return obs, reward, done, {"distance": dist}

    def get_observation(self) -> np.ndarray:
        joint_states = p.getJointStates(
            self._panda_id, range(7), physicsClientId=self._physics_client
        )
        joint_pos = np.array([s[0] for s in joint_states])

        ee_state = p.getLinkState(
            self._panda_id, self._ee_link, physicsClientId=self._physics_client
        )
        ee_pos = np.array(ee_state[0])

        return np.concatenate([joint_pos, ee_pos, self._target_pos])

    def get_success(self) -> bool:
        ee_state = p.getLinkState(
            self._panda_id, self._ee_link, physicsClientId=self._physics_client
        )
        ee_pos = np.array(ee_state[0])
        return float(np.linalg.norm(ee_pos - self._target_pos)) < self._success_threshold

    def close(self):
        if self._physics_client is not None:
            p.disconnect(self._physics_client)
            self._physics_client = None
