"""Small drawn controls matching the application's flat visual style."""
import tkinter as tk


class FlatScrollbar(tk.Canvas):
    """A quiet, arrow-free scrollbar with a wider invisible pointer target."""

    def __init__(self, master, command, background="#f3f6fb"):
        super().__init__(master, width=16, borderwidth=0, highlightthickness=0,
                         background=background, cursor="arrow", takefocus=False)
        self.command = command
        self.first, self.last = 0.0, 1.0
        self.hover = False
        self.drag_offset = None
        self.bind("<Configure>", lambda _event: self.draw())
        self.bind("<Enter>", lambda _event: self.set_hover(True))
        self.bind("<Leave>", lambda _event: self.set_hover(False))
        self.bind("<ButtonPress-1>", self.press)
        self.bind("<B1-Motion>", self.drag)
        self.bind("<ButtonRelease-1>", self.release)

    def set(self, first, last):
        self.first = max(0.0, min(1.0, float(first)))
        self.last = max(self.first, min(1.0, float(last)))
        self.draw()

    def geometry_values(self):
        track = max(1, self.winfo_height() - 16)
        span = self.last - self.first
        size = min(track, max(36, track * span))
        travel = track - size
        top = 8 + (self.first / (1 - span) * travel if span < 1 else 0)
        return top, size, travel, span

    def draw(self):
        self.delete("all")
        if self.last - self.first >= 0.9999:
            return
        top, size, _travel, _span = self.geometry_values()
        center = self.winfo_width() / 2
        active = self.hover or self.drag_offset is not None
        width = 8 if active else 6
        if active:
            self.create_line(center, 12, center, max(12, self.winfo_height() - 12),
                             fill="#e8edf4", width=8, capstyle=tk.ROUND, tags="track")
        self.create_line(center, top + width / 2, center, top + size - width / 2,
                         fill="#7f90a8" if active else "#b9c5d5", width=width,
                         capstyle=tk.ROUND, tags="thumb")

    def set_hover(self, value):
        self.hover = value
        self.draw()

    def move_to(self, top):
        _current, _size, travel, span = self.geometry_values()
        if travel > 0 and span < 1:
            fraction = max(0, min(1, (top - 8) / travel)) * (1 - span)
            self.command("moveto", fraction)

    def press(self, event):
        if self.last - self.first >= 0.9999:
            return "break"
        top, size, _travel, _span = self.geometry_values()
        if top <= event.y <= top + size:
            self.drag_offset = event.y - top
        else:
            self.drag_offset = size / 2
            self.move_to(event.y - self.drag_offset)
        self.grab_set()
        self.draw()
        return "break"

    def drag(self, event):
        if self.drag_offset is not None:
            self.move_to(event.y - self.drag_offset)
        return "break"

    def release(self, event):
        if self.drag_offset is not None:
            self.grab_release()
        self.drag_offset = None
        self.hover = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        self.draw()
        return "break"
