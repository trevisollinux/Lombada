import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'

import type { Locale } from '../../i18n'
import {
  removeProfileAvatar,
  updateProfile,
  uploadProfileAvatar,
} from '../../services/api'
import type { Account } from '../../types/account'
import { prepareAvatar } from './avatarProcessing'
import { profileText } from './profileI18n'

interface ProfileIdentityEditorProps {
  account: Account
  locale: Locale
  onChanged: (handle?: string) => Promise<void>
}

export function ProfileIdentityEditor({ account, locale, onChanged }: ProfileIdentityEditorProps) {
  const fileInput = useRef<HTMLInputElement | null>(null)
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(account.nome)
  const [handle, setHandle] = useState(account.handle)
  const [bio, setBio] = useState(account.bio)
  const [saving, setSaving] = useState(false)
  const [avatarBusy, setAvatarBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setName(account.nome)
    setHandle(account.handle)
    setBio(account.bio)
  }, [account.bio, account.handle, account.nome])

  function reset() {
    setName(account.nome)
    setHandle(account.handle)
    setBio(account.bio)
    setError(null)
    setNotice(null)
    setEditing(false)
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (saving) return
    const normalizedName = name.trim().replace(/\s+/g, ' ')
    const normalizedHandle = handle.trim().toLowerCase()
    const normalizedBio = bio.trim().replace(/\s+/g, ' ')

    if (normalizedName.length < 2 || normalizedName.length > 40) {
      setError('O nome deve ter entre 2 e 40 caracteres.')
      return
    }
    if (!/^[a-z0-9](?:[a-z0-9-]{1,22}[a-z0-9])$/.test(normalizedHandle)) {
      setError('Use de 3 a 24 letras, números ou hífens no nome de usuário.')
      return
    }
    if (normalizedBio.length > 160) {
      setError('A bio deve ter no máximo 160 caracteres.')
      return
    }

    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const result = await updateProfile({
        nome: normalizedName,
        handle: normalizedHandle,
        bio: normalizedBio,
      })
      await onChanged(result.handle)
      setNotice(result.message || profileText(locale, 'profile_saved'))
      setEditing(false)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : profileText(locale, 'profile_error'))
    } finally {
      setSaving(false)
    }
  }

  async function changeAvatar(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || avatarBusy) return
    setAvatarBusy(true)
    setError(null)
    setNotice(null)
    try {
      const prepared = await prepareAvatar(file)
      try {
        await uploadProfileAvatar(prepared.base64)
      } finally {
        URL.revokeObjectURL(prepared.previewUrl)
      }
      await onChanged()
      setNotice(profileText(locale, 'profile_saved'))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : profileText(locale, 'profile_error'))
    } finally {
      setAvatarBusy(false)
    }
  }

  async function removeAvatar() {
    if (avatarBusy) return
    setAvatarBusy(true)
    setError(null)
    setNotice(null)
    try {
      await removeProfileAvatar()
      await onChanged()
      setNotice(profileText(locale, 'profile_saved'))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : profileText(locale, 'profile_error'))
    } finally {
      setAvatarBusy(false)
    }
  }

  if (!account.logado) {
    return (
      <aside className="profile-login-card">
        <p>{profileText(locale, 'login_to_edit')}</p>
        <a className="button button--primary" href="/api/auth/google/login">Entrar com Google</a>
      </aside>
    )
  }

  return (
    <section className="profile-editor" aria-labelledby="profile-editor-title">
      {/* o avatar já aparece grande no hero logo acima; aqui ficam só os
          controles de foto, sem repetir a imagem */}
      <div className="profile-editor__avatar">
        <div>
          <input
            ref={fileInput}
            className="sr-only"
            type="file"
            accept="image/jpeg,image/png,image/webp,image/*"
            onChange={(event) => void changeAvatar(event)}
          />
          <div className="profile-editor__avatar-actions">
            <button
              className="button button--secondary"
              type="button"
              disabled={avatarBusy}
              onClick={() => fileInput.current?.click()}
            >
              {avatarBusy ? profileText(locale, 'avatar_processing') : profileText(locale, 'avatar_change')}
            </button>
            {account.avatar_custom && (
              <button
                className="text-button profile-editor__remove-avatar"
                type="button"
                disabled={avatarBusy}
                onClick={() => void removeAvatar()}
              >
                {profileText(locale, 'avatar_remove')}
              </button>
            )}
          </div>
          <small>{profileText(locale, 'avatar_hint')}</small>
        </div>
      </div>

      {!editing ? (
        <button className="button button--secondary" type="button" onClick={() => setEditing(true)}>
          {profileText(locale, 'edit_profile')}
        </button>
      ) : (
        <form className="profile-editor__form" onSubmit={submit}>
          <h2 id="profile-editor-title">{profileText(locale, 'edit_profile')}</h2>
          <label>
            <span>{profileText(locale, 'name')}</span>
            <input value={name} maxLength={40} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            <span>{profileText(locale, 'handle')}</span>
            <div className="profile-handle-input">
              <span>@</span>
              <input
                value={handle}
                maxLength={24}
                autoCapitalize="none"
                spellCheck={false}
                onChange={(event) => setHandle(event.target.value.replace(/\s+/g, '-').toLowerCase())}
              />
            </div>
          </label>
          <label>
            <span>{profileText(locale, 'bio')}</span>
            <textarea value={bio} rows={3} maxLength={160} onChange={(event) => setBio(event.target.value)} />
            <small>{profileText(locale, 'bio_hint')} · {bio.length}/160</small>
          </label>
          <div className="profile-editor__form-actions">
            <button className="button button--primary" type="submit" disabled={saving}>
              {saving ? '…' : profileText(locale, 'save_profile')}
            </button>
            <button className="button button--ghost" type="button" disabled={saving} onClick={reset}>
              {profileText(locale, 'cancel')}
            </button>
          </div>
        </form>
      )}

      {notice && <p className="profile-editor__notice" role="status">{notice}</p>}
      {error && <p className="profile-editor__error" role="alert">{error}</p>}
    </section>
  )
}
