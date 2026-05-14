import * as THREE from 'three';
import { CFG } from './cfg.js';

// Shared geometries — created once, referenced by every mesh that uses them.
// blocks.js clones MAT.green / MAT.red per block to allow individual emissive animation.
export const GEO = Object.freeze({
  block:      new THREE.BoxGeometry(CFG.BLOCK.W, CFG.BLOCK.H, CFG.BLOCK.D),
  roadSeg:    new THREE.BoxGeometry(CFG.ROAD_W, 0.22, CFG.SEG_LEN),
  marker:     new THREE.BoxGeometry(0.09, 0.25, 2.2),
  wall:       new THREE.BoxGeometry(0.45, 3.2, CFG.SEG_LEN),
  carBody:    new THREE.BoxGeometry(2.4, 0.42, 4.2),
  carCabin:   new THREE.BoxGeometry(1.55, 0.45, 2.1),
  carWheel:   new THREE.CylinderGeometry(0.35, 0.35, 0.25, 12),
  starSphere: new THREE.SphereGeometry(0.07, 4, 4),
});

// Shared materials — treat as read-only; clone before animating per-instance properties.
export const MAT = Object.freeze({
  road:       new THREE.MeshStandardMaterial({ color: 0x07071a, roughness: 0.92, metalness: 0.08 }),
  markerMag:  new THREE.MeshBasicMaterial({ color: 0xff00ff }),
  markerBlue: new THREE.MeshBasicMaterial({ color: 0x2200ff }),
  wall:       new THREE.MeshStandardMaterial({ color: 0x0f0020, roughness: 0.8, emissive: 0x2a0044, emissiveIntensity: 0.4 }),
  car:        new THREE.MeshStandardMaterial({ color: 0x00ffff, emissive: 0x00cccc, emissiveIntensity: 0.55, roughness: 0.25, metalness: 0.85 }),
  wheel:      new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.9 }),
  green:      new THREE.MeshStandardMaterial({ color: 0x00ff88, emissive: 0x00dd66, emissiveIntensity: 0.7, roughness: 0.2, metalness: 0.5 }),
  red:        new THREE.MeshStandardMaterial({ color: 0xff2244, emissive: 0xff0022, emissiveIntensity: 0.7, roughness: 0.2, metalness: 0.5 }),
  star:       new THREE.MeshBasicMaterial({ color: 0xffffff }),
});
