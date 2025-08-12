from unpage.cli._app import app
from unpage.utils import import_submodules

import_submodules("unpage.cli")


def main() -> None:
    app.meta()


if __name__ == "__main__":
    main()
