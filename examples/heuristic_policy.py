"""Heuristic policy using PyBullet IK to move toward the target.

Spins up its own headless PyBullet instance for IK calculations.
Works with all 3 environments.
"""

import numpy as np
import pybullet as p
import pybullet_data


class HeuristicPolicy:
    def __init__(self, action_dim: int):
        self.action_dim = action_dim
        self._ik_client = p.connect(p.DIRECT)
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self._ik_client)
        self._panda = p.loadURDF(
            "franka_panda/panda.urdf",
            basePosition=[0, 0, 0],
            useFixedBase=True,
            physicsClientId=self._ik_client,
        )
        self._ee_link = 11
        self._phase = "approach"
        self._grasp_counter = 0
        self._gain = 8.0

    def _ik_velocity(self, joint_pos: np.ndarray, target_pos: np.ndarray) -> np.ndarray:
        """Compute joint velocities to move ee toward target using IK."""
        # Sync IK robot to current joint state
        for i in range(7):
            p.resetJointState(self._panda, i, float(joint_pos[i]),
                              physicsClientId=self._ik_client)

        # Compute IK for target
        target_joints = p.calculateInverseKinematics(
            self._panda, self._ee_link, target_pos.tolist(),
            maxNumIterations=50,
            residualThreshold=1e-4,
            physicsClientId=self._ik_client,
        )

        # Proportional control: velocity = gain * (target_joint - current_joint)
        velocities = np.zeros(7)
        for i in range(7):
            velocities[i] = self._gain * (target_joints[i] - joint_pos[i])

        return np.clip(velocities, -1.0, 1.0)

    def predict(self, observation: np.ndarray) -> np.ndarray:
        obs = np.array(observation, dtype=np.float64)
        action = np.zeros(self.action_dim)

        joint_pos = obs[:7]
        ee_pos = obs[7:10]

        if self.action_dim == 7:
            # Reach: move directly to target
            target = obs[10:13]
            return self._ik_velocity(joint_pos, target)

        # Pick-place or cluttered (action_dim == 8)
        obj_pos = obs[10:13]
        place_target = obs[13:16]

        if self._phase == "approach":
            above = obj_pos.copy()
            above[2] += 0.08
            action[:7] = self._ik_velocity(joint_pos, above)
            action[7] = 1.0  # open gripper

            if np.linalg.norm(ee_pos - above) < 0.03:
                self._phase = "descend"

        elif self._phase == "descend":
            action[:7] = self._ik_velocity(joint_pos, obj_pos)
            action[7] = 1.0

            if np.linalg.norm(ee_pos - obj_pos) < 0.02:
                self._phase = "grasp"
                self._grasp_counter = 0

        elif self._phase == "grasp":
            action[:7] = 0.0
            action[7] = -1.0
            self._grasp_counter += 1
            if self._grasp_counter > 40:
                self._phase = "lift"

        elif self._phase == "lift":
            lift = ee_pos.copy()
            lift[2] = 0.8
            action[:7] = self._ik_velocity(joint_pos, lift)
            action[7] = -1.0

            if ee_pos[2] > 0.7:
                self._phase = "place"

        elif self._phase == "place":
            above_target = place_target.copy()
            above_target[2] += 0.05
            action[:7] = self._ik_velocity(joint_pos, above_target)
            action[7] = -1.0

            if np.linalg.norm(ee_pos[:2] - place_target[:2]) < 0.04:
                action[7] = 1.0  # release

        return np.clip(action, -1.0, 1.0)
