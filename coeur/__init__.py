import toml
import os

# it will be replaced with the tag version on pipeline, this settings is only for local work
pyproject_data = toml.load(os.path.join(os.path.dirname(__file__), "../pyproject.toml"))
version = pyproject_data["tool"]["poetry"]["version"]

__version__ = version
