// Placeholder outline icons for the skeleton. Replace with the DS icon set (ds.json > icons).
const paths: Record<string, string[]> = {
  home: ["M3 10.5 12 3l9 7.5", "M5 9.5V21h14V9.5"],
  settings: ["M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1", "M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"],
  mode: ["M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"],
}

export function NavIcon({ name, className }: { name: keyof typeof paths; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className ?? "size-5"}>
      {paths[name].map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  )
}
