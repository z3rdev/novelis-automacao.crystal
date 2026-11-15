/** Browser chrome has no place in the native application window. */
export function installNativeShortcuts(target: Document) {
  const blockChrome = (event: KeyboardEvent) => {
    const print =
      (event.ctrlKey || event.metaKey) &&
      (event.key.toLowerCase() === "p" || event.code === "KeyP");
    const inspect =
      event.key === "F12" ||
      event.code === "F12" ||
      ((event.ctrlKey || event.metaKey) &&
        event.shiftKey &&
        (event.key.toLowerCase() === "i" || event.code === "KeyI"));
    if (print || inspect) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  };
  target.addEventListener("keydown", blockChrome, true);
  return () => target.removeEventListener("keydown", blockChrome, true);
}
