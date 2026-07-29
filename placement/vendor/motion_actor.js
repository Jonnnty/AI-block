/**
 * Kimodo NPZ → SOMA solid-color skinned mesh (browser LBS).
 * Expects vendor/soma_skin.bin exported by scripts/export_soma_skin.py.
 */

import { unzipSync } from 'https://cdn.jsdelivr.net/npm/fflate@0.8.2/esm/browser.js';

const SKIN_MAGIC = new Uint8Array([0x53, 0x4f, 0x4d, 0x41, 0x53, 0x4b, 0x49, 0x4e]); // SOMASKIN
const SHELL_MAGIC = new Uint8Array([0x4d, 0x4f, 0x54, 0x53, 0x50, 0x4c, 0x41, 0x54]); // MOTSPLAT

/** @typedef {{bindVertices:Float32Array, faces:Uint32Array, lbsIndices:Uint8Array, lbsWeights:Float32Array, bindRigInv:Float32Array, numVerts:number, numFaces:number, numJoints:number, maxInf:number, floorY:number}} SomaSkin */

/** @typedef {{posedJoints:Float32Array, globalRotMats:Float32Array, numFrames:number, numJoints:number, fps:number, anchor:{x:number,y:number,z:number}, minZ:number}} MotionData */

/** @typedef {{bindVertices:Float32Array, lbsIndices:Uint8Array, lbsWeights:Float32Array, numSplats:number, maxInf:number, splatScale:number, color:[number,number,number], opacity:number}} MotionSplatShell */

/** Kimodo Y-up (x,y,z) → editor Z-up (x,y,z). */
export function yUpPosToZUp(x, y, z) {
  return [x, z, y];
}

const Y_TO_Z_UP_4 = new Float32Array([
  1, 0, 0, 0,
  0, 0, 1, 0,
  0, 1, 0, 0,
  0, 0, 0, 1,
]);

function mat4MultiplyRowMajor(a, b, out) {
  for (let r = 0; r < 4; r++) {
    for (let c = 0; c < 4; c++) {
      let sum = 0;
      for (let k = 0; k < 4; k++) sum += a[r * 4 + k] * b[k * 4 + c];
      out[r * 4 + c] = sum;
    }
  }
}

/** Row-major 4×4: M' = P M P, P maps Y-up to Z-up. */
function yUpMat4ToZUpFlat(src, dst, base = 0) {
  const m = src.subarray(base, base + 16);
  const out = dst.subarray(base, base + 16);
  const pm = new Float32Array(16);
  mat4MultiplyRowMajor(Y_TO_Z_UP_4, m, pm);
  mat4MultiplyRowMajor(pm, Y_TO_Z_UP_4, out);
}

function convertSkinBindPoseToZUp(bindVertices, bindRigInvRaw, bindRigInv, numVerts, numJoints) {
  for (let i = 0; i < numVerts * 3; i += 3) {
    const [nx, ny, nz] = yUpPosToZUp(bindVertices[i], bindVertices[i + 1], bindVertices[i + 2]);
    bindVertices[i] = nx;
    bindVertices[i + 1] = ny;
    bindVertices[i + 2] = nz;
  }
  for (let j = 0; j < numJoints; j++) {
    yUpMat4ToZUpFlat(bindRigInvRaw, bindRigInv, j * 16);
  }
}

export async function loadSomaSkin(url = './vendor/soma_skin.bin') {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`无法加载 SOMA 蒙皮: ${url}`);
  const buf = new Uint8Array(await resp.arrayBuffer());
  const view = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  for (let i = 0; i < 8; i++) {
    if (buf[i] !== SKIN_MAGIC[i]) throw new Error('soma_skin.bin 格式无效');
  }
  const numVerts = view.getUint32(12, true);
  const numFaces = view.getUint32(16, true);
  const numJoints = view.getUint32(20, true);
  const maxInf = view.getUint32(24, true);
  const floorY = view.getFloat32(28, true);
  let off = 32;
  const bindVertices = new Float32Array(numVerts * 3);
  bindVertices.set(new Float32Array(buf.buffer, buf.byteOffset + off, numVerts * 3));
  off += numVerts * 3 * 4;
  const faces = new Uint32Array(buf.buffer, buf.byteOffset + off, numFaces * 3);
  off += numFaces * 3 * 4;
  const lbsIndices = new Uint8Array(buf.buffer, buf.byteOffset + off, numVerts * maxInf);
  off += numVerts * maxInf;
  const lbsWeights = new Float32Array(buf.buffer, buf.byteOffset + off, numVerts * maxInf);
  off += numVerts * maxInf * 4;
  const bindRigInvRaw = new Float32Array(numJoints * 16);
  bindRigInvRaw.set(new Float32Array(buf.buffer, buf.byteOffset + off, numJoints * 16));
  const bindRigInv = new Float32Array(numJoints * 16);
  convertSkinBindPoseToZUp(bindVertices, bindRigInvRaw, bindRigInv, numVerts, numJoints);
  return {
    bindVertices,
    faces: new Uint32Array(faces),
    lbsIndices: new Uint8Array(lbsIndices),
    lbsWeights: new Float32Array(lbsWeights),
    bindRigInv,
    numVerts,
    numFaces,
    numJoints,
    maxInf,
    floorY,
  };
}

function parseNpy(u8) {
  if (u8[0] !== 0x93) throw new Error('invalid npy');
  let i = 10;
  while (u8[i] !== 0x0a) i++;
  i++;
  const header = new TextDecoder().decode(u8.subarray(10, i));
  const shapeMatch = header.match(/'shape': \(([^)]*)\)/);
  if (!shapeMatch) throw new Error('npy shape missing');
  const shape = shapeMatch[1].split(',').map((s) => s.trim()).filter(Boolean).map(Number);
  const descrMatch = header.match(/'descr': '([^']+)'/);
  const descr = descrMatch ? descrMatch[1] : '<f4';
  const little = descr.startsWith('<') || descr.startsWith('|');
  const count = shape.reduce((a, b) => a * b, 1);

  const itemSize = descr === '|b1' || descr === '|u1' ? 1
    : descr.endsWith('f4') ? 4
      : descr.endsWith('f8') ? 8
        : descr.endsWith('i4') ? 4
          : descr.endsWith('i8') ? 8
            : 0;
  if (!itemSize) throw new Error(`unsupported npy dtype ${descr}`);

  const raw = u8.subarray(i, i + count * itemSize);
  const dv = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);

  if (descr.endsWith('f4')) {
    const out = new Float32Array(count);
    for (let k = 0; k < count; k++) out[k] = dv.getFloat32(k * 4, little);
    return { shape, data: out };
  }
  if (descr.endsWith('f8')) {
    const out = new Float32Array(count);
    for (let k = 0; k < count; k++) out[k] = dv.getFloat64(k * 8, little);
    return { shape, data: out };
  }
  if (descr.endsWith('i4')) {
    const out = new Int32Array(count);
    for (let k = 0; k < count; k++) out[k] = dv.getInt32(k * 4, little);
    return { shape, data: out };
  }
  if (descr === '|b1' || descr === '|u1') {
    const out = new Uint8Array(count);
    out.set(raw.subarray(0, count));
    return { shape, data: out };
  }
  throw new Error(`unsupported npy dtype ${descr}`);
}

export function parseKimodoNpz(arrayBuffer) {
  const files = unzipSync(new Uint8Array(arrayBuffer));
  let posedEntry = null;
  let rotEntry = null;
  for (const [name, bytes] of Object.entries(files)) {
    if (!name.endsWith('.npy')) continue;
    const key = name.replace(/\.npy$/, '').split('/').pop();
    if (key === 'posed_joints') posedEntry = parseNpy(bytes);
    else if (key === 'global_rot_mats') rotEntry = parseNpy(bytes);
  }
  if (!posedEntry) throw new Error('NPZ 缺少 posed_joints');
  if (!rotEntry) throw new Error('NPZ 缺少 global_rot_mats');
  const pjShape = posedEntry.shape;
  const numFrames = pjShape[0];
  const numJoints = pjShape[1];
  return {
    posedJoints: posedEntry.data,
    globalRotMats: rotEntry.data,
    numFrames,
    numJoints,
    fps: 30,
  };
}

/** 3×3 row-major rotation: R' = P R P^T, P maps Y-up to Z-up. */
export function yUpMat3ToZUp(m, out) {
  out[0] = m[0]; out[1] = m[2]; out[2] = m[1];
  out[3] = m[6]; out[4] = m[8]; out[5] = m[7];
  out[6] = m[3]; out[7] = m[5]; out[8] = m[4];
  return out;
}

export function buildMotionData(raw) {
  const { posedJoints, globalRotMats, numFrames, numJoints, fps } = raw;
  const posedZ = new Float32Array(numFrames * numJoints * 3);
  const rotZ = new Float32Array(numFrames * numJoints * 9);
  const tmp = new Float32Array(9);
  let minZ = Infinity;
  let ax = 0; let ay = 0; let az = 0;
  for (let t = 0; t < numFrames; t++) {
    for (let j = 0; j < numJoints; j++) {
      const pi = (t * numJoints + j) * 3;
      const x = posedJoints[pi];
      const y = posedJoints[pi + 1];
      const z = posedJoints[pi + 2];
      const [nx, ny, nz] = yUpPosToZUp(x, y, z);
      posedZ[pi] = nx; posedZ[pi + 1] = ny; posedZ[pi + 2] = nz;
      if (nz < minZ) minZ = nz;
      if (t === 0 && j === 0) { ax = nx; ay = ny; az = nz; }
      const ri = (t * numJoints + j) * 9;
      yUpMat3ToZUp(globalRotMats.subarray(ri, ri + 9), rotZ.subarray(ri, ri + 9));
    }
  }
  for (let i = 0; i < posedZ.length; i += 3) {
    posedZ[i + 2] -= minZ;
  }
  const anchor = { x: ax, y: ay, z: 0 };
  let maxZ = 0;
  for (let j = 0; j < numJoints; j++) {
    maxZ = Math.max(maxZ, posedZ[j * 3 + 2]);
  }
  return {
    posedJoints: posedZ,
    globalRotMats: rotZ,
    numFrames,
    numJoints,
    fps,
    anchor,
    minZ,
    height: maxZ,
  };
}

/** Scale motion actor to match scene props (~0.25m tall by default). */
export function motionDefaultScale(motion, sceneScale = 0.12) {
  const height = Math.max(motion.height || 1.75, 0.01);
  const targetHeight = Math.max(sceneScale * 2.0, 0.18);
  return targetHeight / height;
}

/** @returns {Float32Array} joint skinning matrices, length numJoints*12 */
export function computeSkinMatrices(skin, motion, frameIdx) {
  const { numJoints, bindRigInv } = skin;
  const { posedJoints, globalRotMats, numJoints: nj } = motion;
  const f = Math.max(0, Math.min(motion.numFrames - 1, frameIdx | 0));
  const m = new Float32Array(numJoints * 12);

  for (let j = 0; j < numJoints; j++) {
    const ji = (f * nj + j) * 9;
    const ti = (f * nj + j) * 3;
    const px = posedJoints[ti];
    const py = posedJoints[ti + 1];
    const pz = posedJoints[ti + 2];
    const r0 = globalRotMats[ji];
    const r1 = globalRotMats[ji + 1];
    const r2 = globalRotMats[ji + 2];
    const r3 = globalRotMats[ji + 3];
    const r4 = globalRotMats[ji + 4];
    const r5 = globalRotMats[ji + 5];
    const r6 = globalRotMats[ji + 6];
    const r7 = globalRotMats[ji + 7];
    const r8 = globalRotMats[ji + 8];
    const bi = j * 16;
    const a00 = r0 * bindRigInv[bi] + r1 * bindRigInv[bi + 4] + r2 * bindRigInv[bi + 8];
    const a01 = r0 * bindRigInv[bi + 1] + r1 * bindRigInv[bi + 5] + r2 * bindRigInv[bi + 9];
    const a02 = r0 * bindRigInv[bi + 2] + r1 * bindRigInv[bi + 6] + r2 * bindRigInv[bi + 10];
    const a10 = r3 * bindRigInv[bi] + r4 * bindRigInv[bi + 4] + r5 * bindRigInv[bi + 8];
    const a11 = r3 * bindRigInv[bi + 1] + r4 * bindRigInv[bi + 5] + r5 * bindRigInv[bi + 9];
    const a12 = r3 * bindRigInv[bi + 2] + r4 * bindRigInv[bi + 6] + r5 * bindRigInv[bi + 10];
    const a20 = r6 * bindRigInv[bi] + r7 * bindRigInv[bi + 4] + r8 * bindRigInv[bi + 8];
    const a21 = r6 * bindRigInv[bi + 1] + r7 * bindRigInv[bi + 5] + r8 * bindRigInv[bi + 9];
    const a22 = r6 * bindRigInv[bi + 2] + r7 * bindRigInv[bi + 6] + r8 * bindRigInv[bi + 10];
    const tx = r0 * bindRigInv[bi + 3] + r1 * bindRigInv[bi + 7] + r2 * bindRigInv[bi + 11] + px;
    const ty = r3 * bindRigInv[bi + 3] + r4 * bindRigInv[bi + 7] + r5 * bindRigInv[bi + 11] + py;
    const tz = r6 * bindRigInv[bi + 3] + r7 * bindRigInv[bi + 7] + r8 * bindRigInv[bi + 11] + pz;
    m[j * 12] = a00; m[j * 12 + 1] = a01; m[j * 12 + 2] = a02; m[j * 12 + 3] = tx;
    m[j * 12 + 4] = a10; m[j * 12 + 5] = a11; m[j * 12 + 6] = a12; m[j * 12 + 7] = ty;
    m[j * 12 + 8] = a20; m[j * 12 + 9] = a21; m[j * 12 + 10] = a22; m[j * 12 + 11] = tz;
  }
  return m;
}

function lbsVertices(bindVertices, numVerts, maxInf, lbsIndices, lbsWeights, m, out) {
  for (let v = 0; v < numVerts; v++) {
    let ox = 0; let oy = 0; let oz = 0;
    const bx = bindVertices[v * 3];
    const by = bindVertices[v * 3 + 1];
    const bz = bindVertices[v * 3 + 2];
    for (let w = 0; w < maxInf; w++) {
      const idx = v * maxInf + w;
      const weight = lbsWeights[idx];
      if (weight <= 0) continue;
      const joint = lbsIndices[idx];
      const mi = joint * 12;
      ox += weight * (m[mi] * bx + m[mi + 1] * by + m[mi + 2] * bz + m[mi + 3]);
      oy += weight * (m[mi + 4] * bx + m[mi + 5] * by + m[mi + 6] * bz + m[mi + 7]);
      oz += weight * (m[mi + 8] * bx + m[mi + 9] * by + m[mi + 10] * bz + m[mi + 11]);
    }
    out[v * 3] = ox;
    out[v * 3 + 1] = oy;
    out[v * 3 + 2] = oz;
  }
  return out;
}

/**
 * Linear blend skinning for one frame.
 * @returns {Float32Array} length numVerts*3
 */
export function skinFrame(skin, motion, frameIdx) {
  const { numVerts, maxInf, bindVertices, lbsIndices, lbsWeights } = skin;
  const m = computeSkinMatrices(skin, motion, frameIdx);
  return lbsVertices(bindVertices, numVerts, maxInf, lbsIndices, lbsWeights, m, new Float32Array(numVerts * 3));
}

/**
 * LBS for the baked Gaussian shell (~2000 splats).
 * @returns {Float32Array} length numSplats*3
 */
export function shellFrame(shell, skin, motion, frameIdx) {
  const { numSplats, maxInf, bindVertices, lbsIndices, lbsWeights } = shell;
  const m = computeSkinMatrices(skin, motion, frameIdx);
  return lbsVertices(bindVertices, numSplats, maxInf, lbsIndices, lbsWeights, m, new Float32Array(numSplats * 3));
}

export async function loadMotionSplatShell(url = './vendor/motion_splat_shell.bin') {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`无法加载 motion splat shell: ${url}`);
  const buf = new Uint8Array(await resp.arrayBuffer());
  const view = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  for (let i = 0; i < 8; i++) {
    if (buf[i] !== SHELL_MAGIC[i]) throw new Error('motion_splat_shell.bin 格式无效');
  }
  const version = view.getUint32(8, true);
  if (version !== 1) throw new Error(`motion_splat_shell.bin 版本 ${version} 不支持`);
  const numSplats = view.getUint32(12, true);
  const maxInf = view.getUint32(16, true);
  const splatScale = view.getFloat32(20, true);
  const color = [view.getUint8(24), view.getUint8(25), view.getUint8(26)];
  const opacity = view.getUint8(27);
  let off = 28;
  const bindVertices = new Float32Array(numSplats * 3);
  bindVertices.set(new Float32Array(buf.buffer, buf.byteOffset + off, numSplats * 3));
  off += numSplats * 3 * 4;
  const lbsIndices = new Uint8Array(buf.buffer, buf.byteOffset + off, numSplats * maxInf);
  off += numSplats * maxInf;
  const lbsWeights = new Float32Array(numSplats * maxInf);
  lbsWeights.set(new Float32Array(buf.buffer, buf.byteOffset + off, numSplats * maxInf));
  return {
    bindVertices,
    lbsIndices: new Uint8Array(lbsIndices),
    lbsWeights,
    numSplats,
    maxInf,
    splatScale,
    color,
    opacity,
  };
}

export function motionFrameForCameraFrame(camFrame, totalCamFrames, motion) {
  if (!motion || motion.numFrames <= 1) return 0;
  const t = camFrame / Math.max(1, totalCamFrames - 1);
  return Math.min(motion.numFrames - 1, Math.round(t * (motion.numFrames - 1)));
}
