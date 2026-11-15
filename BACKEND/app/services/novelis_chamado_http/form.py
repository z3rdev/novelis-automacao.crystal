"""Successful HTML controls from the authenticated Novelis opening form."""

from html.parser import HTMLParser


class Form(HTMLParser):
    def __init__(self, *, fragment=False):
        super().__init__()
        self.inside = fragment
        self.action = ""
        self.method = ""
        self.fields = {}
        self.buttons = {}
        self.files = {}
        self.options = {}
        self.required = set()
        self._select = None
        self._textarea = None

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "form":
            self.inside = attrs.get("id") == "form"
            if self.inside:
                self.action = attrs.get("action", "")
                self.method = attrs.get("method", "GET").upper()
        if not self.inside or "disabled" in attrs:
            return
        if tag == "option" and self._select:
            self.options[self._select].append(
                {"value": attrs.get("value", ""), "selected": "selected" in attrs, "text": ""}
            )
            return
        name = attrs.get("name")
        if not name:
            return
        kind = attrs.get("type", "text").lower()
        classes = attrs.get("class", "").split()
        if "required" in attrs or "required" in classes or "required-file" in classes:
            self.required.add(name)
        if tag == "input":
            if kind == "file":
                self.files[name] = attrs.get("data-allowed-file-extensions", "").split()
            elif kind in {"button", "submit"}:
                self.buttons[attrs.get("id", name)] = (name, attrs.get("value", ""))
            elif kind not in {"reset", "image"} and (
                kind not in {"checkbox", "radio"} or "checked" in attrs
            ):
                self.fields[name] = attrs.get("value", "on" if kind == "checkbox" else "")
        elif tag == "button":
            self.buttons[attrs.get("id", name)] = (name, attrs.get("value", ""))
        elif tag == "textarea":
            self._textarea = name
            self.fields[name] = ""
        elif tag == "select":
            self._select = name
            self.options[name] = []

    def handle_endtag(self, tag):
        if tag == "form":
            self.inside = False
        elif tag == "textarea":
            self._textarea = None
        elif tag == "select" and self._select:
            options = self.options[self._select]
            chosen = next((item for item in options if item["selected"]), None)
            self.fields[self._select] = (chosen or (options[0] if options else {})).get("value", "")
            self._select = None

    def handle_data(self, data):
        if self._textarea:
            self.fields[self._textarea] += data
        elif self._select and self.options[self._select]:
            self.options[self._select][-1]["text"] += data
