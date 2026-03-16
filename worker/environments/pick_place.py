import numpy as np
import pybullet as p
import pybullet_data

from worker.environments.base import BaseEnvironment


class PickPlaceEnv(BaseEnvironment):
    """Panda arm picks a cube and places it at a target location."""

    def __init__(self):
        self._physics_client = None
        self._panda_id = None
        self._cube_id = None
        self._target_pos = None
        self._step_count = 0
        self._ee_link = 11
        self._finger_joints = [9, 10]
        self._success_threshold = 0.12
        self._grasp_threshold = 0.02

    @property
    def max_steps(self) -> int:
        return 500

    @property
    def action_dim(self) -> int:
        return 8  # 7 joint velocities + 1 gripper

    @property
    def observation_dim(self) -> int:
        return 19  # 7 joint + 3 ee + 3 cube + 3 target + 1 gripper_state + 2 finger

    def reset(self, config: dict | None = None) -> np.ndarray:
        if self._physics_client is not None:
            p.disconnect(self._physics_client)

        self._physics_client = p.connect(p.DIRECT)
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self._physics_client)
        p.setGravity(0, 0, -9.81, physicsClientId=self._physics_client)
        p.setTimeStep(1.0 / 240, physicsClientId=self._physics_client)

        p.loadURDF("plane.urdf", physicsClientId=self._physics_client)
        # Load table
        p.loadURDF(
            "table/table.urdf",
            basePosition=[0.5, 0, 0],
            physicsClientId=self._physics_client,
        )

        self._panda_id = p.loadURDF(
            "franka_panda/panda.urdf",
            basePosition=[0, 0, 0],
            useFixedBase=True,
            physicsClientId=self._physics_client,
        )

        home = [0, -0.785, 0, -2.356, 0, 1.571, 0.785, 0.04, 0.04]
        for i, val in enumerate(home):
            p.resetJointState(self._panda_id, i, val, physicsClientId=self._physics_client)

        cfg = config or {}
        cube_pos = cfg.get("cube_pos", [
            np.random.uniform(0.4, 0.6),
            np.random.uniform(-0.2, 0.2),
            0.625,  # table height
        ])

        self._cube_id = p.loadURDF(
            "cube_small.urdf",
            basePosition=cube_pos,
            physicsClientId=self._physics_client,
        )

        self._target_pos = np.array(cfg.get("target", [
            np.random.uniform(0.4, 0.6),
            np.random.uniform(-0.2, 0.2),
            0.625,
        ]))

        # Let things settle
        for _ in range(50):
            p.stepSimulation(physicsClientId=self._physics_client)

        self._step_count = 0
        return self.get_observation()

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, dict]:
        action = np.clip(action[:8], -1.0, 1.0)

        # Arm joints
        for i in range(7):
            p.setJointMotorControl2(
                self._panda_id, i,
                controlMode=p.VELOCITY_CONTROL,
                targetVelocity=float(action[i]),
                force=87,
                physicsClientId=self._physics_client,
            )

        # Gripper
        gripper_vel = float(action[7]) * 0.05
        for j in self._finger_joints:
            p.setJointMotorControl2(
                self._panda_id, j,
                controlMode=p.VELOCITY_CONTROL,
                targetVelocity=gripper_vel,
                force=20,
                physicsClientId=self._physics_client,
            )

        p.stepSimulation(physicsClientId=self._physics_client)
        self._step_count += 1

        obs = self.get_observation()
        cube_pos = obs[10:13]
        dist = np.linalg.norm(cube_pos - self._target_pos)
        reward = -dist
        done = self.get_success() or self._step_count >= self.max_steps

        return obs, reward, done, {"cube_target_distance": dist}

    def get_observation(self) -> np.ndarray:
        joint_states = p.getJointStates(self._panda_id, range(7), physicsClientId=self._physics_client)
        joint_pos = np.array([s[0] for s in joint_states])

        ee_state = p.getLinkState(self._panda_id, self._ee_link, physicsClientId=self._physics_client)
        ee_pos = np.array(ee_state[0])

        cube_pos, _ = p.getBasePositionAndOrientation(self._cube_id, physicsClientId=self._physics_client)
        cube_pos = np.array(cube_pos)

        finger_states = p.getJointStates(self._panda_id, self._finger_joints, physicsClientId=self._physics_client)
        finger_pos = np.array([s[0] for s in finger_states])
        gripper_open = np.array([finger_pos.sum()])

        return np.concatenate([joint_pos, ee_pos, cube_pos, self._target_pos, gripper_open, finger_pos])

    def get_success(self) -> bool:
        cube_pos, _ = p.getBasePositionAndOrientation(self._cube_id, physicsClientId=self._physics_client)
        return float(np.linalg.norm(np.array(cube_pos) - self._target_pos)) < self._success_threshold

    def close(self):
        if self._physics_client is not None:
            p.disconnect(self._physics_client)
            self._physics_client = None
