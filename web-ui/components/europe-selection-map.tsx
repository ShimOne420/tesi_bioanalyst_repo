"use client";

import { useEffect } from "react";

import L from "leaflet";
import "leaflet-draw";
import { MapContainer, Rectangle, TileLayer, useMap } from "react-leaflet";

import type { SelectionBounds } from "../lib/types";

type EuropeSelectionMapProps = {
  manualBounds: SelectionBounds | null;
  previewBounds: SelectionBounds | null;
  onBoundsChange: (bounds: SelectionBounds | null) => void;
};

function BoundsViewport({ bounds }: { bounds: SelectionBounds }) {
  const map = useMap();

  useEffect(() => {
    map.fitBounds(
      [
        [bounds.minLat, bounds.minLon],
        [bounds.maxLat, bounds.maxLon]
      ],
      { padding: [30, 30] }
    );
  }, [bounds, map]);

  return null;
}

function DrawRectangleControl({
  onBoundsChange
}: {
  onBoundsChange: (bounds: SelectionBounds | null) => void;
}) {
  const map = useMap();

  useEffect(() => {
    const featureGroup = new L.FeatureGroup();
    map.addLayer(featureGroup);

    const drawControl = new L.Control.Draw({
      position: "topright",
      draw: {
        rectangle: {
          shapeOptions: {
            color: "#b35c33"
          }
        },
        polygon: false,
        polyline: false,
        circle: false,
        circlemarker: false,
        marker: false
      },
      edit: {
        featureGroup,
        edit: false,
        remove: false
      }
    });

    map.addControl(drawControl);

    const onCreated: L.LeafletEventHandlerFn = (event) => {
      const drawEvent = event as L.DrawEvents.Created;
      const layer = drawEvent.layer as L.Rectangle;
      const bounds = layer.getBounds();

      featureGroup.clearLayers();
      featureGroup.addLayer(layer);

      onBoundsChange({
        minLat: bounds.getSouth(),
        maxLat: bounds.getNorth(),
        minLon: bounds.getWest(),
        maxLon: bounds.getEast()
      });
    };

    map.on(L.Draw.Event.CREATED, onCreated);

    return () => {
      map.off(L.Draw.Event.CREATED, onCreated);
      map.removeControl(drawControl);
      map.removeLayer(featureGroup);
    };
  }, [map, onBoundsChange]);

  return null;
}

export function EuropeSelectionMap({
  manualBounds,
  previewBounds,
  onBoundsChange
}: EuropeSelectionMapProps) {
  const displayBounds = manualBounds ?? previewBounds;

  return (
    <MapContainer center={[54, 15]} zoom={4} scrollWheelZoom className="map-shell">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {displayBounds ? <BoundsViewport bounds={displayBounds} /> : null}

      {displayBounds ? (
        <Rectangle
          bounds={[
            [displayBounds.minLat, displayBounds.minLon],
            [displayBounds.maxLat, displayBounds.maxLon]
          ]}
          pathOptions={{
            color: manualBounds ? "#b35c33" : "#2f7f5f",
            weight: 2
          }}
        />
      ) : null}

      <DrawRectangleControl onBoundsChange={onBoundsChange} />
    </MapContainer>
  );
}
