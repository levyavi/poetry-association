from __future__ import annotations

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from .. import auth, repository
from ..db import get_connection

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

_VALID_SORTS = frozenset(
    {"title_asc", "title_desc", "created_asc", "created_desc", "updated_asc", "updated_desc"}
)


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
