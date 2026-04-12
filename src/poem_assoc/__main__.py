import sys

from .app import create_app


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "import-csv":
        from .cli import import_csv

        sys.exit(import_csv(sys.argv[2:]))

    app = create_app()
    print("poem_assoc running on http://127.0.0.1:5000", flush=True)
    app.run(host="127.0.0.1", port=5000)


if __name__ == "__main__":
    main()
