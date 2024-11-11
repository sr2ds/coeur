from datetime import datetime
from urllib.parse import urlparse
import json
import os
import re
import re
import requests
import uuid

from coeur.apps.ssg.db import DatabaseManager
from coeur.apps.pds.channels import channel_engines, Channels

from sqlalchemy import text
from bs4 import BeautifulSoup
from dotenv import load_dotenv


load_dotenv(dotenv_path="./.env")
SOCIAL_DEFAULT_IMAGE_URL = os.getenv("SOCIAL_DEFAULT_IMAGE_URL")


class Engine:
    def __init__(
        self,
        channels: list[Channels],
        total: int,
    ):
        self.channels = channels
        self.total = total

    def run(self) -> None:
        for channel in self.channels:
            # when more channels be avaiable, we can to run them in parallel
            self.publish(channel)

    def publish(self, channel: Channels) -> None:
        db = DatabaseManager()
        posts_without_channel_url = db.get_posts(
            limit=1,
            exclude_filters=[
                {"extra": f'"{channel.value}": {{'},
            ],
        )

        channel_engine = channel_engines[channel]()
        for post in posts_without_channel_url:
            try:
                published_url = channel_engine.publish(
                    self.handle_content(post),
                    self.handle_img(post.image),
                    post.title,
                )
                extra = self.update_extra_attribute(channel, post, published_url)
                db.session.execute(
                    text(f"UPDATE db{post.db}.posts SET extra = :extra WHERE uuid = :uuid"),
                    {"extra": extra, "uuid": post.uuid},
                )
                db.session.commit()
                print(post.uuid, post.db, post.title, published_url)
            except Exception as e:
                print(e)
                db.session.rollback()

        db.session.close()

    def update_extra_attribute(self, channel: Channels, post, published_url: str) -> str:
        try:
            channel_object = {
                "url": published_url,
                "date": datetime.now().isoformat(),
            }
            extra = json.loads(post.extra)
            if "social" in extra:
                extra["social"][channel.value] = channel_object
            else:
                extra["social"] = {channel.value: channel_object}
            return json.dumps(extra)
        except:
            print("Error when try to handle the extra post json", post.title)
            return post.extra

    def handle_img(self, image_url=None) -> str:
        try:
            if not image_url:
                image_url = SOCIAL_DEFAULT_IMAGE_URL
            os.makedirs("temp", exist_ok=True)
            extension = os.path.splitext(urlparse(image_url).path)[1] or ".jpg"
            local_path = os.path.join("temp", f"{uuid.uuid4()}{extension}")
            response = requests.get(image_url)
            response.raise_for_status()
            with open(local_path, "wb") as file:
                file.write(response.content)
            return local_path
        except Exception as e:
            print("handle_img", e)

    def handle_content(self, post):
        maped_post = DatabaseManager.map_posts([post])[0]
        text = post.title
        text += f"\n\n{self.extract_text_from_markdown(post.content)}"
        text += f"\n\n{maped_post.permalink}"
        return text

    def extract_text_from_markdown(self, markdown_text: str, word_limit: int = 150) -> str:
        text = re.sub(r"(```.*?```|`[^`]*`)", "", markdown_text, flags=re.DOTALL)
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)  # Imagens
        text = re.sub(r"\[.*?\]\(.*?\)", "", text)  # Links
        text = re.sub(r"#{1,6}\s*", "", text)  # Headers
        text = re.sub(r"[*_~]", "", text)
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text(separator=" ")
        words = text.split()
        limited_text = " ".join(words[:word_limit])
        return f"{ limited_text } ..."
