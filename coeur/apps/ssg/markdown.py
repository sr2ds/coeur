import glob
import itertools
import json
import re
import yaml


from coeur.utils import Benchmark
from coeur.apps.ssg.db import Post, ContentFormat, get_db_session

HANDLE_BATCH_SIZE = 10000

benchmark = Benchmark()


class MarkdownHandler:
    @staticmethod
    def handler(posts_directory):
        file_generator = MarkdownHandler.find_index_md_files(posts_directory)
        errors = []
        db = get_db_session()
        while True:
            batch = list(itertools.islice(file_generator, HANDLE_BATCH_SIZE))
            if not batch:
                break
            try:
                errors = errors + MarkdownHandler.bulk_create_db_post(db, posts_directory, batch)
                benchmark.info()
                db.commit()
            except Exception as e:
                print(e)
        db.close()
        benchmark.info()
        if len(errors):
            print("MarkdownHandler errors:", errors)

    @staticmethod
    def find_index_md_files(directory: str):
        files = glob.glob(f"{directory}/**/*.md", recursive=True)
        for file in files:
            yield file

    @staticmethod
    def bulk_create_db_post(db, base_directory: str, batch: list[str]):
        posts = []
        errors = []
        for file_path in batch:
            with open(file_path, "r") as content:
                try:
                    header, content = MarkdownHandler.extract_markdown_parts(content.read())
                    posts.append(
                        Post(
                            title=header.get("title"),
                            content=content,
                            content_format=ContentFormat.MARKDOWN.value,
                            path=file_path.replace(base_directory, "")
                            .replace("index.md", "")
                            .replace(".md", ""),
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
            db.bulk_save_objects(posts)
        except Exception as e:
            errors.append({"batch": batch, "error": e})
            db.rollback()
        return errors

    @staticmethod
    def extract_markdown_parts(markdown_content: str):
        match = re.match(r"---\s*\n(.*?)\n---\s*\n(.*)", markdown_content, re.DOTALL)
        if not match:
            raise ValueError("Invalid format")
        yaml_header = match.group(1)
        content = match.group(2)
        header_data = yaml.safe_load(yaml_header)
        return header_data, content
