import os
import json
from enum import Enum
from coeur.utils import BuildSettings

from sqlalchemy import Column, Integer, String, create_engine, text, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker, Session
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

    @property
    def permalink(self):
        return f"{settings.get_base_url()}{self.path}"

    @property
    def attrs(self):
        try:
            return json.loads(self.extra)
        except:
            ...


class ShardingManager:
    MAX_FILE_SIZE_MB = 80
    DB1_NAME = "db1.sqlite"

    @staticmethod
    def get_databases():
        return [filename for filename in os.listdir("db")]

    @staticmethod
    def get_smallest_db():
        smallest_db = min(
            ShardingManager.get_databases(), key=lambda db: os.path.getsize(f"db/{db}")
        )
        return os.path.splitext(smallest_db)[0]

    @staticmethod
    def _get_posts_table_by_db(db_file: str):
        db = os.path.splitext(db_file)[0]
        return "posts" if db == "db1" else f"{db}.posts"

    @staticmethod
    def create_new_database():
        engine = create_engine(f"sqlite:///db/{ShardingManager.DB1_NAME}")
        Session = sessionmaker(bind=engine)
        session = Session()
        new_db_filename = f"db{len(ShardingManager.get_databases()) + 1}.sqlite"
        file_prefix = os.path.splitext(new_db_filename)[0]
        session.execute(text(f"ATTACH DATABASE 'db/{new_db_filename}' AS {file_prefix}"))
        session.execute(text(f"CREATE TABLE {file_prefix}.posts AS SELECT * FROM posts WHERE 0"))
        session.commit()
        session.close()

    @staticmethod
    def generate_union_posts_query(fields: str = "*") -> str:
        union_queries = []
        for filename in ShardingManager.get_databases():
            table_name = ShardingManager._get_posts_table_by_db(filename)
            union_queries.append(f"SELECT {fields} FROM {table_name}")
        return " UNION ALL ".join(union_queries)

    @staticmethod
    def attach_databases(session: Session, *args):
        if databases := ShardingManager.get_databases():
            for filename in databases:
                if filename.endswith(".sqlite") and filename != ShardingManager.DB1_NAME:
                    session.execute(
                        f"ATTACH DATABASE 'db/{filename}' AS {os.path.splitext(filename)[0]}"
                    )

    @staticmethod
    def manage_database_size(*args):
        smallest_db = ShardingManager.get_smallest_db()
        file_size = os.path.getsize(f"db/{smallest_db}.sqlite")
        if file_size > ShardingManager.MAX_FILE_SIZE_MB * 1024 * 1024:
            ShardingManager.create_new_database()


class OrderBy(Enum):
    ASC = "ASC"
    DESC = "DESC"


class DatabaseManager:
    def __init__(self):
        engine = create_engine(f"sqlite:///db/{ShardingManager.DB1_NAME}")
        event.listen(engine, "connect", ShardingManager.attach_databases)
        self.Session = sessionmaker(bind=engine)
        self.session = self.Session()
        event.listen(self.session, "after_commit", ShardingManager.manage_database_size)

    def new_post(self, title, content, content_format, path, extra, date, image):
        smallest_db = ShardingManager.get_smallest_db()
        return Post(
            title=title,
            content=content,
            content_format=content_format,
            path=path,
            extra=extra,
            date=date,
            image=image,
            # would be nice do it better, but sqlalchemy orm has no support
            schema=smallest_db if smallest_db != "db1" else None,
        )

    def count_total_posts(self):
        union_query = ShardingManager.generate_union_posts_query(fields="title, content")
        return self.session.execute(text(f"SELECT COUNT(*) FROM ({union_query})")).fetchone()[0]

    def get_posts(
        self,
        page: int = 1,
        limit: int = 200,
        order_by: OrderBy = OrderBy.DESC,
        filters: list = None,
        exclude_filters: list = None,
    ):
        filters = filters or []
        exclude_filters = exclude_filters or []

        offset = (page - 1) * limit
        union_query = ShardingManager.generate_union_posts_query()

        where_clauses = []
        exclude_clauses = []
        parameters = {}

        for filter in filters:
            for field, value in filter.items():
                if field == "extra":
                    where_clauses.append(f"{field} LIKE :{field}")
                    parameters[field] = f"%{value}%"
                else:
                    where_clauses.append(f"{field} = :{field}")
                    parameters[field] = value

        for filter in exclude_filters:
            for field, value in filter.items():
                if field == "extra":
                    exclude_clauses.append(f"{field} NOT LIKE :exclude_{field}")
                    parameters[f"exclude_{field}"] = f"%{value}%"
                else:
                    exclude_clauses.append(f"{field} != :exclude_{field}")
                    parameters[f"exclude_{field}"] = value

        where_clause = (
            " AND ".join(where_clauses + exclude_clauses)
            if where_clauses or exclude_clauses
            else "1=1"
        )

        query = f"""
            SELECT * FROM ({union_query}) AS all_posts
            WHERE {where_clause}
            ORDER BY date {order_by.value}
            LIMIT :limit OFFSET :offset
        """

        parameters["limit"] = limit
        parameters["offset"] = offset

        result = self.session.execute(text(query), parameters)
        posts = result.fetchall()
        posts_dicts = []
        for post_tuple in posts:
            post_dict = {}
            for idx, column in enumerate(result.keys()):
                post_dict[column] = post_tuple[idx]
            posts_dicts.append(post_dict)
        return [Post(**post_dict) for post_dict in posts_dicts]

    def _fetch_pagination_mapped(self, offset: int = 0, limit: int = 200):
        union_query = ShardingManager.generate_union_posts_query()
        query = f"SELECT * FROM ({union_query}) AS all_posts LIMIT :limit OFFSET :offset"
        result = self.session.execute(text(query), {"limit": limit, "offset": offset})
        posts = result.fetchall()
        posts_dicts = []
        for post_tuple in posts:
            post_dict = {}
            for idx, column in enumerate(result.keys()):
                post_dict[column] = post_tuple[idx]
            posts_dicts.append(post_dict)
        return [Post(**post_dict) for post_dict in posts_dicts]

    def generator_page_posts(self, total_by_page: int = 200, max_posts_server: int = None):
        total = self.count_total_posts()
        fetched = 0
        offset = 0

        if max_posts_server and total_by_page >= max_posts_server:
            total_by_page = max_posts_server

        while fetched < total:
            posts = self._fetch_pagination_mapped(offset=offset, limit=total_by_page)
            fetched += len(posts)
            offset = offset + total_by_page
            yield posts
            if max_posts_server and fetched >= max_posts_server:
                break
