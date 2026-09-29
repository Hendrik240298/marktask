// Only path text is handled. Browser file drops never upload or read file contents.
(function () {
  function feedback(message) {
    if (window.dash_clientside && window.dash_clientside.set_props) {
      window.dash_clientside.set_props("visibility-drop-feedback", { children: message });
    }
  }

  function droppedPath(transfer) {
    const uriList = transfer.getData("text/uri-list");
    const candidates = uriList
      ? uriList.split(/\r?\n/).filter((line) => line && !line.startsWith("#"))
      : transfer.getData("text/plain").split(/\r?\n/).filter(Boolean);
    if (candidates.length !== 1) return null;
    let path = candidates[0].trim();
    if (/^file:\/\//i.test(path)) {
      try {
        const uri = new URL(path);
        if (uri.protocol !== "file:" || (uri.hostname && uri.hostname !== "localhost")) return null;
        path = decodeURIComponent(uri.pathname);
      } catch (_) {
        return null;
      }
    }
    return path.startsWith("/") ? path : null;
  }

  document.addEventListener("dragover", function (event) {
    const zone = event.target.closest("#visibility-drop");
    if (!zone) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    zone.classList.add("drag-over");
  });

  document.addEventListener("dragleave", function (event) {
    const zone = event.target.closest("#visibility-drop");
    if (zone && !zone.contains(event.relatedTarget)) zone.classList.remove("drag-over");
  });

  document.addEventListener("drop", function (event) {
    const zone = event.target.closest("#visibility-drop");
    if (!zone) return;
    event.preventDefault();
    zone.classList.remove("drag-over");
    const path = droppedPath(event.dataTransfer);
    if (!path) {
      feedback("Browser did not provide one absolute path. Paste the path into the field instead.");
      return;
    }
    if (window.dash_clientside && window.dash_clientside.set_props) {
      window.dash_clientside.set_props("visibility-pattern", { value: path });
      feedback("Path captured. Review the matches before confirming.");
    }
  });
})();
