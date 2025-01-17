from abc import ABC, abstractmethod
from enum import Enum
import os

from coeur.apps.ssg.db import Post

from dotenv import load_dotenv


load_dotenv(dotenv_path="./.env")


class Channels(Enum):
    INSTAGRAM = "instagram"
    BLUESKY = "bluesky"


class ChannelAbstract(ABC):
    @abstractmethod
    def publish(
        self,
        text,
        title,
        link,
        image_path: str = None,
        post_header: str = None,
        post_footer: str = None,
    ): ...


class Instagram(ChannelAbstract):
    client = None

    def __init__(self):
        self.client = self._create_client()

    def _create_client(self):
        from instagrapi import Client as InstagramClient
        from instagrapi.exceptions import LoginRequired

        client = InstagramClient(delay_range=[1, 3])
        username = os.getenv("INSTAGRAM_USERNAME")
        password = os.getenv("INSTAGRAM_PASSWORD")

        if not username or not password:
            raise ValueError("Instagram username or password not provided.")

        try:
            session = client.load_settings("instagram-session.json")
        except:
            session = None

        login_via_session = False
        login_via_pw = False

        if session:
            try:
                client.set_settings(session)
                client.login(username, password)
                try:
                    client.get_timeline_feed()
                except LoginRequired:
                    print("Session is invalid, need to login via username and password")
                    old_session = client.get_settings()
                    client.set_settings({})
                    client.set_uuids(old_session["uuids"])
                    client.login(username, password)
                    client.dump_settings("instagram-session.json")
                login_via_session = True
            except Exception as e:
                print("Couldn't login user using session information: %s" % e)

        if not login_via_session:
            try:
                print("Attempting to login via username and password. username: %s" % username)
                if client.login(username, password):
                    client.dump_settings("instagram-session.json")
                    login_via_pw = True
            except Exception as e:
                print("Couldn't login user using username and password: %s" % e)

        if not login_via_pw and not login_via_session:
            raise Exception("Couldn't login user with either password or session")

        return client

    def publish(
        self,
        text,
        title,
        link,
        image_path: str = None,
        post_header: str = None,
        post_footer: str = None,
    ) -> dict:
        try:
            if not image_path:
                raise ValueError("Image path is required for Instagram publish")

            publish = self.client.photo_upload(
                image_path,
                text,
                extra_data={
                    "custom_accessibility_caption": title,
                    "like_and_view_counts_disabled": 0,
                    "disable_comments": 0,
                },
            )
            return f"https://www.instagram.com/p/{publish.dict()['code']}"
        except Exception as e:
            print("instagram publish failed:", e)
        finally:
            if os.path.exists(image_path):
                os.remove(image_path)


class Bluesky(ChannelAbstract):
    client = None

    def __init__(self):
        self.client = self._create_client()

    def _create_client(self):
        from atproto import Client as BlueskyClient

        client = BlueskyClient()

        username = os.getenv("BLUESKY_USERNAME")
        password = os.getenv("BLUESKY_PASSWORD")

        if not username or not password:
            raise ValueError("Bluesky username or password not provided.")

        try:
            with open("bluesky-session.txt") as f:
                session = f.read()
        except:
            session = None

        login_via_session = False
        login_via_pw = False

        if session:
            try:
                client.login(session_string=session)
                login_via_session = True
            except Exception as e:
                print("Couldn't login user using session information")

        if not login_via_session:
            try:
                print("Attempting to login via username and password. username: %s" % username)
                client = BlueskyClient()
                client.login(username, password)
                session_string = client.export_session_string()
                with open("bluesky-session.txt", "w") as f:
                    f.write(session_string)
                login_via_pw = True
            except Exception as e:
                print("Couldn't login user using username and password: %s" % e)

        if not login_via_pw and not login_via_session:
            raise Exception("Couldn't login user with either password or session")

        return client

    def publish(
        self,
        text,
        title,
        link,
        image_path: str = None,
        post_header: str = None,
        post_footer: str = None,
    ) -> dict:
        from atproto import client_utils as bluesky_client_utils

        try:
            text = f"{post_header}\n{post_footer}\n"
            publish = self.client.send_post(
                (bluesky_client_utils.TextBuilder().text(text).link(title, link))
            )
            self.client.like(publish.uri, publish.cid)
            return publish.uri
        except Exception as e:
            print("bluesky publish failed:", e)
        finally:
            if image_path and os.path.exists(image_path):
                os.remove(image_path)


channel_engines = {
    Channels.INSTAGRAM: Instagram,
    Channels.BLUESKY: Bluesky,
}
