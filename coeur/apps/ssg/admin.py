"""
Admin web dashboard for SSG: static HTML + REST API to search, get, list (paginated), and update posts.
Runs with cwd = blog project root (where db/ and config.toml live).
"""

import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from coeur.apps.ssg.db import DatabaseManager, ShardingManager
from pydantic import BaseModel


class PostUpdateBody(BaseModel):
    db: int
    title: str | None = None
    content: str | None = None
    content_format: str | None = None
    path: str | None = None
    extra: str | None = None
    date: str | None = None
    image: str | None = None


def _row_to_dict(row):
    """Convert SQLAlchemy Row or sqlite3.Row to dict."""
    if row is None:
        return None
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return dict(row)


class AdminHandler:
    """Admin web dashboard: serves static UI and REST API for posts (search, get, list, update)."""

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 8000
    DB_DIR = "db"

    def __init__(self, host: str = None, port: int = None):
        self.host = host or self.DEFAULT_HOST
        self.port = port or self.DEFAULT_PORT
        self.static_admin = Path(__file__).resolve().parent / "static" / "admin"
        self._app = FastAPI(title="Coeur SSG Admin")
        self._register_routes()

    def _register_routes(self):
        app = self._app

        @app.get("/")
        def index():
            index_path = self.static_admin / "index.html"
            if not index_path.exists():
                raise HTTPException(status_code=404, detail="Admin static files not found")
            return FileResponse(index_path)

        if self.static_admin.exists():
            app.mount("/static", StaticFiles(directory=str(self.static_admin)), name="static")

        @app.get("/api/databases")
        def api_list_databases():
            return self._api_list_databases()

        @app.get("/api/posts/search")
        def api_search_posts(title: str = Query(..., min_length=1)):
            return self._api_search_posts(title)

        @app.get("/api/posts/by-id")
        def api_get_post_by_id(uuid: str = Query(...), db: int = Query(...)):
            return self._api_get_post_by_id(uuid, db)

        @app.get("/api/posts")
        def api_list_posts(
            db: str = Query("all"),
            page: int = Query(1, ge=1),
            per_page: int = Query(20, ge=1, le=100),
        ):
            return self._api_list_posts(db, page, per_page)

        @app.put("/api/posts/{uuid}")
        def api_update_post(uuid: str, body: PostUpdateBody):
            return self._api_update_post(uuid, body)

    def _get_databases_sorted(self):
        """List of sqlite filenames in db/, sorted by shard number (db1, db2, ...)."""
        files = ShardingManager.get_databases()

        def key(f):
            base = f.replace(".sqlite", "")
            try:
                return int(base.replace("db", ""))
            except ValueError:
                return 0

        return sorted(files, key=key)

    def _api_list_databases(self):
        dbs = self._get_databases_sorted()
        return [{"index": i, "name": f.replace(".sqlite", "")} for i, f in enumerate(dbs, start=1)]

    def _api_search_posts(self, title: str):
        union = ShardingManager.generate_union_posts_query()
        query = f"""
            SELECT * FROM ({union}) AS u
            WHERE title LIKE :title
            ORDER BY date DESC
            LIMIT 50
        """
        db = DatabaseManager()
        try:
            result = db.session.execute(text(query), {"title": f"%{title}%"})
            rows = result.fetchall()
            return [_row_to_dict(r) for r in rows]
        finally:
            db.session.close()

    def _api_get_post_by_id(self, uuid: str, db_index: int):
        dbs = self._get_databases_sorted()
        if db_index < 1 or db_index > len(dbs):
            raise HTTPException(status_code=400, detail=f"db must be between 1 and {len(dbs)}")
        path = os.path.abspath(os.path.join(self.DB_DIR, dbs[db_index - 1]))
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute("SELECT * FROM posts WHERE uuid = ?", (uuid,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Post not found")
            return dict(row)
        finally:
            conn.close()

    def _api_list_posts(self, db: str, page: int, per_page: int):
        dbs = self._get_databases_sorted()
        if not dbs:
            return {"items": [], "total": 0, "page": page, "per_page": per_page}
        offset = (page - 1) * per_page

        if db == "all":
            union = ShardingManager.generate_union_posts_query()
            dbm = DatabaseManager()
            try:
                total = dbm.count_total_posts()
                query = f"""
                    SELECT * FROM ({union}) AS u
                    ORDER BY date DESC
                    LIMIT :limit OFFSET :offset
                """
                result = dbm.session.execute(text(query), {"limit": per_page, "offset": offset})
                rows = result.fetchall()
                items = [_row_to_dict(r) for r in rows]
                return {"items": items, "total": total, "page": page, "per_page": per_page}
            finally:
                dbm.session.close()
        else:
            try:
                db_index = int(db)
            except ValueError:
                raise HTTPException(status_code=400, detail="db must be a number or 'all'")
            if db_index < 1 or db_index > len(dbs):
                raise HTTPException(status_code=400, detail=f"db must be between 1 and {len(dbs)}")
            path = os.path.abspath(os.path.join(self.DB_DIR, dbs[db_index - 1]))
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.execute("SELECT COUNT(*) FROM posts")
                total = cur.fetchone()[0]
                cur = conn.execute(
                    "SELECT * FROM posts ORDER BY date DESC LIMIT ? OFFSET ?",
                    (per_page, offset),
                )
                rows = cur.fetchall()
                items = [dict(r) for r in rows]
                return {"items": items, "total": total, "page": page, "per_page": per_page}
            finally:
                conn.close()

    def _api_update_post(self, uuid: str, body: PostUpdateBody):
        dbs = self._get_databases_sorted()
        if body.db < 1 or body.db > len(dbs):
            raise HTTPException(status_code=400, detail=f"db must be between 1 and {len(dbs)}")
        path = os.path.abspath(os.path.join(self.DB_DIR, dbs[body.db - 1]))
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute("SELECT * FROM posts WHERE uuid = ?", (uuid,))
            old_row = cur.fetchone()
            if old_row is None:
                raise HTTPException(status_code=404, detail="Post not found")
            old = dict(old_row)
            updates = {}
            if body.title is not None:
                updates["title"] = body.title
            if body.content is not None:
                updates["content"] = body.content
            if body.content_format is not None:
                updates["content_format"] = body.content_format
            if body.path is not None:
                updates["path"] = body.path
            if body.extra is not None:
                updates["extra"] = body.extra
            if body.date is not None:
                updates["date"] = body.date
            if body.image is not None:
                updates["image"] = body.image
            if not updates:
                return old
            title_new = updates.get("title", old.get("title", ""))
            content_new = updates.get("content", old.get("content", ""))
            content_old = old.get("content", "")
            print("--- UPDATE POST ---")
            print("uuid:", uuid)
            print("banco: db{}".format(body.db))
            print("titulo:", title_new)
            print("conteudo antigo (primeiros 200 chars):", (content_old[:200] + "..." if len(content_old) > 200 else content_old))
            print("conteudo novo (primeiros 200 chars):", (content_new[:200] + "..." if len(content_new) > 200 else content_new))
            print("-------------------")
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            values = list(updates.values()) + [uuid]
            conn.execute(f"UPDATE posts SET {set_clause} WHERE uuid = ?", values)
            conn.commit()
            cur = conn.execute("SELECT * FROM posts WHERE uuid = ?", (uuid,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def handler(self):
        """Run the admin server (FastAPI + uvicorn)."""
        import uvicorn

        print("You can view and manage your posts at http://{}:{}/".format(self.host, self.port))
        uvicorn.run(self._app, host=self.host, port=self.port, log_level="critical")
