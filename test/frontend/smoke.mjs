/*
 * Headless-Durchlauf des Frontends: app.js wird in eine jsdom-Seite geladen
 * und gegen ein nachgebautes Backend bedient – vor allem, um die
 * Tastaturwege durchzuspielen, die man von Hand ständig neu klicken müsste.
 *
 * Start:  node smoke.mjs [pfad/zu/app.js]
 *
 * jsdom ist die einzige npm-Abhängigkeit des Projekts und wird nur hier
 * gebraucht; die App selbst kommt weiterhin ohne JavaScript-Ökosystem aus.
 */
import { JSDOM } from "jsdom";
import fs from "node:fs";

const APP = process.argv[2] || new URL("../../src/ntm/static/app.js", import.meta.url).pathname;

/* ------------------------------------------------------------ Fake-Backend */

const AGES = [
  ...Array.from({ length: 17 }, (_, i) => ({ value: i + 5, label: i + 5 === 21 ? "21+" : String(i + 5) })),
  { value: "Eltern", label: "Eltern" },
];

let nextId = 100;
const db = new Map();
function seed(entry) {
  const id = `e${nextId++}`;
  db.set(id, { id, text: "", tags: [], book: "", location: "", age_from: 5, age_to: 21, ...entry });
  return id;
}
seed({ title: "Kasus-Memory", text: "Memory zu Dativ", tags: ["Sprache/Grammatik/Kasus"], book: "Sprachförderung konkret", location: "S. 45", age_from: 7, age_to: 12 });
seed({ title: "Wortschatzkiste", text: "Bildkarten", tags: ["Sprache/Wortschatz"], book: "Sprachförderung konkret", age_from: 5, age_to: 9 });
seed({ title: "Elternbrief", tags: ["Mit Eltern"], book: "digital", age_from: "Eltern", age_to: "Eltern" });

const label = (from, to) => (String(from) === String(to) ? String(from) : `${from}–${to}`);
const summary = (e) => ({ ...e, age_label: label(e.age_from, e.age_to), has_text: Boolean(e.text) });
const detail = (e) => ({ ...summary(e), text_html: e.text ? `<p>${e.text}</p>` : "", created: "2026-01-01T00:00:00Z", updated: "2026-01-01T00:00:00Z" });

const calls = [];

function respond(data, status = 200) {
  return Promise.resolve({
    ok: status < 400,
    status,
    json: () => Promise.resolve(data),
  });
}

function fakeFetch(path, options = {}) {
  const url = new URL(path, "http://localhost");
  const method = (options.method || "GET").toUpperCase();
  calls.push(`${method} ${url.pathname}`);
  const p = url.pathname;
  const q = url.searchParams;

  if (p === "/api/auth") return respond({ required: false });
  if (p === "/api/meta") {
    return respond({
      ages: AGES,
      tags: [
        { tag: "Sprache", count: 2 },
        { tag: "Sprache/Grammatik", count: 1 },
        { tag: "Sprache/Grammatik/Kasus", count: 1 },
        { tag: "Sprache/Wortschatz", count: 1 },
        { tag: "Mit Eltern", count: 1 },
      ],
      books: [{ book: "Sprachförderung konkret", count: 2 }, { book: "digital", count: 1 }],
      entries: db.size,
      app: { version: "0.1.0", revision: "abc12345" },
    });
  }
  if (p === "/api/tags/suggest") {
    const needle = (q.get("q") || "").toLowerCase();
    const all = ["Sprache", "Sprache/Grammatik", "Sprache/Grammatik/Kasus", "Sprache/Wortschatz", "Mit Eltern"];
    return respond({ suggestions: all.filter((t) => t.toLowerCase().includes(needle)).map((t) => ({ tag: t, count: 1 })) });
  }
  if (p === "/api/books/suggest") {
    const needle = (q.get("q") || "").toLowerCase();
    const all = ["Sprachförderung konkret", "digital"];
    return respond({ suggestions: all.filter((b) => b.toLowerCase().includes(needle)).map((b) => ({ book: b, count: 1 })) });
  }
  if (p === "/api/search") {
    const needle = (q.get("q") || "").toLowerCase();
    const wantedTags = q.getAll("tag");
    const age = q.get("age");
    let hits = [...db.values()];
    if (needle) hits = hits.filter((e) => `${e.title} ${e.text}`.toLowerCase().includes(needle));
    for (const tag of wantedTags) hits = hits.filter((e) => e.tags.some((t) => t === tag || t.startsWith(`${tag}/`)));
    if (age) hits = hits.filter((e) => String(e.age_from) === age || String(e.age_to) === age || (Number(e.age_from) <= Number(age) && Number(age) <= Number(e.age_to)));
    hits.sort((a, b) => a.title.localeCompare(b.title));
    return respond({ total: hits.length, entries: hits.map(summary) });
  }
  const entryMatch = p.match(/^\/api\/entries\/(.+)$/);
  if (p === "/api/entries" && method === "POST") {
    const body = JSON.parse(options.body);
    const id = seed(body);
    return respond(detail(db.get(id)), 201);
  }
  if (entryMatch) {
    const id = entryMatch[1];
    if (!db.has(id)) return respond({ detail: "unbekannter Eintrag" }, 404);
    if (method === "PUT") {
      db.set(id, { ...db.get(id), ...JSON.parse(options.body), id });
      return respond(detail(db.get(id)));
    }
    if (method === "DELETE") {
      db.delete(id);
      return respond({ deleted: true });
    }
    return respond(detail(db.get(id)));
  }
  return respond({ detail: "not found" }, 404);
}

/* ------------------------------------------------------------------ Bühne */

const dom = new JSDOM(
  `<!doctype html><html><body><div id="app" class="app"></div><footer id="foot"></footer><div id="toasts"></div></body></html>`,
  { url: "http://localhost/", runScripts: "dangerously", pretendToBeVisual: true },
);
const { window } = dom;
const { document } = window;

window.fetch = fakeFetch;
window.matchMedia = () => ({ matches: true, addEventListener() {}, removeEventListener() {} });
let confirmAnswer = true;
window.confirm = () => confirmAnswer;

const errors = [];
window.addEventListener("error", (event) => errors.push(String(event.error || event.message)));
window.addEventListener("unhandledrejection", (event) => errors.push(`unhandled rejection: ${event.reason}`));
process.on("unhandledRejection", (reason) => errors.push(`unhandled rejection: ${reason && reason.stack ? reason.stack : reason}`));

const script = document.createElement("script");
script.textContent = fs.readFileSync(APP, "utf8");
document.body.appendChild(script);

/* ------------------------------------------------------------------ Helfer */

const wait = (ms = 40) => new Promise((resolve) => window.setTimeout(resolve, ms));
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

function key(target, name, options = {}) {
  const event = new window.KeyboardEvent("keydown", { key: name, bubbles: true, cancelable: true, ...options });
  target.dispatchEvent(event);
  return event;
}

function type(input, value) {
  input.value = value;
  input.dispatchEvent(new window.Event("input", { bubbles: true }));
}

const results = [];
function check(name, condition, info = "") {
  results.push({ name, ok: Boolean(condition), info });
  if (!condition) console.error(`  ✗ ${name} ${info}`);
}

/* ------------------------------------------------------------------- Test */

await wait(80);

check("Suchansicht gerendert", $(".search-view"));
check("Kein Feld greift den Fokus ab", document.activeElement === document.body, document.activeElement.tagName);
check("Fußzeile zeigt Anzahl und Stand", $("#foot").textContent.includes("3 Einträge") && $("#foot").textContent.includes("abc12345"), $("#foot").textContent);
check("Treffer geladen", $$("a.result").length === 3, `(${$$("a.result").length})`);
check("Altersfilter gefüllt", $("select.age") && $("select.age").options.length === 19);

// Volltextsuche
type($("input.q"), "memory");
await wait(220);
check("Volltextsuche filtert", $$("a.result").length === 1, `(${$$("a.result").length})`);
check("Filter steht in der URL", window.location.hash.includes("q=memory"), window.location.hash);
type($("input.q"), "");
await wait(220);

// Tastatur: Ergebnisliste
$("input.q").focus();
key($("input.q"), "ArrowDown");
check("Pfeiltaste springt in die Liste", document.activeElement === $$("a.result")[0]);
key(document.activeElement, "ArrowDown");
check("Pfeiltaste blättert weiter", document.activeElement === $$("a.result")[1]);

// Tag-Filter über Typeahead
const filterTagInput = $(".searchbar .tag-input");
filterTagInput.focus();
type(filterTagInput, "wortschatz");
await wait(200);
check("Vorschläge erscheinen", $$(".searchbar .suggest-item").length > 0);
key(filterTagInput, "Enter");
await wait(220);
check("Tag wird zum Chip", $(".searchbar .chip-label") && $(".searchbar .chip-label").textContent === "Sprache/Wortschatz");
check("Tag-Filter wirkt", $$("a.result").length === 1, `(${$$("a.result").length})`);
key(filterTagInput, "Backspace");
await wait(220);
check("Backspace entfernt den Chip", !$(".searchbar .chip"));

// Tastenkürzel, obwohl der Fokus in einem Textfeld steht
$("input.q").focus();
key($("input.q"), "Escape");
check("Esc nimmt den Fokus aus dem Suchfeld", document.activeElement !== $("input.q"));
key(document.body, "t");
check("t springt in den Schlagwortfilter", document.activeElement === $(".searchbar .tag-input"));
$("input.q").focus();
key($("input.q"), "n", { altKey: true, code: "KeyN" });
await wait(80);
check("Alt+N wirkt auch im Textfeld", $(".form-view"));
key($(".entry-form"), "Escape");
await wait(100);
check("Zurück in der Suche", $(".search-view"));

// Neuer Eintrag – der Ablauf ohne Maus
key(document.body, "n");
await wait(80);
check("Formular offen", $(".form-view"));
const fields = () => $$(".entry-form input, .entry-form textarea, .entry-form select");
const titleInput = $(".entry-form input");
check("Fokus im Titel", document.activeElement === titleInput);

titleInput.value = "Silbenteppich";
key(titleInput, "Enter");
const textArea = $(".entry-form textarea");
check("Enter springt vom Titel in den Fließtext", document.activeElement === textArea);
textArea.value = "## Ablauf\n\nSilben klatschen.";
key(textArea, "Tab");
const tagInput = $(".entry-form .tag-input");
check("Tab verlässt die Textarea", document.activeElement === tagInput);

// Schlagwort per Vorschlag
type(tagInput, "kasus");
await wait(200);
check("Tag-Vorschläge im Formular", $$(".entry-form .suggest-item").length > 0);
key(tagInput, "Enter");
await wait(120);
check("Vorschlag übernommen", $$(".entry-form .chip-label").map((n) => n.textContent).includes("Sprache/Grammatik/Kasus"));
check("Fokus bleibt im Schlagwortfeld", document.activeElement === tagInput);

// Neues Schlagwort frei eintippen
type(tagInput, "Format/Bewegung");
await wait(200);
key(tagInput, "Escape");
key(tagInput, "Enter");
await wait(120);
check("Neues Schlagwort angelegt", $$(".entry-form .chip-label").map((n) => n.textContent).includes("Format/Bewegung"));

// Leeres Tag-Feld: Enter geht weiter
type(tagInput, "");
await wait(120);
key(tagInput, "Escape");
key(tagInput, "Enter");
const bookInput = $(".entry-form .field:nth-of-type(4) input");
check("Enter im leeren Tagfeld springt zum Buch", document.activeElement === bookInput, document.activeElement.outerHTML.slice(0, 60));

// Buch per Typeahead
type(bookInput, "sprach");
await wait(200);
check("Buch-Vorschläge", $$(".entry-form .suggest-item").length > 0);
key(bookInput, "Enter");
await wait(60);
check("Buch übernommen", bookInput.value === "Sprachförderung konkret", bookInput.value);
key(bookInput, "Enter");
const placeInput = $(".entry-form .field:nth-of-type(5) input");
check("Enter springt zum Ort", document.activeElement === placeInput);
placeInput.value = "S. 7";
key(placeInput, "Enter");
const ageFrom = $$(".entry-form select")[0];
check("Enter springt zum Alter", document.activeElement === ageFrom);

ageFrom.value = "9";
ageFrom.dispatchEvent(new window.Event("change", { bubbles: true }));
const ageTo = $$(".entry-form select")[1];
ageTo.value = "Eltern";
ageTo.dispatchEvent(new window.Event("change", { bubbles: true }));
check("Altersbereich gesetzt", ageFrom.value === "9" && ageTo.value === "Eltern");

// Speichern
const before = db.size;
key($(".entry-form"), "s", { ctrlKey: true });
await wait(150);
check("Eintrag gespeichert", db.size === before + 1, `(${db.size})`);
check("Fußzeile zählt mit", $("#foot").textContent.includes(`${db.size} Einträge`), $("#foot").textContent);
const saved = [...db.values()].at(-1);
check("Alle Felder übertragen",
  saved.title === "Silbenteppich" && saved.tags.length === 2 && saved.book === "Sprachförderung konkret" &&
  saved.location === "S. 7" && saved.age_from === "9" && saved.age_to === "Eltern",
  JSON.stringify(saved));
check("Detailansicht nach dem Speichern", $(".detail-view"), window.location.hash);
check("Markdown gerendert", $(".markdown"));

// Bearbeiten über Tastatur
key($(".detail-view"), "e");
await wait(120);
check("e öffnet das Bearbeiten-Formular", $(".form-view"));
check("Werte vorbelegt", $(".entry-form input").value === "Silbenteppich");
key($(".entry-form"), "Escape");
await wait(120);
check("Esc führt zurück in die Detailansicht", $(".detail-view"), window.location.hash);

// „n" darf im Formular nicht greifen
key($(".detail-view"), "e");
await wait(120);
const saveButton = $(".form-actions button");
saveButton.focus();
key(saveButton, "n");
await wait(60);
check("n im Formular wirkungslos", $(".entry-form input").value === "Silbenteppich" && $(".form-view"));
key($(".entry-form"), "Escape");
await wait(120);

// Speichern und neu
key($(".detail-view"), "e");
await wait(120);
key($(".entry-form"), "Enter", { ctrlKey: true });
await wait(200);
check("Strg+Enter öffnet ein leeres Formular", $(".form-view") && $(".entry-form input").value === "");
check("Buch bleibt stehen", $(".entry-form .field:nth-of-type(4) input").value === "Sprachförderung konkret");
check("Alter bleibt stehen", $$(".entry-form select")[1].value === "Eltern");
confirmAnswer = true;
key($(".entry-form"), "Escape");
await wait(150);

// Löschen
const target = [...db.values()].find((e) => e.title === "Silbenteppich");
window.location.hash = `#/e/${target.id}`;
await wait(150);
check("Detailansicht per URL", $(".detail-view h1") && $(".detail-view h1").textContent === "Silbenteppich");
const sizeBefore = db.size;
key($(".detail-view"), "Delete");
await wait(150);
check("Entf löscht nach Rückfrage", db.size === sizeBefore - 1);
check("Zurück in der Suche", $(".search-view"));

// Tag-Link aus der Detailansicht
window.location.hash = "#/?tag=Sprache";
await wait(200);
check("Tag-Filter aus der URL", $(".searchbar .chip-label") && $(".searchbar .chip-label").textContent === "Sprache");
check("Gefilterte Liste", $$("a.result").length === 2, `(${$$("a.result").length})`);

// Hilfe
window.location.hash = "#/";
await wait(150);
if (typeof window.HTMLDialogElement.prototype.showModal === "function") {
  key(document.body, "?");
  await wait(40);
  check("Hilfe öffnet sich", $("dialog.help"));
}

/* --------------------------------------------------------------- Ergebnis */

console.log("");
for (const r of results) console.log(`${r.ok ? "✓" : "✗"} ${r.name}${r.ok ? "" : ` ${r.info}`}`);
if (errors.length) {
  console.log("\nFehler im Browserkontext:");
  for (const e of errors) console.log(`  ${e}`);
}
const failed = results.filter((r) => !r.ok).length;
console.log(`\n${results.length - failed}/${results.length} Prüfungen bestanden, ${errors.length} Ausnahmen`);
process.exit(failed || errors.length ? 1 : 0);
