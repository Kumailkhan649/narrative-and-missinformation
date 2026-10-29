import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent

class ArchitectureTests(unittest.TestCase):
    def test_only_three_project_data_schemas(self):
        migration=(ROOT/"database"/"migrations"/"001_ai08.sql").read_text(encoding="utf-8")
        self.assertEqual(migration.count("CREATE SCHEMA IF NOT EXISTS"),3)
        for schema in ("raw","mock","processed"):
            self.assertIn(f"CREATE SCHEMA IF NOT EXISTS {schema};",migration)
        for prohibited in ("DROP SCHEMA","DROP TABLE","TRUNCATE "):
            self.assertNotIn(prohibited,migration)

    def test_no_sqlite_or_model_training_dependencies(self):
        sources="\n".join(path.read_text(encoding="utf-8") for path in (ROOT/"ai08").glob("*.py"))
        self.assertNotIn("sqlite3",sources)
        dependencies=(ROOT/"requirements.txt").read_text(encoding="utf-8").casefold()
        for package in ("bertopic","sentence-transformers","torch","transformers"):
            self.assertNotIn(package,dependencies)

    def test_container_targets_python_313_postgres_16(self):
        self.assertIn("FROM python:3.13-slim",(ROOT/"Dockerfile").read_text(encoding="utf-8"))
        self.assertIn("image: postgres:16",(ROOT/"compose.yaml").read_text(encoding="utf-8"))
