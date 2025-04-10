from unpage.cli._app import app


@app.command()
def version() -> None:
    """
    Display the version of the Unpage CLI.
    """
    from unpage import __version__

    print(f"unpage {__version__}")
