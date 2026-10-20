import argparse
import getpass
import json
from pathlib import Path

from sqlalchemy import select, update

from app.core.security import hash_password
from app.core.config import settings
from app.database.models import Job, User
from app.database.session import make_sessions
from app.services.site_seeding import seed_site


def main():
    parser = argparse.ArgumentParser(description="WatchTower administration")
    commands = parser.add_subparsers(dest="command", required=True)
    user = commands.add_parser("create-user")
    user.add_argument("email")
    user.add_argument("--role", choices=["viewer", "operator", "admin"], default="operator")
    recover = commands.add_parser("recover-job", help="Only after confirming the previous worker is stopped")
    recover.add_argument("job_id")
    seed = commands.add_parser("seed-site", help="Create or update a site and its cameras from a JSON file")
    seed.add_argument("path", type=Path)
    args = parser.parse_args()
    cfg = settings()
    engine, sessions = make_sessions(cfg.database_url)
    if args.command == "seed-site":
        seed_site(sessions, json.loads(args.path.read_text(encoding="utf-8")))
        engine.dispose()
        print("Done")
        return
    with sessions() as db:
        if args.command == "create-user":
            if db.scalar(select(User).where(User.email == args.email.lower())):
                raise SystemExit("User already exists")
            password = getpass.getpass("Password (12+ characters): ")
            if password != getpass.getpass("Confirm password: "):
                raise SystemExit("Passwords differ")
            db.add(User(email=args.email.lower(), role=args.role, password_hash=hash_password(password)))
        else:
            changed = db.execute(
                update(Job)
                .where(Job.id == args.job_id, Job.status == "running")
                .values(status="queued", error=None, attempts=0, started_at=None)
            )
            if changed.rowcount != 1:
                raise SystemExit("No running job found")
        db.commit()
    engine.dispose()
    print("Done")


if __name__ == "__main__":
    main()
