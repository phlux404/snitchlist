// SnitchList functional tests.
// Extracts the <script> from ../index.html, runs it in Node under a minimal
// DOM stub, and exercises the real analysis pipeline end to end.
// Run:  npm test   (or: node tests/snitchlist.test.js)
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const INDEX = path.join(__dirname, "..", "index.html");
const html = fs.readFileSync(INDEX, "utf8");
const m = html.match(/<script>([\s\S]*)<\/script>/);
if (!m) { console.error("FAIL: no <script> block found in index.html"); process.exit(1); }
const appJs = m[1];

// 0. Syntax check
try { new vm.Script(appJs, { filename: "snitchlist-app.js" }); console.log("  PASS syntax check (vm.Script)"); }
catch (e) { console.error("  FAIL syntax check:", e.message); process.exit(1); }

// ---------- minimal DOM stub ----------
function makeEl(id) {
  return {
    id,
    value: "",
    innerHTML: "",
    textContent: "",
    style: {},
    dataset: {},
    listeners: {},
    addEventListener(ev, fn) { (this.listeners[ev] = this.listeners[ev] || []).push(fn); },
    click() { (this.listeners["click"] || []).forEach((fn) => fn()); },
    scrollIntoView() {},
  };
}
const els = {};
function el(id) { return (els[id] = els[id] || makeEl(id)); }
["log","analyze","clear","sample","export","toggleclean","drop","file",
 "cards","snitchcount","unkcount","cleancount","results",
 "snitchtable","unktable","markedtable","companytable","cleantable"].forEach(el);

let alertMsg = null;
const store = {};
global.localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: (k) => { delete store[k]; },
};
global.alert = (msg) => { alertMsg = msg; };

const docListeners = {};
global.document = {
  getElementById: (id) => el(id),
  querySelector: (sel) => {
    const mm = sel.match(/^#(\w+)/);
    if (mm) return el(mm[1] + "__tbody");
    return makeEl("q");
  },
  addEventListener: (ev, fn) => { (docListeners[ev] = docListeners[ev] || []).push(fn); },
  createElement: () => makeEl("a"),
};
global.URL = { createObjectURL: () => "blob:fake", revokeObjectURL: () => {} };
global.Blob = function (parts) { this.parts = parts; };

eval(appJs);

// ---------- helpers ----------
let pass = 1, fail = 0; // pass starts at 1: syntax check above
function check(name, cond, extra = "") {
  if (cond) { pass++; console.log("  PASS " + name); }
  else { fail++; console.log("  FAIL " + name + (extra ? " — " + extra : "")); }
}
function tbodyHTML(id) { return el(id + "__tbody").innerHTML; }
function fireDocClick(buttonStub) {
  (docListeners["click"] || []).forEach((fn) => fn({ target: buttonStub }));
}
function verdictBtn(domain, v) {
  return { closest: (sel) => (sel === "button[data-d]" ? { dataset: { d: domain, v } } : null) };
}

// ---------- Test 1: realistic mixed log ----------
console.log("Test 1: realistic mixed log");
el("log").value = `2026-09-21 14:02:11  t.uptodown.app  A  blocked
2026-09-21 14:02:12  graph.facebook.com  A  allowed
2026-09-21 14:02:13  firebaselogging.googleapis.com  A  allowed
2026-09-21 14:02:14  bat.bing.com  A  allowed
2026-09-21 14:02:15  pixel-config.reddit.com  A  allowed
2026-09-21 14:02:16  alb.reddit.com  A  allowed
2026-09-21 14:02:17  inmobi-choice.io  A  blocked
2026-09-21 14:02:18  sentry.io  A  allowed
2026-09-21 14:02:19  app-measurement.com  A  allowed
2026-09-21 14:02:20  connectivitycheck.gstatic.com  A  allowed
2026-09-21 14:02:21  play.googleapis.com  A  allowed
2026-09-21 14:02:22  some-mystery-domain-4821.xyz  A  allowed`;
el("analyze").click();

const sn = tbodyHTML("snitchtable"), un = tbodyHTML("unktable");
check("t.uptodown.app flagged", sn.includes("t.uptodown.app"));
check("graph.facebook.com flagged as Meta", sn.includes("graph.facebook.com") && sn.includes("Meta"));
check("firebaselogging flagged", sn.includes("firebaselogging.googleapis.com"));
check("bat.bing.com flagged", sn.includes("bat.bing.com"));
check("pixel-config.reddit.com flagged", sn.includes("pixel-config.reddit.com"));
check("alb.reddit.com flagged", sn.includes("alb.reddit.com"));
check("inmobi-choice.io flagged", sn.includes("inmobi-choice.io"));
check("sentry.io flagged (crash)", sn.includes("sentry.io"));
check("app-measurement.com flagged", sn.includes("app-measurement.com"));
check("connectivitycheck.gstatic.com is unknown, not snitch", un.includes("connectivitycheck.gstatic.com") && !sn.includes("connectivitycheck.gstatic.com"));
check("mystery .xyz domain is unknown", un.includes("some-mystery-domain-4821.xyz"));
check("cards show 9 snitches / 3 unknowns", el("cards").innerHTML.includes(">9<") && el("unkcount").textContent.includes("3"));

// ---------- Test 2: suffix matching ----------
console.log("Test 2: suffix matching");
el("log").value = "sub.foo.doubleclick.net\ndeep.sub.facebook.net\nevil-doubleclick.net\n";
el("analyze").click();
const sn2 = tbodyHTML("snitchtable"), un2 = tbodyHTML("unktable");
check("sub.foo.doubleclick.net matches doubleclick.net", sn2.includes("sub.foo.doubleclick.net"));
check("deep.sub.facebook.net matches facebook.net", sn2.includes("deep.sub.facebook.net"));
check("evil-doubleclick.net NOT matched (not a true subdomain)", !sn2.includes("evil-doubleclick.net") && un2.includes("evil-doubleclick.net"));

// ---------- Test 3: functional category goes to clean ----------
console.log("Test 3: functional domains");
el("log").value = "hatch.metaaivm.com\nnextdns.io\nintercom.io\n";
el("analyze").click();
const cl3 = tbodyHTML("cleantable");
check("hatch.metaaivm.com listed as clean", cl3.includes("hatch.metaaivm.com"));
check("nextdns.io listed as clean", cl3.includes("nextdns.io"));
check("intercom.io listed as clean", cl3.includes("intercom.io"));

// ---------- Test 4: verdicts (snitch/clean/forget) ----------
console.log("Test 4: user verdicts");
el("log").value = "mystery-one.example\nmystery-two.example\n";
el("analyze").click();
check("both start as unknowns", tbodyHTML("unktable").includes("mystery-one.example") && tbodyHTML("unktable").includes("mystery-two.example"));
fireDocClick(verdictBtn("mystery-one.example", "snitch"));
check("marked snitch moves to snitch table", tbodyHTML("snitchtable").includes("mystery-one.example"));
check("marked snitch tagged as your verdict", tbodyHTML("markedtable").includes("mystery-one.example"));
fireDocClick(verdictBtn("mystery-two.example", "clean"));
check("marked clean moves to clean table", tbodyHTML("cleantable").includes("mystery-two.example"));
fireDocClick({ closest: (sel) => (sel === "button[data-unmark]" ? { dataset: { unmark: "mystery-one.example" } } : null) });
el("log").value = "mystery-one.example\n";
el("analyze").click();
check("forget returns domain to unknowns", tbodyHTML("unktable").includes("mystery-one.example"));
check("verdicts persist in localStorage", JSON.parse(store["snitchlist_verdicts_v1"])["mystery-two.example"] === "clean");

// ---------- Test 5: parser edge cases ----------
console.log("Test 5: parser edge cases");
el("log").value = "192.168.1.1\n10.0.0.5\nsomefile.apk\nnotes.txt\nUPPERCASE.EXAMPLE.COM\ntrailing. dot test. example.org.\n";
el("analyze").click();
const un5 = tbodyHTML("unktable");
check("IPv4 addresses skipped", !un5.includes("192.168.1.1") && !un5.includes("10.0.0.5"));
check("file extensions skipped", !un5.includes("somefile.apk") && !un5.includes("notes.txt"));
check("uppercase normalized", un5.includes("uppercase.example.com"));
check("valid domain with trailing dot parsed", un5.includes("example.org"));

// ---------- Test 6: empty input ----------
console.log("Test 6: empty input");
alertMsg = null;
el("log").value = "   \n";
el("analyze").click();
check("empty input triggers alert", alertMsg === "Paste some log lines first.");

// ---------- Test 7: sample button + export report ----------
console.log("Test 7: sample + export");
el("sample").click();
check("sample fills log and analyzes", el("log").value.includes("t.uptodown.app") && tbodyHTML("snitchtable").includes("t.uptodown.app"));
check("export button visible after analyze", el("export").style.display === "");
let downloaded = null, blobText = null;
document.createElement = () => { const a = makeEl("a"); a.click = () => { downloaded = a.download; }; return a; };
global.Blob = function (parts) { blobText = parts.join(""); };
el("export").click();
check("export produces markdown report", downloaded === "snitchlist-report.md" && blobText.includes("# SnitchList report") && blobText.includes("t.uptodown.app"));

// ---------- Test 8: HTML escaping ----------
console.log("Test 8: escaping");
check("no raw <script> in output tables", tbodyHTML("snitchtable").indexOf("<script>") === -1);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
