# popup.py  ─  FolderGuardian  BatchGuardianPopup (Tkinter)
#
# V1 fixes applied:
#   - _acting guard stops focus-out collapse during flash
#   - DISMISS_DELAY_MS reduced to 300
#   - Full batch popup — one popup for N files, each with Allow/Deny toggle
#   - Arrow cursor forced recursively on every widget

import tkinter as tk
from pathlib import Path
from file_info import get_file_info, get_folder_summary, FILE_TYPES

C = {
    'bg':             '#0F0F13',
    'card':           '#17171F',
    'card_border':    '#2C2C3E',
    'input_bg':       '#1F1F2B',
    'detail_bg':      '#13131A',
    'row_hover':      '#21212F',
    'text_primary':   '#F0F0F8',
    'text_secondary': '#9898B8',
    'text_dim':       '#55556A',
    'accent':         '#6B6BF5',
    'divider':        '#22222E',
    'allow':          '#1A8A55',
    'allow_hover':    '#22A866',
    'allow_text':     '#D4F5E3',
    'deny':           '#8A1A2A',
    'deny_hover':     '#B02235',
    'deny_text':      '#F5D4D8',
    'tab_accent':     '#6B6BF5',
    'toggle_off':     '#2C2C3E',
    'toggle_on_a':    '#1A8A55',
    'toggle_on_d':    '#8A1A2A',
}

POPUP_W        = 360
ROW_H          = 58
HEADER_H       = 72
FOOTER_H       = 64
TAB_W          = 30
ANIM_STEP      = 24
ANIM_MS        = 7
DISMISS_DELAY  = 3    # ms — was 800, now snappy


def _cursor(widget, cur='arrow'):
    try: widget.config(cursor=cur)
    except Exception: pass
    for c in widget.winfo_children():
        _cursor(c, cur)


class BatchGuardianPopup:
    """
    Single popup listing ALL pending files.
    Each row has an Allow/Deny toggle.
    Footer has Allow All / Deny All / Confirm.
    """

    def __init__(self, batch: list[tuple[str, str | None]],
                 on_allow, on_deny):
        self.batch    = batch           # [(filepath, origin), ...]
        self.on_allow = on_allow
        self.on_deny  = on_deny
        self._acting  = False
        self._collapsed = False
        self.result: tuple[list[str], list[tuple[str, str | None]]] | None = None

        # Decision per file: True=allow, False=deny. Default allow.
        self._decisions: dict[str, bool] = {fp: True for fp, _ in batch}
        self._infos = {fp: get_file_info(fp) for fp, _ in batch}

        # Use first file's folder for summary
        self._folder = str(Path(batch[0][0]).parent)
        self._summary = get_folder_summary(self._folder)

        self._build()
        self._slide_in()

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
        self._sw, self._sh = sw, sh

        n         = len(self.batch)
        popup_h   = HEADER_H + (ROW_H * n) + 1 + FOOTER_H
        self._popup_h = popup_h
        self._full_x  = sw - POPUP_W - 16
        self._tab_x   = sw - TAB_W - 2
        self._y       = max(8, sh - popup_h - 52)
        self._cur_x   = sw + 20

        self.root.geometry(f"{POPUP_W}x{popup_h}+{self._cur_x}+{self._y}")
        self._build_ui()
        self._bind_focus()

    # ── UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        outer = tk.Frame(self.root, bg=C['card_border'], padx=1, pady=1, cursor='arrow')
        outer.pack(fill='both', expand=True)
        self.frame = tk.Frame(outer, bg=C['card'], cursor='arrow')
        self.frame.pack(fill='both', expand=True)

        self._build_header()
        self._build_file_list()
        self._build_footer()
        _cursor(self.root, 'arrow')

    # ── Header ──────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self.frame, bg=C['card'], padx=16, pady=14, cursor='arrow')
        hdr.pack(fill='x')

        left = tk.Frame(hdr, bg=C['card'], cursor='arrow')
        left.pack(side='left', fill='both', expand=True)

        brand = tk.Frame(left, bg=C['card'], cursor='arrow')
        brand.pack(anchor='w')
        tk.Label(brand, text='●', fg=C['accent'], bg=C['card'],
                 font=('Helvetica Neue', 9), cursor='arrow').pack(side='left', padx=(0, 5))
        tk.Label(brand, text='FolderGuardian', fg=C['text_primary'], bg=C['card'],
                 font=('Helvetica Neue', 11, 'bold'), cursor='arrow').pack(side='left')

        n = len(self.batch)
        sub = f"{n} file{'s' if n > 1 else ''} requesting entry"
        tk.Label(left, text=sub, fg=C['text_secondary'], bg=C['card'],
                 font=('Helvetica Neue', 9), cursor='arrow').pack(anchor='w', pady=(3, 0))

        close = tk.Label(hdr, text='✕', fg=C['text_dim'], bg=C['card'],
                         font=('Helvetica Neue', 12), cursor='hand2')
        close.pack(side='right', anchor='n')
        close.bind('<Button-1>', lambda e: self._dismiss_all_allow())
        close.bind('<Enter>', lambda e: close.config(fg=C['text_primary']))
        close.bind('<Leave>', lambda e: close.config(fg=C['text_dim']))

        tk.Frame(self.frame, bg=C['divider'], height=1, cursor='arrow').pack(fill='x')

    # ── File list ───────────────────────────────────────────────
    def _build_file_list(self):
        self._row_frames: dict[str, tk.Frame] = {}
        self._toggle_labels: dict[str, tk.Label] = {}

        for i, (fp, _) in enumerate(self.batch):
            info = self._infos[fp]
            is_last = (i == len(self.batch) - 1)

            row = tk.Frame(self.frame, bg=C['card'], padx=14, pady=0,
                           height=ROW_H, cursor='arrow')
            row.pack(fill='x')
            row.pack_propagate(False)
            self._row_frames[fp] = row

            inner = tk.Frame(row, bg=C['card'], cursor='arrow')
            inner.place(relx=0, rely=0.5, anchor='w', relwidth=1)

            # Icon
            icon_box = tk.Frame(inner, bg=C['input_bg'], width=34, height=34,
                                cursor='arrow')
            icon_box.pack(side='left', padx=(0, 10))
            icon_box.pack_propagate(False)
            tk.Label(icon_box, text=info['icon'], bg=C['input_bg'],
                     fg=C['text_primary'],
                     font=('Helvetica Neue', 15), cursor='arrow').place(
                         relx=.5, rely=.5, anchor='center')

            # Name + chips
            meta = tk.Frame(inner, bg=C['card'], cursor='arrow')
            meta.pack(side='left', fill='both', expand=True)

            name = info['name']
            if len(name) > 24: name = name[:21] + '…'
            tk.Label(meta, text=name, fg=C['text_primary'], bg=C['card'],
                     font=('Helvetica Neue', 9, 'bold'),
                     anchor='w', cursor='arrow').pack(fill='x')

            chips = tk.Frame(meta, bg=C['card'], cursor='arrow')
            chips.pack(anchor='w')
            self._chip(chips, info['type'], small=True)
            self._chip(chips, info['size'], small=True, accent=True)

            # Allow/Deny toggle button
            tog = tk.Label(inner, text='✓ Allow',
                           bg=C['toggle_on_a'], fg=C['allow_text'],
                           font=('Helvetica Neue', 8, 'bold'),
                           padx=8, pady=4, cursor='hand2')
            tog.pack(side='right', padx=(8, 0))
            self._toggle_labels[fp] = tog
            tog.bind('<Button-1>', lambda e, f=fp: self._toggle(f))

            if not is_last:
                tk.Frame(self.frame, bg=C['divider'], height=1,
                         cursor='arrow').pack(fill='x')

    def _toggle(self, fp: str):
        current = self._decisions[fp]
        self._decisions[fp] = not current
        lbl = self._toggle_labels[fp]
        if self._decisions[fp]:
            lbl.config(text='✓ Allow', bg=C['toggle_on_a'], fg=C['allow_text'])
        else:
            lbl.config(text='✕ Deny', bg=C['toggle_on_d'], fg=C['deny_text'])

    # ── Footer ──────────────────────────────────────────────────
    def _build_footer(self):
        tk.Frame(self.frame, bg=C['divider'], height=1, cursor='arrow').pack(fill='x')

        bar = tk.Frame(self.frame, bg=C['card'], padx=12, pady=10, cursor='arrow')
        bar.pack(fill='x')

        # Deny All
        da = tk.Label(bar, text='✕ Deny All', bg=C['deny'], fg=C['deny_text'],
                      font=('Helvetica Neue', 8, 'bold'), padx=10, pady=7,
                      cursor='hand2')
        da.pack(side='left', padx=(0, 4))
        da.bind('<Button-1>', lambda e: self._set_all(False))
        da.bind('<Enter>', lambda e: da.config(bg=C['deny_hover']))
        da.bind('<Leave>', lambda e: da.config(bg=C['deny']))

        # Allow All
        aa = tk.Label(bar, text='✓ Allow All', bg=C['allow'], fg=C['allow_text'],
                      font=('Helvetica Neue', 8, 'bold'), padx=10, pady=7,
                      cursor='hand2')
        aa.pack(side='left', padx=(0, 4))
        aa.bind('<Button-1>', lambda e: self._set_all(True))
        aa.bind('<Enter>', lambda e: aa.config(bg=C['allow_hover']))
        aa.bind('<Leave>', lambda e: aa.config(bg=C['allow']))

        # Confirm
        cf = tk.Label(bar, text='Confirm →', bg=C['accent'], fg='white',
                      font=('Helvetica Neue', 8, 'bold'), padx=14, pady=7,
                      cursor='hand2')
        cf.pack(side='right')
        cf.bind('<Button-1>', lambda e: self._confirm())
        cf.bind('<Enter>', lambda e: cf.config(bg='#5555DD'))
        cf.bind('<Leave>', lambda e: cf.config(bg=C['accent']))

    def _set_all(self, val: bool):
        for fp in self._decisions:
            self._decisions[fp] = val
            lbl = self._toggle_labels[fp]
            if val:
                lbl.config(text='✓ Allow', bg=C['toggle_on_a'], fg=C['allow_text'])
            else:
                lbl.config(text='✕ Deny', bg=C['toggle_on_d'], fg=C['deny_text'])

    # ── Confirm ─────────────────────────────────────────────────
    def _confirm(self):
        if self._acting:
            return
        self._acting = True

        allowed = [fp for fp, dec in self._decisions.items() if dec]
        denied  = [fp for fp, dec in self._decisions.items() if not dec]
        label   = f"✓ {len(allowed)} allowed  ✕ {len(denied)} denied"

        for widget in self.root.winfo_children():
            widget.destroy()
        flash = tk.Frame(self.root, bg=C['accent'], cursor='arrow')
        flash.pack(fill='both', expand=True)
        tk.Label(flash, text=label, bg=C['accent'], fg='white',
                 font=('Helvetica Neue', 10, 'bold'),
                 cursor='arrow').place(relx=.5, rely=.5, anchor='center')

        def _finish():
            origins = dict(self.batch)
            self.result = (
                allowed,
                [(fp, origins.get(fp)) for fp in denied],
            )
            self._close()

        self.root.after(DISMISS_DELAY, _finish)

    def _dismiss_all_allow(self):
        if self._acting:
            return
        self._acting = True
        self.result = ([fp for fp, _ in self.batch], [])
        self._close()

    # ── Chip ────────────────────────────────────────────────────
    def _chip(self, parent, text, small=False, accent=False, dim=False):
        size = 7 if small else 8
        fg   = C['text_dim'] if dim else (C['accent'] if accent else C['text_secondary'])
        tk.Label(parent, text=text, bg=C['input_bg'], fg=fg,
                 font=('Helvetica Neue', size), padx=6, pady=1,
                 cursor='arrow').pack(side='left', padx=(0, 3))

    # ── Collapse / Tab ──────────────────────────────────────────
    def _bind_focus(self):
        self.root.bind('<FocusOut>', self._on_focus_out)
        self.root.bind('<FocusIn>',  self._on_focus_in)

    def _on_focus_out(self, _):
        if not self._collapsed and not self._acting:
            self._collapse()

    def _on_focus_in(self, _):
        if self._collapsed:
            self._expand()

    def _collapse(self):
        self._collapsed = True
        self.frame.pack_forget()
        self._build_tab()
        self.root.geometry(f"{TAB_W}x{64}+{self._tab_x}+{self._y}")

    def _expand(self):
        if hasattr(self, '_tab_frame'):
            self._tab_frame.destroy()
        self._collapsed = False
        self.frame.pack(fill='both', expand=True)
        self.root.geometry(f"{POPUP_W}x{self._popup_h}+{self._full_x}+{self._y}")
        self.root.focus_force()
        _cursor(self.root, 'arrow')

    def _build_tab(self):
        self._tab_frame = tk.Frame(self.root, bg=C['tab_accent'],
                                   width=TAB_W, cursor='hand2')
        self._tab_frame.pack(fill='both', expand=True)
        self._tab_frame.bind('<Button-1>', lambda e: self._expand())
        c = tk.Canvas(self._tab_frame, bg=C['tab_accent'],
                      width=TAB_W, height=64, highlightthickness=0, cursor='hand2')
        c.pack()
        c.create_text(TAB_W // 2, 32, text='🛡',
                      font=('Helvetica Neue', 13), fill='white', anchor='center')
        c.bind('<Button-1>', lambda e: self._expand())

    # ── Slide-in ────────────────────────────────────────────────
    def _slide_in(self):
        if self._cur_x > self._full_x:
            self._cur_x = max(self._full_x, self._cur_x - ANIM_STEP)
            self.root.geometry(f"{POPUP_W}x{self._popup_h}+{self._cur_x}+{self._y}")
            self.root.after(ANIM_MS, self._slide_in)
        else:
            self.root.focus_force()
            _cursor(self.root, 'arrow')

    def _close(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()
        if self.result is None:
            self.result = ([fp for fp, _ in self.batch], [])
        return self.result
