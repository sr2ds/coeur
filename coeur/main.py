import typer

from coeur.apps.ssg import ssg
from coeur.apps.cmp import cmp
from coeur import __version__

app = typer.Typer(help=f"Welcome to Couer {__version__}!", no_args_is_help=True)
app.add_typer(ssg.app, name="ssg", help="Static Site Generator tool")
app.add_typer(cmp.app, name="cmp", help="Content Machine Processor tool")
