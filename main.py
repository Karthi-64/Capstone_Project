# main.py  ─  FolderGuardian  entry point
#
# Usage
# ─────
#   python main.py folder1 [folder2] [folder3] [folder4]
#   python main.py   (uses ./watched_folder by default)
#
# Requirements
# ────────────
#   pip install watchdog anthropic
#   pip install python-docx   (optional)

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
    then shows ONE BatchGuardianPopup for the whole group.
    Optionally shows WorkflowPopup first if agent is available.
    """
    # Import here to keep startup fast and allow graceful missing-deps
    from popup import BatchGuardianPopup

    _agent_available = False
    try:
        from agent import analyse_file
        _agent_available = True
    except ImportError:
        pass

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

        # ── Optional: AI workflow analysis ──────────────────────
# ── Automatic AI workflow organization ─────────────────
        if _agent_available:

            from agent import analyse_file

            for fp, _ in batch:

                if not Path(fp).exists():
                    continue

                parent = str(Path(fp).parent)

                result = analyse_file(
                    fp,
                    parent
                )

                if "error" in result:
                    log.error(
                        f"AI error for {Path(fp).name}: "
                        f"{result['error']}"
                    )
                    continue

                if result.get("empty_file"):
                    log.info(
                        f"Skipping empty file → "
                        f"{Path(fp).name}"
                    )
                    continue

                target = result.get(
                    "target_folder"
                )

                if not target:
                    log.warning(
                        f"No target folder for "
                        f"{Path(fp).name}"
                    )
                    continue

                target_path = Path(target)

                target_path.mkdir(
                    parents=True,
                    exist_ok=True
                )

                destination = (
                    target_path /
                    Path(fp).name
                )

                try:

                    shutil.move(
                        fp,
                        str(destination)
                    )

                    log.info(
                        f"Moved → {destination}"
                    )

                except Exception as e:

                    log.error(
                        f"Move failed: {e}"
                    )

                # ── Guardian batch popup ─────────────────────────────────
                try:
                    popup = BatchGuardianPopup(
                        batch     = batch,
                        on_allow  = handle_allow,
                        on_deny   = handle_deny,
                    )
                    popup.run()
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