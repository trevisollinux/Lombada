const migrationSteps = [
  'Shell, tema, idioma e navegação',
  'Estante somente leitura',
  'Detalhe e mutações de leitura',
  'Diário de leitura',
  'Busca, obra e edições',
  'Explorar, feed e perfil',
  'Cards, retrospectiva e PWA',
] as const

export function App() {
  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Voltar para o Lombada atual">
          <span className="brand-mark" aria-hidden="true">
            L
          </span>
          <span className="wordmark">
            lombada<span>.</span>
          </span>
        </a>
        <span className="environment-label">app-v2 · fundação</span>
      </header>

      <section className="hero" aria-labelledby="migration-title">
        <p className="eyebrow">migração incremental</p>
        <h1 id="migration-title">
          O novo frontend começa <em>sem interromper a leitura.</em>
        </h1>
        <p className="hero-copy">
          Esta rota será a área segura de evolução do Lombada em React,
          TypeScript e Vite. O aplicativo atual continua sendo a experiência de
          produção até que exista paridade funcional.
        </p>
        <div className="hero-actions">
          <a className="primary-action" href="/">
            abrir aplicativo atual
          </a>
          <a
            className="secondary-action"
            href="https://github.com/trevisollinux/Lombada"
          >
            ver repositório
          </a>
        </div>
      </section>

      <section className="status-card" aria-labelledby="status-title">
        <div>
          <p className="eyebrow">estado desta entrega</p>
          <h2 id="status-title">Fundação técnica</h2>
        </div>
        <dl className="status-grid">
          <div>
            <dt>Frontend</dt>
            <dd>React 19 + TypeScript</dd>
          </div>
          <div>
            <dt>Build</dt>
            <dd>Vite</dd>
          </div>
          <div>
            <dt>Rota planejada</dt>
            <dd>/app-v2</dd>
          </div>
          <div>
            <dt>Produção atual</dt>
            <dd>inalterada</dd>
          </div>
        </dl>
      </section>

      <section className="roadmap" aria-labelledby="roadmap-title">
        <div className="section-heading">
          <p className="eyebrow">próximas etapas</p>
          <h2 id="roadmap-title">Migração por funcionalidades</h2>
        </div>
        <ol>
          {migrationSteps.map((step, index) => (
            <li key={step}>
              <span>{String(index + 1).padStart(2, '0')}</span>
              <p>{step}</p>
            </li>
          ))}
        </ol>
      </section>

      <footer>
        <p>
          Primeira fundação do frontend React. Nenhum fluxo legado foi removido.
        </p>
      </footer>
    </main>
  )
}
