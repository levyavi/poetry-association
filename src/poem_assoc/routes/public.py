from flask import Blueprint, render_template, request

public_bp = Blueprint("public", __name__)


@public_bp.route("/", methods=["GET", "POST"])
def index():
    q = request.form.get("q", "").strip() if request.method == "POST" else ""
    return render_template("search.html", q=q)
