// READ-ONLY plan re-read. Paste into the javascript tool on a GHL tab of the WUW sub-account
// (https://app.gohighlevel.com/v2/location/BDeGaczWUBVqlvyWoI7l/...), after starting scripts/plan_receive.py.
// Set IDS to the flagged workflow IDs (data.json -> plan_check.items[].id). Only GETs; nothing is saved to GHL.
const IDS = [/* 'workflow-id', ... */];
const LOC = 'BDeGaczWUBVqlvyWoI7l';
const here = (location.href.match(/\/location\/([A-Za-z0-9]+)/) || [])[1];
if (here !== LOC) throw new Error('Wrong sub-account: tab is on ' + here + ', expected ' + LOC + '. Stop.');
const http = window.SHELL_STORE.$http;
const slim = {};
for (const id of IDS) {
  const d = (await http.get(`https://backend.leadconnectorhq.com/workflow/${LOC}/${id}`)).data;
  slim[id] = {name: d.name, version: d.version, updatedAt: d.updatedAt, status: d.status,
    templates: (d.workflowData?.templates || []).map(x => {
      const a = {...(x.attributes || {})}; delete a.html; if (x.type === 'email') delete a.body;
      return {id: x.id, order: x.order, name: x.name, type: x.type, parentKey: x.parentKey, parent: x.parent, next: x.next, attributes: a};
    })};
}
const r = await fetch('http://127.0.0.1:8765/', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(slim)});
Object.entries(slim).map(([id, w]) => `${w.name} · v${w.version} · ${w.templates.filter(t => ['email','sms'].includes(t.type)).length} msgs`).concat('saved: ' + r.status);
