from __future__ import annotations

import os
import secrets
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .. import auth, csv_import, csrf, import_state, rebuild, repository
from ..csv_import import CsvFormatError
from ..db import get_connection
from ..repository import DuplicatePoemError, PoemNotFoundError

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _import_session_id() -> str:
    """Return a stable random token stored in the Flask session for keying import state."""
    key = "_import_sid"
    sid = session.get(key)
    if not sid:
        sid = secrets.token_hex(16)
        session[key] = sid
    return sid


@admin_bp.before_request
def _housekeeping():
    import_state.cleanup_expired()


_VALID_SORTS = frozenset(
    {
        "title_asc",
        "title_desc",
        "created_asc",
        "created_desc",
        "updated_asc",
        "updated_desc",
    }
)


def _verify_csrf_or_abort() -> None:
    """Abort 400 if the submitted CSRF token is missing or invalid."""
    if not csrf.verify_token(request.form.get("csrf_token", "")):
        abort(400, "CSRF token missing or invalid")


def _reject_if_rebuilding():
    """If a rebuild is in progress, flash a message and return a redirect."""
    startup_status = current_app.extensions["startup_upgrade"].status()
    if not startup_status.is_write_available():
        if startup_status.state == "running":
            flash("Search data is still being upgraded - write actions are disabled.", "error")
        else:
            flash(
                "Startup search-data upgrade failed - retry the rebuild before changing poems.",
                "error",
            )
        return redirect(url_for("admin.dashboard"))

    lock = current_app.extensions["rebuild_lock"]
    if lock.is_rebuilding():
        flash("Rebuild in progress - write actions are disabled.", "error")
        return redirect(url_for("admin.dashboard"))


@admin_bp.route("/login", methods=["GET", "POST"])
def login_view():
    if request.method == "POST":
        submitted = request.form.get("password", "")
        if auth.verify_password(submitted):
            auth.login()
            flash("Welcome", "success")
            return redirect(url_for("admin.dashboard"))
        flash("Incorrect password", "error")
    return render_template("admin/login.html")


@admin_bp.route("/logout", methods=["POST"])
def logout_view():
    auth.logout()
    flash("Logged out", "info")
    return redirect(url_for("admin.login_view"))


@admin_bp.route("/", methods=["GET"])
@auth.login_required
def dashboard():
    sort = request.args.get("sort", "title_asc")
    if sort not in _VALID_SORTS:
        sort = "title_asc"

    cfg = current_app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    try:
        poems = repository.list_poems(conn, order_by=sort)
    finally:
        conn.close()

    return render_template("admin/dashboard.html", poems=poems, current_sort=sort)


# ── Add ──────────────────────────────────────────────────────────


@admin_bp.route("/poems/new", methods=["GET"])
@auth.login_required
def add_poem_form():
    return render_template("admin/add.html", title="", text="")


@admin_bp.route("/poems", methods=["POST"])
@auth.login_required
def add_poem():
    if (resp := _reject_if_rebuilding()):
        return resp
    _verify_csrf_or_abort()

    title = request.form.get("title", "").strip()
    text = request.form.get("text", "")

    if not title:
        flash("Poem title is required", "error")
        return render_template("admin/add.html", title=title, text=text), 422

    cfg = current_app.config["POEM_CONFIG"]
    embedding_service = current_app.extensions["embedding"]
    lexical_processor = current_app.extensions["lexical"]
    conn = get_connection(cfg.db_path)
    try:
        repository.create_poem(
            conn, title, text, embedding_service, lexical_processor
        )
    except DuplicatePoemError:
        flash("A poem with this title and text already exists", "error")
        return render_template("admin/add.html", title=title, text=text), 422
    except Exception as exc:
        flash(f"Failed to generate search data — poem not saved: {exc}", "error")
        return render_template("admin/add.html", title=title, text=text), 500
    finally:
        conn.close()

    search_service = current_app.extensions["search"]
    search_service.refresh()

    flash("Saved", "success")
    return redirect(url_for("admin.dashboard"))


# ── Edit ─────────────────────────────────────────────────────────


@admin_bp.route("/poems/<int:poem_id>/edit", methods=["GET"])
@auth.login_required
def edit_poem_form(poem_id: int):
    cfg = current_app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    try:
        poem = repository.get_poem(conn, poem_id)
    finally:
        conn.close()

    if poem is None:
        abort(404)

    return render_template(
        "admin/edit.html",
        poem_id=poem_id,
        title=poem["title"],
        text=poem["text"],
    )


@admin_bp.route("/poems/<int:poem_id>/edit", methods=["POST"])
@auth.login_required
def edit_poem(poem_id: int):
    if (resp := _reject_if_rebuilding()):
        return resp
    _verify_csrf_or_abort()

    title = request.form.get("title", "").strip()
    text = request.form.get("text", "")

    if not title:
        flash("Poem title is required", "error")
        return render_template(
            "admin/edit.html", poem_id=poem_id, title=title, text=text
        ), 422

    cfg = current_app.config["POEM_CONFIG"]
    embedding_service = current_app.extensions["embedding"]
    lexical_processor = current_app.extensions["lexical"]
    conn = get_connection(cfg.db_path)
    try:
        repository.update_poem(
            conn,
            poem_id,
            title,
            text,
            embedding_service,
            lexical_processor,
        )
    except PoemNotFoundError:
        abort(404)
    except DuplicatePoemError:
        flash("A poem with this title and text already exists", "error")
        return render_template(
            "admin/edit.html", poem_id=poem_id, title=title, text=text
        ), 422
    except Exception as exc:
        flash(f"Failed to generate search data — poem not saved: {exc}", "error")
        return render_template(
            "admin/edit.html", poem_id=poem_id, title=title, text=text
        ), 500
    finally:
        conn.close()

    search_service = current_app.extensions["search"]
    search_service.refresh()

    flash("Saved", "success")
    return redirect(url_for("admin.dashboard"))


# ── Delete ───────────────────────────────────────────────────────


@admin_bp.route("/poems/<int:poem_id>/delete", methods=["GET"])
@auth.login_required
def delete_poem_confirm(poem_id: int):
    cfg = current_app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    try:
        poem = repository.get_poem(conn, poem_id)
    finally:
        conn.close()

    if poem is None:
        abort(404)

    return render_template("admin/delete_confirm.html", poem=poem)


@admin_bp.route("/poems/<int:poem_id>/delete", methods=["POST"])
@auth.login_required
def delete_poem(poem_id: int):
    if (resp := _reject_if_rebuilding()):
        return resp
    _verify_csrf_or_abort()

    cfg = current_app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    try:
        deleted = repository.delete_poem(conn, poem_id)
    finally:
        conn.close()

    if not deleted:
        flash("Poem not found", "error")
        return redirect(url_for("admin.dashboard"))

    search_service = current_app.extensions["search"]
    search_service.refresh()

    flash("Deleted", "success")
    return redirect(url_for("admin.dashboard"))


# ── CSV Import ──────────────────────────────────────────────────


@admin_bp.route("/import", methods=["GET"])
@auth.login_required
def import_upload():
    return render_template("admin/import_upload.html")


@admin_bp.route("/import/preview", methods=["POST"])
@auth.login_required
def import_preview():
    if (resp := _reject_if_rebuilding()):
        return resp
    _verify_csrf_or_abort()

    uploaded = request.files.get("csv_file")
    if uploaded is None or uploaded.filename == "":
        flash("No file selected", "error")
        return render_template("admin/import_upload.html"), 422

    cfg = current_app.config["POEM_CONFIG"]
    temp_dir = cfg.import_temp_dir
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f"{uuid4()}.csv")

    try:
        uploaded.save(temp_path)
    except Exception:
        flash("Failed to save uploaded file", "error")
        return render_template("admin/import_upload.html"), 500

    conn = get_connection(cfg.db_path)
    try:
        plan = csv_import.plan(conn, temp_path)
    except CsvFormatError as exc:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        flash(str(exc), "error")
        return render_template("admin/import_upload.html"), 422
    finally:
        conn.close()

    sid = _import_session_id()
    import_state.create(sid, plan, temp_path, uploaded.filename or "upload.csv")

    return render_template(
        "admin/import_preview.html",
        filename=uploaded.filename,
        importable=len(plan.importable_rows),
        duplicates=plan.duplicate_count,
    )


@admin_bp.route("/import/confirm", methods=["POST"])
@auth.login_required
def import_confirm():
    if (resp := _reject_if_rebuilding()):
        return resp
    _verify_csrf_or_abort()

    sid = _import_session_id()
    sess = import_state.get(sid)
    if sess is None:
        flash("No pending import — please upload a CSV first", "error")
        return redirect(url_for("admin.import_upload"))

    cfg = current_app.config["POEM_CONFIG"]
    embedding_service = current_app.extensions["embedding"]
    lexical_processor = current_app.extensions["lexical"]
    conn = get_connection(cfg.db_path)
    try:
        result = csv_import.execute(
            conn,
            sess.plan,
            embedding_service,
            lexical_processor,
            cancel_flag=sess.is_cancelled,
        )
    finally:
        conn.close()

    if result.imported > 0:
        search_service = current_app.extensions["search"]
        search_service.refresh()

    import_state.discard(sid)

    return render_template("admin/import_result.html", result=result)


@admin_bp.route("/import/cancel", methods=["POST"])
@auth.login_required
def import_cancel():
    if (resp := _reject_if_rebuilding()):
        return resp
    _verify_csrf_or_abort()

    sid = _import_session_id()
    sess = import_state.get(sid)

    if sess is None:
        flash("No active import to cancel", "info")
        return redirect(url_for("admin.import_upload"))

    sess.cancel()
    import_state.discard(sid)
    flash("Import cancelled", "info")
    return redirect(url_for("admin.import_upload"))


# ── Rebuild ────────────────────────────────────────────────


@admin_bp.route("/rebuild", methods=["POST"])
@auth.login_required
def rebuild_all():
    _verify_csrf_or_abort()

    lock = current_app.extensions["rebuild_lock"]
    startup_upgrade = current_app.extensions["startup_upgrade"]
    if not lock.acquire():
        flash("Rebuild already in progress", "error")
        return redirect(url_for("admin.dashboard"))

    try:
        cfg = current_app.config["POEM_CONFIG"]
        embedding_service = current_app.extensions["embedding"]
        lexical_processor = current_app.extensions["lexical"]
        conn = get_connection(cfg.db_path)
        try:
            result = rebuild.run_rebuild(conn, embedding_service, lexical_processor)
        finally:
            conn.close()

        if result.succeeded:
            search_service = current_app.extensions["search"]
            search_service.refresh()
            startup_upgrade.mark_ready()
        elif startup_upgrade.status().state == "failed":
            startup_upgrade.mark_failed(
                f"Automatic startup upgrade failed after {result.rebuilt}/{result.total} poems: {result.error}"
            )
    finally:
        lock.release()

    if result.error:
        flash(
            f"Rebuild stopped with error after {result.rebuilt}/{result.total} poems: {result.error}",
            "error",
        )
    else:
        flash(f"Rebuilt {result.rebuilt} poems", "success")

    return render_template("admin/rebuild_result.html", result=result)
