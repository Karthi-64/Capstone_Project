# step_choice_popup.py  ─  FolderGuardian  2-step vs 4-step workflow choice
#
# Shown right after a file is Allowed. Small, centered, two clear options.

import tkinter as tk
from pathlib import Path
from file_info import get_file_info

C = {
    'bg':             '#0F0F13',
    'card':           '#17171F',
    'card_border':    '#2C2C3E',
    'input_bg':       '#1F1F2B',
    'text_primary':   '#F0F0F8',
    'text_secondary': '#9898B8',
    'text_dim':       '#55556A',
    'accent':         '#6B6BF5',
    'accent_hover':   '#5555DD',
    'divider':        '#22222E',
    'option_bg':      '#1C1C26',
    'option_hover':   '#23233A',
    'option_border':  '#2E2E42',
}

POPUP_W = 420
POPUP_H = 320


def _cursor(w, cur='arrow'):
    try: w.config(cursor=cur)
    except Exception: pass
    for c in w.winfo_children():
        _cursor(c, cur)


class StepChoicePopup:
    """
    Asks the user: 2-step workflow or 4-step workflow?
    Blocking — call .run() then read .choice (2, 4, or None if dismissed).
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.choice: int | None = None
        self.info = get_file_info(filepath)
        self._build()

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
        frame = tk.Frame(outer, bg=C['card'], cursor='arrow')
        frame.pack(fill='both', expand=True)

        # Header
        hdr = tk.Frame(frame, bg=C['card'], padx=20, pady=16, cursor='arrow')
        hdr.pack(fill='x')
        tk.Label(hdr, text='◈  Workflow Agent', fg=C['accent'], bg=C['card'],
                 font=('Helvetica Neue', 12, 'bold'), cursor='arrow').pack(anchor='w')

        name = self.info['name']
        if len(name) > 40: name = name[:37] + '…'
        tk.Label(hdr, text=f"{self.info['icon']}  {name}",
                 fg=C['text_secondary'], bg=C['card'],
                 font=('Helvetica Neue', 9), cursor='arrow').pack(anchor='w', pady=(4, 0))

        tk.Frame(frame, bg=C['divider'], height=1, cursor='arrow').pack(fill='x')

        body = tk.Frame(frame, bg=C['card'], padx=20, pady=16, cursor='arrow')
        body.pack(fill='both', expand=True)

        tk.Label(body, text='How should this file be processed?',
                 fg=C['text_primary'], bg=C['card'],
                 font=('Helvetica Neue', 10, 'bold'),
                 cursor='arrow').pack(anchor='w', pady=(0, 12))

        self._option(body, '2', "2-Step Workflow",
                     "Ingest → Generate. Fast, minimal — good for simple documents.")
        self._option(body, '4', "4-Step Workflow",
                     "Ingest → Analyze → Generate → Review. Deeper analysis and a final QA pass.")

        self._bind_focus()
        _cursor(self.root, 'arrow')

    def _option(self, parent, value, title, desc):
        card = tk.Frame(parent, bg=C['option_bg'],
                        highlightbackground=C['option_border'],
                        highlightthickness=1, cursor='hand2')
        card.pack(fill='x', pady=4)
        inner = tk.Frame(card, bg=C['option_bg'], padx=14, pady=10, cursor='hand2')
        inner.pack(fill='x')

        title_lbl = tk.Label(inner, text=title, fg=C['text_primary'], bg=C['option_bg'],
                             font=('Helvetica Neue', 10, 'bold'), anchor='w', cursor='hand2')
        title_lbl.pack(fill='x')
        desc_lbl = tk.Label(inner, text=desc, fg=C['text_dim'], bg=C['option_bg'],
                            font=('Helvetica Neue', 8), anchor='w',
                            wraplength=350, justify='left', cursor='hand2')
        desc_lbl.pack(fill='x', pady=(2, 0))

        widgets = [card, inner, title_lbl, desc_lbl]

        def on_click(e):
            self.choice = int(value)
            self._close()

        def on_enter(e):
            for w in widgets:
                w.config(bg=C['option_hover'])

        def on_leave(e):
            for w in widgets:
                w.config(bg=C['option_bg'])

        for w in widgets:
            w.bind('<Button-1>', on_click)
            w.bind('<Enter>', on_enter)
            w.bind('<Leave>', on_leave)

    def _bind_focus(self):
        # No collapse behaviour here — this is a decision modal, stays put.
        pass

    def _close(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> int | None:
        self.root.mainloop()
        return self.choice
