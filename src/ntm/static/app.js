/*
 * ntm – Frontend.
 *
 * Bewusst ohne Framework und ohne Build-Schritt: der Zustand ist klein, die
 * Tastaturbedienung profitiert von direktem DOM-Zugriff, und das Nix-Paket
 * bleibt ein reines Python-Paket.
 *
 * Routen (Hash, damit der Zurück-Button überall funktioniert):
 *   #/?q=…&tag=…&age=…   Suche
 *   #/new                Neuer Eintrag
 *   #/e/<id>             Detailansicht
 *   #/e/<id>/edit        Bearbeiten
 */

const TOKEN_KEY = "ntm.token";
const LISTVIEW_KEY = "ntm.listview";

const app = document.getElementById("app");
const foot = document.getElementById("foot");
const toasts = document.getElementById("toasts");

/* ------------------------------------------------------------------ Helfer */

function h(tag, props, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class" || key === "className") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "html") node.innerHTML = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on") && typeof value === "function")
      node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key in node && key !== "list") node[key] = value;
    else node.setAttribute(key, value === true ? "" : value);
  }
  append(node, children);
  return node;
}

function append(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function debounce(fn, ms) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

function isTyping(target) {
  if (!target) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

/* --------------------------------------------------------------- Meldungen */

function toast(message, kind = "info") {
  const node = h("div", { class: `toast toast-${kind}`, text: message });
  toasts.append(node);
  setTimeout(() => {
    node.classList.add("fade");
    setTimeout(() => node.remove(), 400);
  }, kind === "error" ? 5000 : 2200);
}

/* --------------------------------------------------------------------- API */

const session = {
  token: localStorage.getItem(TOKEN_KEY) || "",
  required: true,
};

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function api(path, options = {}) {
  const headers = { Accept: "application/json" };
  if (session.token) headers.Authorization = `Bearer ${session.token}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method: options.method || "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });
  if (response.status === 401) {
    session.token = "";
    localStorage.removeItem(TOKEN_KEY);
    renderLogin();
    throw new ApiError(401, "nicht angemeldet");
  }
  if (!response.ok) {
    let detail = `Fehler ${response.status}`;
    try {
      const data = await response.json();
      if (data && data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch (_) {
      /* Antwort war kein JSON */
    }
    throw new ApiError(response.status, detail);
  }
  return response.status === 204 ? null : response.json();
}

/* --------------------------------------------------------------- Typeahead */

/**
 * Hängt eine Vorschlagsliste an ein Eingabefeld.
 *
 * Wichtig: diese Funktion muss *vor* den feldeigenen keydown-Handlern
 * aufgerufen werden – verarbeitet sie eine Taste, bricht sie die Kette mit
 * stopImmediatePropagation ab.
 */
function attachTypeahead(input, { fetchItems, onPick, openOnFocus = true }) {
  // Die Vorschlagsliste hängt an einem positionierten Container. Hat das
  // Eingabefeld noch keinen – etwa weil es noch gar nicht im Dokument steht –,
  // bekommt es hier einen.
  let host = input.parentNode;
  if (!host || !host.classList || !host.classList.contains("combo")) {
    const wrapper = h("div", { class: "combo" });
    if (host) host.replaceChild(wrapper, input);
    wrapper.append(input);
    host = wrapper;
  }
  const list = h("div", { class: "suggest", role: "listbox", hidden: true });
  host.append(list);
  input.setAttribute("autocomplete", "off");
  input.setAttribute("role", "combobox");

  let items = [];
  let active = -1;
  let sequence = 0;

  const close = () => {
    list.hidden = true;
    items = [];
    active = -1;
  };

  const draw = () => {
    clear(list);
    if (!items.length) {
      list.hidden = true;
      return;
    }
    items.forEach((item, index) => {
      list.append(
        h(
          "div",
          {
            class: `suggest-item${index === active ? " active" : ""}`,
            role: "option",
            onmousedown: (event) => {
              event.preventDefault();
              pick(item);
            },
            onmouseenter: () => {
              active = index;
              draw();
            },
          },
          h("span", { class: "suggest-label", text: item.label }),
          item.hint ? h("span", { class: "suggest-hint", text: item.hint }) : null,
        ),
      );
    });
    list.hidden = false;
  };

  const pick = (item) => {
    close();
    onPick(item);
  };

  const load = async () => {
    const mine = ++sequence;
    try {
      const found = await fetchItems(input.value);
      if (mine !== sequence) return;
      items = found;
      active = items.length ? 0 : -1;
      draw();
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) close();
    }
  };

  const loadSoon = debounce(load, 70);

  input.addEventListener("input", loadSoon);
  input.addEventListener("focus", () => {
    if (openOnFocus) loadSoon();
  });
  input.addEventListener("blur", () => setTimeout(close, 120));

  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (list.hidden) {
        load();
      } else {
        active = (active + (event.key === "ArrowDown" ? 1 : items.length - 1)) % items.length;
        draw();
      }
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    if (event.key === "Escape" && !list.hidden) {
      close();
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    if (event.key === "Enter" && !list.hidden && active >= 0) {
      pick(items[active]);
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    if (event.key === "Tab" && !list.hidden && active >= 0 && !event.shiftKey) {
      // Übernehmen, aber den Fokuswechsel nicht aufhalten.
      pick(items[active]);
    }
  });

  return { close, reload: load, root: host };
}

async function fetchTagSuggestions(query, exclude = []) {
  const params = new URLSearchParams({ q: query || "", limit: "10" });
  const data = await api(`/api/tags/suggest?${params}`);
  const skip = new Set(exclude.map((tag) => tag.toLowerCase()));
  return data.suggestions
    .filter((item) => !skip.has(item.tag.toLowerCase()))
    .map((item) => ({ value: item.tag, label: item.tag, hint: String(item.count) }));
}

async function fetchBookSuggestions(query) {
  const params = new URLSearchParams({ q: query || "", limit: "10" });
  const data = await api(`/api/books/suggest?${params}`);
  return data.suggestions.map((item) => ({
    value: item.book,
    label: item.book,
    hint: String(item.count),
  }));
}

/* ------------------------------------------------------------- Tag-Eingabe */

/** Wie ntm.tags.normalize_tag im Backend: getrimmte Segmente, einfache Trenner. */
function normalizeTagText(raw) {
  return String(raw || "")
    .split("/")
    .map((part) => part.trim())
    .filter(Boolean)
    .join("/");
}

/** Chips + Eingabefeld mit Typeahead. Gibt {root, input, values, set} zurück. */
function createTagField({ values = [], onChange, placeholder = "Schlagwort …" }) {
  let tags = [...values];
  const chips = h("div", { class: "chips" });
  const input = h("input", { type: "text", placeholder, class: "tag-input" });
  const combo = h("div", { class: "combo" }, input);
  const root = h("div", { class: "tagfield" }, chips, combo);

  const drawChips = () => {
    clear(chips);
    tags.forEach((tag, index) => {
      chips.append(
        h(
          "span",
          { class: "chip" },
          h("span", { class: "chip-label", text: tag }),
          h("button", {
            type: "button",
            class: "chip-remove",
            tabIndex: -1,
            title: "Entfernen",
            text: "×",
            onclick: () => remove(index),
          }),
        ),
      );
    });
  };

  const changed = () => {
    drawChips();
    if (onChange) onChange([...tags]);
  };

  const add = (tag) => {
    const value = normalizeTagText(tag);
    if (!value) return false;
    if (tags.some((existing) => existing.toLowerCase() === value.toLowerCase())) return false;
    tags.push(value);
    changed();
    return true;
  };

  const remove = (index) => {
    tags.splice(index, 1);
    changed();
    input.focus();
  };

  const typeahead = attachTypeahead(input, {
    fetchItems: async (query) => {
      const found = await fetchTagSuggestions(query, tags);
      // Was getippt wurde, aber noch nicht existiert, steht als eigener
      // Eintrag am Ende – so ist immer sichtbar, was Enter tun wird.
      const typed = normalizeTagText(query);
      if (typed && !found.some((item) => item.value.toLowerCase() === typed.toLowerCase())) {
        found.push({ value: typed, label: typed, hint: "neu" });
      }
      return found;
    },
    onPick: (item) => {
      add(item.value);
      input.value = "";
      typeahead.reload();
    },
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === ",") {
      if (input.value.trim()) {
        add(input.value);
        input.value = "";
        event.preventDefault();
        event.stopPropagation(); // Fokus bleibt im Schlagwortfeld
      }
      return; // leeres Feld: Enter darf weiterspringen
    }
    if (event.key === "Tab" && !event.shiftKey && input.value.trim()) {
      add(input.value);
      input.value = "";
      return; // Fokus darf weiterwandern
    }
    if (event.key === "Backspace" && !input.value && tags.length) {
      tags.pop();
      changed();
      event.preventDefault();
    }
  });

  drawChips();
  return {
    root,
    input,
    get values() {
      return [...tags];
    },
    set(next) {
      tags = [...next];
      drawChips();
    },
  };
}

/* ----------------------------------------------------------------- Layout */

function mount(...children) {
  clear(app);
  append(app, children);
}

function topbar(...children) {
  return h("header", { class: "topbar" }, ...children);
}

function iconButton(label, title, onclick, extra = "") {
  return h("button", { type: "button", class: `btn ${extra}`, title, onclick, text: label });
}

/* ------------------------------------------------------------------ Login */

function renderLogin() {
  document.title = "Anmelden – Therapiematerialien";
  const password = h("input", {
    type: "password",
    placeholder: "Passwort",
    autofocus: true,
    autocomplete: "current-password",
  });
  const form = h(
    "form",
    {
      class: "login",
      onsubmit: async (event) => {
        event.preventDefault();
        try {
          const data = await api("/api/login", { method: "POST", body: { password: password.value } });
          session.token = data.token || "";
          localStorage.setItem(TOKEN_KEY, session.token);
          if (await loadMeta()) route();
        } catch (error) {
          toast(error.status === 401 ? "Falsches Passwort" : error.message, "error");
          password.select();
        }
      },
    },
    h("h1", { text: "Therapiematerialien" }),
    h("label", { text: "Passwort" }, password),
    h("button", { type: "submit", class: "btn primary", text: "Anmelden" }),
  );
  mount(form);
  password.focus();
}

/* ------------------------------------------------------------------ Suche */

let searchView = null;

function createSearchView() {
  const state = { q: "", tags: [], age: "", mode: localStorage.getItem(LISTVIEW_KEY) || "detail" };
  let controller = null;

  const q = h("input", {
    type: "search",
    class: "q",
    placeholder: "Volltext in Titel und Text …",
    autocomplete: "off",
    enterkeyhint: "search",
  });

  const tagField = createTagField({
    placeholder: "Schlagwort filtern …",
    onChange: (values) => {
      state.tags = values;
      commit();
    },
  });

  const ageSelect = h("select", {
    class: "age",
    onchange: () => {
      state.age = ageSelect.value;
      commit();
    },
  });

  const modeButton = h("button", {
    type: "button",
    class: "btn ghost mode",
    title: "Ansicht umschalten (v oder Alt+V)",
    onclick: toggleMode,
  });

  const count = h("span", { class: "count" });
  const results = h("ol", { class: "results" });

  const clearButton = h("button", {
    type: "button",
    class: "btn ghost clear",
    text: "Filter löschen",
    title: "Alle Filter zurücksetzen",
    onclick: () => {
      state.q = "";
      state.tags = [];
      state.age = "";
      q.value = "";
      tagField.set([]);
      ageSelect.value = "";
      commit();
      tagField.input.focus();
    },
  });

  // Kopf- und Filterzeile sind ein einziger klebender Block: sonst schöbe
  // sich die Filterzeile beim Scrollen unter die Kopfzeile.
  const root = h(
    "div",
    { class: "view search-view" },
    h(
      "header",
      { class: "searchbar" },
      h(
        "div",
        { class: "searchbar-row" },
        tagField.root,
        h("button", {
          type: "button",
          class: "btn primary neu",
          text: "+ Neu",
          title: "Neuer Eintrag (n oder Alt+N)",
          onclick: () => go("/new"),
        }),
      ),
      h(
        "div",
        { class: "searchbar-row secondary" },
        h("label", { class: "age-filter" }, h("span", { text: "Alter" }), ageSelect),
        h("div", { class: "combo grow" }, q),
      ),
    ),
    h("div", { class: "status" }, count, h("div", { class: "list-actions" }, clearButton, modeButton)),
    results,
  );

  function fillAges() {
    clear(ageSelect);
    ageSelect.append(h("option", { value: "", text: "alle" }));
    for (const item of meta.ages) {
      ageSelect.append(h("option", { value: String(item.value), text: item.label }));
    }
    ageSelect.value = state.age;
  }

  function toggleMode() {
    state.mode = state.mode === "compact" ? "detail" : "compact";
    localStorage.setItem(LISTVIEW_KEY, state.mode);
    drawMode();
  }

  function drawMode() {
    results.classList.toggle("compact", state.mode === "compact");
    modeButton.textContent = state.mode === "compact" ? "Nur Titel" : "Mit Angaben";
  }

  function params() {
    const search = new URLSearchParams();
    if (state.q) search.set("q", state.q);
    for (const tag of state.tags) search.append("tag", tag);
    if (state.age) search.set("age", state.age);
    return search;
  }

  /** Zustand in die URL schreiben (ohne History-Eintrag) und neu suchen. */
  function commit() {
    const search = params().toString();
    history.replaceState(null, "", `#/${search ? `?${search}` : ""}`);
    refresh();
  }

  const commitSoon = debounce(commit, 130);
  q.addEventListener("input", () => {
    state.q = q.value;
    commitSoon();
  });

  q.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      const first = results.querySelector("a.result");
      if (first) first.focus();
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      const first = results.querySelector("a.result");
      if (first) first.focus();
    }
  });

  results.addEventListener("keydown", (event) => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const links = [...results.querySelectorAll("a.result")];
    const index = links.indexOf(document.activeElement);
    if (index < 0) return;
    event.preventDefault();
    if (event.key === "ArrowUp" && index === 0) {
      q.focus();
      q.select();
      return;
    }
    const next = links[index + (event.key === "ArrowDown" ? 1 : -1)];
    if (next) next.focus();
  });

  function drawResults(data) {
    clear(results);
    if (!data.entries.length) {
      count.textContent = "Keine Treffer.";
      return;
    }
    count.textContent =
      data.total === data.entries.length
        ? `${data.total} ${data.total === 1 ? "Eintrag" : "Einträge"}`
        : `${data.entries.length} von ${data.total} Einträgen`;
    for (const entry of data.entries) {
      results.append(
        h(
          "li",
          {},
          h(
            "a",
            { class: "result", href: `#/e/${entry.id}` },
            h(
              "div",
              { class: "result-head" },
              h("span", { class: "result-title", text: entry.title }),
              h("span", { class: "result-age", text: entry.age_label }),
            ),
            h(
              "div",
              { class: "result-meta" },
              entry.book ? h("span", { class: "meta-book", text: entry.book }) : null,
              entry.book && entry.location ? h("span", { class: "meta-sep", text: "·" }) : null,
              entry.location ? h("span", { class: "meta-location", text: entry.location }) : null,
              ...entry.tags.map((tag) => h("span", { class: "tag", text: tag })),
            ),
          ),
        ),
      );
    }
  }

  async function refresh() {
    // Zurücksetzen anzubieten ergibt nur Sinn, wenn etwas gesetzt ist.
    clearButton.hidden = !(state.q || state.tags.length || state.age);
    if (controller) controller.abort();
    controller = new AbortController();
    const search = params();
    search.set("limit", "300");
    try {
      const data = await api(`/api/search?${search}`, { signal: controller.signal });
      drawResults(data);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      if (error.status !== 401) {
        count.textContent = "";
        toast(error.message, "error");
      }
    }
  }

  return {
    root,
    /** which: "q" für die Volltextsuche, sonst das Schlagwortfeld. */
    focus(which) {
      const field = which === "q" ? q : tagField.input;
      field.focus();
      if (field.select) field.select();
    },
    toggleMode,
    sync(search) {
      state.q = search.get("q") || "";
      state.tags = search.getAll("tag");
      state.age = search.get("age") || "";
      if (q.value !== state.q) q.value = state.q;
      tagField.set(state.tags);
      fillAges();
      drawMode();
      refresh();
    },
  };
}

// Beim Betreten der Suche bekommt bewusst *kein* Feld den Fokus: sonst
// landen die Buchstabenkürzel im Eingabefeld statt im Programm.
let focusAfterRoute = null;

function renderSearch(search) {
  document.title = "Therapiematerialien";
  if (!searchView) searchView = createSearchView();
  mount(searchView.root);
  searchView.sync(search);
  if (focusAfterRoute) {
    searchView.focus(focusAfterRoute);
    focusAfterRoute = null;
  }
}

/* ------------------------------------------------------------ Detailseite */

async function renderDetail(id) {
  let entry;
  try {
    entry = await api(`/api/entries/${encodeURIComponent(id)}`);
  } catch (error) {
    if (error.status === 401) return;
    toast(error.message, "error");
    go("/");
    return;
  }
  document.title = `${entry.title} – Therapiematerialien`;

  const remove = async () => {
    if (!confirm(`„${entry.title}“ wirklich löschen?`)) return;
    try {
      await api(`/api/entries/${encodeURIComponent(id)}`, { method: "DELETE" });
      toast("Eintrag gelöscht");
      await loadMeta();
      go("/", null, { replace: true });
    } catch (error) {
      toast(error.message, "error");
    }
  };

  const view = h(
    "div",
    { class: "view detail-view", tabIndex: -1 },
    topbar(
      iconButton("← Zurück", "Zurück (Esc)", () => back(), "ghost"),
      h("div", { class: "spacer" }),
      iconButton("Bearbeiten", "Bearbeiten (e)", () => go(`/e/${id}/edit`), "primary"),
      iconButton("Löschen", "Löschen (Entf)", remove, "danger"),
    ),
    h("article", { class: "detail" }, [
      h("h1", { text: entry.title }),
      h(
        "div",
        { class: "detail-meta" },
        h("span", { class: "pill age", text: `Alter ${entry.age_label}` }),
        entry.book ? h("span", { class: "pill", text: entry.book }) : null,
        entry.location ? h("span", { class: "pill", text: entry.location }) : null,
      ),
      entry.tags.length
        ? h(
            "div",
            { class: "detail-tags" },
            ...entry.tags.map((tag) =>
              h("a", { class: "tag link", href: `#/?tag=${encodeURIComponent(tag)}`, text: tag }),
            ),
          )
        : null,
      entry.text_html ? h("div", { class: "markdown", html: entry.text_html }) : null,
    ]),
  );

  view.addEventListener("keydown", (event) => {
    if (isTyping(event.target) || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === "e") {
      event.preventDefault();
      go(`/e/${id}/edit`);
    } else if (event.key === "Delete") {
      event.preventDefault();
      remove();
    }
  });

  mount(view);
  view.focus();
}

/* ----------------------------------------------------------------- Formular */

const AGE_DEFAULT = { from: "5", to: "21" };
let carryOver = null; // Buch/Alter für „Speichern und neu“

async function renderForm(id) {
  const isNew = !id;
  let original = null;
  if (!isNew) {
    try {
      original = await api(`/api/entries/${encodeURIComponent(id)}`);
    } catch (error) {
      if (error.status === 401) return;
      toast(error.message, "error");
      go("/");
      return;
    }
  }
  document.title = isNew ? "Neuer Eintrag – Therapiematerialien" : `Bearbeiten: ${original.title}`;

  const initial = original || {
    title: "",
    text: "",
    tags: [],
    book: (carryOver && carryOver.book) || "",
    location: "",
    age_from: (carryOver && carryOver.age_from) || AGE_DEFAULT.from,
    age_to: (carryOver && carryOver.age_to) || AGE_DEFAULT.to,
  };

  const title = h("input", { type: "text", value: initial.title, required: true, placeholder: "Titel" });
  const text = h("textarea", { rows: 12, placeholder: "Fließtext (Markdown, optional)" });
  text.value = initial.text || "";
  const tagField = createTagField({ values: initial.tags, placeholder: "Schlagwort, z. B. Sprache/Grammatik/Kasus" });
  const book = h("input", { type: "text", value: initial.book, placeholder: "Buch, Zeitschrift, „digital“ …" });
  const place = h("input", { type: "text", value: initial.location, placeholder: "Seite, Kapitel, Pfad …" });
  const ageFrom = h("select", {});
  const ageTo = h("select", {});

  for (const select of [ageFrom, ageTo]) {
    for (const item of meta.ages) {
      select.append(h("option", { value: String(item.value), text: item.label }));
    }
  }
  ageFrom.value = String(initial.age_from);
  ageTo.value = String(initial.age_to);
  const ageIndex = (value) => meta.ages.findIndex((item) => String(item.value) === value);
  ageFrom.addEventListener("change", () => {
    if (ageIndex(ageFrom.value) > ageIndex(ageTo.value)) ageTo.value = ageFrom.value;
  });
  ageTo.addEventListener("change", () => {
    if (ageIndex(ageTo.value) < ageIndex(ageFrom.value)) ageFrom.value = ageTo.value;
  });

  const bookCombo = attachTypeahead(book, {
    fetchItems: fetchBookSuggestions,
    onPick: (item) => (book.value = item.value),
  }).root;

  const payload = () => ({
    title: title.value,
    text: text.value,
    tags: tagField.values,
    book: book.value,
    location: place.value,
    age_from: ageFrom.value,
    age_to: ageTo.value,
  });

  const snapshot = JSON.stringify(payload());
  const dirty = () => JSON.stringify(payload()) !== snapshot;
  let saving = false;

  async function save(andNew = false) {
    if (saving) return;
    if (!title.value.trim()) {
      toast("Ohne Titel geht es nicht", "error");
      title.focus();
      return;
    }
    saving = true;
    try {
      const data = payload();
      const saved = isNew
        ? await api("/api/entries", { method: "POST", body: data })
        : await api(`/api/entries/${encodeURIComponent(id)}`, { method: "PUT", body: data });
      toast("Gespeichert");
      await loadMeta();
      guard.enabled = false;
      if (andNew) {
        // Buch und Altersbereich bleiben stehen – meist kommt der nächste
        // Eintrag aus derselben Quelle.
        carryOver = { book: saved.book, age_from: saved.age_from, age_to: saved.age_to };
        if (window.location.hash === "#/new") renderForm(null); // Route unverändert
        else go("/new");
      } else {
        carryOver = null;
        go(`/e/${saved.id}`, null, { replace: true });
      }
    } catch (error) {
      if (error.status !== 401) toast(error.message, "error");
    } finally {
      saving = false;
    }
  }

  function cancel() {
    if (dirty() && !confirm("Änderungen verwerfen?")) return;
    guard.enabled = false;
    carryOver = null;
    if (isNew) go("/");
    else go(`/e/${id}`, null, { replace: true });
  }

  const fieldRow = (label, hint, ...controls) =>
    h(
      "div",
      { class: "field" },
      h("label", { class: "field-label" }, h("span", { text: label }), hint ? h("small", { text: hint }) : null),
      h("div", { class: "field-control" }, ...controls),
    );

  const form = h(
    "form",
    {
      class: "entry-form",
      autocomplete: "off",
      onsubmit: (event) => {
        event.preventDefault();
        save(false);
      },
    },
    fieldRow("Titel", null, title),
    fieldRow("Fließtext", "Markdown, optional", text),
    fieldRow("Schlagworte", "Enter übernimmt, Backspace löscht", tagField.root),
    fieldRow("Buch", null, bookCombo),
    fieldRow("Ort", "Seite, Kapitel, Pfad", place),
    fieldRow(
      "Alter",
      "„Eltern“ ist der oberste Punkt der Skala",
      h("div", { class: "age-range" }, ageFrom, h("span", { class: "dash", text: "–" }), ageTo),
    ),
    h(
      "div",
      { class: "form-actions" },
      h("button", { type: "submit", class: "btn primary", text: "Speichern", title: "Strg+S" }),
      h("button", {
        type: "button",
        class: "btn",
        text: "Speichern und neu",
        title: "Strg+Enter",
        onclick: () => save(true),
      }),
      h("button", { type: "button", class: "btn ghost", text: "Abbrechen", title: "Esc", onclick: cancel }),
    ),
  );

  // Tastenfluss: Enter springt weiter, Tab verlässt auch die Textarea.
  form.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      save(false);
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      save(true);
      return;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation(); // der globale Handler soll nicht zusätzlich zurückspringen
      cancel();
      return;
    }
    if (event.key === "Tab" && event.target === text && !event.shiftKey) {
      event.preventDefault();
      focusNext(form, text);
      return;
    }
    if (event.key === "Enter" && !event.ctrlKey && !event.metaKey) {
      // Schlagwort- und Buchfeld fangen Enter selbst ab, solange dort etwas
      // zu übernehmen ist; hier kommt nur noch der Sprung ins nächste Feld an.
      const target = event.target;
      if (target.tagName === "INPUT" || target.tagName === "SELECT") {
        event.preventDefault();
        focusNext(form, target);
      }
    }
  });

  const view = h(
    "div",
    { class: "view form-view" },
    topbar(
      h("h1", { class: "form-title", text: isNew ? "Neuer Eintrag" : "Eintrag bearbeiten" }),
      h("div", { class: "spacer" }),
      iconButton("Abbrechen", "Esc", cancel, "ghost"),
    ),
    form,
  );

  mount(view);
  title.focus();
  title.select();
  guard.enabled = true;
  guard.dirty = dirty;
}

function focusNext(container, current) {
  // tabIndex -1 hält die Löschknöpfe der Chips draußen; auf eine
  // Layout-Abfrage (offsetParent) verzichten wir bewusst – sie ist auch für
  // position:fixed null und im Formular ist ohnehin alles sichtbar.
  const focusables = [...container.querySelectorAll("input, textarea, select, button")].filter(
    (node) => !node.disabled && node.tabIndex !== -1 && !node.hidden,
  );
  const index = focusables.indexOf(current);
  const next = focusables[index + 1];
  if (next) {
    next.focus();
    if (next.select) next.select();
  }
}

const guard = { enabled: false, dirty: () => false };
window.addEventListener("beforeunload", (event) => {
  if (guard.enabled && guard.dirty()) {
    event.preventDefault();
    event.returnValue = "";
  }
});

/* --------------------------------------------------------------- Hilfe */

const SHORTCUTS = [
  ["n", "Neuen Eintrag anlegen"],
  ["t", "Zum Schlagwortfilter"],
  ["/", "Zur Volltextsuche"],
  ["v", "Listenansicht umschalten"],
  ["?", "Diese Hilfe"],
  ["Alt + n t / v h", "dieselben Befehle, auch während man in einem Feld tippt"],
  ["Esc", "Fokus aus dem Feld nehmen, Vorschlagsliste schließen, zurück"],
  ["↑ ↓", "In der Trefferliste blättern"],
  ["Enter", "Eintrag öffnen; im Formular ins nächste Feld"],
  ["e", "Eintrag bearbeiten (in der Detailansicht)"],
  ["Entf", "Eintrag löschen (in der Detailansicht)"],
  ["Enter , ", "Schlagwort übernehmen (Vorschlag oder Getipptes)"],
  ["Tab", "Nächstes Feld, übernimmt dabei den Vorschlag"],
  ["Strg + s", "Speichern"],
  ["Strg + Enter", "Speichern und gleich den nächsten Eintrag anlegen"],
];

function showHelp() {
  const dialog = h(
    "dialog",
    { class: "help", onclose: () => dialog.remove() },
    h("h2", { text: "Tastenkürzel" }),
    h(
      "dl",
      {},
      ...SHORTCUTS.flatMap(([key, description]) => [
        h("dt", {}, h("kbd", { text: key })),
        h("dd", { text: description }),
      ]),
    ),
    h("button", { class: "btn", text: "Schließen", onclick: () => dialog.close() }),
  );
  document.body.append(dialog);
  dialog.showModal();
}

/* ------------------------------------------------------------- Fußzeile */

function drawFooter() {
  clear(foot);
  if (!meta.app) return;
  const dot = () => h("span", { class: "foot-dot", text: "·" });
  append(foot, [
    // "insgesamt", weil die Statuszeile darüber die Treffer der Suche zählt.
    h("span", { text: `${meta.entries} ${meta.entries === 1 ? "Eintrag" : "Einträge"} insgesamt` }),
    dot(),
    h("span", { title: "Datenmodell und Programmstand", text: `ntm ${meta.app.version}` }),
    meta.app.revision ? [dot(), h("code", { class: "rev", text: meta.app.revision })] : null,
    dot(),
    h("button", { type: "button", class: "linkish", text: "Tastenkürzel", onclick: showHelp }),
  ]);
}

/* ----------------------------------------------------------------- Router */

let meta = { ages: [], tags: [], books: [] };

function go(path, search = null, { replace = false } = {}) {
  const target = `#${path}${search && String(search) ? `?${search}` : ""}`;
  if (replace) history.replaceState(null, "", target);
  else location.hash = target;
  if (replace) route();
}

function back() {
  if (history.length > 1) history.back();
  else go("/");
}

function route() {
  const raw = location.hash.slice(1) || "/";
  const [path, queryString] = raw.split("?");
  const search = new URLSearchParams(queryString || "");
  guard.enabled = false;
  if (session.required && !session.token) {
    renderLogin();
    return;
  }
  const editMatch = path.match(/^\/e\/([^/]+)\/edit$/);
  const detailMatch = path.match(/^\/e\/([^/]+)$/);
  if (path === "/new") renderForm(null);
  else if (editMatch) renderForm(decodeURIComponent(editMatch[1]));
  else if (detailMatch) renderDetail(decodeURIComponent(detailMatch[1]));
  else renderSearch(search);
}

window.addEventListener("hashchange", route);

/*
 * Zwei Wege zum selben Ziel:
 *
 *   – einzelne Buchstaben, solange der Fokus in keinem Eingabefeld steht,
 *   – dieselben Befehle mit Alt, die auch beim Tippen greifen.
 *
 * Für die Alt-Kürzel zählt `event.code`, nicht `event.key`: mit gedrückter
 * Alt-Taste liefern manche Tastaturbelegungen Sonderzeichen statt Buchstaben.
 */
const COMMANDS = {
  KeyN: () => go("/new"),
  KeyT: () => focusFilter("tag"),
  KeyF: () => focusFilter("q"),
  KeyV: () => searchView && searchView.toggleMode(),
  KeyH: () => showHelp(),
};

const LETTER_COMMANDS = {
  n: COMMANDS.KeyN,
  t: COMMANDS.KeyT,
  "/": COMMANDS.KeyF,
  v: COMMANDS.KeyV,
  "?": COMMANDS.KeyH,
};

/** Springt zur Suche (falls nötig) und fokussiert dort ein Filterfeld. */
function focusFilter(which) {
  const onSearch = location.hash === "" || location.hash === "#/" || location.hash.startsWith("#/?");
  if (onSearch && searchView) {
    searchView.focus(which);
  } else {
    focusAfterRoute = which;
    go("/");
  }
}

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey || event.metaKey) return;
  const inDialog = document.querySelector("dialog[open]");
  if (inDialog) return; // der Dialog kümmert sich selbst um Esc

  if (event.key === "Escape") {
    if (isTyping(event.target)) {
      // Fokus aus dem Feld nehmen, damit die Buchstabenkürzel wieder greifen.
      event.target.blur();
      return;
    }
    if (!location.hash.startsWith("#/e/") && location.hash !== "#/new") return;
    event.preventDefault();
    back();
    return;
  }

  // Im Formular würde jede Navigation die Eingabe wegwerfen.
  if (guard.enabled) return;

  if (event.altKey) {
    const command = COMMANDS[event.code];
    if (command) {
      event.preventDefault();
      command();
    }
    return;
  }

  if (isTyping(event.target)) return;
  const command = LETTER_COMMANDS[event.key];
  if (command) {
    event.preventDefault();
    command();
  }
});

/* ------------------------------------------------------------------ Start */

async function loadMeta() {
  try {
    meta = await api("/api/meta");
    drawFooter();
    return true;
  } catch (error) {
    if (error.status !== 401) toast(error.message, "error");
    return false;
  }
}

async function boot() {
  try {
    const info = await fetch("/api/auth").then((response) => response.json());
    session.required = Boolean(info.required);
  } catch (_) {
    session.required = true;
  }
  if (session.required && !session.token) {
    renderLogin();
    return;
  }
  if (await loadMeta()) route();
}

boot();
