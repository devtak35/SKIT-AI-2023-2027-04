"""Keep API tests away from a developer's persistent local meeting database."""

import os
import tempfile


os.environ["APP_ENV"] = "test"
os.environ.pop("DATABASE_URL", None)
_TEST_DATABASE_DIRECTORY = tempfile.TemporaryDirectory(prefix="skit-ai-tests-")
os.environ["DATABASE_PATH"] = f"{_TEST_DATABASE_DIRECTORY.name}/app.db"
