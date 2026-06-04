# workflow_popup.py  ─  FolderGuardian  AI Workflow Analysis Popup
#
# Shown BEFORE the guardian popup.
# Displays a loading state while the agent runs in a background thread,
# then renders the AI result (workflow placement or new workflow suggestion).

import tkinter as tk
import threading
from pathlib import Path
from file_info import get_file_info
from workflow_store import save_workflow

C = {
    'bg':             '#0F0F13',
    'card':           '#17171F',
    'card_border':    '#2C2C3E',
    'input_bg':       '#1F1F2B',
    'detail_bg':      '#13131A',
    'step_bg':        '#1C1C2A',
    'step_active':    '#252540',
    'step_border':    '#3B3B60',
    'text_primary':   '#F0F0F8',
    'text_secondary': '#9898B8',
    'text_dim':       '#55556A',
    'accent':         '#6B6BF5',
    'accent_dim':     '#4A4ABF',
    'divider':        '#22222E',
    'allow':          '#1A8A55',
    'allow_text':     '#D4F5E3',
    'error':          '#8A1A2A',
}

POPUP_W = 480
POPUP_H = 440
POLL_MS = 120    # how often to check if agent threads are done


def _cursor(w, cur='arrow'):
    try: w.config(cursor=cur)
    except Exception: pass
    for c in w.winfo_children():
        _cursor(c, cur)


class WorkflowPopup:
    """
    Shows AI workflow analysis for all files in the batch.
    Polls agent threads. When all done, renders results.
    User clicks "Continue →" to close and proceed to guardian popup.
    """

    def __init__(self, batch: list, results: dict, threads: list):
        self.batch    = batch      # [(filepath, origin), ...]
        self.results  = results    # filepath → result dict (populated by threads)
        self.threads  = threads    # list of Thread objects
        self._done    = False
        self._current = 0          # which file result is displayed
        self._saved_workflows = set()

        self._build()

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
        x  = (sw - POPUP_W) // 2
        y  = (sh - POPUP_H) // 2
        self.root.geometry(f"{POPUP_W}x{POPUP_H}+{x}+{y}")

        self._build_ui()

    # ── UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        outer = tk.Frame(self.root, bg=C['card_border'], padx=1, pady=1, cursor='arrow')
        outer.pack(fill='both', expand=True)
        self.frame = tk.Frame(outer, bg=C['card'], cursor='arrow')
        self.frame.pack(fill='both', expand=True)

        self._build_header()
        tk.Frame(self.frame, bg=C['divider'], height=1).pack(fill='x')
        self._content_frame = tk.Frame(self.frame, bg=C['card'], cursor='arrow')
        self._content_frame.pack(fill='both', expand=True, padx=0, pady=0)
        self._build_footer()

        self._show_loading()
        self.root.after(POLL_MS, self._poll)

    # ── Header ──────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self.frame, bg=C['card'], padx=20, pady=14, cursor='arrow')
        hdr.pack(fill='x')

        left = tk.Frame(hdr, bg=C['card'], cursor='arrow')
        left.pack(side='left', fill='both', expand=True)

        brand = tk.Frame(left, bg=C['card'], cursor='arrow')
        brand.pack(anchor='w')
        tk.Label(brand, text='◈', fg=C['accent'], bg=C['card'],
                 font=('Helvetica Neue', 10), cursor='arrow').pack(side='left', padx=(0, 6))
        tk.Label(brand, text='Workflow Agent', fg=C['text_primary'], bg=C['card'],
                 font=('Helvetica Neue', 12, 'bold'), cursor='arrow').pack(side='left')

        n = len(self.batch)
        sub = f"Analysing {n} incoming file{'s' if n > 1 else ''}"
        tk.Label(left, text=sub, fg=C['text_secondary'], bg=C['card'],
                 font=('Helvetica Neue', 9), cursor='arrow').pack(anchor='w', pady=(3, 0))

    # ── Footer ──────────────────────────────────────────────────
    def _build_footer(self):
        tk.Frame(self.frame, bg=C['divider'], height=1).pack(fill='x', side='bottom')
        foot = tk.Frame(self.frame, bg=C['card'], padx=20, pady=12,
                        cursor='arrow')
        foot.pack(fill='x', side='bottom')

        # File nav dots (if batch > 1)
        self._nav_frame = tk.Frame(foot, bg=C['card'], cursor='arrow')
        self._nav_frame.pack(side='left')

        self._continue_btn = tk.Label(foot, text='Continue  →',
                                      bg=C['input_bg'], fg=C['text_dim'],
                                      font=('Helvetica Neue', 9, 'bold'),
                                      padx=16, pady=7, cursor='arrow')
        self._continue_btn.pack(side='right')

    def _enable_continue(self):
        self._continue_btn.config(
            bg=C['accent'], fg='white', cursor='hand2')
        self._continue_btn.bind('<Button-1>', lambda e: self._close())
        self._continue_btn.bind('<Enter>', lambda e: self._continue_btn.config(bg=C['accent_dim']))
        self._continue_btn.bind('<Leave>', lambda e: self._continue_btn.config(bg=C['accent']))

    # ── Loading state ────────────────────────────────────────────
    def _show_loading(self):
        self._clear_content()
        wrap = tk.Frame(self._content_frame, bg=C['card'], cursor='arrow')
        wrap.place(relx=.5, rely=.45, anchor='center')

        self._dot_label = tk.Label(wrap, text='Analysing', fg=C['accent'],
                                   bg=C['card'],
                                   font=('Helvetica Neue', 13, 'bold'),
                                   cursor='arrow')
        self._dot_label.pack()
        tk.Label(wrap, text='AI agent is reading the file and workflow context…',
                 fg=C['text_dim'], bg=C['card'],
                 font=('Helvetica Neue', 9), cursor='arrow').pack(pady=(6, 0))
        self._dot_count = 0
        self._animate_dots()

    def _animate_dots(self):
        if self._done:
            return
        dots = '●' * (self._dot_count % 4)
        spaces = '○' * (3 - self._dot_count % 4)
        try:
            self._dot_label.config(text=f"Analysing  {dots}{spaces}")
        except Exception:
            return
        self._dot_count += 1
        self.root.after(400, self._animate_dots)

    # ── Poll for agent completion ────────────────────────────────
    def _poll(self):
        all_done = all(not t.is_alive() for t in self.threads)
        if all_done:
            self._done = True
            self._render_results()
        else:
            self.root.after(POLL_MS, self._poll)

    # ── Render results ───────────────────────────────────────────
    def _render_results(self):
        self._build_nav_dots()
        self._show_result(0)
        self._enable_continue()
        _cursor(self.root, 'arrow')

    def _build_nav_dots(self):
        for w in self._nav_frame.winfo_children():
            w.destroy()
        if len(self.batch) <= 1:
            return
        for i in range(len(self.batch)):
            d = tk.Label(self._nav_frame,
                         text='●' if i == self._current else '○',
                         fg=C['accent'] if i == self._current else C['text_dim'],
                         bg=C['card'], font=('Helvetica Neue', 8),
                         cursor='hand2')
            d.pack(side='left', padx=2)
            d.bind('<Button-1>', lambda e, idx=i: self._show_result(idx))

    def _show_result(self, idx: int):
        self._current = idx
        fp, _  = self.batch[idx]
        result = self.results.get(fp, {})
        info   = get_file_info(fp)
        self._build_nav_dots()
        self._clear_content()

        if 'error' in result:
            self._show_error(result['error'], info)
        elif result.get('workflow_exists'):
            self._show_existing_workflow(result, info)
        else:
            self._show_new_workflow(result, info, fp)

        _cursor(self.root, 'arrow')

    def _clear_content(self):
        for w in self._content_frame.winfo_children():
            w.destroy()

    # ── Result: existing workflow ────────────────────────────────
    def _show_existing_workflow(self, result: dict, info: dict):
        pad = tk.Frame(self._content_frame, bg=C['card'], cursor='arrow')
        pad.pack(fill='both', expand=True, padx=20, pady=16)

        # File pill
        self._file_pill(pad, info)

        # Placement card
        card = tk.Frame(pad, bg=C['step_active'],
                        highlightbackground=C['step_border'],
                        highlightthickness=1, cursor='arrow')
        card.pack(fill='x', pady=(14, 0))

        inner = tk.Frame(card, bg=C['step_active'], padx=16, pady=14, cursor='arrow')
        inner.pack(fill='x')

        step_n = result.get('suggested_step', '?')
        step_nm = result.get('step_name', '')
        wf_name = result.get('workflow_name', '')
        reason  = result.get('reason', '')

        tk.Label(inner, text=f"Step {step_n}", fg=C['accent'], bg=C['step_active'],
                 font=('Helvetica Neue', 9, 'bold'), cursor='arrow').pack(anchor='w')
        tk.Label(inner, text=step_nm, fg=C['text_primary'], bg=C['step_active'],
                 font=('Helvetica Neue', 14, 'bold'), cursor='arrow').pack(anchor='w', pady=(2, 0))
        tk.Label(inner, text=f"in  {wf_name}", fg=C['text_secondary'],
                 bg=C['step_active'],
                 font=('Helvetica Neue', 9), cursor='arrow').pack(anchor='w', pady=(1, 8))

        tk.Frame(inner, bg=C['step_border'], height=1, cursor='arrow').pack(fill='x')

        tk.Label(inner, text=reason, fg=C['text_secondary'], bg=C['step_active'],
                 font=('Helvetica Neue', 9), wraplength=380, justify='left',
                 cursor='arrow').pack(anchor='w', pady=(8, 0))

    # ── Result: new workflow suggestion ─────────────────────────
    def _show_new_workflow(self, result: dict, info: dict, fp: str):
        pad = tk.Frame(self._content_frame, bg=C['card'], cursor='arrow')
        pad.pack(fill='both', expand=True, padx=20, pady=12)

        self._file_pill(pad, info)

        sw = result.get('suggested_workflow', {})
        if not sw:
            self._show_error("Agent returned no workflow suggestion.", info)
            return

        tk.Label(pad, text='No workflow found — suggested structure:',
                 fg=C['text_dim'], bg=C['card'],
                 font=('Helvetica Neue', 8), cursor='arrow').pack(anchor='w', pady=(10, 4))

        wf_name     = sw.get('name', 'New Workflow')
        steps       = sw.get('steps', [])
        target_step = result.get('suggested_step', 1)

        tk.Label(pad, text=wf_name, fg=C['text_primary'], bg=C['card'],
                 font=('Helvetica Neue', 11, 'bold'), cursor='arrow').pack(anchor='w', pady=(0, 8))

        for s in steps:
            active = (s['step'] == target_step)
            bg_col = C['step_active'] if active else C['step_bg']
            bd_col = C['accent'] if active else C['step_border']

            scard = tk.Frame(pad, bg=bg_col,
                             highlightbackground=bd_col,
                             highlightthickness=1, cursor='arrow')
            scard.pack(fill='x', pady=2)
            row = tk.Frame(scard, bg=bg_col, padx=12, pady=6, cursor='arrow')
            row.pack(fill='x')

            tk.Label(row, text=f"  {s['step']}  ", fg=C['accent'] if active else C['text_dim'],
                     bg=bg_col,
                     font=('Helvetica Neue', 9, 'bold'), cursor='arrow').pack(side='left')
            txt = tk.Frame(row, bg=bg_col, cursor='arrow')
            txt.pack(side='left', fill='both', expand=True)
            tk.Label(txt, text=s['name'], fg=C['text_primary'] if active else C['text_secondary'],
                     bg=bg_col,
                     font=('Helvetica Neue', 9, 'bold'), anchor='w',
                     cursor='arrow').pack(fill='x')
            tk.Label(txt, text=s.get('description', ''), fg=C['text_dim'],
                     bg=bg_col,
                     font=('Helvetica Neue', 8), anchor='w',
                     cursor='arrow').pack(fill='x')
            if active:
                tk.Label(row, text='← this file', fg=C['accent'],
                         bg=bg_col,
                         font=('Helvetica Neue', 8, 'bold'),
                         cursor='arrow').pack(side='right')

        # Save workflow button
        folder = str(Path(fp).parent)
        if folder not in self._saved_workflows:
            save_btn = tk.Label(pad, text='＋ Save this workflow',
                                fg=C['accent'], bg=C['input_bg'],
                                font=('Helvetica Neue', 8, 'bold'),
                                padx=10, pady=5, cursor='hand2')
            save_btn.pack(anchor='w', pady=(10, 0))
            save_btn.bind('<Button-1>',
                          lambda e, f=folder, w=sw, b=save_btn: self._save_wf(f, w, b))

    # ── Error state ──────────────────────────────────────────────
    def _show_error(self, msg: str, info: dict):
        pad = tk.Frame(self._content_frame, bg=C['card'], cursor='arrow')
        pad.pack(fill='both', expand=True, padx=20, pady=20)
        self._file_pill(pad, info)
        tk.Label(pad, text='Agent unavailable', fg=C['error'],
                 bg=C['card'],
                 font=('Helvetica Neue', 10, 'bold'), cursor='arrow').pack(anchor='w', pady=(16, 4))
        tk.Label(pad, text=msg, fg=C['text_dim'], bg=C['card'],
                 font=('Helvetica Neue', 8), wraplength=420, justify='left',
                 cursor='arrow').pack(anchor='w')

    # ── File pill ────────────────────────────────────────────────
    def _file_pill(self, parent, info: dict):
        pill = tk.Frame(parent, bg=C['input_bg'], cursor='arrow')
        pill.pack(anchor='w', fill='x')
        inner = tk.Frame(pill, bg=C['input_bg'], padx=10, pady=7, cursor='arrow')
        inner.pack(fill='x')
        tk.Label(inner, text=info['icon'], bg=C['input_bg'],
                 fg=C['text_primary'],
                 font=('Helvetica Neue', 14), cursor='arrow').pack(side='left', padx=(0, 8))
        right = tk.Frame(inner, bg=C['input_bg'], cursor='arrow')
        right.pack(side='left')
        name = info['name']
        if len(name) > 42: name = name[:39] + '…'
        tk.Label(right, text=name, fg=C['text_primary'], bg=C['input_bg'],
                 font=('Helvetica Neue', 9, 'bold'), cursor='arrow').pack(anchor='w')
        tk.Label(right, text=f"{info['type']}  ·  {info['size']}",
                 fg=C['text_dim'], bg=C['input_bg'],
                 font=('Helvetica Neue', 8), cursor='arrow').pack(anchor='w')

    # ── Save workflow ────────────────────────────────────────────
    def _save_wf(self, folder: str, wf: dict, btn: tk.Label):
        try:
            save_workflow(folder, wf)
            self._saved_workflows.add(folder)
            btn.config(text='✓ Workflow saved', fg=C['allow'], cursor='arrow')
            btn.unbind('<Button-1>')
        except Exception as e:
            btn.config(text=f'Error: {e}', fg=C['error'])

    # ── Close ────────────────────────────────────────────────────
    def _close(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()
