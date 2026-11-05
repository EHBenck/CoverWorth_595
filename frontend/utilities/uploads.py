"""Read a NiceGUI upload event the same way on NiceGUI 2.x and 3.x."""


async def read_upload(e) -> tuple[bytes, str, str]:
    """Return (file_bytes, filename, content_type) for a ui.upload event."""
    file = getattr(e, "file", None)
    if file is not None:  # NiceGUI 3.x: e.file is a FileUpload with an async read()
        return await file.read(), file.name, file.content_type or ""
    # NiceGUI 2.x: e.content is a binary stream
    return e.content.read(), e.name, e.type or ""
