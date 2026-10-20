// @ts-ignore
import * as satelliteModule from 'satellite.js';
import { SatelliteEntity } from '../types/scenario';

// Safely resolve the pure JS methods without pulling in threaded wasm
const sat: any = satelliteModule;
const twoline2satrec = sat.twoline2satrec;
const propagate = sat.propagate;
const gstime = sat.gstime;
const degreesLong = sat.degreesLong;
const degreesLat = sat.degreesLat;
const eciToGeodetic = sat.eciToGeodetic;

export interface OrbitPoint {
  lon: number;
  lat: number;
  altKm: number;
}

/**
 * Propagate a satellite TLE to ECI/Geodetic coordinates at a given Date.
 */
export function propagateSatellite(
  tleLine1: string,
  tleLine2: string,
  date: Date
): { lon: number; lat: number; altKm: number } | null {
  try {
    const satrec = twoline2satrec(tleLine1, tleLine2);
    const positionAndVelocity = propagate(satrec, date);
    if (!positionAndVelocity) return null;
    const posEci = positionAndVelocity.position;
    if (!posEci || typeof posEci === 'boolean') return null;

    const gmst = gstime(date);
    const geodetic = eciToGeodetic(posEci as any, gmst);

    const lonDeg = degreesLong(geodetic.longitude);
    const latDeg = degreesLat(geodetic.latitude);
    const altKm = geodetic.height;

    return {
      lon: Number.isFinite(lonDeg) ? lonDeg : 0,
      lat: Number.isFinite(latDeg) ? latDeg : 0,
      altKm: Number.isFinite(altKm) ? altKm : 550,
    };
  } catch (err) {
    return null;
  }
}

/**
 * Calculate the ground track points for one full orbit (approx 95 min for LEO).
 */
export function calculateOrbitGroundTrack(
  tleLine1: string,
  tleLine2: string,
  baseDate: Date,
  samples: number = 60
): [number, number, number][] {
  const points: [number, number, number][] = [];
  try {
    const satrec = twoline2satrec(tleLine1, tleLine2);
    // Period is approx 95 mins = 5700s
    const periodSec = 5700;
    const dt = periodSec / samples;

    for (let i = 0; i < samples; i++) {
      const t = new Date(baseDate.getTime() + i * dt * 1000);
      const pv = propagate(satrec, t);
      if (!pv) continue;
      const pos = pv.position;
      if (pos && typeof pos !== 'boolean') {
        const gmst = gstime(t);
        const geo = eciToGeodetic(pos as any, gmst);
        const lon = degreesLong(geo.longitude);
        const lat = degreesLat(geo.latitude);
        const altM = geo.height * 1000;
        if (Number.isFinite(lon) && Number.isFinite(lat)) {
          points.push([lon, lat, altM]);
        }
      }
    }
  } catch {
    // Return empty on parse error
  }
  return points;
}

/**
 * Generate synthetic TLE lines for a Walker-Delta constellation shell.
 * Useful for real-time live preview before simulation runs.
 */
export function generateSyntheticShellSats(
  shellName: string,
  altitudeKm: number,
  inclinationDeg: number,
  numPlanes: number,
  satsPerPlane: number,
  baseDate: Date
): SatelliteEntity[] {
  const satellites: SatelliteEntity[] = [];
  const meanMotion = 86400 / (2 * Math.PI * Math.sqrt(Math.pow((6371 + altitudeKm) * 1000, 3) / 3.986004418e14));

  for (let p = 0; p < numPlanes; p++) {
    const raan = (360 / numPlanes) * p;
    for (let s = 0; s < satsPerPlane; s++) {
      const meanAnomaly = (360 / satsPerPlane) * s + (360 / (numPlanes * satsPerPlane)) * p;
      const satId = `sat_${shellName}_p${p}_s${s}`;
      const satNum = 90000 + p * 100 + s;

      // Format two-line element set
      const l1 = `1 ${satNum}U 24999A   24001.00000000  .00000000  00000-0  00000-0 0  9991`;
      const incStr = inclinationDeg.toFixed(4).padStart(8, ' ');
      const raanStr = raan.toFixed(4).padStart(8, ' ');
      const maStr = meanAnomaly.toFixed(4).padStart(8, ' ');
      const mmStr = meanMotion.toFixed(8).padStart(11, ' ');
      const l2 = `2 ${satNum} ${incStr} ${raanStr} 0001000   0.0000 ${maStr} ${mmStr}000018`;

      const pos = propagateSatellite(l1, l2, baseDate) || {
        lon: ((raan + meanAnomaly) % 360) - 180,
        lat: Math.sin(((meanAnomaly * Math.PI) / 180)) * inclinationDeg,
        altKm: altitudeKm,
      };

      satellites.push({
        id: satId,
        name: `LEO-${shellName.toUpperCase()}-${p + 1}.${s + 1}`,
        planeIndex: p,
        satIndex: s,
        altitudeKm: altitudeKm,
        lat: pos.lat,
        lon: pos.lon,
        altM: pos.altKm * 1000,
        tleLine1: l1,
        tleLine2: l2,
        footprintRadiusKm: Math.sqrt(Math.pow(6371 + altitudeKm, 2) - Math.pow(6371, 2)),
      });
    }
  }

  return satellites;
}
