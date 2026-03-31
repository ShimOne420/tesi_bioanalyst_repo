import type { CityOption, SelectionBounds } from "./types";

export const CITY_OPTIONS: CityOption[] = [
  { value: "milano", label: "Milano", country: "Italia", lat: 45.4642, lon: 9.19 },
  { value: "roma", label: "Roma", country: "Italia", lat: 41.9028, lon: 12.4964 },
  { value: "parigi", label: "Parigi", country: "Francia", lat: 48.8566, lon: 2.3522 },
  { value: "barcellona", label: "Barcellona", country: "Spagna", lat: 41.3851, lon: 2.1734 },
  { value: "madrid", label: "Madrid", country: "Spagna", lat: 40.4168, lon: -3.7038 },
  { value: "berlino", label: "Berlino", country: "Germania", lat: 52.52, lon: 13.405 },
  { value: "amsterdam", label: "Amsterdam", country: "Paesi Bassi", lat: 52.3676, lon: 4.9041 },
  { value: "lisbona", label: "Lisbona", country: "Portogallo", lat: 38.7223, lon: -9.1393 },
  { value: "vienna", label: "Vienna", country: "Austria", lat: 48.2082, lon: 16.3738 },
  { value: "varsavia", label: "Varsavia", country: "Polonia", lat: 52.2297, lon: 21.0122 }
];

export function buildBoundsFromCity(city: CityOption, halfWindowDeg: number): SelectionBounds {
  return {
    minLat: city.lat - halfWindowDeg,
    maxLat: city.lat + halfWindowDeg,
    minLon: city.lon - halfWindowDeg,
    maxLon: city.lon + halfWindowDeg
  };
}
