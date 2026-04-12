from flask import Blueprint, current_app, render_template, request

public_bp = Blueprint("public", __name__)


@public_bp.route("/", methods=["GET"])
def index():
    return render_template("search.html", q="", results=None)


@public_bp.route("/search", methods=["POST"])
def search():
    raw_q = request.form.get("q", "")
    display_q = raw_q.strip()

    if not display_q:
        return render_template("search.html", q="", results=None)

    search_service = current_app.extensions["search"]
    results = search_service.search(display_q)
    return render_template("search.html", q=display_q, results=results)
