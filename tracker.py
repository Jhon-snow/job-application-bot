import json
import csv
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ApplicationTracker:
    def __init__(self, json_path: str, pipeline_path: str):
        self.json_path = json_path
        self.pipeline_path = pipeline_path
        self.applied: dict[str, dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for k, v in raw.items():
                    if isinstance(v, str):
                        portal = k.split("_")[0] if "_" in k else ""
                        self.applied[k] = {
                            "date": v, "portal": portal,
                            "company": "", "title": "",
                        }
                    else:
                        self.applied[k] = v
                logger.info(f"Loaded {len(self.applied)} previously applied jobs")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load applied jobs: {e}")
                self.applied = {}
        else:
            self.applied = {}

    def _save(self):
        """Atomic write so partial files aren't left if the process crashes."""
        tmp_path = self.json_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.applied, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.json_path)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise

    def is_already_applied(self, job_id: str) -> bool:
        return job_id in self.applied

    def mark_applied(
        self, job_id: str, portal: str = "", company: str = "", title: str = "",
    ):
        today = datetime.now().strftime("%Y-%m-%d")
        self.applied[job_id] = {
            "date": today,
            "portal": portal,
            "company": company,
            "title": title,
        }
        self._save()
        logger.info(
            f"Tracked: {job_id} ({company} - {title}) on {today} [{portal}]"
        )
        self._append_pipeline(company, title, today, portal)

    def _append_pipeline(
        self, company: str, title: str, date: str, portal: str = "",
    ):
        file_exists = os.path.exists(self.pipeline_path)
        with open(self.pipeline_path, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "Company", "Role", "Applied Date", "Portal",
                    "Referral", "Interview Status", "Notes",
                ])
            writer.writerow([company, title, date, portal, "No", "Pending", ""])

    def _get_date(self, v) -> str:
        if isinstance(v, dict):
            return v.get("date", "")
        return v

    def _get_portal(self, k: str, v) -> str:
        if isinstance(v, dict):
            return v.get("portal", "")
        return k.split("_")[0] if "_" in k else ""

    def get_today_count(self, portal: str = "") -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        count = 0
        for k, v in self.applied.items():
            if self._get_date(v) != today:
                continue
            if portal and self._get_portal(k, v) != portal:
                continue
            count += 1
        return count

    def get_stats(self) -> dict:
        today = datetime.now().strftime("%Y-%m-%d")
        total = len(self.applied)
        today_count = self.get_today_count()
        by_portal: dict[str, int] = {}
        for k, v in self.applied.items():
            if self._get_date(v) == today:
                p = self._get_portal(k, v)
                by_portal[p] = by_portal.get(p, 0) + 1
        return {
            "total_applied": total,
            "applied_today": today_count,
            "by_portal_today": by_portal,
            "date": today,
        }

    def print_stats(self):
        stats = self.get_stats()
        print(f"\n{'='*50}")
        print(f"  Application Tracker Stats")
        print(f"{'='*50}")
        print(f"  Date:            {stats['date']}")
        print(f"  Applied Today:   {stats['applied_today']}")
        for portal, cnt in stats.get("by_portal_today", {}).items():
            print(f"    {portal:>12s}:   {cnt}")
        print(f"  Total Applied:   {stats['total_applied']}")
        print(f"{'='*50}\n")
