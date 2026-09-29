// A drop requests a server-side preview; Markdown changes only after confirmation.
(function () {
  let draggedKey = null;
  let sourceLane = null;
  let targets = [];
  let requestId = 0;

  document.addEventListener("dragstart", function (event) {
    const card = event.target.closest(".task-card[data-move-key]");
    if (!card || !event.dataTransfer) return;
    draggedKey = card.dataset.moveKey;
    sourceLane = card.dataset.moveSource;
    targets = JSON.parse(card.dataset.moveTargets);
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", draggedKey);
    card.classList.add("dragging");
  });

  document.addEventListener("dragover", function (event) {
    const lane = event.target.closest(".kanban-column[data-move-lane]");
    if (!draggedKey) return;
    if (!lane || lane.dataset.moveLane === sourceLane || !targets.includes(lane.dataset.moveLane)) {
      document.querySelectorAll(".kanban-column.drop-target").forEach(function (item) {
        item.classList.remove("drop-target");
      });
      return;
    }
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    document.querySelectorAll(".kanban-column.drop-target").forEach(function (item) {
      if (item !== lane) item.classList.remove("drop-target");
    });
    lane.classList.add("drop-target");
  });

  document.addEventListener("drop", function (event) {
    const lane = event.target.closest(".kanban-column[data-move-lane]");
    if (!draggedKey || !lane || lane.dataset.moveLane === sourceLane || !targets.includes(lane.dataset.moveLane)) return;
    event.preventDefault();
    if (window.dash_clientside && window.dash_clientside.set_props) {
      window.dash_clientside.set_props("move-request", {
        data: { key: draggedKey, destination: lane.dataset.moveLane, nonce: ++requestId }
      });
    }
    draggedKey = null;
    sourceLane = null;
    targets = [];
    document.querySelectorAll(".kanban-column.drop-target, .task-card.dragging").forEach(function (item) {
      item.classList.remove("drop-target", "dragging");
    });
  });

  document.addEventListener("dragend", function () {
    draggedKey = null;
    sourceLane = null;
    targets = [];
    document.querySelectorAll(".kanban-column.drop-target, .task-card.dragging").forEach(function (item) {
      item.classList.remove("drop-target", "dragging");
    });
  });
})();
