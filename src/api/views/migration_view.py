from flask import jsonify


def pending_migrations_response(migrations: list[dict[str, str]]):
    return jsonify({"pending": migrations, "count": len(migrations)})


def applied_migrations_response(revisions: list[str]):
    return jsonify({"applied": revisions, "count": len(revisions)})
