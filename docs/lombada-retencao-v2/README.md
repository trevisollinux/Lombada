# Lombada 2.0 — ritual de leitura, identidade e retenção

Este documento registra a direção aprovada para a próxima fase do produto.

## Baseline preservado

- Commit estável: `da505b3df7ac530b0420998f43c8938f00f9f246`
- Branch de recuperação: `baseline/pre-retencao-v2-2026-07-11`
- Issue de acompanhamento: #277

Nenhuma mudança desta fase deve exigir migração destrutiva. Toda funcionalidade nova deve nascer atrás de feature flag, e o fluxo anterior deve permanecer utilizável durante o rollout.

## Objetivo

Organizar o Lombada em torno do ciclo:

> Ler fora do aplicativo → registrar em poucos segundos → receber progresso e significado → compartilhar ou interagir → criar expectativa para a próxima leitura.

A métrica principal será **eventos significativos de leitura por usuário ativo semanal**, não tempo de tela.

## O que já existe

O projeto já possui catálogo e busca avançada, cadastro manual, estante, diário com progresso, perfil público, feed social, seguidores, curtidas, comentários, notificações, PWA, autenticação anônima/Google, temas, idiomas, cards, retrospectiva e micro-recompensas.

A fase 2.0 não deve duplicar esses recursos. Deve conectá-los num ritual coerente.

## Motores do produto

1. **Ritual:** “Li mais” como ação principal, com atualização em poucos segundos.
2. **Identidade:** quatro essenciais e retrato do leitor.
3. **Memória:** recaps mensais, anuais e snapshots compartilháveis.
4. **Vínculo:** reações literárias, comentários por progresso e afinidade entre leitores.
5. **Consistência:** ritmo semanal gentil, conquistas editoriais e notificações opt-in.

## Ordem recomendada

1. Segurança, backup, feature flags e métricas.
2. Ritual de progresso e home centrada na leitura atual.
3. Onboarding, quatro essenciais e retrato do leitor.
4. Retrospectivas por período.
5. Reações, feed finito e comentários desbloqueados por progresso.
6. Ritmo semanal, conquistas e preferências.
7. Gêmeo de leitura e recomendações explicadas.

## Regras de produto

- Sem feed infinito.
- Sem streak punitivo.
- Sem ranking global.
- Sem moedas, vidas ou recompensa apenas por abrir o app.
- Sem push antes de consentimento e preferências.
- Toda recompensa deve seguir uma ação real de leitura.

## Primeiro pacote para implementação

1. Feature flags, sem mudança visual quando desligadas.
2. Campos aditivos de sessão no diário.
3. Serviço e endpoint de resumo de progresso.
4. Sheet “Li mais” reutilizando o diário atual.
5. Card “Continue sua leitura” atrás de flag.

## Definition of Done

Uma entrega só é concluída quando possui critério de aceite, testes proporcionais ao risco, estados de loading/vazio/erro, compatibilidade mobile/desktop, claro/escuro, PT/EN/ES, redução de movimento, privacidade, smoke pós-deploy e instrução de rollback.

O backlog marcável e os critérios detalhados estão na issue #277. O PRD completo e o backlog granular também são mantidos como artefatos de planejamento para consulta durante os PRs.