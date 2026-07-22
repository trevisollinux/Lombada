/* Limpa o campo autor para exibição. Parte do catálogo tem o campo sujo com
   metadados concatenados na ingestão — ex.: "Fiódor Dostoiévski Autor: Fiódor
   Dostoievski Tradutor: Franci" — que estouram cards e dropdowns. Cortamos no
   primeiro marcador de papel (Autor/Tradutor/Editor…) e limitamos o tamanho.
   É defensivo: autor limpo passa intacto. */
const ROLE_MARKER = /\s+(?:Autor|Autora|Tradutor|Tradutora|Tradução|Translator|Author|Ilustrador|Organizador|Organizadora|Editor|Editora)\s*:/i

export function formatAuthor(raw: string | null | undefined, maxLength = 80): string {
  if (!raw) return ''
  let value = raw.split(ROLE_MARKER)[0].replace(/\s+/g, ' ').trim()
  if (value.length > maxLength) value = `${value.slice(0, maxLength - 1).trimEnd()}…`
  return value
}
