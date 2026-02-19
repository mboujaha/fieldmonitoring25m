"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import MapboxDraw from "@mapbox/mapbox-gl-draw";

import { MapMode } from "@fieldmonitor/shared-types";
import { ImageryItem } from "@/lib/api";

interface MapWorkspaceProps {
  mapMode: MapMode;
  onGeometryChange: (geometry: GeoJSON.Geometry | null) => void;
  imageryResults: ImageryItem[];
  selectedSceneId: string;
  onSceneSelect: (sceneId: string) => void;
  selectedFieldId: string;
  selectedFieldGeometry: GeoJSON.Geometry | null;
}

const IMAGERY_SOURCE_ID = "imagery-footprints";
const IMAGERY_FILL_LAYER_ID = "imagery-footprints-fill";
const IMAGERY_LINE_LAYER_ID = "imagery-footprints-line";
const FIELD_SOURCE_ID = "selected-field";
const FIELD_FILL_LAYER_ID = "selected-field-fill";
const FIELD_LINE_LAYER_ID = "selected-field-line";
const BASEMAP_LAYER_IDS = {
  SATELLITE: "basemap-satellite",
  DARK: "basemap-dark",
  TOPO: "basemap-topo",
} as const;
type BasemapKey = keyof typeof BASEMAP_LAYER_IDS;

const BASEMAP_OPTIONS: Array<{ key: BasemapKey; label: string }> = [
  { key: "SATELLITE", label: "Satellite" },
  { key: "DARK", label: "Dark" },
  { key: "TOPO", label: "Topo" },
];

const DEFAULT_MAP_STYLE = {
  version: 8,
  sources: {
    satellite: {
      type: "raster",
      tiles: ["https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      attribution: "Esri World Imagery",
      maxzoom: 19,
    },
    dark: {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution: "CARTO, OpenStreetMap contributors",
      maxzoom: 20,
    },
    topo: {
      type: "raster",
      tiles: [
        "https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
        "https://b.tile.opentopomap.org/{z}/{x}/{y}.png",
        "https://c.tile.opentopomap.org/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution: "OpenTopoMap, OpenStreetMap contributors",
      maxzoom: 17,
    },
  },
  layers: [
    {
      id: "background",
      type: "background",
      paint: { "background-color": "#0a1422" },
    },
    {
      id: BASEMAP_LAYER_IDS.DARK,
      type: "raster",
      source: "dark",
      layout: { visibility: "none" },
    },
    {
      id: BASEMAP_LAYER_IDS.TOPO,
      type: "raster",
      source: "topo",
      layout: { visibility: "none" },
    },
    {
      id: BASEMAP_LAYER_IDS.SATELLITE,
      type: "raster",
      source: "satellite",
      layout: { visibility: "visible" },
    },
  ],
} as const;

function applyBasemapVisibility(map: maplibregl.Map, basemap: BasemapKey) {
  for (const [key, layerId] of Object.entries(BASEMAP_LAYER_IDS) as Array<[BasemapKey, string]>) {
    if (!map.getLayer(layerId)) {
      continue;
    }
    map.setLayoutProperty(layerId, "visibility", key === basemap ? "visible" : "none");
  }
}

const MODE_DESCRIPTION: Record<MapMode, { label: string; detail: string }> = {
  NATIVE: {
    label: "Native",
    detail: "Original Sentinel-2 analytics layer.",
  },
  SR: {
    label: "SR",
    detail: "Model-enhanced close-up visualization (MODEL_DERIVED).",
  },
  SIDE_BY_SIDE: {
    label: "Split",
    detail: "Native and SR comparison side-by-side.",
  },
  SWIPE: {
    label: "Swipe",
    detail: "Drag divider style comparison between Native and SR.",
  },
};

const DRAW_STYLES = [
  {
    id: "gl-draw-polygon-fill-inactive",
    type: "fill",
    filter: ["all", ["==", "active", "false"], ["==", "$type", "Polygon"], ["!=", "mode", "static"]],
    paint: { "fill-color": "#3b82f6", "fill-outline-color": "#3b82f6", "fill-opacity": 0.08 },
  },
  {
    id: "gl-draw-polygon-fill-active",
    type: "fill",
    filter: ["all", ["==", "active", "true"], ["==", "$type", "Polygon"]],
    paint: { "fill-color": "#f59e0b", "fill-outline-color": "#f59e0b", "fill-opacity": 0.1 },
  },
  {
    id: "gl-draw-polygon-midpoint",
    type: "circle",
    filter: ["all", ["==", "$type", "Point"], ["==", "meta", "midpoint"]],
    paint: { "circle-radius": 3, "circle-color": "#f59e0b" },
  },
  {
    id: "gl-draw-polygon-stroke-inactive",
    type: "line",
    filter: ["all", ["==", "$type", "Polygon"], ["==", "active", "false"], ["!=", "mode", "static"]],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#2563eb", "line-width": 2 },
  },
  {
    id: "gl-draw-polygon-stroke-active",
    type: "line",
    filter: ["all", ["==", "$type", "Polygon"], ["==", "active", "true"]],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#f59e0b", "line-width": 2, "line-dasharray": ["literal", [0.2, 2]] },
  },
  {
    id: "gl-draw-line-inactive",
    type: "line",
    filter: ["all", ["==", "$type", "LineString"], ["==", "active", "false"]],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#2563eb", "line-width": 2 },
  },
  {
    id: "gl-draw-line-active",
    type: "line",
    filter: ["all", ["==", "$type", "LineString"], ["==", "active", "true"]],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#f59e0b", "line-width": 2, "line-dasharray": ["literal", [0.2, 2]] },
  },
  {
    id: "gl-draw-polygon-and-line-vertex-stroke-inactive",
    type: "circle",
    filter: ["all", ["==", "meta", "vertex"], ["==", "$type", "Point"], ["!=", "mode", "static"]],
    paint: { "circle-radius": 5, "circle-color": "#ffffff" },
  },
  {
    id: "gl-draw-polygon-and-line-vertex-inactive",
    type: "circle",
    filter: ["all", ["==", "meta", "vertex"], ["==", "$type", "Point"], ["!=", "mode", "static"]],
    paint: { "circle-radius": 3, "circle-color": "#2563eb" },
  },
  {
    id: "gl-draw-point-point-stroke-inactive",
    type: "circle",
    filter: ["all", ["==", "meta", "feature"], ["==", "$type", "Point"], ["!=", "mode", "static"]],
    paint: { "circle-radius": 5, "circle-opacity": 1, "circle-color": "#ffffff" },
  },
  {
    id: "gl-draw-point-inactive",
    type: "circle",
    filter: ["all", ["==", "meta", "feature"], ["==", "$type", "Point"], ["!=", "mode", "static"]],
    paint: { "circle-radius": 3, "circle-opacity": 1, "circle-color": "#2563eb" },
  },
  {
    id: "gl-draw-point-stroke-active",
    type: "circle",
    filter: ["all", ["==", "$type", "Point"], ["==", "active", "true"], ["!=", "meta", "midpoint"]],
    paint: { "circle-radius": 6, "circle-color": "#ffffff" },
  },
  {
    id: "gl-draw-point-active",
    type: "circle",
    filter: ["all", ["==", "$type", "Point"], ["==", "active", "true"], ["!=", "meta", "midpoint"]],
    paint: { "circle-radius": 4, "circle-color": "#f59e0b" },
  },
  {
    id: "gl-draw-polygon-fill-static",
    type: "fill",
    filter: ["all", ["==", "mode", "static"], ["==", "$type", "Polygon"]],
    paint: { "fill-color": "#475569", "fill-outline-color": "#475569", "fill-opacity": 0.1 },
  },
  {
    id: "gl-draw-polygon-stroke-static",
    type: "line",
    filter: ["all", ["==", "mode", "static"], ["==", "$type", "Polygon"]],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#475569", "line-width": 2 },
  },
  {
    id: "gl-draw-line-static",
    type: "line",
    filter: ["all", ["==", "mode", "static"], ["==", "$type", "LineString"]],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#475569", "line-width": 2 },
  },
  {
    id: "gl-draw-point-static",
    type: "circle",
    filter: ["all", ["==", "mode", "static"], ["==", "$type", "Point"]],
    paint: { "circle-radius": 4, "circle-color": "#475569" },
  },
] as const;

function patchMapboxDrawForMapLibre() {
  const drawConstants = (MapboxDraw as unknown as {
    constants: {
      classes: Record<string, string>;
      styles?: Array<{ paint?: Record<string, unknown> }>;
    };
  }).constants;
  const classes = drawConstants.classes;
  classes.CANVAS = "maplibregl-canvas";
  classes.CONTROL_BASE = "maplibregl-ctrl";
  classes.CONTROL_PREFIX = "maplibregl-ctrl-";
  classes.CONTROL_GROUP = "maplibregl-ctrl-group";
  classes.ATTRIBUTION = "maplibregl-ctrl-attrib";

  // MapLibre requires array literals inside expressions to be wrapped with ["literal", ...].
  if (Array.isArray(drawConstants.styles)) {
    drawConstants.styles = drawConstants.styles.map((style) => {
      const dashArray = style.paint?.["line-dasharray"];
      if (!Array.isArray(dashArray) || typeof dashArray[0] !== "string") {
        return style;
      }

      const patchedDashArray = dashArray.map((item, index) =>
        index > 0 &&
        Array.isArray(item) &&
        item.every((value) => typeof value === "number")
          ? ["literal", item]
          : item
      );

      return {
        ...style,
        paint: {
          ...style.paint,
          "line-dasharray": patchedDashArray,
        },
      };
    });
  }
}

function toFootprintFeatureCollection(
  imageryResults: ImageryItem[],
  selectedSceneId: string,
): GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, { scene_id: string; selected: boolean }> {
  const selectedSceneIds = selectedSceneId
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  if (selectedSceneIds.length === 0) {
    return { type: "FeatureCollection", features: [] };
  }
  const selectedSceneSet = new Set(selectedSceneIds);
  const features: Array<
    GeoJSON.Feature<GeoJSON.Polygon | GeoJSON.MultiPolygon, { scene_id: string; selected: boolean }>
  > = [];

  for (const scene of imageryResults) {
    if (!selectedSceneSet.has(scene.scene_id)) {
      continue;
    }

    if (scene.footprint_geojson?.type === "Polygon" || scene.footprint_geojson?.type === "MultiPolygon") {
      features.push({
        type: "Feature",
        properties: { scene_id: scene.scene_id, selected: true },
        geometry: scene.footprint_geojson as GeoJSON.Polygon | GeoJSON.MultiPolygon,
      });
      continue;
    }

    if (!Array.isArray(scene.bbox) || scene.bbox.length !== 4) {
      continue;
    }

    const [minLon, minLat, maxLon, maxLat] = scene.bbox;
    if (![minLon, minLat, maxLon, maxLat].every((value) => Number.isFinite(value))) {
      continue;
    }
    if (minLon >= maxLon || minLat >= maxLat) {
      continue;
    }

    features.push({
      type: "Feature",
      properties: { scene_id: scene.scene_id, selected: true },
      geometry: {
        type: "Polygon",
        coordinates: [[
          [minLon, minLat],
          [maxLon, minLat],
          [maxLon, maxLat],
          [minLon, maxLat],
          [minLon, minLat],
        ]],
      },
    });
  }

  return { type: "FeatureCollection", features };
}

function sceneBounds(scene: ImageryItem): maplibregl.LngLatBoundsLike | null {
  if (Array.isArray(scene.bbox) && scene.bbox.length === 4) {
    const [minLon, minLat, maxLon, maxLat] = scene.bbox;
    if (
      [minLon, minLat, maxLon, maxLat].every((value) => Number.isFinite(value)) &&
      minLon < maxLon &&
      minLat < maxLat
    ) {
      return [
        [minLon, minLat],
        [maxLon, maxLat],
      ];
    }
  }

  const geometry = scene.footprint_geojson;
  if (!geometry) {
    return null;
  }

  const coordinates: number[][] =
    geometry.type === "Polygon"
      ? geometry.coordinates.flat()
      : geometry.type === "MultiPolygon"
        ? geometry.coordinates.flat(2)
        : [];

  if (coordinates.length === 0) {
    return null;
  }

  let minLon = Number.POSITIVE_INFINITY;
  let minLat = Number.POSITIVE_INFINITY;
  let maxLon = Number.NEGATIVE_INFINITY;
  let maxLat = Number.NEGATIVE_INFINITY;

  for (const [lon, lat] of coordinates) {
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      continue;
    }
    minLon = Math.min(minLon, lon);
    minLat = Math.min(minLat, lat);
    maxLon = Math.max(maxLon, lon);
    maxLat = Math.max(maxLat, lat);
  }

  if (!Number.isFinite(minLon) || !Number.isFinite(minLat) || !Number.isFinite(maxLon) || !Number.isFinite(maxLat)) {
    return null;
  }
  if (minLon >= maxLon || minLat >= maxLat) {
    return null;
  }

  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ];
}

function toFieldFeatureCollection(
  geometry: GeoJSON.Geometry | null,
  fieldId: string,
): GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, { field_id: string }> {
  if (!fieldId || !geometry) {
    return { type: "FeatureCollection", features: [] };
  }
  if (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon") {
    return { type: "FeatureCollection", features: [] };
  }
  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { field_id: fieldId },
        geometry: geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon,
      },
    ],
  };
}

function geometryBounds(geometry: GeoJSON.Geometry | null): maplibregl.LngLatBoundsLike | null {
  if (!geometry) {
    return null;
  }
  const coordinates: number[][] =
    geometry.type === "Polygon"
      ? geometry.coordinates.flat()
      : geometry.type === "MultiPolygon"
        ? geometry.coordinates.flat(2)
        : [];

  if (coordinates.length === 0) {
    return null;
  }

  let minLon = Number.POSITIVE_INFINITY;
  let minLat = Number.POSITIVE_INFINITY;
  let maxLon = Number.NEGATIVE_INFINITY;
  let maxLat = Number.NEGATIVE_INFINITY;

  for (const [lon, lat] of coordinates) {
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      continue;
    }
    minLon = Math.min(minLon, lon);
    minLat = Math.min(minLat, lat);
    maxLon = Math.max(maxLon, lon);
    maxLat = Math.max(maxLat, lat);
  }

  if (!Number.isFinite(minLon) || !Number.isFinite(minLat) || !Number.isFinite(maxLon) || !Number.isFinite(maxLat)) {
    return null;
  }
  if (minLon >= maxLon || minLat >= maxLat) {
    return null;
  }

  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ];
}

export function MapWorkspace({
  mapMode,
  onGeometryChange,
  imageryResults = [],
  selectedSceneId = "",
  onSceneSelect = () => {},
  selectedFieldId = "",
  selectedFieldGeometry = null,
}: MapWorkspaceProps) {
  const [basemap, setBasemap] = useState<BasemapKey>("SATELLITE");
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const onSceneSelectRef = useRef(onSceneSelect);
  const imageryResultsRef = useRef(imageryResults);
  const selectedSceneIdRef = useRef(selectedSceneId);
  const selectedFieldIdRef = useRef(selectedFieldId);
  const selectedFieldGeometryRef = useRef(selectedFieldGeometry);
  const lastZoomedFieldIdRef = useRef<string>("");

  useEffect(() => {
    onSceneSelectRef.current = onSceneSelect;
  }, [onSceneSelect]);

  useEffect(() => {
    imageryResultsRef.current = imageryResults;
    selectedSceneIdRef.current = selectedSceneId;
  }, [imageryResults, selectedSceneId]);

  useEffect(() => {
    selectedFieldIdRef.current = selectedFieldId;
    selectedFieldGeometryRef.current = selectedFieldGeometry;
  }, [selectedFieldId, selectedFieldGeometry]);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) {
      return;
    }

    patchMapboxDrawForMapLibre();

    const [lon, lat] = (process.env.NEXT_PUBLIC_DEFAULT_CENTER ?? "-5.5,35.2")
      .split(",")
      .map((value) => Number(value.trim()));
    const zoom = Number(process.env.NEXT_PUBLIC_DEFAULT_ZOOM ?? "7");

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: DEFAULT_MAP_STYLE as any,
      center: [lon, lat],
      zoom,
      pitch: 0,
    });

    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
    map.addControl(new maplibregl.FullscreenControl(), "top-right");
    map.addControl(
      new maplibregl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: false,
        showUserLocation: true,
      }),
      "top-right",
    );
    map.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 120 }), "bottom-left");

    const draw = new MapboxDraw({
      displayControlsDefault: false,
      controls: {
        polygon: true,
        trash: true,
      },
      defaultMode: "draw_polygon",
      styles: DRAW_STYLES as any,
    });

    map.addControl(draw as unknown as maplibregl.IControl, "top-left");

    const handleFootprintClick = (event: maplibregl.MapLayerMouseEvent) => {
      const sceneId = event.features?.[0]?.properties?.scene_id;
      if (typeof sceneId === "string" && sceneId) {
        onSceneSelectRef.current(sceneId);
      }
    };

    map.on("load", () => {
      applyBasemapVisibility(map, basemap);

      if (!map.getSource(IMAGERY_SOURCE_ID)) {
        map.addSource(IMAGERY_SOURCE_ID, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }
      if (!map.getSource(FIELD_SOURCE_ID)) {
        map.addSource(FIELD_SOURCE_ID, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }

      if (!map.getLayer(IMAGERY_FILL_LAYER_ID)) {
        map.addLayer({
          id: IMAGERY_FILL_LAYER_ID,
          type: "fill",
          source: IMAGERY_SOURCE_ID,
          paint: {
            "fill-color": [
              "case",
              ["==", ["get", "selected"], true],
              "#22c6be",
              "#13a56f",
            ],
            "fill-opacity": 0.16,
          },
        });
      }

      if (!map.getLayer(IMAGERY_LINE_LAYER_ID)) {
        map.addLayer({
          id: IMAGERY_LINE_LAYER_ID,
          type: "line",
          source: IMAGERY_SOURCE_ID,
          paint: {
            "line-color": [
              "case",
              ["==", ["get", "selected"], true],
              "#74e6df",
              "#13a56f",
            ],
            "line-width": [
              "case",
              ["==", ["get", "selected"], true],
              2.5,
              1.6,
            ],
          },
        });
      }
      if (!map.getLayer(FIELD_FILL_LAYER_ID)) {
        map.addLayer({
          id: FIELD_FILL_LAYER_ID,
          type: "fill",
          source: FIELD_SOURCE_ID,
          paint: {
            "fill-color": "#f59e0b",
            "fill-opacity": 0.14,
          },
        });
      }
      if (!map.getLayer(FIELD_LINE_LAYER_ID)) {
        map.addLayer({
          id: FIELD_LINE_LAYER_ID,
          type: "line",
          source: FIELD_SOURCE_ID,
          paint: {
            "line-color": "#fbbf24",
            "line-width": 2.6,
          },
        });
      }

      const source = map.getSource(IMAGERY_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
      source?.setData(toFootprintFeatureCollection(imageryResultsRef.current, selectedSceneIdRef.current));
      const fieldSource = map.getSource(FIELD_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
      fieldSource?.setData(toFieldFeatureCollection(selectedFieldGeometryRef.current, selectedFieldIdRef.current));

      const initialFieldBounds = geometryBounds(selectedFieldGeometryRef.current);
      if (initialFieldBounds && selectedFieldIdRef.current) {
        map.fitBounds(initialFieldBounds, {
          padding: 72,
          duration: 0,
          maxZoom: 15,
        });
        lastZoomedFieldIdRef.current = selectedFieldIdRef.current;
      }

      map.on("click", IMAGERY_FILL_LAYER_ID, handleFootprintClick);
      map.on("click", IMAGERY_LINE_LAYER_ID, handleFootprintClick);
      map.on("mouseenter", IMAGERY_FILL_LAYER_ID, () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", IMAGERY_FILL_LAYER_ID, () => {
        map.getCanvas().style.cursor = "";
      });
    });

    const sync = () => {
      const data = draw.getAll();
      const geometry = data.features[0]?.geometry as GeoJSON.Geometry | undefined;
      onGeometryChange(geometry ?? null);
    };

    map.on("draw.create", sync);
    map.on("draw.update", sync);
    map.on("draw.delete", sync);

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [onGeometryChange]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) {
      return;
    }
    applyBasemapVisibility(map, basemap);
  }, [basemap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }
    const source = map.getSource(IMAGERY_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    source?.setData(toFootprintFeatureCollection(imageryResults, selectedSceneId));
  }, [imageryResults, selectedSceneId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }
    const source = map.getSource(FIELD_SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    source?.setData(toFieldFeatureCollection(selectedFieldGeometry, selectedFieldId));
  }, [selectedFieldGeometry, selectedFieldId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }
    if (!selectedFieldId || !selectedFieldGeometry) {
      lastZoomedFieldIdRef.current = "";
      return;
    }
    if (lastZoomedFieldIdRef.current === selectedFieldId) {
      return;
    }
    const bounds = geometryBounds(selectedFieldGeometry);
    if (!bounds) {
      return;
    }
    map.fitBounds(bounds, {
      padding: 72,
      duration: 550,
      maxZoom: 15,
    });
    lastZoomedFieldIdRef.current = selectedFieldId;
  }, [selectedFieldGeometry, selectedFieldId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedSceneId) {
      return;
    }
    const scene = imageryResults.find((item) => item.scene_id === selectedSceneId);
    if (!scene) {
      return;
    }
    const bounds = sceneBounds(scene);
    if (!bounds) {
      return;
    }
    map.fitBounds(bounds, {
      padding: 72,
      duration: 550,
      maxZoom: 14,
    });
  }, [imageryResults, selectedSceneId]);

  const selectedSceneSummary = selectedSceneId ? `Selected scene: ${selectedSceneId}` : "";
  const selectedFieldSummary = selectedFieldId ? `Selected field: ${selectedFieldId}` : "";
  const selectedSceneCount = selectedSceneId
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean).length;
  const sceneCountSummary =
    selectedSceneCount > 0
      ? `${selectedSceneCount} selected footprint(s) visible.`
      : imageryResults.length > 0
        ? "No scene selected. Choose one in Imagery Results."
        : "";
  const modeMeta = MODE_DESCRIPTION[mapMode];

  return (
    <div className="relative h-full w-full">
      <div ref={mapContainerRef} className="map-root rounded-[18px]" />
      <div className="pointer-events-none absolute right-4 top-4 z-10 rounded-full border border-[var(--line-strong)] bg-[rgba(7,16,29,0.84)] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--ink-800)] shadow-[0_14px_26px_rgba(0,0,0,0.34)]">
        Mode {modeMeta.label}
      </div>
      <div className="absolute left-1/2 top-4 z-10 flex -translate-x-1/2 items-center gap-1 rounded-lg border border-[var(--line-strong)] bg-[rgba(7,16,29,0.84)] p-1 shadow-[0_14px_26px_rgba(0,0,0,0.34)]">
        {BASEMAP_OPTIONS.map((option) => (
          <button
            key={option.key}
            type="button"
            onClick={() => setBasemap(option.key)}
            className={`rounded-md px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] transition ${
              basemap === option.key
                ? "bg-[var(--accent-500)] text-[#04141a]"
                : "text-[var(--ink-700)] hover:bg-[rgba(37,61,90,0.64)]"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
      <div className="pointer-events-none absolute bottom-4 left-4 z-10 max-w-[420px] rounded-lg border border-[var(--line-strong)] bg-[rgba(7,16,29,0.78)] px-3 py-2 text-[11px] font-medium text-[var(--ink-800)] shadow-[0_14px_26px_rgba(0,0,0,0.34)]">
        <div>{modeMeta.detail}</div>
        <div>Draw tools stay available at the top-left map controls.</div>
        {sceneCountSummary && <div>{sceneCountSummary}</div>}
        {selectedSceneSummary && <div className="truncate">{selectedSceneSummary}</div>}
        {selectedFieldSummary && <div className="truncate">{selectedFieldSummary}</div>}
      </div>
    </div>
  );
}
