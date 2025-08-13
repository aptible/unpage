from cyclopts import Parameter

from unpage.config import manager

DEFAULT_PROFILE = manager.get_active_profile()

ProfileParameter = Parameter(
    name="--profile",
    help="Use profiles to manage multiple graphs",
    env_var="UNPAGE_PROFILE",
    show_env_var=True,
)
