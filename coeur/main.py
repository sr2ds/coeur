import typer

from coeur.apps.ssg import ssg

app = typer.Typer()
app.add_typer(ssg.app, name="ssg", help="Static Site Generator tool")
