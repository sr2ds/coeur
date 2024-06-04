from concurrent.futures import as_completed
import os
import shutil

from coeur.apps.ssg.db import get_db_session, Post, ContentFormat
from coeur.utils import Benchmark, BuildSettings, HttpHandler

import mistune
import htmlmin
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

benchmark = Benchmark()


class BuildHandler:
    def __init__(self, max_posts: int = None):
        self.max_posts = max_posts
        self.settings = BuildSettings("./config.toml")
        shutil.rmtree(self.settings.root_folder, ignore_errors=True)
        if os.path.exists(f"{self.settings.template_folder}/static"):
            shutil.copytree(
                f"{self.settings.template_folder}/static",
                self.settings.root_folder,
                dirs_exist_ok=True,
            )

    def handler(self, *args, **kwargs) -> None:
        benchmark.info()
        self.create_pagination()
        self.create_posts_from_db()
        self.create_sitemap()
        benchmark.info()

    def generate_db_paginate_posts(self, max_by_page: int):
        db_page = 0
        has_posts = True
        posts = 0
        counter = 0
        if self.max_posts and self.max_posts < max_by_page:
            max_by_page = self.max_posts
        while has_posts:
            db = get_db_session()
            posts = db.query(Post).offset(db_page).limit(max_by_page).all()
            if not len(posts) or (self.max_posts and counter >= self.max_posts):
                has_posts = False
                return

            db_page += max_by_page

            yield posts
            counter += len(posts)
            db.close()

    def create_sitemap(
        self,
    ):
        print("Starting Sitemaps Creation")
        base_url = (
            self.settings.config["base_url"][:-1]
            if self.settings.config["base_url"].endswith("/")
            else self.settings.config["base_url"]
        )

        sitemaps = []
        for page, posts_db_page in enumerate(
            self.generate_db_paginate_posts(max_by_page=30000), start=1
        ):
            sitemap = self.settings.templates["sitemap"].render({"entries": posts_db_page})
            self.create_file(f"/sitemap{page}.xml", sitemap)
            sitemaps.append(f"<sitemap><loc>{base_url}/sitemap{page}.xml</loc></sitemap>")

        sitemap_index = f"""<?xml version="1.0" encoding="UTF-8"?>
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            {" ".join(sitemaps)}
        </sitemapindex>
        """

        self.create_file(f"/sitemap.xml", sitemap_index)
        print(f"Finished Sitemaps Creation - total pages: {page}")

    def create_pagination(
        self,
    ):
        print("Starting Pagination Creation")
        db = get_db_session()
        total = db.query(Post).count()
        db.close()

        for page, posts_db_page in enumerate(
            self.generate_db_paginate_posts(max_by_page=self.settings.posts_pagination), start=1
        ):
            navigation = {"current": page}

            if page > 1:
                previous = page - 1
                if previous == 1:
                    navigation["previous"] = "/index.html"
                else:
                    navigation["previous"] = f"/page/{previous}"

            if page < (total / self.settings.posts_pagination):
                navigation["next"] = f"/page/{page + 1}"

            page_list = self.settings.templates["page"].render(
                {"paginator": {"pages": posts_db_page, "navegation": navigation}}
            )
            if page == 1:
                self.create_file(f"/index.html", page_list)
            else:
                self.create_file(f"/page/{page}/index.html", page_list)

        print("Finished Pagination Creation, last page: ", page)

    def create_posts_from_db(
        self,
    ):
        db = get_db_session()
        total = db.query(Post).count()
        total_used = self.max_posts if self.max_posts else total
        print(f"Starting Posts Creation - creating {total_used} from {total}")
        db.close()

        for posts_db_page in self.generate_db_paginate_posts(
            max_by_page=self.settings.posts_db_pagination
        ):
            for future in as_completed(
                (
                    self.settings.coeur_thread_ex.submit(self.handle_post, post)
                    for post in posts_db_page
                )
            ):
                benchmark.increase()
                try:
                    future.result()
                except Exception as e:
                    print(e)
            benchmark.info()

    def handle_post(self, post: Post) -> None:
        if post.content_format == ContentFormat.MARKDOWN.value:
            post.content = mistune.html(post.content)
        html = self.settings.templates["post"].render(post=post)
        if self.settings.config.get("minify", False):
            print(" minifying")
            html = htmlmin.minify(html, remove_empty_space=True)

        self.create_file(f"{post.path}/index.html", html)

    def create_file(self, path: str, html: str) -> None:
        folder_path = f"{self.settings.root_folder}/{path}"
        file_path = os.path.dirname(folder_path)
        if not os.path.exists(file_path):
            os.makedirs(file_path)
        with open(folder_path, "w") as file:
            file.writelines(html)
            file.close()

    def serve(self, port: int):
        self.handler()

        observer = ServerObserver(self).observer()
        handler = HttpHandler(self.settings.root_folder, port=port)
        try:
            handler.serve_forever()
        except KeyboardInterrupt:
            self.settings.coeur_thread_ex.shutdown()
            handler.shutdown()
            observer.stop()


class ServerObserver:
    def __init__(self, cls: BuildHandler) -> None:
        self.cls = cls

    def observer(self):
        event_handler = FileSystemEventHandler()
        event_handler.on_modified = self.on_change
        observer = Observer()
        observer.schedule(event_handler, self.cls.settings.template_folder, recursive=True)
        observer.start()
        return observer

    def on_change(self, *args):
        self.cls.handler()
        self.cls.settings.reload_templates()
