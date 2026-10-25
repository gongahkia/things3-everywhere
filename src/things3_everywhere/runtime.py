import os

from .adapter import ThingsAppleScriptAdapter
from .safety import WritePolicy
from .service import ThingsService


def live_service(*, read_only=False):
    policy = WritePolicy() if read_only else WritePolicy.from_env(os.environ)
    return ThingsService(ThingsAppleScriptAdapter(policy, app_path=os.environ.get("THINGS_APP_PATH")), policy)

