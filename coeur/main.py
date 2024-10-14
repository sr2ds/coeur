import typer

from coeur.apps.ssg import ssg
from coeur.apps.cmp import cmp

app = typer.Typer()
app.add_typer(ssg.app, name="ssg", help="Static Site Generator tool")
app.add_typer(cmp.app, name="cmp", help="Content Machine Processor tool")
