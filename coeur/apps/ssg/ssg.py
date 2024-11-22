from coeur.apps.ssg.build import BuildHandler
from coeur.apps.ssg.markdown import MarkdownHandler
from coeur.apps.ssg.bootstrap import CreateHandler, ExportTemplates
from coeur.apps.ssg.admin import AdminPanel

import typer

app = typer.Typer()


@app.command()
def build() -> None:
    """Build the site in current directory"""
    BuildHandler().handler()


@app.command()
def markdown_to_db(posts_directory: str):
    """Create the coeur database from markdown files of Zola framework"""
    MarkdownHandler.handler(posts_directory)


@app.command()
def serve(port: int = 8080, max_posts: int = None):
    """Server to test and see the project working locally"""
    BuildHandler(max_posts=max_posts).serve(port)


@app.command()
def create(name: str):
    """Create a new coeur ssg project"""
    CreateHandler(name)


@app.command()
def export_templates():
    """Export the default template for customization"""
    ExportTemplates.export()


@app.command()
def admin():
    """Manage your posts using the web dashboard"""
    AdminPanel.handler()
