import customtkinter as ctk

from src import theme

class SlidePanel(ctk.CTkFrame):
    def __init__(
        self,
        parent,
        *,
        side: str = "right",
        width: float = 0.30,
        title: str = "Panel",
        step: float = 0.04,
        interval: int = 10,
        on_close=None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self._width = width
        self._step = step
        self._interval = interval
        self._on_close = on_close

        # Resting (closed) and visible (open) horizontal positions, as a
        # fraction of the parent width understood by place(relx=...).
        if side == "left":
            self._closed_pos = -width
            self._open_pos = 0.0
        else:  # right
            self._closed_pos = 1.0
            self._open_pos = 1.0 - width

        self._pos = self._closed_pos
        self._target = self._closed_pos
        self.is_open = False
        self._animating = False

        self._place()
        self._build_chrome(title)

    def toggle(self) -> None:
        if self._animating:
            return
        self.close() if self.is_open else self.open()

    def open(self) -> None:
        self.lift()  # ensure the drawer floats above the rest of the window
        self.is_open = True
        self._animate_to(self._open_pos)

    def close(self) -> None:
        self.is_open = False
        self._animate_to(self._closed_pos)

    def _build_chrome(self, title: str) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(
            header, text=title, font=theme.FONT_SECTION, text_color=theme.TEXT_MUTED
        ).pack(side="left")

        ctk.CTkButton(
            header,
            text="✕",
            width=32,
            height=32,
            corner_radius=8,
            fg_color=theme.DANGER,
            hover_color=theme.DANGER,
            command=self.close,
        ).pack(side="right")

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=12, pady=(6, 12))

    def _place(self) -> None:
        self.place(relx=self._pos, rely=0, relwidth=self._width, relheight=1.0)

    def _animate_to(self, target: float) -> None:
        self._target = target
        self._animating = True
        self._tick()

    def _tick(self) -> None:
        # Close enough — snap to the target and stop.
        if abs(self._pos - self._target) <= self._step:
            self._pos = self._target
            self._place()
            self._animating = False
            if not self.is_open and self._on_close is not None:
                self._on_close()
            return

        self._pos += self._step if self._target > self._pos else -self._step
        self._place()
        self.after(self._interval, self._tick)
