from concurrent.futures import as_completed
from datetime import datetime
import os
import shutil

from coeur.apps.ssg.db import DatabaseManager, Post, ContentFormat
from coeur.utils import Benchmark, BuildSettings, HttpHandler

from rich.progress import Progress, SpinnerColumn, TextColumn
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
import minify_html
import mistune

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
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            auto_refresh=True,
        ) as progress:
            task = progress.add_task(description="Creating pages (pagination)...", total=10)
            self.create_pagination()
            progress.update(task_id=task, advance=10)

            task = progress.add_task(description="Creating single posts...", total=10)
            self.create_posts_from_db()
            progress.update(task_id=task, advance=10)

            task = progress.add_task(description="Creating sitemap...", total=10)
            self.create_sitemap()
            progress.update(task_id=task, advance=10)

    def create_sitemap(
        self,
    ):
        base_url = (
            self.settings.config["base_url"][:-1]
            if self.settings.config["base_url"].endswith("/")
            else self.settings.config["base_url"]
        )
        sitemaps = []
        db = DatabaseManager()
        max_items_by_sitemap = 30000
        seo_variations = self.settings.get_seo_variations_path()
        seo_variations_count = len(seo_variations) if seo_variations else 1
        total_by_page = int(max_items_by_sitemap / seo_variations_count)

        for page, posts_db_page in enumerate(
            db.generator_page_posts(total_by_page=total_by_page, max_posts_server=self.max_posts),
            start=1,
        ):
            extra_posts = []
            for post in posts_db_page:
                for path in seo_variations:
                    extra_post = post.__dict__.copy()
                    extra_post.pop("_sa_instance_state", None)
                    extra_post["path"] = f'{post.path.rstrip("/")}-{path}/'
                    extra_post["date"] = datetime.today().strftime("%Y-%m-%d")
                    extra_posts.append(Post(**extra_post))

            sitemap = self.settings.templates["sitemap"].render(
                {"entries": posts_db_page + extra_posts}
            )
            self.create_file(f"/sitemap{page}.xml", sitemap)
            sitemaps.append(f"<sitemap><loc>{base_url}/sitemap{page}.xml</loc></sitemap>")

        sitemap_index = f"""<?xml version="1.0" encoding="UTF-8"?>
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            {" ".join(sitemaps)}
        </sitemapindex>
        """
        self.create_file(f"/sitemap.xml", sitemap_index)
        db.session.close()

    def create_pagination(
        self,
    ):
        db = DatabaseManager()
        total = 0

        for page, posts_db_page in enumerate(
            db.generator_page_posts(
                total_by_page=self.settings.posts_pagination, max_posts_server=self.max_posts
            ),
            start=1,
        ):
            navigation = {"current": page}
            total += page

            if page > 1:
                previous = page - 1
                if previous == 1:
                    navigation["previous"] = "/index.html"
                else:
                    navigation["previous"] = f"/page/{previous}"

            if page > (total / self.settings.posts_pagination):
                navigation["next"] = f"/page/{page + 1}"

            page_list = self.settings.templates["page"].render(
                {"paginator": {"pages": posts_db_page, "navegation": navigation}}
            )
            if page == 1:
                self.create_file(f"/index.html", page_list)
            else:
                self.create_file(f"/page/{page}/index.html", page_list)
        db.session.close()

    def create_posts_from_db(
        self,
    ):
        db = DatabaseManager()

        for posts_db_page in db.generator_page_posts(
            total_by_page=self.settings.posts_db_pagination, max_posts_server=self.max_posts
        ):
            for future in as_completed(
                (
                    self.settings.coeur_thread_ex.submit(self.handle_post, post)
                    for post in posts_db_page
                )
            ):
                try:
                    future.result()
                except Exception as e:
                    print(e)
        db.session.close()

    def handle_post(self, post: Post) -> None:
        if post.content_format == ContentFormat.MARKDOWN.value:
            post.content = mistune.html(post.content)
        html = self.settings.templates["post"].render(post=post)
        if self.settings.config.get("minify", False):
            html = minify_html.minify(
                html,
                minify_js=True,
                minify_css=True,
                remove_processing_instructions=True,
            )
        self.create_file(f"{post.path}/index.html", html)
        extra_paths = self.settings.get_seo_variations_path()
        for path in extra_paths:
            extra_path = f'{post.path.rstrip("/")}-{path}'
            self.create_file(f"/{extra_path}/index.html", html)

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
