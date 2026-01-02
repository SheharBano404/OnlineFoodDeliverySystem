const API = ""; // same origin

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

function pretty(x){ return JSON.stringify(x, null, 2); }

async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

function setOut(id, msg){
  $(id).textContent = typeof msg === "string" ? msg : pretty(msg);
}

function money(s){
  // API returns DECIMAL as string; keep display stable
  return `${s}`;
}

/* ---------------- Tabs ---------------- */
function initTabs(){
  $$(".tab").forEach(btn => {
    btn.addEventListener("click", () => {
      $$(".tab").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      $$(".panel").forEach(p => p.classList.remove("active"));
      $(`#tab-${btn.dataset.tab}`).classList.add("active");
    });
  });
}

/* ---------------- Live data ---------------- */
async function loadLiveData(){
  const [users, restaurants] = await Promise.all([
    api("/api/users"),
    api("/api/restaurants"),
  ]);

  $("#countsBadge").textContent = `${users.length} users • ${restaurants.length} restaurants`;

  $("#usersList").innerHTML = users.slice(0, 8).map(u => `
    <div>
      <div><b>#${u.user_id}</b> ${escapeHtml(u.full_name)}</div>
      <div style="opacity:.85">${escapeHtml(u.type)} • ${escapeHtml(u.email)}</div>
    </div>
  `).join("") || "<div>No users yet</div>";

  $("#restaurantsList").innerHTML = restaurants.slice(0, 8).map(r => `
    <div>
      <div><b>#${r.restaurant_id}</b> ${escapeHtml(r.name)}</div>
      <div style="opacity:.85">${escapeHtml(r.status)} • ${escapeHtml(r.address)}</div>
    </div>
  `).join("") || "<div>No restaurants yet</div>";

  // Fill restaurant selects
  const options = restaurants.map(r => `<option value="${r.restaurant_id}">#${r.restaurant_id} — ${escapeHtml(r.name)}</option>`).join("");
  const fallback = `<option value="">Create a restaurant first</option>`;

  $("#menuRestaurantSelect").innerHTML = options || fallback;
  $("#viewMenuRestaurantSelect").innerHTML = options || fallback;
  $("#orderRestaurantSelect").innerHTML = options || fallback;
}

function escapeHtml(str){
  return String(str ?? "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

/* ---------------- Health badge ---------------- */
async function checkHealth(){
  try{
    await api("/api/health");
    $("#healthBadge").textContent = "API: online";
    $("#healthBadge").style.borderColor = "rgba(51,214,159,.35)";
    $("#healthBadge").style.background = "rgba(51,214,159,.12)";
  }catch{
    $("#healthBadge").textContent = "API: offline";
    $("#healthBadge").style.borderColor = "rgba(255,92,122,.35)";
    $("#healthBadge").style.background = "rgba(255,92,122,.12)";
  }
}

/* ---------------- Menu viewer ---------------- */
async function loadMenuFor(restaurantId){
  const rows = await api(`/api/restaurants/${Number(restaurantId)}/menu`);
  $("#menuList").innerHTML = rows.map(m => `
    <div class="rowcard">
      <div>
        <div class="title">#${m.menu_id} — ${escapeHtml(m.name)}</div>
        <div class="meta">${escapeHtml(m.category || "—")} • ${m.availability == 1 ? "Available" : "Unavailable"}</div>
      </div>
      <div class="tag">PKR ${money(m.price)}</div>
    </div>
  `).join("") || `<div class="rowcard"><div>No menu items yet</div></div>`;
  return rows;
}

/* ---------------- Order item rows ---------------- */
function makeOrderItemRow(menuOptionsHtml){
  const div = document.createElement("div");
  div.className = "item-row";
  div.innerHTML = `
    <label>Menu item
      <select name="menu_item_id" required>
        ${menuOptionsHtml}
      </select>
    </label>
    <label>Qty
      <input name="quantity" type="number" min="1" value="1" required />
    </label>
    <button type="button" class="remove">Remove</button>
  `;
  div.querySelector(".remove").addEventListener("click", () => div.remove());
  return div;
}

async function refreshOrderMenuOptions(){
  const rid = $("#orderRestaurantSelect").value;
  if (!rid) return { menu: [], optionsHtml: `<option value="">No restaurant</option>` };

  const menu = await api(`/api/restaurants/${Number(rid)}/menu`);
  const available = menu.filter(m => Number(m.availability) === 1);
  const optionsHtml = available.map(m => `<option value="${m.menu_id}">#${m.menu_id} — ${escapeHtml(m.name)} (PKR ${money(m.price)})</option>`).join("")
    || `<option value="">No available items</option>`;
  return { menu: available, optionsHtml };
}

/* ---------------- Reviews segmented control ---------------- */
function initReviewTargetToggle(){
  const buttons = $$(".seg");
  buttons.forEach(b => {
    b.addEventListener("click", () => {
      buttons.forEach(x => x.classList.remove("active"));
      b.classList.add("active");

      const t = b.dataset.target;
      const restRow = $("#reviewRestaurantRow");
      const agentRow = $("#reviewAgentRow");

      if (t === "restaurant"){
        restRow.classList.remove("hidden");
        agentRow.classList.add("hidden");
        // clear agent input
        $("#reviewForm").querySelector('input[name="delivery_agent_id"]').value = "";
      } else {
        agentRow.classList.remove("hidden");
        restRow.classList.add("hidden");
        // clear restaurant input
        $("#reviewForm").querySelector('input[name="restaurant_id"]').value = "";
      }
    });
  });
}

/* ---------------- Forms ---------------- */
function formToObj(form){
  const fd = new FormData(form);
  return Object.fromEntries(fd.entries());
}

function initForms(){
  // Create user
  $("#userForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const raw = formToObj(e.target);
    const payload = {
      full_name: raw.full_name,
      email: raw.email,
      phone_number: raw.phone_number,
      type: raw.type,
      address: raw.address || null
    };
    try{
      const out = await api("/api/users", { method:"POST", body: JSON.stringify(payload) });
      setOut("#userOut", out);
      await loadLiveData();
    }catch(err){
      setOut("#userOut", err.message);
    }
  });

  // Create restaurant
  $("#restaurantForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const raw = formToObj(e.target);
    try{
      const out = await api("/api/restaurants", { method:"POST", body: JSON.stringify(raw) });
      setOut("#restaurantOut", out);
      await loadLiveData();
    }catch(err){
      setOut("#restaurantOut", err.message);
    }
  });

  // Add menu item
  $("#menuForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const raw = formToObj(e.target);
    const payload = {
      restaurant_id: Number(raw.restaurant_id),
      name: raw.name,
      price: raw.price,
      category: raw.category,
      availability: e.target.availability.checked ? 1 : 0
    };
    try{
      const out = await api("/api/menu-items", { method:"POST", body: JSON.stringify(payload) });
      setOut("#menuOut", out);
    }catch(err){
      setOut("#menuOut", err.message);
    }
  });

  // View menu
  $("#loadMenuBtn").addEventListener("click", async () => {
    const rid = $("#viewMenuRestaurantSelect").value;
    if (!rid) return;
    await loadMenuFor(rid);
  });

  // Place order
  $("#orderRestaurantSelect").addEventListener("change", async () => {
    // reset items with new menu options
    const { optionsHtml } = await refreshOrderMenuOptions();
    $("#orderItemsWrap").innerHTML = "";
    $("#orderItemsWrap").appendChild(makeOrderItemRow(optionsHtml));
  });

  $("#addItemBtn").addEventListener("click", async () => {
    const { optionsHtml } = await refreshOrderMenuOptions();
    $("#orderItemsWrap").appendChild(makeOrderItemRow(optionsHtml));
  });

  $("#orderForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const raw = formToObj(e.target);

    const itemRows = $$("#orderItemsWrap .item-row");
    const items = itemRows.map(r => ({
      menu_item_id: Number(r.querySelector('select[name="menu_item_id"]').value),
      quantity: Number(r.querySelector('input[name="quantity"]').value)
    })).filter(x => x.menu_item_id && Number.isFinite(x.quantity) && x.quantity > 0);

    const payload = {
      user_id: Number(raw.user_id),
      restaurant_id: Number(raw.restaurant_id),
      payment_method: raw.payment_method,
      delivery_instructions: raw.delivery_instructions || null,
      items
    };

    try{
      const out = await api("/api/orders", { method:"POST", body: JSON.stringify(payload) });
      setOut("#orderOut", out);
    }catch(err){
      setOut("#orderOut", err.message);
    }
  });

  // Track order
  $("#trackForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const raw = formToObj(e.target);
    try{
      const out = await api(`/api/orders/${Number(raw.order_id)}`);
      setOut("#trackOut", out);
    }catch(err){
      setOut("#trackOut", err.message);
    }
  });

  $("#updateStatusBtn").addEventListener("click", async () => {
    const raw = formToObj($("#trackForm"));
    if (!raw.order_id || !raw.status) return setOut("#trackOut", "Provide Order ID and select a status to update.");
    try{
      const out = await api(`/api/orders/${Number(raw.order_id)}/status`, {
        method:"POST",
        body: JSON.stringify({ status: raw.status })
      });
      const refreshed = await api(`/api/orders/${Number(raw.order_id)}`);
      setOut("#trackOut", { update: out, refreshed });
    }catch(err){
      setOut("#trackOut", err.message);
    }
  });

  // Assign delivery
  $("#deliveryForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const raw = formToObj(e.target);
    const payload = {
      order_id: Number(raw.order_id),
      delivery_agent_id: Number(raw.delivery_agent_id),
      expected_drop_at: raw.expected_drop_at || null
    };
    try{
      const out = await api("/api/deliveries/assign", { method:"POST", body: JSON.stringify(payload) });
      setOut("#deliveryOut", out);
    }catch(err){
      setOut("#deliveryOut", err.message);
    }
  });

  // Review
  $("#reviewForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const raw = formToObj(e.target);
    const payload = {
      reviewer_id: Number(raw.reviewer_id),
      rating: Number(raw.rating),
      comment: raw.comment || null,
      restaurant_id: raw.restaurant_id ? Number(raw.restaurant_id) : null,
      delivery_agent_id: raw.delivery_agent_id ? Number(raw.delivery_agent_id) : null,
    };
    try{
      const out = await api("/api/reviews", { method:"POST", body: JSON.stringify(payload) });
      setOut("#reviewOut", out);
    }catch(err){
      setOut("#reviewOut", err.message);
    }
  });
}

/* ---------------- Init ---------------- */
async function init(){
  initTabs();
  initReviewTargetToggle();
  initForms();

  $("#refreshBtn").addEventListener("click", async () => {
    await loadLiveData();
  });

  await checkHealth();
  await loadLiveData();

  // Prepare initial order item UI
  const { optionsHtml } = await refreshOrderMenuOptions();
  $("#orderItemsWrap").innerHTML = "";
  $("#orderItemsWrap").appendChild(makeOrderItemRow(optionsHtml));
}

init();