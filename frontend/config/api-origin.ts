/** Vercel hosts the SPA without the same-origin API proxy used by Docker. */
export function validateVercelApiOrigin(value: string | undefined): void {
  const message = "Vercel requires VITE_API_BASE_URL to be the public HTTPS backend origin (no /api/v1 path or credentials).";
  let url: URL;
  try {
    url = new URL(value ?? "");
  } catch {
    throw new Error(message);
  }
  const hostname = url.hostname.toLowerCase().replace(/\.$/, "");
  if (
    value !== value?.trim() || url.protocol !== "https:" ||
    url.username || url.password || url.pathname !== "/" ||
    url.search || url.hash || hostname === "localhost" ||
    hostname.endsWith(".localhost") || hostname === "[::1]" ||
    hostname === "0.0.0.0" || hostname.startsWith("127.")
  ) {
    throw new Error(message);
  }
}
