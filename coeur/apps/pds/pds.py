from coeur.apps.pds.engine import Engine
from coeur.apps.pds.channels import Channels

import typer

app = typer.Typer()
from typing import List


@app.command()
def publish(
    channels: List[Channels], total: int = 1, post_header: str = None, post_footer: str = None
) -> None:
    Engine(channels, total, post_header, post_footer).run()
