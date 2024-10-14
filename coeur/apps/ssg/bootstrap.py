import os
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

"""

GITIGNORE_TEMPLATE = """
.env

"""


class CreateHandler:
    def __init__(self, name) -> None:
        if os.path.exists(f"./{name}"):
            raise "Folder exists"

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
                title="Hello World!",
                content="Welcome to Coeur Post",
                content_format=ContentFormat.MARKDOWN.value,
                path="/posts/welcome",
                extra=None,
                image="/img/sacre-coeur.png",
            )
        )
        session.flush()
        session.commit()
