import type { ReactNode, SVGProps } from 'react'

export type IconName =
  | 'search'
  | 'explore'
  | 'feed'
  | 'shelf'
  | 'diary'
  | 'memory'
  | 'profile'
  | 'people'
  | 'heart'
  | 'bookmark'
  | 'comment'
  | 'flag'
  | 'plus'
  | 'settings'
  | 'close'
  | 'moon'
  | 'sun'
  | 'arrow'
  | 'refresh'
  | 'external'
  | 'chevron-down'
  | 'bell'

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

  const paths: Record<IconName, ReactNode> = {
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
    'chevron-down': <path d="m6 9 6 6 6-6" />,
    explore: <><circle cx="12" cy="12" r="9" /><path d="m15.5 8.5-2.2 4.8-4.8 2.2 2.2-4.8z" /></>,
    feed: <><path d="M5 5h14" /><path d="M5 12h10" /><path d="M5 19h7" /></>,
    shelf: <><path d="M4 5h4v14H4z" /><path d="M10 5h4v14h-4z" /><path d="m16 6 3-1 3 13-3 1z" /></>,
    diary: <><path d="M5 4h12a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2z" /><path d="M8 4v16" /><path d="M11 8h5" /><path d="M11 12h5" /></>,
    memory: <><path d="M5 4h14v16H5z" /><path d="M8 4v16" /><path d="m13 8 .7 1.5 1.6.2-1.2 1.1.3 1.7-1.4-.8-1.4.8.3-1.7-1.2-1.1 1.7-.2z" /></>,
    profile: <><circle cx="12" cy="8" r="3" /><path d="M5 20c.8-4 3-6 7-6s6.2 2 7 6" /></>,
    people: <><circle cx="9" cy="8" r="3" /><path d="M3 20c.7-4 2.7-6 6-6s5.3 2 6 6" /><path d="M16 5a3 3 0 0 1 0 6" /><path d="M18 14c1.8.7 2.8 2.7 3 6" /></>,
    heart: <path d="M20.8 5.8a5 5 0 0 0-7.1 0L12 7.5l-1.7-1.7a5 5 0 1 0-7.1 7.1L12 21l8.8-8.1a5 5 0 0 0 0-7.1Z" />,
    bookmark: <path d="M6 4h12v17l-6-4-6 4z" />,
    comment: <><path d="M4 5h16v11H9l-5 4z" /><path d="M8 9h8" /><path d="M8 12h5" /></>,
    flag: <><path d="M5 21V4" /><path d="M5 5h11l-2 3 2 3H5" /></>,
    plus: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21h-4v-.1A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3.1 14H3v-4h.1A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6 1.7 1.7 0 0 0 10 3.1V3h4v.1A1.7 1.7 0 0 0 15 4.6a1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.5 1h.1v4h-.1a1.7 1.7 0 0 0-1.5 1Z" /></>,
    close: <><path d="m6 6 12 12" /><path d="M18 6 6 18" /></>,
    moon: <path d="M20 15.5A8 8 0 0 1 8.5 4 8 8 0 1 0 20 15.5Z" />,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2" /><path d="M12 20v2" /><path d="m4.9 4.9 1.4 1.4" /><path d="m17.7 17.7 1.4 1.4" /><path d="M2 12h2" /><path d="M20 12h2" /><path d="m4.9 19.1 1.4-1.4" /><path d="m17.7 6.3 1.4-1.4" /></>,
    arrow: <><path d="M5 12h14" /><path d="m14 7 5 5-5 5" /></>,
    refresh: <><path d="M20 6v5h-5" /><path d="M4 18v-5h5" /><path d="M6.1 9A7 7 0 0 1 18.5 6.5L20 11" /><path d="M17.9 15A7 7 0 0 1 5.5 17.5L4 13" /></>,
    external: <><path d="M14 5h5v5" /><path d="m10 14 9-9" /><path d="M19 13v6H5V5h6" /></>,
    bell: <><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6" /><path d="M10.5 20a2 2 0 0 0 3 0" /></>,
  }

  return <svg {...common} {...props}>{paths[name]}</svg>
}
