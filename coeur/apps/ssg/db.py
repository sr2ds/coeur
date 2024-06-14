import os
from enum import Enum
from coeur.utils import BuildSettings

from sqlalchemy import Column, Integer, String, create_engine, text, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import event

Base = declarative_base()
settings = BuildSettings("./config.toml")


class ContentFormat(Enum):
    MARKDOWN = "md"
    HTML = "html"


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    content_format = Column(String)
    path = Column(String)
    image = Column(String)
    extra = Column(String)
    date = Column(String)

    def __init__(self, schema=None, **kwargs):
        if schema:
            self.__table__.schema = schema
            self.__table__.metadata = MetaData(schema=schema)

        for key, value in kwargs.items():
            setattr(self, key, value)

    @hybrid_property
    def permalink(self):
        return f"{settings.get_base_url()}{self.path}/"


class ShardingManager:
    MAX_FILE_SIZE_MB = 80
    DB1_NAME = "db1.sqlite"

    @staticmethod
    def _get_databases():
        return [filename for filename in os.listdir("db")]

    @staticmethod
    def _get_posts_table_by_db(db_file):
        db = os.path.splitext(db_file)[0]
        return "posts" if db == "db1" else f"{db}.posts"


class DatabaseManager:
    def __init__(self):
        engine = create_engine(
            f"sqlite:///db/{ShardingManager.DB1_NAME}",
            connect_args={"check_same_thread": False},
        )
        event.listen(engine, "connect", self._attach_databases)
        self.databases = ShardingManager._get_databases()
        self.Session = sessionmaker(bind=engine)
        self.session = self.Session()
        self.smallest_db = self._get_smallest_db()
        event.listen(self.session, "after_commit", self.handle_db_size_limit)

    def _attach_databases(self, dbapi_connection, *args):
        if databases := ShardingManager._get_databases():
            for filename in databases:
                if filename.endswith(".sqlite") and filename != ShardingManager.DB1_NAME:
                    dbapi_connection.execute(
                        f"ATTACH DATABASE 'db/{filename}' AS {os.path.splitext(filename)[0]}"
                    )

    def _get_smallest_db(self):
        smallest_db = min(self.databases, key=lambda db: os.path.getsize(f"db/{db}"))
        return os.path.splitext(smallest_db)[0]

    def handle_db_size_limit(self, *args):
        session = self.Session()
        self.smallest_db = self._get_smallest_db()
        file_size = os.path.getsize(f"db/{self.smallest_db}.sqlite")
        if file_size > ShardingManager.MAX_FILE_SIZE_MB * 1024 * 1024:
            filename = f"db{len(self.databases) + 1}.sqlite"
            file_prefix = os.path.splitext(filename)[0]
            session.execute(text(f"ATTACH DATABASE 'db/{filename}' AS {file_prefix}"))
            session.execute(
                text(f"CREATE TABLE {file_prefix}.posts AS SELECT * FROM posts WHERE 0")
            )
            session.commit()
            session.close()
            self.databases.append(filename)

    def new_post(self, title, content, content_format, path, extra, date, image):
        return Post(
            title=title,
            content=content,
            content_format=content_format,
            path=path,
            extra=extra,
            date=date,
            image=image,
            schema=self.smallest_db if self.smallest_db != "db1" else None,
        )

    def count_total_posts(self):
        union_query = " UNION ALL ".join(
            [
                f"SELECT title, content FROM {ShardingManager._get_posts_table_by_db(filename)}"
                for filename in self.databases
            ]
        )
        return self.session.execute(text(f"SELECT COUNT(*) FROM ({union_query})")).fetchone()[0]

    def _get_all_posts(self, page=1, limit=200):
        offset = (page - 1) * limit
        union_query = " UNION ALL ".join(
            [
                f"SELECT * FROM {ShardingManager._get_posts_table_by_db(filename)}"
                for filename in self.databases
            ]
        )
        paginated_query = f"SELECT * FROM ({union_query}) AS all_posts LIMIT :limit OFFSET :offset"
        result = self.session.execute(text(paginated_query), {"limit": limit, "offset": offset})
        return result.fetchall()

    def _fetch_pagination_mapped(self, offset=0, limit=200):
        union_query = " UNION ALL ".join(
            [
                f"SELECT * FROM {ShardingManager._get_posts_table_by_db(filename)}"
                for filename in self.databases
            ]
        )
        paginated_query = f"SELECT * FROM ({union_query}) AS all_posts LIMIT :limit OFFSET :offset"
        result = self.session.execute(text(paginated_query), {"limit": limit, "offset": offset})
        posts = result.fetchall()
        posts_dicts = []
        for post_tuple in posts:
            post_dict = {}
            for idx, column in enumerate(result.keys()):
                post_dict[column] = post_tuple[idx]
            posts_dicts.append(post_dict)
        return [Post(**post_dict) for post_dict in posts_dicts]

    def generator_page_posts(self, limit=200):
        total = self.count_total_posts()
        fetched = 0
        offset = 0

        while fetched < total:
            posts = self._fetch_pagination_mapped(offset=offset, limit=limit)
            fetched += len(posts)
            offset = offset + limit
            yield posts
