import os
import json
from datetime import datetime

from coeur.apps.ssg.db import ContentFormat, DatabaseManager
from slugify import slugify

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(dotenv_path="./.env")


class Content:
    title: str
    img_url: str | None
    content: str

    def __init__(self, title, img_url, content):
        self.title = title
        self.img_url = img_url
        self.content = content


class OpenAIEngine:
    def client(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API key is missing or not set in the environment variables.")
        return OpenAI(api_key=api_key)

    def generate_content(
        self,
        title,
        custom_prompt: str = None,
        model="gpt-3.5-turbo",
    ):
        prompt = f"""
            Please return the content in HTML and only content about my requests, with no prefix.\n
            The content need to be optimized for SEO but is important NOT tell NOTHING about SEO in the content, like tags for seo or something like that.\n
            Create a creative blog post, considering great tags for SEO and high quality content about this specific content: {title}
        """
        if custom_prompt:
            prompt = f"{custom_prompt}: {title}"

        chat_completion = self.client().chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            model=model,
        )
        return chat_completion.choices[0].message.content


class Engine:
    @staticmethod
    def title_to_post(
        title: str,
        img_url: str = None,
        custom_prompt: str = None,
        custom_path: str = None,
    ):
        ai_engine = OpenAIEngine()

        content = Content(
            title=title,
            img_url=img_url,
            content=ai_engine.generate_content(title, custom_prompt=custom_prompt),
        )

        Engine.store_post(content, custom_path)

    @staticmethod
    def build_post_path(content: Content, custom_path: str = None):
        if custom_path:
            parts = custom_path.split("/")
            slugs = [slugify(part) for part in parts if part]
            path = "/".join(slugs)
            if not path.endswith("/"):
                path = f"{path}/"
            return path

        today = datetime.now()
        path_prefix = today.strftime("%Y/%m/%d")
        return f"/{path_prefix}/{slugify(content.title)}/"

    @staticmethod
    def store_post(content: Content, custom_path: str = None):
        db = DatabaseManager()
        today = datetime.now()
        try:
            post = db.new_post(
                title=content.title,
                content=content.content,
                content_format=ContentFormat.HTML.value,
                path=Engine.build_post_path(content, custom_path),
                extra=json.dumps({}),
                date=today.strftime("%Y-%m-%d"),
                image=content.img_url,
            )
            db.session.add(post)
            db.session.commit()
        except Exception as e:
            print(e)
            db.session.rollback()
        finally:
            db.session.close()
