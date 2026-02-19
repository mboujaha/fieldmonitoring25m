const EARTH_RADIUS_M = 6_378_137;

function toRadians(value: number): number {
  return (value * Math.PI) / 180;
}

function ringAreaSquareMeters(ring: number[][]): number {
  if (ring.length < 3) {
    return 0;
  }

  let total = 0;
  for (let i = 0; i < ring.length; i += 1) {
    const current = ring[i];
    const next = ring[(i + 1) % ring.length];
    const lonCurrent = toRadians(current[0]);
    const lonNext = toRadians(next[0]);
    const latCurrent = toRadians(current[1]);
    const latNext = toRadians(next[1]);
    total += (lonNext - lonCurrent) * (2 + Math.sin(latCurrent) + Math.sin(latNext));
  }

  return (total * EARTH_RADIUS_M * EARTH_RADIUS_M) / 2;
}

function polygonAreaSquareMeters(coordinates: number[][][]): number {
  if (coordinates.length === 0) {
    return 0;
  }

  const outer = Math.abs(ringAreaSquareMeters(coordinates[0]));
  const holes = coordinates
    .slice(1)
    .reduce((sum, ring) => sum + Math.abs(ringAreaSquareMeters(ring)), 0);
  return outer - holes;
}

export function computeGeometryAreaHa(geometry: GeoJSON.Geometry): number | null {
  switch (geometry.type) {
    case "Polygon":
      return Math.abs(polygonAreaSquareMeters(geometry.coordinates as number[][][])) / 10_000;
    case "MultiPolygon":
      return (
        Math.abs(
          (geometry.coordinates as number[][][][]).reduce(
            (sum, polygonCoords) => sum + polygonAreaSquareMeters(polygonCoords),
            0,
          ),
        ) / 10_000
      );
    default:
      return null;
  }
}
