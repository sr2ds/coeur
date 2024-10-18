from datetime import datetime, date
import glob
import itertools
import json
import re
import yaml


from coeur.utils import Benchmark
from coeur.apps.ssg.db import ContentFormat, DatabaseManager

HANDLE_BATCH_SIZE = 10000

benchmark = Benchmark()


class MarkdownHandler:
    @staticmethod
    def handler(posts_directory):
        file_generator = MarkdownHandler.find_index_md_files(posts_directory)
        errors = []
        while True:
            batch = list(itertools.islice(file_generator, HANDLE_BATCH_SIZE))
            if not batch:
                break
            try:
                errors = errors + MarkdownHandler.bulk_create_db_post(posts_directory, batch)
                benchmark.info()
            except Exception as e:
                print(e)
        benchmark.info()
        if len(errors):
            print("MarkdownHandler errors:", errors)

    @staticmethod
    def find_index_md_files(directory: str):
        files = glob.glob(f"{directory}/**/*.md", recursive=True)
        for file in files:
            yield file

    @staticmethod
    def bulk_create_db_post(base_directory: str, batch: list[str]):
        posts = []
        errors = []
        db = DatabaseManager()
        for file_path in batch:
            with open(file_path, "r") as content:
                try:
                    header, content = MarkdownHandler.extract_markdown_parts(content.read())
                    posts.append(
                        db.new_post(
                            title=header.get("title"),
                            content=content,
                            content_format=ContentFormat.MARKDOWN.value,
                            path=MarkdownHandler.get_post_path(base_directory, file_path),
                            extra=json.dumps(header) if header else None,
                            date=header.get("date"),
                            image=header.get("extra", {}).get("image"),
                        )
                    )
                except Exception as e:
                    errors.append({"file_path": file_path, "error": e})
                finally:
                    benchmark.increase()
        try:
            db.session.bulk_save_objects(posts)
            db.session.commit()
            db.session.close()
        except Exception as e:
            print(e)
            errors.append({"batch": batch, "error": e})
            db.session.rollback()
        return errors

    @staticmethod
    def get_post_path(base_directory, file_path):
        path = file_path.replace(base_directory, "").replace("index.md", "").replace(".md", "")
        if not path.startswith("/"):
            path = "/" + path
        return path

    @staticmethod
    def extract_markdown_parts(markdown_content: str):
        match = re.match(r"---\s*\n(.*?)\n---\s*\n(.*)", markdown_content, re.DOTALL)
        if not match:
            raise ValueError("Invalid format")
        yaml_header = match.group(1)
        content = match.group(2)
        header_data = MarkdownHandler.serialize_header(yaml.safe_load(yaml_header))
        return header_data, content

    @staticmethod
    def serialize_header(header):
        for key, value in header.items():
            if isinstance(value, (datetime, date)):
                header[key] = value.isoformat()
            elif isinstance(value, dict):
                MarkdownHandler.serialize_header(value)
        return header
