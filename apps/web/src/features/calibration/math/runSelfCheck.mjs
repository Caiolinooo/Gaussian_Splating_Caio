/** Autoverificação Node (sem deps) — espelha tapeMath + scaleFactor. */
function distance3(a, b) {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  const dz = a.z - b.z;
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}
function midpoint3(a, b) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, z: (a.z + b.z) / 2 };
}
function isCalibrated(c) {
  return typeof c.scaleFactor === 'number' && c.scaleFactor > 0 && c.source !== 'none';
}
function scaleFactorFromSceneAndMeters(sceneDistance, realMeters) {
  return realMeters / sceneDistance;
}
function metersFromScene(sceneDistance, scaleFactor) {
  return sceneDistance * scaleFactor;
}
function compensatePoint(point, oldF, newF) {
  const r = oldF / newF;
  return { x: point.x * r, y: point.y * r, z: point.z * r };
}
function shouldCompensateObjects(prev, next) {
  return isCalibrated(prev) && isCalibrated(next) && prev.scaleFactor !== next.scaleFactor;
}
function hudCalibrationLabel(c) {
  if (!isCalibrated(c)) return 'não calibrada';
  const src =
    c.source === 'auto-height' ? 'auto-altura' : c.source === 'manual' ? 'manual' : 'não calibrada';
  if (c.source === 'auto-height' && c.confidence >= 0.75) return `calibrada · ${src} · conf. alta`;
  return `calibrada · ${src}`;
}
function close(a, e) {
  return Math.abs(a - e) < 1e-10;
}
function assert(c, m) {
  if (!c) throw new Error(m);
}

assert(close(distance3({ x: 0, y: 0, z: 0 }, { x: 3, y: 4, z: 0 }), 5), '3-4-5');
const mid = midpoint3({ x: 0, y: 0, z: 2 }, { x: 2, y: 4, z: 2 });
assert(mid.x === 1 && mid.y === 2 && mid.z === 2, 'midpoint');
assert(close(scaleFactorFromSceneAndMeters(2, 1.6), 0.8), 'scale');
assert(close(metersFromScene(2, 0.8), 1.6), 'meters');
assert(close(compensatePoint({ x: 2, y: 0, z: 0 }, 0.8, 1.6).x, 1), 'compensate');
const noneCal = { scaleFactor: null, source: 'none', confidence: null };
const autoCal = { scaleFactor: 0.85, source: 'auto-height', confidence: 0.9 };
const manualCal = { scaleFactor: 1.1, source: 'manual', confidence: null };
assert(!isCalibrated(noneCal), 'none');
assert(shouldCompensateObjects(autoCal, manualCal), 'redefine');
assert(!shouldCompensateObjects(noneCal, autoCal), 'first');
assert(hudCalibrationLabel(noneCal) === 'não calibrada', 'hud none');
assert(hudCalibrationLabel(autoCal) === 'calibrada · auto-altura · conf. alta', 'hud auto');
assert(hudCalibrationLabel(manualCal) === 'calibrada · manual', 'hud manual');
console.log('calibration self-check: ok');
