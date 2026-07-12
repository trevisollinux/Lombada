# L2-012 — Funil de ativação e retenção

Issue: #291 · Parent: #277

Esta branch transforma eventos agregados em métricas de ativação e retenção, mantendo coleta e painel desligados por padrão.

## Entregas

- [ ] Definições formais de usuário ativo, ativação e coorte.
- [ ] Instrumentação dos marcos essenciais atrás de feature flag.
- [ ] Funil de ativação em 24h e 7d.
- [ ] WAU e retenção D1/D7/D30.
- [ ] Exclusão de usuários demo.
- [ ] Agregação sem exposição de eventos individuais.
- [ ] Painel administrativo protegido por flag interna.
- [ ] Testes das fórmulas e do controle de acesso.
- [ ] CI verde e revisão final.

## Critério de saída

Com as flags desligadas, o aplicativo mantém o comportamento atual e o painel não fica acessível. Com as flags ligadas, somente métricas agregadas aparecem para o administrador.
