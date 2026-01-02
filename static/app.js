const wrap = document.querySelector("#orderItemsWrap");
const addBtn = document.querySelector("#addItemBtn");

function wireRemove(row){
  const btn = row.querySelector(".remove");
  if (btn) btn.addEventListener("click", () => row.remove());
}

if (wrap) {
  wrap.querySelectorAll(".item-row").forEach(wireRemove);
}

if (addBtn && wrap) {
  addBtn.addEventListener("click", () => {
    const row = document.createElement("div");
    row.className = "item-row";
    row.innerHTML = `
      <label>Menu Item ID <input name="menu_item_id[]" type="number" required></label>
      <label>Qty <input name="quantity[]" type="number" min="1" value="1" required></label>
      <button type="button" class="remove">Remove</button>
    `;
    wireRemove(row);
    wrap.appendChild(row);
  });
}

// Review toggle
const segs = document.querySelectorAll(".seg");
const targetType = document.querySelector("#target_type");
const restRow = document.querySelector("#reviewRestaurantRow");
const agentRow = document.querySelector("#reviewAgentRow");
const reviewForm = document.querySelector("#reviewForm");

if (segs.length && targetType && restRow && agentRow && reviewForm) {
  segs.forEach(seg => {
    seg.addEventListener("click", () => {
      segs.forEach(s => s.classList.remove("active"));
      seg.classList.add("active");

      const t = seg.dataset.target;
      if (t === "restaurant") {
        targetType.value = "restaurant";
        restRow.classList.remove("hidden");
        agentRow.classList.add("hidden");
        const agentInput = reviewForm.querySelector('input[name="delivery_agent_id"]');
        if (agentInput) agentInput.value = "";
      } else {
        targetType.value = "agent";
        agentRow.classList.remove("hidden");
        restRow.classList.add("hidden");
        const restInput = reviewForm.querySelector('input[name="restaurant_id"]');
        if (restInput) restInput.value = "";
      }
    });
  });
}