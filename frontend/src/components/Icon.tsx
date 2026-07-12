import type { SVGProps } from 'react'

export type IconName =
  | 'search'
  | 'feed'
  | 'shelf'
  | 'diary'
  | 'profile'
  | 'plus'
  | 'settings'
  | 'close'
  | 'moon'
  | 'sun'
  | 'arrow'
  | 'refresh'
  | 'external'

interface IconProps extends SVGProps<SVGSVGElement> {
  name: IconName
  size?: number
}

export function Icon({ name, size = 22, ...props }: IconProps) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }

  const paths: Record<IconName, React.ReactNode> = {
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    feed: <><path d="M5 5h14" /><path d="M5 12h10" /><path d="M5 19h7" /></>,
    shelf: <><path d="M4 5h4v14H4z" /><path d="M10 5h4v14h-4z" /><path d="m16 6 3-1 3 13-3 1z" /></>,
    diary: <><path d="M5 4h12a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2z" /><path d="M8 4v16" /><path d="M11 8h5" /><path d="M11 12h5" /></>,
    profile: <><circle cx="12" cy="8" r="3" /><path d="M5 20c.8-4 3-6 7-6s6.2 2 7 6" /></>,
    plus: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21h-4v-.1A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3.1 14H3v-4h.1A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3.1V3h4v.1A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.5 1h.1v4h-.1a1.7 1.7 0 0 0-1.5 1Z" /></>,
    close: <><path d="m6 6 12 12" /><path d="M18 6 6 18" /></>,
    moon: <path d="M20 15.5A8 8 0 0 1 8.5 4 8 8 0 1 0 20 15.5Z" />,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2" /><path d="M12 20v2" /><path d="m4.9 4.9 1.4 1.4" /><path d="m17.7 17.7 1.4 1.4" /><path d="M2 12h2" /><path d="M20 12h2" /><path d="m4.9 19.1 1.4-1.4" /><path d="m17.7 6.3 1.4-1.4" /></>,
    arrow: <><path d="M5 12h14" /><path d="m14 7 5 5-5 5" /></>,
    refresh: <><path d="M20 6v5h-5" /><path d="M4 18v-5h5" /><path d="M6.1 9A7 7 0 0 1 18.5 6.5L20 11" /><path d="M17.9 15A7 7 0 0 1 5.5 17.5L4 13" /></>,
    external: <><path d="M14 5h5v5" /><path d="m10 14 9-9" /><path d="M19 13v6H5V5h6" /></>,
  }

  return <svg {...common} {...props}>{paths[name]}</svg>
}
