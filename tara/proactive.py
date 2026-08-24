import re
import time
import logging
import datetime
import threading
from typing import Optional, Any, Callable

logger = logging.getLogger("tara.proactive")


class ProactiveEngine:
    """
    Lightweight, anti-overengineering proactive intelligence engine for TARA.
    Runs a single non-blocking background thread with strict safety, rate limits, and zero-bloat.
    """

    def __init__(self, orchestrator=None, check_interval_seconds: int = 60):
        self.orchestrator = orchestrator
        self.check_interval = check_interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Rate-limiting state
        self.min_cooldown_seconds = 3600  # 1 hour minimum between notifications
        self.max_daily_notifications = 3
        self.daily_notification_count = 0
        self.last_notification_time: Optional[float] = None
        self.last_notification_date = datetime.date.today()
        self.last_morning_briefing_date: Optional[datetime.date] = None

        # Session duration tracking
        self.session_start_time = time.time()
        self.break_reminder_sent = False

    def is_enabled(self) -> bool:
        """Check if user has proactive reminders enabled in SQLite memory."""
        if not self.orchestrator or not self.orchestrator.memory:
            return True
        facts = self.orchestrator.memory.get_all_facts()
        # Look in general or preferences for 'proactive_mode'
        val = facts.get("general", {}).get("proactive_mode", "enabled")
        return str(val).lower() != "disabled"

    def set_enabled(self, enabled: bool) -> None:
        """Set proactive preference in SQLite memory."""
        if self.orchestrator and self.orchestrator.memory:
            status = "enabled" if enabled else "disabled"
            self.orchestrator.memory.save_fact_safe("preference", "proactive_mode", status)
            logger.info(f"Proactive reminders {status}")

    def generate_morning_briefing(self) -> str:
        """Generate a concise, contextual morning briefing based on facts and episodic memory."""
        if not self.orchestrator or not self.orchestrator.memory:
            return "Good morning. Systems online."

        facts = self.orchestrator.memory.get_all_facts()
        name = facts.get("name", "Sir")
        curr_project = facts.get("current_project")
        summary = self.orchestrator.memory.get_episodic_summary(self.orchestrator.session_id)

        lines = [f"Good morning {name}. Systems online."]
        if curr_project:
            lines.append(f"Your active project is {curr_project}.")
        if summary and "Pending" in summary:
            # Extract pending tasks line if available
            for line in summary.split("\n"):
                if "pending" in line.lower() or "task" in line.lower():
                    lines.append(line.strip("- *# "))
                    break

        return " ".join(lines)

    def check_battery_status(self) -> Optional[str]:
        """Check system battery and return warning if low and discharging."""
        try:
            from tara.tools import get_battery_status
            status_text = get_battery_status()
            match = re.search(r"(\d+)%", status_text)
            if match:
                pct = int(match.group(1))
                is_charging = "charging" in status_text.lower() or "ac attached" in status_text.lower()
                if pct < 20 and not is_charging:
                    return f"Battery is low at {pct}%. Please connect your charger."
        except Exception as e:
            logger.debug(f"Battery check failed: {e}")
        return None

    def check_long_session(self) -> Optional[str]:
        """Detect continuous interaction over 3 hours."""
        elapsed = time.time() - self.session_start_time
        if elapsed >= 3 * 3600 and not self.break_reminder_sent:
            self.break_reminder_sent = True
            return "You have been working continuously for over 3 hours. Consider taking a short break."
        return None

    def check_pending_tasks(self) -> Optional[str]:
        """Retrieve unresolved tasks reminder from episodic memory."""
        if not self.orchestrator or not self.orchestrator.memory:
            return None
        summary = self.orchestrator.memory.get_episodic_summary(self.orchestrator.session_id)
        if summary:
            for line in summary.split("\n"):
                if any(k in line.lower() for k in ["pending task", "unresolved", "to do", "need to"]):
                    clean_line = line.strip("- *# ")
                    return f"Reminder: You have a pending item — {clean_line}"
        return None

    def _can_notify(self) -> bool:
        """Enforce rate limits, daily caps, user preference, and orchestrator idle state."""
        if not self.is_enabled():
            return False

        # Reset daily counter on date change
        today = datetime.date.today()
        if today != self.last_notification_date:
            self.daily_notification_count = 0
            self.last_notification_date = today

        if self.daily_notification_count >= self.max_daily_notifications:
            return False

        now = time.time()
        if self.last_notification_time and (now - self.last_notification_time) < self.min_cooldown_seconds:
            return False

        # Never interrupt active thinking / speech
        if self.orchestrator:
            from tara.orchestrator import State
            if self.orchestrator.state != State.IDLE:
                return False

        return True

    def notify(self, message: str) -> bool:
        """Deliver proactive notification safely via console and voice."""
        if not self._can_notify():
            return False

        self.last_notification_time = time.time()
        self.daily_notification_count += 1
        logger.info(f"Delivering proactive notification ({self.daily_notification_count}/{self.max_daily_notifications}): '{message}'")

        print(f"\n⚡ [TARA Proactive]: {message}\n")

        if self.orchestrator:
            # Commit notice to SQLite turn history
            self.orchestrator.memory.save_message(self.orchestrator.session_id, "assistant", f"[Proactive Notice]: {message}")
            if self.orchestrator.voice_output:
                self.orchestrator.tts.speak(message)

        return True

    def tick(self) -> Optional[str]:
        """Perform one periodic proactive evaluation cycle."""
        if not self._can_notify():
            return None

        # Check 1: Morning briefing
        today = datetime.date.today()
        now_hour = datetime.datetime.now().hour
        if 6 <= now_hour < 12 and self.last_morning_briefing_date != today:
            briefing = self.generate_morning_briefing()
            if self.notify(briefing):
                self.last_morning_briefing_date = today
                return briefing

        # Check 2: Low battery
        batt_msg = self.check_battery_status()
        if batt_msg and self.notify(batt_msg):
            return batt_msg

        # Check 3: Long session break
        session_msg = self.check_long_session()
        if session_msg and self.notify(session_msg):
            return session_msg

        # Check 4: Pending task reminder
        task_msg = self.check_pending_tasks()
        if task_msg and self.notify(task_msg):
            return task_msg

        return None

    def start(self) -> None:
        """Start the background scheduler thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="TARA-ProactiveScheduler")
        self._thread.start()
        logger.info("Proactive intelligence scheduler started.")

    def _run_loop(self) -> None:
        """Background loop executing check interval safely."""
        while not self._stop_event.is_set():
            try:
                self.tick()
            except Exception as e:
                logger.warning(f"Error in proactive scheduler tick: {e}")

            # Sleep in small slices for quick responsive shutdown on stop()
            for _ in range(self.check_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def stop(self) -> None:
        """Signal and cleanly terminate background scheduler thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("Proactive intelligence scheduler stopped.")
