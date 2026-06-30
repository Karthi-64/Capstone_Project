# processing_popup.py  ─  FolderGuardian  live pipeline processing popup
#
# Bigger than the guardian/step-choice popups. Shows a scrolling feed of
# what the agent is doing internally (LangGraph nodes, LangChain chains,
# LLM calls). Runs the actual pipeline in a background thread and polls
# a queue for progress messages. Auto-closes itself once the pipeline
# thread signals completion.

import tkinter as tk
import threading
import queue as _queue
from pathlib import Path
from file_info import get_file_info

C = {
    'bg':             '#0F0F13',
    'card':           '#17171F',
    'card_border':    '#2C2C3E',
    'input_bg':       '#1F1F2B',
    'feed_bg':        '#13131A',
    'text_primary':   '#F0F0F8',
    'text_secondary': '#9898B8',
    'text_dim':       '#55556A',
    'accent':         '#6B6BF5',
    'divider':        '#22222E',
    'success':        '#1A8A55',
    'error':          '#8A1A2A',
}

POPUP_W = 560
POPUP_H = 480
POLL_MS = 100
# Once pipeline signals done, keep the final state visible briefly
# before auto-closing so the user can register the outcome.
AUTO_CLOSE_DELAY_MS = 1400


def _cursor(w, cur='arrow'):
    try: w.config(cursor=cur)
    except Exception: pass
    for c in w.winfo_children():
        _cursor(c, cur)


class ProcessingPopup:
    """
    filepath, watched_folder, step_count: identify what to process.
    pipeline_fn: callable(filepath, watched_folder, step_count, progress_queue) -> dict
                 (matches v3.pipeline.run_pipeline's signature)
    """

    def __init__(self, filepath: str, watched_folder: str, step_count: int, pipeline_fn):
        self.filepath = filepath
        self.watched_folder = watched_folder
        self.step_count = step_count
        self.pipeline_fn = pipeline_fn

        self.info = get_file_info(filepath)
        self.progress_queue: _queue.Queue = _queue.Queue()
        self.result: dict = {}
        self._thread_done = False
        self._lines: list[str] = []

        self._build()
        self._start_pipeline()

    # ── Window ──────────────────────────────────────────────────
    def _build(self):
        self.root = tk.Tk()
        self.root.title("")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg=C['bg'], cursor='arrow')
        self.root.resizable(False, False)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - POPUP_W) // 2
        y = (sh - POPUP_H) // 2
        self.root.geometry(f"{POPUP_W}x{POPUP_H}+{x}+{y}")

        outer = tk.Frame(self.root, bg=C['card_border'], padx=1, pady=1, cursor='arrow')
        outer.pack(fill='both', expand=True)
        self.frame = tk.Frame(outer, bg=C['card'], cursor='arrow')
        self.frame.pack(fill='both', expand=True)

        self._build_header()
        self._build_feed()
        self._build_footer()
        _cursor(self.root, 'arrow')

    def _build_header(self):
        hdr = tk.Frame(self.frame, bg=C['card'], padx=20, pady=14, cursor='arrow')
        hdr.pack(fill='x')

        left = tk.Frame(hdr, bg=C['card'], cursor='arrow')
        left.pack(side='left', fill='both', expand=True)

        tk.Label(left, text='◈  Workflow Agent — Processing',
                 fg=C['accent'], bg=C['card'],
                 font=('Helvetica Neue', 12, 'bold'), cursor='arrow').pack(anchor='w')

        name = self.info['name']
        if len(name) > 46: name = name[:43] + '…'
        sub = f"{name}   ·   {self.step_count}-step workflow"
        tk.Label(left, text=sub, fg=C['text_secondary'], bg=C['card'],
                 font=('Helvetica Neue', 9), cursor='arrow').pack(anchor='w', pady=(3, 0))

        self._spinner_lbl = tk.Label(hdr, text='◌', fg=C['accent'], bg=C['card'],
                                     font=('Helvetica Neue', 16), cursor='arrow')
        self._spinner_lbl.pack(side='right')
        self._spin_frames = ['◐', '◓', '◑', '◒']
        self._spin_idx = 0

        tk.Frame(self.frame, bg=C['divider'], height=1, cursor='arrow').pack(fill='x')

    def _build_feed(self):
        wrap = tk.Frame(self.frame, bg=C['feed_bg'], cursor='arrow')
        wrap.pack(fill='both', expand=True, padx=0, pady=0)

        inner = tk.Frame(wrap, bg=C['feed_bg'], padx=18, pady=14, cursor='arrow')
        inner.pack(fill='both', expand=True)

        self._feed_canvas = tk.Canvas(inner, bg=C['feed_bg'], highlightthickness=0, cursor='arrow')
        self._feed_canvas.pack(side='left', fill='both', expand=True)

        self._feed_inner = tk.Frame(self._feed_canvas, bg=C['feed_bg'], cursor='arrow')
        self._feed_window = self._feed_canvas.create_window(
            (0, 0), window=self._feed_inner, anchor='nw'
        )

        def _on_configure(e):
            self._feed_canvas.configure(scrollregion=self._feed_canvas.bbox('all'))
            self._feed_canvas.itemconfig(self._feed_window, width=e.width)

        self._feed_canvas.bind('<Configure>', _on_configure)

        tk.Frame(self.frame, bg=C['divider'], height=1, cursor='arrow').pack(fill='x')

    def _build_footer(self):
        self._footer = tk.Frame(self.frame, bg=C['card'], padx=20, pady=12, cursor='arrow')
        self._footer.pack(fill='x', side='bottom')

        self._status_lbl = tk.Label(self._footer, text='Starting…',
                                    fg=C['text_dim'], bg=C['card'],
                                    font=('Helvetica Neue', 9), cursor='arrow')
        self._status_lbl.pack(anchor='w')

    # ── Feed line ───────────────────────────────────────────────
    def _append_line(self, text: str):
        color = C['text_secondary']
        if text.startswith('✅'):
            color = C['success']
        elif text.startswith('❌'):
            color = C['error']

        lbl = tk.Label(self._feed_inner, text=text, fg=color, bg=C['feed_bg'],
                       font=('Helvetica Neue', 9), anchor='w', justify='left',
                       wraplength=POPUP_W - 70, cursor='arrow')
        lbl.pack(fill='x', pady=2, anchor='w')
        self._feed_inner.update_idletasks()
        self._feed_canvas.configure(scrollregion=self._feed_canvas.bbox('all'))
        self._feed_canvas.yview_moveto(1.0)

    # ── Pipeline thread ─────────────────────────────────────────
    def _start_pipeline(self):
        def _run():
            try:
                self.result = self.pipeline_fn(
                    self.filepath,
                    self.watched_folder,
                    self.step_count,
                    self.progress_queue,
                )
            except Exception as exc:
                self.result = {"error": str(exc)}
            finally:
                self._thread_done = True

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        self.root.after(POLL_MS, self._poll)
        self.root.after(150, self._spin)

    def _spin(self):
        if self._thread_done:
            return
        self._spin_idx = (self._spin_idx + 1) % len(self._spin_frames)
        try:
            self._spinner_lbl.config(text=self._spin_frames[self._spin_idx])
        except Exception:
            return
        self.root.after(150, self._spin)

    def _poll(self):
        drained = False
        while True:
            try:
                msg = self.progress_queue.get_nowait()
            except _queue.Empty:
                break
            else:
                self._append_line(msg)
                self._status_lbl.config(text=msg)
                drained = True

        if self._thread_done and self.progress_queue.empty():
            self._finish()
            return

        self.root.after(POLL_MS, self._poll)

    # ── Finish ──────────────────────────────────────────────────
    def _finish(self):
        try:
            self._spinner_lbl.config(text='✓' if not self.result.get('error') else '✕',
                                     fg=C['success'] if not self.result.get('error') else C['error'])
        except Exception:
            pass

        if self.result.get('error'):
            self._status_lbl.config(text=f"Failed: {self.result['error']}", fg=C['error'])
        else:
            n_outputs = sum(
                1 for k in ('output_docx_path', 'analysis_path', 'review_path', 'summary_path')
                if self.result.get(k)
            )
            self._status_lbl.config(
                text=f"Done — workflow complete, {n_outputs} artifact(s) created. Closing…",
                fg=C['success'],
            )

        # Auto-close after a brief moment so the user sees the outcome
        self.root.after(AUTO_CLOSE_DELAY_MS, self._close)

    def _close(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> dict:
        self.root.mainloop()
        return self.result
