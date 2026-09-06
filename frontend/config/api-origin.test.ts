import { describe, expect, it } from "vitest";
import { validateVercelApiOrigin } from "./api-origin";

describe("Vercel API origin", () => {
  it.each(["https://api.example.com", "https://api.example.com/"])("accepts %s", (value) => {
    expect(() => validateVercelApiOrigin(value)).not.toThrow();
  });

  it.each([
    undefined, "", "/api", "http://api.example.com", "https://api.example.com/api/v1",
    "https://user:secret@api.example.com", "https://api.example.com?key=value",
    "https://api.example.com#fragment", "https://localhost", "https://localhost.",
    "https://api.localhost", "https://127.0.0.1", "https://[::1]", "https://0.0.0.0",
    " https://api.example.com ",
  ])("rejects an unusable origin %s", (value) => {
    expect(() => validateVercelApiOrigin(value)).toThrow("VITE_API_BASE_URL");
  });
});
