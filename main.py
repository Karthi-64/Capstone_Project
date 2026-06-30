# main.py  ─  FolderGuardian  entry point
#
# Usage
# ─────
#   python main.py folder1 [folder2] [folder3] [folder4]
#   python main.py   (uses ./watched_folder by default)
#
# Requirements
# ────────────
#   pip install -r requirements.txt

import sys
import os
import shutil
import threading
import queue
import time
import logging
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from file_info import MONITORED_EXTENSIONS

log_format = '[%(asctime)s] %(levelname)s  %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format, datefmt='%H:%M:%S')
log = logging.getLogger('FolderGuardian')

IGNORED_NAMES = {
    '.DS_Store', '.DS_Store?', '._DS_Store',
    'Thumbs.db', 'desktop.ini', '.localized',
    '.Spotlight-V100', '.fseventsd', '.Trashes',
}

# How long to wait for a matching on_moved after on_created (seconds)
MOVE_WINDOW = 1.0
# How long to collect files into a batch before showing popup (seconds)
BATCH_WINDOW = 2.0


# ═══════════════════════════════════════════════════════════════
#  Allow / Deny
# ═══════════════════════════════════════════════════════════════

def handle_allow(filepath: str):
    log.info(f"✓ ALLOWED  →  {Path(filepath).name}")


def handle_deny(filepath: str, origin: str | None = None):
    src = Path(filepath)
    if not src.exists():
        log.warning(f"✕ DENY  →  {src.name} no longer exists, nothing to return.")
        return
    if origin:
        dest = Path(origin)
        if dest.exists():
            ts   = int(time.time())
            dest = dest.parent / f"{dest.stem}_{ts}{dest.suffix}"
        try:
            shutil.move(str(src), str(dest))
            log.info(f"✕ DENIED   →  {src.name}  (returned to {dest.parent})")
        except Exception as e:
            log.warning(f"Could not return {src.name} to origin: {e}")
    else:
        try:
            src.unlink()   # delete denied copied file
            log.info(f"✕ DENIED   →  {src.name}  (removed)")
        except Exception as e:
            log.warning(f"Could not remove denied file {src.name}: {e}")


# ═══════════════════════════════════════════════════════════════
#  File-system event handler
#  KEY FIX: pending-window approach solves macOS on_created → on_moved race
# ═══════════════════════════════════════════════════════════════

class FolderHandler(FileSystemEventHandler):
    TEMP_SUFFIXES = {'.tmp', '.part', '.crdownload', '.download', '.swp', '.lock'}

    def __init__(self, folder: str, file_queue: queue.Queue):
        super().__init__()
        self.folder     = str(Path(folder).resolve())
        self.file_queue = file_queue
        # pending: filename → {'dest': str, 'origin': str|None, 'timer': Timer}
        self._pending: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _is_relevant(self, path_str: str) -> bool:
        p   = Path(path_str)
        ext = p.suffix.lower()
        if str(p.parent.resolve()) != self.folder:            return False
        if p.name in IGNORED_NAMES or p.name.startswith('._'): return False
        if ext not in MONITORED_EXTENSIONS:                    return False
        if ext in self.TEMP_SUFFIXES or p.name.startswith('~'): return False
        return True

    def _commit(self, filename: str):
        """Called by timer after MOVE_WINDOW — file is ready to queue."""
        with self._lock:
            entry = self._pending.pop(filename, None)
        if not entry:
            return
        dest   = entry['dest']
        origin = entry['origin']
        if Path(dest).exists():
            self.file_queue.put((dest, origin))
            log.info(f"Queued  →  {filename}"
                     + (f"  (from {Path(origin).parent})" if origin else "  (copied in)"))

    def on_created(self, event):
        if event.is_directory or not self._is_relevant(event.src_path):
            return
        p        = Path(event.src_path)
        filename = p.name
        resolved = str(p.resolve())

        with self._lock:
            if filename in self._pending:
                # Already seen — cancel old timer, keep existing origin if any
                self._pending[filename]['timer'].cancel()
            timer = threading.Timer(MOVE_WINDOW, self._commit, args=[filename])
            self._pending[filename] = {
                'dest':   resolved,
                'origin': self._pending.get(filename, {}).get('origin'),
                'timer':  timer,
            }
            timer.start()

    def on_moved(self, event):
        if event.is_directory or not self._is_relevant(event.dest_path):
            return
        dest_p   = Path(event.dest_path)
        filename = dest_p.name
        resolved = str(dest_p.resolve())
        origin   = event.src_path

        with self._lock:
            if filename in self._pending:
                # Upgrade the pending entry with the real origin
                self._pending[filename]['timer'].cancel()
            timer = threading.Timer(MOVE_WINDOW, self._commit, args=[filename])
            self._pending[filename] = {
                'dest':   resolved,
                'origin': origin,
                'timer':  timer,
            }
            timer.start()


# ═══════════════════════════════════════════════════════════════
#  Batch collector + dispatcher
# ═══════════════════════════════════════════════════════════════

def dispatch_popups(file_queue: queue.Queue, folders: list[str]):
    """
    Collects files that arrive within BATCH_WINDOW of each other,
    shows ONE BatchGuardianPopup, then for each allowed file:
      1. Shows the step-choice popup (2-step vs 4-step)
      2. Shows the processing popup (live pipeline progress, auto-closes)

    All popups run sequentially on the main thread (Tkinter requirement).
    """
    from popup import BatchGuardianPopup
    from step_choice_popup import StepChoicePopup
    from processing_popup import ProcessingPopup

    _pipeline_available = False
    try:
        from v3.pipeline import run_pipeline
        _pipeline_available = True
    except ImportError as exc:
        log.warning(f"V3 pipeline unavailable: {exc}")

    def on_allow(filepath: str):
        handle_allow(filepath)
        if not _pipeline_available or not Path(filepath).exists():
            return

        watched_folder = str(Path(filepath).parent)

        # 1) Ask the user: 2-step or 4-step workflow?
        choice_popup = StepChoicePopup(filepath)
        step_count = choice_popup.run()

        if step_count not in (2, 4):
            log.info(f"No workflow choice made for {Path(filepath).name} — skipping pipeline.")
            return

        log.info(f"User chose {step_count}-step workflow for {Path(filepath).name}")

        # 2) Run the pipeline with a live processing popup
        proc_popup = ProcessingPopup(filepath, watched_folder, step_count, run_pipeline)
        result = proc_popup.run()

        if result.get("error"):
            log.error(f"Pipeline error for {Path(filepath).name}: {result['error']}")
            return

        if result.get("summary_path"):
            log.info(f"RAG summary → {result['summary_path']}")
        if result.get("workflow_summary_path"):
            log.info(f"Workflow summary → {result['workflow_summary_path']}")
        if result.get("source_path"):
            log.info(f"Source archived → {result['source_path']}")
        if result.get("analysis_path"):
            log.info(f"Analysis → {result['analysis_path']}")
        if result.get("output_docx_path"):
            log.info(f"Generated DOCX → {result['output_docx_path']}")
        if result.get("reviewed_docx_path"):
            log.info(f"Reviewed DOCX → {result['reviewed_docx_path']}")
        if result.get("review_path"):
            log.info(f"Review notes → {result['review_path']}")

    log.info("Dispatcher ready — waiting for incoming files …\n")

    while True:
        # Block until first file arrives
        try:
            first = file_queue.get(timeout=1)
        except queue.Empty:
            continue

        batch = [first]
        file_queue.task_done()

        # Collect more files that arrive within BATCH_WINDOW
        deadline = time.time() + BATCH_WINDOW
        while time.time() < deadline:
            try:
                item = file_queue.get(timeout=max(0.05, deadline - time.time()))
                batch.append(item)
                file_queue.task_done()
                deadline = time.time() + BATCH_WINDOW   # reset window
            except queue.Empty:
                break

        # Filter out files that vanished while waiting
        batch = [(fp, orig) for fp, orig in batch if Path(fp).exists()]
        if not batch:
            continue

        log.info(f"Batch of {len(batch)} file(s) ready for review.")

        try:
            popup = BatchGuardianPopup(
                batch    = batch,
                on_allow = on_allow,
                on_deny  = handle_deny,
            )
            allowed, denied = popup.run()
            for fp in allowed:
                on_allow(fp)
            for fp, origin in denied:
                handle_deny(fp, origin)
        except Exception as e:
            log.error(f"Popup error: {e}")


# ═══════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) > 1:
        raw_folders = sys.argv[1:]
    else:
        default = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'watched_folder')
        raw_folders = [default]

    if len(raw_folders) > 4:
        log.warning("FolderGuardian supports up to 4 folders. Extra folders ignored.")
        raw_folders = raw_folders[:4]

    folders = []
    for f in raw_folders:
        p = Path(f)
        p.mkdir(parents=True, exist_ok=True)
        folders.append(str(p.resolve()))

    log.info("FolderGuardian  🛡")
    for f in folders:
        log.info(f"  Watching  →  {f}")
    log.info("")

    file_queue: queue.Queue = queue.Queue()
    observer = Observer()
    for folder in folders:
        handler = FolderHandler(folder, file_queue)
        observer.schedule(handler, folder, recursive=False)
    observer.start()

    try:
        dispatch_popups(file_queue, folders)
    except KeyboardInterrupt:
        log.info("\nStopping …")
    finally:
        observer.stop()
        observer.join()
        log.info("FolderGuardian stopped.")


if __name__ == '__main__':
    main()
