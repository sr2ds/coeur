import toml
import os

pyproject_data = toml.load(os.path.join(os.path.dirname(__file__), "../pyproject.toml"))
version = pyproject_data["tool"]["poetry"]["version"]

__version__ = version
