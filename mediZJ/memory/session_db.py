"""
SQLite 会话数据库管理器

功能：
- 持久化存储多轮会话数据（sessions + messages 表）
- 持久化存储个人健康档案（profiles 表，md 文本整体入库）
- 支持按 session_id 查询完整对话历史
- 支持会话列表、删除等 CRUD 操作
- 使用 WAL 模式提升并发读性能

存储路径：memory/data/sessions.db
"""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


# 默认数据库路径
_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "data", "sessions.db"
)


class SessionDB:
    """SQLite 会话数据库管理器（线程安全）"""

    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        if hasattr(self, "_initialized"):
            return

        self.db_path = db_path
        self._local = threading.local()

        # 确保目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # 初始化数据库表
        self._execute(self._create_tables)
        self._execute(self._migrate_tables)

        self._initialized = True
        logger.info(f"SessionDB initialized: {db_path}")

    @classmethod
    def reset(cls):
        """重置单例（仅测试使用，生产代码禁止调用）"""
        cls._instance = None

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    def _execute(self, func, *args, **kwargs):
        """在线程安全的连接上执行操作"""
        conn = self._get_conn()
        try:
            result = func(conn, *args, **kwargs)
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def _create_tables(conn: sqlite3.Connection):
        """创建数据库表"""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id     TEXT PRIMARY KEY,
                user_id        TEXT NOT NULL DEFAULT 'default',
                created_at     TEXT NOT NULL,
                updated_at     TEXT NOT NULL,
                mode           TEXT DEFAULT 'single',
                first_question TEXT DEFAULT '',
                total_tokens   INTEGER DEFAULT 0,
                message_count  INTEGER DEFAULT 0,
                turn_count     INTEGER DEFAULT 0,
                parallel_efficiency  REAL DEFAULT 0,
                information_coverage REAL DEFAULT 0,
                redundancy           REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id         TEXT NOT NULL,
                turn_index         INTEGER NOT NULL,
                role               TEXT NOT NULL,
                    -- 'user' | 'assistant'
                content            TEXT NOT NULL,
                timestamp          TEXT NOT NULL,
                images             TEXT,
                    -- 图片 URL 列表 JSON（user 消息专用）
                agent_events       TEXT,
                    -- SSE 事件列表 JSON
                suggestions        TEXT,
                    -- 建议列表 JSON
                agents_involved    TEXT,
                    -- Agent 列表 JSON
                total_time         REAL DEFAULT 0,
                time_to_first_token REAL,
                    -- 首 token 用时（秒），可空
                total_tokens       INTEGER DEFAULT 0,
                subtasks_completed INTEGER DEFAULT 0,
                mode               TEXT,
                citations          TEXT,
                trace_id           TEXT,
                    -- 知识库引用列表 JSON [{index, doc_id, source, ...}]
                FOREIGN KEY (session_id)
                    REFERENCES sessions(session_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS profiles (
                user_id    TEXT PRIMARY KEY,
                content    TEXT NOT NULL DEFAULT '',
                    -- 档案正文（原 PERSONAL.md 全文）
                pending    TEXT NOT NULL DEFAULT '',
                    -- 待确认暂存（原 PENDING.md 全文）
                updated_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id             TEXT PRIMARY KEY,
                username            TEXT NOT NULL,
                username_normalized TEXT NOT NULL UNIQUE,
                role                TEXT NOT NULL DEFAULT 'user',
                is_active           INTEGER NOT NULL DEFAULT 1,
                created_at          TEXT NOT NULL,
                last_login_at       TEXT
            );

            CREATE TABLE IF NOT EXISTS auth_sessions (
                token_hash   TEXT PRIMARY KEY,
                user_id      TEXT NOT NULL,
                created_at   TEXT NOT NULL,
                expires_at   TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                FOREIGN KEY (user_id)
                    REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS uploads (
                filename      TEXT PRIMARY KEY,
                user_id       TEXT NOT NULL,
                original_name TEXT NOT NULL,
                content_type  TEXT NOT NULL,
                size          INTEGER NOT NULL,
                purpose       TEXT NOT NULL DEFAULT 'chat',
                expires_at    TEXT,
                created_at    TEXT NOT NULL,
                FOREIGN KEY (user_id)
                    REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS health_tasks (
                task_id        TEXT PRIMARY KEY,
                user_id        TEXT NOT NULL,
                task_type      TEXT NOT NULL,
                session_id     TEXT,
                status         TEXT NOT NULL,
                input_snapshot TEXT NOT NULL DEFAULT '{}',
                result         TEXT NOT NULL DEFAULT '{}',
                safety_flags   TEXT NOT NULL DEFAULT '[]',
                trace_id       TEXT,
                expires_at     TEXT,
                created_at     TEXT NOT NULL,
                updated_at     TEXT NOT NULL,
                FOREIGN KEY (user_id)
                    REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS health_task_audit (
                audit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                task_hash      TEXT NOT NULL,
                user_hash      TEXT NOT NULL,
                task_type      TEXT NOT NULL,
                action         TEXT NOT NULL,
                created_at     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS health_task_feedback (
                task_id      TEXT PRIMARY KEY,
                user_id      TEXT NOT NULL,
                rating       TEXT NOT NULL,
                reason_codes TEXT NOT NULL DEFAULT '[]',
                comment      TEXT NOT NULL DEFAULT '',
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL,
                FOREIGN KEY (task_id)
                    REFERENCES health_tasks(task_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS report_documents (
                report_id       TEXT PRIMARY KEY,
                task_id         TEXT NOT NULL UNIQUE,
                user_id         TEXT NOT NULL,
                upload_filename TEXT NOT NULL,
                document_type   TEXT NOT NULL DEFAULT 'other',
                status          TEXT NOT NULL,
                analysis_error  TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL,
                FOREIGN KEY (task_id)
                    REFERENCES health_tasks(task_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id)
                    REFERENCES users(user_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS report_measurements (
                measurement_id   TEXT PRIMARY KEY,
                report_id        TEXT NOT NULL,
                name             TEXT NOT NULL,
                value            TEXT,
                unit             TEXT,
                reference_range  TEXT,
                abnormal_flag    TEXT NOT NULL DEFAULT 'unknown',
                confidence       REAL NOT NULL DEFAULT 0,
                raw_text         TEXT,
                user_confirmed   INTEGER NOT NULL DEFAULT 0,
                unable_to_confirm INTEGER NOT NULL DEFAULT 0,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL,
                FOREIGN KEY (report_id)
                    REFERENCES report_documents(report_id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_msg_session
                ON messages(session_id, turn_index);
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_user
                ON auth_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_uploads_user
                ON uploads(user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_health_tasks_user_type_created
                ON health_tasks(user_id, task_type, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_health_tasks_status
                ON health_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_health_tasks_session
                ON health_tasks(user_id, session_id);
            CREATE INDEX IF NOT EXISTS idx_reports_user_created
                ON report_documents(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_reports_status
                ON report_documents(status);
            CREATE INDEX IF NOT EXISTS idx_report_measurements_report
                ON report_measurements(report_id);
        """)

        now = datetime.now().isoformat()
        conn.execute(
            """
            INSERT INTO users
                (user_id, username, username_normalized, role, is_active,
                 created_at, last_login_at)
            VALUES ('default', 'default', 'default', 'user', 1, ?, NULL)
            ON CONFLICT(user_id) DO NOTHING
            """,
            (now,),
        )

    @staticmethod
    def _migrate_tables(conn: sqlite3.Connection):
        """数据库迁移：为已有表添加新列"""
        migrations = [
            ("sessions", "user_id", "TEXT NOT NULL DEFAULT 'default'"),
            ("sessions", "parallel_efficiency", "REAL DEFAULT 0"),
            ("sessions", "information_coverage", "REAL DEFAULT 0"),
            ("sessions", "redundancy", "REAL DEFAULT 0"),
            ("messages", "citations", "TEXT"),
            ("messages", "images", "TEXT"),
            ("messages", "trace_id", "TEXT"),
            ("messages", "time_to_first_token", "REAL"),
            ("uploads", "purpose", "TEXT NOT NULL DEFAULT 'chat'"),
            ("uploads", "expires_at", "TEXT"),
        ]
        for table, col, col_type in migrations:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass  # 列已存在

        conn.execute(
            "UPDATE sessions SET user_id = 'default' "
            "WHERE user_id IS NULL OR user_id = ''"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_user "
            "ON sessions(user_id, updated_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_uploads_expiry "
            "ON uploads(expires_at)"
        )

    # ========== 用户与登录会话 ==========

    def get_or_create_user(
        self,
        username: str,
        role: str = "user",
    ) -> Dict[str, Any]:
        """按规范化用户名获取用户，不存在时自动创建。"""

        normalized = username.casefold()

        def _do_get_or_create(conn: sqlite3.Connection) -> Dict[str, Any]:
            now = datetime.now().isoformat()
            row = conn.execute(
                "SELECT * FROM users WHERE username_normalized = ?",
                (normalized,),
            ).fetchone()
            if row is None:
                user_id = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO users
                        (user_id, username, username_normalized, role,
                         is_active, created_at, last_login_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                    ON CONFLICT(username_normalized) DO NOTHING
                    """,
                    (user_id, username, normalized, role, now, now),
                )
                conn.execute(
                    """
                    UPDATE OR IGNORE profiles
                    SET user_id = ?
                    WHERE lower(user_id) = ? AND user_id != 'default'
                    """,
                    (user_id, normalized),
                )
                row = conn.execute(
                    "SELECT * FROM users WHERE username_normalized = ?",
                    (normalized,),
                ).fetchone()
            effective_role = "admin" if role == "admin" else row["role"]
            conn.execute(
                """
                UPDATE users
                SET last_login_at = ?, role = ?
                WHERE user_id = ?
                """,
                (now, effective_role, row["user_id"]),
            )
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (row["user_id"],),
            ).fetchone()
            return dict(row)

        return self._execute(_do_get_or_create)

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """按用户 ID 查询账号。"""

        def _do_get(conn: sqlite3.Connection):
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return dict(row) if row else None

        return self._execute(_do_get)

    def save_auth_session(
        self,
        token_hash: str,
        user_id: str,
        expires_at: str,
    ) -> None:
        """保存登录令牌哈希。"""

        def _do_save(conn: sqlite3.Connection):
            now = datetime.now().isoformat()
            conn.execute(
                """
                INSERT INTO auth_sessions
                    (token_hash, user_id, created_at, expires_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (token_hash, user_id, now, expires_at, now),
            )

        self._execute(_do_save)

    def get_auth_session(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """查询登录会话及其用户信息。"""

        def _do_get(conn: sqlite3.Connection):
            row = conn.execute(
                """
                SELECT a.token_hash, a.user_id, a.expires_at,
                       u.username, u.role, u.is_active
                FROM auth_sessions AS a
                JOIN users AS u ON u.user_id = a.user_id
                WHERE a.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE auth_sessions SET last_seen_at = ? "
                    "WHERE token_hash = ?",
                    (datetime.now().isoformat(), token_hash),
                )
            return dict(row) if row else None

        return self._execute(_do_get)

    def delete_auth_session(self, token_hash: str) -> bool:
        """撤销指定登录会话。"""

        def _do_delete(conn: sqlite3.Connection):
            cursor = conn.execute(
                "DELETE FROM auth_sessions WHERE token_hash = ?",
                (token_hash,),
            )
            return cursor.rowcount > 0

        return self._execute(_do_delete)

    def save_upload(
        self,
        filename: str,
        user_id: str,
        original_name: str,
        content_type: str,
        size: int,
        purpose: str = "chat",
        expires_at: Optional[str] = None,
    ) -> None:
        """记录上传文件归属。"""

        def _do_save(conn: sqlite3.Connection):
            conn.execute(
                """
                INSERT INTO uploads
                    (filename, user_id, original_name, content_type,
                     size, purpose, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    user_id,
                    original_name,
                    content_type,
                    size,
                    purpose,
                    expires_at,
                    datetime.now().isoformat(),
                ),
            )

        self._execute(_do_save)

    def get_upload(self, filename: str) -> Optional[Dict[str, Any]]:
        """查询上传文件元数据。"""

        def _do_get(conn: sqlite3.Connection):
            row = conn.execute(
                "SELECT * FROM uploads WHERE filename = ?",
                (filename,),
            ).fetchone()
            return dict(row) if row else None

        return self._execute(_do_get)

    def delete_upload(self, filename: str, user_id: Optional[str] = None) -> bool:
        """Delete upload metadata, optionally enforcing ownership."""

        def _do_delete(conn: sqlite3.Connection) -> bool:
            if user_id is None:
                cursor = conn.execute(
                    "DELETE FROM uploads WHERE filename = ?", (filename,)
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM uploads WHERE filename = ? AND user_id = ?",
                    (filename, user_id),
                )
            return cursor.rowcount > 0

        return self._execute(_do_delete)

    def list_expired_uploads(self, now: Optional[str] = None) -> List[Dict[str, Any]]:
        """List uploads whose explicit retention deadline has passed."""

        def _do_list(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
            rows = conn.execute(
                """
                SELECT * FROM uploads
                WHERE expires_at IS NOT NULL AND expires_at <= ?
                ORDER BY expires_at
                """,
                (now or datetime.now().isoformat(),),
            ).fetchall()
            return [dict(row) for row in rows]

        return self._execute(_do_list)

    # ========== Unified health tasks ==========

    def create_health_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a health task and return the stored row."""

        def _do_create(conn: sqlite3.Connection) -> Dict[str, Any]:
            now = task.get("created_at") or datetime.now().isoformat()
            conn.execute(
                """
                INSERT INTO health_tasks (
                    task_id, user_id, task_type, session_id, status,
                    input_snapshot, result, safety_flags, trace_id,
                    expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task["task_id"],
                    task["user_id"],
                    task["task_type"],
                    task.get("session_id"),
                    task["status"],
                    json.dumps(task.get("input_snapshot") or {}, ensure_ascii=False),
                    json.dumps(task.get("result") or {}, ensure_ascii=False),
                    json.dumps(task.get("safety_flags") or [], ensure_ascii=False),
                    task.get("trace_id"),
                    task.get("expires_at"),
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM health_tasks WHERE task_id = ?",
                (task["task_id"],),
            ).fetchone()
            return dict(row)

        return self._execute(_do_create)

    def get_health_task(
        self, task_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get a task, applying user ownership when supplied."""

        def _do_get(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            if user_id is None:
                row = conn.execute(
                    "SELECT * FROM health_tasks WHERE task_id = ?", (task_id,)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM health_tasks WHERE task_id = ? AND user_id = ?",
                    (task_id, user_id),
                ).fetchone()
            return dict(row) if row else None

        return self._execute(_do_get)

    def list_health_tasks(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        task_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List a user's tasks with optional type and status filters."""

        def _do_list(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
            clauses = ["user_id = ?"]
            params: List[Any] = [user_id]
            if task_type:
                clauses.append("task_type = ?")
                params.append(task_type)
            if status:
                clauses.append("status = ?")
                params.append(status)
            params.extend([limit, offset])
            rows = conn.execute(
                f"SELECT * FROM health_tasks WHERE {' AND '.join(clauses)} "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
            return [dict(row) for row in rows]

        return self._execute(_do_list)

    def count_health_tasks(
        self,
        user_id: str,
        task_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """Count a user's tasks using the same filters as list."""

        def _do_count(conn: sqlite3.Connection) -> int:
            clauses = ["user_id = ?"]
            params: List[Any] = [user_id]
            if task_type:
                clauses.append("task_type = ?")
                params.append(task_type)
            if status:
                clauses.append("status = ?")
                params.append(status)
            row = conn.execute(
                f"SELECT COUNT(*) AS count FROM health_tasks "
                f"WHERE {' AND '.join(clauses)}",
                params,
            ).fetchone()
            return int(row["count"])

        return self._execute(_do_count)

    def list_expired_health_tasks(
        self, now: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Return unfinished tasks past their retention/interaction deadline."""

        def _do_list(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
            rows = conn.execute(
                """
                SELECT * FROM health_tasks
                WHERE expires_at IS NOT NULL
                  AND expires_at <= ?
                  AND status IN ('created', 'collecting', 'processing',
                                 'waiting_confirmation')
                ORDER BY expires_at
                """,
                (now or datetime.now().isoformat(),),
            ).fetchall()
            return [dict(row) for row in rows]

        return self._execute(_do_list)

    def update_health_task(
        self,
        task_id: str,
        user_id: str,
        updates: Dict[str, Any],
        expected_status: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Atomically update an owned task, optionally comparing its status."""

        allowed = {
            "status", "session_id", "input_snapshot", "result", "safety_flags",
            "trace_id", "expires_at",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(f"Unsupported task fields: {sorted(unknown)}")

        def _do_update(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            assignments: List[str] = []
            params: List[Any] = []
            for key, value in updates.items():
                assignments.append(f"{key} = ?")
                if key in {"input_snapshot", "result", "safety_flags"}:
                    value = json.dumps(value, ensure_ascii=False)
                params.append(value)
            assignments.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            where = "task_id = ? AND user_id = ?"
            params.extend([task_id, user_id])
            if expected_status is not None:
                where += " AND status = ?"
                params.append(expected_status)
            cursor = conn.execute(
                f"UPDATE health_tasks SET {', '.join(assignments)} WHERE {where}",
                params,
            )
            if cursor.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM health_tasks WHERE task_id = ? AND user_id = ?",
                (task_id, user_id),
            ).fetchone()
            return dict(row) if row else None

        return self._execute(_do_update)

    def delete_health_task(self, task_id: str, user_id: str) -> bool:
        """Delete an owned task. Related feature tables cascade from this row."""

        def _do_delete(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "DELETE FROM health_tasks WHERE task_id = ? AND user_id = ?",
                (task_id, user_id),
            )
            return cursor.rowcount > 0

        return self._execute(_do_delete)

    def add_health_task_audit(
        self, task_hash: str, user_hash: str, task_type: str, action: str
    ) -> None:
        """Store a content-free audit entry."""

        def _do_add(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO health_task_audit
                    (task_hash, user_hash, task_type, action, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    task_hash,
                    user_hash,
                    task_type,
                    action,
                    datetime.now().isoformat(),
                ),
            )

        self._execute(_do_add)

    def get_health_task_metrics(
        self, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Return aggregate task quality metrics without user content or IDs."""

        def _do_metrics(conn: sqlite3.Connection) -> Dict[str, Any]:
            if user_id is None:
                task_rows = conn.execute(
                    "SELECT task_type, status, result FROM health_tasks"
                ).fetchall()
                report_rows = conn.execute(
                    "SELECT status FROM report_documents"
                ).fetchall()
            else:
                task_rows = conn.execute(
                    "SELECT task_type, status, result FROM health_tasks WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
                report_rows = conn.execute(
                    "SELECT status FROM report_documents WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
            by_type: Dict[str, int] = {}
            by_status: Dict[str, int] = {}
            triage_total = 0
            triage_abandoned = 0
            knowledge_total = 0
            knowledge_empty = 0
            for row in task_rows:
                by_type[row["task_type"]] = by_type.get(row["task_type"], 0) + 1
                by_status[row["status"]] = by_status.get(row["status"], 0) + 1
                if row["task_type"] == "triage":
                    triage_total += 1
                    if row["status"] in {"cancelled", "failed"}:
                        triage_abandoned += 1
                if row["task_type"] == "knowledge_search":
                    knowledge_total += 1
                    try:
                        result = json.loads(row["result"] or "{}")
                    except json.JSONDecodeError:
                        result = {}
                    if result.get("total", 0) == 0:
                        knowledge_empty += 1
            report_total = len(report_rows)
            report_completed = sum(
                1 for row in report_rows if row["status"] == "completed"
            )
            report_failed = sum(
                1 for row in report_rows
                if row["status"] in {"failed", "manual_review"}
            )
            total = len(task_rows)
            completed = by_status.get("completed", 0) + by_status.get(
                "needs_medical_attention", 0
            )
            return {
                "total": total,
                "completion_rate": completed / total if total else 0,
                "by_type": by_type,
                "by_status": by_status,
                "questionnaire_abandonment_rate": (
                    triage_abandoned / triage_total if triage_total else 0
                ),
                "knowledge_empty_rate": (
                    knowledge_empty / knowledge_total if knowledge_total else 0
                ),
                "report_confirmation_rate": (
                    report_completed / report_total if report_total else 0
                ),
                "report_failure_rate": (
                    report_failed / report_total if report_total else 0
                ),
            }

        return self._execute(_do_metrics)

    def upsert_health_task_feedback(
        self,
        task_id: str,
        user_id: str,
        rating: str,
        reason_codes: List[str],
        comment: str,
    ) -> Dict[str, Any]:
        """Store task quality feedback without copying task health content."""

        def _do_upsert(conn: sqlite3.Connection) -> Dict[str, Any]:
            owned = conn.execute(
                "SELECT 1 FROM health_tasks WHERE task_id = ? AND user_id = ?",
                (task_id, user_id),
            ).fetchone()
            if owned is None:
                raise LookupError(task_id)
            now = datetime.now().isoformat()
            conn.execute(
                """
                INSERT INTO health_task_feedback
                    (task_id, user_id, rating, reason_codes, comment,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    rating = excluded.rating,
                    reason_codes = excluded.reason_codes,
                    comment = excluded.comment,
                    updated_at = excluded.updated_at
                """,
                (
                    task_id,
                    user_id,
                    rating,
                    json.dumps(reason_codes, ensure_ascii=False),
                    comment,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM health_task_feedback WHERE task_id = ? AND user_id = ?",
                (task_id, user_id),
            ).fetchone()
            result = dict(row)
            result["reason_codes"] = json.loads(result["reason_codes"])
            return result

        return self._execute(_do_upsert)

    # ========== Report interpretation ==========

    def create_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        def _do_create(conn: sqlite3.Connection) -> Dict[str, Any]:
            now = datetime.now().isoformat()
            conn.execute(
                """
                INSERT INTO report_documents (
                    report_id, task_id, user_id, upload_filename,
                    document_type, status, analysis_error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    report["report_id"], report["task_id"], report["user_id"],
                    report["upload_filename"], report.get("document_type", "other"),
                    report["status"], now, now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM report_documents WHERE report_id = ?",
                (report["report_id"],),
            ).fetchone()
            return dict(row)

        return self._execute(_do_create)

    def get_report(
        self, report_id: str, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        def _do_get(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            if user_id is None:
                row = conn.execute(
                    "SELECT * FROM report_documents WHERE report_id = ?",
                    (report_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM report_documents WHERE report_id = ? AND user_id = ?",
                    (report_id, user_id),
                ).fetchone()
            return dict(row) if row else None

        return self._execute(_do_get)

    def get_report_by_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        def _do_get(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            row = conn.execute(
                "SELECT * FROM report_documents WHERE task_id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

        return self._execute(_do_get)

    def list_reports(
        self, user_id: str, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        def _do_list(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
            rows = conn.execute(
                """
                SELECT * FROM report_documents WHERE user_id = ?
                ORDER BY created_at DESC LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()
            return [dict(row) for row in rows]

        return self._execute(_do_list)

    def update_report(
        self, report_id: str, user_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        allowed = {"status", "document_type", "analysis_error"}
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(f"Unsupported report fields: {sorted(unknown)}")

        def _do_update(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            assignments = [f"{key} = ?" for key in updates]
            params = list(updates.values())
            assignments.append("updated_at = ?")
            params.extend([datetime.now().isoformat(), report_id, user_id])
            cursor = conn.execute(
                f"UPDATE report_documents SET {', '.join(assignments)} "
                "WHERE report_id = ? AND user_id = ?",
                params,
            )
            if cursor.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM report_documents WHERE report_id = ? AND user_id = ?",
                (report_id, user_id),
            ).fetchone()
            return dict(row) if row else None

        return self._execute(_do_update)

    def replace_report_measurements(
        self, report_id: str, measurements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        def _do_replace(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
            conn.execute(
                "DELETE FROM report_measurements WHERE report_id = ?", (report_id,)
            )
            now = datetime.now().isoformat()
            for item in measurements:
                conn.execute(
                    """
                    INSERT INTO report_measurements (
                        measurement_id, report_id, name, value, unit,
                        reference_range, abnormal_flag, confidence, raw_text,
                        user_confirmed, unable_to_confirm, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["measurement_id"], report_id, item["name"],
                        item.get("value"), item.get("unit"),
                        item.get("reference_range"),
                        item.get("abnormal_flag", "unknown"),
                        float(item.get("confidence", 0)), item.get("raw_text"),
                        int(bool(item.get("user_confirmed", False))),
                        int(bool(item.get("unable_to_confirm", False))), now, now,
                    ),
                )
            rows = conn.execute(
                "SELECT * FROM report_measurements WHERE report_id = ? ORDER BY rowid",
                (report_id,),
            ).fetchall()
            return [dict(row) for row in rows]

        return self._execute(_do_replace)

    def list_report_measurements(
        self, report_id: str
    ) -> List[Dict[str, Any]]:
        def _do_list(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
            rows = conn.execute(
                "SELECT * FROM report_measurements WHERE report_id = ? ORDER BY rowid",
                (report_id,),
            ).fetchall()
            return [dict(row) for row in rows]

        return self._execute(_do_list)

    def update_report_measurement(
        self, measurement_id: str, report_id: str, updates: Dict[str, Any]
    ) -> bool:
        allowed = {
            "name", "value", "unit", "reference_range", "abnormal_flag",
            "user_confirmed", "unable_to_confirm",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(f"Unsupported measurement fields: {sorted(unknown)}")

        def _do_update(conn: sqlite3.Connection) -> bool:
            assignments = [f"{key} = ?" for key in updates]
            values = [
                int(bool(value)) if key in {"user_confirmed", "unable_to_confirm"}
                else value
                for key, value in updates.items()
            ]
            assignments.append("updated_at = ?")
            values.extend([datetime.now().isoformat(), measurement_id, report_id])
            cursor = conn.execute(
                f"UPDATE report_measurements SET {', '.join(assignments)} "
                "WHERE measurement_id = ? AND report_id = ?",
                values,
            )
            return cursor.rowcount > 0

        return self._execute(_do_update)

    def delete_report_measurement(
        self, measurement_id: str, report_id: str
    ) -> bool:
        def _do_delete(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "DELETE FROM report_measurements "
                "WHERE measurement_id = ? AND report_id = ?",
                (measurement_id, report_id),
            )
            return cursor.rowcount > 0

        return self._execute(_do_delete)

    def delete_report(self, report_id: str, user_id: str) -> bool:
        def _do_delete(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute(
                "DELETE FROM report_documents WHERE report_id = ? AND user_id = ?",
                (report_id, user_id),
            )
            return cursor.rowcount > 0

        return self._execute(_do_delete)

    def list_stale_reports(self) -> List[Dict[str, Any]]:
        def _do_list(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
            rows = conn.execute(
                "SELECT * FROM report_documents WHERE status IN ('analyzing', 'processing')"
            ).fetchall()
            return [dict(row) for row in rows]

        return self._execute(_do_list)

    # ========== 个人健康档案（profiles 表） ==========

    def get_profile(self, user_id: str) -> Optional[Dict[str, str]]:
        """读取用户档案行，不存在时返回 None"""

        def _do_get(conn: sqlite3.Connection):
            row = conn.execute(
                "SELECT content, pending FROM profiles WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                return None
            return {"content": row["content"], "pending": row["pending"]}

        return self._execute(_do_get)

    def upsert_profile(
        self,
        user_id: str,
        content: Optional[str] = None,
        pending: Optional[str] = None,
    ):
        """写入用户档案，仅更新传入的非 None 列；行不存在则插入"""

        def _do_upsert(conn: sqlite3.Connection):
            now = datetime.now().isoformat()
            conn.execute(
                """
                INSERT INTO profiles (user_id, content, pending, updated_at)
                VALUES (?, '', '', ?)
                ON CONFLICT(user_id) DO NOTHING
                """,
                (user_id, now),
            )
            if content is not None:
                conn.execute(
                    "UPDATE profiles SET content = ?, updated_at = ?"
                    " WHERE user_id = ?",
                    (content, now, user_id),
                )
            if pending is not None:
                conn.execute(
                    "UPDATE profiles SET pending = ?, updated_at = ?"
                    " WHERE user_id = ?",
                    (pending, now, user_id),
                )

        self._execute(_do_upsert)

    def save_turn(
        self,
        session_id: str,
        turn_index: int,
        user_msg: Dict[str, Any],
        assistant_msg: Dict[str, Any],
        user_id: str = "default",
    ):
        """
        保存一轮对话（user + assistant），事务原子写入

        Args:
            session_id: 会话 ID
            turn_index: 轮次索引（从 0 开始）
            user_msg: 用户消息 {role, content, timestamp}
            assistant_msg: 助手消息 {role, content, timestamp, agent_events,
                suggestions, agents_involved, total_time,
                total_tokens, subtasks_completed, mode}
        """

        def _do_save(conn: sqlite3.Connection):
            now = datetime.now().isoformat()

            owner = conn.execute(
                "SELECT user_id FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if owner is not None and owner["user_id"] != user_id:
                raise PermissionError("会话不属于当前用户")

            # UPSERT session 元数据
            conn.execute(
                """
                INSERT INTO sessions
                    (session_id, user_id, created_at, updated_at, mode,
                     first_question, total_tokens, message_count, turn_count,
                     parallel_efficiency, information_coverage, redundancy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    updated_at     = excluded.updated_at,
                    mode           = excluded.mode,
                    total_tokens   = sessions.total_tokens + excluded.total_tokens,
                    message_count  = sessions.message_count + excluded.message_count,
                    turn_count     = sessions.turn_count + 1,
                    parallel_efficiency  = excluded.parallel_efficiency,
                    information_coverage = excluded.information_coverage,
                    redundancy           = excluded.redundancy
                """,
                (
                    session_id,
                    user_id,
                    user_msg.get("timestamp", now),
                    now,
                    assistant_msg.get("mode", "single"),
                    user_msg.get("content", "")[:200],
                    assistant_msg.get("total_tokens", 0),
                    2,  # 每轮 2 条消息
                    1,
                    assistant_msg.get("parallel_efficiency", 0),
                    assistant_msg.get("information_coverage", 0),
                    assistant_msg.get("redundancy", 0),
                ),
            )

            persisted_owner = conn.execute(
                "SELECT user_id FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if persisted_owner["user_id"] != user_id:
                raise PermissionError("会话不属于当前用户")

            # INSERT user message
            images_json = json.dumps(user_msg.get("images") or [], ensure_ascii=False)
            conn.execute(
                """
                INSERT INTO messages
                    (session_id, turn_index, role, content, timestamp, images)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    turn_index,
                    "user",
                    user_msg.get("content", ""),
                    user_msg.get("timestamp", now),
                    images_json,
                ),
            )

            # INSERT assistant message
            agent_events = assistant_msg.get("agent_events")
            suggestions = assistant_msg.get("suggestions")
            agents_involved = assistant_msg.get("agents_involved")
            citations = assistant_msg.get("citations")

            assistant_cursor = conn.execute(
                """
                INSERT INTO messages
                    (session_id, turn_index, role, content, timestamp,
                     agent_events, suggestions,
                     agents_involved, total_time, total_tokens,
                     subtasks_completed, mode, citations, trace_id,
                     time_to_first_token)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    turn_index,
                    "assistant",
                    assistant_msg.get("content", ""),
                    assistant_msg.get("timestamp", now),
                    json.dumps(agent_events, ensure_ascii=False, default=str)
                    if agent_events else None,
                    json.dumps(suggestions, ensure_ascii=False)
                    if suggestions else None,
                    json.dumps(agents_involved, ensure_ascii=False)
                    if agents_involved else None,
                    assistant_msg.get("total_time", 0),
                    assistant_msg.get("total_tokens", 0),
                    assistant_msg.get("subtasks_completed", 0),
                    assistant_msg.get("mode"),
                    json.dumps(citations, ensure_ascii=False, default=str)
                    if citations else None,
                    assistant_msg.get("trace_id"),
                    assistant_msg.get("time_to_first_token"),
                ),
            )
            return {
                "assistant_message_id": str(assistant_cursor.lastrowid),
                "turn_index": turn_index,
            }

        saved = self._execute(_do_save)
        logger.debug(
            f"Saved turn {turn_index} for session {session_id}"
        )
        return saved

    def get_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        获取完整会话（含所有 messages）

        Returns:
            {session_id, created_at, updated_at, mode, ...,
             messages: [{turn_index, role, content, timestamp, agent_events, ...}, ...]}
            不存在时返回 None
        """

        def _do_get(conn: sqlite3.Connection) -> Optional[Dict[str, Any]]:
            if user_id is None:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM sessions "
                    "WHERE session_id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone()
            if not row:
                return None

            session = dict(row)

            msg_rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ?
                ORDER BY turn_index, id
                """,
                (session_id,),
            ).fetchall()

            messages = []
            for mr in msg_rows:
                msg = dict(mr)
                # 反序列化 JSON 字段
                for field in ("agent_events", "suggestions", "agents_involved", "citations", "images"):
                    val = msg.get(field)
                    if val and isinstance(val, str):
                        try:
                            msg[field] = json.loads(val)
                        except (json.JSONDecodeError, TypeError):
                            pass
                messages.append(msg)

            session["messages"] = messages
            return session

        return self._execute(_do_get)

    def get_turn_count(self, session_id: str) -> int:
        """获取当前会话的轮次数量"""

        def _do_count(conn: sqlite3.Connection) -> int:
            row = conn.execute(
                """
                SELECT MAX(turn_index) as max_turn
                FROM messages WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            if row and row["max_turn"] is not None:
                return row["max_turn"] + 1
            return 0

        return self._execute(_do_count)

    def get_recent_turns(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        limit: Optional[int] = 10,
    ) -> List[Dict[str, Any]]:
        """获取最近 N 轮消息（按时间正序返回），用于会话恢复回填短期记忆

        limit 为 None 时返回全部消息。仅反序列化 images 列
        （恢复上下文只需要 role/content/timestamp），避免反序列化大 JSON 字段。
        """

        def _do_get(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
            if user_id is None:
                owner_ok = conn.execute(
                    "SELECT 1 FROM sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone() is not None
            else:
                owner_ok = conn.execute(
                    "SELECT 1 FROM sessions WHERE session_id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone() is not None
            if not owner_ok:
                return []

            sql = """
                SELECT * FROM messages
                WHERE session_id = ?
                ORDER BY turn_index DESC, id DESC
            """
            params: tuple = (session_id,)
            if limit is not None:
                sql += " LIMIT ?"
                params = (session_id, limit * 2)

            rows = conn.execute(sql, params).fetchall()

            messages = []
            for mr in reversed(rows):  # 逆序回正：旧 → 新
                msg = dict(mr)
                images = msg.get("images")
                if images and isinstance(images, str):
                    try:
                        msg["images"] = json.loads(images)
                    except (json.JSONDecodeError, TypeError):
                        pass
                messages.append(msg)
            return messages

        return self._execute(_do_get)

    def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """列出会话摘要，按 updated_at DESC"""

        def _do_list(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
            if user_id is None:
                rows = conn.execute(
                    """
                    SELECT * FROM sessions
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM sessions
                    WHERE user_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (user_id, limit, offset),
                ).fetchall()
            return [dict(r) for r in rows]

        return self._execute(_do_list)

    def count_sessions(self, user_id: Optional[str] = None) -> int:
        """获取会话总数"""

        def _do_count(conn: sqlite3.Connection) -> int:
            if user_id is None:
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM sessions"
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM sessions WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
            return row["cnt"] if row else 0

        return self._execute(_do_count)

    def delete_session(
        self,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """删除会话及其所有 messages（CASCADE）"""

        def _do_delete(conn: sqlite3.Connection) -> bool:
            if user_id is not None:
                owned = conn.execute(
                    "SELECT 1 FROM sessions "
                    "WHERE session_id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone()
                if owned is None:
                    return False
            conn.execute(
                "DELETE FROM messages WHERE session_id = ?",
                (session_id,),
            )
            cursor = conn.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            return cursor.rowcount > 0

        result = self._execute(_do_delete)
        if result:
            logger.debug(f"Deleted session from DB: {session_id}")
        return result
