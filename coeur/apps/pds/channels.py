from abc import ABC, abstractmethod
from enum import Enum
from urllib.parse import urlparse
import os
import os
import requests
import uuid

from coeur.apps.ssg.db import Post

from dotenv import load_dotenv
from instagrapi import Client as InstagramClient

load_dotenv(dotenv_path="./.env")


class Channels(Enum):
    INSTAGRAM = "instagram"


class ChannelAbstract(ABC):
    @abstractmethod
    def publish(self, post: Post): ...

    @abstractmethod
    def build_text(self, post: Post) -> str: ...


class Instagram(ChannelAbstract):
    client = None

    def __init__(self):
        self.client = self._create_client()

    def _create_client(self) -> InstagramClient:
        client = InstagramClient()
        username = os.getenv("INSTAGRAM_USERNAME")
        password = os.getenv("INSTAGRAM_PASSWORD")

        if not username or not password:
            raise ValueError("Instagram username or password not provided.")

        client.login(username, password)
        return client

    def publish(self, post: Post) -> dict:
        # @todo: test it and return the publish URL
        return ""
        try:
            img_path = download_image(post.image)
            publish = self.client.photo_upload(
                img_path,
                post.text,
                extra_data={
                    "custom_accessibility_caption": post.title,
                    "like_and_view_counts_disabled": 0,
                    "disable_comments": 0,
                },
            )
            print(publish.dict())
            return publish.dict()
        except Exception as e:
            print(e)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def build_text(self, post: Post) -> str:
        # do something in the text
        return post.text


channel_engines = {
    Channels.INSTAGRAM: Instagram,
}


def download_image(url, save_dir="temp"):
    os.makedirs(save_dir, exist_ok=True)
    extension = os.path.splitext(urlparse(url).path)[1] or ".jpg"
    local_path = os.path.join(save_dir, f"{uuid.uuid4()}{extension}")
    response = requests.get(url)
    response.raise_for_status()
    with open(local_path, "wb") as file:
        file.write(response.content)
    return local_path
