import * as THREE from 'three';
import { CFG } from './cfg.js';
import { scene } from './scene.js';
import { GEO, MAT } from './assets.js';

export const roadPool = [];

// Builds the recycled road segment pool and adds all segments to the scene.
// Call once at boot.
export function buildRoadPool() {
  for (let i = 0; i < CFG.ROAD_SEGS; i++) {
    const group = new THREE.Group();
    group.add(new THREE.Mesh(GEO.roadSeg, MAT.road));

    if (i % CFG.ROAD_MARKER_EVERY === 0) {
      [-CFG.ROAD_W / 6, 0, CFG.ROAD_W / 6].forEach((x, idx) => {
        const marker = new THREE.Mesh(GEO.marker, idx === 1 ? MAT.markerBlue : MAT.markerMag);
        marker.position.set(x, 0.14, 0);
        group.add(marker);
      });
    }

    const wallL = new THREE.Mesh(GEO.wall, MAT.wall);
    wallL.position.set(-(CFG.ROAD_W / 2 + 0.22), 1.6, 0);
    group.add(wallL);

    const wallR = new THREE.Mesh(GEO.wall, MAT.wall);
    wallR.position.set(CFG.ROAD_W / 2 + 0.22, 1.6, 0);
    group.add(wallR);

    group.position.z = CFG.PLAYER_Z + 6 - i * CFG.SEG_LEN;
    scene.add(group);
    roadPool.push(group);
  }
}

// Populates the scene with a static randomised starfield. Call once at boot.
export function buildStarfield() {
  for (let i = 0; i < 350; i++) {
    const star = new THREE.Mesh(GEO.starSphere, MAT.star);
    star.position.set(
      (Math.random() - 0.5) * 240,
      Math.random() * 50 + 6,
      Math.random() * 240 - 120,
    );
    scene.add(star);
  }
}

// Advances road segments and wraps them when they pass the player.
// Receives speed as a parameter so this module stays state-independent.
export function tickRoad(dt, speed) {
  const totalLen = CFG.ROAD_SEGS * CFG.SEG_LEN;
  for (const seg of roadPool) {
    seg.position.z += speed * dt;
    if (seg.position.z > CFG.PLAYER_Z + 8) seg.position.z -= totalLen;
  }
}
