# Decisões arquiteturais

## ADR-001 — Migração incremental do frontend para React

- **Status:** aprovada para execução incremental
- **Data:** 12 de julho de 2026
- **Decisão:** usar React + TypeScript + Vite no frontend interativo, preservando FastAPI, PostgreSQL, APIs, páginas públicas e identidade visual.
- **Estratégia:** migração por funcionalidades, mantendo o frontend legado disponível como fallback até a paridade.
- **Documento detalhado:** [Avaliação arquitetural e plano de migração do frontend para React](./migracao-frontend-react.md)
