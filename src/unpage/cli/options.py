from cyclopts import Parameter

DEFAULT_PROFILE = "default"

ProfileParameter = Parameter(
    name="--profile",
    help="Use profiles to manage multiple graphs",
    env_var="UNPAGE_PROFILE",
    show_env_var=True,
)
