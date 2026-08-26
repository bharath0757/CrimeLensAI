/**
 * CrimeLensAI — Platform Adapter Layer
 * ======================================
 * Thin adapter isolating platform-specific code (browser APIs, Capacitor, etc.)
 * from shared components.
 *
 * WHY: The web app must deploy as a static site (Vercel) AND be wrappable
 * with Capacitor for mobile builds without restructuring. All platform-specific
 * calls go through this adapter so shared components never use browser-only
 * APIs directly.
 *
 * USAGE:
 *   import { platform } from '@/adapters/platform';
 *   const data = await platform.storage.get('key');
 *   await platform.share({ title, text, url });
 */

// ---- Storage Adapter ----
export interface StorageAdapter {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}

const webStorage: StorageAdapter = {
  async get(key) {
    return localStorage.getItem(key);
  },
  async set(key, value) {
    localStorage.setItem(key, value);
  },
  async remove(key) {
    localStorage.removeItem(key);
  },
};

// ---- Share Adapter ----
export interface ShareData {
  title?: string;
  text?: string;
  url?: string;
}

export interface ShareAdapter {
  share(data: ShareData): Promise<void>;
  canShare(): boolean;
}

const webShare: ShareAdapter = {
  async share(data) {
    if (navigator.share) {
      await navigator.share(data);
    } else {
      // Fallback: copy to clipboard
      const text = `${data.title ?? ""}\n${data.text ?? ""}\n${data.url ?? ""}`.trim();
      await navigator.clipboard.writeText(text);
    }
  },
  canShare() {
    return typeof navigator.share === "function";
  },
};

// ---- File System Adapter ----
export interface FileAdapter {
  downloadBlob(blob: Blob, filename: string): void;
}

const webFile: FileAdapter = {
  downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  },
};

// ---- Platform Object ----
export interface Platform {
  type: "web" | "capacitor";
  storage: StorageAdapter;
  share: ShareAdapter;
  file: FileAdapter;
}

/**
 * Current platform implementation.
 *
 * For Capacitor builds, replace this with a Capacitor-backed implementation
 * that uses @capacitor/preferences, @capacitor/share, @capacitor/filesystem.
 */
export const platform: Platform = {
  type: "web",
  storage: webStorage,
  share: webShare,
  file: webFile,
};
