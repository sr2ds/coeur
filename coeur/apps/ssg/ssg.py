import types

from coeur.apps.ssg.db import Post, ShardingManager
from coeur.apps.ssg.build import BuildHandler
from coeur.apps.ssg.markdown import MarkdownHandler
from coeur.apps.ssg.bootstrap import CreateHandler, ExportTemplates

from sqladmin import ModelView
from sqlalchemy.orm.session import sessionmaker
from sqladmin import Admin
from sqlalchemy import create_engine
from fastapi import FastAPI
import uvicorn
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


class UserAdminPostBase(ModelView, model=Post): ...


@app.command()
def admin():
    """Manage your posts using the web dashboard"""
    post_classes = ShardingManager.get_posts_classes()
    binds = {}
    for key, post_classe in post_classes.items():
        binds[post_classe] = create_engine(f"sqlite:///db/db{key}.sqlite")

    Session = sessionmaker()
    Session.configure(binds=binds)

    app = FastAPI()
    admin = Admin(app=app, session_maker=Session)

    for key, post_classe in post_classes.items():
        user_admin_post_class = types.new_class(
            f"UserAdminPostsDb{key}", UserAdminPostBase.__bases__, {"model": post_classe}
        )
        user_admin_post_class.name_plural = f"db{key}"
        user_admin_post_class.column_searchable_list = [Post.uuid, Post.title, Post.path, Post.date]
        user_admin_post_class.column_list = [Post.uuid, Post.title, Post.path, Post.date]
        user_admin_post_class.column_sortable_list = [Post.title, Post.date]
        # @todo: fix crud operations
        user_admin_post_class.can_create = False
        user_admin_post_class.can_edit = False
        user_admin_post_class.can_delete = False
        user_admin_post_class.icon = "fa-solid fa-database"
        user_admin_post_class.category = "posts by database"
        # @todo: fix counter by db
        # user_admin_post_class.count_query = False
        admin.add_view(user_admin_post_class)

    uvicorn.run(app, host="127.0.0.1", port=8000)
