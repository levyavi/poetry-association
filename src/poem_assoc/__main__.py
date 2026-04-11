import sys

from .app import create_app


def main() -> None:
    app = create_app()
    print("poem_assoc running on http://127.0.0.1:5000", flush=True)
    app.run(host="127.0.0.1", port=5000)


if __name__ == "__main__":
    main()
