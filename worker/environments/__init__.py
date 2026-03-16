from worker.environments.cluttered import ClutteredPickEnv
from worker.environments.pick_place import PickPlaceEnv
from worker.environments.reach import ReachEnv

ENV_REGISTRY = {
    "reach": ReachEnv,
    "pick_place": PickPlaceEnv,
    "cluttered": ClutteredPickEnv,
}
