import psutil
import os
import time
from datetime import timedelta, datetime
from concurrent.futures import ThreadPoolExecutor
import http.server
import socketserver
import re
import unicodedata

import toml
from jinja2 import Environment, FileSystemLoader

process = psutil.Process(os.getpid())


class BuildSettings:
    def __init__(self, config_path) -> None:
        self.database = "db/db1.sqlite"
        self.posts_db_pagination = 10000
        self.posts_pagination = 100
        self.root_folder = self.get_output_folder()
        self.template_folder = self.get_template_folder()
        self.coeur_thread_ex = self.get_async_executor()
        if os.path.exists(config_path):
            self.config = toml.load(config_path)
            self.templates = self.get_templates()

    def reload_templates(self):
        self.templates = self.get_templates()

    def get_base_url(self):
        return (
            self.config["base_url"][:-1]
            if self.config["base_url"].endswith("/")
            else self.config["base_url"]
        )

    def get_templates(self):
        template_eng = Environment(loader=FileSystemLoader(searchpath=self.template_folder))
        template_eng.globals.update({**self.config})

        template_eng.globals.update({"year": datetime.now().year})
        return {
            "post": template_eng.get_template("post.html"),
            "page": template_eng.get_template("page.html"),
            "sitemap": template_eng.get_template("sitemap.xml"),
        }

    def get_async_executor(self):
        return ThreadPoolExecutor(max_workers=4, thread_name_prefix="coeur")

    def get_output_folder(self):
        return "./public"

    def get_template_folder(self):
        default = os.path.join(os.path.dirname(__file__), "apps", "ssg", "templates")
        if os.path.exists("./templates/"):
            return "./templates/"
        else:
            return default


class Benchmark:
    def __init__(self):
        self.start_time = time.time()
        self.processed = 0

    def info(self):
        memory_info = process.memory_full_info()
        cpu_usage = process.cpu_percent()
        info = (
            f"Debug: "
            f"RSS: {self.bytes_to_mb(memory_info.rss):.2f} MB | "
            f"VMS: {self.bytes_to_mb(memory_info.vms):.2f} MB | "
            f"Data: {self.bytes_to_mb(memory_info.data):.2f} MB | "
            f"USS: {self.bytes_to_mb(memory_info.uss):.2f} MB | "
            f"PSS: {self.bytes_to_mb(memory_info.pss):.2f} MB | "
            f"Processed: {self.processed} | "
            f"CPU: {cpu_usage:.2f}%\n"
        )
        self.execution_time()
        print(info)

    def bytes_to_mb(self, bytes_value):
        return bytes_value / (1024 * 1024)

    def increase(self):
        self.processed += 1

    def execution_time(self):
        execution_time = timedelta(seconds=time.time() - self.start_time)
        print(f"Processed: {self.processed} | Duration: {execution_time}")


class HttpHandler:
    class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, root_folder=None, **kwargs):
            self.root_folder = root_folder
            super().__init__(*args, **kwargs)

        def translate_path(self, path):
            path = super().translate_path(path)
            relpath = os.path.relpath(path, os.getcwd())
            return os.path.join(self.root_folder, relpath)

    def __init__(self, root_folder, port=8081):
        self.root_folder = root_folder
        self.port = port
        self.httpd = None

    def serve_forever(self):
        Handler = lambda *args, **kwargs: self.CustomHTTPRequestHandler(
            *args, root_folder=self.root_folder, **kwargs
        )
        socketserver.TCPServer.allow_reuse_address = True
        self.httpd = socketserver.TCPServer(("", self.port), Handler)
        print(f"Serving at port http://localhost:{self.port}")
        self.httpd.serve_forever()

    def shutdown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        print("Server stopped")
