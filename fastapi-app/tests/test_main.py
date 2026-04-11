"""
main.py API 엔드포인트 테스트

실행: pytest tests/ -v
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from datetime import datetime
import mysql.connector

from main import app

client = TestClient(app)


# ── GET / ────────────────────────────────────────────────────────

class TestReadIndex:
    def test_index_calls_file_response(self):
        with patch("main.FileResponse") as mock_fr:
            mock_fr.return_value = MagicMock(status_code=200)
            client.get("/")
            mock_fr.assert_called_once_with("templates/index.html")



def make_mock_db(rows):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = rows
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor




# ── auto-generated: get_db ──────────────────────────────────
# ── auto-generated: get_db ──────────────────────────────────
class TestGetDb:
    def test_get_db_calls_mysql_connect_with_db_config(self):
        mock_config = {
            "host": "localhost",
            "user": "testuser",
            "password": "testpass",
            "database": "testdb",
        }
        mock_conn = MagicMock()

        with patch("main.DB_CONFIG", mock_config), \
             patch("main.mysql.connector.connect", return_value=mock_conn) as mock_connect:
            from main import get_db
            result = get_db()

        mock_connect.assert_called_once_with(**mock_config)
        assert result is mock_conn

    def test_get_db_returns_connection_object(self):
        mock_conn = MagicMock()

        with patch("main.DB_CONFIG", {"host": "localhost"}), \
             patch("main.mysql.connector.connect", return_value=mock_conn):
            from main import get_db
            result = get_db()

        assert result is mock_conn

    def test_get_db_propagates_mysql_error(self):
        with patch("main.DB_CONFIG", {"host": "invalid"}), \
             patch("main.mysql.connector.connect", side_effect=mysql.connector.Error("Connection refused")):
            from main import get_db
            with pytest.raises(mysql.connector.Error, match="Connection refused"):
                get_db()

    def test_get_db_propagates_interface_error(self):
        with patch("main.DB_CONFIG", {"host": "localhost"}), \
             patch("main.mysql.connector.connect", side_effect=mysql.connector.InterfaceError("Cannot connect")):
            from main import get_db
            with pytest.raises(mysql.connector.InterfaceError):
                get_db()

    def test_get_db_passes_all_config_keys(self):
        mock_config = {
            "host": "prod-server",
            "port": 3307,
            "user": "admin",
            "password": "secret",
            "database": "mydb",
            "charset": "utf8mb4",
        }

        with patch("main.DB_CONFIG", mock_config), \
             patch("main.mysql.connector.connect", return_value=MagicMock()) as mock_connect:
            from main import get_db
            get_db()

        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs["host"] == "prod-server"
        assert call_kwargs["port"] == 3307
        assert call_kwargs["user"] == "admin"
        assert call_kwargs["password"] == "secret"
        assert call_kwargs["database"] == "mydb"
        assert call_kwargs["charset"] == "utf8mb4"

    def test_get_db_with_empty_config(self):
        mock_conn = MagicMock()

        with patch("main.DB_CONFIG", {}), \
             patch("main.mysql.connector.connect", return_value=mock_conn) as mock_connect:
            from main import get_db
            result = get_db()

        mock_connect.assert_called_once_with()
        assert result is mock_conn

    def test_get_db_raises_on_generic_exception(self):
        with patch("main.DB_CONFIG", {"host": "localhost"}), \
             patch("main.mysql.connector.connect", side_effect=OSError("Network unreachable")):
            from main import get_db
            with pytest.raises(OSError, match="Network unreachable"):
                get_db()

    def test_get_db_called_multiple_times_returns_separate_connections(self):
        mock_conn_1 = MagicMock(name="conn1")
        mock_conn_2 = MagicMock(name="conn2")

        with patch("main.DB_CONFIG", {"host": "localhost"}), \
             patch("main.mysql.connector.connect", side_effect=[mock_conn_1, mock_conn_2]):
            from main import get_db
            result1 = get_db()
            result2 = get_db()

        assert result1 is mock_conn_1
        assert result2 is mock_conn_2
        assert result1 is not result2

    def test_get_db_does_not_modify_db_config(self):
        original_config = {
            "host": "localhost",
            "user": "root",
            "password": "pass",
            "database": "db",
        }
        config_copy = original_config.copy()

        with patch("main.DB_CONFIG", original_config), \
             patch("main.mysql.connector.connect", return_value=MagicMock()):
            from main import get_db
            get_db()

        assert original_config == config_copy


# ── auto-generated: signup ──────────────────────────────────
class TestSignup:
    def _make_signup_request(self, email="test@example.com", name="TestUser", password="pass123"):
        req = MagicMock()
        req.email = email
        req.name = name
        req.password = password
        return req

    def test_signup_success(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [None, {"id": 1, "email": "test@example.com", "name": "TestUser", "password": "pass123"}]
        mock_cursor.lastrowid = 1

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_response = {"id": 1, "email": "test@example.com", "name": "TestUser"}

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._user_to_response", return_value=mock_response) as mock_utr:
            from main import signup
            req = self._make_signup_request()
            result = signup(req)

        assert result == mock_response
        mock_cursor.execute.assert_any_call("SELECT * FROM users WHERE email = %s", ("test@example.com",))
        mock_cursor.execute.assert_any_call(
            "INSERT INTO users (email, name, password) VALUES (%s, %s, %s)",
            ("test@example.com", "TestUser", "pass123"),
        )
        mock_conn.commit.assert_called_once()
        mock_cursor.execute.assert_any_call("SELECT * FROM users WHERE id = %s", (1,))
        mock_cursor.close.assert_called_once()
        mock_utr.assert_called_once_with({"id": 1, "email": "test@example.com", "name": "TestUser", "password": "pass123"}, mock_conn)

    def test_signup_duplicate_email_raises_400(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1, "email": "dup@example.com", "name": "Existing", "password": "pw"}

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import signup
            req = self._make_signup_request(email="dup@example.com")
            with pytest.raises(HTTPException) as exc_info:
                signup(req)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "이미 가입된 이메일입니다."
        mock_conn.close.assert_called_once()

    def test_signup_duplicate_email_does_not_insert(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1, "email": "dup@example.com"}

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import signup
            req = self._make_signup_request(email="dup@example.com")
            with pytest.raises(HTTPException):
                signup(req)

        # Only the SELECT for email check should have been called, no INSERT
        assert mock_cursor.execute.call_count == 1
        mock_conn.commit.assert_not_called()

    def test_signup_conn_closed_on_success(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [None, {"id": 5, "email": "a@b.com", "name": "A", "password": "p"}]
        mock_cursor.lastrowid = 5

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._user_to_response", return_value={}):
            from main import signup
            signup(self._make_signup_request(email="a@b.com"))

        mock_conn.close.assert_called_once()

    def test_signup_conn_closed_on_insert_exception(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.execute.side_effect = [None, mysql.connector.Error("Insert failed")]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import signup
            req = self._make_signup_request()
            with pytest.raises(mysql.connector.Error, match="Insert failed"):
                signup(req)

        mock_conn.close.assert_called_once()

    def test_signup_conn_closed_on_commit_exception(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit.side_effect = mysql.connector.Error("Commit failed")

        with patch("main.get_db", return_value=mock_conn):
            from main import signup
            req = self._make_signup_request()
            with pytest.raises(mysql.connector.Error, match="Commit failed"):
                signup(req)

        mock_conn.close.assert_called_once()

    def test_signup_passes_correct_lastrowid_to_select(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [None, {"id": 42, "email": "x@y.com", "name": "X", "password": "pw"}]
        mock_cursor.lastrowid = 42

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._user_to_response", return_value={}):
            from main import signup
            signup(self._make_signup_request(email="x@y.com"))

        # Third execute call should be SELECT with lastrowid=42
        calls = mock_cursor.execute.call_args_list
        assert calls[2] == (("SELECT * FROM users WHERE id = %s", (42,)),)

    def test_signup_returns_user_to_response_result(self):
        mock_cursor = MagicMock()
        user_row = {"id": 10, "email": "u@v.com", "name": "U", "password": "secret"}
        mock_cursor.fetchone.side_effect = [None, user_row]
        mock_cursor.lastrowid = 10

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        expected_response = {"id": 10, "email": "u@v.com", "name": "U", "token": "abc"}

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._user_to_response", return_value=expected_response):
            from main import signup
            result = signup(self._make_signup_request(email="u@v.com"))

        assert result is expected_response

    def test_signup_cursor_uses_dictionary_mode(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [None, {"id": 1, "email": "a@b.com", "name": "A", "password": "p"}]
        mock_cursor.lastrowid = 1

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._user_to_response", return_value={}):
            from main import signup
            signup(self._make_signup_request())

# ── auto-generated: login ──────────────────────────────────
class TestLogin:
    def _make_login_request(self, email="test@example.com", password="password123"):
        req = MagicMock()
        req.email = email
        req.password = password
        return req

    def test_login_success_returns_user_to_response_result(self):
        user_row = {"id": 1, "email": "test@example.com", "name": "Test", "password": "password123"}
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = user_row

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        expected_response = {"id": 1, "email": "test@example.com", "name": "Test", "token": "tok123"}

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._user_to_response", return_value=expected_response) as mock_utr:
            from main import login
            result = login(self._make_login_request())

        assert result is expected_response
        mock_utr.assert_called_once_with(user_row, mock_conn)

    def test_login_user_not_found_raises_401(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import login
            with pytest.raises(HTTPException) as exc_info:
                login(self._make_login_request())

        assert exc_info.value.status_code == 401
        assert "이메일 또는 비밀번호가 올바르지 않습니다." in str(exc_info.value.detail)

    def test_login_conn_closed_on_success(self):
        user_row = {"id": 2, "email": "a@b.com", "name": "A", "password": "pw"}
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = user_row

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._user_to_response", return_value={}):
            from main import login
            login(self._make_login_request(email="a@b.com"))

        mock_conn.close.assert_called_once()

    def test_login_conn_closed_on_user_not_found(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import login
            with pytest.raises(HTTPException):
                login(self._make_login_request())

        mock_conn.close.assert_called_once()

    def test_login_conn_closed_on_execute_exception(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = mysql.connector.Error("DB error")

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import login
            with pytest.raises(mysql.connector.Error, match="DB error"):
                login(self._make_login_request())

        mock_conn.close.assert_called_once()

    def test_login_conn_closed_on_user_to_response_exception(self):
        user_row = {"id": 3, "email": "c@d.com", "name": "C", "password": "pw"}
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = user_row

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._user_to_response", side_effect=Exception("response error")):
            from main import login
            with pytest.raises(Exception, match="response error"):
                login(self._make_login_request(email="c@d.com"))

        mock_conn.close.assert_called_once()

    def test_login_executes_correct_query_with_email(self):
        user_row = {"id": 5, "email": "specific@test.com", "name": "S", "password": "pw"}
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = user_row

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._user_to_response", return_value={}):
            from main import login
            login(self._make_login_request(email="specific@test.com"))

        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM users WHERE email = %s", ("specific@test.com",)
        )

    def test_login_cursor_uses_dictionary_mode(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 6, "email": "d@e.com", "name": "D", "password": "pw"}

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._user_to_response", return_value={}):
            from main import login
            login(self._make_login_request(email="d@e.com"))

        mock_conn.cursor.assert_called_once_with(dictionary=True)

    def test_login_cursor_closed_before_user_to_response(self):
        user_row = {"id": 7, "email": "e@f.com", "name": "E", "password": "pw"}
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = user_row

        call_order = []
        mock_cursor.close.side_effect = lambda: call_order.append("cursor_close")

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        def track_user_to_response(user, conn):
            call_order.append("user_to_response")
            return {}

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._user_to_response", side_effect=track_user_to_response):
            from main import login
            login(self._make_login_request(email="e@f.com"))

        assert call_order == ["cursor_close", "user_to_response"]

    def test_login_passes_conn_to_user_to_response(self):
        user_row = {"id": 8, "email": "f@g.com", "name": "F", "password": "pw"}
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = user_row

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._user_to_response", return_value={"ok": True}) as mock_utr:
            from main import login
            login(self._make_login_request(email="f@g.com"))

        args = mock_utr.call_args[0]
        assert args[0] is user_row
        assert args[1] is mock_conn

    def test_login_with_empty_email(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch("main.get_db", return_value=mock_conn):
            from main import login
            with pytest.raises(HTTPException):
                login(self._make_login_request(email=""))

# ── auto-generated: get_keywords ──────────────────────────────────
class TestGetKeywords:
    def test_returns_keywords_for_user(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("python",), ("fastapi",), ("react",)]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            result = get_keywords(user_id=1)

        assert result == ["python", "fastapi", "react"]

    def test_returns_empty_list_when_no_keywords(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            result = get_keywords(user_id=999)

        assert result == []

    def test_executes_correct_query_with_user_id(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            get_keywords(user_id=42)

        mock_cursor.execute.assert_called_once_with(
            "SELECT keyword FROM user_keywords WHERE user_id = %s", (42,)
        )

    def test_cursor_is_closed_after_execution(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("keyword1",)]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            get_keywords(user_id=1)

        mock_cursor.close.assert_called_once()

    def test_connection_is_closed_after_execution(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            get_keywords(user_id=1)

        mock_conn.close.assert_called_once()

    def test_connection_closed_even_when_execute_raises(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB execute error")

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            with pytest.raises(Exception, match="DB execute error"):
                get_keywords(user_id=1)

        mock_conn.close.assert_called_once()

    def test_connection_closed_even_when_fetchall_raises(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = Exception("fetchall error")

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            with pytest.raises(Exception, match="fetchall error"):
                get_keywords(user_id=1)

        mock_conn.close.assert_called_once()

    def test_connection_closed_even_when_cursor_close_raises(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("kw",)]
        mock_cursor.close.side_effect = Exception("cursor close error")

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            with pytest.raises(Exception, match="cursor close error"):
                get_keywords(user_id=1)

        mock_conn.close.assert_called_once()

    def test_returns_single_keyword(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("only_one",)]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            result = get_keywords(user_id=10)

        assert result == ["only_one"]

    def test_returns_many_keywords(self):
        keywords_data = [(f"keyword_{i}",) for i in range(100)]

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = keywords_data

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            result = get_keywords(user_id=5)

        assert len(result) == 100
        assert result[0] == "keyword_0"
        assert result[99] == "keyword_99"

    def test_cursor_closed_before_connection_closed(self):
        call_order = []

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("kw",)]
        mock_cursor.close.side_effect = lambda: call_order.append("cursor_close")

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.close.side_effect = lambda: call_order.append("conn_close")

        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            get_keywords(user_id=1)

        assert call_order == ["cursor_close", "conn_close"]

    def test_get_db_called_once(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn) as mock_get_db:
            from main import get_keywords
            get_keywords(user_id=7)

        mock_get_db.assert_called_once()

    def test_get_db_raises_propagates_exception(self):
        with patch("main.get_db", side_effect=Exception("connection failed")):
            from main import get_keywords
            with pytest.raises(Exception, match="connection failed"):
                get_keywords(user_id=1)

    def test_keywords_with_special_characters(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("키워드",), ("hello world",), ("c++",), ("",), ("a' OR 1=1 --",)
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            result = get_keywords(user_id=3)

        assert result == ["키워드", "hello world", "c++", "", "a' OR 1=1 --"]

        mock_cursor.fetchall.return_value = []
        with patch("main.get_db", return_value=mock_conn):
            from main import get_keywords
            result = get_keywords(user_id=0)
        assert result == []

# ── auto-generated: update_keywords ──────────────────────────────────
class TestUpdateKeywords:
    def test_update_keywords_returns_keywords(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        req = MagicMock()
        req.keywords = ["python", "java", "rust"]

        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            result = update_keywords(user_id=1, req=req)

        assert result == ["python", "java", "rust"]

    def test_update_keywords_deletes_old_keywords_first(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        req = MagicMock()
        req.keywords = ["new_kw"]

        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            update_keywords(user_id=42, req=req)

        first_call = mock_cursor.execute.call_args_list[0]
        assert "DELETE FROM user_keywords" in first_call[0][0]
        assert first_call[0][1] == (42,)

    def test_update_keywords_inserts_each_keyword(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        req = MagicMock()
        req.keywords = ["alpha", "beta", "gamma"]

        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            update_keywords(user_id=5, req=req)

        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT INTO user_keywords" in c[0][0]
        ]
        assert len(insert_calls) == 3
        assert insert_calls[0][0][1] == (5, "alpha")
        assert insert_calls[1][0][1] == (5, "beta")
        assert insert_calls[2][0][1] == (5, "gamma")

    def test_update_keywords_empty_list(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        req = MagicMock()
        req.keywords = []

        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            result = update_keywords(user_id=1, req=req)

        assert result == []
        insert_calls = [
            c for c in mock_cursor.execute.call_args_list
            if "INSERT" in c[0][0]
        ]
        assert len(insert_calls) == 0

    def test_update_keywords_commits_transaction(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        req = MagicMock()
        req.keywords = ["kw1"]

        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            update_keywords(user_id=1, req=req)

        mock_conn.commit.assert_called_once()

    def test_update_keywords_closes_cursor(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        req = MagicMock()
        req.keywords = ["kw1"]

        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            update_keywords(user_id=1, req=req)

        mock_cursor.close.assert_called_once()

    def test_update_keywords_closes_connection_in_finally(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        req = MagicMock()
        req.keywords = ["kw1"]

        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            update_keywords(user_id=1, req=req)

        mock_conn.close.assert_called_once()

    def test_update_keywords_closes_connection_on_insert_error(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = [None, Exception("insert failed")]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        req = MagicMock()
        req.keywords = ["kw1"]

        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            with pytest.raises(Exception, match="insert failed"):
                update_keywords(user_id=1, req=req)

        mock_conn.close.assert_called_once()

    def test_update_keywords_closes_connection_on_delete_error(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("delete failed")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        req = MagicMock()
        req.keywords = ["kw1"]

        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            with pytest.raises(Exception, match="delete failed"):
                update_keywords(user_id=1, req=req)

        mock_conn.close.assert_called_once()

    def test_update_keywords_with_special_characters(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        req = MagicMock()
        req.keywords = ["키워드", "c++", "a' OR 1=1 --", "hello world"]

        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            result = update_keywords(user_id=3, req=req)

        assert result == ["키워드", "c++", "a' OR 1=1 --", "hello world"]

    def test_update_keywords_large_keyword_list(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        keywords = [f"keyword_{i}" for i in range(500)]
        req = MagicMock()
        req.keywords = keywords

        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            result = update_keywords(user_id=10, req=req)

        assert len(result) == 500
        # 1 DELETE + 500 INSERTs
        assert mock_cursor.execute.call_count == 501

    def test_update_keywords_user_id_zero(self):
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        req = MagicMock()
        req.keywords = ["kw"]

        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            result = update_keywords(user_id=0, req=req)

        assert result == ["kw"]
        delete_call = mock_cursor.execute.call_args_list[0]
        assert delete_call[0][1] == (0,)

    def test_update_keywords_negative_user_id(self):
        # negative user_id is passed through to SQL; no application-level validation
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        with patch("main.get_db", return_value=mock_conn):
            from main import update_keywords
            result = update_keywords(user_id=-1, req=MagicMock(keywords=[]))
        assert result == []

# ── auto-generated: get_board_items ──────────────────────────────────
class TestGetBoardItems:
    def test_no_filters_returns_all_items(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"id": 1, "title": "Test", "source_name": "src", "raw_content": "content", "created_at": datetime(2024, 1, 1)},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._row_to_board_item", side_effect=lambda r: r):
            from main import get_board_items
            result = get_board_items(page=1, size=20)

        assert len(result) == 1
        executed_query = mock_cursor.execute.call_args[0][0]
        assert "WHERE" not in executed_query
        assert "ORDER BY created_at DESC" in executed_query
        params = mock_cursor.execute.call_args[0][1]
        assert params == [20, 0]

    def test_category_filter(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        fake_category_map = {"source_a": "cat1", "source_b": "cat1", "source_c": "cat2"}

        with patch("main.get_db", return_value=mock_conn), \
             patch("main.CATEGORY_MAP", fake_category_map), \
             patch("main._row_to_board_item", side_effect=lambda r: r):
            from main import get_board_items
            result = get_board_items(category="cat1", page=1, size=20)

        assert result == []
        executed_query = mock_cursor.execute.call_args[0][0]
        assert "source_name IN" in executed_query
        params = mock_cursor.execute.call_args[0][1]
        assert "source_a" in params
        assert "source_b" in params
        assert "source_c" not in params

    def test_category_filter_no_matching_sources(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        fake_category_map = {"source_a": "cat1"}

        with patch("main.get_db", return_value=mock_conn), \
             patch("main.CATEGORY_MAP", fake_category_map), \
             patch("main._row_to_board_item", side_effect=lambda r: r):
            from main import get_board_items
            result = get_board_items(category="nonexistent_category", page=1, size=20)

        assert result == []
        executed_query = mock_cursor.execute.call_args[0][0]
        assert "WHERE" not in executed_query

    def test_keywords_filter_single_keyword(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._row_to_board_item", side_effect=lambda r: r):
            from main import get_board_items
            result = get_board_items(keywords="python", page=1, size=20)

        executed_query = mock_cursor.execute.call_args[0][0]
        assert "title LIKE %s OR raw_content LIKE %s" in executed_query
        params = mock_cursor.execute.call_args[0][1]
        assert "%python%" in params

    def test_keywords_filter_multiple_keywords(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._row_to_board_item", side_effect=lambda r: r):
            from main import get_board_items
            result = get_board_items(keywords="python,java,rust", page=1, size=20)

        params = mock_cursor.execute.call_args[0][1]
        assert "%python%" in params
        assert "%java%" in params
        assert "%rust%" in params
        executed_query = mock_cursor.execute.call_args[0][0]
        assert executed_query.count("title LIKE %s OR raw_content LIKE %s") == 3
        assert "OR" in executed_query

    def test_category_and_keywords_combined(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        fake_category_map = {"src1": "mycat"}

        with patch("main.get_db", return_value=mock_conn), \
             patch("main.CATEGORY_MAP", fake_category_map), \
             patch("main._row_to_board_item", side_effect=lambda r: r):
            from main import get_board_items
            result = get_board_items(category="mycat", keywords="test", page=1, size=20)

        executed_query = mock_cursor.execute.call_args[0][0]
        assert "WHERE" in executed_query
        assert "AND" in executed_query
        assert "source_name IN" in executed_query
        assert "title LIKE" in executed_query

    def test_pagination_page_1(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._row_to_board_item", side_effect=lambda r: r):
            from main import get_board_items
            get_board_items(page=1, size=10)

        params = mock_cursor.execute.call_args[0][1]
        assert params[-2] == 10  # size
        assert params[-1] == 0   # offset

    def test_pagination_page_3_size_15(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._row_to_board_item", side_effect=lambda r: r):
            from main import get_board_items
            get_board_items(page=3, size=15)

        params = mock_cursor.execute.call_args[0][1]
        assert params[-2] == 15  # size
        assert params[-1] == 30  # offset = (3-1)*15

    def test_empty_keywords_string(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._row_to_board_item", side_effect=lambda r: r):
            from main import get_board_items
            get_board_items(keywords="", page=1, size=20)

        executed_query = mock_cursor.execute.call_args[0][0]
        assert "WHERE" not in executed_query

    def test_keywords_with_whitespace_only(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_board_items
            get_board_items(keywords="   ", page=1, size=20)

# ── auto-generated: get_board_item ──────────────────────────────────
class TestGetBoardItem:
    def test_returns_board_item_when_found(self):
        fake_row = {
            "id": 1,
            "title": "테스트 게시글",
            "raw_content": "내용",
            "source_name": "src1",
            "created_at": datetime(2024, 1, 1),
        }
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = fake_row
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        fake_board_item = {"id": 1, "title": "테스트 게시글"}

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._row_to_board_item", return_value=fake_board_item) as mock_convert:
            from main import get_board_item
            result = get_board_item(1)

        assert result == fake_board_item
        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM contents WHERE id = %s", (1,)
        )
        mock_convert.assert_called_once_with(fake_row)
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_raises_404_when_not_found(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_board_item
            with pytest.raises(HTTPException) as exc_info:
                get_board_item(999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "게시글을 찾을 수 없습니다."
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    def test_cursor_created_with_dictionary_true(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 5, "title": "test"}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._row_to_board_item", side_effect=lambda r: r):
            from main import get_board_item
            get_board_item(5)

        mock_conn.cursor.assert_called_once_with(dictionary=True)

    def test_connection_closed_even_on_cursor_execute_exception(self):
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("DB error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_board_item
            with pytest.raises(Exception, match="DB error"):
                get_board_item(1)

        mock_conn.close.assert_called_once()

    def test_connection_closed_even_on_http_exception(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_board_item
            with pytest.raises(HTTPException):
                get_board_item(0)

        mock_conn.close.assert_called_once()

    def test_passes_correct_item_id_as_tuple(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 42, "title": "hello"}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._row_to_board_item", side_effect=lambda r: r):
            from main import get_board_item
            get_board_item(42)

        args = mock_cursor.execute.call_args[0]
        assert args[1] == (42,)

    def test_with_large_item_id(self):
        large_id = 2**31 - 1
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": large_id, "title": "big id"}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._row_to_board_item", side_effect=lambda r: r):
            from main import get_board_item
            result = get_board_item(large_id)

        assert result["id"] == large_id
        args = mock_cursor.execute.call_args[0]
        assert args[1] == (large_id,)

    def test_row_to_board_item_receives_exact_db_row(self):
        fake_row = {
            "id": 7,
            "title": "특수문자 !@#$%",
            "raw_content": "본문 내용",
            "source_name": "source",
            "created_at": datetime(2025, 6, 15, 12, 0, 0),
            "extra_field": "extra_value",
        }
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = fake_row
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        captured = {}

        def capture_row(row):
            captured["row"] = row
            return row

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._row_to_board_item", side_effect=capture_row):
            from main import get_board_item
            get_board_item(7)

        assert captured["row"] is fake_row

    def test_connection_closed_when_fetchone_raises(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = RuntimeError("fetch failed")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_board_item
            with pytest.raises(RuntimeError, match="fetch failed"):
                get_board_item(10)

        mock_conn.close.assert_called_once()

    def test_connection_closed_when_row_to_board_item_raises(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 3, "title": "test"}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main._row_to_board_item", side_effect=ValueError("conversion error")):
            from main import get_board_item
            with pytest.raises(ValueError, match="conversion error"):
                get_board_item(3)

        mock_conn.close.assert_called_once()


# ── auto-generated: get_recommendation ──────────────────────────────────
class TestGetRecommendation:
    def test_content_not_found_raises_404(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_recommendation
            with pytest.raises(HTTPException) as exc_info:
                get_recommendation(item_id=999, user_id=1)
            assert exc_info.value.status_code == 404
            assert "게시글을 찾을 수 없습니다." in str(exc_info.value.detail)

        mock_conn.close.assert_called_once()

    def test_no_keywords_returns_default_recommendation(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1, "title": "Test", "category": "cat", "raw_content": "body"}
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_recommendation
            result = get_recommendation(item_id=1, user_id=10)

        assert result.itemId == "1"
        assert result.matchScore == 0
        assert "키워드를 설정하면" in result.matchReason
        assert "관심 키워드를 먼저 설정해주세요." in result.preparationTips
        mock_conn.close.assert_called_once()

    def test_with_keywords_calls_llm_and_returns_recommendation(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 5, "title": "AI 뉴스", "category": "기술", "raw_content": "인공지능 관련 기사"}
        mock_cursor.fetchall.return_value = [{"keyword": "AI"}, {"keyword": "기술"}]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        llm_result = {
            "matchScore": 85,
            "matchReason": "AI 키워드와 높은 관련성",
            "preparationTips": ["AI 트렌드를 확인하세요."],
        }

        with patch("main.get_db", return_value=mock_conn), \
             patch("main.get_llm_recommendation", return_value=llm_result) as mock_llm:
            from main import get_recommendation
            result = get_recommendation(item_id=5, user_id=20)

        mock_llm.assert_called_once_with(
            keywords=["AI", "기술"],
            title="AI 뉴스",
            category="기술",
            raw_content="인공지능 관련 기사",
        )
        assert result.itemId == "5"
        assert result.matchScore == 85
        assert result.matchReason == "AI 키워드와 높은 관련성"
        mock_conn.close.assert_called_once()

    def test_content_with_missing_optional_fields(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 3}
        mock_cursor.fetchall.return_value = [{"keyword": "python"}]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        llm_result = {
            "matchScore": 50,
            "matchReason": "부분 일치",
            "preparationTips": [],
        }

        with patch("main.get_db", return_value=mock_conn), \
             patch("main.get_llm_recommendation", return_value=llm_result) as mock_llm:
            from main import get_recommendation
            result = get_recommendation(item_id=3, user_id=7)

        mock_llm.assert_called_once_with(
            keywords=["python"],
            title="",
            category="",
            raw_content="",
        )
        assert result.itemId == "3"
        assert result.matchScore == 50

    def test_connection_closed_on_content_not_found(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_recommendation
            with pytest.raises(HTTPException):
                get_recommendation(item_id=1, user_id=1)

        mock_conn.close.assert_called_once()

    def test_connection_closed_when_llm_raises(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 2, "title": "T", "category": "C", "raw_content": "R"}
        mock_cursor.fetchall.return_value = [{"keyword": "k1"}]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn), \
             patch("main.get_llm_recommendation", side_effect=RuntimeError("LLM error")):
            from main import get_recommendation
            with pytest.raises(RuntimeError, match="LLM error"):
                get_recommendation(item_id=2, user_id=3)

        mock_conn.close.assert_called_once()

    def test_connection_closed_when_fetchall_raises(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1, "title": "T", "category": "C", "raw_content": "R"}
        mock_cursor.fetchall.side_effect = RuntimeError("fetchall failed")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_recommendation
            with pytest.raises(RuntimeError, match="fetchall failed"):
                get_recommendation(item_id=1, user_id=1)

        mock_conn.close.assert_called_once()

    def test_cursor_close_called_when_keywords_empty(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1, "title": "T", "category": "C", "raw_content": "R"}
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("main.get_db", return_value=mock_conn):
            from main import get_recommendation
            get_recommendation(item_id=1, user_id=1)

        mock_cursor.close.assert_called_once()

    def test_cursor_close_called_when_keywords_present(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1, "title": "T", "category": "C", "raw_content": "R"}
        mock_cursor.fetchall.return_value = [{"keyword": "test"}]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        llm_result = {"matchScore": 70, "matchReason": "reason", "preparationTips": []}

        with patch("main.get_db", return_value=mock_conn), \
             patch("main.get_llm_recommendation", return_value=llm_result):
            from main import get_recommendation
            get_recommendation(item_id=1, user_id=1)

        mock_cursor.close.assert_called_once()
