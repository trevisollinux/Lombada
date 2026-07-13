import { Link } from 'react-router'

import { BookCover } from '../../components/BookCover'
import { Icon } from '../../components/Icon'
import type { Locale } from '../../i18n'
import type { FeedUser, ReadingNowItem } from '../../types/feed'
import { FeedAvatar } from './FeedAvatar'
import { feedText } from './feedI18n'
import { FollowButton } from './FollowButton'

interface ReadingNowRailProps {
  items: ReadingNowItem[]
  locale: Locale
}

export function ReadingNowRail({ items, locale }: ReadingNowRailProps) {
  if (items.length === 0) return null

  return (
    <section className="feed-panel feed-panel--reading-now" aria-labelledby="reading-now-title">
      <div className="feed-panel__heading">
        <div>
          <p className="eyebrow">{feedText(locale, 'reading_now')}</p>
          <h2 id="reading-now-title">{feedText(locale, 'reading_now')}</h2>
        </div>
        <span>{items.length}</span>
      </div>
      <div className="reading-now-rail">
        {items.map((item) => {
          const params = new URLSearchParams({
            work_key: item.work_key,
            titulo: item.titulo,
            autor: item.autor,
          })
          const state = {
            work: {
              work_key: item.work_key,
              titulo: item.titulo,
              autor: item.autor,
              ano: null,
              idioma_original: '',
              capa_url: item.capa_url,
            },
          }
          return (
            <article key={`${item.handle}-${item.work_key}-${item.titulo}`} className="reading-now-card">
              <Link
                className="reading-now-card__book"
                to={{ pathname: '/obra', search: `?${params.toString()}` }}
                state={state}
              >
                <BookCover title={item.titulo} author={item.autor} url={item.capa_url} />
              </Link>
              <div className="reading-now-card__reader">
                <a href={`/u/${encodeURIComponent(item.handle)}`}>
                  <FeedAvatar name={item.nome} handle={item.handle} url={item.avatar_url} size="small" />
                </a>
                <div>
                  <a href={`/u/${encodeURIComponent(item.handle)}`}>{item.nome || `@${item.handle}`}</a>
                  <span>{item.titulo}</span>
                </div>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

interface ReaderSuggestionsProps {
  readers: FeedUser[]
  locale: Locale
  loggedIn: boolean
  onFollowChange: (handle: string, following: boolean) => void
}

export function ReaderSuggestions({ readers, locale, loggedIn, onFollowChange }: ReaderSuggestionsProps) {
  if (readers.length === 0) return null

  return (
    <section className="feed-panel feed-panel--readers" aria-labelledby="reader-suggestions-title">
      <div className="feed-panel__heading">
        <div>
          <p className="eyebrow">{feedText(locale, 'discover')}</p>
          <h2 id="reader-suggestions-title">{feedText(locale, 'reader_suggestions')}</h2>
        </div>
        <Icon name="people" size={25} />
      </div>
      <div className="reader-suggestion-grid">
        {readers.map((reader) => (
          <article key={reader.handle} className="reader-suggestion-card">
            <a className="reader-suggestion-card__identity" href={`/u/${encodeURIComponent(reader.handle)}`}>
              <FeedAvatar name={reader.nome} handle={reader.handle} url={reader.avatar_url} size="large" />
              <span>
                <strong>{reader.nome || `@${reader.handle}`}</strong>
                <small>@{reader.handle}</small>
              </span>
            </a>
            {reader.bio && <p>{reader.bio}</p>}
            <div className="reader-suggestion-card__metrics">
              <span><strong>{reader.reviews_count ?? 0}</strong>{feedText(locale, 'reviews')}</span>
              <span><strong>{reader.followers_count ?? 0}</strong>{feedText(locale, 'followers')}</span>
            </div>
            <div className="reader-suggestion-card__actions">
              <FollowButton
                handle={reader.handle}
                following={reader.is_following}
                isMe={reader.is_me}
                isDemo={reader.is_demo}
                loggedIn={loggedIn}
                locale={locale}
                onChange={onFollowChange}
              />
              <a className="text-button" href={`/u/${encodeURIComponent(reader.handle)}`}>
                {feedText(locale, 'open_profile')} <Icon name="arrow" size={14} />
              </a>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
