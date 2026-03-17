import numpy as np
import pybullet as p
import pybullet_data

from worker.environments.base import BaseEnvironment


class ClutteredPickEnv(BaseEnvironment):
    """Panda picks an object from a cluttered scene with obstacles. Tracks collisions."""

    def __init__(self):
        self._physics_client = None
        self._panda_id = None
        self._target_obj_id = None
        self._obstacle_ids = []
        self._target_pos = None
        self._step_count = 0
        self._collision_count = 0
        self._ee_link = 11
        self._finger_joints = [9, 10]
        self._success_threshold = 0.12
        self._num_obstacles = 4

    @property
    def max_steps(self) -> int:
        return 500

    @property
    def action_dim(self) -> int:
        return 8

    @property
    def observation_dim(self) -> int:
        return 22  # 7 joint + 3 ee + 3 target_obj + 3 place_target + 2 finger + 4 nearest_obstacle

    def reset(self, config: dict | None = None) -> np.ndarray:
        if self._physics_client is not None:
            p.disconnect(self._physics_client)

        self._physics_client = p.connect(p.DIRECT)
        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self._physics_client)
        p.setGravity(0, 0, -9.81, physicsClientId=self._physics_client)
        p.setTimeStep(1.0 / 240, physicsClientId=self._physics_client)

        p.loadURDF("plane.urdf", physicsClientId=self._physics_client)
        p.loadURDF(
            "table/table.urdf", basePosition=[0.5, 0, 0], physicsClientId=self._physics_client
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
        table_h = 0.625

        # Target object
        target_pos = cfg.get(
            "target_obj_pos",
            [
                np.random.uniform(0.35, 0.65),
                np.random.uniform(-0.15, 0.15),
                table_h,
            ],
        )
        self._target_obj_id = p.loadURDF(
            "cube_small.urdf",
            basePosition=target_pos,
            physicsClientId=self._physics_client,
        )
        # Color target red
        p.changeVisualShape(
            self._target_obj_id, -1, rgbaColor=[1, 0, 0, 1], physicsClientId=self._physics_client
        )

        # Place target
        self._target_pos = np.array(
            cfg.get(
                "place_target",
                [
                    np.random.uniform(0.35, 0.65),
                    np.random.uniform(-0.3, 0.3),
                    table_h,
                ],
            )
        )

        # Obstacles
        self._obstacle_ids = []
        for i in range(self._num_obstacles):
            ox = np.random.uniform(0.3, 0.7)
            oy = np.random.uniform(-0.25, 0.25)
            # Avoid placing on top of target
            while abs(ox - target_pos[0]) < 0.08 and abs(oy - target_pos[1]) < 0.08:
                ox = np.random.uniform(0.3, 0.7)
                oy = np.random.uniform(-0.25, 0.25)

            obs_id = p.loadURDF(
                "cube_small.urdf",
                basePosition=[ox, oy, table_h],
                physicsClientId=self._physics_client,
            )
            p.changeVisualShape(
                obs_id, -1, rgbaColor=[0.5, 0.5, 0.5, 1], physicsClientId=self._physics_client
            )
            self._obstacle_ids.append(obs_id)

        for _ in range(50):
            p.stepSimulation(physicsClientId=self._physics_client)

        self._step_count = 0
        self._collision_count = 0
        return self.get_observation()

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, dict]:
        action = np.clip(action[:8], -1.0, 1.0)

        for i in range(7):
            p.setJointMotorControl2(
                self._panda_id,
                i,
                controlMode=p.VELOCITY_CONTROL,
                targetVelocity=float(action[i]),
                force=87,
                physicsClientId=self._physics_client,
            )

        gripper_vel = float(action[7]) * 0.05
        for j in self._finger_joints:
            p.setJointMotorControl2(
                self._panda_id,
                j,
                controlMode=p.VELOCITY_CONTROL,
                targetVelocity=gripper_vel,
                force=20,
                physicsClientId=self._physics_client,
            )

        p.stepSimulation(physicsClientId=self._physics_client)
        self._step_count += 1

        # Check collisions with obstacles
        for obs_id in self._obstacle_ids:
            contacts = p.getContactPoints(
                bodyA=self._panda_id,
                bodyB=obs_id,
                physicsClientId=self._physics_client,
            )
            if contacts:
                self._collision_count += 1

        obs = self.get_observation()
        target_obj_pos, _ = p.getBasePositionAndOrientation(
            self._target_obj_id, physicsClientId=self._physics_client
        )
        dist = np.linalg.norm(np.array(target_obj_pos) - self._target_pos)
        collision_penalty = -0.1 * (self._collision_count > 0)
        reward = -dist + collision_penalty
        done = self.get_success() or self._step_count >= self.max_steps

        return (
            obs,
            reward,
            done,
            {
                "distance": dist,
                "collisions": self._collision_count,
            },
        )

    def get_observation(self) -> np.ndarray:
        joint_states = p.getJointStates(
            self._panda_id, range(7), physicsClientId=self._physics_client
        )
        joint_pos = np.array([s[0] for s in joint_states])

        ee_state = p.getLinkState(
            self._panda_id, self._ee_link, physicsClientId=self._physics_client
        )
        ee_pos = np.array(ee_state[0])

        target_obj_pos, _ = p.getBasePositionAndOrientation(
            self._target_obj_id, physicsClientId=self._physics_client
        )
        target_obj_pos = np.array(target_obj_pos)

        finger_states = p.getJointStates(
            self._panda_id, self._finger_joints, physicsClientId=self._physics_client
        )
        finger_pos = np.array([s[0] for s in finger_states])

        # Nearest obstacle distance (from ee)
        min_dists = []
        for obs_id in self._obstacle_ids:
            obs_pos, _ = p.getBasePositionAndOrientation(
                obs_id, physicsClientId=self._physics_client
            )
            d = np.linalg.norm(ee_pos - np.array(obs_pos))
            min_dists.append(d)
        nearest_4 = sorted(min_dists)[:4]
        while len(nearest_4) < 4:
            nearest_4.append(1.0)

        return np.concatenate(
            [
                joint_pos,
                ee_pos,
                target_obj_pos,
                self._target_pos,
                finger_pos,
                np.array(nearest_4),
            ]
        )

    def get_success(self) -> bool:
        target_obj_pos, _ = p.getBasePositionAndOrientation(
            self._target_obj_id, physicsClientId=self._physics_client
        )
        return (
            float(np.linalg.norm(np.array(target_obj_pos) - self._target_pos))
            < self._success_threshold
        )

    def close(self):
        if self._physics_client is not None:
            p.disconnect(self._physics_client)
            self._physics_client = None
