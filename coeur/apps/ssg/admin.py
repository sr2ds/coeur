import types
from coeur.apps.ssg.db import Post, ShardingManager
from fastapi import FastAPI
from sqladmin import Admin
from sqladmin import ModelView
from sqlalchemy import create_engine
from sqlalchemy.orm.session import sessionmaker
import uvicorn


class UserAdminPostBase(ModelView, model=Post): ...


class AdminPanel:
    @staticmethod
    def handler():
        """
        Initializes and starts a FastAPI application with an admin interface for managing posts from multiple SQLite databases.

        This method dynamically loads all post classes from the ShardingManager and configures
        the database bindings for each post class. It then creates a FastAPI application and
        adds a custom Admin view for each post class, allowing users to manage posts via the
        admin interface.

        The method performs the following steps:
        1. Retrieves the post classes from the ShardingManager.
        2. Configures the database engine bindings for each post class (SQLite database for each).
        3. Sets up a FastAPI app and an Admin interface with user-specific views for managing posts.
        4. Enables editing and deletion of posts for a single database or disables it for multiple databases.
        5. Adds a view to the Admin interface for each post class, defining the columns and features.
        6. Starts a local development server for the Admin interface at `http://localhost:8000/admin`.

        Notes:
        - The method currently supports one database with the ability to edit/delete posts.
          Multi-database support for editing and deleting posts is planned for future implementation.
        - The `count_query` for each post class is a placeholder and needs to be implemented.

        Example:
            To run the application with the admin interface:
            ```
            AdminPanel().handler()
            ```
        """
        post_classes = ShardingManager.get_posts_classes()
        binds = {}
        for key, post_classe in post_classes.items():
            binds[post_classe] = create_engine(f"sqlite:///db/db{key}.sqlite")

        Session = sessionmaker()
        Session.configure(binds=binds)

        app = FastAPI()
        admin = Admin(app=app, session_maker=Session)
        # @todo: allow edit/delete for multi databases
        enable_edit_delete = True if len(post_classes.items()) == 1 else False
        for key, post_classe in post_classes.items():
            user_admin_post_class = types.new_class(
                f"UserAdminPostsDb{key}", UserAdminPostBase.__bases__, {"model": post_classe}
            )
            user_admin_post_class.name_plural = f"db{key}"
            user_admin_post_class.column_searchable_list = [
                Post.uuid,
                Post.title,
                Post.path,
                Post.date,
            ]
            user_admin_post_class.column_list = [Post.uuid, Post.title, Post.path, Post.date]
            user_admin_post_class.column_sortable_list = [Post.title, Post.date]
            user_admin_post_class.can_create = False
            user_admin_post_class.can_edit = enable_edit_delete
            user_admin_post_class.can_delete = enable_edit_delete
            user_admin_post_class.icon = "fa-solid fa-database"
            user_admin_post_class.category = "posts by database"
            # @todo: fix counter by db
            # user_admin_post_class.count_query = ?
            admin.add_view(user_admin_post_class)

        print("You can view and manage your posts at http://localhost:8000/admin")

        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="critical",
        )
