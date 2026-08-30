import type { TileManifestEntry, TilePayload, WorldManifest } from './types';

export interface WorldSource {
  loadManifest(): Promise<WorldManifest>;
  loadTile(entry: TileManifestEntry): Promise<TilePayload>;
}

async function fetchJson<T>(url: string): Promise<{ value: T; responseUrl: string }> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`World data request failed (${response.status}): ${url}`);
  }
  return { value: (await response.json()) as T, responseUrl: response.url };
}

export class HttpWorldSource implements WorldSource {
  private manifestBaseUrl: URL | undefined;

  constructor(private readonly manifestUrl = '/manifest.json') {}

  async loadManifest(): Promise<WorldManifest> {
    const { value, responseUrl } = await fetchJson<WorldManifest>(this.manifestUrl);
    const baseHref = responseUrl || new URL(this.manifestUrl, document.baseURI).toString();
    this.manifestBaseUrl = new URL(baseHref);
    return value;
  }

  async loadTile(entry: TileManifestEntry): Promise<TilePayload> {
    if (!this.manifestBaseUrl) {
      throw new Error('World manifest must be loaded before tile requests.');
    }
    const url = new URL(entry.file, this.manifestBaseUrl).toString();
    const { value } = await fetchJson<TilePayload>(url);
    if (value.tile_id !== entry.tile_id) {
      throw new Error(`Tile identity mismatch: expected ${entry.tile_id}, received ${value.tile_id}`);
    }
    return value;
  }
}
