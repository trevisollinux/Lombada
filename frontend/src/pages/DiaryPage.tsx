import { Icon } from '../components/Icon'
import { PageHeader } from '../components/PageHeader'
import { usePreferences } from '../providers/PreferencesProvider'

const timeline = [
  { day: '12', month: 'jul', title: 'Progresso de leitura', note: 'Página 148 · 52%' },
  { day: '09', month: 'jul', title: 'Impressão rápida', note: 'Uma frase que merece voltar depois.' },
  { day: '04', month: 'jul', title: 'Início da leitura', note: 'Nova edição adicionada à estante.' },
]

export function DiaryPage() {
  const { t } = usePreferences()

  return (
    <section className="page">
      <PageHeader
        eyebrow={t('diary_eyebrow')}
        title={t('diary_title')}
        description={t('diary_copy')}
        aside={<span className="stage-stamp">04 · memória</span>}
      />

      <div className="diary-preview" aria-hidden="true">
        {timeline.map((item, index) => (
          <article className="diary-preview__entry" key={`${item.day}-${item.title}`}>
            <time>
              <strong>{item.day}</strong>
              <span>{item.month}</span>
            </time>
            <span className="diary-preview__line" />
            <div>
              <p className="eyebrow">entrada {String(index + 1).padStart(2, '0')}</p>
              <h2>{item.title}</h2>
              <p>{item.note}</p>
            </div>
            <Icon name="arrow" size={20} />
          </article>
        ))}
      </div>

      <p className="migration-note">{t('feature_next')} · formulário, progresso e linha do tempo real</p>
    </section>
  )
}
