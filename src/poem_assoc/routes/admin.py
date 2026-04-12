from __future__ import annotations

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from .. import auth, csrf, repository
from ..db import get_connection
from ..repository import DuplicatePoemError, PoemNotFoundError

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

_VALID_SORTS = frozenset(
    {"title_asc", "title_desc", "created_asc", "created_desc", "updated_asc", "updated_desc"}
)


def _verify_csrf_or_abort() -> None:
    """Abort 400 if the submitted CSRF token is missing or invalid."""
    if not csrf.verify_token(request.form.get("csrf_token", "")):
        abort(400, "CSRF token missing or invalid")


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
    _verify_csrf_or_abort()

    title = request.form.get("title", "").strip()
    text = request.form.get("text", "")

    if not text.strip():
        flash("Poem text is required", "error")
        return render_template("admin/add.html", title=title, text=text), 422

    cfg = current_app.config["POEM_CONFIG"]
    embedding_service = current_app.extensions["embedding"]
    conn = get_connection(cfg.db_path)
    try:
        repository.create_poem(conn, title, text, embedding_service)
    except DuplicatePoemError:
        flash("A poem with this cleaned text already exists", "error")
        return render_template("admin/add.html", title=title, text=text), 422
    except Exception:
        flash("Failed to generate embedding — poem not saved", "error")
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
    _verify_csrf_or_abort()

    title = request.form.get("title", "").strip()
    text = request.form.get("text", "")

    if not text.strip():
        flash("Poem text is required", "error")
        return render_template(
            "admin/edit.html", poem_id=poem_id, title=title, text=text
        ), 422

    cfg = current_app.config["POEM_CONFIG"]
    embedding_service = current_app.extensions["embedding"]
    conn = get_connection(cfg.db_path)
    try:
        repository.update_poem(conn, poem_id, title, text, embedding_service)
    except PoemNotFoundError:
        abort(404)
    except DuplicatePoemError:
        flash("A poem with this cleaned text already exists", "error")
        return render_template(
            "admin/edit.html", poem_id=poem_id, title=title, text=text
        ), 422
    except Exception:
        flash("Failed to generate embedding — poem not saved", "error")
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
