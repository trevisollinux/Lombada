import { useEffect, useId, useMemo, useRef, useState } from 'react'

import { Icon } from './Icon'

export interface SelectOption {
  value: string
  label: string
  /** texto auxiliar à direita (ex.: contagem de obras) */
  hint?: string
}

interface SelectMenuProps {
  /** rótulo em caixa-alta acima do gatilho (opcional) */
  label?: string
  value: string
  options: SelectOption[]
  onChange: (value: string) => void
  /** rótulo do gatilho quando nada está selecionado */
  placeholder?: string
  ariaLabel?: string
  /** mostra um campo de filtro no topo (para listas longas, ex.: editoras) */
  searchable?: boolean
  searchPlaceholder?: string
  emptyLabel?: string
  className?: string
}

/* Dropdown editorial no lugar do <select> nativo: no v1 os filtros nunca usam
   picker nativo (que abre a folha do sistema, fora do estilo). Mesma mecânica
   do menu de filtro da estante — gatilho + lista custom, fecha no Esc/fora. */
export function SelectMenu({
  label,
  value,
  options,
  onChange,
  placeholder,
  ariaLabel,
  searchable = false,
  searchPlaceholder,
  emptyLabel = '—',
  className = '',
}: SelectMenuProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const searchRef = useRef<HTMLInputElement>(null)
  const rootId = useId()

  const selected = options.find((option) => option.value === value)
  const triggerLabel = selected?.label ?? placeholder ?? ''

  const filtered = useMemo(() => {
    if (!searchable || !query.trim()) return options
    const q = query
      .trim()
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
    return options.filter((option) =>
      option.label
        .toLowerCase()
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .includes(q),
    )
  }, [options, query, searchable])

  useEffect(() => {
    if (!open) {
      setQuery('')
      return
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', onKeyDown)
    if (searchable) searchRef.current?.focus()
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, searchable])

  function choose(next: string) {
    onChange(next)
    setOpen(false)
  }

  return (
    <div className={`select-menu ${className}`.trim()}>
      {label && (
        <span className="select-menu__label" id={`${rootId}-label`}>
          {label}
        </span>
      )}
      <button
        type="button"
        className="select-menu__trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-labelledby={label ? `${rootId}-label ${rootId}-value` : undefined}
        aria-label={label ? undefined : ariaLabel}
        onClick={() => setOpen((current) => !current)}
      >
        <span id={`${rootId}-value`} className="select-menu__value">
          {triggerLabel}
        </span>
        <Icon name="chevron-down" size={15} />
      </button>

      {open && (
        <>
          <button
            className="select-menu__backdrop"
            type="button"
            aria-hidden="true"
            tabIndex={-1}
            onClick={() => setOpen(false)}
          />
          <div className="select-menu__panel" role="listbox" aria-label={ariaLabel || label}>
            {searchable && (
              <input
                ref={searchRef}
                className="select-menu__search"
                type="text"
                value={query}
                placeholder={searchPlaceholder || 'Filtrar…'}
                onChange={(event) => setQuery(event.target.value)}
              />
            )}
            <div className="select-menu__list">
              {filtered.map((option) => (
                <button
                  key={option.value || '__none__'}
                  type="button"
                  role="option"
                  aria-selected={option.value === value}
                  className={option.value === value ? 'is-active' : ''}
                  onClick={() => choose(option.value)}
                >
                  <span>{option.label}</span>
                  {option.hint && <small>{option.hint}</small>}
                </button>
              ))}
              {filtered.length === 0 && <p className="select-menu__empty">{emptyLabel}</p>}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
