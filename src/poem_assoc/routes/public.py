from flask import Blueprint, current_app, render_template, request, jsonify, abort

from .. import repository
from ..db import get_connection

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


@public_bp.route("/poems/<int:id>", methods=["GET"])
def get_poem(id):
    cfg = current_app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    try:
        poem = repository.get_poem(conn, id)
        if poem is None:
            abort(404)
        return jsonify({
            "id": poem["id"],
            "title": poem["title"],
            "text": poem["text"]
        })
    finally:
        conn.close()
