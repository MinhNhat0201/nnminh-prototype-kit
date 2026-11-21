// Figma level 1: push the DS variables and text styles into the open Figma file.
// Sent as the code of one use_figma call (load the figma-use skill first).
// adopt.py fills __DATA__ with the profile's figma-variables.json:
//   python3 <kit>/skills/adopt/scripts/adopt.py figma-script --out ds/acme > /tmp/figma-push.js
// Idempotent: collections, modes, variables and styles are found by name and updated, never duplicated.
// Plan limits: a Figma plan that allows fewer modes per collection makes addMode throw; the error is returned.

const DATA = __DATA__;

const report = { collections: {}, created: 0, updated: 0, textStyles: 0, warnings: [] };

function hexToRgba(hex) {
  const h = hex.replace('#', '');
  const n = (i) => parseInt(h.slice(i, i + 2), 16) / 255;
  return { r: n(0), g: n(2), b: n(4), a: h.length === 8 ? n(6) : 1 };
}

const existingCollections = await figma.variables.getLocalVariableCollectionsAsync();
const existingVariables = await figma.variables.getLocalVariablesAsync();
const byName = {}; // "<collection>/<variable name>" -> Variable
for (const v of existingVariables) {
  const c = existingCollections.find((x) => x.id === v.variableCollectionId);
  if (c) byName[c.name + '/' + v.name] = v;
}

async function ensureCollection(spec) {
  let col = existingCollections.find((c) => c.name === spec.name);
  if (!col) col = figma.variables.createVariableCollection(spec.name);
  const modeIds = {};
  spec.modes.forEach((name, i) => {
    let m = col.modes.find((x) => x.name === name);
    if (!m && i === 0 && col.modes.length === 1 && !spec.modes.includes(col.modes[0].name)) {
      col.renameMode(col.modes[0].modeId, name);
      m = col.modes[0];
    }
    if (!m) {
      try { const id = col.addMode(name); m = { modeId: id, name }; }
      catch (e) { report.warnings.push(`Mode "${name}" not added to ${spec.name}: ${e.message}`); }
    }
    if (m) modeIds[name] = m.modeId;
  });
  return { col, modeIds };
}

const made = {};
const order = ['primitives', 'spacing', 'semantic'];
const specs = order.filter((k) => DATA.collections[k]).map((k) => DATA.collections[k]);
// Primitives first, so aliases in the other collections resolve.
for (const spec of specs) {
  const { col, modeIds } = await ensureCollection(spec);
  made[spec.name] = { col, modeIds };
  report.collections[spec.name] = { modes: Object.keys(modeIds), variables: 0 };
}

function resolveAlias(ref) {
  // ref = "Primitives/color/neutral/950"
  const v = byName[ref];
  return v ? figma.variables.createVariableAlias(v) : null;
}

for (const spec of specs) {
  const { col, modeIds } = made[spec.name];
  for (const item of spec.variables) {
    const key = spec.name + '/' + item.name;
    let v = byName[key];
    if (!v) { v = figma.variables.createVariable(item.name, col, item.type); byName[key] = v; report.created++; }
    else report.updated++;
    for (const [mode, val] of Object.entries(item.values)) {
      const modeId = modeIds[mode];
      if (!modeId) continue;
      let value;
      if (val && typeof val === 'object' && val.alias) {
        value = resolveAlias(val.alias);
        if (!value) { report.warnings.push(`${key}: alias ${val.alias} not found`); continue; }
      } else if (item.type === 'COLOR') value = hexToRgba(val);
      else value = val;
      v.setValueForMode(modeId, value);
    }
    if (item.scopes) v.scopes = item.scopes;
    if (item.code) v.setVariableCodeSyntax('WEB', `var(${item.code})`);
    if (item.description) v.description = item.description;
    report.collections[spec.name].variables++;
  }
}

// Text styles
const styles = await figma.getLocalTextStylesAsync();
for (const ts of DATA.textStyles || []) {
  const font = { family: ts.fontFamily, style: ts.fontStyle };
  try { await figma.loadFontAsync(font); }
  catch (e) { report.warnings.push(`Font ${font.family} ${font.style} not available; style "${ts.name}" skipped. Install or enable the font, then run again.`); continue; }
  let s = styles.find((x) => x.name === ts.name);
  if (!s) s = figma.createTextStyle();
  s.name = ts.name;
  s.fontName = font;
  s.fontSize = ts.fontSize;
  s.lineHeight = { unit: 'PIXELS', value: ts.lineHeight };
  s.letterSpacing = { unit: 'PERCENT', value: ts.letterSpacing || 0 };
  if (ts.description) s.description = ts.description;
  report.textStyles++;
}

return report;
