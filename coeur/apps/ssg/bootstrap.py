import os
import uuid
import pathlib
import shutil
from coeur.apps.ssg.db import Post, ContentFormat, Base, ShardingManager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

CONFIG_TEMPLATE = """
site_title="My Blog with Coeur"
site_description="This is a blog sample made with Coeur"
default_language = "en"
base_url = "https://google.com/"
minify=false

[extra]
custom_head_attributes = []
menu_pages = [
    {title = "Example menu", url =  "/"}
]
footer_pages = [
    { title = "Example footer", url = "/" },
]

[lang]
previous_text="Previous Page"
next_text="Next Page"

"""

ENV_TEMPLATE = """
OPENAI_API_KEY=""
INSTAGRAM_USERNAME=""
INSTAGRAM_PASSWORD=""
SOCIAL_DEFAULT_IMAGE_URL=""

"""

GITIGNORE_TEMPLATE = """
.env
session.json
"""


class CreateHandler:
    def __init__(self, name) -> None:
        if os.path.exists(f"./{name}"):
            raise ValueError("Folder exists")

        os.mkdir(name)
        os.mkdir(f"{name}/db")

        files_x_contents = {
            "config.toml": CONFIG_TEMPLATE,
            ".env": ENV_TEMPLATE,
            ".gitignore": GITIGNORE_TEMPLATE,
        }

        for file_name, content in files_x_contents.items():
            with open(f"{name}/{file_name}", "w") as file:
                file.writelines(content)
                file.close()

        engine = create_engine(
            f"sqlite:///{name}/db/{ShardingManager.DB1_NAME}",
            connect_args={"check_same_thread": False},
        )

        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        session.add(
            Post(
                uuid=str(uuid.uuid4()),
                title="Hello World!",
                content="Welcome to Coeur Post",
                content_format=ContentFormat.MARKDOWN.value,
                path="/posts/welcome",
                extra=None,
                image="/img/sacre-coeur.png",
                db=1,
            )
        )
        session.flush()
        session.commit()


class ExportTemplates:
    @staticmethod
    def export():
        if os.path.exists("./templates"):
            raise ValueError(
                f"You already have the templates folder at templates. "
                "Backup it and rename to be able to export the default."
            )
        os.makedirs("./templates", exist_ok=True)
        src = pathlib.Path(__file__).parent.resolve()
        shutil.copytree(f"{src}/templates/", "./templates/", dirs_exist_ok=True)
