const paths = {
  shield: "M12 3 4 6v6c0 4 4 7 8 9 4-2 8-5 8-9V6l-8-3Z M9 12l2 2 4-4",
  dashboard: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  link: "m10 13 4-4 M8 16l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0 M16 8l1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0",
  network: "M12 5v5 M5 17l5-5 M19 17l-5-5 M10 2h4v4h-4z M2 17h5v5H2z M17 17h5v5h-5z M10 10h4v4h-4z",
  file: "M14 2H5v20h14V7l-5-5Z M14 2v6h5 M8 12h8 M8 16h6",
  audit: "M8 4H5v18h14V4h-3 M8 2h8v4H8z M8 11h8 M8 15h8 M8 19h5",
  arrow: "M4 12h16 M14 6l6 6-6 6",
  menu: "M4 6h16 M4 12h16 M4 18h16",
  close: "m6 6 12 12 M6 18 18 6",
  logout: "M9 4H4v16h5 M9 12h12 M16 7l5 5-5 5",
} as const;

export type InterfaceIconName = keyof typeof paths;

export function InterfaceIcon({ name, size = 20 }: { name: InterfaceIconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false"><path d={paths[name]} /></svg>;
}
