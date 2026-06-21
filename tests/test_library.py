from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.analyzer import Analysis
from src.extractor import Script
from src import library


class LibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = library.DB_PATH
        self.original_scripts_path = library.SCRIPTS_PATH
        root = Path(self.temp_dir.name)
        library.DB_PATH = root / "video_library.sqlite3"
        library.SCRIPTS_PATH = root / "scripts"
        library.initialize()

    def tearDown(self) -> None:
        library.DB_PATH = self.original_db_path
        library.SCRIPTS_PATH = self.original_scripts_path
        self.temp_dir.cleanup()

    def test_video_and_job_lifecycle(self) -> None:
        script = Script(
            video_id="dQw4w9WgXcQ",
            language="en",
            language_name="English",
            is_generated=False,
            is_translated=False,
            text="A short transcript.",
            segments=[{"text": "A short transcript.", "start": 0, "duration": 10}],
        )
        analysis = Analysis(
            video_id=script.video_id,
            language="en",
            summary="Summary",
            key_points=["Point one"],
            deep_dive="Deep dive",
            ai_comments="Comment",
            topics=["testing"],
            word_count=3,
            estimated_watch_minutes=0.2,
            method="claude",
        )

        saved = library.upsert_video(
            "Test video",
            script,
            analysis,
            notion_url="https://notion.so/test",
        )
        self.assertEqual(saved["title"], "Test video")
        self.assertEqual(saved["key_points"], ["Point one"])
        self.assertFalse(saved["is_favorite"])

        favorite = library.update_video_state(script.video_id, is_favorite=True)
        self.assertTrue(favorite["is_favorite"])
        self.assertEqual(len(library.list_videos(favorite=True)), 1)

        job = library.create_job("job-1", script.video_id, script.video_id)
        self.assertEqual(job["status"], "queued")
        completed = library.update_job(
            "job-1",
            status="completed",
            message="done",
            video_id=script.video_id,
        )
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["message"], "done")


if __name__ == "__main__":
    unittest.main()
