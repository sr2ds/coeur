import time
from enum import Enum

from coeur.utils import BuildSettings

from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.hybrid import hybrid_property


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

    @hybrid_property
    def permalink(self):
        return f"{settings.get_base_url()}{self.path}/"


def get_db_session(max_retries=5, wait_time=2):
    engine = create_engine(
        f"sqlite:///{settings.database}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    retries = 0
    while retries < max_retries:
        try:
            session = Session()
            session.execute(text("SELECT 1"))
            return session
        except OperationalError:
            retries += 1
            print(
                f"Connection unavailable, attempt {retries} of {max_retries}. Waiting {wait_time} seconds..."
            )
            time.sleep(wait_time)

    raise OperationalError(f"Could not obtain a connection after {max_retries} attempts.")
