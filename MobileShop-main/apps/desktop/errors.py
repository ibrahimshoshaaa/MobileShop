class AppError(Exception):
    """User-facing validation/business error, shown directly in a dialog.

    Mirrors InventoryException / SalesException / CustomerException /
    InstallmentException on the Flutter side — one exception type here since
    Tkinter error dialogs don't need per-feature classes to render correctly.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
